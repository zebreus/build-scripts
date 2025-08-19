import os
import sys
import io
import tempfile
import unittest
import binascii

from Crypto import __version__ as pycryptodome_version
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Cipher import ChaCha20
try:
    from Crypto.Cipher import ChaCha20_Poly1305
    HAVE_CHACHA20_POLY1305 = True
except Exception:
    HAVE_CHACHA20_POLY1305 = False

from Crypto.Hash import (
    HMAC, CMAC,
    SHA1, SHA224, SHA256, SHA384, SHA512,
    SHA3_256, SHA3_512,
    SHAKE128, SHAKE256,
    BLAKE2b, BLAKE2s,
    Poly1305 as Poly1305Hash,
)
from Crypto.Protocol.KDF import PBKDF2, scrypt, HKDF
from Crypto.Random import get_random_bytes, random
from Crypto.Util import Padding

from Crypto.PublicKey import RSA, DSA, ECC
from Crypto.Signature import pkcs1_15, pss, DSS


def flip_one_byte(b: bytes, index: int = 0) -> bytes:
    ba = bytearray(b)
    ba[index % len(ba)] ^= 0x01
    return bytes(ba)


class TestInfo(unittest.TestCase):
    def test_version_present(self):
        self.assertTrue(pycryptodome_version)
        self.assertRegex(pycryptodome_version, r"\d+\.\d+(\.\d+)?")

class TestSymmetricCiphers(unittest.TestCase):
    def setUp(self):
        self.data = b"The quick brown fox jumps over the lazy dog."
        self.key128 = b"K" * 16
        self.key192 = b"K" * 24
        self.key256 = b"K" * 32
        self.iv = b"I" * 16
        self.assoc = b"header-associated-data"

    def test_aes_ecb_cbc_ctr(self):
        # ECB (requires padding)
        cipher = AES.new(self.key128, AES.MODE_ECB)
        ct = cipher.encrypt(Padding.pad(self.data, AES.block_size))
        pt = AES.new(self.key128, AES.MODE_ECB).decrypt(ct)
        self.assertEqual(Padding.unpad(pt, AES.block_size), self.data)

        # CBC (requires IV and padding)
        cipher = AES.new(self.key192, AES.MODE_CBC, iv=self.iv)
        ct = cipher.encrypt(Padding.pad(self.data, AES.block_size))
        pt = AES.new(self.key192, AES.MODE_CBC, iv=self.iv).decrypt(ct)
        self.assertEqual(Padding.unpad(pt, AES.block_size), self.data)

        # CTR (no padding)
        cipher = AES.new(self.key256, AES.MODE_CTR)
        nonce = cipher.nonce
        ct = cipher.encrypt(self.data)
        pt = AES.new(self.key256, AES.MODE_CTR, nonce=nonce).decrypt(ct)
        self.assertEqual(pt, self.data)

    def test_aes_cfb_ofb(self):
        # CFB
        cipher = AES.new(self.key128, AES.MODE_CFB, iv=self.iv, segment_size=128)
        ct = cipher.encrypt(self.data)
        pt = AES.new(self.key128, AES.MODE_CFB, iv=self.iv, segment_size=128).decrypt(ct)
        self.assertEqual(pt, self.data)
        # OFB
        cipher = AES.new(self.key128, AES.MODE_OFB, iv=self.iv)
        ct = cipher.encrypt(self.data)
        pt = AES.new(self.key128, AES.MODE_OFB, iv=self.iv).decrypt(ct)
        self.assertEqual(pt, self.data)

    def test_aes_eax_gcm_ccm_ocb_siv(self):
        # EAX
        cipher = AES.new(self.key128, AES.MODE_EAX)
        cipher.update(self.assoc)
        ct, tag = cipher.encrypt_and_digest(self.data)
        dec = AES.new(self.key128, AES.MODE_EAX, nonce=cipher.nonce)
        dec.update(self.assoc)
        self.assertEqual(dec.decrypt_and_verify(ct, tag), self.data)
        with self.subTest("EAX tamper"):
            with self.assertRaises(ValueError):
                dec = AES.new(self.key128, AES.MODE_EAX, nonce=cipher.nonce)
                dec.update(self.assoc)
                dec.decrypt_and_verify(flip_one_byte(ct), tag)

        # GCM
        cipher = AES.new(self.key128, AES.MODE_GCM)
        cipher.update(self.assoc)
        ct, tag = cipher.encrypt_and_digest(self.data)
        dec = AES.new(self.key128, AES.MODE_GCM, nonce=cipher.nonce)
        dec.update(self.assoc)
        self.assertEqual(dec.decrypt_and_verify(ct, tag), self.data)
        with self.subTest("GCM tamper"):
            with self.assertRaises(ValueError):
                dec = AES.new(self.key128, AES.MODE_GCM, nonce=cipher.nonce)
                dec.update(self.assoc)
                dec.decrypt_and_verify(ct, flip_one_byte(tag))

        # CCM (requires nonce length in [7..13])
        nonce = b"NCCMnonce!!"  # 11 bytes
        cipher = AES.new(self.key128, AES.MODE_CCM, nonce=nonce, mac_len=16)
        cipher.update(self.assoc)
        ct = cipher.encrypt(self.data)
        tag = cipher.digest()
        dec = AES.new(self.key128, AES.MODE_CCM, nonce=nonce, mac_len=16)
        dec.update(self.assoc)
        pt = dec.decrypt(ct)
        self.assertEqual(pt, self.data)
        dec.verify(tag)

        # OCB (if available)
        if hasattr(AES, "MODE_OCB"):
            cipher = AES.new(self.key128, AES.MODE_OCB)
            cipher.update(self.assoc)
            ct, tag = cipher.encrypt_and_digest(self.data)
            dec = AES.new(self.key128, AES.MODE_OCB, nonce=cipher.nonce)
            dec.update(self.assoc)
            self.assertEqual(dec.decrypt_and_verify(ct, tag), self.data)

        # SIV (deterministic AEAD; requires 32/48/64 byte key)
        if hasattr(AES, "MODE_SIV"):
            key = b"K" * 32
            # Use explicit nonce to avoid relying on cipher.nonce (not present on some versions)
            nonce = b"N" * 16
            cipher = AES.new(key, AES.MODE_SIV, nonce=nonce)
            cipher.update(self.assoc)
            ct, tag = cipher.encrypt_and_digest(self.data)
            cipher2 = AES.new(key, AES.MODE_SIV, nonce=nonce)
            cipher2.update(self.assoc)
            self.assertEqual(cipher2.decrypt_and_verify(ct, tag), self.data)

    def test_chacha20_and_aead(self):
        # ChaCha20 stream
        key = get_random_bytes(32)
        nonce = get_random_bytes(8)
        cipher = ChaCha20.new(key=key, nonce=nonce)
        ct = cipher.encrypt(self.data)
        pt = ChaCha20.new(key=key, nonce=nonce).decrypt(ct)
        self.assertEqual(pt, self.data)

        # ChaCha20-Poly1305 AEAD (if available)
        if HAVE_CHACHA20_POLY1305:
            key = get_random_bytes(32)
            cipher = ChaCha20_Poly1305.new(key=key)
            cipher.update(self.assoc)
            ct, tag = cipher.encrypt_and_digest(self.data)
            dec = ChaCha20_Poly1305.new(key=key, nonce=cipher.nonce)
            dec.update(self.assoc)
            self.assertEqual(dec.decrypt_and_verify(ct, tag), self.data)
            with self.assertRaises(ValueError):
                dec = ChaCha20_Poly1305.new(key=key, nonce=cipher.nonce)
                dec.update(self.assoc)
                dec.decrypt_and_verify(flip_one_byte(ct), tag)


