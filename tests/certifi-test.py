# test_certifi_intense.py
import os
import ssl
import sys
import subprocess
import unittest
from pathlib import Path

import certifi


def _run_certifi_module(*args, check=True):
    """Run `python -m certifi [args...]` and return (stdout, stderr, returncode)."""
    proc = subprocess.run(
        [sys.executable, "-m", "certifi", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"`python -m certifi {' '.join(args)}` failed "
            f"(code {proc.returncode}):\nSTDERR:\n{proc.stderr}"
        )
    return proc.stdout, proc.stderr, proc.returncode


class TestCertifiIntense(unittest.TestCase):
    # ---------- File & content invariants ----------
    def test_where_points_to_real_pem_with_many_certs(self):
        path = certifi.where()
        self.assertIsInstance(path, str)
        p = Path(path)
        self.assertTrue(p.is_absolute(), "certifi.where() should be absolute")
        self.assertTrue(p.exists(), "certifi.where() path does not exist")
        self.assertTrue(p.is_file(), "certifi.where() did not return a file")

        text = p.read_text(encoding="utf-8", errors="ignore")
        self.assertGreater(len(text), 0, "CA bundle is empty")
        self.assertIn("BEGIN CERTIFICATE", text, "PEM cert header not found")
        # Count certs; should be more than just a few (keep threshold conservative)
        cert_count = text.count("BEGIN CERTIFICATE")
        self.assertGreaterEqual(cert_count, 10, f"Unexpectedly few certs: {cert_count}")
        # Size sanity (typical bundles are > 100KB; keep conservative)
        self.assertGreater(p.stat().st_size, 50 * 1024, "Bundle seems unusually small")

    def test_cli_prints_same_path_and_resolves(self):
        expected = Path(certifi.where()).resolve()
        out, err, code = _run_certifi_module()
        self.assertEqual(code, 0, "CLI exited non-zero")
        first_line = next((ln for ln in out.splitlines() if ln.strip()), "")
        self.assertTrue(first_line, "No CLI output")
        cli_path = Path(first_line.strip()).resolve()
        self.assertEqual(cli_path, expected, "CLI path != certifi.where() (after resolve)")

    # ---------- SSLContext loading paths ----------
    def test_ssl_context_loads_with_cafile_str_and_path(self):
        cafile = certifi.where()

        # Load via str
        ctx1 = ssl.create_default_context(cafile=cafile)
        self.assertEqual(ctx1.verify_mode, ssl.CERT_REQUIRED)
        ctx1.load_verify_locations(cafile=cafile)  # re-load should not raise

        # Load via Path
        cafile_path = Path(cafile)
        ctx2 = ssl.create_default_context(cafile=str(cafile_path))  # create_default_context needs str for cafile
        self.assertEqual(ctx2.verify_mode, ssl.CERT_REQUIRED)
        # But load_verify_locations *does* accept Path in modern Pythons; try both for completeness
        ctx2.load_verify_locations(cafile=cafile_path)  # should not raise

    def test_loading_via_cadata_when_available(self):
        contents_fn = getattr(certifi, "contents", None)
        if contents_fn is None:
            self.skipTest("certifi.contents() not available in this version")
        pem_text = contents_fn()
        self.assertIsInstance(pem_text, str)
        self.assertIn("BEGIN CERTIFICATE", pem_text)
        # Create a context and load via cadata (string PEM)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_verify_locations(cadata=pem_text)  # should not raise

    # ---------- CLI features ----------
    def test_cli_contents_mode_if_supported(self):
        # Not all historic builds support --contents; handle gracefully.
        out, err, code = _run_certifi_module("--contents", check=False)
        if code != 0:
            self.skipTest("`python -m certifi --contents` not supported in this build")
        self.assertIn("BEGIN CERTIFICATE", out)
        # Keep the check moderate; ensure it's not trivially short
        self.assertGreater(len(out), 50 * 1024, "CLI --contents output seems too small")

    # ---------- Consistency checks ----------
    def test_contents_matches_disk_loosely_when_available(self):
        contents_fn = getattr(certifi, "contents", None)
        if contents_fn is None:
            self.skipTest("certifi.contents() not available in this version")
        from_file = Path(certifi.where()).read_text(encoding="utf-8", errors="ignore")
        from_api = contents_fn()

        # Normalize newlines for a fairer comparison across platforms
        def norm(s: str) -> str:
            return s.replace("\r\n", "\n").replace("\r", "\n")

        nf, na = norm(from_file), norm(from_api)
        # They often match exactly, but allow small differences (whitespace, ordering across releases).
        self.assertTrue(
            abs(len(na) - len(nf)) < max(2048, int(len(nf) * 0.05)),
            "contents() length differs significantly from file contents",
        )
        # Ensure both contain many certs
        self.assertGreaterEqual(na.count("BEGIN CERTIFICATE"), 10)
        self.assertGreaterEqual(nf.count("BEGIN CERTIFICATE"), 10)

    def test_version_field_shape_and_is_strictly_string_if_present(self):
        ver = getattr(certifi, "__version__", None)
        # Some builds may not expose __version__; if present, it must be a string & non-empty.
        if ver is not None:
            self.assertIsInstance(ver, str)
            self.assertTrue(ver.strip(), "__version__ is empty string")


if __name__ == "__main__":
    unittest.main(verbosity=2)