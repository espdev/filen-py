from typing import TYPE_CHECKING, Optional, Self, Type
from enum import StrEnum

from httpx import AsyncClient, Client

from filen.config import FilenConfig
from filen.errors import APIKeyRequiredError, RequestErrorHandler

from .models.auth import RequestData, ResponseData

if TYPE_CHECKING:
    from ._api import FilenAPIBase


class APIEndpoint(StrEnum):
    """Base enumeration class for all API endpoint enumerations"""


class _APIBase[TClient: Client | AsyncClient]:
    """Base class for all Filen APIs"""

    def __init__(self, config: FilenConfig, http_client: TClient) -> None:
        self._config = config
        self._http_client = http_client
        self._request_error_handler = RequestErrorHandler()

    @property
    def closed(self) -> bool:
        return self._http_client.is_closed  # noqa

    def _ensure_api_key(
        self,
        use_api_key: bool,
        endpoint: APIEndpoint,
        headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        headers = headers or {}
        if use_api_key:
            if api_key := self._config.api_key:
                headers['Authorization'] = f'Bearer {api_key.get_secret_value()}'
            else:
                url = str(self._http_client.base_url).rstrip('/') + endpoint
                raise APIKeyRequiredError(f'API key required for {url}')
        return headers


class APIBase(_APIBase[Client]):
    def _post[TResponse: ResponseData](
        self,
        endpoint: APIEndpoint,
        data: RequestData,
        response_model: Type[TResponse],
        use_api_key: bool = True,
    ) -> TResponse:
        headers = self._ensure_api_key(use_api_key, endpoint)

        with self._request_error_handler:
            r = self._http_client.post(endpoint, headers=headers, json=data.dump_for_payload())
            return response_model.from_response(r)

    def _get[TResponse: ResponseData](
        self,
        endpoint: APIEndpoint,
        response_model: Type[TResponse],
        use_api_key: bool = True,
    ) -> TResponse:
        headers = self._ensure_api_key(use_api_key, endpoint)

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
        headers = self._ensure_api_key(use_api_key, endpoint)

        with self._request_error_handler:
            r = await self._http_client.post(endpoint, headers=headers, json=data.dump_for_payload())
            return response_model.from_response(r)

    async def _get[TResponse: ResponseData](
        self,
        endpoint: APIEndpoint,
        response_model: Type[TResponse],
        use_api_key: bool = True,
    ) -> TResponse:
        headers = self._ensure_api_key(use_api_key, endpoint)

        with self._request_error_handler:
            r = await self._http_client.get(endpoint, headers=headers)
            return response_model.from_response(r)


class _APIDescriptor[TAPI: APIBase | AsyncAPIBase]:
    """API descriptor

    Initializes and caches API instances in the Filen API provider class.
    """

    def __init__(self, api_type: Type[TAPI]) -> None:
        self._api_type = api_type
        self._apis: dict[int, TAPI] = {}

    def __get__(
        self,
        filen_api: Optional['FilenAPIBase'],
        filen_api_type: Type['FilenAPIBase'] | None = None,
    ) -> TAPI | Self:
        if filen_api is None:
            return self

        _id = id(filen_api)

        if _id not in self._apis:
            self._apis[_id] = self._api_type(
                config=filen_api.config,
                http_client=filen_api._http_client,  # noqa
            )

        return self._apis[_id]


api = _APIDescriptor[APIBase | AsyncAPIBase]
