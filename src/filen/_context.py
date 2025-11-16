from typing import Self
from dataclasses import dataclass
from uuid import UUID

from filen.api.models.auth import AuthVersion
from filen.config import FilenConfig


@dataclass
class Context:
    """Filen client context"""

    api_url: str
    auth_version: AuthVersion

    email: str | None
    password: str | None
    api_key: str | None
    master_keys: list[str]
    public_key: str | None
    private_key: str | None

    user_id: int | None
    base_folder_uuid: UUID | None

    @classmethod
    def create_from_config(cls, config: FilenConfig) -> Self:
        return cls(
            api_url=str(config.api_url),
            auth_version=AuthVersion.v2,
            api_key=config.api_key.get_secret_value() if config.api_key else None,
            master_keys=[config.master_key] if config.master_key else [],
            email=str(config.email) if config.email else None,
            password=config.password.get_secret_value() if config.password else None,
            public_key=None,
            private_key=None,
            user_id=None,
            base_folder_uuid=None,
        )

    @property
    def has_api_key(self) -> bool:
        """Return True if the context contains API key for access to API"""

        return self.api_key is not None

    @property
    def has_master_keys(self) -> bool:
        """Return True if the context contains encryption master keys"""

        return len(self.master_keys) > 0

    @property
    def has_credentials(self) -> bool:
        """Return True if the context contains email/password for login"""

        return self.email is not None and self.password is not None
