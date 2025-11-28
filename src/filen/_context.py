from typing import NoReturn, Self
from dataclasses import dataclass
from uuid import UUID

from filen.config import (
    AuthVersion,
    FilenConfig,
    get_random_filen_egest_url,
    get_random_filen_gateway_url,
    get_random_filen_ingest_url,
)
from filen.errors import InaccessibleKeysError


@dataclass
class Context:
    """Filen client context"""

    gateway_url: str | None
    egest_url: str | None
    ingest_url: str | None

    auth_version: AuthVersion

    email: str | None
    password: str | None

    api_key: str | None
    master_keys: list[str]
    public_key: str | None
    private_key: str | None
    base_folder_uuid: UUID | None

    @classmethod
    def create_from_config(cls, config: FilenConfig) -> Self:
        return cls(
            gateway_url=str(config.gateway_url) if config.gateway_url else None,
            egest_url=str(config.egest_url) if config.egest_url else None,
            ingest_url=str(config.ingest_url) if config.ingest_url else None,
            auth_version=AuthVersion.v2,
            email=str(config.email) if config.email else None,
            password=config.password.get_secret_value() if config.password else None,
            api_key=config.api_key.get_secret_value() if config.api_key else None,
            master_keys=[config.master_key.get_secret_value()] if config.master_key else [],
            public_key=None,
            private_key=None,
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

    @property
    def has_keypair(self) -> bool:
        """Return True if the context contains private and public keys for asymmetric encryption"""

        return self.public_key is not None and self.private_key is not None

    @property
    def is_valid(self) -> bool:
        """Return True if the context is valid for use with Filen service"""

        # fmt: off
        return (
            self.has_api_key
            and self.has_master_keys
            and self.has_keypair
            and self.base_folder_uuid is not None
        )
        # fmt: on

    @property
    def current_master_key(self) -> str:
        if not self.has_master_keys:
            raise InaccessibleKeysError('There are no master keys in the context.')
        return self.master_keys[-1]

    def get_gateway_url(self) -> str:
        return self.gateway_url or get_random_filen_gateway_url()

    def get_egest_url(self) -> str:
        return self.egest_url or get_random_filen_egest_url()

    def get_ingest_url(self) -> str:
        return self.ingest_url or get_random_filen_ingest_url()

    def raise_for_inaccessible_keys(self) -> None | NoReturn:
        """Raise InaccessibleKeysError if it is not possible to obtain the user's keys in any way"""

        if self.has_master_keys:
            return

        if not self.has_api_key:
            raise InaccessibleKeysError("There are no API key in the context to ensure user's keys.")

        if not self.has_credentials:
            raise InaccessibleKeysError("There are no credentials in the context to ensure user's keys.")
