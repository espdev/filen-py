from typing import AsyncContextManager, ContextManager

import pytest

from filen import AsyncFilenClient, FilenClient, FilenConfig

SKIP_MESSAGE = 'Missing authentication info to use Filen client: API key, master keys.'


@pytest.fixture(scope='session')
def filen_client(config: FilenConfig) -> ContextManager[FilenClient]:
    with FilenClient(config) as client:
        if not client.ensure_context(raise_err=False):
            pytest.skip(SKIP_MESSAGE)
        yield client


@pytest.fixture(scope='session')
async def async_filen_client(config: FilenConfig) -> AsyncContextManager[AsyncFilenClient]:
    async with AsyncFilenClient(config) as client:
        if not (await client.ensure_context(raise_err=False)):
            pytest.skip(SKIP_MESSAGE)
        yield client
