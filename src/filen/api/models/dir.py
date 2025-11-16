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


class ContentType(StrEnum):
    upload = auto()
    folder = auto()


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
    parent: UUID
    metadata: str | UploadMetadata
    favorited: bool
    rm: str
    region: str
    bucket: str
    size: int
    chunks: int
    timestamp: int
    version: FileEncryptionVersion


class Folder(BaseModel):
    uuid: UUID
    name: str
    parent: UUID
    timestamp: int
    is_sync: bool
    is_default: bool
    color: str | None


class FolderContent(ValidationAliasedModel):
    uploads: list[Upload]
    folders: list[Folder]


class FolderContentResponseData(ResponseData[FolderContent]): ...
