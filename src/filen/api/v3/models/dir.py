from typing import Annotated, Final
from enum import StrEnum, auto
from uuid import UUID

from pydantic import AliasChoices, Field, computed_field, field_validator, model_validator

from .base import RequestData, ResponseData, ValidationAliasedModel
from .file import FileEncryptionVersion, FileMetadata

ROOT_PARENT: Final = 'base'


class FolderItem(StrEnum):
    file = auto()
    folder = auto()


class FolderContentType(StrEnum):
    favorites = auto()
    recents = auto()
    links = auto()
    trash = auto()


class FolderContentRequestData(RequestData):
    uuid: UUID | FolderContentType


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
        if v == ROOT_PARENT:
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


class FolderCreateRequestData(RequestData):
    uuid: UUID
    name: str
    name_hashed: str
    parent: UUID


class FolderCreated(ValidationAliasedModel):
    uuid: UUID
    timestamp: int = None

    @computed_field
    def created(self) -> bool:
        return self.timestamp is not None


class FolderCreateResponseData(ResponseData[FolderCreated]): ...
