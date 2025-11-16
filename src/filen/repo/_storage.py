from typing import Final
from uuid import UUID

from filen.api.models.dir import (
    ContentType,
    FolderContent,
    FolderInfo,
    FolderMetadata,
    FolderUUIDRequestData,
    UploadMetadata,
)
from filen.crypto import decrypt_metadata

from ._base import AsyncRepoBase, RepoBase

type _ID = UUID | str

BASE_FOLDER_NAME: Final = 'default'


class StorageMixIn:
    @staticmethod
    def _collect_decrypted_metadata(
        folder_content: FolderContent,
        decryption_results: dict[tuple[ContentType, int], str],
    ) -> FolderContent:
        for (t, i), metadata in decryption_results.items():
            match t:
                case ContentType.upload:
                    folder_content.uploads[i].metadata = UploadMetadata.model_validate_json(metadata)
                case ContentType.folder:
                    folder_content.folders[i].name = FolderMetadata.model_validate_json(metadata).name
        return folder_content


class Storage(RepoBase, StorageMixIn):
    """Storage repository

    Provides methods for manipulating with directories and files in the cloud storage.
    """

    def info(self, uuid: _ID | None = None) -> FolderInfo:
        """Retrieve folder info with metadata decryption"""

        uuid = uuid if uuid else self._ensure_base_folder_uuid()
        folder_info = self._api.dir.info(FolderUUIDRequestData(uuid=uuid)).data

        if uuid != self._context.base_folder_uuid:
            master_keys = self._ensure_master_keys()
            metadata_json = decrypt_metadata(folder_info.name, master_keys)
            folder_info.name = FolderMetadata.model_validate_json(metadata_json).name

        return folder_info

    def content(self, uuid: _ID | None = None) -> FolderContent:
        """Retrieve folder content with metadata decryption"""

        uuid = uuid if uuid else self._ensure_base_folder_uuid()
        folder_content = self._api.dir.content(FolderUUIDRequestData(uuid=uuid)).data

        master_keys = self._ensure_master_keys()

        with self._runner.task_group() as tg:
            for i, upload in enumerate(folder_content.uploads):
                tg.add_task((ContentType.upload, i), decrypt_metadata, upload.metadata, master_keys)

            for i, folder in enumerate(folder_content.folders):
                tg.add_task((ContentType.folder, i), decrypt_metadata, folder.name, master_keys)

        return self._collect_decrypted_metadata(folder_content, tg.results)


class AsyncStorage(AsyncRepoBase, StorageMixIn):
    """Async Storage repository"""

    async def info(self, uuid: _ID | None = None) -> FolderInfo:
        uuid = uuid if uuid else (await self._ensure_base_folder_uuid())
        folder_info = (await self._api.dir.info(FolderUUIDRequestData(uuid=uuid))).data

        if uuid != self._context.base_folder_uuid:
            master_keys = await self._ensure_master_keys()
            metadata_json = await self._runner.run_sync(decrypt_metadata, folder_info.name, master_keys)
            folder_info.name = FolderMetadata.model_validate_json(metadata_json).name

        return folder_info

    async def content(self, uuid: _ID | None = None) -> FolderContent:
        uuid = uuid if uuid else (await self._ensure_base_folder_uuid())
        folder_content = (await self._api.dir.content(FolderUUIDRequestData(uuid=uuid))).data

        master_keys = await self._ensure_master_keys()

        async with self._runner.task_group() as tg:
            for i, upload in enumerate(folder_content.uploads):
                tg.add_task((ContentType.upload, i), decrypt_metadata, upload.metadata, master_keys)

            for i, folder in enumerate(folder_content.folders):
                tg.add_task((ContentType.folder, i), decrypt_metadata, folder.name, master_keys)

        return self._collect_decrypted_metadata(folder_content, tg.results)
