from typing import Final
from base64 import b64decode
from hashlib import sha1, sha256, sha512
import hmac

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from filen.config import AuthVersion

from ._base import backend

HMAC_KEY_LENGTH: Final = 32


def generate_hmac_key(private_key: str) -> bytes:
    """Generate hmac key for hashing names"""

    return HKDF(
        algorithm=hashes.SHA256(),
        length=HMAC_KEY_LENGTH,
        salt=None,
        info=b'hmac-sha256-key',
        backend=backend,
    ).derive(b64decode(private_key))


def hash_name(name: str, auth_version: AuthVersion | int, hmac_key: bytes | None = None) -> str:
    """Hash file/folder name"""

    match auth_version:
        case AuthVersion.v1 | AuthVersion.v2:
            return sha1(sha512(name.lower().encode()).hexdigest().encode()).hexdigest()

        case AuthVersion.v3:
            if not hmac_key:
                raise ValueError('hmac_key is required for hashing names with auth version v3.')
            if len(hmac_key) != HMAC_KEY_LENGTH:
                raise ValueError(f'hmac_key must be with {HMAC_KEY_LENGTH} length.')

            return hmac.new(hmac_key, name.lower().encode(), sha256).hexdigest()

        case _:
            raise NotImplementedError(f'Hashing names is not implemented for auth version {auth_version.value}')
