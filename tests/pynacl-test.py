import unittest

import nacl
import nacl.utils
import nacl.encoding as enc
import nacl.exceptions as exc
import nacl.hash as nhash
import nacl.pwhash
from nacl.public import PrivateKey, PublicKey, Box, SealedBox
from nacl.signing import SigningKey, VerifyKey
from nacl.secret import SecretBox, Aead as AeadBox


# --- Public Key Encryption (Box / SealedBox) --------------------------------
class TestPublicKeyBox(unittest.TestCase):
    def setUp(self):
        # Alice and Bob keypairs
        self.skalice = PrivateKey.generate()
        self.pkalice = self.skalice.public_key
        self.skbob = PrivateKey.generate()
        self.pkbob = self.skbob.public_key
        self.message = b"Kill all humans"

    def test_box_encrypt_decrypt_with_random_nonce(self):
        bob_box = Box(self.skbob, self.pkalice)
        encrypted = bob_box.encrypt(self.message)
        self.assertIsInstance(encrypted, nacl.utils.EncryptedMessage)
        # Encrypted message length = plaintext + nonce + MAC (16 bytes)
        self.assertEqual(
            len(encrypted),
            len(self.message) + Box.NONCE_SIZE + 16,
        )

        alice_box = Box(self.skalice, self.pkbob)
        plaintext = alice_box.decrypt(encrypted)
        self.assertEqual(plaintext, self.message)

    def test_box_encrypt_decrypt_with_explicit_nonce(self):
        nonce = nacl.utils.random(Box.NONCE_SIZE)
        bob_box = Box(self.skbob, self.pkalice)
        encrypted = bob_box.encrypt(self.message, nonce)
        # nonce attribute must match what we provided
        self.assertEqual(encrypted.nonce, nonce)

        alice_box = Box(self.skalice, self.pkbob)
        plaintext = alice_box.decrypt(encrypted)
        self.assertEqual(plaintext, self.message)

    def test_box_tamper_detection(self):
        bob_box = Box(self.skbob, self.pkalice)
        encrypted = bytearray(bob_box.encrypt(self.message))
        # Flip one bit in the ciphertext portion to trigger MAC failure
        encrypted[-1] ^= 0x01
        alice_box = Box(self.skalice, self.pkbob)
        with self.assertRaises(exc.CryptoError):
            alice_box.decrypt(bytes(encrypted))

    def test_box_shared_key_symmetry(self):
        # shared_key() from (pkA, skB) equals (pkB, skA)
        ab = Box(self.skalice, self.pkbob).shared_key()
        ba = Box(self.skbob, self.pkalice).shared_key()
        self.assertEqual(ab, ba)
        self.assertEqual(len(ab), 32)


class TestSealedBox(unittest.TestCase):
    def setUp(self):
        self.skbob = PrivateKey.generate()
        self.pkbob = self.skbob.public_key
        self.message = b"Kill all kittens"

    def test_sealedbox_encrypt_decrypt(self):
        sealed = SealedBox(self.pkbob)
        ciphertext = sealed.encrypt(self.message)
        self.assertIsInstance(ciphertext, bytes)
        # Receiver can decrypt with private key
        unseal = SealedBox(self.skbob)
        plaintext = unseal.decrypt(ciphertext)
        self.assertEqual(plaintext, self.message)

    def test_sealedbox_wrong_key_fails(self):
        sealed = SealedBox(self.pkbob)
        ciphertext = sealed.encrypt(self.message)
        # Another key cannot decrypt
        other_sk = PrivateKey.generate()
        with self.assertRaises(exc.CryptoError):
            SealedBox(other_sk).decrypt(ciphertext)


