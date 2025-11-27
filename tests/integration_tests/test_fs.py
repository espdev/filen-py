import pytest

from filen.repo.models import StorageItemType

pytestmark = pytest.mark.integration

CLOUD_TEST_FOLDER = '/Projects/filen-py/tests'
CLOUD_TEST_FILE = '/Projects/filen-py/tests/file.txt'

PARAMS_TEST_EXISTS = [
    (CLOUD_TEST_FOLDER, True, StorageItemType.folder),
    (CLOUD_TEST_FOLDER.strip('/'), True, StorageItemType.folder),
    (f'/{CLOUD_TEST_FOLDER}///', True, StorageItemType.folder),
    ('', True, StorageItemType.folder),
    ('/', True, StorageItemType.folder),
    (CLOUD_TEST_FILE, True, StorageItemType.file),
    (CLOUD_TEST_FILE.upper(), True, StorageItemType.file),
    (CLOUD_TEST_FILE.lower(), True, StorageItemType.file),
    ('/not_existing/', False, None),
    ('/not_existing/file.txt', False, None),
    ('/.././^${}<>[]7%#@', False, None),
]


@pytest.mark.parametrize('path, exists, item_type', PARAMS_TEST_EXISTS)
def test_folder_exists(path, exists, item_type, filen_client):
    folder_exists = filen_client.fs.exists(path)
    assert folder_exists.exists is exists
    assert folder_exists.type == item_type


@pytest.mark.parametrize('path, exists, item_type', PARAMS_TEST_EXISTS)
async def test_async_folder_exists(path, exists, item_type, async_filen_client):
    folder_exists = await async_filen_client.fs.exists(path)
    assert folder_exists.exists is exists
    assert folder_exists.type == item_type
