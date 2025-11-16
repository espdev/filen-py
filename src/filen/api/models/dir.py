from uuid import UUID

from .base import RequestData, ResponseData, ValidationAliasedModel


class FolderUUIDRequestData(RequestData):
    uuid: UUID


class FolderInfo(ValidationAliasedModel):
    uuid: UUID
    name_encrypted: str
    name_hashed: str
    parent: str | None
    trash: bool
    favorited: bool
    color: str | None


class FolderInfoResponseData(ResponseData[FolderInfo]): ...
