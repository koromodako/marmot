"""Marmot cryptographic operations helper
"""
from base64 import b64encode, b64decode
from getpass import getpass
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.hashes import Hash, SHA256
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    PrivateFormat,
    BestAvailableEncryption,
    load_der_public_key,
    load_der_private_key,
)
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey as MarmotPublicKey,
    Ed25519PrivateKey as MarmotPrivateKey,
)
from .logging import LOGGER


def load_marmot_public_key(b64_der_data: str) -> MarmotPublicKey:
    """Load a public key"""
    return load_der_public_key(b64decode(b64_der_data))


def dump_marmot_public_key(pubkey: MarmotPublicKey) -> str:
    """Dump a public key"""
    der_data = pubkey.public_bytes(
        Encoding.DER, PublicFormat.SubjectPublicKeyInfo
    )
    return b64encode(der_data).decode()


def load_marmot_private_key(b64_der_data: str) -> MarmotPrivateKey:
    """Load a passphrase protected private key"""
    passphrase = getpass("private key passphrase please: ")
    if not passphrase:
        passphrase = None
    prikey = load_der_private_key(
        b64decode(b64_der_data), passphrase.encode()
    )
    LOGGER.info("passphrase is correct.")
    return prikey


def dump_marmot_private_key(prikey: MarmotPrivateKey) -> str:
    """Dump a passphrase protected private key"""
    passphrase = getpass("private key passphrase please: ")
    if not passphrase:
        passphrase = None
    der_data = prikey.private_bytes(
        Encoding.DER,
        PrivateFormat.PKCS8,
        BestAvailableEncryption(passphrase.encode()),
    )
    LOGGER.info("passphrase is correct.")
    return b64encode(der_data).decode()


def generate_marmot_private_key() -> MarmotPrivateKey:
    """Generate a passphrase protected private key"""
    return MarmotPrivateKey.generate()


def hash_marmot_data(data: bytes) -> bytes:
    """Compute marmot data digest"""
    digest = Hash(SHA256())
    digest.update(data)
    return digest.finalize()


def sign_marmot_data_digest(prikey: MarmotPrivateKey, digest: bytes) -> str:
    """Sign marmot data using private key"""
    return b64encode(prikey.sign(digest)).decode()


def verify_marmot_data_digest(
    pubkey: MarmotPublicKey, digest: bytes, signature: str
) -> bool:
    """Verify marmot data signature using public key"""
    try:
        pubkey.verify(b64decode(signature), digest)
    except InvalidSignature:
        return False
    return True