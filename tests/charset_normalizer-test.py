import io
import os
import tempfile
import unittest
from charset_normalizer import from_bytes, from_path, from_fp, detect

class TestCharsetNormalizerBasics(unittest.TestCase):
    def setUp(self):
        # Sample texts in different scripts/encodings
        self.text_utf8 = "café – résumé € snowman ☃"
        # Bulgarian sentence from docs (Cyrillic)
        self.text_cp1251 = "Всеки човек има право на образование."
        # Make temp files with controlled encodings
        self.tmpdir = tempfile.TemporaryDirectory()
        self.utf8_bom_path = os.path.join(self.tmpdir.name, "utf8_bom.txt")
        self.cp1251_path = os.path.join(self.tmpdir.name, "cyrillic_cp1251.txt")

        with open(self.utf8_bom_path, "wb") as f:
            f.write(self.text_utf8.encode("utf-8-sig"))  # UTF-8 with BOM

        with open(self.cp1251_path, "wb") as f:
            f.write(self.text_cp1251.encode("cp1251"))

    def tearDown(self):
        self.tmpdir.cleanup()

    # ---------- detect() (chardet-compatible shim) ----------
    def test_detect_on_bytes(self):
        payload = self.text_utf8.encode("utf-8")
        result = detect(payload)
        self.assertIsInstance(result, dict)
        self.assertIn("encoding", result)
        self.assertIsNotNone(result["encoding"])
        # Decoding with detected encoding should not raise and should roundtrip
        decoded = payload.decode(result["encoding"], errors="strict")
        self.assertEqual(decoded, self.text_utf8)

    # ---------- from_bytes ----------
    def test_from_bytes_best_and_match_basics(self):
        payload = self.text_utf8.encode("utf-8")
        matches = from_bytes(payload)
        self.assertTrue(matches)  # list-like truthiness
        self.assertGreaterEqual(len(matches), 1)

        best = matches.best()
        self.assertIsNotNone(best)
        # Best should decode to the original text
        self.assertEqual(str(best), self.text_utf8)

        # list-like: first() is alias of best()
        self.assertIs(best, matches.first())

        # Access via index returns a CharsetMatch
        self.assertIs(best, matches[0])

        # Common properties should be present with expected types
        self.assertIsInstance(best.encoding, str)
        self.assertIsInstance(best.language, str)  # may be "Unknown"
        self.assertIsInstance(best.could_be_from_charset, list)
        self.assertIsInstance(best.encoding_aliases, list)
        self.assertIsInstance(best.fingerprint, str)
        self.assertIsInstance(best.raw, (bytes, bytearray))

        # raw equals original bytes for from_bytes()
        self.assertEqual(best.raw, payload)

        # Re-encode output() to UTF-8 and compare to original text
        out = best.output(encoding="utf_8")
        self.assertIsInstance(out, (bytes, bytearray))
        self.assertEqual(out.decode("utf-8"), self.text_utf8)

    def test_from_bytes_with_options_and_isolation(self):
        payload = self.text_utf8.encode("utf-8")
        # Limit search space to UTF-8 to ensure options path is exercised
        matches = from_bytes(
            payload,
            steps=5,
            chunk_size=256,
            threshold=0.3,
            cp_isolation=["utf_8", "utf_8_sig"],
            cp_exclusion=None,
            preemptive_behaviour=True,
            explain=False,
            language_threshold=0.05,
        )
        best = matches.best()
        self.assertIsNotNone(best)
        self.assertIn(best.encoding.lower().replace("-", "_"), {"utf_8", "utf_8_sig"})
        self.assertEqual(str(best), self.text_utf8)

    # ---------- from_path ----------
    def test_from_path_utf8_bom(self):
        matches = from_path(self.utf8_bom_path)
        self.assertTrue(matches)
        best = matches.best()
        self.assertIsNotNone(best)
        # Should decode to original string regardless of BOM handling
        self.assertEqual(str(best), self.text_utf8)

        # raw should equal the original file bytes
        with open(self.utf8_bom_path, "rb") as f:
            original_bytes = f.read()
        self.assertEqual(best.raw, original_bytes)

    def test_from_path_cp1251(self):
        matches = from_path(self.cp1251_path)
        self.assertTrue(matches)
        best = matches.best()
        self.assertIsNotNone(best)
        # Decoded text must match what we wrote
        self.assertEqual(str(best), self.text_cp1251)
        # Encoding should be cp1251 or an alias that roundtrips identically
        self.assertIn("cp1251", best.could_be_from_charset + [best.encoding.lower()])

    # ---------- from_fp ----------
    def test_from_fp_binary_stream(self):
        with open(self.cp1251_path, "rb") as f:
            matches = from_fp(f)
        self.assertTrue(matches)
        self.assertEqual(str(matches.best()), self.text_cp1251)

    # ---------- CharsetMatches iteration semantics ----------
    def test_matches_iteration_and_membership(self):
        payload = ("ASCII only line\n" * 3).encode("ascii")
        matches = from_bytes(payload)
        self.assertTrue(matches)

        # Iteration yields CharsetMatch objects; the first is best()
        encodings_seen = []
        for i, m in enumerate(matches):
            self.assertIsNotNone(m.encoding)
            encodings_seen.append(m.encoding.lower())

        self.assertIn(matches.best().encoding.lower(), [e for e in encodings_seen])

    def test_empty_input_returns_sensible_result(self):
        matches = from_bytes(b"")
        self.assertIsNotNone(matches)
    
        best = matches.best()
    
        # Some versions return None; others return a valid "empty" match (often UTF-8/ASCII).
        if best is None:
            # Nothing more to assert — absence of a best match is acceptable.
            return
    
        # If a match is returned, it should decode to an empty string and have empty raw bytes.
        self.assertEqual(str(best), "")
        self.assertEqual(best.raw, b"")
        self.assertIn(best.encoding.lower().replace("-", "_"), {"utf_8", "ascii", "utf_8_sig"})
        # Re-encoding an empty payload should remain empty
        self.assertEqual(best.output(), b"")

    def test_empty_input_returns_utf8_empty_match(self):
        matches = from_bytes(b"")
        self.assertTrue(matches)                      # container is truthy
        best = matches.best()
        self.assertIsNotNone(best)                    # a real match is returned
        self.assertEqual(best.encoding.lower(), "utf_8")
        self.assertEqual(best.raw, b"")               # original payload is empty
        self.assertEqual(str(best), "")               # decoded string is empty
        self.assertEqual(best.output(), b"")          # re-encoding stays empty

    def test_invalid_bytes_still_handles_gracefully(self):
        # Create bytes that are invalid in many encodings
        junk = b"\xff\xfe\xfa\xfb\xfc\xfd" * 10
        matches = from_bytes(junk)
        # We only assert that API doesn't crash and returns a container
        self.assertIsNotNone(matches)
        # best() may be None or some guess; just call it to ensure no exception
        _ = matches.best()


if __name__ == "__main__":
    unittest.main()