from typing import Final
from functools import partial

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import GCM
from cryptography.hazmat.primitives.hashes import SHA512
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

backend = default_backend()

MASTER_KEY_LENGTH: Final = 64
DERIVE_MASTER_KEY_ITERATIONS: Final = 200_000

master_key_pbkdf2hmac = partial(
    PBKDF2HMAC,
    algorithm=SHA512(),
    length=MASTER_KEY_LENGTH,
    iterations=DERIVE_MASTER_KEY_ITERATIONS,
    backend=backend,
)


def create_aes_256_gcm_cipher(key: bytes, iv: bytes) -> Cipher:
    return Cipher(
        algorithm=AES(key),
        mode=GCM(iv),
        backend=backend,
    )
