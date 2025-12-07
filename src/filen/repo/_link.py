from uuid import UUID

from filen.api.v3.models.dir import BASE_PARENT, FolderPublicLinkAddRequestData
from filen.api.v3.models.link import PublicLinkExpiration
from filen.crypto import encrypt_metadata_model

from ._base import AsyncRepoBase, RepoBase
from .models import FileInfo, FolderInfo, FolderMetadata


class PublicLink(RepoBase):
    def add_item_to_directory_public_link(
        self,
        item: FileInfo | FolderInfo,
        link_uuid: UUID,
        key: str,
        key_enc: str,
        expiration: PublicLinkExpiration,
    ) -> None:
        if item.type == 'folder':
            metadata = FolderMetadata(name=item.name)
        else:
            metadata = item.metadata

        metadata_enc = encrypt_metadata_model(metadata, key)

        link_add_data = FolderPublicLinkAddRequestData(
            uuid=item.uuid,
            parent=item.parent or BASE_PARENT,
            link_uuid=link_uuid,
            type=item.type,
            metadata=metadata_enc,
            key=key_enc,
            expiration=expiration,
        )

        self._api.v3.dir.link_add(link_add_data)


class AsyncPublicLink(AsyncRepoBase):
    async def add_item_to_directory_public_link(
        self,
        item: FileInfo | FolderInfo,
        link_uuid: UUID,
        key: str,
        key_enc: str,
        expiration: PublicLinkExpiration,
    ) -> None:
        if item.type == 'folder':
            metadata = FolderMetadata(name=item.name)
        else:
            metadata = item.metadata

        metadata_enc = await self._runner.run_sync(encrypt_metadata_model, metadata, key)

        link_add_data = FolderPublicLinkAddRequestData(
            uuid=item.uuid,
            parent=item.parent or BASE_PARENT,
            link_uuid=link_uuid,
            type=item.type,
            metadata=metadata_enc,
            key=key_enc,
            expiration=expiration,
        )

        await self._api.v3.dir.link_add(link_add_data)
