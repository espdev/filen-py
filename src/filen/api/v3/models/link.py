from typing import Annotated
from enum import StrEnum
from uuid import UUID

from pydantic import AliasChoices, Field

from .base import ValidationAliasedModel


class PublicLinkExpiration(StrEnum):
    exp_30d = '30d'
    exp_14d = '14d'
    exp_7d = '7d'
    exp_3d = '3d'
    exp_1d = '1d'
    exp_6h = '6h'
    exp_1h = '1h'
    never = 'never'


class PublicLinkStatus(ValidationAliasedModel):
    exists: Annotated[bool, Field(validation_alias=AliasChoices('exists', 'enabled'))]
    uuid: UUID | None = None
    key: str | None = None
    expiration: int | None = None
    expiration_text: PublicLinkExpiration | None = None
    download_btn: bool | None = None
    password: str | None = None
