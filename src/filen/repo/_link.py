from urllib.parse import quote
from uuid import UUID

from filen.api.v3.models import StorageItemUUIDRequestData
from filen.api.v3.models.dir import BASE_PARENT, FolderPublicLinkAddRequestData
from filen.api.v3.models.link import PublicLinkExpiration
from filen.config import FILEN_FILE_PUBLIC_LINK_BASE_URL, FILEN_FOLDER_PUBLIC_LINK_BASE_URL
from filen.crypto import decrypt_metadata, encrypt_metadata_model

from ._base import AsyncRepoBase, RepoBase
from .models import FileInfo, FolderInfo, FolderLinked, FolderLinkInfo, FolderMetadata, StorageItemType

type ItemId = UUID | str


class PublicLinkMixIn:
    @staticmethod
    def get_public_link_url(item_type: StorageItemType, link_uuid: ItemId, link_key: str) -> str:
        if item_type == StorageItemType.file:
            link_base_url = FILEN_FILE_PUBLIC_LINK_BASE_URL
        else:
            link_base_url = FILEN_FOLDER_PUBLIC_LINK_BASE_URL

        link_path = quote(f'{link_uuid}#{link_key}')
        return f'{link_base_url}/{link_path}'


class PublicLink(RepoBase, PublicLinkMixIn):
    def folder_public_linked(self, item_uuid: ItemId) -> FolderLinked:
        folder_linked = self._api.v3.dir.linked(data=StorageItemUUIDRequestData(uuid=item_uuid)).data
        key = self._ensure_master_key()

        link_keys_enc = {}

        with self._runner.task_group() as tg:
            for link_info in folder_linked.links:
                link_keys_enc[link_info.link_uuid] = link_info.link_key
                tg.add_task(link_info.link_uuid, decrypt_metadata, link_info.link_key, key)

        links = []

        for link_uuid, link_key in tg.results.items():
            links.append(
                FolderLinkInfo(
                    link_uuid=link_uuid,
                    link_key=link_key,
                    link_key_encrypted=link_keys_enc[link_uuid],
                    link_url=self.get_public_link_url(StorageItemType.folder, link_uuid, link_key),
                )
            )

        return FolderLinked(exists=folder_linked.exists, links=links)

    def add_item_to_directory_public_link(
        self,
        item: FileInfo | FolderInfo,
        link_uuid: ItemId,
        key: str,
        key_enc: str,
        expiration: PublicLinkExpiration = 'never',
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


class AsyncPublicLink(AsyncRepoBase, PublicLinkMixIn):
    async def folder_public_linked(self, item_uuid: ItemId) -> FolderLinked:
        folder_linked = (await self._api.v3.dir.linked(data=StorageItemUUIDRequestData(uuid=item_uuid))).data
        key = await self._ensure_master_key()

        link_keys_enc = {}

        async with self._runner.task_group() as tg:
            for link_info in folder_linked.links:
                link_keys_enc[link_info.link_uuid] = link_info.link_key
                tg.add_task(link_info.link_uuid, decrypt_metadata, link_info.link_key, key)

        links = []

        for link_uuid, link_key in tg.results.items():
            links.append(
                FolderLinkInfo(
                    link_uuid=link_uuid,
                    link_key=link_key,
                    link_key_encrypted=link_keys_enc[link_uuid],
                    link_url=self.get_public_link_url(StorageItemType.folder, link_uuid, link_key),
                )
            )

        return FolderLinked(exists=folder_linked.exists, links=links)

    async def add_item_to_directory_public_link(
        self,
        item: FileInfo | FolderInfo,
        link_uuid: ItemId,
        key: str,
        key_enc: str,
        expiration: PublicLinkExpiration = 'never',
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
