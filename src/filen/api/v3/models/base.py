from typing import Self, Type
from datetime import timedelta
from uuid import UUID

from httpx import Response
from pydantic import AliasGenerator, BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from filen.errors import RequestFailedError, ResponseParseError

from ..._base import RequestModelBase, ResponseModelBase


class SerializationAliasedModel(BaseModel):
    """Model class with serialization to camelCase field names by default

    The model should be used for Filen API request data.
    """

    model_config = ConfigDict(alias_generator=AliasGenerator(serialization_alias=to_camel))


class ValidationAliasedModel(BaseModel):
    """Model class with validation from camelCase field names by default

    The model should be used for Filen API response data.
    """

    model_config = ConfigDict(alias_generator=AliasGenerator(validation_alias=to_camel))


class RequestData(RequestModelBase, SerializationAliasedModel):
    """Base model class for all Filen API request data models"""


class StorageItemUUIDRequestData(RequestData):
    uuid: UUID


class ResponseModel(ResponseModelBase):
    """Model class for Filen API responses without additional data"""

    status: bool
    message: str
    code: str
    elapsed: timedelta

    @classmethod
    def from_response(cls, response: Response) -> Self:
        """Create the model from HTTP client response instance"""

        response.raise_for_status()

        data_raw = response.json()
        data_raw['elapsed'] = response.elapsed

        try:
            response_data = cls.model_validate(data_raw)
        except ValidationError as err:
            raise ResponseParseError(f'API response parsing failed for {response.url} due to: {err}') from err

        if not response_data.status:
            raise RequestFailedError(
                f'API request failed for {response.url} due to: "{response_data.message}" ({response_data.code})',
                message=response_data.message,
                code=response_data.code,
            )

        return response_data


class ResponseData[TData: ValidationAliasedModel](ResponseModel):
    """Genedic model class for Filen API responses with additional data"""

    data: TData | list[TData] | None = None

    def data_as[T](self, model: Type[BaseModel]) -> T:
        return model.model_validate(self.data)
