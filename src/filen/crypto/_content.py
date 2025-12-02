from typing import Final

from filen.config import FILE_ENCRYPTION_VERSION, FileEncryptionVersion
from filen.errors import ContentDecryptError, ContentEncryptError

from ._base import create_aes_256_gcm_cipher
from ._utils import generate_random_bytes, generate_random_string

IV_LENGTH: Final = 12
AUTH_TAG_LENGTH: Final = 16

V1_V2_KEY_STR_LENGTH: Final = 32
V3_KEY_STR_LENGTH: Final = 64


def _get_key_in_bytes(key: str, version: FileEncryptionVersion) -> bytes:
    match version:
        case FileEncryptionVersion.v1 | FileEncryptionVersion.v1_5 | FileEncryptionVersion.v2:
            if len(key) != V1_V2_KEY_STR_LENGTH:
                raise ValueError(
                    f'Key must be {V1_V2_KEY_STR_LENGTH} chars in ascii for encryption version "{version}".'
                )
            return key.encode()

        case FileEncryptionVersion.v3:
            if len(key) != V3_KEY_STR_LENGTH:
                raise ValueError(f'Key must be {V3_KEY_STR_LENGTH} chars in hex for encryption version "{version}".')
            return bytes.fromhex(key)

        case _:
            raise ValueError(f'Invalid encryption version "{version}".')


def _generate_iv(version: FileEncryptionVersion) -> bytes | None:
    match version:
        case FileEncryptionVersion.v2:
            return generate_random_string(IV_LENGTH).encode()
        case FileEncryptionVersion.v3:
            return generate_random_bytes(IV_LENGTH)
    return None


def _encrypt_content_v2_v3(data: bytes, key: bytes, version: FileEncryptionVersion) -> bytes:
    try:
        iv = _generate_iv(version)
        cipher = create_aes_256_gcm_cipher(key=key, iv=iv)

        encryptor = cipher.encryptor()
        data_enc = encryptor.update(data) + encryptor.finalize()
        auth_tag = encryptor.tag
    except Exception as err:
        raise ContentEncryptError(f'Content encryption failed due to: "{err}"') from err

    return b''.join([iv, data_enc, auth_tag])


def encrypt_content(data: bytes, key: str, version: FileEncryptionVersion = FILE_ENCRYPTION_VERSION) -> bytes:
    """Encrypt data content"""

    try:
        key_b = _get_key_in_bytes(key, version)
    except Exception as e:
        raise ContentEncryptError(f'Unable to get encryption key: {e}') from e

    match version:
        case FileEncryptionVersion.v1 | FileEncryptionVersion.v1_5:
            raise ContentEncryptError(f'Unsupported deprecated encryption version "{version}".')
        case FileEncryptionVersion.v2 | FileEncryptionVersion.v3:
            return _encrypt_content_v2_v3(data, key_b, version)
        case _:
            raise ContentEncryptError(f'Unsupported encryption version "{version}".')


def _decrypt_content_v1_v1_5(data: bytes, key: bytes) -> bytes:
    raise ContentDecryptError('Decrypt v1/v1.5 is not implemented until better times.')


def _decrypt_content_v2_v3(data: bytes, key: bytes) -> bytes:
    try:
        iv = data[:IV_LENGTH]
        data_enc = data[IV_LENGTH:-AUTH_TAG_LENGTH]
        auth_tag = data[-AUTH_TAG_LENGTH:]

        cipher = create_aes_256_gcm_cipher(key=key, iv=iv)
        decryptor = cipher.decryptor()
        data_dec = decryptor.update(data_enc) + decryptor.finalize_with_tag(auth_tag)
    except Exception as err:
        raise ContentDecryptError(f'Content decryption failed due to: "{err}"') from err

    return data_dec


def decrypt_content(data: bytes, key: str, version: FileEncryptionVersion) -> bytes:
    """Decrypt data content"""

    try:
        key_b = _get_key_in_bytes(key, version)
    except Exception as e:
        raise ContentDecryptError(f'Unable to get encryption key: {e}') from e

    match version:
        case FileEncryptionVersion.v1 | FileEncryptionVersion.v1_5:
            return _decrypt_content_v1_v1_5(data, key_b)
        case FileEncryptionVersion.v2 | FileEncryptionVersion.v3:
            return _decrypt_content_v2_v3(data, key_b)
        case _:
            raise ContentDecryptError(f'Unsupported encryption version "{version}".')
