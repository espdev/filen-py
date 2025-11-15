from typing import Annotated, Final

from pydantic import HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

FILEN_API_URL: Final = 'https://gateway.filen.io/v3'


class FilenConfig(BaseSettings):
    """Filen configuration"""

    api_url: HttpUrl = HttpUrl(FILEN_API_URL)
    api_key: SecretStr | None = None
    master_keys: Annotated[list[SecretStr], NoDecode] = []

    model_config = SettingsConfigDict(
        validate_assignment=True,
        env_prefix='FILEN_',
        env_ignore_empty=True,
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    @field_validator('master_keys', mode='before')
    @classmethod
    def parse_master_keys(cls, v):
        if v and isinstance(v, str):
            return v.split('|')
        return v
