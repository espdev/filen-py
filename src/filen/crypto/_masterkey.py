from typing import Final
from dataclasses import dataclass
from functools import partial
from hashlib import sha512

from ._base import create_pbkdf2hmac_sha512
from ._metadata import (
    MetadataEncryptionVersion,
    current_metadata_encryption_version,
    decrypt_metadata,
    encrypt_metadata,
)

MASTER_KEY_LENGTH: Final = 64
DERIVE_MASTER_KEY_ITERATIONS: Final = 200_000

master_key_pbkdf2hmac = partial(
    create_pbkdf2hmac_sha512,
    length=MASTER_KEY_LENGTH,
    iterations=DERIVE_MASTER_KEY_ITERATIONS,
)


@dataclass
class DerivedInfo:
    hashed_password: str
    master_key: str


def derive_master_key_and_hashed_password(password: str, salt: str) -> DerivedInfo:
    """Derive master key and hashed password from the raw password and salt"""

    kdf = master_key_pbkdf2hmac(salt=salt.encode())
    key = kdf.derive(password.encode()).hex()

    split_index = len(key) // 2

    return DerivedInfo(
        hashed_password=sha512(key[split_index:].encode()).hexdigest(),
        master_key=key[:split_index],
    )


def encrypt_master_keys(
    master_keys: list[str],
    encryption_version: MetadataEncryptionVersion = current_metadata_encryption_version,
) -> str:
    """Encrypt the list of master keys"""

    master_keys_metadata = '|'.join(master_keys)
    return encrypt_metadata(master_keys_metadata, master_keys[-1], encryption_version=encryption_version)


def decrypt_master_keys(master_keys: str, key: str) -> list[str]:
    """Decrypt master keys"""

    return decrypt_metadata(master_keys, key).split('|')
