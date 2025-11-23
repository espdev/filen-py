from typing import Final
from enum import IntEnum, ReprEnum

from pydantic import EmailStr, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

FILEN_API_URL: Final = 'https://gateway.filen.io/v3'
DEFAULT_REQUEST_TIMEOUT: Final = 15.0  # sec


class AuthVersion(IntEnum):
    v1 = 1
    v2 = 2
    v3 = 3


class FileEncryptionVersion(float, ReprEnum):
    v1 = 1
    v1_5 = 1.5
    v2 = 2
    v3 = 3


class FilenConfig(BaseSettings):
    """Filen configuration"""

    api_url: HttpUrl = HttpUrl(FILEN_API_URL)

    email: EmailStr | None = None
    password: SecretStr | None = None
    master_key: SecretStr | None = None
    api_key: SecretStr | None = None

    request_timeout: float | tuple[float, float, float, float] = DEFAULT_REQUEST_TIMEOUT

    model_config = SettingsConfigDict(
        frozen=True,
        env_prefix='FILEN_',
        env_ignore_empty=True,
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )
