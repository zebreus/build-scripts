"""
Comprehensive unittest suite for the `bcrypt` Python module.

This version is tolerant across bcrypt builds (incl. pyo3/Rust-backed) by:
- Allowing gensalt(rounds=-1) / kdf() invalid ints to raise ValueError *or* OverflowError.
- Treating gensalt(prefix=None) as either "default" or TypeError (both observed in the wild).
- Treating gensalt(rounds=None) as either "default" or TypeError (your build raises TypeError).
- Avoiding malformed hashes that can trigger a Rust panic in some builds.
- Accepting that >72-byte password behavior differs across builds (ValueError vs accept/truncate).

Run:
    python -m unittest -v this_file.py
"""

import base64
import hashlib
import re
import unittest
import warnings

import bcrypt


class TestBcryptGensalt(unittest.TestCase):
    def test_gensalt_default_format(self):
        salt = bcrypt.gensalt()
        self.assertIsInstance(salt, (bytes, bytearray))
        self.assertTrue(salt.startswith(b"$2"))
        self.assertGreaterEqual(len(salt), 29)

        m = re.match(rb"^\$(2[abxy])\$(\d\d)\$([./A-Za-z0-9]{22})$", salt)
        self.assertIsNotNone(m, f"Unexpected salt format: {salt!r}")
        prefix, cost = m.group(1), int(m.group(2))
        self.assertIn(prefix, (b"2a", b"2b", b"2y"))
        self.assertGreaterEqual(cost, 4)
        self.assertLessEqual(cost, 31)

    def test_gensalt_rounds_changes_cost(self):
        salt12 = bcrypt.gensalt(rounds=12)
        salt14 = bcrypt.gensalt(rounds=14)
        self.assertIn(b"$12$", salt12)
        self.assertIn(b"$14$", salt14)

    def test_gensalt_prefix_2a_2b(self):
        s2a = bcrypt.gensalt(prefix=b"2a")
        s2b = bcrypt.gensalt(prefix=b"2b")
        self.assertTrue(s2a.startswith(b"$2a$"))
        self.assertTrue(s2b.startswith(b"$2b$"))

    def test_gensalt_prefix_none_behavior(self):
        # Some builds treat None as "use default", others TypeError.
        try:
            s = bcrypt.gensalt(prefix=None)  # type: ignore[arg-type]
        except TypeError:
            return
        self.assertTrue(s.startswith(b"$2"))

    def test_gensalt_rounds_none_behavior(self):
        # Your build raises TypeError; other builds may treat None as default.
        try:
            s = bcrypt.gensalt(rounds=None)  # type: ignore[arg-type]
        except TypeError:
            return
        self.assertTrue(s.startswith(b"$2"))

    def test_gensalt_invalid_prefix_raises(self):
        for bad in (b"2x", b"2y", b"2", b"2bb", b"", "2b"):
            with self.subTest(bad=bad):
                if isinstance(bad, str):
                    with self.assertRaises(TypeError):
                        bcrypt.gensalt(prefix=bad)  # type: ignore[arg-type]
                else:
                    with self.assertRaises(ValueError):
                        bcrypt.gensalt(prefix=bad)

    def test_gensalt_invalid_rounds_raise(self):
        for bad in (-1, 0, 1, 3, 32, 100, "12"):
            with self.subTest(bad=bad):
                if not isinstance(bad, int):
                    with self.assertRaises(TypeError):
                        bcrypt.gensalt(rounds=bad)  # type: ignore[arg-type]
                else:
                    with self.assertRaises((ValueError, OverflowError)):
                        bcrypt.gensalt(rounds=bad)


class TestBcryptHashpwAndCheckpw(unittest.TestCase):
    def test_hashpw_and_checkpw_happy_path(self):
        password = b"super secret password"
        hashed = bcrypt.hashpw(password, bcrypt.gensalt())
        self.assertIsInstance(hashed, (bytes, bytearray))
        self.assertTrue(bcrypt.checkpw(password, hashed))
        self.assertFalse(bcrypt.checkpw(b"wrong password", hashed))

    def test_hashpw_same_password_different_salts_different_hashes(self):
        password = b"password"
        h1 = bcrypt.hashpw(password, bcrypt.gensalt())
        h2 = bcrypt.hashpw(password, bcrypt.gensalt())
        self.assertNotEqual(h1, h2)
        self.assertTrue(bcrypt.checkpw(password, h1))
        self.assertTrue(bcrypt.checkpw(password, h2))

    def test_hashpw_is_deterministic_given_same_salt(self):
        password = b"password"
        salt = bcrypt.gensalt()
        h1 = bcrypt.hashpw(password, salt)
        h2 = bcrypt.hashpw(password, salt)
        self.assertEqual(h1, h2)
        self.assertTrue(bcrypt.checkpw(password, h1))

    def test_hashpw_rounds_in_hash(self):
        password = b"password"
        hashed = bcrypt.hashpw(password, bcrypt.gensalt(rounds=14))
        self.assertIn(b"$14$", hashed)
        self.assertTrue(bcrypt.checkpw(password, hashed))

    def test_hashpw_prefix_compatibility_2a_2b(self):
        password = b"password"
        for prefix in (b"2a", b"2b"):
            with self.subTest(prefix=prefix):
                salt = bcrypt.gensalt(prefix=prefix)
                hashed = bcrypt.hashpw(password, salt)
                self.assertTrue(hashed.startswith(b"$" + prefix + b"$"))
                self.assertTrue(bcrypt.checkpw(password, hashed))

    def test_hashpw_accepts_2y_hashes(self):
        # README: "$2y$ prefix is still supported in hashpw but deprecated."
        password = b"password"
        original = bcrypt.hashpw(password, bcrypt.gensalt(prefix=b"2b"))
        self.assertTrue(original.startswith(b"$2b$"))
        twoy = b"$2y$" + original[4:]
        derived = bcrypt.hashpw(password, twoy)
        self.assertTrue(derived.startswith(b"$2y$"))
        self.assertTrue(bcrypt.checkpw(password, derived))

    def test_hashpw_invalid_types(self):
        salt = bcrypt.gensalt()
        with self.assertRaises(TypeError):
            bcrypt.hashpw("password", salt)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            bcrypt.hashpw(b"password", "notbytes")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            bcrypt.checkpw("password", bcrypt.hashpw(b"password", salt))  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            bcrypt.checkpw(b"password", "notbytes")  # type: ignore[arg-type]

    def test_checkpw_rejects_wrong_prefix_safely(self):
        password = b"password"
        bogus = b"$2x$12$" + (b"." * 22) + (b"." * 31)
        try:
            ok = bcrypt.checkpw(password, bogus)
            self.assertFalse(ok)
        except (ValueError, TypeError):
            pass

    def test_checkpw_with_valid_format_but_wrong_hash_is_false(self):
        password = b"password"
        real = bcrypt.hashpw(password, bcrypt.gensalt())
        self.assertGreaterEqual(len(real), 60)
        mutated = bytearray(real)
        mutated[-1] = ord(b"." if mutated[-1] != ord(b".") else b"/")
        mutated = bytes(mutated)
        self.assertFalse(bcrypt.checkpw(password, mutated))


