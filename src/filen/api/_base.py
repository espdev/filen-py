from typing import Self, Type
from enum import StrEnum

from httpx import AsyncClient, Client

from filen._context import Context
from filen.errors import APIKeyRequiredError, RequestErrorHandler

from .models.auth import RequestData, ResponseData


class APIEndpoint(StrEnum):
    """Base enumeration class for all API endpoint enumerations"""


class APIGenericBase[TClient: Client | AsyncClient]:
    """Base generic class for all sync/async Filen APIs"""

    def __init__(self, context: Context, http_client: TClient) -> None:
        self._context = context
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
            if api_key := self._context.api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            else:
                url = str(self._http_client.base_url).rstrip('/') + endpoint
                raise APIKeyRequiredError(f'API key required for {url}')
        return headers


class APIBase(APIGenericBase[Client]):
    """Base class for all sync APIs"""

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


class AsyncAPIBase(APIGenericBase[AsyncClient]):
    """Base class for all async APIs"""

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


class FilenAPIGenericBase[TClient: Client | AsyncClient, TAPI: APIBase | AsyncAPIBase]:
    """Base generic class for sync/async Filen API facades"""

    def __init__(self, context: Context, http_client: TClient):
        self._context = context
        self._http_client = http_client

    @property
    def closed(self) -> bool:
        return self._http_client.is_closed  # noqa

    def _create_api(self, api_type: Type[TAPI]) -> TAPI:
        return api_type(context=self._context, http_client=self._http_client)


class APIGenericDescriptor[TAPI: APIBase | AsyncAPIBase]:
    """Generic descriptor class initializes and caches API instances in sync/async Filen API facades"""

    def __init__(self, api_type: Type[TAPI]) -> None:
        self._api_type = api_type
        self._apis: dict[int, TAPI] = {}

    def __get__(
        self,
        filen_api: FilenAPIGenericBase | None,
        filen_api_type: Type[FilenAPIGenericBase] | None = None,
    ) -> TAPI | Self:
        if filen_api is None:
            return self

        _id = id(filen_api)

        if _id not in self._apis:
            self._apis[_id] = filen_api._create_api(self._api_type)  # noqa

        return self._apis[_id]


api = APIGenericDescriptor[APIBase]
"""API descriptor should be used in sync Filen API facade"""

async_api = APIGenericDescriptor[AsyncAPIBase]
"""API descriptor should be used in async Filen API facade"""