# --- Secret Key Encryption (SecretBox / AEAD) --------------------------------
class TestSecretBox(unittest.TestCase):
    def setUp(self):
        self.key = nacl.utils.random(SecretBox.KEY_SIZE)
        self.box = SecretBox(self.key)
        self.message = b"The president will be exiting through the lower levels"

    def test_secretbox_encrypt_decrypt_random_nonce(self):
        encrypted = self.box.encrypt(self.message)
        self.assertIsInstance(encrypted, nacl.utils.EncryptedMessage)
        self.assertEqual(
            len(encrypted),
            len(self.message) + self.box.NONCE_SIZE + self.box.MACBYTES,
        )
        plaintext = self.box.decrypt(encrypted)
        self.assertEqual(plaintext, self.message)

    def test_secretbox_encrypt_decrypt_explicit_nonce(self):
        nonce = nacl.utils.random(self.box.NONCE_SIZE)
        encrypted = self.box.encrypt(self.message, nonce)
        self.assertEqual(encrypted.nonce, nonce)
        ciphertext_only = encrypted.ciphertext
        # ciphertext only length is msg + MACBYTES
        self.assertEqual(len(ciphertext_only), len(self.message) + self.box.MACBYTES)
        plaintext = self.box.decrypt(encrypted)
        self.assertEqual(plaintext, self.message)

    def test_secretbox_tamper_detection(self):
        encrypted = bytearray(self.box.encrypt(self.message))
        encrypted[-1] ^= 0x01
        with self.assertRaises(exc.CryptoError):
            self.box.decrypt(bytes(encrypted))

    def test_secretbox_same_nonce_same_ciphertext(self):
        # Demonstrate nonce reuse danger: same key+nonce+plaintext -> same ciphertext
        nonce = nacl.utils.random(self.box.NONCE_SIZE)
        c1 = self.box.encrypt(self.message, nonce)
        c2 = self.box.encrypt(self.message, nonce)
        self.assertEqual(c1.ciphertext, c2.ciphertext)


class TestAead(unittest.TestCase):
    def setUp(self):
        self.key = nacl.utils.random(AeadBox.KEY_SIZE)
        self.box = AeadBox(self.key)
        self.message = b"The president will be exiting through the upper levels"
        self.aad = b"POTUS"

    def test_aead_encrypt_decrypt_with_aad(self):
        encmsg = self.box.encrypt(self.message, self.aad)
        self.assertEqual(
            len(encmsg), len(self.message) + self.box.NONCE_SIZE + self.box.MACBYTES
        )
        dec = self.box.decrypt(encmsg, self.aad)
        self.assertEqual(dec, self.message)

    def test_aead_wrong_aad_fails(self):
        encmsg = self.box.encrypt(self.message, self.aad)
        with self.assertRaises(exc.CryptoError):
            self.box.decrypt(encmsg, b"WRONG")


# --- Digital Signatures ------------------------------------------------------
class TestSigning(unittest.TestCase):
    def setUp(self):
        self.sk = SigningKey.generate()
        self.vk = self.sk.verify_key
        self.msg = b"Attack at Dawn"

    def test_sign_verify_raw(self):
        signed = self.sk.sign(self.msg)
        # Two equivalent verify interfaces
        self.assertEqual(self.vk.verify(signed), self.msg)
        self.assertEqual(self.vk.verify(signed.message, signed.signature), self.msg)

    def test_forged_signature_raises(self):
        signed = self.sk.sign(self.msg)
        forged = signed[:-1] + bytes([signed[-1] ^ 1])
        with self.assertRaises(exc.BadSignatureError):
            self.vk.verify(forged)

    def test_hex_encoder_roundtrip(self):
        signed_hex = self.sk.sign(self.msg, encoder=enc.HexEncoder)
        vk_hex = self.vk.encode(encoder=enc.HexEncoder)
        vk2 = VerifyKey(vk_hex, encoder=enc.HexEncoder)
        # two verify forms
        self.assertEqual(vk2.verify(signed_hex, encoder=enc.HexEncoder), self.msg)
        sig_bytes = enc.HexEncoder.decode(signed_hex.signature)
        self.assertEqual(
            vk2.verify(signed_hex.message, sig_bytes, encoder=enc.HexEncoder), self.msg
        )

    def test_base64_encoder_roundtrip(self):
        signed_b64 = self.sk.sign(self.msg, encoder=enc.Base64Encoder)
        vk_b64 = self.vk.encode(encoder=enc.Base64Encoder)
        vk2 = VerifyKey(vk_b64, encoder=enc.Base64Encoder)
        self.assertEqual(vk2.verify(signed_b64, encoder=enc.Base64Encoder), self.msg)
        sig_bytes = enc.Base64Encoder.decode(signed_b64.signature)
        self.assertEqual(
            vk2.verify(signed_b64.message, sig_bytes, encoder=enc.Base64Encoder), self.msg
        )


