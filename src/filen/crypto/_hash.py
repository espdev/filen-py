from typing import Final
from base64 import b64decode
from hashlib import sha1, sha256, sha512
import hmac

from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from filen.config import AuthVersion

from ._base import backend

HMAC_KEY_LENGTH: Final = 32


def generate_hmac_key(private_key: str) -> bytes:
    """Generate hmac key for hashing names"""

    return HKDF(
        algorithm=SHA256(),
        length=HMAC_KEY_LENGTH,
        salt=None,
        info=b'hmac-sha256-key',
        backend=backend,
    ).derive(b64decode(private_key))


def combined_sha_hash_func(text: str) -> str:
    """sha1/sha512 combined hash function"""

    return sha1(sha512(text.encode()).hexdigest().encode()).hexdigest()


def hmac_sha256_hash_func(text: str, hmac_key: bytes) -> str:
    """hmac sha256 hash function"""

    return hmac.new(hmac_key, text.encode(), sha256).hexdigest()


def hash_name(name: str, auth_version: AuthVersion | int, hmac_key: bytes | None = None) -> str:
    """Hash storage item (file/folder) name"""

    name = name.lower()

    match auth_version:
        case AuthVersion.v1 | AuthVersion.v2:
            return combined_sha_hash_func(name)

        case AuthVersion.v3:
            if hmac_key is None:
                raise ValueError('hmac_key is required for hashing names with auth version v3.')
            elif len(hmac_key) != HMAC_KEY_LENGTH:
                raise ValueError(f'hmac_key must be with {HMAC_KEY_LENGTH} length.')

            return hmac_sha256_hash_func(name, hmac_key)

        case _:
            raise NotImplementedError(f'Hashing names is not implemented for auth version {auth_version.value}')
