from typing import Annotated
from uuid import UUID

from pydantic import EmailStr, Field

from .base import ResponseData, ValidationAliasedModel


class UserInfoData(ValidationAliasedModel):
    id: int
    email: EmailStr
    max_storage: int
    storage_used: int
    is_premium: bool
    avatar_url: Annotated[str | None, Field(validation_alias='avatarURL')]
    base_folder_uuid: Annotated[UUID, Field(validation_alias='baseFolderUUID')]


class UserInfoResponseData(ResponseData[UserInfoData]): ...
