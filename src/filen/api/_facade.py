from httpx import AsyncClient, Client

from ._auth import AsyncAuthAPI, AuthAPI
from ._base import APIBase, AsyncAPIBase, FilenAPIGenericBase, api, async_api
from ._user import AsyncUserAPI, UserAPI


class FilenAPI(FilenAPIGenericBase[Client, APIBase]):
    """Filen API provider (facade)"""

    auth: AuthAPI = api(AuthAPI)
    user: UserAPI = api(UserAPI)


class AsyncFilenAPI(FilenAPIGenericBase[AsyncClient, AsyncAPIBase]):
    """Filen API async provider (facade)"""

    auth: AsyncAuthAPI = async_api(AsyncAuthAPI)
    user: AsyncUserAPI = async_api(AsyncUserAPI)
