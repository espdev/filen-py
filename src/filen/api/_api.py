from typing import Self, Type
from dataclasses import dataclass, field

from httpx import AsyncClient, Client

from filen.config import FilenConfig

from ._auth import AsyncAuthAPI, AuthAPI
from ._base import APIBase, AsyncAPIBase
from ._user import AsyncUserAPI, UserAPI


@dataclass(slots=True)
class FilenAPIBase[TClient: Client | AsyncClient]:
    """Base class for Filen APIs"""

    config: FilenConfig
    http_client: TClient

    @property
    def closed(self) -> bool:
        return self.http_client.is_closed  # noqa

    def _init_api[T: APIBase | AsyncAPIBase](self, api_cls: Type[T]) -> T:
        return api_cls(self.config, self.http_client)


@dataclass(slots=True)
class FilenAPI(FilenAPIBase[Client]):
    """Filen API provider"""

    auth: AuthAPI = field(init=False)
    user: UserAPI = field(init=False)

    def __post_init__(self):
        self.auth = self._init_api(AuthAPI)
        self.user = self._init_api(UserAPI)

    def __enter__(self) -> Self:
        self.http_client.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.http_client.__exit__(exc_type, exc_val, exc_tb)


@dataclass(slots=True)
class AsyncFilenAPI(FilenAPIBase[AsyncClient]):
    """Filen API async provider"""

    auth: AsyncAuthAPI = field(init=False)
    user: AsyncUserAPI = field(init=False)

    def __post_init__(self):
        self.auth = self._init_api(AsyncAuthAPI)
        self.user = self._init_api(AsyncUserAPI)

    async def __aenter__(self) -> Self:
        await self.http_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self.http_client.__aexit__(exc_type, exc_val, exc_tb)
