# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

import json
from inspect import signature
from typing import Any, cast
from collections.abc import Awaitable

from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr, Field

from search2o.common.rest_call import RestCall
from search2o.common.exceptions import ShowMessage, error_message
from search2o.common.mylogger import MyLogger
from search2o.common.sensitivestring import SensitiveString
from search2o.execution.allowlist import Allowlist
from search2o.execution.encryptor import Encryptor
from search2o.execution.runtime import Runtime, PROMPT_DECRYPTION_ERROR
from search2o.models.apimodels import ErrorResponseModel, BaseResponseModel, EmptyRequestModel, PagedRequestModel, RequestModel
from search2o.models.configtypes import SystemConfigPart, AgentConfigPart
from search2o.models.schemaobjects import UserRole, UserRoleFacet
from search2o.models.systemconfig import SecretSource, AgentSecretsModel, \
    EncryptionModel, EncryptionSource, SystemConfigModelUnion, AgentConfigModelUnion, \
    ApiConnectionPoolsModel, AgentServerModels, CompileOptions, EvalAllowlistModel, PromptProfileModel

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserItemModel(BaseModel):
    email: EmailStr = Field(..., description="Email of the user.")
    userName: str = Field(..., description="Full name of this user or what the user prefers others to see them as")
    role: UserRole = Field(..., description="This user's role, which determines the actions that the user can execute in the system.")


class UserModel(UserItemModel):
    lastLoginAt: int | None = Field(default=None, description="Last time the user logged in, in epoch milliseconds. Null if the user has never logged in.")


class GetUsersResponseModel(BaseResponseModel):
    users: list[UserItemModel] = Field(..., description="List of users who have access to this system.")
    nextCursor: str | None = Field(default=None, description="Opaque cursor to fetch the next page; pass it back as nextCursor. Null when there are no more results.")
    userCounts: dict[UserRoleFacet, int] = Field(default_factory=dict, description="Number of users holding each role. The size of the current facet is that role's entry, or the sum of all of them for the 'all' facet. This is a snapshot taken when users last changed, so a page can hold one row more or fewer than it implies; nextCursor remains the authority on whether more results exist.")


class GetUserResponseModel(BaseResponseModel):
    user: UserModel


class RotateLicenseResponseModel(BaseResponseModel):
    license: str = Field(..., description="Returns the new license for the system. Old license would continue working for 24 hours or as configured in the system configuration.")


class RotateEncryptionKeyResponseModel(BaseResponseModel):
    rotatedAt: int = Field(..., description="When the new encryption key was generated, in epoch milliseconds.")
    nextRotationAllowedAt: int = Field(..., description="The earliest time the key can be rotated again, in epoch milliseconds.")


class FrozenInfoResponseModel(BaseResponseModel):
    isFrozen: bool = Field(..., description="Whether the system is frozen.")
    frozenBy: str | None = Field(default=None, description="Name of the user who froze the system.")
    frozenAt: int | None = Field(default=None, description="Time in epoch milliseconds of when the system was frozen.")


class GetLicenseResponseModel(BaseResponseModel):
    license: str = Field(..., description="New/Current license key (last 4 characters).")
    licenseCreatedAt: int = Field(..., description="New/Current license created time.")
    licenseCreatedByEmail: str | None = Field(default=None, description="Email of the user that created the current license.")
    licenseCreatedByName: str | None = Field(default=None, description="Name of the user that created the current license.")
    oldLicense: str | None = Field(default=None, description="Old license key, if not expired (last 4 characters).")
    oldLicenseCreatedByEmail: str | None = Field(default=None, description="Email of the user that created the old license.")
    oldLicenseCreatedByName: str | None = Field(default=None, description="Name of the user that created the old license.")
    oldLicenseExpiry: int | None = Field(default=None, description="Expiration time in epoch milliseconds of the old license key if it has not expired.")
    oldLicenseCreatedAt: int | None = Field(default=None, description="Old license created time")


