from typing import Final
from dataclasses import dataclass
from functools import partial
from hashlib import sha512

from filen.config import (
    FILE_ENCRYPTION_VERSION,
    METADATA_ENCRYPTION_VERSION,
    FileEncryptionVersion,
    MetadataEncryptionVersion,
)

from ._base import create_pbkdf2hmac_sha512
from ._metadata import (
    decrypt_metadata,
    encrypt_metadata,
)
from ._utils import generate_random_hex_string, generate_random_string

MASTER_KEY_LENGTH: Final = 64
ENCRYPTION_KEY_LENGTH: Final = 32

DERIVE_MASTER_KEY_ITERATIONS: Final = 200_000

master_key_pbkdf2hmac = partial(
    create_pbkdf2hmac_sha512,
    length=MASTER_KEY_LENGTH,
    iterations=DERIVE_MASTER_KEY_ITERATIONS,
)


@dataclass
class DerivedKeyInfo:
    hashed_password: str
    master_key: str


def derive_master_key_and_hashed_password(password: str, salt: str) -> DerivedKeyInfo:
    """Derive master key and hashed password from the raw password and salt"""

    kdf = master_key_pbkdf2hmac(salt=salt.encode())
    key = kdf.derive(password.encode()).hex()

    split_index = len(key) // 2

    return DerivedKeyInfo(
        hashed_password=sha512(key[split_index:].encode()).hexdigest(),
        master_key=key[:split_index],
    )


def encrypt_master_keys(
    master_keys: list[str],
    encryption_version: MetadataEncryptionVersion = METADATA_ENCRYPTION_VERSION,
) -> str:
    """Encrypt the list of master keys"""

    master_keys_metadata = '|'.join(master_keys)
    return encrypt_metadata(master_keys_metadata, master_keys[-1], encryption_version=encryption_version)


def decrypt_master_keys(master_keys: str, key: str) -> list[str]:
    """Decrypt master keys"""

    return decrypt_metadata(master_keys, key).split('|')


def generate_file_encryption_key(version: FileEncryptionVersion = FILE_ENCRYPTION_VERSION) -> str:
    """Generate file encryption key"""

    if version in (FileEncryptionVersion.v1, FileEncryptionVersion.v2):
        return generate_random_string(ENCRYPTION_KEY_LENGTH)
    else:
        return generate_random_hex_string(ENCRYPTION_KEY_LENGTH)


def generate_metadata_encryption_key(version: MetadataEncryptionVersion = METADATA_ENCRYPTION_VERSION) -> str:
    """Generate metadata encryption key for a public link"""

    if version in (MetadataEncryptionVersion.v1, MetadataEncryptionVersion.v2):
        return generate_random_string(ENCRYPTION_KEY_LENGTH)
    else:
        return generate_random_hex_string(ENCRYPTION_KEY_LENGTH)


def generate_rm():
    return generate_random_string(ENCRYPTION_KEY_LENGTH)


def generate_upload_key():
    return generate_random_string(ENCRYPTION_KEY_LENGTH)
