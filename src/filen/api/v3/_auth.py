from .._base import APIBase, AsyncAPIBase
from ._base import APIv3Endpoint
from .models.auth import (
    AuthInfoRequestData,
    AuthInfoResponseData,
    LoginRequestData,
    LoginResponseData,
)


class AuthEndpoint(APIv3Endpoint):
    auth_info = '/auth/info'
    login = '/login'


class AuthAPI(APIBase):
    def info(self, data: AuthInfoRequestData) -> AuthInfoResponseData:
        return self._post(AuthEndpoint.auth_info, data, AuthInfoResponseData, use_api_key=False)

    def login(self, data: LoginRequestData) -> LoginResponseData:
        return self._post(AuthEndpoint.login, data, LoginResponseData, use_api_key=False)


class AsyncAuthAPI(AsyncAPIBase):
    async def info(self, data: AuthInfoRequestData) -> AuthInfoResponseData:
        return await self._post(AuthEndpoint.auth_info, data, AuthInfoResponseData, use_api_key=False)

    async def login(self, data: LoginRequestData) -> LoginResponseData:
        return await self._post(AuthEndpoint.login, data, LoginResponseData, use_api_key=False)