@admin_router.post("/getLicenseInfo", response_model=GetLicenseResponseModel,
                   summary="Get license key information",
                   description="Shows the current license key and, during a rotation, the old key and when it expires. Keys are shown by their last four characters only.",
                   )
async def getLicenseInfo(item: EmptyRequestModel, request: Request)-> GetLicenseResponseModel:
    ret = await RestCall.passthrough(request,  item.model_dump())
    return GetLicenseResponseModel.model_validate(ret)

class RotateLicenseModel(RequestModel):
    oldLicenseExpiry: int = Field(..., description="Time at which the old license key expires, in epoch milliseconds. Until this time, both the old and new license keys will work. After this time, only the new license will work. Servers need to be restarted with the new license, before this time.")

@admin_router.post("/rotateLicense", response_model=RotateLicenseResponseModel,
                   summary="Change license key",
                   description="This call is used to periodically rotate the license key of the system. The old license will still stay active until the time specified here. The servers must be restarted within this duration, with the new license key.",
                   )
async def rotateLicense(item: RotateLicenseModel, request: Request)-> RotateLicenseResponseModel:
    ret = await RestCall.passthrough(request,  item.model_dump())
    return RotateLicenseResponseModel.model_validate(ret)


@admin_router.post("/cancelRotateLicense", response_model=BaseResponseModel, summary="Cancel pending license rotation", description="This will cancel a pending license rotation, if the old/current license key has not expired. The new license key will be immediately invalid.")
async def cancelRotateLicense(item: EmptyRequestModel, request: Request)-> BaseResponseModel:
    ret = await RestCall.passthrough(request,  item.model_dump())
    return BaseResponseModel.model_validate(ret)


@admin_router.post("/rotateEncryptionKey", response_model=RotateEncryptionKeyResponseModel,
                   summary="Rotate the encryption key",
                   description="Rotates the account's encryption key. New data is encrypted with the new key, while data encrypted with earlier keys stays readable. Agent servers keep using the previous key until they are restarted. The key can be rotated at most once every 90 days.")
async def rotateEncryptionKey(item: EmptyRequestModel, request: Request)-> RotateEncryptionKeyResponseModel:
    ret = await RestCall.passthrough(request,  item.model_dump())
    return RotateEncryptionKeyResponseModel.model_validate(ret)

class AddUsersModel(RequestModel):
    emails: list[EmailStr] = Field(..., min_length=1, max_length=25, title="Emails", description="Emails of users to add to the system.")
    role: UserRole
    sendEmail: bool = Field(default=True, title="Send email", description="Whether to email an invitation to each added user. When false, the users are added but no email is sent to them.")

class AddUsersResponseModel(BaseResponseModel):
    pass


@admin_router.post("/addUsers", response_model=AddUsersResponseModel,
                   summary="Add users", description="Adds a list of users to the system with the role provided.")
async def addUsers(item: AddUsersModel, request: Request)-> AddUsersResponseModel:
    ret = await RestCall.passthrough(request,  item.model_dump())
    return AddUsersResponseModel.model_validate(ret)

class GetUsersModel(PagedRequestModel):
    limit: int = Field(default=10, ge=1, le=5000, description="The maximum number of results to return.")
    roleFacet: UserRoleFacet = UserRoleFacet.all

@admin_router.post("/getUsers", response_model=GetUsersResponseModel, summary="Get users", description="This call fetches all the users in the system.")
async def getUsers(item: GetUsersModel, request: Request)-> GetUsersResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return GetUsersResponseModel.model_validate(ret)

class GetUserModel(RequestModel):
    email: EmailStr


@admin_router.post("/getUser", response_model=GetUserResponseModel, summary="Get one user", description="This call fetches a single user in the system.")
async def getUser(item: GetUserModel, request: Request)-> GetUserResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return GetUserResponseModel.model_validate(ret)


