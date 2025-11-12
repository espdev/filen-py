from ._base import APIBase, APIEndpoint, AsyncAPIBase
from .models.user import UserInfoResponseData


class UserAPI(APIBase):
    def info(self) -> UserInfoResponseData:
        return self._get(APIEndpoint.user_info, UserInfoResponseData)


class AsyncUserAPI(AsyncAPIBase):
    async def info(self) -> UserInfoResponseData:
        return await self._get(APIEndpoint.user_info, UserInfoResponseData)
