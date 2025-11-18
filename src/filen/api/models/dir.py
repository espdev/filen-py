from typing import Annotated, Final
from enum import Enum, StrEnum, auto
from uuid import UUID

from pydantic import AliasChoices, Field, field_validator, model_validator

from .base import RequestData, ResponseData, ValidationAliasedModel

BASE_NAME: Final = 'base'


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


class FolderUUIDRequestData(RequestData):
    uuid: UUID


class FolderContentRequestData(RequestData):
    uuid: UUID | FolderContentType


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


class StorageItemInfo[TMetadata: FileMetadata | FolderMetadata](ValidationAliasedModel):
    uuid: UUID
    parent: UUID | None
    metadata: Annotated[str | TMetadata, Field(validation_alias=AliasChoices('metadata', 'name', 'nameEncrypted'))]
    name_hashed: str | None = None
    favorited: bool
    trash: bool = False
    timestamp: int
    trash_timestamp: Annotated[
        int | None,
        Field(validation_alias=AliasChoices('trashTimestamp', 'trash_timestamp')),
    ] = None

    @field_validator('parent', mode='before')
    @classmethod
    def _validate_parent(cls, v) -> UUID | None:
        if v == BASE_NAME:
            return None
        return v

    @model_validator(mode='after')
    def _validate_item(self):
        if self.trash_timestamp:
            self.trash = True
        return self


class FileInfo(StorageItemInfo[FileMetadata]):
    bucket: str
    region: str
    chunks: int
    chunks_size: int | None = None
    rm: str | None = None
    version: FileEncryptionVersion


class FolderInfo(StorageItemInfo[FolderMetadata]):
    color: str | None
    is_sync: Annotated[bool | None, Field(validation_alias=AliasChoices('isSync', 'is_sync'))] = None
    is_default: Annotated[bool | None, Field(validation_alias=AliasChoices('isDefault', 'is_default'))] = None
    trash_parent: Annotated[
        int | None,
        Field(validation_alias=AliasChoices('trashParent', 'trash_parent')),
    ] = None


class FolderInfoResponseData(ResponseData[FolderInfo]): ...


class FolderContent(ValidationAliasedModel):
    files: Annotated[list[FileInfo], Field(validation_alias='uploads')]
    folders: list[FolderInfo]


class FolderContentResponseData(ResponseData[FolderContent]): ...


class FolderDownload(ValidationAliasedModel):
    files: list[FileInfo]
    folders: list[FolderInfo]


class FolderDownloadResponseData(ResponseData[FolderDownload]): ...