class DeleteUsersModel(RequestModel):
    emails: list[EmailStr] = Field(..., min_length=1, max_length=25, description="Emails of the users to delete, up to 25 at a time.")


@admin_router.post("/deleteUsers", response_model=BaseResponseModel, summary="Delete users", description="Deletes users from the system. Once deleted, a user cannot be recovered. Users with a role of owner can be deleted only by another owner.")
async def deleteUsers(item: DeleteUsersModel, request: Request)-> BaseResponseModel:
    ret = await RestCall.passthrough(request,  item.model_dump())
    return BaseResponseModel.model_validate(ret)

class UpdateRoleModel(RequestModel):
    emails: list[EmailStr] = Field(..., min_length=1, max_length=25, description="Emails of the users whose role is being changed, up to 25 at a time.")
    role: UserRole


@admin_router.post("/updateRole", response_model=BaseResponseModel, summary="Modify a user's role", description="Modifies a user's role. Users can run searches and execute agents. Developers can draft and publish agents and descriptors. They can also change the environment configuration. Administrators can add users and change the system configuration. Owners can access billing information. Each role is a superset of the one below it. Only owners can assign the role of an owner to a user.")
async def updateRole(item: UpdateRoleModel, request: Request)-> BaseResponseModel:
    ret = await RestCall.passthrough(request,  item.model_dump())
    return BaseResponseModel.model_validate(ret)


@admin_router.post("/freeze", response_model=BaseResponseModel, summary="Freeze system",
                   description="This call can be made to stop any changes to agents or descriptors in the system. No new agents can be published either. Developers can still create draft agents and run them.")
async def freeze(item: EmptyRequestModel, request: Request)-> BaseResponseModel:
    ret = await RestCall.passthrough(request,  item.model_dump())
    return BaseResponseModel.model_validate(ret)


@admin_router.post("/unfreeze", response_model=BaseResponseModel, summary="Unfreeze system",
                   description="Unfreezes the system.")
async def unfreeze(item: EmptyRequestModel, request: Request)-> BaseResponseModel:
    ret = await RestCall.passthrough(request,  item.model_dump())
    return BaseResponseModel.model_validate(ret)


@admin_router.post("/getFrozenInfo", response_model=FrozenInfoResponseModel, summary="Get information about whether the system is frozen",
                   description="If the system is frozen, returns who froze it and when.")
async def getFrozenInfo(item: EmptyRequestModel, request: Request)-> FrozenInfoResponseModel:
    ret = await RestCall.passthrough(request,  item.model_dump())
    return FrozenInfoResponseModel.model_validate(ret)


class ConfigPartRequestModel(RequestModel):
    part: SystemConfigPart

class ConfigPartResponseModel(BaseResponseModel):
    configValue: SystemConfigModelUnion
    configVersion: int
    lastUpdatedByName: str
    lastUpdatedByEmail: str
    configError: str | None = None


@admin_router.post("/getSystemConfigPart", response_model=ConfigPartResponseModel, summary="Get a configuration", description="Gets one of the configurations. See the documentation for more details.")
async def getSystemConfigPart(item: ConfigPartRequestModel, request: Request)-> ConfigPartResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    model = ConfigPartResponseModel.model_validate(ret)
    if item.part == SystemConfigPart.secrets:
        await _decrypt_secrets(model.configValue, request)
    return model


class AgentConfigPartRequestModel(RequestModel):
    part: AgentConfigPart

class AgentConfigPartRowModel(BaseModel):
    configValue: AgentConfigModelUnion
    configVersion: int
    lastUpdatedByName: str
    lastUpdatedByEmail: str
    usedBy: list[str] = []

class AgentConfigPartResponseModel(BaseResponseModel):
    configParts: list[AgentConfigPartRowModel]


