from typing import Final, NoReturn, Type
from abc import ABC, abstractmethod
from base64 import b64decode, b64encode
from enum import StrEnum
from secrets import token_bytes, token_hex

from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.hashes import SHA512
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from filen.errors import FilenError, MetadataDecryptError, MetadataEncryptError, MetadataEncryptionVersionError

from ._base import MASTER_KEY_LENGTH, backend, create_aes_256_gcm_cipher


class MetadataEncryptionVersion(StrEnum):
    """All metadata encryption versions"""

    v1 = 'U2FsdGVk'
    v2 = '002'
    v3 = '003'


class MetadataCipherBase(ABC):
    """Base metadata cipher class"""

    ENCRYPTION_VERSION: MetadataEncryptionVersion
    VERSION_LENGTH: int

    def __init__(self, key: str) -> None:
        self._key = key

    @classmethod
    @abstractmethod
    def verify_encryption_version(cls, metadata: str, raise_error: bool = False) -> bool | NoReturn:
        pass

    @abstractmethod
    def encrypt(self, metadata: str) -> str:
        pass

    @abstractmethod
    def decrypt(self, metadata: str) -> str:
        pass


class MetadataCipherNewBase(MetadataCipherBase):
    VERSION_LENGTH: Final = 3

    @classmethod
    def verify_encryption_version(cls, metadata: str, raise_error: bool = False) -> bool | NoReturn:
        enc_ver = metadata[: cls.VERSION_LENGTH]
        is_ok = enc_ver == cls.ENCRYPTION_VERSION

        if not is_ok and raise_error:
            raise MetadataEncryptionVersionError(f'Unsupported metadata encryption version {enc_ver}.')
        return is_ok


class MetadataCipher002(MetadataCipherNewBase):
    """Metadata cipher for encryption version 002"""

    ENCRYPTION_VERSION: Final = MetadataEncryptionVersion.v2

    KEY_LENGTH: Final = 32
    IV_LENGTH: Final = 12
    AUTH_TAG_LENGTH: Final = 16

    B64_CHARSET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'

    def encrypt(self, content: str) -> str:
        iv = self._generate_iv()
        cipher = self._create_cipher(iv)

        encryptor = cipher.encryptor()
        encrypted = encryptor.update(content.encode()) + encryptor.finalize()
        auth_tag = encryptor.tag

        data_b64 = b64encode(encrypted + auth_tag).decode()

        return f'{self.ENCRYPTION_VERSION}{iv}{data_b64}'

    def decrypt(self, content: str) -> str:
        self.verify_encryption_version(content, raise_error=True)

        iv = content[self.VERSION_LENGTH : self.VERSION_LENGTH + self.IV_LENGTH]
        data_b64 = content[self.VERSION_LENGTH + self.IV_LENGTH :]

        data = b64decode(data_b64)
        encrypted = data[: -self.AUTH_TAG_LENGTH]
        auth_tag = data[-self.AUTH_TAG_LENGTH :]

        cipher = self._create_cipher(iv)

        decryptor = cipher.decryptor()
        content_decrypted = decryptor.update(encrypted) + decryptor.finalize_with_tag(auth_tag)

        return content_decrypted.decode()

    def _create_cipher(self, iv: str) -> Cipher:
        key_e = self._key.encode()

        key = PBKDF2HMAC(
            algorithm=SHA512(),
            length=self.KEY_LENGTH,
            salt=key_e,
            iterations=1,
            backend=backend,
        ).derive(key_e)

        return create_aes_256_gcm_cipher(
            key=key,
            iv=iv.encode(),
        )

    def _generate_iv(self) -> str:
        """
        This guarantees that the length of the string will be equal to the size in bytes,
        but there is a loss of entropy.
        """
        charset_len = len(self.B64_CHARSET)
        return ''.join(self.B64_CHARSET[b % charset_len] for b in token_bytes(self.IV_LENGTH))


class MetadataCipher003(MetadataCipherNewBase):
    """Metadata cipher for encryption version 003"""

    ENCRYPTION_VERSION: Final = MetadataEncryptionVersion.v3

    IV_LENGTH: Final = 12
    IV_HEX_LENGTH: Final = 24
    AUTH_TAG_LENGTH: Final = 16

    def encrypt(self, content: str) -> str:
        iv_hex = token_hex(self.IV_LENGTH)
        cipher = self._create_cipher(iv_hex)

        encryptor = cipher.encryptor()
        encrypted = encryptor.update(content.encode()) + encryptor.finalize()
        auth_tag = encryptor.tag

        data_b64 = b64encode(encrypted + auth_tag).decode()

        return f'{self.ENCRYPTION_VERSION}{iv_hex}{data_b64}'

    def decrypt(self, content: str) -> str:
        self.verify_encryption_version(content, raise_error=True)

        iv_hex = content[self.VERSION_LENGTH : self.VERSION_LENGTH + self.IV_HEX_LENGTH]
        data_b64 = content[self.VERSION_LENGTH + self.IV_HEX_LENGTH :]

        data = b64decode(data_b64)
        encrypted = data[: -self.AUTH_TAG_LENGTH]
        auth_tag = data[-self.AUTH_TAG_LENGTH :]

        cipher = self._create_cipher(iv_hex)

        decryptor = cipher.decryptor()
        content_decrypted = decryptor.update(encrypted) + decryptor.finalize_with_tag(auth_tag)

        return content_decrypted.decode()

    def _create_cipher(self, iv: str) -> Cipher:
        if len(self._key) != MASTER_KEY_LENGTH:
            raise FilenError(
                f'Invalid key length {len(self._key)} in hex for encrypting metadata. '
                f'Must be {MASTER_KEY_LENGTH} in hex.'
            )

        return create_aes_256_gcm_cipher(
            key=bytes.fromhex(self._key),
            iv=bytes.fromhex(iv),
        )


metadata_ciphers: dict[MetadataEncryptionVersion, Type[MetadataCipherBase] | None] = {
    MetadataCipher002.ENCRYPTION_VERSION: MetadataCipher002,
    MetadataCipher003.ENCRYPTION_VERSION: MetadataCipher003,
    MetadataEncryptionVersion.v1: None,
}

current_metadata_encryption_version = MetadataEncryptionVersion.v2
current_metadata_cipher = metadata_ciphers[current_metadata_encryption_version]


def encrypt_metadata(
    metadata: str,
    key: str,
    encryption_version: MetadataEncryptionVersion = current_metadata_encryption_version,
) -> str:
    """Encrypt metadata by the given encryption version (current version by default)"""

    metadata_cipher_cls = metadata_ciphers.get(encryption_version)

    try:
        if not metadata_cipher_cls:
            raise NotImplementedError(f'metadata cipher not implemented for encryption version {encryption_version}.')

        return metadata_cipher_cls(key).encrypt(metadata)
    except Exception as err:
        raise MetadataEncryptError(f'Metadata encryption failed due to: {err}') from err


def decrypt_metadata(metadata: str, keys: str | list[str]) -> str:
    """Decrypt metadata by existing metadata ciphers and a set of keys"""

    if isinstance(keys, str):
        keys = [keys]

    for metadata_chiper_cls in metadata_ciphers.values():
        if metadata_chiper_cls and metadata_chiper_cls.verify_encryption_version(metadata):
            last_err: Exception | None = None

            for key in reversed(keys):
                try:
                    return metadata_chiper_cls(key).decrypt(metadata)
                except Exception as err:
                    last_err = err

            raise MetadataDecryptError(f'Metadata decryption failed due to: {last_err}') from last_err

    raise MetadataEncryptionVersionError('Unsupported metadata encryption version.')