# --- Encoders & Utilities ----------------------------------------------------
class TestEncodersAndUtilities(unittest.TestCase):
    def test_encoders_roundtrip_for_signingkey(self):
        sk = SigningKey.generate()
        hex_key = sk.encode(encoder=enc.HexEncoder)
        sk2 = SigningKey(hex_key, encoder=enc.HexEncoder)
        self.assertEqual(sk.encode(), sk2.encode())

        b64_key = sk.encode(encoder=enc.Base64Encoder)
        sk3 = SigningKey(b64_key, encoder=enc.Base64Encoder)
        self.assertEqual(sk.encode(), sk3.encode())

    def test_random_and_randombytes_deterministic(self):
        r = nacl.utils.random(32)
        self.assertEqual(len(r), 32)

        seed = nacl.utils.random(32)
        a = nacl.utils.randombytes_deterministic(64, seed)
        b = nacl.utils.randombytes_deterministic(64, seed)
        c = nacl.utils.randombytes_deterministic(64, nacl.utils.random(32))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

        # Wrong seed length -> TypeError
        with self.assertRaises(TypeError):
            nacl.utils.randombytes_deterministic(32, b"short")


# --- Hashing -----------------------------------------------------------------
class TestHashing(unittest.TestCase):
    def setUp(self):
        self.msg = (b"256 BytesMessage" * 16)

    def test_sha256_matches_hashlib(self):
        import hashlib
        dgst_hex = nhash.sha256(self.msg, encoder=enc.HexEncoder)
        self.assertEqual(dgst_hex, hashlib.sha256(self.msg).hexdigest().encode())

    def test_sha512_matches_hashlib(self):
        import hashlib
        dgst_hex = nhash.sha512(self.msg, encoder=enc.HexEncoder)
        self.assertEqual(dgst_hex, hashlib.sha512(self.msg).hexdigest().encode())

    def test_blake2b_keyed_mac_and_derivation(self):
        import hashlib
        # Explicitly pin digest_size for cross-impl consistency
        d1 = nhash.blake2b(self.msg, digest_size=64, encoder=enc.HexEncoder)
        h = hashlib.blake2b(self.msg, digest_size=64)
        self.assertEqual(d1, h.hexdigest().encode())
        # Keyed MAC: same msg+key -> same MAC; change key or msg -> different
        key = nacl.utils.random(32)
        mac0 = nhash.blake2b(self.msg, key=key, digest_size=64, encoder=enc.HexEncoder)
        mac1 = nhash.blake2b(
            self.msg, key=nacl.utils.random(32), digest_size=64, encoder=enc.HexEncoder
        )
        mac2 = nhash.blake2b(
            self.msg + b"x", key=key, digest_size=64, encoder=enc.HexEncoder
        )
        self.assertNotEqual(mac0, mac1)
        self.assertNotEqual(mac0, mac2)

    def test_siphash24_basic(self):
        key = nacl.utils.random(16)  # SipHash-2-4 uses 16-byte key
        d0 = nhash.siphash24(b"hello", key=key)
        d1 = nhash.siphash24(b"hello", key=key)
        d2 = nhash.siphash24(b"world", key=key)
        self.assertIsInstance(d0, bytes)
        self.assertEqual(d0, d1)
        self.assertNotEqual(d0, d2)

    def test_siphashx24_basic(self):
        key = nacl.utils.random(16)
        d0 = nhash.siphashx24(b"hello", key=key)
        d1 = nhash.siphashx24(b"hello", key=key)
        d2 = nhash.siphashx24(b"world", key=key)
        self.assertIsInstance(d0, bytes)
        self.assertEqual(d0, d1)
        self.assertNotEqual(d0, d2)


