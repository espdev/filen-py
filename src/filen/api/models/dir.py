from typing import Annotated, Final
from enum import Enum, StrEnum, auto
from uuid import UUID

from pydantic import AliasChoices, Field, field_validator

from .base import RequestData, ResponseData, ValidationAliasedModel

BASE_FOLDER_NAME: Final = 'base'


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


class FileMetadata(ValidationAliasedModel):
    """Decrypted file metadata"""

    name: str
    size: int
    mime: str
    key: str
    last_modified: int


class FolderMetadata(ValidationAliasedModel):
    """Decrypted folder metadata (name)"""

    name: str


class FolderUUIDRequestData(RequestData):
    uuid: UUID


class FolderContentRequestData(RequestData):
    uuid: UUID | FolderContentType


class ItemInfo(ValidationAliasedModel):
    uuid: UUID
    parent: UUID | None
    favorited: bool
    timestamp: int

    @field_validator('parent', mode='before')
    @classmethod
    def _validate_parent(cls, v) -> UUID | None:
        if v == BASE_FOLDER_NAME:
            return None
        return v


class FileInfo(ItemInfo):
    bucket: str
    region: str
    metadata: str | FileMetadata
    name_hashed: str
    version: FileEncryptionVersion
    chunks: int
    chunks_size: int
    trash: bool = False


class FolderInfo(ItemInfo):
    metadata: Annotated[str | FolderMetadata, Field(validation_alias=AliasChoices('nameEncrypted', 'name'))]
    name_hashed: str
    color: str | None
    trash: bool = False


class FolderInfoResponseData(ResponseData[FolderInfo]): ...


class File(ItemInfo):
    uuid: UUID
    parent: UUID | None
    metadata: str | FileMetadata
    favorited: bool
    version: FileEncryptionVersion
    rm: str
    region: str
    bucket: str
    size: int
    chunks: int
    timestamp: int
    trash_timestamp: int | None = None


class Folder(ItemInfo):
    metadata: Annotated[str | FolderMetadata, Field(validation_alias='name')]
    color: str | None
    is_sync: bool | None = None
    is_default: bool | None = None
    trash_parent: int | None = None
    trash_timestamp: int | None = None


class FolderContent(ValidationAliasedModel):
    files: Annotated[list[File], Field(validation_alias='uploads')]
    folders: list[Folder]


class FolderContentResponseData(ResponseData[FolderContent]): ...


class FolderDownload(ValidationAliasedModel):
    files: list[FileInfo]
    folders: list[FolderInfo]


class FolderDownloadResponseData(ResponseData[FolderDownload]): ...
