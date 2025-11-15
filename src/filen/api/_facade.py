from httpx import AsyncClient, Client

from filen.config import FilenConfig

from ._auth import AsyncAuthAPI, AuthAPI
from ._base import api
from ._user import AsyncUserAPI, UserAPI


class FilenAPIBase[TClient: Client | AsyncClient]:
    """Base class for Filen API providers (facades)"""

    def __init__(self, config: FilenConfig, http_client: TClient):
        self.config = config
        self._http_client = http_client

    @property
    def closed(self) -> bool:
        return self._http_client.is_closed  # noqa


class FilenAPI(FilenAPIBase[Client]):
    """Filen API provider"""

    auth: AuthAPI = api(AuthAPI)
    user: UserAPI = api(UserAPI)


class AsyncFilenAPI(FilenAPIBase[AsyncClient]):
    """Filen API async provider"""

    auth: AsyncAuthAPI = api(AsyncAuthAPI)
    user: AsyncUserAPI = api(AsyncUserAPI)
