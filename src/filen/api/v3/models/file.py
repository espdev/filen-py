from enum import ReprEnum
from uuid import UUID

from .base import ResponseData, ValidationAliasedModel


class FileEncryptionVersion(float, ReprEnum):
    v1 = 1
    v1_5 = 1.5
    v2 = 2
    v3 = 3


class FileMetadata(ValidationAliasedModel):
    """Decrypted file metadata"""

    name: str
    size: int
    mime: str
    key: str
    last_modified: int


class FileInfo(ValidationAliasedModel):
    uuid: UUID
    parent: UUID
    region: str
    bucket: str
    metadata: str | FileMetadata
    name_hashed: str
    favorited: bool
    versioned: bool
    trash: bool
    version: FileEncryptionVersion
    timestamp: int


class FileInfoResponseData(ResponseData[FileInfo]): ...