class TestHashesAndMACs(unittest.TestCase):
    def setUp(self):
        self.msg = b"hello world"
        self.key = b"supersecretkey"

    def test_sha2_family(self):
        self.assertEqual(SHA256.new(self.msg).digest_size, 32)
        self.assertNotEqual(SHA256.new(self.msg).digest(), SHA256.new(self.msg + b"!").digest())
        self.assertEqual(SHA512.new(self.msg).hexdigest(), SHA512.new(self.msg).hexdigest())

    def test_sha3_and_shake(self):
        d = SHA3_256.new(self.msg).digest()
        self.assertEqual(len(d), 32)
        shake = SHAKE128.new(self.msg)
        out = shake.read(42)
        self.assertEqual(len(out), 42)
        shake2 = SHAKE128.new(self.msg)
        self.assertEqual(out, shake2.read(42))  # deterministic XOF

    def test_blake2(self):
        self.assertEqual(len(BLAKE2b.new(data=self.msg).digest()), 64)
        self.assertEqual(len(BLAKE2s.new(data=self.msg).digest()), 32)

    def test_hmac(self):
        h = HMAC.new(self.key, digestmod=SHA256)
        h.update(self.msg)
        tag = h.digest()
        h2 = HMAC.new(self.key, digestmod=SHA256)
        h2.update(self.msg)
        h2.verify(tag)  # should not raise
        with self.assertRaises(ValueError):
            h2.verify(flip_one_byte(tag))

    def test_cmac(self):
        cmac = CMAC.new(self.key.ljust(16, b"\x00")[:16], ciphermod=AES)
        cmac.update(self.msg)
        tag = cmac.digest()
        cmac2 = CMAC.new(self.key.ljust(16, b"\x00")[:16], ciphermod=AES)
        cmac2.update(self.msg)
        cmac2.verify(tag)
        with self.assertRaises(ValueError):
            cmac2.verify(flip_one_byte(tag))

    def test_poly1305_hash(self):
        msg = self.msg
        # Try one-time 32-byte key form first; fall back if this build requires a cipher
        one_time_key = get_random_bytes(32)
        try:
            p = Poly1305Hash.new(key=one_time_key)
            p.update(msg)
            tag = p.digest()

            p2 = Poly1305Hash.new(key=one_time_key)
            p2.update(msg)
            p2.verify(tag)
            with self.assertRaises(ValueError):
                p2.verify(flip_one_byte(tag))
        except ValueError:
            # Some builds require specifying a cipher. Try AES first (needs 32-byte key, 16-byte nonce).
            try:
                aes_key = get_random_bytes(32)   # AES-256 for Poly1305-AES
                nonce = get_random_bytes(16)     # 16-byte nonce for Poly1305-AES
                p = Poly1305Hash.new(key=aes_key, cipher=AES, nonce=nonce)
                p.update(msg)
                tag = p.digest()

                p2 = Poly1305Hash.new(key=aes_key, cipher=AES, nonce=nonce)
                p2.update(msg)
                p2.verify(tag)
                with self.assertRaises(ValueError):
                    p2.verify(flip_one_byte(tag))
            except ValueError:
                # Fallback to ChaCha20-based Poly1305 (32-byte key, 8-byte nonce typical)
                chacha_key = get_random_bytes(32)
                chacha_nonce = get_random_bytes(8)
                p = Poly1305Hash.new(key=chacha_key, cipher=ChaCha20, nonce=chacha_nonce)
                p.update(msg)
                tag = p.digest()

                p2 = Poly1305Hash.new(key=chacha_key, cipher=ChaCha20, nonce=chacha_nonce)
                p2.update(msg)
                p2.verify(tag)
                with self.assertRaises(ValueError):
                    p2.verify(flip_one_byte(tag))


