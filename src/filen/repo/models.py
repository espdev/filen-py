from typing import Annotated, Literal, Self
from datetime import datetime
from enum import StrEnum, auto
from uuid import UUID

from pydantic import AliasChoices, ConfigDict, Field, computed_field, model_validator
from pydantic import BaseModel as _BaseModel

from filen.api.v3.models.link import PublicLinkExpiration
from filen.config import STORAGE_ROOT_NAME, AuthVersion, FileEncryptionVersion


class BaseModel(_BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserAuthInfo(BaseModel):
    id: int
    email: str
    salt: str
    auth_version: AuthVersion


class UserKeys(BaseModel):
    api_key: str
    master_keys: list[str]
    public_key: str
    private_key: str
    dek: str | None


class UserInfo(BaseModel):
    id: int
    email: str
    max_storage: int
    storage_used: int
    is_premium: bool
    avatar_url: str | None
    base_folder_uuid: UUID


class UserSettings(BaseModel):
    email: str
    two_factor_key: str | None
    two_factor_enabled: bool
    versioned_files: int
    versioned_storage: int
    unfinished_files: int
    unfinished_storage: int
    storage_used: int


class UserKeyPair(BaseModel):
    public_key: str
    private_key: str


class FileMetadata(BaseModel):
    """Decrypted file metadata"""

    name: str
    size: int
    mime: str
    key: str
    last_modified: Annotated[int, Field(validation_alias=AliasChoices('lastModified', 'last_modified'))]


class FolderMetadata(BaseModel):
    """Decrypted folder metadata (name)"""

    name: str


class FileInfo(BaseModel):
    uuid: UUID
    parent: UUID | None
    region: str
    bucket: str
    metadata: FileMetadata
    name_hashed: str
    favorited: bool
    versioned: bool = False
    trash: bool
    trash_timestamp: int | None = None
    version: FileEncryptionVersion
    timestamp: int

    @computed_field
    def type(self) -> Literal['file']:
        return 'file'


class FolderInfo(BaseModel):
    uuid: UUID
    parent: UUID | None
    name: str
    name_hashed: str
    favorited: bool
    trash: bool
    trash_parent: int | None = None
    trash_timestamp: int | None = None
    color: str | None
    timestamp: int

    @computed_field
    def type(self) -> Literal['folder']:
        return 'folder'

    @model_validator(mode='after')
    def _validate_model(self) -> Self:
        if self.name_hashed == STORAGE_ROOT_NAME:
            self.name_hashed = '/'
            self.name = '/'
        return self


class FolderContent(BaseModel):
    files: list[FileInfo]
    folders: list[FolderInfo]


class CreateFolderInfo(BaseModel):
    uuid: UUID
    timestamp: int | None = None

    @computed_field
    def created(self) -> bool:
        return self.timestamp is not None


class StorageItemType(StrEnum):
    file = auto()
    folder = auto()


type StorageItemTypeLiteral = Literal['folder', 'file']


class StorageItemPresent(BaseModel):
    present: bool
    trash: bool = False
    versioned: bool | None = None
    type: StorageItemType | None = None

    def __bool__(self) -> bool:
        return self.present

    @classmethod
    def not_present(cls) -> Self:
        return cls(present=False)


class StorageItemExists(BaseModel):
    uuid: UUID | None
    type: StorageItemType | None
    exists: bool

    @model_validator(mode='after')
    def _validate_model(self):
        if not self.exists:
            self.type = None
        return self

    def __bool__(self) -> bool:
        return self.exists

    @classmethod
    def not_exist(cls) -> Self:
        return cls(
            uuid=None,
            type=None,
            exists=False,
        )

    @classmethod
    def folder_exists(cls, uuid: UUID) -> Self:
        return cls(
            uuid=uuid,
            type=StorageItemType.folder,
            exists=True,
        )

    @classmethod
    def file_exists(cls, uuid: UUID) -> Self:
        return cls(
            uuid=uuid,
            type=StorageItemType.file,
            exists=True,
        )


class FileDetail(BaseModel):
    path: str
    name: str
    uuid: UUID
    parent: UUID
    size: int
    mime: str
    favorited: bool
    trash: bool
    created: datetime
    last_modified: datetime

    @computed_field
    def type(self) -> Literal['file']:
        return 'file'

    @classmethod
    def from_info(cls, path: str, file_info: FileInfo) -> Self:
        path = path.removesuffix(file_info.metadata.name).rstrip('/')

        return cls(
            path=f'{path}/{file_info.metadata.name}',
            name=file_info.metadata.name,
            uuid=file_info.uuid,
            parent=file_info.parent,
            size=file_info.metadata.size,
            mime=file_info.metadata.mime,
            favorited=file_info.favorited,
            trash=file_info.trash,
            created=datetime.fromtimestamp(file_info.timestamp),
            last_modified=datetime.fromtimestamp(file_info.metadata.last_modified / 1000),
        )


class FolderDetail(BaseModel):
    path: str
    name: str
    uuid: UUID
    parent: UUID | None
    favorited: bool
    trash: bool
    created: datetime

    @computed_field
    def type(self) -> Literal['folder']:
        return 'folder'

    @classmethod
    def from_info(cls, path: str, folder_info: FolderInfo) -> Self:
        path = path.removesuffix(folder_info.name).rstrip('/')

        return cls(
            path=f'{path}/{folder_info.name}',
            name=folder_info.name,
            uuid=folder_info.uuid,
            parent=folder_info.parent,
            favorited=folder_info.favorited,
            trash=folder_info.trash,
            created=datetime.fromtimestamp(folder_info.timestamp),
        )


class PublicLinkStatus(BaseModel):
    exists: Annotated[bool, Field(validation_alias=AliasChoices('exists', 'enabled'))]
    type: StorageItemType | None = None
    uuid: UUID | None = None
    item_uuid: UUID | None = None
    key: str | None = None
    link: str | None = None
    expiration: int | None = None
    expiration_text: PublicLinkExpiration | None = None
    download_btn: bool | None = None
    password: str | None = None

    @classmethod
    def not_exist(cls, link_type: StorageItemType | None = None, item_uuid: UUID | None = None) -> Self:
        return cls(exists=False, type=link_type, item_uuid=item_uuid)

    def __bool__(self) -> bool:
        return self.exists
