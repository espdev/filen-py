from typing import Any, Final, Self, Type
from abc import ABC, abstractmethod
from enum import StrEnum

from httpx import AsyncClient, Client, Response
from pydantic import BaseModel

from filen._context import Context
from filen._helpers import FactoryDescriptor
from filen._logging import debug_log_api_request, debug_log_api_response
from filen.errors import APIKeyRequiredError, RequestErrorHandler

API_VERSION_PATH: Final = '/v3'


class APIEndpoint(StrEnum):
    """Base enumeration class for all API endpoint enumerations"""


class RequestModelBase(BaseModel):
    def dump_for_payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, mode='json')


class ResponseModelBase(BaseModel, ABC):
    @classmethod
    @abstractmethod
    def from_response(cls, response: Response) -> Self:
        """Create the response model from the HTTP client response object"""


class APIGenericBase[TClient: Client | AsyncClient]:
    """Base generic class for all sync/async Filen APIs"""

    def __init__(self, context: Context, http_client: TClient) -> None:
        self._context = context
        self._http_client = http_client
        self._request_error_handler = RequestErrorHandler()

    @property
    def is_closed(self) -> bool:
        return self._http_client.is_closed  # noqa

    def _get_api_url(self, endpoint: str) -> str:
        base_url = self._context.get_gateway_url().rstrip('/')
        return f'{base_url}{API_VERSION_PATH}{endpoint}'

    def _ensure_api_key(
        self,
        use_api_key: bool,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        headers = headers or {}
        if use_api_key:
            if api_key := self._context.api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            else:
                raise APIKeyRequiredError(f'API key required for {url}')
        return headers


class APINamespaceGenericBase[TClient: Client | AsyncClient, TAPI: APIBase | AsyncAPIBase]:
    """Base generic class for sync/async API namespaces"""

    def __init__(self, context: 'Context', http_client: TClient):
        self._context = context
        self._http_client = http_client

    @property
    def is_closed(self) -> bool:
        return self._http_client.is_closed  # noqa


class APIFactoryMixIn:
    _context: Context
    _http_client: Client | AsyncClient

    def _create[T: APIGenericBase | APINamespaceGenericBase](self, api_type: Type[T]) -> T:
        return api_type(context=self._context, http_client=self._http_client)


class APIBase(APIGenericBase[Client], APIFactoryMixIn):
    """Base class for all sync APIs"""

    def _post[TResponse: ResponseModelBase](
        self,
        endpoint: APIEndpoint,
        data: RequestModelBase,
        response_model: Type[TResponse],
        use_api_key: bool = True,
    ) -> TResponse:
        url = self._get_api_url(endpoint)
        headers = self._ensure_api_key(use_api_key, url)

        with self._request_error_handler:
            debug_log_api_request('post', url, data)
            r = self._http_client.post(url, headers=headers, json=data.dump_for_payload())
            debug_log_api_response('post', r)
            return response_model.from_response(r)

    def _get[TResponse: ResponseModelBase](
        self,
        endpoint: APIEndpoint,
        response_model: Type[TResponse],
        use_api_key: bool = True,
    ) -> TResponse:
        url = self._get_api_url(endpoint)
        headers = self._ensure_api_key(use_api_key, url)

        with self._request_error_handler:
            debug_log_api_request('get', url)
            r = self._http_client.get(url, headers=headers)
            debug_log_api_response('get', r)
            return response_model.from_response(r)


class AsyncAPIBase(APIGenericBase[AsyncClient], APIFactoryMixIn):
    """Base class for all async APIs"""

    async def _post[TResponse: ResponseModelBase](
        self,
        endpoint: APIEndpoint,
        data: RequestModelBase,
        response_model: Type[TResponse],
        *,
        use_api_key: bool = True,
    ) -> TResponse:
        url = self._get_api_url(endpoint)
        headers = self._ensure_api_key(use_api_key, url)

        with self._request_error_handler:
            debug_log_api_request('post', url, data)
            r = await self._http_client.post(url, headers=headers, json=data.dump_for_payload())
            debug_log_api_response('post', r)
            return response_model.from_response(r)

    async def _get[TResponse: ResponseModelBase](
        self,
        endpoint: APIEndpoint,
        response_model: Type[TResponse],
        use_api_key: bool = True,
    ) -> TResponse:
        url = self._get_api_url(endpoint)
        headers = self._ensure_api_key(use_api_key, url)

        with self._request_error_handler:
            debug_log_api_request('get', url)
            r = await self._http_client.get(url, headers=headers)
            resp = response_model.from_response(r)
            debug_log_api_response('get', r)
            return resp


class APINamespaceBase(APINamespaceGenericBase[Client, APIBase], APIFactoryMixIn):
    """Sync API namespace base class"""


class AsyncAPINamespaceBase(APINamespaceGenericBase[AsyncClient, AsyncAPIBase], APIFactoryMixIn):
    """Async API namespace base class"""


api = FactoryDescriptor[APIBase | AsyncAPIBase | APINamespaceBase | AsyncAPINamespaceBase]
