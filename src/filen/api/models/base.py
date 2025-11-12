from typing import Any, Self
from datetime import timedelta

from httpx import Response
from pydantic import AliasGenerator, BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from filen.errors import RequestFailedError, ResponseParseError


class SerializationAliasedModel(BaseModel):
    model_config = ConfigDict(alias_generator=AliasGenerator(serialization_alias=to_camel))


class ValidationAliasedModel(BaseModel):
    model_config = ConfigDict(alias_generator=AliasGenerator(validation_alias=to_camel))


class RequestData(SerializationAliasedModel):
    def dump_for_payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, mode='json')


class ResponseData[TData: BaseModel](BaseModel):
    status: bool
    message: str
    code: str
    elapsed: timedelta
    data: TData | list[TData] | None = None

    @classmethod
    def from_response(cls, response: Response) -> Self:
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
