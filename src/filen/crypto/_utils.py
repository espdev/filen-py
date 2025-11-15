from hashlib import sha512

from ._base import DerivedPasswordAndMasterKey, master_key_pbkdf2hmac
from ._metadata import (
    MetadataEncryptionVersion,
    current_metadata_encryption_version,
    decrypt_metadata,
    encrypt_metadata,
)


def derive_password_and_master_key(password: str, salt: str) -> DerivedPasswordAndMasterKey:
    """Derive hashed password and master key from the raw password and salt"""

    kdf = master_key_pbkdf2hmac(salt=salt.encode())
    key = kdf.derive(password.encode()).hex()

    split_index = len(key) // 2

    return DerivedPasswordAndMasterKey(
        password=sha512(key[split_index:].encode()).hexdigest(),
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
