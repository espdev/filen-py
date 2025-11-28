import json
import logging

from httpx import Response
from pydantic import BaseModel

logger = logging.getLogger('filen')
logger.addHandler(logging.NullHandler())


def debug_log_api_request(method: str, url: str, data: BaseModel | None = None) -> None:
    if logger.isEnabledFor(logging.DEBUG):
        if data:
            logger.debug('%s request to %s, payload:\n%s', method.upper(), url, data.model_dump_json(indent=2))
        else:
            logger.debug('%s request to %s', method.upper(), url)


def debug_log_api_response(method: str, resp: Response) -> None:
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            '%s request to %s completed in %.2fs, response data:\n%s',
            method.upper(),
            resp.url,
            resp.elapsed.total_seconds(),
            json.dumps(resp.json(), indent=2),
        )
