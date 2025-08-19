# tests/test_pypandoc_module.py
import os
import tempfile
import unittest
import logging
from pathlib import Path
from contextlib import contextmanager

try:
    import pypandoc
except Exception as e:  # pragma: no cover
    raise RuntimeError("pypandoc must be importable to run these tests") from e


# ---------- helpers ----------

def _pandoc_available():
    """Return True if pypandoc can find and execute a pandoc binary."""
    try:
        _ = pypandoc.get_pandoc_version()
        return True
    except Exception:
        return False


def _pandoc_has_format(fmt: str, direction: str = "to"):
    """
    Best-effort check whether pandoc supports a specific format either
    as input ("from") or output ("to"). Returns True/False/None (unknown).
    """
    try:
        formats = pypandoc.get_pandoc_formats()
    except Exception:
        return None

    # pypandoc historically returned either a tuple (from_list, to_list)
    # or a dict-like object; support both.
    from_formats = None
    to_formats = None
    if isinstance(formats, (list, tuple)) and len(formats) >= 2:
        from_formats, to_formats = formats[0], formats[1]
    elif isinstance(formats, dict):
        from_formats = formats.get("from") or formats.get("input") or []
        to_formats = formats.get("to") or formats.get("output") or []
    else:
        return None

    if direction == "from":
        return fmt in from_formats
    return fmt in to_formats


@contextmanager
def temp_cwd():
    old = os.getcwd()
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as d:
        os.chdir(d)
        try:
            yield Path(d)
        finally:
            os.chdir(old)


# ---------- tests ----------

class TestEnvironmentAndLogging(unittest.TestCase):
    def test_logging_can_be_silenced(self):
        # Should not raise even if called before any pypandoc function
        logging.getLogger('pypandoc').addHandler(logging.NullHandler())

    def test_env_pandoc_path_missing_behaviour(self):
        """
        If PYPANDOC_PANDOC points to a missing binary, pypandoc should either:
          1) Honor it and fail on use, OR
          2) Ignore it (e.g., when a bundled binary takes precedence) and still work.
        Both are acceptable across supported installs; we assert one of these holds.
        """
        fake = os.path.join(tempfile.gettempdir(), "no_such_pandoc___does_not_exist")
        prev = os.environ.get("PYPANDOC_PANDOC")
        try:
            os.environ["PYPANDOC_PANDOC"] = fake

            failed = False
            try:
                pypandoc.convert_text("# Title", to="html", format="md")
            except Exception:
                failed = True

            if failed:
                # Env var was honored -> we failed as expected.
                self.assertTrue(failed)
            else:
                # Env var was ignored; ensure pypandoc can still convert.
                out = pypandoc.convert_text("# Title", to="html", format="md")
                self.assertIn("<h1", out)
        finally:
            if prev is None:
                os.environ.pop("PYPANDOC_PANDOC", None)
            else:
                os.environ["PYPANDOC_PANDOC"] = prev


@unittest.skipUnless(_pandoc_available(), "pandoc is not available; skipping integration tests")
class TestUtilityFunctions(unittest.TestCase):
    def test_get_pandoc_version_returns_something(self):
        v = pypandoc.get_pandoc_version()
        self.assertTrue(str(v))
        self.assertRegex(str(v), r"^\d+\.\d+")

    def test_get_pandoc_path_points_to_binary(self):
        path = pypandoc.get_pandoc_path()
        self.assertTrue(path)
        self.assertTrue(Path(path).name.lower().startswith("pandoc"))

    def test_get_pandoc_formats_has_common_ones(self):
        formats = pypandoc.get_pandoc_formats()
        if isinstance(formats, (list, tuple)):
            self.assertGreaterEqual(len(formats), 2)
            from_fmts, to_fmts = formats[0], formats[1]
        else:
            from_fmts = formats.get("from") or formats.get("input") or []
            to_fmts = formats.get("to") or formats.get("output") or []

        self.assertIn("markdown", from_fmts)
        self.assertTrue(any(f in to_fmts for f in ("html", "html5", "gfm", "commonmark")))


@unittest.skipUnless(_pandoc_available(), "pandoc is not available; skipping integration tests")
class TestConvertText(unittest.TestCase):
    def test_convert_text_html_to_md_with_extra_args(self):
        html = "<h1>Primary Heading</h1>"

        # Prefer modern flag; fall back to legacy if running against older pandoc
        try:
            out = pypandoc.convert_text(
                html, to="md", format="html",
                extra_args=["--markdown-headings=atx"]
            )
        except RuntimeError as e:
            if "Unknown option" in str(e) or "Unknown" in str(e):
                out = pypandoc.convert_text(
                    html, to="md", format="html",
                    extra_args=["--atx-headers"]  # legacy
                )
            else:
                raise

        self.assertIn("# Primary Heading", out)

    def test_convert_text_md_to_html_with_extra_args(self):
        md = "# Primary Heading"
        out = pypandoc.convert_text(
            md, to="html", format="md",
            extra_args=["--shift-heading-level-by=1"]
        )
        self.assertIn("<h2", out)
        self.assertIn("Primary Heading", out)

    def test_convert_text_accepts_utf8_bytes_and_returns_str(self):
        md = "# Título".encode("utf-8")
        out = pypandoc.convert_text(md, to="html", format="md")
        self.assertIsInstance(out, str)
        self.assertIn("Título", out)


