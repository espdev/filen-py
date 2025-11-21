from ._base import APINamespaceBase, AsyncAPINamespaceBase, api
from .v3 import APIv3, AsyncAPIv3


class FilenAPI(APINamespaceBase):
    """Sync Filen API namespace"""

    v3: APIv3 = api(APIv3)


class AsyncFilenAPI(AsyncAPINamespaceBase):
    """Async Filen API namespace"""

    v3: AsyncAPIv3 = api(AsyncAPIv3)
