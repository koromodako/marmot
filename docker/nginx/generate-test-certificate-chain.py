"""Generate test certificate chain including test CA certificate

TESTING ONLY, UNSAFE FOR PRODUCTION!
"""
import typing as t
from uuid import uuid4
from pathlib import Path
from getpass import getpass
from datetime import timedelta, datetime
from argparse import ArgumentParser
from cryptography.x509 import (
    Name,
    DNSName,
    NameAttribute,
    BasicConstraints,
    SubjectAlternativeName,
    Certificate,
    CertificateBuilder,
    CertificateSigningRequest,
    CertificateSigningRequestBuilder,
    random_serial_number,
)
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.asymmetric.rsa import (
    RSAPrivateKey, generate_private_key
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
    NoEncryption,
    BestAvailableEncryption,
)


UTC_NOW = datetime.utcnow()
ONE_DAY = timedelta(days=1)
ONE_MONTH = timedelta(days=30)
ONE_YEAR = timedelta(days=365)


PrivateKey = RSAPrivateKey


def _write_file(filepath: Path, data: bytes):
    print(f"writing: {filepath}")
    filepath.write_bytes(data)


def _generate_private_key(
    keypath: Path, passphrase: t.Optional[str] = None
) -> PrivateKey:
    private_key = generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    encryption_algorithm = NoEncryption()
    if passphrase:
        encryption_algorithm = BestAvailableEncryption(passphrase.encode())
    _write_file(
        keypath,
        private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=encryption_algorithm,
        ),
    )
    return private_key


def _generate_ca(
    keypath: Path, crtpath: Path
) -> t.Tuple[PrivateKey, Certificate]:
    passphrase = getpass("please type CA key passphrase: ")
    ca_key = _generate_private_key(keypath, passphrase)
    subject = issuer = Name(
        [
            NameAttribute(NameOID.COMMON_NAME, "Marmot Test CA"),
            NameAttribute(NameOID.ORGANIZATION_NAME, "Marmot"),
            NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Marmot Testing Unit"),
        ]
    )
    ca_crt = CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).not_valid_before(
        UTC_NOW - ONE_DAY
    ).not_valid_after(
        UTC_NOW + ONE_YEAR
    ).serial_number(
        int(uuid4())
    ).public_key(
        ca_key.public_key()
    ).add_extension(
        BasicConstraints(ca=True, path_length=None), critical=True,
    ).sign(
        private_key=ca_key, algorithm=SHA256(), backend=default_backend()
    )
    _write_file(crtpath, ca_crt.public_bytes(encoding=Encoding.PEM))
    return ca_key, ca_crt


def _generate_csr(keypath: Path, csrpath: Path) -> CertificateSigningRequest:
    private_key = _generate_private_key(keypath)
    csr = CertificateSigningRequestBuilder().subject_name(
        Name(
            [
                NameAttribute(NameOID.COUNTRY_NAME, "US"),
                NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Marmot Mountains"),
                NameAttribute(NameOID.LOCALITY_NAME, "Marmot Mount"),
                NameAttribute(NameOID.ORGANIZATION_NAME, "Marmot Company"),
                NameAttribute(NameOID.COMMON_NAME, "api.marmot.org"),
            ]
        )
    ).add_extension(
        SubjectAlternativeName(
            [
                DNSName("api.marmot.org"),
            ]
        ),
        critical=False,
    ).sign(
        private_key, SHA256()
    )
    _write_file(csrpath, csr.public_bytes(Encoding.PEM))
    return csr


def _sign_csr(
    crtpath: Path,
    csr: CertificateSigningRequest,
    ca_key: PrivateKey,
    ca_crt: Certificate,
) -> Certificate:
    crt = CertificateBuilder().subject_name(
        csr.subject
    ).issuer_name(
        ca_crt.subject
    ).public_key(
        csr.public_key()
    ).serial_number(
        random_serial_number()
    ).not_valid_before(
        UTC_NOW - ONE_DAY
    ).not_valid_after(
        UTC_NOW + ONE_MONTH
    ).sign(
        ca_key, SHA256()
    )
    _write_file(crtpath, crt.public_bytes(Encoding.PEM))
    return crt


def _parse_args():
    parser = ArgumentParser(
        description="Generate test certificate chain including test CA certificate"
    )
    parser.add_argument('--cn', default='api.marmot.org', help="Certificate common name")
    parser.add_argument('--outdir', type=Path, default=Path('.'), help="Output directory")
    return parser.parse_args()


def app():
    """Application entry point"""
    args = _parse_args()
    ca_key, ca_crt = _generate_ca(
        args.outdir / 'marmot.ca.key.pem', args.outdir / 'marmot.ca.crt.pem'
    )
    csr = _generate_csr(
        args.outdir / f'{args.cn}.key.pem', args.outdir / f'{args.cn}.csr.pem'
    )
    _sign_csr(
        args.outdir / f'{args.cn}.crt.pem', csr, ca_key, ca_crt
    )


if __name__ == '__main__':
    app()