class TestKDFs(unittest.TestCase):
    def setUp(self):
        self.password = b"correct horse battery staple"
        self.salt = b"NaCl"
        self.info = b"context-info"

    def test_pbkdf2(self):
        dk = PBKDF2(self.password, self.salt, dkLen=32, count=100_000, hmac_hash_module=SHA256)
        self.assertEqual(len(dk), 32)
        # Same inputs => same output
        dk2 = PBKDF2(self.password, self.salt, dkLen=32, count=100_000, hmac_hash_module=SHA256)
        self.assertEqual(dk, dk2)

    def test_scrypt(self):
        dk = scrypt(self.password, self.salt, key_len=32, N=2**14, r=8, p=1)
        self.assertEqual(len(dk), 32)

    def test_hkdf(self):
        prk = HKDF(master=self.password, key_len=32, salt=self.salt, hashmod=SHA256, context=self.info)
        self.assertEqual(len(prk), 32)
        prk2 = HKDF(master=self.password, key_len=32, salt=self.salt, hashmod=SHA256, context=self.info)
        self.assertEqual(prk, prk2)


class TestRSA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use 2048 like the examples (may take a few seconds)
        cls.key = RSA.generate(2048)
        cls.pub = cls.key.publickey()

    def test_encrypt_oaep(self):
        data = b"I met aliens in UFO. Here is the map."
        cipher_rsa = PKCS1_OAEP.new(self.pub)
        enc = cipher_rsa.encrypt(get_random_bytes(16))  # encrypt session key (hybrid pattern)
        self.assertEqual(len(enc), self.pub.size_in_bytes())

    def test_encrypt_decrypt_hybrid_eax(self):
        data = b"I met aliens in UFO. Here is the map."
        session_key = get_random_bytes(16)
        enc_session_key = PKCS1_OAEP.new(self.pub).encrypt(session_key)
        cipher_aes = AES.new(session_key, AES.MODE_EAX)
        ciphertext, tag = cipher_aes.encrypt_and_digest(data)
        nonce = cipher_aes.nonce

        session_key_out = PKCS1_OAEP.new(self.key).decrypt(enc_session_key)
        self.assertEqual(session_key_out, session_key)
        data_out = AES.new(session_key_out, AES.MODE_EAX, nonce).decrypt_and_verify(ciphertext, tag)
        self.assertEqual(data_out, data)

    def test_sign_verify_pkcs1_v15_and_pss(self):
        msg = b"sign me plz"
        h = SHA256.new(msg)
        sig1 = pkcs1_15.new(self.key).sign(h)
        pkcs1_15.new(self.pub).verify(h, sig1)  # should not raise

        sig2 = pss.new(self.key).sign(h)
        pss.new(self.pub).verify(h, sig2)  # should not raise

        with self.assertRaises(ValueError):
            pkcs1_15.new(self.pub).verify(h, flip_one_byte(sig1))

        with self.assertRaises(ValueError):
            pss.new(self.pub).verify(h, flip_one_byte(sig2))

    def test_serialize_import_encrypted(self):
        secret = "Unguessable"
        enc_priv = self.key.export_key(
            passphrase=secret, pkcs=8, protection="scryptAndAES128-CBC",
            prot_params={"iteration_count": 131072},
        )
        key2 = RSA.import_key(enc_priv, passphrase=secret)
        self.assertEqual(key2.publickey().export_key(), self.pub.export_key())

    def test_file_io_pattern_like_example(self):
        data = b"secret data to transmit"
        aes_key = get_random_bytes(16)
        hmac_key = get_random_bytes(16)

        cipher = AES.new(aes_key, AES.MODE_CTR)
        ciphertext = cipher.encrypt(data)
        hmac = HMAC.new(hmac_key, digestmod=SHA256)
        tag = hmac.update(cipher.nonce + ciphertext).digest()

        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
            f.write(tag)
            f.write(cipher.nonce)
            f.write(ciphertext)

        try:
            with open(path, "rb") as f:
                tag2 = f.read(32)
                nonce2 = f.read(8)
                ct2 = f.read()

            hmac2 = HMAC.new(hmac_key, digestmod=SHA256)
            hmac2.update(nonce2 + ct2).verify(tag2)

            msg = AES.new(aes_key, AES.MODE_CTR, nonce=nonce2).decrypt(ct2)
            self.assertEqual(msg, data)
        finally:
            os.unlink(path)


