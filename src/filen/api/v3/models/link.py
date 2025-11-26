from typing import Annotated, Literal
from uuid import UUID

from pydantic import AliasChoices, Field

from .base import ValidationAliasedModel

type PublicLinkExpiration = Literal['30d', '14d', '7d', '3d', '1d', '6h', '1h', 'never']


class PublicLinkStatus(ValidationAliasedModel):
    exists: Annotated[bool, Field(validation_alias=AliasChoices('exists', 'enabled'))]
    uuid: UUID | None = None
    key: str | None = None
    expiration: int | None = None
    expiration_text: PublicLinkExpiration | None = None
    download_btn: bool | None = None
    password: str | None = None
