from typing import Annotated
from enum import Enum, StrEnum, auto
from uuid import UUID

from pydantic import BaseModel, Field

from .base import RequestData, ResponseData, ValidationAliasedModel


class FileEncryptionVersion(float, Enum):
    v1 = 1
    v1_5 = 1.5
    v2 = 2
    v3 = 3


class FolderItem(StrEnum):
    file = auto()
    folder = auto()


class FolderContentType(StrEnum):
    favorites = auto()
    recents = auto()
    links = auto()
    trash = auto()


class FolderMetadata(ValidationAliasedModel):
    """Decrypted folder metadata (name)"""

    name: str


class UploadMetadata(ValidationAliasedModel):
    """Decrypted upload metadata"""

    name: str
    size: int
    mime: str
    key: str
    last_modified: int


class FolderUUIDRequestData(RequestData):
    uuid: UUID


class FolderContentRequestData(RequestData):
    uuid: UUID | FolderContentType


class FolderInfo(ValidationAliasedModel):
    uuid: UUID
    name: Annotated[str, Field(validation_alias='nameEncrypted')]
    name_hashed: str
    parent: UUID | None
    trash: bool
    favorited: bool
    color: str | None


class FolderInfoResponseData(ResponseData[FolderInfo]): ...


class Upload(BaseModel):
    uuid: UUID
    parent: UUID | None
    metadata: str | UploadMetadata
    favorited: bool
    version: FileEncryptionVersion
    rm: str
    region: str
    bucket: str
    size: int
    chunks: int
    timestamp: int
    trash_timestamp: int | None = None


class Folder(BaseModel):
    uuid: UUID
    name: str
    parent: UUID | None
    color: str | None
    timestamp: int
    favorited: bool
    is_sync: bool | None = None
    is_default: bool | None = None
    trash_parent: int | None = None
    trash_timestamp: int | None = None


class FolderContent(ValidationAliasedModel):
    uploads: list[Upload]
    folders: list[Folder]


class FolderContentResponseData(ResponseData[FolderContent]): ...
