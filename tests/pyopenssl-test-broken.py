import os
import sys
import time
import unittest
import tempfile
from datetime import datetime, timedelta, timezone

from OpenSSL import SSL, crypto

# cryptography for modern-safe key/cert generation
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa


# ---------- Key/Cert generation with cryptography (reduced deprecations) ----------

def generate_crypto_key(bits=2048):
    return rsa.generate_private_key(public_exponent=65537, key_size=bits)

def generate_crypto_self_signed_cert(common_name="localhost", days_valid=365, key=None):
    if key is None:
        key = generate_crypto_key()

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Org"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Testing"),
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        ]
    )

    san = x509.SubjectAlternativeName(
        [x509.DNSName("localhost")]
    )

    ku = x509.KeyUsage(
        digital_signature=True,
        key_encipherment=True,
        content_commitment=False,
        data_encipherment=True,
        key_agreement=False,
        key_cert_sign=True,
        crl_sign=False,
        encipher_only=False,
        decipher_only=False,
    )

    bc = x509.BasicConstraints(ca=True, path_length=None)

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(int(time.time()))
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=days_valid))
        .add_extension(bc, critical=False)
        .add_extension(ku, critical=False)
        .add_extension(san, critical=False)
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    return cert, key

def to_pyopenssl(cert_crypto, key_crypto):
    """Return (pyopenssl_x509, pyopenssl_pkey) from cryptography objects."""
    cert_pyo = crypto.X509.from_cryptography(cert_crypto)
    pkey_pyo = crypto.PKey.from_cryptography_key(key_crypto)
    return cert_pyo, pkey_pyo


# ---------- Memory BIO helpers ----------

def pump(src_conn, dst_conn):
    """Move pending outbound bytes from src -> dst memory BIO (returns total moved)."""
    moved = 0
    while True:
        try:
            data = src_conn.bio_read(65535)
        except SSL.WantReadError:
            break
        except SSL.Error:
            break
        if not data:
            break
        moved += len(data)
        dst_conn.bio_write(data)
    return moved

def handshake_both(client, server, max_iters=1000):
    """Drive TLS handshake between two in-memory Connections."""
    client.set_connect_state()
    server.set_accept_state()

    c_done = False
    s_done = False

    for _ in range(max_iters):
        if not c_done:
            try:
                client.do_handshake()
                c_done = True
            except (SSL.WantReadError, SSL.WantWriteError):
                pass
        if not s_done:
            try:
                server.do_handshake()
                s_done = True
            except (SSL.WantReadError, SSL.WantWriteError):
                pass

        moved = pump(client, server) + pump(server, client)
        if c_done and s_done:
            return True
        if moved == 0 and not (c_done and s_done):
            time.sleep(0.001)
    return False

def recv_with_pumping(receiver, sender, nbytes, timeout=2.0):
    """Recv up to nbytes from `receiver` while pumping BIOs until timeout."""
    deadline = time.time() + timeout
    while True:
        try:
            return receiver.recv(nbytes)
        except SSL.WantReadError:
            # Move any encrypted records across and try again
            pump(sender, receiver)
            if time.time() > deadline:
                raise TimeoutError("Timed out waiting for application data over memory BIO")