@admin_router.post("/getAgentConfigPart", response_model=AgentConfigPartResponseModel, summary="Get a collection configuration", description="Gets one of the configurations. See the documentation for more details.")
async def getAgentConfigPart(item: AgentConfigPartRequestModel, request: Request)-> AgentConfigPartResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    model = AgentConfigPartResponseModel.model_validate(ret)
    if item.part == AgentConfigPart.prompt:
        for row in model.configParts:
            await _decrypt_prompt_profile(cast(PromptProfileModel, row.configValue), request)
    return model



async def _decrypt_prompt_profile(profile: PromptProfileModel, request: Request):
    for field in ("system", "user"):
        text = getattr(profile, field)
        if text:
            try:
                setattr(profile, field, await Encryptor.decrypt_query(request, text))
            except Exception as e:
                MyLogger.error(f"Could not decrypt the {field} prompt of profile {profile.name!r}: {SensitiveString.safe_text(error_message(e))}")
                setattr(profile, field, PROMPT_DECRYPTION_ERROR)


async def _encrypt_prompt_profile(profile: PromptProfileModel, request: Request):
    for field in ("system", "user"):
        text = getattr(profile, field)
        if text:
            setattr(profile, field, await Encryptor.encrypt_query(request, text))


class UpdateSystemConfigPartModel(RequestModel):
    configValue: SystemConfigModelUnion
    configVersion: int

class UpdateConfigPartResponseModel(BaseResponseModel):
    configVersion: int

async def api_connection_pool_names(request: Request) -> list[str]:
    ret = ConfigPartResponseModel.model_validate(
        await RestCall.call_method(request, "getSystemConfigPart", {"part": SystemConfigPart.apiConnectionPools}))
    return sorted(cast(ApiConnectionPoolsModel, ret.configValue).pools)


def _check_connection_pool(name: str, pool_names: list[str]):
    if name not in pool_names:
        raise ShowMessage(f"API connection pool {name!r} is not defined. It must be one of: {', '.join(pool_names)}.")


_REWRITE_PROBE = object()

_REWRITE_TRIALS = {"add": (7, 3), "sub": (7, 3), "mult": (7, 3), "div": (7, 3), "floordiv": (7, 3),
                   "mod": (7, 3), "pow": (2, 3), "lshift": (1, 2), "rshift": (8, 2)}


async def _rewrite_problem(op: str, name: str, available: dict[str, Any]) -> str:
    if name not in available:
        return "is not in the allowlist"
    fn = available[name]
    if not callable(fn):
        return "is not a function"
    try:
        sig = signature(fn)
    except (ValueError, TypeError):
        sig = None
    if sig is not None:
        try:
            sig.bind(_REWRITE_PROBE, _REWRITE_PROBE)
        except TypeError:
            return "does not take two values"
    trial = _REWRITE_TRIALS.get(op)
    if trial is None:
        return ""
    try:
        result = fn(*trial)
        if isinstance(result, Awaitable):
            await result
    except Exception as e:
        return f"failed a trial run with {trial[0]} and {trial[1]}: {SensitiveString.safe_text(error_message(e))}"
    return ""


async def _check_rewrite_targets(model: CompileOptions, request: Request):
    wanted = {op: action.rewrite for op, action in model.operators if action.allow and action.rewrite}
    if not wanted:
        return
    ret = ConfigPartResponseModel.model_validate(
        await RestCall.call_method(request, "getSystemConfigPart", {"part": SystemConfigPart.allowlist}))
    available = Allowlist(cast(EvalAllowlistModel, ret.configValue)).eval_allowlist
    problems = []
    for op, name in wanted.items():
        problem = await _rewrite_problem(op, name, available)
        if problem:
            problems.append(f"{name!r} for the {op} operator {problem}")
    if problems:
        raise ShowMessage(f"A rewrite function must be a function in the expression allowlist that works "
                          f"on the operator's two values: {', '.join(problems)}.")


