from typing import Final
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import partial

from cryptography.hazmat.backends import default_backend
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


@dataclass
class DerivedPasswordAndMasterKey:
    password: str
    master_key: str


class AbstractCipher(ABC):
    @abstractmethod
    def encrypt(self, content: str) -> str:
        pass

    @abstractmethod
    def decrypt(self, content: str) -> str:
        pass
