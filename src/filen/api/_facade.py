from httpx import AsyncClient, Client

from ._auth import AsyncAuthAPI, AuthAPI
from ._base import APIBase, AsyncAPIBase, FilenAPIBase, api, async_api
from ._user import AsyncUserAPI, UserAPI


class FilenAPI(FilenAPIBase[Client, APIBase]):
    """Filen API provider (facade)"""

    auth: AuthAPI = api(AuthAPI)
    user: UserAPI = api(UserAPI)


class AsyncFilenAPI(FilenAPIBase[AsyncClient, AsyncAPIBase]):
    """Filen API async provider (facade)"""

    auth: AsyncAuthAPI = async_api(AsyncAuthAPI)
    user: AsyncUserAPI = async_api(AsyncUserAPI)