@admin_router.post("/updateSystemConfigPart", response_model=UpdateConfigPartResponseModel, summary="Updates part of the configuration", description="Updates part of the configuration. See the documentation for more details.")
async def updateSystemConfigPart(item: UpdateSystemConfigPartModel, request: Request)-> UpdateConfigPartResponseModel:
    if item.configValue.type == SystemConfigPart.servers:
        pool_names = await api_connection_pool_names(request)
        for server in item.configValue.servers.values():
            _check_connection_pool(server.cloudPoolName, pool_names)
    elif item.configValue.type == SystemConfigPart.apiConnectionPools:
        await _check_pools_not_in_use(item.configValue, request)
    elif item.configValue.type == SystemConfigPart.operators:
        for _op, action in item.configValue.operators:
            if not action.allow:
                action.rewrite = ""
        await _check_rewrite_targets(item.configValue, request)
    elif item.configValue.type == SystemConfigPart.allowlist:
        al = Allowlist(item.configValue)
        if al.errors:
            return UpdateConfigPartResponseModel(success=False, error=ErrorResponseModel(message=f"Allowlist has errors: {'\n'.join(al.errors)}"), configVersion=0)
    elif item.configValue.type == SystemConfigPart.secrets:
        await _validate_secrets_update(item.configValue, request)
    elif item.configValue.type == SystemConfigPart.encryption:
        await _validate_encryption(item.configValue, request)

    ret = await RestCall.passthrough(request, item.model_dump())
    uec = UpdateConfigPartResponseModel.model_validate(ret)
    return uec


async def _check_pools_not_in_use(model: BaseModel, request: Request):
    removed = set(await api_connection_pool_names(request)) - set(cast(ApiConnectionPoolsModel, model).pools)
    if not removed:
        return
    users: dict[str, list[str]] = {}

    def add_user(pool_name: str, used_by: str):
        if pool_name in removed:
            users.setdefault(pool_name, []).append(used_by)

    servers = ConfigPartResponseModel.model_validate(
        await RestCall.call_method(request, "getSystemConfigPart", {"part": SystemConfigPart.servers}))
    for name, server in cast(AgentServerModels, servers.configValue).servers.items():
        add_user(server.cloudPoolName, f"agent server {name!r}")
    for part, label in ((AgentConfigPart.llm, "LLM profile"), (AgentConfigPart.api, "API profile")):
        profiles = AgentConfigPartResponseModel.model_validate(
            await RestCall.call_method(request, "getAgentConfigPart", {"part": part}))
        for config_part in profiles.configParts:
            add_user(config_part.configValue.connectionPoolName, f"{label} {config_part.configValue.name!r}")

    if users:
        details = "; ".join(f"{pool!r} is used by {', '.join(sorted(used_by))}" for pool, used_by in sorted(users.items()))
        raise ShowMessage(f"An API connection pool that is in use cannot be deleted: {details}.")


async def _validate_encryption(model: BaseModel, request: Request):
    em = cast(EncryptionModel, model)
    if em.encryptionSource == EncryptionSource.client:
        if em.keyFunction:
            rs = Runtime.current()
            kf = rs.allowlist.eval_allowlist.get(em.keyFunction)
            if kf:
                if em.keys:
                    ek = em.keys[-1]
                    if '|' in ek.keyName:
                        raise ShowMessage(f"{ek.keyName} cannot contain '|'")
                    try:
                        k_awaitable = kf(ek.keyName)
                    except Exception:
                        raise ShowMessage(f"{em.keyFunction} threw an exception when called with {ek.keyName}")

                    if not isinstance(k_awaitable, Awaitable):
                        raise ShowMessage(f"{em.keyFunction} must be async")
                    try:
                        k = await k_awaitable
                    except Exception:
                        raise ShowMessage(f"{em.keyFunction} threw an exception when called with {ek.keyName}")
                    if not isinstance(k, bytes):
                        raise ShowMessage(f"{em.keyFunction} must return bytes")
                    if not Encryptor.is_valid_key(k):
                        raise ShowMessage(f"{em.keyFunction} did not return a valid AESGCM key for {ek.keyName}")
            else:
                raise ShowMessage(f"{em.keyFunction} is not found in the allowlist.")
        else:
            raise ShowMessage("Must specify a key function name. See the documentation.")


