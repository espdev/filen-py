from typing import Type
from enum import StrEnum

from httpx import AsyncClient, Client

from filen.config import FilenConfig
from filen.errors import RequestErrorHandler

from .models.auth import RequestData, ResponseData


class APIEndpoint(StrEnum):
    """All API endpoints"""

    # Auth
    auth_info = '/auth/info'
    login = '/login'

    # User
    user_info = '/user/info'


class _APIBase[TClient: Client | AsyncClient]:
    """Base class for all Filen APIs"""

    def __init__(self, config: FilenConfig, http_client: TClient) -> None:
        self._config = config
        self._http_client = http_client
        self._request_error_handler = RequestErrorHandler()

    @property
    def closed(self) -> bool:
        return self._http_client.is_closed  # noqa

    def _use_api_key(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        headers = headers or {}
        if api_key := self._config.api_key:
            headers['Authorization'] = f'Bearer {api_key.get_secret_value()}'
        return headers


class APIBase(_APIBase[Client]):
    def _post[TResponse: ResponseData](
        self,
        endpoint: APIEndpoint,
        data: RequestData,
        response_model: Type[TResponse],
        use_api_key: bool = True,
    ) -> TResponse:
        headers = {}
        if use_api_key:
            headers = self._use_api_key()

        with self._request_error_handler:
            r = self._http_client.post(endpoint, headers=headers, json=data.dump_for_payload())
            return response_model.from_response(r)

    def _get[TResponse: ResponseData](
        self,
        endpoint: APIEndpoint,
        response_model: Type[TResponse],
        use_api_key: bool = True,
    ) -> TResponse:
        headers = {}
        if use_api_key:
            headers = self._use_api_key()

        with self._request_error_handler:
            r = self._http_client.get(endpoint, headers=headers)
            return response_model.from_response(r)


class AsyncAPIBase(_APIBase[AsyncClient]):
    async def _post[TResponse: ResponseData](
        self,
        endpoint: APIEndpoint,
        data: RequestData,
        response_model: Type[TResponse],
        *,
        use_api_key: bool = True,
    ) -> TResponse:
        headers = {}
        if use_api_key:
            headers = self._use_api_key()

        with self._request_error_handler:
            r = await self._http_client.post(endpoint, headers=headers, json=data.dump_for_payload())
            return response_model.from_response(r)

    async def _get[TResponse: ResponseData](
        self,
        endpoint: APIEndpoint,
        response_model: Type[TResponse],
        use_api_key: bool = True,
    ) -> TResponse:
        headers = {}
        if use_api_key:
            headers = self._use_api_key()

        with self._request_error_handler:
            r = await self._http_client.get(endpoint, headers=headers)
            return response_model.from_response(r)