@unittest.skipUnless(_pandoc_available(), "pandoc is not available; skipping integration tests")
class TestConvertFile(unittest.TestCase):
    def test_convert_file_infer_input_format_and_override(self):
        with temp_cwd() as d:
            p = d / "somefile.md"
            p.write_text("# Hello\n\nThis is *markdown*.\n", encoding="utf-8")

            # Let pandoc infer from .md
            out_inferred = pypandoc.convert_file(str(p), to="rst")
            self.assertIsInstance(out_inferred, str)
            self.assertIn("Hello", out_inferred)

            # Override format explicitly even if extension is .txt
            p_txt = d / "somefile.txt"
            p_txt.write_text("# Hi\n\nThis is **bold**.\n", encoding="utf-8")
            out_overridden = pypandoc.convert_file(str(p_txt), to="html", format="md")
            self.assertIn("<strong>bold</strong>", out_overridden)

    def test_convert_file_outputfile_returns_empty_string_and_creates_file(self):
        with temp_cwd() as d:
            p = d / "page.md"
            p.write_text("# Title\n\nBody.\n", encoding="utf-8")

            out_path = d / "page.html"
            ret = pypandoc.convert_file(str(p), to="html", outputfile=str(out_path))
            self.assertEqual(ret, "")
            self.assertTrue(out_path.exists())
            self.assertGreater(out_path.stat().st_size, 0)

    def test_convert_file_multiple_inputs_glob_and_list(self):
        with temp_cwd() as d:
            (d / "chapters").mkdir()
            for i in range(3):
                (d / "chapters" / f"c{i}.md").write_text(f"# Chapter {i}\n\nBody.\n", encoding="utf-8")

            out = d / "book.html"
            # pattern string
            ret = pypandoc.convert_file("chapters/*.md", to="html", outputfile=str(out))
            self.assertEqual(ret, "")
            self.assertTrue(out.exists())

            # list of patterns
            out2 = d / "book2.html"
            ret2 = pypandoc.convert_file(["chapters/*.md"], to="html", outputfile=str(out2))
            self.assertEqual(ret2, "")
            self.assertTrue(out2.exists())

    def test_convert_file_with_pathlib_inputs(self):
        with temp_cwd() as d:
            (d / "book1").mkdir()
            (d / "book2").mkdir()
            for folder in ("book1", "book2"):
                for i in range(2):
                    (d / folder / f"{folder}_{i}.md").write_text(f"# {folder} {i}\n\nBody.\n", encoding="utf-8")

            # single Path
            single_in = d / "book1" / "book1_0.md"
            single_out = single_in.with_suffix(".html")
            ret = pypandoc.convert_file(single_in, to="html", outputfile=single_out)
            self.assertEqual(ret, "")
            self.assertTrue(single_out.exists())

            # glob iterator
            glob_out = d / "globbed.html"
            ret2 = pypandoc.convert_file((d / "book1").glob("*.md"), to="html", outputfile=glob_out)
            self.assertEqual(ret2, "")
            self.assertTrue(glob_out.exists())

            # list of unpacked globs
            combo_out = d / "combo.html"
            inputs = [*(d / "book1").glob("*.md"), *(d / "book2").glob("*.md")]
            ret3 = pypandoc.convert_file(inputs, to="html", outputfile=combo_out)
            self.assertEqual(ret3, "")
            self.assertTrue(combo_out.exists())

    def test_extra_args_variable_flag_list_splitting(self):
        # Use html writer with a standalone document so we actually get a <head>/<title>.
        with temp_cwd() as d:
            src = d / "demo.md"
            src.write_text("# Title\n\nBody.\n", encoding="utf-8")
            out = d / "demo.html"

            # Exercise “split args” behavior with --metadata which must be split
            # (analogous to -V). Also add --standalone so the title is emitted.
            ret = pypandoc.convert_file(
                str(src), to="html", outputfile=str(out),
                extra_args=["--standalone", "--metadata", "pagetitle=Custom Page Title"]
            )
            self.assertEqual(ret, "")
            txt = out.read_text(encoding="utf-8")

            self.assertTrue(
                "Custom Page Title" in txt,
                msg=f"'Custom Page Title' not found in output:\n{txt[:2000]}"
            )


@unittest.skipUnless(
    _pandoc_available() and bool(os.environ.get("PYPANDOC_TEST_FILTERS")),
    "pandoc or filters not available; set PYPANDOC_TEST_FILTERS=1 to enable"
)
class TestFiltersOptional(unittest.TestCase):
    def test_filters_argument_accepts_list_and_runs(self):
        with temp_cwd() as d:
            src = d / "f.md"
            src.write_text("# Ref\n\nSome text.\n", encoding="utf-8")
            out = d / "f.html"
            ret = pypandoc.convert_file(
                str(src), to="html", outputfile=str(out),
                format="md",
                filters=["pandoc-citeproc"]  # must be installed in env for this test
            )
            self.assertEqual(ret, "")
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)


# ---------- edge cases & regressions ----------

@unittest.skipUnless(_pandoc_available(), "pandoc is not available; skipping integration tests")
class TestEdgeCases(unittest.TestCase):
    def test_outputfile_is_only_way_for_certain_formats(self):
        # Some writers (e.g., ODT/DOCX/EPUB) require writing to a file.
        # Prefer 'odt' or 'docx' which don't need a LaTeX install.
        preferred = None
        for candidate in ("docx", "odt", "epub"):
            if _pandoc_has_format(candidate, direction="to"):
                preferred = candidate
                break
        if preferred is None:
            self.skipTest("No binary output writer available (docx/odt/epub)")

        with temp_cwd() as d:
            md = d / "x.md"
            md.write_text("# Title\n\nBody.\n", encoding="utf-8")
            out = d / f"x.{preferred}"
            ret = pypandoc.convert_file(str(md), to=preferred, outputfile=str(out))
            self.assertEqual(ret, "")
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)


if __name__ == "__main__":
    # Allow running this file directly: `python -m unittest tests/test_pypandoc_module.py -v`
    unittest.main(verbosity=2)