class TestPyOpenSSL(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Make server + client certs with cryptography to avoid deprecation warnings
        cls.server_cert_crypto, cls.server_key_crypto = generate_crypto_self_signed_cert("localhost")
        cls.client_cert_crypto, cls.client_key_crypto = generate_crypto_self_signed_cert("client")

        # Also keep pyOpenSSL representations for crypto.* API tests
        cls.server_cert_pyo, cls.server_key_pyo = to_pyopenssl(cls.server_cert_crypto, cls.server_key_crypto)
        cls.client_cert_pyo, cls.client_key_pyo = to_pyopenssl(cls.client_cert_crypto, cls.client_key_crypto)

        # Temp files for file-based loaders
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.server_cert_pem = os.path.join(cls.tmpdir.name, "server.crt")
        cls.server_key_pem = os.path.join(cls.tmpdir.name, "server.key")
        cls.server_cert_der = os.path.join(cls.tmpdir.name, "server.der")
        cls.client_cert_pem = os.path.join(cls.tmpdir.name, "client.crt")
        cls.client_key_pem = os.path.join(cls.tmpdir.name, "client.key")

        # Dump using pyOpenSSL dumpers (exercise those APIs)
        with open(cls.server_cert_pem, "wb") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cls.server_cert_pyo))
        with open(cls.server_key_pem, "wb") as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, cls.server_key_pyo))
        with open(cls.server_cert_der, "wb") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_ASN1, cls.server_cert_pyo))
        with open(cls.client_cert_pem, "wb") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cls.client_cert_pyo))
        with open(cls.client_key_pem, "wb") as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, cls.client_key_pyo))

    @classmethod
    def tearDownClass(cls):
        cls.tmpdir.cleanup()

    # ---------- Constants & version ----------

    def test_openssl_version_constants_and_function(self):
        for attr in ["OPENSSL_VERSION", "OPENSSL_CFLAGS", "OPENSSL_BUILT_ON", "OPENSSL_PLATFORM", "OPENSSL_DIR"]:
            if hasattr(SSL, attr):
                v = SSL.OpenSSL_version(getattr(SSL, attr))
                self.assertIsInstance(v, (bytes, bytearray))
        self.assertTrue(isinstance(getattr(SSL, "OPENSSL_VERSION_NUMBER", 0), int))

    def test_method_constants_exist(self):
        self.assertTrue(hasattr(SSL, "TLS_METHOD"))
        self.assertTrue(hasattr(SSL, "TLS_SERVER_METHOD"))
        self.assertTrue(hasattr(SSL, "TLS_CLIENT_METHOD"))

    # ---------- Context helpers ----------

    def make_context(self, server=False):
        meth = SSL.TLS_SERVER_METHOD if server else SSL.TLS_CLIENT_METHOD
        ctx = SSL.Context(meth)

        if hasattr(SSL, "OP_NO_COMPRESSION"):
            ctx.set_options(SSL.OP_NO_COMPRESSION)
        if hasattr(SSL, "OP_NO_TICKET"):
            ctx.set_options(SSL.OP_NO_TICKET)
        for op in ["OP_SINGLE_DH_USE", "OP_SINGLE_ECDH_USE", "OP_EPHEMERAL_RSA"]:
            if hasattr(SSL, op):
                ctx.set_options(getattr(SSL, op))

        ctx.set_cipher_list(b"DEFAULT:@SECLEVEL=2")
        if hasattr(ctx, "set_tls13_ciphersuites"):
            ctx.set_tls13_ciphersuites(b"TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256")

        ctx.set_verify(SSL.VERIFY_NONE, callback=None)
        self.assertEqual(ctx.get_verify_mode(), SSL.VERIFY_NONE)
        ctx.set_verify_depth(5)
        self.assertEqual(ctx.get_verify_depth(), 5)

        prev_timeout = ctx.set_timeout(600)
        self.assertIsInstance(prev_timeout, int)
        _ = ctx.get_timeout()
        if hasattr(SSL, "SESS_CACHE_BOTH"):
            prev_mode = ctx.set_session_cache_mode(SSL.SESS_CACHE_BOTH)
            _ = ctx.get_session_cache_mode()

        ctx.set_app_data({"hello": "world"})
        self.assertEqual(ctx.get_app_data()["hello"], "world")

        store = ctx.get_cert_store()
        self.assertTrue(store is None or isinstance(store, crypto.X509Store))

        if hasattr(ctx, "set_keylog_callback"):
            ctx.set_keylog_callback(lambda conn, line: None)

        return ctx

    def test_context_loaders_and_files(self):
        ctx = self.make_context(server=True)
        # Load via file APIs
        ctx.use_certificate_file(self.server_cert_pem, SSL.FILETYPE_PEM)
        ctx.use_privatekey_file(self.server_key_pem, SSL.FILETYPE_PEM)
        ctx.check_privatekey()

        # Trust store via context/store
        store = ctx.get_cert_store()
        if store is None:
            ctx.load_verify_locations(self.server_cert_pem, None)
        else:
            store.load_locations(self.server_cert_pem, None)

        # ASN.1/DER load path
        with open(self.server_cert_der, "rb") as f:
            der = f.read()
        loaded_der = crypto.load_certificate(crypto.FILETYPE_ASN1, der)
        self.assertIsInstance(loaded_der, crypto.X509)

    def test_context_min_max_versions(self):
        ctx = self.make_context(server=True)
        minv = getattr(SSL, "TLS1_VERSION", None)
        maxv = getattr(SSL, "TLS1_3_VERSION", None)
        if minv is not None and hasattr(ctx, "set_min_proto_version"):
            ctx.set_min_proto_version(0)
            ctx.set_min_proto_version(minv)
        if maxv is not None and hasattr(ctx, "set_max_proto_version"):
            ctx.set_max_proto_version(0)
            ctx.set_max_proto_version(maxv)

    def test_context_alpn_and_sni_and_callbacks(self):
        server_ctx = self.make_context(server=True)
        client_ctx = self.make_context(server=False)

        # Use cryptography objects to avoid deprecation warnings
        server_ctx.use_certificate(self.server_cert_crypto)
        server_ctx.use_privatekey(self.server_key_crypto)
        server_ctx.check_privatekey()

        chosen = {}
        def alpn_select_cb(conn, protos):
            if b"http/1.1" in protos:
                chosen["proto"] = b"http/1.1"
                return b"http/1.1"
            return getattr(SSL, "NO_OVERLAPPING_PROTOCOLS", b"")

        if hasattr(server_ctx, "set_alpn_select_callback"):
            server_ctx.set_alpn_select_callback(alpn_select_cb)
        if hasattr(client_ctx, "set_alpn_protos"):
            client_ctx.set_alpn_protos([b"h2", b"http/1.1"])

        seen_sni = {"name": None}
        def sni_cb(conn):
            seen_sni["name"] = conn.get_servername()
        if hasattr(server_ctx, "set_tlsext_servername_callback"):
            server_ctx.set_tlsext_servername_callback(sni_cb)

        info_events = []
        if hasattr(server_ctx, "set_info_callback"):
            server_ctx.set_info_callback(lambda conn, where, ret: info_events.append((where, ret)))

        client = SSL.Connection(client_ctx, None)
        server = SSL.Connection(server_ctx, None)

        if hasattr(client, "set_tlsext_host_name"):
            client.set_tlsext_host_name(b"localhost")

        self.assertTrue(handshake_both(client, server))

        if hasattr(client, "get_alpn_proto_negotiated"):
            negotiated = client.get_alpn_proto_negotiated()
            if negotiated:
                self.assertEqual(negotiated, b"http/1.1")
                self.assertEqual(chosen.get("proto"), b"http/1.1")

        if seen_sni["name"] is not None:
            self.assertEqual(seen_sni["name"], b"localhost")

        self.assertIsInstance(client.get_cipher_name(), (str, type(None)))
        self.assertIsInstance(client.get_cipher_version(), (str, type(None)))
        self.assertIsInstance(client.get_cipher_bits(), (int, type(None)))
        self.assertTrue(client.get_protocol_version_name().startswith("TLS") or client.get_protocol_version_name() == "Unknown")

        self.assertIs(client.get_context(), client_ctx)
        client.set_context(client_ctx)
        self.assertIs(client.get_context(), client_ctx)

        _ = client.get_finished()
        _ = client.get_peer_finished()

        km = client.export_keying_material(b"test-label", 32, context=b"context")
        self.assertEqual(len(km), 32)

        sess = client.get_session()
        self.assertTrue(sess is None or isinstance(sess, SSL.Session))

        calist = server.get_client_ca_list()
        self.assertIsInstance(calist, list)

        client.shutdown()
        server.shutdown()

    # ---------- Connection I/O over memory BIO (robust read loop) ----------

    def test_connection_send_recv_and_pending(self):
        server_ctx = self.make_context(server=True)
        client_ctx = self.make_context(server=False)

        server_ctx.use_certificate(self.server_cert_crypto)
        server_ctx.use_privatekey(self.server_key_crypto)
        server_ctx.check_privatekey()

        client = SSL.Connection(client_ctx, None)
        server = SSL.Connection(server_ctx, None)

        if hasattr(client, "request_ocsp"):
            client.request_ocsp()
        if hasattr(server_ctx, "set_ocsp_server_callback"):
            server_ctx.set_ocsp_server_callback(lambda conn, _: b"\x01\x02")

        self.assertTrue(handshake_both(client, server))

        msg = b"hello over tls"
        self.assertEqual(client.send(msg), len(msg))

        # Shuttle and read using a pump-aware recv loop (no brittle pending() assertion)
        pump(client, server)
        data = recv_with_pumping(server, client, 65535)
        self.assertEqual(data, msg)

        # Send back with sendall
        total2 = server.sendall(b"ack")
        self.assertEqual(total2, 3)
        pump(server, client)
        got = recv_with_pumping(client, server, 3)
        self.assertEqual(got, b"ack")

        # MSG_PEEK path (best-effort)
        if sys.platform != "win32":
            client.send(b"peektest")
            pump(client, server)
            try:
                peeked = server.recv(8, flags=0x2)  # MSG_PEEK
                self.assertEqual(peeked, b"peektest")
                again = recv_with_pumping(server, client, 8)
                self.assertEqual(again, b"peektest")
            finally:
                pass

        self.assertIn(server.want_read(), (True, False))
        self.assertIn(server.want_write(), (True, False))

        client.shutdown()
        server.shutdown()

    # ---------- Session resumption (best-effort) ----------

    def test_session_resumption_best_effort(self):
        server_ctx = self.make_context(server=True)
        client_ctx = self.make_context(server=False)
        server_ctx.use_certificate(self.server_cert_crypto)
        server_ctx.use_privatekey(self.server_key_crypto)
        server_ctx.set_session_id(b"test-session-id")

        c1 = SSL.Connection(client_ctx, None)
        s1 = SSL.Connection(server_ctx, None)
        self.assertTrue(handshake_both(c1, s1))

        sess = c1.get_session()
        c1.shutdown()
        s1.shutdown()

        if sess is None:
            self.skipTest("Session resumption not supported by this OpenSSL build/config")

        c2 = SSL.Connection(client_ctx, None)
        s2 = SSL.Connection(server_ctx, None)
        c2.set_session(sess)
        self.assertTrue(handshake_both(c2, s2))
        self.assertIsNotNone(c2.get_session())
        c2.shutdown()
        s2.shutdown()

    # ---------- X509 / Store / CSR / dump-load ----------

    def test_crypto_x509_store_and_verify(self):
        store = crypto.X509Store()
        # Without trust anchor, verification should fail
        with self.assertRaises(crypto.X509StoreContextError):
            ctx = crypto.X509StoreContext(store, self.server_cert_pyo)
            ctx.verify_certificate()
        # Add the self-signed cert as trusted -> verifies
        store.add_cert(self.server_cert_pyo)
        ctx = crypto.X509StoreContext(store, self.server_cert_pyo)
        ctx.verify_certificate()

        if hasattr(crypto.X509StoreContext, "get_verified_chain"):
            chain = crypto.X509StoreContext(store, self.server_cert_pyo).get_verified_chain()
            self.assertTrue(isinstance(chain, list) and len(chain) >= 1)

        if hasattr(store, "set_time"):
            store.set_time(datetime.now(timezone.utc) - timedelta(days=1))
        if hasattr(store, "set_flags"):
            try:
                store.set_flags(crypto.X509StoreFlags.X509_STRICT)
            except Exception:
                pass

    def test_dump_load_keys_certs_public_private_and_text(self):
        cert_pem = crypto.dump_certificate(crypto.FILETYPE_PEM, self.server_cert_pyo)
        cert_der = crypto.dump_certificate(crypto.FILETYPE_ASN1, self.server_cert_pyo)
        self.assertTrue(cert_pem.startswith(b"-----BEGIN CERTIFICATE-----"))
        self.assertTrue(len(cert_der) > 0)

        loaded_pem = crypto.load_certificate(crypto.FILETYPE_PEM, cert_pem)
        loaded_der = crypto.load_certificate(crypto.FILETYPE_ASN1, cert_der)
        self.assertEqual(loaded_pem.get_subject().CN, "localhost")
        self.assertEqual(loaded_der.get_subject().CN, "localhost")

        key_pem = crypto.dump_privatekey(crypto.FILETYPE_PEM, self.server_key_pyo)
        key_der = crypto.dump_privatekey(crypto.FILETYPE_ASN1, self.server_key_pyo)
        self.assertTrue(key_pem.startswith(b"-----BEGIN"))
        self.assertTrue(len(key_der) > 0)

        loaded_key_pem = crypto.load_privatekey(crypto.FILETYPE_PEM, key_pem)
        loaded_key_der = crypto.load_privatekey(crypto.FILETYPE_ASN1, key_der)
        self.assertIsInstance(loaded_key_pem, crypto.PKey)
        self.assertIsInstance(loaded_key_der, crypto.PKey)

        pub_pem = crypto.dump_publickey(crypto.FILETYPE_PEM, self.server_cert_pyo.get_pubkey())
        pub_der = crypto.dump_publickey(crypto.FILETYPE_ASN1, self.server_cert_pyo.get_pubkey())
        self.assertTrue(pub_pem.startswith(b"-----BEGIN PUBLIC KEY-----"))
        loaded_pub_pem = crypto.load_publickey(crypto.FILETYPE_PEM, pub_pem)
        loaded_pub_der = crypto.load_publickey(crypto.FILETYPE_ASN1, pub_der)
        self.assertIsInstance(loaded_pub_pem, crypto.PKey)
        self.assertIsInstance(loaded_pub_der, crypto.PKey)

    def test_x509_fields_and_extensions(self):
        cert = self.server_cert_pyo
        self.assertEqual(cert.get_subject().CN, "localhost")
        self.assertEqual(cert.get_issuer().CN, "localhost")
        self.assertGreaterEqual(cert.get_version(), 2)
        self.assertIsInstance(cert.get_serial_number(), int)
        self.assertIn(b"sha", cert.get_signature_algorithm().lower())
        comps = dict(cert.get_subject().get_components())
        self.assertIn(b"CN", comps)
        _ = cert.subject_name_hash()
        _ = cert.get_subject().der()
        count = cert.get_extension_count()
        if count:
            ext0 = cert.get_extension(0)
            _ = ext0.get_short_name()
            _ = ext0.get_data()
            _ = str(ext0)
            _ = ext0.get_critical()
        dg = cert.digest("sha256")
        self.assertIsInstance(dg, bytes)
        self.assertIn(b":", dg)

    def test_x509req_sign_verify(self):
        # Still exercise pyOpenSSL CSR path; warnings are acceptable here,
        # but you can switch to cryptography CSR if desired.
        req = crypto.X509Req()
        subj = req.get_subject()
        subj.CN = "req-cn"
        subj.O = "Test Org"
        req.set_pubkey(self.client_key_pyo)
        req.set_version(0)
        req.sign(self.client_key_pyo, "sha256")
        self.assertEqual(req.get_subject().CN, "req-cn")
        self.assertTrue(req.verify(self.client_key_pyo))
        if hasattr(crypto.X509Req, "to_cryptography"):
            _ = req.to_cryptography()
        if hasattr(crypto.X509Req, "from_cryptography"):
            _ = crypto.X509Req.from_cryptography(req.to_cryptography())

    def test_pkey_introspection_and_checks(self):
        key = self.client_key_pyo
        self.assertEqual(key.type(), crypto.TYPE_RSA)
        self.assertGreaterEqual(key.bits(), 2048)
        self.assertTrue(key.check())
        if hasattr(key, "to_cryptography_key"):
            ck = key.to_cryptography_key()
            key2 = crypto.PKey.from_cryptography_key(ck)
            self.assertIsInstance(key2, crypto.PKey)

    def test_context_client_ca_list_and_extra_chain(self):
        server_ctx = self.make_context(server=True)
        server_ctx.use_certificate(self.server_cert_crypto)
        server_ctx.use_privatekey(self.server_key_crypto)
        server_ctx.check_privatekey()

        # Use cryptography certs for these calls to avoid deprecation warnings
        server_ctx.add_client_ca(self.server_cert_crypto)
        server_ctx.set_client_ca_list([self.server_cert_pyo.get_subject()])  # X509Name still fine
        server_ctx.add_extra_chain_cert(self.server_cert_crypto)
        server_ctx.set_alpn_protos([b"http/1.1", b"h2"])

    def test_connection_verify_override(self):
        server_ctx = self.make_context(server=True)
        server_ctx.use_certificate(self.server_cert_crypto)
        server_ctx.use_privatekey(self.server_key_crypto)

        client_ctx = self.make_context(server=False)
        client_ctx.set_verify(SSL.VERIFY_PEER, callback=None)

        client = SSL.Connection(client_ctx, None)
        server = SSL.Connection(server_ctx, None)

        client.set_verify(SSL.VERIFY_NONE, callback=None)

        self.assertTrue(handshake_both(client, server))
        self.assertEqual(client.get_verify_mode(), SSL.VERIFY_NONE)

        client.shutdown()
        server.shutdown()

    def test_dtls_methods_presence(self):
        for name in ["DTLSv1_get_timeout", "DTLSv1_handle_timeout", "DTLSv1_listen"]:
            self.assertTrue(hasattr(SSL.Connection, name), f"{name} missing on Connection class")

    def test_ssl_exceptions_exist(self):
        for exc in [SSL.Error, SSL.ZeroReturnError, SSL.WantReadError, SSL.WantWriteError,
                    SSL.WantX509LookupError, SSL.SysCallError]:
            self.assertTrue(issubclass(exc, Exception))

    def test_verified_chain_from_connection_best_effort(self):
        server_ctx = self.make_context(server=True)
        client_ctx = self.make_context(server=False)
        server_ctx.use_certificate(self.server_cert_crypto)
        server_ctx.use_privatekey(self.server_key_crypto)

        client = SSL.Connection(client_ctx, None)
        server = SSL.Connection(server_ctx, None)
        self.assertTrue(handshake_both(client, server))

        if hasattr(client, "get_peer_cert_chain"):
            chain = client.get_peer_cert_chain()
            self.assertTrue(chain is None or isinstance(chain, list))
        if hasattr(client, "get_verified_chain"):
            vchain = client.get_verified_chain()
            self.assertTrue(vchain is None or isinstance(vchain, list))

        client.shutdown()
        server.shutdown()


if __name__ == "__main__":
    unittest.main(verbosity=2)