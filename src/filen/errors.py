from enum import StrEnum, auto
from http import HTTPStatus

from httpx import HTTPError, HTTPStatusError, TimeoutException


class FilenError(Exception): ...


class RequestError(FilenError): ...


class RequestHTTPError(RequestError):
    def __init__(self, *args, http_error: HTTPError):
        super().__init__(*args)
        self.http_error = http_error


class RequestHTTPStatusError(RequestHTTPError):
    def __init__(self, *args, http_error: HTTPStatusError):
        super().__init__(*args, http_error=http_error)
        self.status = HTTPStatus(http_error.response.status_code)


class RequestFailedError(RequestError):
    def __init__(self, *args, message: str, code: str):
        super().__init__(*args)
        self.message = message
        self.code = code


class AuthenticationError(RequestFailedError):
    pass


class ResponseParseError(FilenError):
    pass


class CryptographyError(FilenError):
    pass


class NoMasterKeysError(CryptographyError):
    pass


class MetadataEncryptionVersionError(CryptographyError):
    pass


class EncryptError(CryptographyError):
    pass


class DecryptError(CryptographyError):
    pass


class MetadataEncryptError(EncryptError):
    pass


class MetadataDecryptError(DecryptError):
    pass


class FilenErrorCode(StrEnum):
    email_or_password_wrong = auto()
    enter_2fa = auto()


class RequestErrorHandler:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool | None:
        if not exc_type:
            return None

        match exc_val:
            case RequestFailedError():
                match exc_val.code:
                    case FilenErrorCode.email_or_password_wrong | FilenErrorCode.enter_2fa:
                        raise AuthenticationError(
                            exc_val.message,
                            message=exc_val.message,
                            code=exc_val.code,
                        ) from exc_val
                return False

            case ResponseParseError():
                return False

            case HTTPStatusError():
                raise RequestHTTPStatusError(
                    f'{exc_type.__name__}: {exc_val.response.status_code} for {exc_val.request.url}',
                    http_error=exc_val,
                ) from exc_val

            case TimeoutException():
                raise RequestHTTPError(
                    f'{exc_type.__name__}: Timed out for {exc_val.request.url}',
                    http_error=exc_val,
                ) from exc_val

            case HTTPError():
                raise RequestHTTPError(
                    f'{exc_type.__name__}: "{exc_val}" for {exc_val.request.url}',
                    http_error=exc_val,
                ) from exc_val

            case _:
                raise FilenError(*exc_val.args) from exc_val
