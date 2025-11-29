from typing import Final
from enum import nonmember

from .._base import APIEndpoint

API_VERSION_PATH: Final = '/v3'


class APIv3Endpoint(APIEndpoint):
    api_path = nonmember(API_VERSION_PATH)
