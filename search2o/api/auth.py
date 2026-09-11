# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from fastapi import APIRouter, Request, Response
from pydantic import EmailStr, Field, JsonValue

from search2o.common.docsweb import DocsWeb, DocsWebType
from search2o.common.exceptions import ShowMessage
from search2o.common.rest_call import RestCall
from search2o.execution.runtime import Runtime
from search2o.models.configtypes import AuthMethod
from search2o.models.systemconfig import CookieModel
from search2o.models.apimodels import BaseResponseModel, RequestModel

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


def _connect_page() -> str:
    from search2o.config.config import Config
    conf = Config.init_model.agentServer
    page = conf.connectPageUrl.strip()
    if page.startswith("http://") or page.startswith("https://"):
        return page.rstrip("/")
    if not conf.uiPath:
        raise ShowMessage("No connect page is configured, so there is nowhere for a user to approve this request.")
    base = f"/{conf.uiPath.strip('/')}"
    return f"{base}/{page.strip('/')}" if page else f"{base}/"


class LogoutResponseModel(BaseResponseModel):
    cookie: CookieModel


class LoginModel(RequestModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class LoginResponseModel(BaseResponseModel):
    mustChangePassword: bool = Field(False, description="Specifies whether the user must change their password. This would be true when the user logs in for the first time or when the user forgets their password.")
    cookie: dict[str, JsonValue] = Field(default_factory=dict, description="Cookie authentication information")


class ScriptLoginResponseModel(BaseResponseModel):
    token: str | None = Field(default=None, description="Token that identifies the user for script access. This token is valid for 1 hour or as set in the system configuration.")
    tokenType: str = Field(default="", description="Type of token. Typically its value is 'Bearer'.")
    expiresIn: int = Field(default=0, description="Time in seconds until the token expires.")


class EmailCodeModel(RequestModel):
    email: EmailStr


class CreatePasswordWithEmailCodeModel(RequestModel):
    email: EmailStr
    code: str
    newPassword: str = Field(..., min_length=6, max_length=128)


class AccountNameResponseModel(BaseResponseModel):
    accountName: str = Field(default="", description="Name of this account. Displayed in the UI.")
    authMethod: AuthMethod = Field(default=AuthMethod.builtin, title="Sign-in method", description="How users of this account sign in, so the sign-in screen knows what to offer before anyone types.")


class PasswordHelpResponseModel(BaseResponseModel):
    passwordHelp: str = Field(default="", description="Help text describing the password requirements, shown in the UI when a user creates a password.")


@auth_router.post("/login", response_model=LoginResponseModel,
                  summary="Login to the system",
                  description="This is used to log in from the browser. It sets a cookie to maintain a login session.",
                  openapi_extra={"security": []})
async def login(item: LoginModel, request: Request, response: Response) -> LoginResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    lrm = LoginResponseModel.model_validate(ret)
    cookie = lrm.cookie
    if lrm.success and cookie:
        response.set_cookie(**cookie)
    return lrm


@auth_router.post("/scriptLogin", response_model=ScriptLoginResponseModel,
                  summary="Script login to the system",
                  description="To use scripts to access this API, one needs a token. This call is used to "
                              "generate that authorization token. By default, this token is valid for one hour. "
                              "This can be changed in the system configuration.",
                  openapi_extra={"security": []})
async def scriptLogin(item: LoginModel, request: Request) -> ScriptLoginResponseModel:
    d = await RestCall.passthrough(request, item.model_dump())
    return ScriptLoginResponseModel.model_validate(d)


@auth_router.post("/emailCode", response_model=BaseResponseModel,
                  summary="Email a code to reset a password",
                  description="Call to reset one's password. The system sends an email with a code that can be "
                              "used to create a new password.",
                  openapi_extra={"security": []})
async def emailCode(item: EmailCodeModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


@auth_router.post("/createPasswordWithEmailCode", response_model=BaseResponseModel,
                  summary="Create a password with an email code",
                  description="When the user receives a code in the email to reset the password, they enter it "
                              "on the UI. The UI then prompts them to create a new password.",
                  openapi_extra={"security": []})
async def createPasswordWithEmailCode(item: CreatePasswordWithEmailCodeModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


@auth_router.post("/getAccountName", response_model=AccountNameResponseModel,
                  summary="Gets the account name",
                  description="Gets the account name. It is answered by the agent server itself, so it "
                              "also confirms that the server is up. Anyone can call this.",
                  openapi_extra={"security": []})
async def getAccountName(request: Request) -> AccountNameResponseModel:
    from search2o.config.config import Config
    return AccountNameResponseModel(accountName=Config.init_model.accountName, authMethod=Runtime.auth_method, success=True)


@auth_router.post("/getPasswordHelp", response_model=PasswordHelpResponseModel,
                  summary="Gets the password help text",
                  description="Gets the help text that describes what a password must contain. It is shown in "
                              "the UI wherever a user creates or changes a password. Anyone can call this.",
                  openapi_extra={"security": []})
async def getPasswordHelp() -> PasswordHelpResponseModel:
    return PasswordHelpResponseModel(passwordHelp=Runtime.password_help, success=True)


class GetDocsWebModel(RequestModel):
    dtype: DocsWebType = Field(..., title="Document type", description="Which dynamic document to fetch.")


class GetDocsWebResponseModel(BaseResponseModel):
    dtype: DocsWebType = Field(..., title="Document type", description="The document that was fetched.")
    version: str = Field(..., title="Version", description="The version of the document that was served.")
    document: JsonValue = Field(..., title="Document", description="The document contents.")


@auth_router.post("/getDocsWeb", response_model=GetDocsWebResponseModel,
                  summary="Gets a dynamic UI document",
                  description="Fetches a document the UI needs at runtime, such as the agent schema, the "
                              "evaluation form or the UI text. The agent server checks for the latest version "
                              "and serves it from an in-memory cache. Anyone can call this.",
                  openapi_extra={"security": []})
async def getDocsWeb(item: GetDocsWebModel) -> GetDocsWebResponseModel:
    version, document = await DocsWeb.get(item.dtype)
    return GetDocsWebResponseModel(dtype=item.dtype, version=version, document=document, success=True)


class StartConnectModel(RequestModel):
    clientName: str = Field(..., min_length=1, max_length=80, title="Client name", description="What the approval page shows as the thing asking for access, such as the name of a chat workspace.")


class StartConnectResponseModel(BaseResponseModel):
    connectId: str = Field(default="", title="Connect id", description="Identifies this connect request. It goes in the link the user opens.")
    connectSecret: str = Field(default="", title="Connect secret", description="Returned once, to the caller only. It is what authorizes getConnectToken, so it must not be shown to the user or put in a link.")
    connectUrl: str = Field(default="", title="Connect URL", description="The address of the page the user opens to approve this request. It is the configured connect page, which may be hosted anywhere, with this request's identifier added.")
    userCode: str = Field(default="", title="User code", description="Short code to show the user alongside the link, so they can check it matches the one on the approval page before approving.")
    expiresIn: int = Field(default=0, title="Expires in", description="Seconds until this request stops being usable.")
    pollIntervalSeconds: int = Field(default=0, title="Poll interval", description="How often getConnectToken may be called. Polling faster is refused.")


class ConnectIdModel(RequestModel):
    connectId: str = Field(..., min_length=1, max_length=64, title="Connect id", description="The connect request being read or acted on.")


class ConnectRequestResponseModel(BaseResponseModel):
    clientName: str = Field(default="", title="Client name", description="What is asking for access, as supplied when the request was created. It is not verified, which is what the code is for.")
    userCode: str = Field(default="", title="User code", description="The code the user checks against the one shown where they started.")
    expiresIn: int = Field(default=0, title="Expires in", description="Seconds until this request stops being usable.")


class GetConnectTokenModel(RequestModel):
    connectId: str = Field(..., min_length=1, max_length=64, title="Connect id", description="The connect request to collect.")
    connectSecret: str = Field(..., min_length=1, max_length=128, title="Connect secret", description="The secret returned when the request was created. It is what authorizes this call.")


class GetConnectTokenResponseModel(BaseResponseModel):
    status: str = Field(default="", title="Status", description="One of pending, approved, denied or expired.")
    token: str | None = Field(default=None, title="Token", description="The token to use as a Bearer credential. Set only when the status is approved, and returned only once.")
    tokenType: str = Field(default="", title="Token type", description="Type of token. Typically its value is 'Bearer'.")
    expiresIn: int = Field(default=0, title="Expires in", description="Seconds until the token expires, or 0 when it does not expire.")
    userEmail: str = Field(default="", title="User email", description="The user who approved the request.")
    userName: str = Field(default="", title="User name", description="The name of the user who approved the request.")


@auth_router.post("/startConnect", response_model=StartConnectResponseModel,
                  summary="Start connecting an integration to a user",
                  description="Creates a request for a user to approve in the browser, so an integration can act as them without ever handling their password. Anyone can call this: an unapproved request grants nothing.",
                  openapi_extra={"security": []})
async def startConnect(item: StartConnectModel, request: Request) -> StartConnectResponseModel:
    page = _connect_page()
    ret = await RestCall.passthrough(request, item.model_dump())
    scm = StartConnectResponseModel.model_validate(ret)
    if scm.connectId:
        scm.connectUrl = f"{page}{'&' if '?' in page else '?'}c={scm.connectId}"
    return scm


@auth_router.post("/getConnectRequest", response_model=ConnectRequestResponseModel,
                  summary="Read a connect request",
                  description="What the approval page shows before the user decides. It returns only what is already on their screen or where they started, and nothing about any user.",
                  openapi_extra={"security": []})
async def getConnectRequest(item: ConnectIdModel, request: Request) -> ConnectRequestResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return ConnectRequestResponseModel.model_validate(ret)


@auth_router.post("/getConnectToken", response_model=GetConnectTokenResponseModel,
                  summary="Collect the token for an approved connect request",
                  description="Called repeatedly by the integration until the user has approved, and then once more to receive the token. The secret is what authorizes it, and the request is used up once the token is handed over.",
                  openapi_extra={"security": []})
async def getConnectToken(item: GetConnectTokenModel, request: Request) -> GetConnectTokenResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return GetConnectTokenResponseModel.model_validate(ret)
@auth_router.post("/logout", response_model=BaseResponseModel,
                 summary="Log out of the system", description="This is used to log out of the system from the UI.")
async def logout(request: Request, response: Response) -> BaseResponseModel:
    d = await RestCall.passthrough(request, {})
    model = LogoutResponseModel.model_validate(d)
    if model.success:
        response.delete_cookie(key=model.cookie.key, domain=model.cookie.domain, path=model.cookie.path)
    return model
