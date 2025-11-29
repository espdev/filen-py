from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, computed_field

from filen.config import FileEncryptionVersion

from .base import RequestData, ResponseData, StorageItemExists, ValidationAliasedModel
from .link import PublicLinkExpiration, PublicLinkStatus


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


class FilePresent(ValidationAliasedModel):
    present: bool
    trash: bool = False
    versioned: bool = False


class FilePresentResponseData(ResponseData[FilePresent]): ...


class FileExistsResponseData(ResponseData[StorageItemExists]): ...


class FileMoveRequestData(RequestData):
    uuid: UUID
    to: UUID


class FileRenameRequestData(RequestData):
    uuid: UUID
    name: str
    metadata: str
    name_hashed: str


class FilePublicLinkStatusResponseData(ResponseData[PublicLinkStatus]): ...


class FilePublicLinkEditRequestData(RequestData):
    uuid: Annotated[UUID, Field(serialization_alias='fileUUID')]
    link_uuid: Annotated[UUID, Field(serialization_alias='uuid')]
    expiration: PublicLinkExpiration
    has_password: Annotated[bool, Field(exclude=True)]
    password_hashed: str
    salt: str
    download_btn: bool
    type: Literal['enable', 'disable']

    @computed_field
    def password(self) -> Literal['empty', 'notempty']:
        return 'notempty' if self.has_password else 'empty'
