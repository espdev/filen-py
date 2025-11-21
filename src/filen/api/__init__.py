"""
Filen API layer

APIs implement functionality for interacting with Filen API on low-level data model level.
"""

from ._base import APIBase, APIEndpoint, APINamespaceBase, AsyncAPIBase, AsyncAPINamespaceBase, api
from .v3 import APIv3, AsyncAPIv3

__all__ = [
    'api',
    'APIEndpoint',
    'APIBase',
    'AsyncAPIBase',
    'APINamespaceBase',
    'AsyncAPINamespaceBase',
    'FilenAPI',
    'AsyncFilenAPI',
]


class FilenAPI(APINamespaceBase):
    """Sync Filen API namespace"""

    v3: APIv3 = api(APIv3)


class AsyncFilenAPI(AsyncAPINamespaceBase):
    """Async Filen API namespace"""

    v3: AsyncAPIv3 = api(AsyncAPIv3)
