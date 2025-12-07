from typing import Final
from enum import IntEnum, ReprEnum
from functools import cached_property
import random

from pydantic import EmailStr, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

FILEN_GATEWAY_URLS = [
    'https://gateway.filen.io',
    'https://gateway.filen.net',
    'https://gateway.filen-1.net',
    'https://gateway.filen-2.net',
    'https://gateway.filen-3.net',
    'https://gateway.filen-4.net',
    'https://gateway.filen-5.net',
    'https://gateway.filen-6.net',
]

FILEN_EGEST_URLS = [
    'https://egest.filen.io',
    'https://egest.filen.net',
    'https://egest.filen-1.net',
    'https://egest.filen-2.net',
    'https://egest.filen-3.net',
    'https://egest.filen-4.net',
    'https://egest.filen-5.net',
    'https://egest.filen-6.net',
]

FILEN_INGEST_URLS = [
    'https://ingest.filen.io',
    'https://ingest.filen.net',
    'https://ingest.filen-1.net',
    'https://ingest.filen-2.net',
    'https://ingest.filen-3.net',
    'https://ingest.filen-4.net',
    'https://ingest.filen-5.net',
    'https://ingest.filen-6.net',
]

FILEN_APP_URL: Final = 'https://app.filen.io'

FILEN_FILE_PUBLIC_LINK_BASE_URL: Final = f'{FILEN_APP_URL}/#/d'
FILEN_FOLDER_PUBLIC_LINK_BASE_URL: Final = f'{FILEN_APP_URL}/#/f'

FILEN_USER_AGENT: Final = 'filen-sdk'

DEFAULT_REQUEST_TIMEOUT: Final = 15.0  # sec
DEFAULT_MAX_CONNECTIONS: Final = 100
DEFAULT_MAX_KEEPALIVE_CONNECTIONS: Final = 20
DEFAULT_TASK_GROUP_CONCURRENCY: Final = 200

STORAGE_ROOT_NAME: Final = 'default'

FALLBACK_MIME_TYPE: Final = 'application/octet-stream'

DEFAULT_UPLOAD_REGION: Final = 'de-1'
DEFAULT_UPLOAD_BUCKET: Final = 'filen-1'

UPLOAD_CHUNK_SIZE: Final = 1024 * 1024  # 1 MB

DOWNLOAD_STREAM_CHUNK_SIZE: Final = 64 * 1024  # 64 KB
DOWNLOAD_CHUNKS_CONCURRENCY: Final = 32
DOWNLOAD_CHUNKS_BACKPRESSURE: Final = 100  # max number of chunks in memory for one file
MAX_CONCURRENT_DOWNLOADS: Final = 16

UPLOAD_CHUNKS_CONCURRENCY: Final = 16
MAX_CONCURRENT_UPLOADS: Final = 8

DEBUG_PRINT_INTERVAL: Final = 50


class AuthVersion(IntEnum):
    """Authentication versions"""

    v1 = 1
    v2 = 2
    v3 = 3


class MetadataEncryptionVersion(IntEnum):
    """All metadata encryption versions"""

    v1 = 1, 'U2FsdGVk'
    v2 = 2, '002'
    v3 = 3, '003'

    def __new__(cls, value: int, version_prefix: str):
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.version_prefix = version_prefix
        return obj

    @cached_property
    def length(self) -> int:
        return len(self.version_prefix)  # noqa


class FileEncryptionVersion(float, ReprEnum):
    """All file encryption versions"""

    v1 = 1
    v1_5 = 1.5
    v2 = 2
    v3 = 3


class PublicLinkVersion(IntEnum):
    """All versions of public links"""

    v1 = 1
    v2 = 2
    v3 = 3


METADATA_ENCRYPTION_VERSION: Final = MetadataEncryptionVersion.v2
FILE_ENCRYPTION_VERSION: Final = FileEncryptionVersion.v2
PUBLIC_LINK_VERSION: Final = PublicLinkVersion.v2


class FilenConfig(BaseSettings):
    """Filen configuration"""

    gateway_url: HttpUrl | None = None
    egest_url: HttpUrl | None = None
    ingest_url: HttpUrl | None = None

    email: EmailStr | None = None
    password: SecretStr | None = None
    master_key: SecretStr | None = None
    api_key: SecretStr | None = None

    request_timeout: float | tuple[float, float, float, float] = DEFAULT_REQUEST_TIMEOUT
    max_connections: int = DEFAULT_MAX_CONNECTIONS

    download_chunks_concurrency: int = DOWNLOAD_CHUNKS_CONCURRENCY
    max_concurrent_downloads: int = MAX_CONCURRENT_DOWNLOADS
    download_chunks_backpressure: int = DOWNLOAD_CHUNKS_BACKPRESSURE

    upload_chunks_concurrency: int = UPLOAD_CHUNKS_CONCURRENCY
    max_concurrent_uploads: int = MAX_CONCURRENT_UPLOADS

    model_config = SettingsConfigDict(
        frozen=True,
        env_prefix='FILEN_',
        env_ignore_empty=True,
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )


def get_randomly_chosen_filen_gateway_url() -> str:
    return random.choice(FILEN_GATEWAY_URLS)


def get_randomly_chosen_filen_egest_url() -> str:
    return random.choice(FILEN_EGEST_URLS)


def get_randomly_chosen_filen_ingest_url() -> str:
    return random.choice(FILEN_INGEST_URLS)
