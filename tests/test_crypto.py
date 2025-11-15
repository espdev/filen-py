from cryptography.hazmat.primitives import serialization
import pytest

from filen.crypto import (
    MetadataEncryptionVersion,
    create_der_keypair,
    current_metadata_cipher,
    decrypt_master_keys,
    decrypt_metadata,
    derive_password_and_master_key,
    encrypt_master_keys,
    encrypt_metadata,
    generate_private_key,
    keypair_der_to_pem,
    metadata_ciphers,
)
from filen.errors import MetadataDecryptError, MetadataEncryptionVersionError


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

    key1 = 'c438c484766b8ff500b0b918fd44f1f643929f7656a648f6b3dd76aea56c121b'
    key2 = '1828d1cba88e28377a3d9c8f64e3aad36a0287fb5f9ad3485f9922b071827aa0'
    key3 = 'd899ab9d9032c49ff39428964607db67225e338612059776447715d37586eba3'

    assert decrypt_metadata(encrypt_metadata(metadata, key1), key1) == metadata
    assert decrypt_metadata(encrypt_metadata(metadata, key1), [key1, key2, key3]) == metadata
    assert decrypt_metadata(encrypt_metadata(metadata, key2), [key1, key2, key3]) == metadata
    assert decrypt_metadata(encrypt_metadata(metadata, key3), [key1, key2, key3]) == metadata


def test_decrypt_metadata_error():
    metadata = (
        'Filen uses symmetric AES-256-GCM cryptography. '
        'We differentiate between two basic encryption concerns: '
        'Metadata encryption is our term for any small strings, like file metadata or directory names, '
        'that need to be encrypted. Data encryption means encryption of binary file content.'
    )

    key1 = 'ef8bcd0f76c70767e533b2695e134b75fcf00baa2000aacf57242186bde125ef'
    key2 = '7ef190b14d40eee8ac991d2bab40c613877ee1f22f225c371e22fc5321422550'
    key3 = '1828d1cba88e28377a3d9c8f64e3aad36a0287fb5f9ad3485f9922b071827aa0'

    metadata_e = encrypt_metadata(metadata, key1)

    with pytest.raises(MetadataDecryptError):
        _ = decrypt_metadata(metadata_e, key2)

    with pytest.raises(MetadataDecryptError):
        _ = decrypt_metadata(metadata_e, [key2, key3])


def test_decrypt_metadata_encryption_version_error():
    metadata_e = '00028964607db67225e338612059776447715d37586eb484766b8ff500b0b918fd44f1f643970767e533b2695e134b75'

    key1 = 'c438c484766b8ff500b0b918fd44f1f643929f7656a648f6b3dd76aea56c121b'
    key2 = 'd899ab9d9032c49ff39428964607db67225e338612059776447715d37586eba3'

    with pytest.raises(MetadataEncryptionVersionError):
        _ = decrypt_metadata(metadata_e, key1)

    with pytest.raises(MetadataEncryptionVersionError):
        _ = decrypt_metadata(metadata_e, [key1, key2])


def test_encrypt_decrypt_master_keys():
    keys = [
        'c438c484766b8ff500b0b918fd44f1f643929f7656a648f6b3dd76aea56c121b',
        'd899ab9d9032c49ff39428964607db67225e338612059776447715d37586eba3',
        '1828d1cba88e28377a3d9c8f64e3aad36a0287fb5f9ad3485f9922b071827aa0',
    ]

    assert decrypt_master_keys(encrypt_master_keys(keys), keys[-1]) == keys


def test_keypair_der_to_pem():
    private_key = generate_private_key()

    keypair_der = create_der_keypair(private_key)
    keypair_pem = keypair_der_to_pem(*keypair_der)

    private_key_from_pem = serialization.load_pem_private_key(
        data=keypair_pem.private_key.encode(),
        password=None,
    )
    public_key_from_pem = serialization.load_pem_public_key(
        data=keypair_pem.public_key.encode(),
    )

    assert private_key.private_numbers() == private_key_from_pem.private_numbers()
    assert private_key.public_key().public_numbers() == public_key_from_pem.public_numbers()
