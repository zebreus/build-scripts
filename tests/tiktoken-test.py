import unittest
import tiktoken

class TestTiktokenBasics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use a widely available modern base encoding
        cls.enc = tiktoken.get_encoding("o200k_base")

    def test_get_encoding_roundtrip_ascii(self):
        text = "hello world"
        tokens = self.enc.encode(text)
        self.assertIsInstance(tokens, list)
        self.assertTrue(all(isinstance(t, int) for t in tokens))
        self.assertEqual(self.enc.decode(tokens), text)

    def test_get_encoding_roundtrip_unicode(self):
        # Mix emoji, accented chars, and CJK to ensure robust handling
        text = "Café 😊 — 你好，世界"
        tokens = self.enc.encode(text)
        decoded = self.enc.decode(tokens)
        self.assertEqual(decoded, text)

    def test_encoding_for_model_returns_encoding(self):
        # Ensure lookup works and returns an Encoding instance
        enc_for_model = tiktoken.encoding_for_model("gpt-4o")
        self.assertIsNotNone(enc_for_model)
        # roundtrip with that encoding too
        text = "Model-based encoding roundtrip ✅"
        self.assertEqual(enc_for_model.decode(enc_for_model.encode(text)), text)

    def test_special_token_handling(self):
        # Common special token used by many encodings
        special = "<|endoftext|>"
        text_with_special = f"before {special} after"

        # By default, disallowed specials should raise when present
        with self.assertRaises(Exception):
            _ = self.enc.encode(text_with_special)

        # Allow specials explicitly: should not raise
        toks_allowed = self.enc.encode(text_with_special, allowed_special={special})
        self.assertIsInstance(toks_allowed, list)
        # Decoding should roundtrip even with specials present
        self.assertEqual(self.enc.decode(toks_allowed), text_with_special)

        # Allow all specials: also should not raise
        toks_all = self.enc.encode(text_with_special, allowed_special="all")
        self.assertEqual(self.enc.decode(toks_all), text_with_special)

    def test_decode_empty(self):
        self.assertEqual(self.enc.decode([]), "")

    def test_unknown_encoding_raises(self):
        # Some tiktoken versions used KeyError; 0.8.0 uses ValueError.
        with self.assertRaises((KeyError, ValueError)):
            tiktoken.get_encoding("this_encoding_does_not_exist")

    def test_encode_types_are_ints(self):
        txt = "type checks"
        toks = self.enc.encode(txt)
        self.assertTrue(all(isinstance(t, int) for t in toks))


if __name__ == "__main__":
    unittest.main()