from filen.crypto import (
    MetadataEncryptionVersion,
    current_metadata_cipher,
    decrypt_metadata,
    derive_password_and_master_key,
    encrypt_metadata,
    metadata_ciphers,
)


def test_derive_password_and_master_key():
    password = 'Hello@W0rld123!'
    salt = '4bOVDgDoVqV9PMkuOXWi6FB91K2MvTV84weHsUNHpVmbWXzq8mclnCqjX9qEyA5guIu590W63HlcYAAPTQlbZLplZC_UBjNKnv-O'

    res = derive_password_and_master_key(password, salt)

    assert res.password == (
        '6391048cdfc0df0f933093f25ddb333cc7ea9363201f4e617b521227db88887f9e49904'
        '0472fd5aefdf6f8fbbf03e75eacf8e2dedd680089b858fcf0a00b635f'
    )
    assert res.master_key == 'c438c484766b8ff500b0b918fd44f1f643929f7656a648f6b3dd76aea56c121b'


def test_encrypt_decrypt_metadata_current():
    metadata = (
        'Filen uses symmetric AES-256-GCM cryptography. '
        'We differentiate between two basic encryption concerns: '
        'Metadata encryption is our term for any small strings, like file metadata or directory names, '
        'that need to be encrypted. Data encryption means encryption of binary file content.'
    )

    key = 'c438c484766b8ff500b0b918fd44f1f643929f7656a648f6b3dd76aea56c121b'

    metadata_cipher = current_metadata_cipher(key)
    assert metadata_cipher.decrypt(metadata_cipher.encrypt(metadata)) == metadata


def test_encrypt_decrypt_metadata_v2():
    metadata = (
        'Filen uses symmetric AES-256-GCM cryptography. '
        'We differentiate between two basic encryption concerns: '
        'Metadata encryption is our term for any small strings, like file metadata or directory names, '
        'that need to be encrypted. Data encryption means encryption of binary file content.'
    )

    key = 'c438c484766b8ff500b0b918fd44f1f643929f7656a648f6b3dd76aea56c121b'

    cipher = metadata_ciphers[MetadataEncryptionVersion.v2](key)
    assert cipher.decrypt(cipher.encrypt(metadata)) == metadata


def test_encrypt_decrypt_metadata():
    metadata = (
        'Filen uses symmetric AES-256-GCM cryptography. '
        'We differentiate between two basic encryption concerns: '
        'Metadata encryption is our term for any small strings, like file metadata or directory names, '
        'that need to be encrypted. Data encryption means encryption of binary file content.'
    )

    key = 'c438c484766b8ff500b0b918fd44f1f643929f7656a648f6b3dd76aea56c121b'

    assert decrypt_metadata(encrypt_metadata(metadata, key), key) == metadata
