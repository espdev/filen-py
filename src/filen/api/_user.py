from ._base import APIBase, APIEndpoint, AsyncAPIBase
from .models.user import (
    UserBaseFolderResponseData,
    UserInfoResponseData,
    UserKeyPairInfoResponseData,
    UserMasterKeysRequestData,
    UserMasterKeysResponseData,
    UserSettingsResponseData,
)


class UserEndpoint(APIEndpoint):
    user_info = '/user/info'
    user_settings = '/user/settings'
    base_folder = '/user/baseFolder'
    master_keys = '/user/masterKeys'
    user_key_pair_info = '/user/keyPair/info'


class UserAPI(APIBase):
    def info(self) -> UserInfoResponseData:
        return self._get(UserEndpoint.user_info, UserInfoResponseData)

    def settings(self) -> UserSettingsResponseData:
        return self._get(UserEndpoint.user_settings, UserSettingsResponseData)

    def base_folder(self) -> UserBaseFolderResponseData:
        return self._get(UserEndpoint.base_folder, UserBaseFolderResponseData)

    def master_keys(self, data: UserMasterKeysRequestData) -> UserMasterKeysResponseData:
        return self._post(UserEndpoint.master_keys, data, UserMasterKeysResponseData)

    def key_pair_info(self) -> UserKeyPairInfoResponseData:
        return self._get(UserEndpoint.user_key_pair_info, UserKeyPairInfoResponseData)


class AsyncUserAPI(AsyncAPIBase):
    async def info(self) -> UserInfoResponseData:
        return await self._get(UserEndpoint.user_info, UserInfoResponseData)

    async def settings(self) -> UserSettingsResponseData:
        return await self._get(UserEndpoint.user_settings, UserSettingsResponseData)

    async def base_folder(self) -> UserBaseFolderResponseData:
        return await self._get(UserEndpoint.base_folder, UserBaseFolderResponseData)

    async def master_keys(self, data: UserMasterKeysRequestData) -> UserMasterKeysResponseData:
        return await self._post(UserEndpoint.master_keys, data, UserMasterKeysResponseData)

    async def key_pair_info(self) -> UserKeyPairInfoResponseData:
        return await self._get(UserEndpoint.user_key_pair_info, UserKeyPairInfoResponseData)
