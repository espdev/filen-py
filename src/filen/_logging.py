import json
import logging

from httpx import Response
from pydantic import BaseModel

logger = logging.getLogger('filen')
logger.addHandler(logging.NullHandler())


def debug_log_api_request(method: str, endpoint: str, data: BaseModel | None = None) -> None:
    if logger.isEnabledFor(logging.DEBUG):
        if data:
            logger.debug(
                "%s request to '%s' API, payload:\n%s", method.upper(), endpoint, data.model_dump_json(indent=2)
            )
        else:
            logger.debug("%s request to '%s' API", method.upper(), endpoint)


def debug_log_api_response(method: str, endpoint: str, resp: Response) -> None:
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "%s request to '%s' API completed in %.2fs, response data:\n%s",
            method.upper(),
            endpoint,
            resp.elapsed.total_seconds(),
            json.dumps(resp.json(), indent=2),
        )
