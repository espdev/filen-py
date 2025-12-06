from typing import Annotated, Literal
from hashlib import sha512
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

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
    chunks: int
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
    metadata: str
    name: str
    name_hashed: str


class FileUploadChunkRequestData(RequestData):
    uuid: UUID
    index: int
    parent: UUID
    upload_key: str
    hash: str
    chunk: bytes

    @property
    def url_params(self) -> dict[str, str | int]:
        return self.dump_for_payload(exclude={'chunk'})

    def url_params_hash(self) -> str:
        json_data = self.model_dump_json(exclude={'chunk'}, by_alias=True)
        return sha512(json_data.encode()).hexdigest()


class FileUploadChunkResponse(BaseModel):
    bucket: str
    region: str


class FileUploadBase(RequestData):
    uuid: UUID
    name: str
    name_hashed: str
    mime: str
    size: int
    metadata: str
    version: FileEncryptionVersion


class FileUploadDone(FileUploadBase):
    rm: str
    chunks: int
    upload_key: str


class FileUploadEmpty(FileUploadBase):
    parent: UUID


class FileUploadStatus(ValidationAliasedModel):
    chunks: int
    size: int


class FileUploadStatusResponseData(ResponseData[FileUploadStatus]): ...


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
