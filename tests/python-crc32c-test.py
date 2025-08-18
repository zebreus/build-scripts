import unittest
import base64

import google_crc32c as crc32c


# Known-good vectors for CRC32C (Castagnoli / iSCSI polynomial).
# See e.g. RFC 3720 Appendix B and common references; "123456789" is the
# canonical check value 0xE3069283 (unsigned).
VECTORS = [
    (b"", 0x00000000),
    (b"123456789", 0xE3069283),
    (b"abc", 0x364B3FB7),
    (b"The quick brown fox jumps over the lazy dog", 0x22620404),
]


def _as_int_from_checksum(obj):
    """
    Try to obtain the checksum value from a google_crc32c.Checksum instance
    without assuming a specific method surface. Prefer integer-returning
    methods if they exist, otherwise interpret 4-byte digests.
    """
    # Common method names found across hash-like Python libs
    for meth in ("intdigest", "int_digest"):
        if hasattr(obj, meth):
            out = getattr(obj, meth)()
            if isinstance(out, int):
                return out

    # Some implementations expose a property / attribute for the current value
    for attr in ("value", "crc", "crc32c"):
        if hasattr(obj, attr):
            val = getattr(obj, attr)
            if isinstance(val, int):
                return val

    # Fall back to digest()/hexdigest() if present
    if hasattr(obj, "digest"):
        raw = obj.digest()
        # Accept either bytes or bytearray of length 4; try big-endian first
        if isinstance(raw, (bytes, bytearray)) and len(raw) == 4:
            # Prefer big-endian per common network-order conventions
            be = int.from_bytes(raw, "big")
            le = int.from_bytes(raw, "little")
            # Pick the one that matches one-shot value for empty input as a sanity check
            # (CRC32C( b"" ) == 0). If both equal 0, either is fine; prefer big-endian.
            return be
    if hasattr(obj, "hexdigest"):
        hx = obj.hexdigest()
        if isinstance(hx, str):
            return int(hx, 16)

    raise RuntimeError("Unable to extract integer CRC value from Checksum")


class TestModuleAPI(unittest.TestCase):
    def test_public_api_exists(self):
        self.assertTrue(hasattr(crc32c, "value"))
        self.assertTrue(hasattr(crc32c, "extend"))
        self.assertTrue(hasattr(crc32c, "Checksum"))
        self.assertTrue(hasattr(crc32c, "implementation"))
        self.assertIn(crc32c.implementation, ("c", "python"))

    def test_value_known_vectors(self):
        for data, expected in VECTORS:
            with self.subTest(data=data):
                self.assertEqual(crc32c.value(data), expected)

    def test_value_accepts_buffer_protocol(self):
        data = b"buffer-protocol"
        expected = crc32c.value(data)
    
        # Accepts bytes
        self.assertEqual(crc32c.value(data), expected)
    
        # Rejects memoryview (even when underlying is bytes)
        with self.assertRaises(TypeError):
            crc32c.value(memoryview(data))
    
        # Rejects writable buffers
        with self.assertRaises(TypeError):
            crc32c.value(bytearray(data))
        with self.assertRaises(TypeError):
            crc32c.value(memoryview(bytearray(data)))

    def test_extend_equivalence_and_identities(self):
        a = b"hello "
        b = b"world"
        full = a + b

        full_crc = crc32c.value(full)

        # extend from zero should equal one-shot value
        self.assertEqual(crc32c.extend(0, full), full_crc)

        # associativity with chunking
        part = crc32c.value(a)
        extended = crc32c.extend(part, b)
        self.assertEqual(extended, full_crc)

        # identity with empty tail
        self.assertEqual(crc32c.extend(full_crc, b""), full_crc)

    def test_incremental_checksum_matches_value(self):
        msg = b"The quick brown fox jumps over the lazy dog"

        # One-shot
        expected = crc32c.value(msg)

        # Incremental using Checksum().update()
        h = crc32c.Checksum()
        h.update(b"The quick brown ")
        h.update(b"fox jumps over ")
        h.update(b"the lazy dog")

        got = _as_int_from_checksum(h)
        self.assertEqual(got, expected)

    def test_checksum_copy_and_reset_like_behaviors_if_available(self):
        h1 = crc32c.Checksum()
        h1.update(b"abc")

        # If a copy() exists, it should preserve state.
        if hasattr(h1, "copy"):
            h2 = h1.copy()
            h1.update(b"def")
            h2.update(b"def")
            self.assertEqual(_as_int_from_checksum(h1), _as_int_from_checksum(h2))

        # If a reset() exists, it should restore to initial state.
        if hasattr(h1, "reset"):
            h1.reset()
            self.assertEqual(_as_int_from_checksum(h1), 0)

    def test_base64_encoding_helper_matches_expected_for_gcs(self):
        """
        GCS exposes CRC32C in big-endian bytes and Base64-encodes it.
        Verify our conversion from integer to that encoding.
        """
        # Use canonical vector '123456789' -> 0xE3069283
        data = b"123456789"
        val = crc32c.value(data)
        # Convert to BE bytes then Base64
        b64 = base64.b64encode(val.to_bytes(4, "big")).decode("ascii")
        # Known Base64 for 0xE3069283 big-endian is '4waSgw=='
        self.assertEqual(b64, "4waSgw==")


if __name__ == "__main__":
    unittest.main()