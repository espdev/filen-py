from httpx import AsyncClient, Client

from ._auth import AsyncAuthAPI, AuthAPI
from ._base import APIBase, APIFactoryMixIn, AsyncAPIBase, FilenAPIGenericBase, api
from ._dir import AsyncDirAPI, DirAPI
from ._user import AsyncUserAPI, UserAPI


class FilenAPI(FilenAPIGenericBase[Client, APIBase], APIFactoryMixIn):
    """Filen API provider (facade)"""

    auth: AuthAPI = api(AuthAPI)
    user: UserAPI = api(UserAPI)
    dir: DirAPI = api(DirAPI)


class AsyncFilenAPI(FilenAPIGenericBase[AsyncClient, AsyncAPIBase], APIFactoryMixIn):
    """Filen API async provider (facade)"""

    auth: AsyncAuthAPI = api(AsyncAuthAPI)
    user: AsyncUserAPI = api(AsyncUserAPI)
    dir: AsyncDirAPI = api(AsyncDirAPI)
