from typing import Final, NamedTuple
from base64 import b64decode
from hashlib import file_digest, sha1, sha256, sha512
import hmac
from os import PathLike

from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from filen.config import PUBLIC_LINK_VERSION, AuthVersion, PublicLinkVersion

from ._base import backend, create_pbkdf2hmac_sha512
from ._utils import generate_random_string

HMAC_KEY_LENGTH: Final = 32

data_hasher = sha512


def derive_hmac_sha256_key(private_key: str) -> bytes:
    """Derive hmac SHA-256 key from a user private key for using in hmac hash fucntion"""

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


def hash_file(file_path: PathLike) -> str:
    with open(file_path, 'rb') as fp:
        return file_digest(fp, data_hasher).hexdigest()


def hash_data(data: bytes) -> str:
    return data_hasher(data).hexdigest()


class HashedPasswordAndSalt(NamedTuple):
    password_hashed: str
    salt: str


def hash_public_link_password(
    password: str | None,
    public_link_version: PublicLinkVersion = PUBLIC_LINK_VERSION,
) -> HashedPasswordAndSalt:
    """Hash public link password and return password and salt"""

    match public_link_version:
        case PublicLinkVersion.v1:
            password_hashed = combined_sha_hash_func(password) if password else 'empty'

            return HashedPasswordAndSalt(
                password_hashed=password_hashed,
                salt='',
            )

        case PublicLinkVersion.v2:
            salt = generate_random_string(32)
            deriver = create_pbkdf2hmac_sha512(
                length=64,
                salt=salt.encode(),
                iterations=200_000,
            )
            password_hashed = deriver.derive(password.encode()).hex() if password else 'empty'

            return HashedPasswordAndSalt(
                password_hashed=password_hashed,
                salt=salt,
            )

        # case PublicLinkVersion.v3:
        #     salt = generate_random_hex_string(256)

        case _:
            raise NotImplementedError(
                f'Hashing of public link password is not implemented for public link version {public_link_version}'
            )
