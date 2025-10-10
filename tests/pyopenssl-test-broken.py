import time
from OpenSSL import SSL, crypto

def generate_key(bits=2048):
    pkey = crypto.PKey()
    pkey.generate_key(crypto.TYPE_RSA, bits)
    return pkey

def generate_self_signed_cert(common_name=b"localhost", days_valid=365, pkey=None, digest=b"sha256"):
    if pkey is None:
        pkey = generate_key()

    cert = crypto.X509()
    subj = cert.get_subject()
    subj.CN = common_name.decode()
    subj.O = "Test Org"
    subj.OU = "Testing"
    subj.C = "US"
    cert.set_serial_number(int(time.time()))
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(days_valid * 24 * 60 * 60)
    cert.set_issuer(subj)
    cert.set_pubkey(pkey)
    cert.set_version(2)  # v3 (0-based)
    # Add a couple of extensions
    cert.add_extensions([
        crypto.X509Extension(b"basicConstraints", False, b"CA:TRUE"),
        crypto.X509Extension(b"keyUsage", False, b"keyEncipherment, dataEncipherment, digitalSignature, keyCertSign"),
        crypto.X509Extension(b"subjectAltName", False, b"DNS:localhost,IP:127.0.0.1"),
    ])
    cert.sign(pkey, digest.decode())
    return cert, pkey

generate_self_signed_cert(common_name=b"localhost")