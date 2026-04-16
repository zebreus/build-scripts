import unittest
import os
import base64
import datetime

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, hmac, constant_time, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec, ed25519
from cryptography import x509
from cryptography.x509.oid import NameOID


BACKEND = default_backend()


class TestFernet(unittest.TestCase):
    def test_generate_key_and_encrypt_decrypt(self):
        key = Fernet.generate_key()
        self.assertIsInstance(key, bytes)
        f = Fernet(key)

        data = b"secret payload"
        token1 = f.encrypt(data)
        token2 = f.encrypt(data)

        # Decryption round-trip
        self.assertEqual(f.decrypt(token1), data)
        self.assertEqual(f.decrypt(token2), data)

        # Tokens should differ due to different timestamps / IVs
        self.assertNotEqual(token1, token2)


class TestHashesAndHMAC(unittest.TestCase):
    def test_sha256_hash(self):
        digest = hashes.Hash(hashes.SHA256(), backend=BACKEND)
        digest.update(b"hello")
        digest.update(b" world")
        result = digest.finalize()

        self.assertIsInstance(result, bytes)
        self.assertEqual(len(result), 32)

        # Ensure deterministic behavior
        digest2 = hashes.Hash(hashes.SHA256(), backend=BACKEND)
        digest2.update(b"hello world")
        self.assertEqual(result, digest2.finalize())

    def test_hmac_sha256(self):
        key = b"supersecretkey"
        h = hmac.HMAC(key, hashes.SHA256(), backend=BACKEND)
        h.update(b"message")
        tag = h.finalize()

        self.assertIsInstance(tag, bytes)
        self.assertEqual(len(tag), 32)

        # Verify succeeds with same key/message
        h2 = hmac.HMAC(key, hashes.SHA256(), backend=BACKEND)
        h2.update(b"message")
        h2.verify(tag)

        # Verification fails with different key
        h3 = hmac.HMAC(b"otherkey", hashes.SHA256(), backend=BACKEND)
        h3.update(b"message")
        with self.assertRaises(Exception):
            h3.verify(tag)

    def test_constant_time_compare(self):
        self.assertTrue(constant_time.bytes_eq(b"abc", b"abc"))
        self.assertFalse(constant_time.bytes_eq(b"abc", b"abd"))
        self.assertFalse(constant_time.bytes_eq(b"abc", b"abcd"))


class TestKDFs(unittest.TestCase):
    def test_pbkdf2_hmac(self):
        password = b"correct horse battery staple"
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
            backend=BACKEND,
        )

        key = kdf.derive(password)
        self.assertEqual(len(key), 32)

        # verify() should succeed for the same password
        kdf_verify = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
            backend=BACKEND,
        )
        kdf_verify.verify(password, key)

        # and fail for a different password
        kdf_verify2 = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
            backend=BACKEND,
        )
        with self.assertRaises(Exception):
            kdf_verify2.verify(b"wrong password", key)


class TestSymmetricCiphers(unittest.TestCase):
    def test_aes_gcm_roundtrip(self):
        key = os.urandom(32)  # AES-256
        iv = os.urandom(12)   # Recommended size for GCM
        aad = b"associated data"
        plaintext = b"top secret message"

        encryptor = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=BACKEND,
        ).encryptor()

        encryptor.authenticate_additional_data(aad)
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        tag = encryptor.tag

        decryptor = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, tag),
            backend=BACKEND,
        ).decryptor()
        decryptor.authenticate_additional_data(aad)
        decrypted = decryptor.update(ciphertext) + decryptor.finalize()

        self.assertEqual(plaintext, decrypted)

    def test_aes_cbc_roundtrip(self):
        key = os.urandom(32)
        iv = os.urandom(16)
        plaintext = b"16 bytes of data"  # already block aligned for AES

        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=BACKEND)
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()

        decryptor = cipher.decryptor()
        decrypted = decryptor.update(ciphertext) + decryptor.finalize()
        self.assertEqual(plaintext, decrypted)


