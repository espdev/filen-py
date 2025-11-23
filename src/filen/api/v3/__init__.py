"""
Filen API v3

https://gateway.filen.io/v3/docs/
"""

from .._base import APINamespaceBase, AsyncAPINamespaceBase, api
from ._auth import AsyncAuthAPI, AuthAPI
from ._dir import AsyncDirAPI, DirAPI
from ._file import AsyncFileAPI, FileAPI
from ._user import AsyncUserAPI, UserAPI
from .models.dir import FolderContentType
from .models.link import PublicLinkExpiration

__all__ = [
    'APIv3',
    'AsyncAPIv3',
    'FolderContentType',
    'PublicLinkExpiration',
]


class APIv3(APINamespaceBase):
    """Filen API v3 namespace"""

    auth: AuthAPI = api(AuthAPI)
    user: UserAPI = api(UserAPI)
    dir: DirAPI = api(DirAPI)
    file: FileAPI = api(FileAPI)


class AsyncAPIv3(AsyncAPINamespaceBase):
    """Async Filen API v3 namespace"""

    auth: AsyncAuthAPI = api(AsyncAuthAPI)
    user: AsyncUserAPI = api(AsyncUserAPI)
    dir: AsyncDirAPI = api(AsyncDirAPI)
    file: AsyncFileAPI = api(AsyncFileAPI)
