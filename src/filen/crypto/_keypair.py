from typing import Final, NamedTuple
from base64 import b64decode, b64encode

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key as _generate_private_key

from ._base import backend

PUBLIC_EXPONENT: Final = 65537
KEY_SIZE: Final = 2048


class KeyPair(NamedTuple):
    """Key-pair in DER/PEM format"""

    private_key: str
    public_key: str


def generate_private_key() -> RSAPrivateKey:
    return _generate_private_key(
        public_exponent=PUBLIC_EXPONENT,
        key_size=KEY_SIZE,
        backend=backend,
    )


def create_der_keypair(private_key: RSAPrivateKey) -> KeyPair:
    """Return key-pair in DER (Base64) encoding without encryption"""

    public_key = private_key.public_key()

    private_key_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_key_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return KeyPair(
        private_key=b64encode(private_key_der).decode(),
        public_key=b64encode(public_key_der).decode(),
    )


def private_key_der_to_pem(key: str) -> str:
    """Convert a private key from DER to PEM encoding"""

    private_key = serialization.load_der_private_key(
        data=b64decode(key),
        password=None,
        backend=backend,
    )

    pem_data = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return pem_data.decode()


def public_key_der_to_pem(key: str) -> str:
    """Convert a public key from DER to PEM encoding"""

    public_key = serialization.load_der_public_key(
        data=b64decode(key),
        backend=backend,
    )

    pem_data = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return pem_data.decode()


def keypair_der_to_pem(private_key: str, public_key: str) -> KeyPair:
    """Convert key-pair from DER to PEM enconding"""

    return KeyPair(
        private_key=private_key_der_to_pem(private_key),
        public_key=public_key_der_to_pem(public_key),
    )