class TestRSA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=BACKEND,
        )
        cls.public_key = cls.private_key.public_key()

    def test_rsa_key_properties(self):
        numbers = self.private_key.private_numbers()
        self.assertIsNotNone(numbers.p)
        self.assertIsNotNone(numbers.q)

    def test_rsa_sign_verify_pss(self):
        message = b"message to sign"
        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )

        # Should verify successfully
        self.public_key.verify(
            signature,
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )

        # And fail for tampered message
        with self.assertRaises(Exception):
            self.public_key.verify(
                signature,
                b"other message",
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )

    def test_rsa_encrypt_decrypt_oaep(self):
        message = b"rsa encrypted message"
        ciphertext = self.public_key.encrypt(
            message,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        plaintext = self.private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        self.assertEqual(message, plaintext)


class TestEllipticCurveKeys(unittest.TestCase):
    def test_ecdsa_sign_verify(self):
        private_key = ec.generate_private_key(ec.SECP256R1(), backend=BACKEND)
        public_key = private_key.public_key()

        data = b"ecdsa data"
        signature = private_key.sign(data, ec.ECDSA(hashes.SHA256()))

        # Verify succeeds
        public_key.verify(signature, data, ec.ECDSA(hashes.SHA256()))

        # Verify fails on different data
        with self.assertRaises(Exception):
            public_key.verify(signature, b"other data", ec.ECDSA(hashes.SHA256()))

    def test_ed25519_sign_verify(self):
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        data = b"ed25519 data"
        signature = private_key.sign(data)

        public_key.verify(signature, data)
        with self.assertRaises(Exception):
            public_key.verify(signature, b"tampered")


class TestSerialization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=BACKEND,
        )
        cls.public_key = cls.private_key.public_key()

    def test_serialize_private_key_pem_unencrypted(self):
        pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self.assertIn(b"BEGIN PRIVATE KEY", pem)

        loaded_key = serialization.load_pem_private_key(
            pem,
            password=None,
            backend=BACKEND,
        )
        self.assertIsInstance(loaded_key, rsa.RSAPrivateKey)

    def test_serialize_private_key_pem_encrypted(self):
        password = b"password123"
        pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(password),
        )
        self.assertIn(b"BEGIN ENCRYPTED PRIVATE KEY", pem)

        loaded_key = serialization.load_pem_private_key(
            pem,
            password=password,
            backend=BACKEND,
        )
        self.assertIsInstance(loaded_key, rsa.RSAPrivateKey)

    def test_serialize_public_key_pem(self):
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.assertIn(b"BEGIN PUBLIC KEY", pem)

        loaded_pub = serialization.load_pem_public_key(pem, backend=BACKEND)
        self.assertIsInstance(loaded_pub, rsa.RSAPublicKey)


class TestX509(unittest.TestCase):
    def test_create_and_parse_self_signed_cert(self):
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=BACKEND,
        )

        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Example Org"),
                x509.NameAttribute(NameOID.COMMON_NAME, "example.org"),
            ]
        )

        now = datetime.datetime.utcnow()
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
            .sign(private_key=key, algorithm=hashes.SHA256(), backend=BACKEND)
        )

        # Serialize to PEM and load again
        pem = cert.public_bytes(serialization.Encoding.PEM)
        self.assertIn(b"BEGIN CERTIFICATE", pem)

        loaded_cert = x509.load_pem_x509_certificate(pem, backend=BACKEND)
        self.assertEqual(
            loaded_cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value,
            "example.org",
        )
        self.assertEqual(
            loaded_cert.issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value,
            "Example Org",
        )

        # Check public key matches
        self.assertEqual(
            loaded_cert.public_key().public_numbers(),
            key.public_key().public_numbers(),
        )


if __name__ == "__main__":
    unittest.main()
