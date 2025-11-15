from typing import Self
from dataclasses import dataclass
from uuid import UUID

from filen.api.models.auth import AuthVersion
from filen.config import FilenConfig
from filen.errors import NoMasterKeysError


@dataclass
class Context:
    """Filen client context"""

    api_url: str
    api_key: str | None

    master_keys: list[str]
    public_key: str | None
    private_key: str | None

    user_id: int | None
    base_folder_uuid: UUID | None

    auth_version: AuthVersion

    @classmethod
    def create_from_config(cls, config: FilenConfig) -> Self:
        return cls(
            api_url=str(config.api_url),
            api_key=config.api_key.get_secret_value() if config.api_key else None,
            master_keys=[k.get_secret_value() for k in config.master_keys],
            public_key=None,
            private_key=None,
            user_id=None,
            base_folder_uuid=None,
            auth_version=AuthVersion.v2,
        )

    @property
    def latest_master_key(self) -> str:
        if not self.master_keys:
            raise NoMasterKeysError('There are no master keys in the config.')
        return self.master_keys[-1]

    def is_valid_for_auth(self) -> bool:
        """Return True if the config is valid for authorized access to API"""

        # fmt: off
        return (
            self.auth_version is not None
            and self.api_key is not None
        )
        # fmt: on

    def is_valid_master_keys(self) -> bool:
        """Return True if the config contains valid encryption master keys"""

        return len(self.master_keys) > 0
