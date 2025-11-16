from typing import Final

from pydantic import EmailStr, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

FILEN_API_URL: Final = 'https://gateway.filen.io/v3'


class FilenConfig(BaseSettings):
    """Filen configuration"""

    api_url: HttpUrl = HttpUrl(FILEN_API_URL)

    email: EmailStr | None = None
    password: SecretStr | None = None
    master_key: SecretStr | None = None
    api_key: SecretStr | None = None

    model_config = SettingsConfigDict(
        validate_assignment=True,
        env_prefix='FILEN_',
        env_ignore_empty=True,
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )
