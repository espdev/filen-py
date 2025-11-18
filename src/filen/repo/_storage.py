from uuid import UUID

from filen.api.models.dir import (
    BASE_FOLDER_NAME,
    FileMetadata,
    FolderContent,
    FolderContentRequestData,
    FolderContentType,
    FolderDownload,
    FolderInfo,
    FolderItem,
    FolderMetadata,
    FolderUUIDRequestData,
)
from filen.crypto import decrypt_metadata

from ._base import AsyncRepoBase, RepoBase

type ItemId = UUID | str


class StorageMixIn:
    @staticmethod
    def _collect_decrypted_metadata[T: FolderContent | FolderDownload](
        folder_items: T,
        decryption_results: dict[tuple[FolderItem, int], str],
    ) -> T:
        for (t, i), metadata in decryption_results.items():
            match t:
                case FolderItem.file:
                    folder_items.files[i].metadata = FileMetadata.model_validate_json(metadata)
                case FolderItem.folder:
                    folder_items.folders[i].metadata = FolderMetadata.model_validate_json(metadata)
        return folder_items


class Storage(RepoBase, StorageMixIn):
    """Storage repository

    Provides methods for manipulating with directories and files in the cloud storage.
    """

    def base_folder(self) -> UUID:
        """Retrieve the base foder UUID (root srorage UUID)"""

        return self._ensure_base_folder_uuid()

    def folder_info(self, uuid: ItemId | None = None) -> FolderInfo:
        """Retrieve folder info with metadata decryption"""

        uuid = uuid if uuid else self._ensure_base_folder_uuid()
        folder_info = self._api.dir.info(FolderUUIDRequestData(uuid=uuid)).data

        if uuid != self._context.base_folder_uuid:
            master_keys = self._ensure_master_keys()
            metadata_json = decrypt_metadata(folder_info.metadata, master_keys)
            folder_info.metadata = FolderMetadata.model_validate_json(metadata_json)
        else:
            folder_info.metadata = FolderMetadata(name=BASE_FOLDER_NAME)
            folder_info.name_hashed = BASE_FOLDER_NAME

        return folder_info

    def folder_content(self, uuid: ItemId | FolderContentType | None = None) -> FolderContent:
        """Retrieve folder content with metadata decryption"""

        uuid = uuid if uuid else self._ensure_base_folder_uuid()
        master_keys = self._ensure_master_keys()

        folder_content = self._api.dir.content(FolderContentRequestData(uuid=uuid)).data

        with self._runner.task_group() as tg:
            for i, file in enumerate(folder_content.files):
                tg.add_task((FolderItem.file, i), decrypt_metadata, file.metadata, master_keys)

            for i, folder in enumerate(folder_content.folders):
                tg.add_task((FolderItem.folder, i), decrypt_metadata, folder.metadata, master_keys)

        return self._collect_decrypted_metadata(folder_content, tg.results)

    def folder_download(self, uuid: ItemId | None = None) -> FolderDownload:
        """Retrieve folder tree (flattened) with metadata decryption"""

        uuid = uuid if uuid else self._ensure_base_folder_uuid()
        master_keys = self._ensure_master_keys()

        folder_download = self._api.dir.download(FolderUUIDRequestData(uuid=uuid)).data

        with self._runner.task_group() as tg:
            for i, file in enumerate(folder_download.files):
                tg.add_task((FolderItem.file, i), decrypt_metadata, file.metadata, master_keys)

            for i, folder in enumerate(folder_download.folders):
                tg.add_task((FolderItem.folder, i), decrypt_metadata, folder.metadata, master_keys)

        return self._collect_decrypted_metadata(folder_download, tg.results)


class AsyncStorage(AsyncRepoBase, StorageMixIn):
    """Async Storage repository"""

    async def base_folder(self) -> UUID:
        return await self._ensure_base_folder_uuid()

    async def folder_info(self, uuid: ItemId | FolderContentType | None = None) -> FolderInfo:
        uuid = uuid if uuid else (await self._ensure_base_folder_uuid())
        folder_info = (await self._api.dir.info(FolderUUIDRequestData(uuid=uuid))).data

        if uuid != self._context.base_folder_uuid:
            master_keys = await self._ensure_master_keys()
            metadata_json = await self._runner.run_sync(decrypt_metadata, folder_info.metadata, master_keys)
            folder_info.metadata = FolderMetadata.model_validate_json(metadata_json)
        else:
            folder_info.metadata = FolderMetadata(name=BASE_FOLDER_NAME)
            folder_info.name_hashed = BASE_FOLDER_NAME

        return folder_info

    async def folder_content(self, uuid: ItemId | None = None) -> FolderContent:
        uuid = uuid if uuid else (await self._ensure_base_folder_uuid())
        master_keys = await self._ensure_master_keys()

        folder_content = (await self._api.dir.content(FolderContentRequestData(uuid=uuid))).data

        async with self._runner.task_group() as tg:
            for i, file in enumerate(folder_content.files):
                tg.add_task((FolderItem.file, i), decrypt_metadata, file.metadata, master_keys)

            for i, folder in enumerate(folder_content.folders):
                tg.add_task((FolderItem.folder, i), decrypt_metadata, folder.metadata, master_keys)

        return self._collect_decrypted_metadata(folder_content, tg.results)

    async def folder_download(self, uuid: ItemId | None = None) -> FolderDownload:
        uuid = uuid if uuid else self._ensure_base_folder_uuid()
        master_keys = await self._ensure_master_keys()

        folder_download = (await self._api.dir.download(FolderUUIDRequestData(uuid=uuid))).data

        async with self._runner.task_group() as tg:
            for i, file in enumerate(folder_download.files):
                tg.add_task((FolderItem.file, i), decrypt_metadata, file.metadata, master_keys)

            for i, folder in enumerate(folder_download.folders):
                tg.add_task((FolderItem.folder, i), decrypt_metadata, folder.metadata, master_keys)

        return self._collect_decrypted_metadata(folder_download, tg.results)
