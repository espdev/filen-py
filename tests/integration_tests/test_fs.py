import secrets

import pytest

from filen.repo.models import StorageItemType

pytestmark = pytest.mark.integration

CLOUD_TEST_FOLDER = '/filen-py-tests'

PARAMS_TEST_EXISTS = [
    (CLOUD_TEST_FOLDER, True, StorageItemType.folder),
    (CLOUD_TEST_FOLDER.upper(), True, StorageItemType.folder),
    (CLOUD_TEST_FOLDER.strip('/'), True, StorageItemType.folder),
    (f'/{CLOUD_TEST_FOLDER}///', True, StorageItemType.folder),
    ('', True, StorageItemType.folder),
    ('/', True, StorageItemType.folder),
    ('/not_existing/', False, None),
    ('/not_existing/file.txt', False, None),
    ('/.././^${}<>[]7%#@', False, None),
]


@pytest.fixture(scope='module')
def cloud_test_folder(filen_client):
    filen_client.fs.mkdir(CLOUD_TEST_FOLDER)
    try:
        yield CLOUD_TEST_FOLDER
    finally:
        filen_client.fs.rmdir(CLOUD_TEST_FOLDER, permanent=True)


@pytest.fixture
def paths_for_mvdir(cloud_test_folder):
    name1 = secrets.token_urlsafe(8)
    name2 = secrets.token_urlsafe(8)
    name3 = secrets.token_urlsafe(8)

    path1 = f'{cloud_test_folder}/{name1}'
    path2 = f'{cloud_test_folder}/{name1}/{name2}'
    path3 = f'{cloud_test_folder}/{name3}'
    path4 = f'{cloud_test_folder}/{name3}/{name1}/{name2}'

    return path1, path2, path3, path4


@pytest.mark.parametrize('path, exists, item_type', PARAMS_TEST_EXISTS)
def test_folder_exists(cloud_test_folder, path, exists, item_type, filen_client):
    folder_exists = filen_client.fs.exists(path)
    assert folder_exists.exists is exists
    assert folder_exists.type == item_type


@pytest.mark.parametrize('path, exists, item_type', PARAMS_TEST_EXISTS)
async def test_async_folder_exists(cloud_test_folder, path, exists, item_type, async_filen_client):
    folder_exists = await async_filen_client.fs.exists(path)
    assert folder_exists.exists is exists
    assert folder_exists.type == item_type


def test_mkdir_rmdir_permanent(cloud_test_folder, filen_client):
    name1 = secrets.token_urlsafe(8)
    name2 = secrets.token_urlsafe(8)
    path1 = f'{cloud_test_folder}/{name1}/{name2}'

    folder_uuid = filen_client.fs.mkdir(path1)
    assert filen_client.fs.exists(path1).uuid == folder_uuid

    filen_client.fs.rmdir(f'{cloud_test_folder}/{name1}', permanent=True)
    assert filen_client.fs.exists(path1).exists is False


async def test_async_mkdir_rmdir_permanent(cloud_test_folder, async_filen_client):
    name1 = secrets.token_urlsafe(8)
    name2 = secrets.token_urlsafe(8)
    path = f'{cloud_test_folder}/{name1}/{name2}'

    folder_uuid = await async_filen_client.fs.mkdir(path)
    assert (await async_filen_client.fs.exists(path)).uuid == folder_uuid

    await async_filen_client.fs.rmdir(f'{cloud_test_folder}/{name1}', permanent=True)
    assert (await async_filen_client.fs.exists(path)).exists is False


def test_mvdir(paths_for_mvdir, filen_client):
    path1, path2, path3, path4 = paths_for_mvdir

    filen_client.fs.mkdir(path2)
    filen_client.fs.mkdir(path3)
    filen_client.fs.mvdir(path1, path3)

    assert filen_client.fs.exists(path2).exists is False
    assert filen_client.fs.exists(path4).exists is True


async def test_async_mvdir(paths_for_mvdir, async_filen_client):
    path1, path2, path3, path4 = paths_for_mvdir

    await async_filen_client.fs.mkdir(path2)
    await async_filen_client.fs.mkdir(path3)
    await async_filen_client.fs.mvdir(path1, path3)

    assert (await async_filen_client.fs.exists(path2)).exists is False
    assert (await async_filen_client.fs.exists(path4)).exists is True
