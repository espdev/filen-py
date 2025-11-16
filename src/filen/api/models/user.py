from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from .base import RequestData, ResponseData, ValidationAliasedModel


class UserInfo(ValidationAliasedModel):
    id: int
    email: EmailStr
    max_storage: int
    storage_used: int
    is_premium: bool
    avatar_url: Annotated[str | None, Field(validation_alias='avatarURL')]
    base_folder_uuid: Annotated[UUID, Field(validation_alias='baseFolderUUID')]


class UserInfoResponseData(ResponseData[UserInfo]): ...


class UserSettings(ValidationAliasedModel):
    email: EmailStr
    two_factor_key: str | None
    two_factor_enabled: bool
    versioned_files: int
    versioned_storage: int
    unfinished_files: int
    unfinished_storage: int
    storage_used: int


class UserSettingsResponseData(ResponseData[UserSettings]): ...


class UserMasterKeysRequestData(RequestData):
    master_keys: str


class UserMasterKeys(ValidationAliasedModel):
    keys: str


class UserMasterKeysResponseData(ResponseData[UserMasterKeys]): ...


class UserKeyPairInfo(ValidationAliasedModel):
    public_key: str
    private_key: str


class UserKeyPairInfoResponseData(ResponseData[UserKeyPairInfo]): ...


class UserKeyPair(BaseModel):
    public_key: str
    private_key: str


class UserBaseFolder(ValidationAliasedModel):
    uuid: UUID


class UserBaseFolderResponseData(ResponseData[UserBaseFolder]): ...
