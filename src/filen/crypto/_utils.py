from hashlib import sha512

from ._base import DerivedPasswordAndMasterKey, master_key_pbkdf2hmac


def derive_password_and_master_key(password: str, salt: str) -> DerivedPasswordAndMasterKey:
    """Derive hashed password and master key from the raw password and salt"""

    kdf = master_key_pbkdf2hmac(salt=salt.encode())
    key = kdf.derive(password.encode()).hex()

    split_index = len(key) // 2

    return DerivedPasswordAndMasterKey(
        password=sha512(key[split_index:].encode()).hexdigest(),
        master_key=key[:split_index],
    )