async def _validate_secrets_update(model: BaseModel, request: Request):
    secrets_model = cast(AgentSecretsModel, model)
    if secrets_model.secretSource == SecretSource.hosted:
        rs = Runtime.current()
        if rs.encryption_model.encryptionSource != EncryptionSource.client:
            raise ShowMessage("To use hosted secrets, you should first set up end-to-end encryption. See the documentation for more details.")
        if secrets_model.secrets:
            ss = json.dumps(secrets_model.secrets)
            try:
                secrets_model.secretsEncrypted = await Encryptor.encrypt(request, rs, ss)
                secrets_model.secrets = None
            except Exception:
                raise ShowMessage("Error encrypting secrets.")
        else:
            secrets_model.secretsEncrypted = None
            secrets_model.secrets = None
    else:
        secrets_model.secretsEncrypted = None
        secrets_model.secrets = None

async def _decrypt_secrets(model: BaseModel, request: Request):
    secrets_model = cast(AgentSecretsModel, model)
    if secrets_model.secretSource == SecretSource.hosted:
        if secrets_model.secretsEncrypted:
            rs = Runtime.current()
            try:
                decrypted = await Encryptor.decrypt(request, rs, secrets_model.secretsEncrypted)
            except Exception:
                raise ShowMessage("Error decrypting secrets.")
            if decrypted:
                secrets_model.secrets = json.loads(decrypted)
            secrets_model.secretsEncrypted = None

class UpsertAgentConfigPartModel(RequestModel):
    configValue: AgentConfigModelUnion
    configVersion: int

class UpsertAgentConfigPartResponseModel(BaseResponseModel):
    configVersion: int

@admin_router.post("/upsertAgentConfigPart", response_model=UpsertAgentConfigPartResponseModel, summary="Add or update a collection config object", description="Add or update one of the objects in a collection configuration. See the documentation for more details.")
async def upsertAgentConfigPart(item: UpsertAgentConfigPartModel, request: Request)-> UpsertAgentConfigPartResponseModel:
    if item.configValue.type in (AgentConfigPart.llm, AgentConfigPart.api):
        _check_connection_pool(item.configValue.connectionPoolName, await api_connection_pool_names(request))
    elif item.configValue.type == AgentConfigPart.prompt:
        await _encrypt_prompt_profile(item.configValue, request)
    ret = await RestCall.passthrough(request,  item.model_dump())
    uec = UpsertAgentConfigPartResponseModel.model_validate(ret)
    return uec

class DeleteAgentConfigPartModel(RequestModel):
    part: AgentConfigPart
    name: str
    configVersion: int

@admin_router.post("/deleteAgentConfigPart", response_model=BaseResponseModel, summary="Delete a collection config object", description="Deletes one of the elements in a collection configuration. See the documentation for more details.")
async def deleteAgentConfigPart(item: DeleteAgentConfigPartModel, request: Request)-> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)

class LlmAdaptersResponseModel(BaseResponseModel):
    adapters: dict[str, str]


@admin_router.post("/getLlmAdapters", response_model=LlmAdaptersResponseModel, summary="Get the LLM adapters defined in the system", description="Gets a dict of LLM adapter names and their descriptions. LLM configs should use one of the adapters here.")
async def getLlmAdapters(item: EmptyRequestModel, request: Request) -> LlmAdaptersResponseModel:
    await RestCall.call_method(request, "checkRole", {"role": UserRole.developer})
    return LlmAdaptersResponseModel(success=True, adapters=Runtime.current().llm_connections.adapter_names)
