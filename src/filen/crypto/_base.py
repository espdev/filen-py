from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import GCM
from cryptography.hazmat.primitives.hashes import SHA512
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

backend = default_backend()


def create_pbkdf2hmac_sha512(length: int, salt: bytes, iterations: int) -> PBKDF2HMAC:
    return PBKDF2HMAC(
        algorithm=SHA512(),
        length=length,
        salt=salt,
        iterations=iterations,
        backend=backend,
    )


def create_aes_256_gcm_cipher(key: bytes, iv: bytes) -> Cipher:
    return Cipher(
        algorithm=AES(key),
        mode=GCM(iv),
        backend=backend,
    )
