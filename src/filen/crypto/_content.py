from typing import Final

from filen.errors import ContentDecryptError, ContentEncryptError

from ._base import create_aes_256_gcm_cipher
from ._utils import generate_random_bytes

IV_LENGTH: Final = 12
AUTH_TAG_LENGTH: Final = 16


def encrypt_content(data: bytes, key: str) -> bytes:
    """Encrypt data content"""

    iv = generate_random_bytes(IV_LENGTH)

    try:
        cipher = create_aes_256_gcm_cipher(
            key=key.encode(),
            iv=iv,
        )

        encryptor = cipher.encryptor()
        data_enc = encryptor.update(data) + encryptor.finalize()
        auth_tag = encryptor.tag
    except Exception as err:
        raise ContentEncryptError(f'Content encryption failed due to: "{err}"') from err

    return b''.join([iv, data_enc, auth_tag])


def decrypt_content(data: bytes, key: str) -> bytes:
    """Decrypt data content"""

    try:
        iv = data[:IV_LENGTH]
        data_enc = data[IV_LENGTH:-AUTH_TAG_LENGTH]
        auth_tag = data[-AUTH_TAG_LENGTH:]

        cipher = create_aes_256_gcm_cipher(
            key=key.encode(),
            iv=iv,
        )

        decryptor = cipher.decryptor()
        data_dec = decryptor.update(data_enc) + decryptor.finalize_with_tag(auth_tag)
    except Exception as err:
        raise ContentDecryptError(f'Content decryption failed due to: "{err}"') from err

    return data_dec