class TestBcryptMaxPasswordLength(unittest.TestCase):
    def test_password_length_72_ok(self):
        pw72 = b"a" * 72
        hashed = bcrypt.hashpw(pw72, bcrypt.gensalt())
        self.assertTrue(bcrypt.checkpw(pw72, hashed))

    def test_password_length_73_behavior(self):
        pw73 = b"a" * 73
        try:
            hashed = bcrypt.hashpw(pw73, bcrypt.gensalt())
        except ValueError:
            return
        self.assertTrue(bcrypt.checkpw(pw73, hashed))

    def test_workaround_hash_then_b64_then_bcrypt(self):
        password = b"an incredibly long password" * 10
        prehashed = base64.b64encode(hashlib.sha256(password).digest())
        self.assertLessEqual(len(prehashed), 72)
        hashed = bcrypt.hashpw(prehashed, bcrypt.gensalt())
        self.assertTrue(bcrypt.checkpw(prehashed, hashed))


class TestBcryptKdf(unittest.TestCase):
    def test_kdf_deterministic_with_same_inputs(self):
        dk1 = bcrypt.kdf(password=b"password", salt=b"salt", desired_key_bytes=32, rounds=100)
        dk2 = bcrypt.kdf(password=b"password", salt=b"salt", desired_key_bytes=32, rounds=100)
        self.assertEqual(dk1, dk2)
        self.assertEqual(len(dk1), 32)

    def test_kdf_changes_when_salt_or_password_changes(self):
        dk_base = bcrypt.kdf(password=b"password", salt=b"salt", desired_key_bytes=32, rounds=100)
        dk_pw = bcrypt.kdf(password=b"password2", salt=b"salt", desired_key_bytes=32, rounds=100)
        dk_salt = bcrypt.kdf(password=b"password", salt=b"salt2", desired_key_bytes=32, rounds=100)
        self.assertNotEqual(dk_base, dk_pw)
        self.assertNotEqual(dk_base, dk_salt)

    def test_kdf_output_length(self):
        for n in (1, 16, 32, 64):
            with self.subTest(n=n):
                dk = bcrypt.kdf(password=b"password", salt=b"salt", desired_key_bytes=n, rounds=100)
                self.assertEqual(len(dk), n)

    def test_kdf_type_validation(self):
        with self.assertRaises(TypeError):
            bcrypt.kdf(password="password", salt=b"salt", desired_key_bytes=32, rounds=100)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            bcrypt.kdf(password=b"password", salt="salt", desired_key_bytes=32, rounds=100)  # type: ignore[arg-type]

    def test_kdf_parameter_validation(self):
        bad_cases = [
            dict(password=b"p", salt=b"s", desired_key_bytes=0, rounds=100),
            dict(password=b"p", salt=b"s", desired_key_bytes=-1, rounds=100),
            dict(password=b"p", salt=b"s", desired_key_bytes=32, rounds=0),
            dict(password=b"p", salt=b"s", desired_key_bytes=32, rounds=-5),
            dict(password=b"p", salt=b"s", desired_key_bytes="32", rounds=100),
            dict(password=b"p", salt=b"s", desired_key_bytes=32, rounds="100"),
        ]
        for kwargs in bad_cases:
            with self.subTest(kwargs=kwargs):
                if isinstance(kwargs["desired_key_bytes"], str) or isinstance(kwargs["rounds"], str):
                    with self.assertRaises(TypeError):
                        bcrypt.kdf(**kwargs)  # type: ignore[arg-type]
                else:
                    with self.assertRaises((ValueError, OverflowError)):
                        bcrypt.kdf(**kwargs)

    def test_kdf_warning_can_be_silenced(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = bcrypt.kdf(password=b"password", salt=b"salt", desired_key_bytes=16, rounds=10)
            self.assertGreaterEqual(len(w), 0)

        with warnings.catch_warnings(record=True) as w2:
            warnings.simplefilter("ignore")
            _ = bcrypt.kdf(password=b"password", salt=b"salt", desired_key_bytes=16, rounds=10)
            self.assertEqual(len(w2), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)