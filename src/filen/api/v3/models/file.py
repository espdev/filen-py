from uuid import UUID

from filen.config import FileEncryptionVersion

from .base import ResponseData, ValidationAliasedModel


class FileInfo(ValidationAliasedModel):
    uuid: UUID
    parent: UUID
    region: str
    bucket: str
    metadata: str
    name_hashed: str
    favorited: bool
    versioned: bool
    trash: bool
    version: FileEncryptionVersion
    timestamp: int


class FileInfoResponseData(ResponseData[FileInfo]): ...
