from typing import Final
from enum import IntEnum, ReprEnum
from functools import cached_property

from pydantic import EmailStr, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

FILEN_API_URL: Final = 'https://gateway.filen.io/v3'
FILEN_APP_URL: Final = 'https://app.filen.io'

FILEN_PUBLIC_FILE_LINK_BASE_URL: Final = f'{FILEN_APP_URL}/#/d'
FILEN_PUBLIC_FOLDER_LINK_BASE_URL: Final = f'{FILEN_APP_URL}/#/f'

DEFAULT_REQUEST_TIMEOUT: Final = 15.0  # sec
DEFAULT_MAX_CONNECTIONS: Final = 50
DEFAULT_MAX_KEEPALIVE_CONNECTIONS: Final = 20

STORAGE_ROOT_NAME: Final = 'default'


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

    api_url: HttpUrl = HttpUrl(FILEN_API_URL)

    email: EmailStr | None = None
    password: SecretStr | None = None
    master_key: SecretStr | None = None
    api_key: SecretStr | None = None

    request_timeout: float | tuple[float, float, float, float] = DEFAULT_REQUEST_TIMEOUT
    max_connections: int = DEFAULT_MAX_CONNECTIONS

    model_config = SettingsConfigDict(
        frozen=True,
        env_prefix='FILEN_',
        env_ignore_empty=True,
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )
