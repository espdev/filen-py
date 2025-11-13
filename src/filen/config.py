from typing import Annotated, Final
from enum import IntEnum

from pydantic import HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

FILEN_API_URL: Final = 'https://gateway.filen.io/v3'


class AuthVersion(IntEnum):
    v1 = 1
    v2 = 2
    v3 = 3


class FilenConfig(BaseSettings):
    """Filen configuration"""

    api_url: HttpUrl = HttpUrl(FILEN_API_URL)

    auth_version: AuthVersion | None = None
    api_key: SecretStr | None = None
    master_keys: Annotated[list[SecretStr], NoDecode] = []
    public_key: str | None = None
    private_key: SecretStr | None = None

    model_config = SettingsConfigDict(
        validate_assignment=True,
        env_prefix='FILEN_',
        env_ignore_empty=True,
        env_file='.env',
        env_file_encoding='utf-8',
    )

    @field_validator('master_keys', mode='before')
    @classmethod
    def parse_master_keys(cls, v):
        if v and isinstance(v, str):
            return v.split('|')
        return v

    def is_valid_for_auth(self) -> bool:
        """Return True if the config is valid for authorized access to API"""

        return self.auth_version is not None and self.api_key is not None

    def is_valid_keys(self) -> bool:
        """Return True if the config contains valid encryption keys"""

        return len(self.master_keys) > 0 and self.public_key is not None and self.private_key is not None
