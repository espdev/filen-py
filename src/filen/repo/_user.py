from filen.api.models.user import UserInfoData

from ._base import AsyncRepo, Repo


class User(Repo):
    """User repository"""

    def info(self) -> UserInfoData:
        return self._api.user.info().data


class AsyncUser(AsyncRepo):
    """Async user repository"""

    async def info(self) -> UserInfoData:
        return (await self._api.user.info()).data
