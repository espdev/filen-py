from typing import Annotated, Final, Literal

from pydantic import BaseModel, EmailStr, StringConstraints

from filen.config import AuthVersion

from .base import RequestData, ResponseData, ValidationAliasedModel

NO_2FA_CODE_PLACEHOLDER: Final = 'XXXXXX'


class AuthInfoRequestData(RequestData):
    email: EmailStr


class AuthInfo(ValidationAliasedModel):
    email: EmailStr
    salt: str
    id: int
    auth_version: AuthVersion


class AuthInfoResponseData(ResponseData[AuthInfo]): ...


TwoFactorCodeStr = Annotated[str, StringConstraints(pattern=r'^[0-9]{6}$')]


class LoginRequestData(RequestData):
    email: EmailStr
    password: str
    two_factor_code: TwoFactorCodeStr | Literal['XXXXXX'] = NO_2FA_CODE_PLACEHOLDER
    auth_version: AuthVersion = AuthVersion.v2


class LoginData(ValidationAliasedModel):
    api_key: str
    master_keys: str
    public_key: str
    private_key: str
    dek: str | None


class LoginResponseData(ResponseData[LoginData]): ...


class UserKeys(BaseModel):
    api_key: str
    master_keys: list[str]
    public_key: str
    private_key: str
    dek: str | None
