from secrets import token_bytes

from cryptography.hazmat.primitives import serialization
from pydantic import BaseModel
import pytest

from filen.config import AuthVersion
from filen.crypto import (
    MetadataEncryptionVersion,
    create_der_keypair,
    current_metadata_cipher,
    decrypt_content,
    decrypt_master_keys,
    decrypt_metadata,
    decrypt_metadata_model,
    derive_hmac_sha256_key,
    derive_master_key_and_hashed_password,
    encrypt_content,
    encrypt_master_keys,
    encrypt_metadata,
    encrypt_metadata_model,
    generate_private_key,
    hash_name,
    keypair_der_to_pem,
    metadata_ciphers,
)
from filen.errors import (
    ContentDecryptError,
    ContentEncryptError,
    MetadataDecryptErrorGroup,
    MetadataEncryptionVersionError,
)


def test_derive_password_and_master_key():
    password = 'Hello@W0rld123!'
    salt = '4bOVDgDoVqV9PMkuOXWi6FB91K2MvTV84weHsUNHpVmbWXzq8mclnCqjX9qEyA5guIu590W63HlcYAAPTQlbZLplZC_UBjNKnv-O'

    res = derive_master_key_and_hashed_password(password, salt)

    assert res.hashed_password == (
        '6391048cdfc0df0f933093f25ddb333cc7ea9363201f4e617b521227db88887f9e49904'
        '0472fd5aefdf6f8fbbf03e75eacf8e2dedd680089b858fcf0a00b635f'
    )
    assert res.master_key == 'c438c484766b8ff500b0b918fd44f1f643929f7656a648f6b3dd76aea56c121b'


def test_encrypt_decrypt_master_keys():
    keys = [
        'c438c484766b8ff500b0b918fd44f1f643929f7656a648f6b3dd76aea56c121b',
        'd899ab9d9032c49ff39428964607db67225e338612059776447715d37586eba3',
        '1828d1cba88e28377a3d9c8f64e3aad36a0287fb5f9ad3485f9922b071827aa0',
    ]

    assert decrypt_master_keys(encrypt_master_keys(keys), keys[-1]) == keys


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


def test_encrypt_decrypt_metadata_model():
    key = 'd899ab9d9032c49ff39428964607db67225e338612059776447715d37586eba3'

    class Model(BaseModel):
        foo: int
        bar: str

    model = Model(foo=1, bar='hello')
    assert decrypt_metadata_model(Model, encrypt_metadata_model(model, key), key) == model


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

    with pytest.raises(MetadataDecryptErrorGroup) as exc_info:
        _ = decrypt_metadata(metadata_e, key2)

    assert len(exc_info.value.exceptions) == 1

    with pytest.raises(MetadataDecryptErrorGroup) as exc_info:
        _ = decrypt_metadata(metadata_e, [key2, key3])

    assert len(exc_info.value.exceptions) == 2


def test_decrypt_metadata_encryption_version_error():
    metadata_e = '00028964607db67225e338612059776447715d37586eb484766b8ff500b0b918fd44f1f643970767e533b2695e134b75'

    key1 = 'c438c484766b8ff500b0b918fd44f1f643929f7656a648f6b3dd76aea56c121b'
    key2 = 'd899ab9d9032c49ff39428964607db67225e338612059776447715d37586eba3'

    with pytest.raises(MetadataEncryptionVersionError):
        _ = decrypt_metadata(metadata_e, key1)

    with pytest.raises(MetadataEncryptionVersionError):
        _ = decrypt_metadata(metadata_e, [key1, key2])


def test_encrypt_decrypt_content():
    data = token_bytes(1024)
    key = '485cfd4b2c99fb2cb7bd2c288158811b'

    assert decrypt_content(encrypt_content(data, key), key) == data


def test_encrypt_content_error():
    data = token_bytes(1024)
    key = 'd899ab9d9032c49ff39428964607db67225e338612059776447715d37586eba3'

    with pytest.raises(ContentEncryptError):
        _ = encrypt_content(data, key)


def test_decrypt_content_error():
    data = token_bytes(1024)
    key = 'd899ab9d9032c49ff39428964607db67225e338612059776447715d37586eba3'

    with pytest.raises(ContentDecryptError):
        _ = decrypt_content(data, key)

    data = token_bytes(10)
    key = '485cfd4b2c99fb2cb7bd2c288158811b'

    with pytest.raises(ContentDecryptError):
        _ = decrypt_content(data, key)


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


@pytest.mark.parametrize(
    'name, name_hashed',
    [
        ('Backup', 'bee4407adc7501da1a6facafe587fe30aada4bff'),
        ('Docs', '455f3194ec552fbc452397fc4d6676427fe1bb96'),
        ('Temp', 'c6392de62a260845105a4d76095bfa656a37203b'),
    ],
)
def test_hash_name_auth_v1_v2(name, name_hashed):
    assert hash_name(name, AuthVersion.v2) == name_hashed


