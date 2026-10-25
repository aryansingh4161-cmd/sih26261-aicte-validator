"""A DEMO certificate authority (not a real CA) so we can sign synthetic affidavits and validate them with pyHanko.
make_pki(dir) writes demo_root.pem, signer_key.pem, signer_cert.pem. sign_pdf(src, dst, dir) needs pyHanko (UNTESTED by
the author; test on a Mac). OWNER: Jasraj."""
from __future__ import annotations

import datetime as dt
import os


def make_pki(d: str = "data/demo/pki", root_copy: str = "config/trust/demo_root.pem") -> dict:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    os.makedirs(d, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)

    def name(cn):
        return x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Pramaan DEMO (synthetic)"),
                          x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    ck = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca = (x509.CertificateBuilder().subject_name(name("Pramaan DEMO Root CA")).issuer_name(name("Pramaan DEMO Root CA"))
          .public_key(ck.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now)
          .not_valid_after(now + dt.timedelta(days=730)).add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
          .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False, data_encipherment=False,
                                       key_agreement=False, key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
          .sign(ck, hashes.SHA256()))
    sk = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    sc = (x509.CertificateBuilder().subject_name(name("Demo Trust Secretary (synthetic)")).issuer_name(ca.subject)
          .public_key(sk.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now)
          .not_valid_after(now + dt.timedelta(days=365))
          .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False, data_encipherment=False,
                                       key_agreement=False, key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
          .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False)
          .sign(ck, hashes.SHA256()))
    pem = serialization.Encoding.PEM
    paths = {"root": os.path.join(d, "demo_root.pem"), "key": os.path.join(d, "signer_key.pem"), "cert": os.path.join(d, "signer_cert.pem")}
    open(paths["root"], "wb").write(ca.public_bytes(pem))
    open(paths["cert"], "wb").write(sc.public_bytes(pem))
    open(paths["key"], "wb").write(sk.private_bytes(pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    os.makedirs(os.path.dirname(root_copy), exist_ok=True)
    open(root_copy, "wb").write(ca.public_bytes(pem))
    return paths


def can_sign() -> bool:
    try:
        import pyhanko.sign  # noqa: F401
        return True
    except Exception:
        return False


def sign_pdf(src: str, dst: str, pki: dict) -> None:
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers
    signer = signers.SimpleSigner.load(pki["key"], pki["cert"], ca_chain_files=(pki["root"],))
    with open(src, "rb") as inf:
        w = IncrementalPdfFileWriter(inf)
        with open(dst + ".tmp", "wb") as outf:
            signers.sign_pdf(w, signers.PdfSignatureMetadata(field_name="Signature1"), signer=signer, output=outf)
    os.replace(dst + ".tmp", dst)