# --- Password hashing / KDF --------------------------------------------------
class TestPasswordHashing(unittest.TestCase):
    def setUp(self):
        self.password = b"my password"
        self.wrong = b"My password"

    def test_top_level_str_and_verify(self):
        h = nacl.pwhash.str(self.password)
        self.assertTrue(isinstance(h, (bytes, bytearray)))
        # Correct password -> True; wrong raises
        self.assertTrue(nacl.pwhash.verify(h, self.password))
        with self.assertRaises(exc.InvalidkeyError):
            nacl.pwhash.verify(h, self.wrong)

    def test_mechanism_specific_str_and_verify(self):
        # argon2id
        h_id = nacl.pwhash.argon2id.str(self.password)
        self.assertTrue(nacl.pwhash.argon2id.verify(h_id, self.password))
        with self.assertRaises(exc.InvalidkeyError):
            nacl.pwhash.argon2id.verify(h_id, self.wrong)
        # argon2i
        h_i = nacl.pwhash.argon2i.str(self.password)
        self.assertTrue(nacl.pwhash.argon2i.verify(h_i, self.password))
        with self.assertRaises(exc.InvalidkeyError):
            nacl.pwhash.argon2i.verify(h_i, self.wrong)

    def test_kdf_and_secretbox_roundtrip(self):
        # Use interactive limits for speed in CI
        kdf = nacl.pwhash.argon2i.kdf
        salt = nacl.utils.random(nacl.pwhash.argon2i.SALTBYTES)
        ops = nacl.pwhash.argon2i.OPSLIMIT_INTERACTIVE
        mem = nacl.pwhash.argon2i.MEMLIMIT_INTERACTIVE
        size = SecretBox.KEY_SIZE
        key1 = kdf(size, self.password, salt, opslimit=ops, memlimit=mem)
        key2 = kdf(size, self.password, salt, opslimit=ops, memlimit=mem)
        self.assertEqual(key1, key2)
        box = SecretBox(key1)
        msg = b"This is a message for Bob's eyes only"
        nonce = nacl.utils.random(SecretBox.NONCE_SIZE)
        ct = box.encrypt(msg, nonce)
        self.assertEqual(box.decrypt(ct), msg)
        # Wrong password -> different key -> decryption failure
        wrong_key = kdf(size, self.wrong, salt, opslimit=ops, memlimit=mem)
        wrong_box = SecretBox(wrong_key)
        with self.assertRaises(exc.CryptoError):
            wrong_box.decrypt(ct)


# --- Exceptions --------------------------------------------------------------
class TestExceptions(unittest.TestCase):
    def test_cryptoerror_base_and_specifics(self):
        # Tamper a SecretBox ciphertext to raise CryptoError
        key = nacl.utils.random(SecretBox.KEY_SIZE)
        box = SecretBox(key)
        ct = bytearray(box.encrypt(b"hello"))
        ct[-1] ^= 1
        with self.assertRaises(exc.CryptoError):
            box.decrypt(bytes(ct))
        # Signature failure raises BadSignatureError which is a CryptoError
        sk = SigningKey.generate()
        vk = sk.verify_key
        signed = sk.sign(b"msg")
        forged = signed[:-1] + bytes([signed[-1] ^ 1])
        with self.assertRaises(exc.BadSignatureError):
            vk.verify(forged)


if __name__ == "__main__":
    unittest.main(verbosity=2)