@pytest.mark.parametrize(
    'name, name_hashed',
    [
        ('Backup', '9a4673b0aa883dfc1ba5d1271a0c6c08386840f1eddd694d01074b583f882a13'),
        ('Docs', 'ea420534ff14e752bb46ab065e238b5fcf2a33e9910636b9419e6ec3898e814c'),
        ('Temp', '346671e0baa4f063eb6496680383f3a6e4c0f3ef83cff2383e9ed384746fae2c'),
    ],
)
def test_hash_name_auth_v3(name, name_hashed):
    private_key = (
        'MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCXPshFForAMLkuX4BrjqnZK3bcAQJwdv/xzXFETGuxR/eE2aC7j5zSQjiFuA'
        '9OADZVPePjTphwSMfngIHwuA/lGKPpJf6lnjBnLZ+6mmrRJdDYNDhRz/r8xw71OB+e4e9MJBag2ke5WJWf/c4ypsaBiHsp96aImqjZQA8O8bpE'
        'nXy62QpWgxm87TatXnPVz6kqjBjvg9lmBUZT2ZScb42SqkhRzEOuN7jYnqgAqnmKcDdbMapzYKwVfhIX+qSRUZnJqG2cmUwZk2JJpz6Y2AjFth'
        'bso/AbadHobOanp0F3s4dpP4PABIwzFN7Ok7dkrJzsu0hyEHX9X6s4fPeltE+JAgMBAAECggEAEKlgLyo/UVJcyCTJtS+jevLslmp/DgwyAH2Z'
        'LYS8tWw/8pD2Acudo1UbvHFtMDLaSXQ2u3cQWIhQC2sPBYmFaL/Y6MmgfrbJTsiKKOizfURs+DByhuLCW+ADABU1eI+byNfN7Vz2m07MtvIjKd'
        'XRFvqF1Pb9D9333W0O657KHh5O4pp8xyLsNaURk/RId0FymY/47PeiHxDSZ0JpXzhk+XFXZgtLNPYBwvjrn8odAq9RtkQRocNo3l5utUiZRni7'
        'iXAqgrM4TyNGKCyO+heWpR1U8UPeUcKNkBGlAlLjHiNWAekI12n0SFm9ESfwPKrEt4pqIR8TExRVJdaGQAVVAQKBgQDT+kD8F2HnFjCwCET8x2'
        'KB+bxoKuZK5KA1EHvIEvUtveNmS++U149dGb44NabRxlp5HuQgvV2CTAQQRdKj3YmSmMVrM9xRXunGjdIKYdGn2MDnMgEmnj1bFi3fDUQ61PSc'
        'ujw0z/FkS0Uz3chczfpjFIZq+YwC9lopVVVm3HitgQKBgQC2p7TuiJwg25O/+KcrCEuPvTSxoUm9LeI39EGz1ezu5LaK0TnrpjkQjFVUlIh2bI'
        '2mI31mwUuk5/OAkVqt7mcKXgbeUT0pKrUxV8wfDMPiyxQD8Ygy/9nTdeoRoUmBw4UNcRenCSatdQy4kbZ2v2bxeNrALlKR/qpfGwWX6V02CQKB'
        'gDmHPz+rMNzAPvJnLCHWErvnhORYUCufJIOCN7Wyv2tsj1xh22Fvpu7DX8ZteRqRVFhus8bW3ZvQ+YFZEbN7Giz43QsdBfvnYFaMgqZiqb19q8'
        'yS25EZfNlNiaFxPkUhKkmmmVRT4tUvQFa1J/1XwU5GcbxygTcEmK+DAyxpRS8BAoGAOhoI3OPJvk36ptNC4dZmqteF3ocuvKXO0vu4tqrzDl7k'
        'ji3V3dbnShNJxXjmG72WJWYeqsQL+u3psFkMXk16q3qTdr6i1OiH8KU8Ahh+azMsL8DyET7/nFti1K7YghWeylLSMkkf64dTP5biUs25wlAuTX'
        'muvFAlA9HFqrgJ9XkCgYEAxnVrZToQJ/xTc5J2+ClKK8sc6mYDH7RisdVqt8YGlKAzau7ZYlvTuNzOlfQltEId42CI02po898nvSP383MAdHir'
        'p5XckLLdXLSKbhLE0rD6EvX8PpgdPeoeULM4qcNspg6q5JV0fla2DkWZ7LHO3iHukk/r6UsQgWLZU1b5e0E='
    )
    hmac_key = derive_hmac_sha256_key(private_key)

    assert len(hmac_key) == 32
    assert hash_name(name, AuthVersion.v3, hmac_key) == name_hashed