class TestDSAandECC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsa_key = DSA.generate(2048)
        cls.dsa_pub = cls.dsa_key.publickey()
        cls.ecc_key = ECC.generate(curve="P-256")
        cls.ecc_pub = cls.ecc_key.public_key()

    def test_dsa_sign_verify(self):
        msg = b"DSA message"
        h = SHA256.new(msg)
        signer = DSS.new(self.dsa_key, "fips-186-3")
        sig = signer.sign(h)
        verifier = DSS.new(self.dsa_pub, "fips-186-3")
        verifier.verify(h, sig)  # should not raise
        with self.assertRaises(ValueError):
            verifier.verify(h, flip_one_byte(sig))

    def test_ecc_sign_verify(self):
        msg = b"ECDSA message"
        h = SHA256.new(msg)
        signer = DSS.new(self.ecc_key, "fips-186-3")
        sig = signer.sign(h)
        verifier = DSS.new(self.ecc_pub, "fips-186-3")
        verifier.verify(h, sig)
        with self.assertRaises(ValueError):
            verifier.verify(h, flip_one_byte(sig))

    def test_ecc_serialize(self):
        pem = self.ecc_key.export_key(format="PEM")
        key2 = ECC.import_key(pem)
        self.assertEqual(key2.pointQ, self.ecc_key.pointQ)


class TestUtilities(unittest.TestCase):
    def test_padding_pkcs7(self):
        for block in (8, 16):
            with self.subTest(block=block):
                data = b"abc"
                padded = Padding.pad(data, block)
                self.assertEqual(padded[-1], block - len(data) % block)
                self.assertEqual(Padding.unpad(padded, block), data)

    def test_randomness(self):
        a = get_random_bytes(32)
        b = get_random_bytes(32)
        self.assertNotEqual(a, b)
        # randint from Crypto.Random.random (independent from stdlib)
        n = random.randint(1, 10)
        self.assertTrue(1 <= n <= 10)


class TestExampleOCB(unittest.TestCase):
    def test_example_ocb_like(self):
        if not hasattr(AES, "MODE_OCB"):
            self.skipTest("OCB not available")
        data = b"secret data to transmit"
        aes_key = get_random_bytes(16)
        cipher = AES.new(aes_key, AES.MODE_OCB)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        self.assertEqual(len(cipher.nonce), 15)
        # Write to a temp file like the example
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
            f.write(tag)
            f.write(cipher.nonce)
            f.write(ciphertext)
        try:
            with open(path, "rb") as f:
                tag2 = f.read(16)
                nonce2 = f.read(15)
                ct2 = f.read()
            cipher2 = AES.new(aes_key, AES.MODE_OCB, nonce=nonce2)
            msg = cipher2.decrypt_and_verify(ct2, tag2)
            self.assertEqual(msg, data)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)