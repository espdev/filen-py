from typing import Annotated, Final, Literal
from enum import StrEnum, auto
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field, computed_field

from filen.config import FileEncryptionVersion

from .base import RequestData, ResponseData, StorageItemExists, ValidationAliasedModel
from .link import PublicLinkExpiration, PublicLinkStatus

BASE_PARENT: Final = 'base'


class FolderContentType(StrEnum):
    favorites = auto()
    recents = auto()
    links = auto()
    trash = auto()


class FolderContentRequestData(RequestData):
    uuid: UUID | FolderContentType


FolderParent = Annotated[UUID | None, BeforeValidator(lambda v: v if v != BASE_PARENT else None)]


class FolderInfo(ValidationAliasedModel):
    uuid: UUID
    parent: FolderParent
    name_encrypted: str
    name_hashed: str
    favorited: bool
    trash: bool
    color: str | None
    timestamp: int


class FolderInfoResponseData(ResponseData[FolderInfo]): ...


class FolderContentUploadInfo(ValidationAliasedModel):
    uuid: UUID
    parent: UUID | None
    region: str
    bucket: str
    metadata: str
    rm: str
    chunks: int
    size: int
    favorited: bool
    version: FileEncryptionVersion
    trash_timestamp: int | None = None
    timestamp: int


class FolderContentFolderInfo(BaseModel):
    uuid: UUID
    parent: FolderParent
    name: str
    favorited: bool
    color: str | None
    trash_parent: int | None = None
    trash_timestamp: int | None = None
    timestamp: int


class FolderContent(ValidationAliasedModel):
    uploads: list[FolderContentUploadInfo]
    folders: list[FolderContentFolderInfo]


class FolderContentResponseData(ResponseData[FolderContent]): ...


class FolderDownloadFileInfo(ValidationAliasedModel):
    uuid: UUID
    parent: UUID
    region: str
    bucket: str
    metadata: str
    name_hashed: str
    chunks: int
    chunks_size: int
    favorited: bool
    version: FileEncryptionVersion
    timestamp: int


class FolderDownloadFolderInfo(ValidationAliasedModel):
    uuid: UUID
    parent: FolderParent
    name: str
    name_hashed: str
    favorited: bool
    color: str | None
    timestamp: int


class FolderDownload(ValidationAliasedModel):
    files: list[FolderDownloadFileInfo]
    folders: list[FolderDownloadFolderInfo]


class FolderDownloadResponseData(ResponseData[FolderDownload]): ...


class FolderCreateRequestData(RequestData):
    uuid: UUID
    name: str
    name_hashed: str
    parent: UUID


class FolderCreated(ValidationAliasedModel):
    uuid: UUID
    timestamp: int = None


class FolderCreateResponseData(ResponseData[FolderCreated]): ...


class FolderExistsResponseData(ResponseData[StorageItemExists]): ...


class FolderPresent(ValidationAliasedModel):
    present: bool
    trash: bool = False


class FolderPresentResponseData(ResponseData[FolderPresent]): ...


class FolderMoveRequestData(RequestData):
    uuid: UUID
    to: UUID


class FolderRenameRequestData(RequestData):
    uuid: UUID
    name: str
    name_hashed: str


class FolderPublicLinkStatusResponseData(ResponseData[PublicLinkStatus]): ...


class FolderPublicLinkAddRequestData(RequestData):
    uuid: UUID
    parent: UUID | Literal['base']
    link_uuid: Annotated[UUID, Field(serialization_alias='linkUUID')]
    type: Literal['file', 'folder']
    metadata: str
    key: str
    expiration: PublicLinkExpiration


class FolderPublicLinkEditRequestData(RequestData):
    uuid: UUID
    expiration: PublicLinkExpiration
    has_password: Annotated[bool, Field(exclude=True)]
    password_hashed: str
    salt: str
    download_btn: bool

    @computed_field
    def password(self) -> Literal['empty', 'notempty']:
        return 'notempty' if self.has_password else 'empty'
