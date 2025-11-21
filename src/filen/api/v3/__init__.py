from .._base import APINamespaceBase, AsyncAPINamespaceBase, api
from ._auth import AsyncAuthAPI, AuthAPI
from ._dir import AsyncDirAPI, DirAPI
from ._user import AsyncUserAPI, UserAPI

__all__ = [
    'APIv3',
    'AsyncAPIv3',
]


class APIv3(APINamespaceBase):
    """Filen API v3 namespace"""

    auth: AuthAPI = api(AuthAPI)
    user: UserAPI = api(UserAPI)
    dir: DirAPI = api(DirAPI)


class AsyncAPIv3(AsyncAPINamespaceBase):
    """Async Filen API v3 namespace"""

    auth: AsyncAuthAPI = api(AsyncAuthAPI)
    user: AsyncUserAPI = api(AsyncUserAPI)
    dir: AsyncDirAPI = api(AsyncDirAPI)
