# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from enum import StrEnum, auto
from typing import Literal, Annotated, TypeAlias, Self

from pydantic import BaseModel, Field, JsonValue, PrivateAttr, AfterValidator, model_validator

from .configtypes import SystemConfigPart, AgentConfigPart, AuthMethod, ProfileName, TagFilter


ProfileDoc = Annotated[str, Field(default="", title="Documentation", description="Documentation of what this profile is used for. This field is optional. It can be useful in generating agent definitions.", max_length=500)]

class NamedBaseModel(BaseModel):
    name: ProfileName = Field(..., title="Name", description="The name this profile is referred to by, in agents and in other configuration.")
    doc: ProfileDoc = Field(..., title="Notes", description="Free-text notes about this profile, for whoever maintains the configuration.")

class TimeoutModel(BaseModel):
    connect: float = Field(default=10.0, title="Connection timeout (seconds)", description="How long to wait to establish the TCP/TLS connection.")
    read: float = Field(default=300.0, title="Read timeout (seconds)", description="How long to wait for response bytes.")
    write: float = Field(default=30.0, title="Write timeout (seconds)", description="How long to wait while sending the request body.")
    pool: float = Field(default=10.0, title="Pool timeout (seconds)", description="How long to wait for a free connection from the pool.")

class ApiConnectionPoolModel(BaseModel):
    maxConnections: int = Field(
        default=20,
        title="Max connections",
        description="The most connections this pool opens at once.",
    )
    maxKeepaliveConnections: int = Field(
        default=10,
        title="Max keep-alive connections",
        description="The most idle connections kept open for reuse.",
    )
    keepaliveExpiry: int = Field(
        default=60,
        title="Keep-alive expiry (seconds)",
        description="How long an idle connection is kept before it is closed.",
    )
    timeout: TimeoutModel = Field(default_factory=TimeoutModel, title="Timeouts", description="The connect, read, write and pool timeouts for calls made through this pool.")

class ApiConnectionPoolsModel(BaseModel):
    type: Literal[SystemConfigPart.apiConnectionPools] = Field(default=SystemConfigPart.apiConnectionPools, title="Config part", description="Identifies which configuration part this is.")
    pools: dict[ProfileName, ApiConnectionPoolModel] = Field(default_factory=dict, title="Connection pools",
                                                     description="The connection pools available to the whole system, keyed by name. The pool named 'default' cannot be deleted.")

    @model_validator(mode="after")
    def validate_default_server(self) -> Self:
        if "default" not in self.pools:
            self.pools["default"] = ApiConnectionPoolModel()
        return self

class ApiServerModel(NamedBaseModel):
    type: Literal[AgentConfigPart.api] = Field(default=AgentConfigPart.api, title="Config part", description="Identifies which configuration part this is.")
    url: str = Field(
        ...,
        title="Server URL",
        description="The base URL of this API server.",
    )
    headers: dict[str, JsonValue] = Field(
        default_factory=dict,
        title="Server headers",
        description="Headers sent with every call, including any authentication.",
    )
    connectionPoolName: ProfileName = Field(default="default", title="Connection pool", description="The connection pool used for calls to this server.")


class DbConnectionPool(BaseModel):
    isolationLevel: Literal["READ COMMITTED", "AUTOCOMMIT"] | None = Field(
        default=None,
        title="Isolation level",
        description="The transaction isolation level, such as 'READ COMMITTED' or 'AUTOCOMMIT'. Leave unset for the driver's default."
    )
    poolSize: int = Field(
        default=3,
        title="Pool size",
        description="The number of connections kept open in the pool."
    )
    poolTimeout: int = Field(
        default=5,
        title="Pool timeout (seconds)",
        description="How long to wait for a free connection before failing.",
    )
    poolRecycle: int = Field(
        default=-1,
        title="Pool recycle (seconds)",
        description="Close and reopen a connection after this many seconds. -1 disables recycling."
    )
    poolPrePing: bool = Field(
        default=False,
        title="Pre-ping connections",
        description="Test a connection before using it, so stale ones are not handed out.",
    )
    maxOverflow: int = Field(
        default=10,
        title="Max overflow",
        description="How many extra connections may be opened above the pool size during a burst.",
    )
    connectArgs: dict[str, JsonValue] = Field(
        default_factory=dict,
        title="Driver arguments",
        description="Arguments passed straight through to the database driver.",
    )


class DbConnectionModel(NamedBaseModel):
    type: Literal[AgentConfigPart.db] = Field(default=AgentConfigPart.db, title="Config part", description="Identifies which configuration part this is.")
    connectionString: str | None = Field(default=None, title="Connection string", description="The database connection string. When set here, an agent cannot override it.")
    connectionPool: DbConnectionPool = Field(default_factory=DbConnectionPool, title="Connection pool", description="Pool settings for connections to this database.")

def not_reserved_function(value: str) -> str:
    if value == "function":
        raise ValueError("MCP cannot be named 'function' to not conflict with agent functions used in tool calls.")
    return value


SafeMcpName = Annotated[
    str,
    Field(
        max_length=16,
        pattern=r"^[A-Za-z][A-Za-z0-9]{1,15}$",
    ),
    AfterValidator(not_reserved_function),
]


class McpServerModel(BaseModel):
    type: Literal[AgentConfigPart.mcp] = Field(default=AgentConfigPart.mcp, title="Config part", description="Identifies which configuration part this is.")
    name: SafeMcpName = Field(..., title="Name", description="The name agents use to refer to this MCP server.")
    doc: ProfileDoc = Field(..., title="Notes", description="Free-text notes about this server, for whoever maintains the configuration.")
    url: str = Field(
        ...,
        title="Server URL",
        description="The URL of the MCP server.",
    )
    headers: dict[str, JsonValue] = Field(
        default_factory=dict,
        title="Server headers",
        description="Headers sent with every call, including any authentication.",
    )
    retryableErrorCodes: list[int] = Field(
        default_factory=lambda: [-32600, -32601, -32602],
        title="Retryable error codes",
        description="MCP (JSON-RPC) error codes treated as recoverable: the error is given back to the LLM to correct itself instead of failing the agent. Defaults to -32600 (invalid request), -32601 (method not found) and -32602 (invalid params).",
    )

class ModelDetails(BaseModel):
    inputText: float = Field(default=0, title="Input text", description="Price per million input text tokens.")
    outputText: float = Field(default=0, title="Output text", description="Price per million output text tokens.")
    inputImage: float = Field(default=0, title="Input image", description="Price per million input image tokens.")
    outputImage: float = Field(default=0, title="Output image", description="Price per million output image tokens.")

class LlmModel(NamedBaseModel):
    type: Literal[AgentConfigPart.llm] = Field(default=AgentConfigPart.llm, title="Config part", description="Identifies which configuration part this is.")
    vendor: str = Field(default="openai", title="Vendor", description="The LLM vendor. Reports are organized under this name.")
    adapter: str = Field(default="openai", title="Adapter", description="The adapter class that connects to this LLM. It must implement the LlmAdapter interface and be on the allowlist.")
    url: str = Field(default="https://api.openai.com", title="Server URL", description="The URL of the LLM server.")
    headers: dict[str, str] = Field(default_factory=dict, title="HTTP headers", description="Headers added to the request. Values are dynamic strings, as in agents.")
    additionalParams: dict[str, JsonValue] = Field(default_factory=dict, title="Additional parameters", description="Additional parameters to send to the LLM. They are merged with the parameters the adapter class produces and win wherever the two disagree. String values are interpreted as dynamic strings, as in agents.")
    model: str = Field(..., title="Model", description="The model this profile calls. A profile represents one model of one vendor; to use another model, define another profile.")
    pricing: ModelDetails = Field(default_factory=ModelDetails, title="Pricing", description="The model's prices per million tokens. The cost of a run is calculated from these.")
    maxTokens: int = Field(default=5000, title="Max tokens",
                           description="The token ceiling for agents using this profile. An agent may ask for fewer but not more. What it counts depends on the vendor.")
    retries: int = Field(default=1, title="Retries", description="How many times a failed request is retried.")
    connectionPoolName: ProfileName = Field(default="default", title="Connection pool", description="The connection pool used for calls to the LLM server.")
    maxTools: int = Field(default=10, title="Max tools", description="The most tools that may be sent in a single call.")
    toolErrorPrompt: str = Field(default="Tool returned an error. If changing the arguments to the tool would get past this error, change the arguments. Otherwise, if the tool can be skipped, skip it. As a last resort, provide a text error message and end the conversation.", title="Tool error prompt",
                             description="The user prompt sent to the LLM when a tool call fails.")


class PromptProfileModel(NamedBaseModel):
    type: Literal[AgentConfigPart.prompt] = Field(default=AgentConfigPart.prompt, title="Config part", description="Identifies which configuration part this is.")
    system: str | None = Field(default=None, title="System prompt", description="The system prompt. Usually set once per conversation. Stored encrypted; the Search2o cloud never holds the text.")
    user: str | None = Field(default=None, title="User prompt", description="The user prompt. Can be set many times; those set before one LLM call are merged into a single string. Stored encrypted; the Search2o cloud never holds the text.")

class SecretConversionOptions(StrEnum):
    upper = auto()
    lower = auto()
    none = auto()

class SecretTransformModel(BaseModel):
    match: str = Field(default="[^a-zA-Z0-9]", title="Match pattern", description="Regular expression matched against the secret name. Each match is replaced with the replacement string.")
    replace: str = Field(default="_", title="Replacement", description="What each match is replaced with.")
    convertTo: SecretConversionOptions = Field(default=SecretConversionOptions.none, title="Case conversion", description="After the replacement, whether the name is uppercased, lowercased or left as is.")

class SecretSource(StrEnum):
    env = auto()
    file = auto()
    hosted = auto()


class AgentSecretsModel(BaseModel):
    type: Literal[SystemConfigPart.secrets] = Field(default=SystemConfigPart.secrets, title="Config part", description="Identifies which configuration part this is.")
    secretSource: SecretSource = Field(default=SecretSource.env, title="Secrets source", description="Where secrets are read from.")
    transform: SecretTransformModel = Field(default_factory=SecretTransformModel, title="Name transform", description="Applied to a secret's name before the environment variable is read or the file is opened.")
    secretsEncrypted: str | None = Field(default=None, description="Encrypted secrets, for hosted secrets. Sent only between the Search2o cloud and the agent server.", title="Encrypted secrets")
    secrets: dict[str, str] | None = Field(default=None, title="Secrets", description="Decrypted secrets, for hosted secrets. Never sent to the Search2o cloud.")

    _cache: dict[str, str] = PrivateAttr(default_factory=dict)

    @property
    def cache(self) -> dict[str, str]:
        return self._cache

    @cache.setter
    def cache(self, value: dict[str, str]) -> None:
        self._cache = value


class CookieModel(BaseModel):
    key: Literal["search2o_session"] = Field(default="search2o_session", title="Cookie name", description="The name of the session cookie.")
    path: Literal["/"] = Field(default="/", title="Path", description="The path the cookie is sent for.")
    httponly: Literal[True] = Field(default=True, title="HTTP only", description="Whether the cookie is hidden from JavaScript. Leave on unless a client needs to read it.")
    max_age: int = Field(default=86400, title="Max age (seconds)", description="How long the cookie lives.")
    domain: str = Field(default="", title="Domain", description="The domain the cookie is valid for.")
    secure: bool = Field(default=True, title="Require HTTPS", description="Whether the browser sends the cookie only over HTTPS.")
    samesite: Literal["Lax", "Strict", "None"] = Field(default="Lax", title="SameSite policy", description="When the browser sends the cookie on cross-site requests.")


class EmailFormat(BaseModel):
    subject: str = Field(default=..., title="Subject", description="The subject line of the email.")
    bodyHtml: str = Field(default=..., title="HTML body", description="The body of the email, as HTML. This must be set.")

class PasswordModel(BaseModel):
    minLength: int = Field(default=8, title="Minimum length", description="The fewest characters a password may have.", ge=4, le=128)
    maxLength: int = Field(default=16, title="Maximum length", description="The most characters a password may have.", ge=4, le=128)
    minSpecialChars: int = Field(default=2, title="Minimum special characters", description="How many special characters a password must contain.", ge=0)
    minUpper: int = Field(default=2, title="Minimum uppercase letters", description="How many uppercase letters a password must contain.", ge=0)
    minLower: int = Field(default=2, title="Minimum lowercase letters", description="How many lowercase letters a password must contain.", ge=0)
    minNumbers: int = Field(default=2, title="Minimum digits", description="How many digits a password must contain.", ge=0)
    passwordRules: str = Field(
        default="Minimum 2 each of lower, upper, number and special characters",
        title="Password help",
        description="Help text shown in the UI describing these rules.",
    )

    @model_validator(mode="after")
    def satisfiable(self) -> "PasswordModel":
        if self.minLength > self.maxLength:
            raise ValueError("minLength must not exceed maxLength.")
        required = self.minSpecialChars + self.minUpper + self.minLower + self.minNumbers
        if required > self.maxLength:
            raise ValueError(f"The required character counts add up to {required}, more than "
                             f"maxLength ({self.maxLength}) allows.")
        return self


class BuiltinAuthModel(BaseModel):
    method: Literal[AuthMethod.builtin] = Field(default=AuthMethod.builtin, title="Sign-in method", description="Identifies which sign-in method this is.")
    password: PasswordModel = Field(default_factory=PasswordModel, title="Password policy", description="What a password must contain.")
    maxInactivityMinutes: int = Field(default=60, title="Sign out after inactivity (minutes)", description="How long a session may sit idle before the user is signed out.", ge=5)
    reauthenticateAfterMinutes: int = Field(default=720, title="Re-authenticate after (minutes)", description="How long a session lasts before the user must sign in again, however active they are.", ge=5)
    emailCodeActiveMinutes: int = Field(default=30, title="Emailed code validity (minutes)", description="How long a code emailed for a new user or a password reset stays usable.", ge=1)
    mustChangePasswordEveryDays: int = Field(default=365, title="Force password change (days)", description="How often users must choose a new password.", ge=1, le=3650)
    scriptAccessMaxAgeMinutes: int = Field(default=60, title="Script token max age (minutes)", description="How long a token issued to a script stays valid.", ge=1)
    emailDomain: str | None = Field(default=None, title="Allowed email domain", description="Only addresses in this domain may have accounts.")
    newUserEmail: EmailFormat = Field(
        default_factory=lambda: EmailFormat(
            subject="Welcome to Search2o",
            bodyHtml="",
        ),
        title="New user email",
        description="Sent when an administrator adds a user.",
    )
    forgotPasswordEmail: EmailFormat = Field(
        default_factory=lambda: EmailFormat(
            subject="Reset your password in Search2o",
            bodyHtml="",
        ),
        title="Password reset email",
        description="Sent when a user asks to reset their password.",
    )

class SsoProvisioning(StrEnum):
    reject = auto()      # refuse the sign-in; an administrator adds people first
    createUser = "createUser"   # create them with the 'user' role


class OidcAuthModel(BaseModel):
    method: Literal[AuthMethod.oidc] = Field(default=AuthMethod.oidc, title="Sign-in method", description="Identifies which sign-in method this is.")
    issuer: str = Field(..., title="Issuer", description="The provider's issuer URL, such as https://login.example.com. Its configuration is read from there, and it is what the 'iss' claim must match.", max_length=500)
    clientId: str = Field(..., title="Client id", description="The client id this account was registered with at the provider.", max_length=200)
    clientSecretName: ProfileName | None = Field(default=None, title="Client secret name", description="The name of the entry in the secrets configuration holding the client secret. The agent server resolves it, since the agent server is what calls the provider. Leave it empty for a provider registered without a secret.")
    scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"], title="Scopes", description="What to ask the provider for. The email and name are read from the result, so both are needed.", max_length=20)
    signingKeys: str = Field(default="", title="Signing keys", description="The provider's signing keys as a JWKS document. Leave it empty when the provider can be reached from the internet, and the keys are read from it directly. Set it for a provider inside your network, and update it whenever the provider's keys change.", max_length=20000)
    emailClaim: str = Field(default="email", title="Email claim", description="Which claim in the token holds the email address.", max_length=100)
    nameClaim: str = Field(default="name", title="Name claim", description="Which claim in the token holds the person's name.", max_length=100)
    provisioning: SsoProvisioning = Field(default=SsoProvisioning.reject, title="Unknown users", description="What to do when somebody signs in and has no account here.")
    allowedEmailDomains: list[str] = Field(default_factory=list, title="Allowed email domains", description="Only addresses in these domains may sign in. Leave it empty to allow any address the provider vouches for.", max_length=20)


class Saml2AuthModel(BaseModel):
    method: Literal[AuthMethod.saml2] = Field(default=AuthMethod.saml2, title="Sign-in method", description="Identifies which sign-in method this is.")
    idpEntityId: str = Field(..., title="Identity provider id", description="The identity provider's entity id, which is what the assertion's issuer must match.", max_length=500)
    idpSsoUrl: str = Field(..., title="Identity provider sign-in URL", description="Where the browser is sent to sign in.", max_length=500)
    idpCertificate: str = Field(..., title="Identity provider certificate", description="The provider's signing certificate, in PEM form. Every assertion is checked against it, so it must be replaced whenever the provider's certificate changes.", max_length=20000)
    spEntityId: str = Field(..., title="Service provider id", description="The entity id this account is known by at the identity provider.", max_length=500)
    acsUrl: str = Field(..., title="Sign-in return address", description="The address the identity provider sends people back to, which is this agent server as it is reached from a browser, such as https://search2o.example.com/api/auth/saml/acs.", max_length=500)
    emailAttribute: str = Field(default="email", title="Email attribute", description="Which attribute in the assertion holds the email address. Identity providers differ, so check what yours sends.", max_length=200)
    nameAttribute: str = Field(default="displayName", title="Name attribute", description="Which attribute in the assertion holds the person's name.", max_length=200)
    provisioning: SsoProvisioning = Field(default=SsoProvisioning.reject, title="Unknown users", description="What to do when somebody signs in and has no account here.")
    allowedEmailDomains: list[str] = Field(default_factory=list, title="Allowed email domains", description="Only addresses in these domains may sign in. Leave it empty to allow any address the identity provider vouches for.", max_length=20)


AuthModelUnion: TypeAlias = Annotated[
        BuiltinAuthModel | OidcAuthModel | Saml2AuthModel,
        Field(discriminator="method"),
]


class AuthModel(BaseModel):
    type: Literal[SystemConfigPart.auth] = Field(default=SystemConfigPart.auth, title="Config part", description="Identifies which configuration part this is.")
    cookie: CookieModel = Field(default_factory=CookieModel, title="Session cookie", description="Cookie settings for user sessions.")
    integrationTokenMaxAgeDays: int | None = Field(default=365, title="Integration token max age (days)", description="How long a token issued to an integration stays valid. Leave empty for tokens that never expire.", ge=1)
    auth: AuthModelUnion = Field(default_factory=BuiltinAuthModel, title="Sign-in method", description="How users of this account sign in, and the settings for that method.")


class SysVariables(StrEnum):
    userEmail = "userEmail"  # Email of the user.
    userSession = "userSession" # A hashed value of the session ID of the user in the agent server. This can be used to store data that is specific to the current user session.
    serverIp = "serverIp" # IP address of the agent server as seen by the cloud. This can be used in logging server specific activity.
    cookies = "cookies" # User cookies in the request. This can expose the raw session ID of the user and other such secret values. This needs to be used carefully.


class SysVar(BaseModel):
    type: Literal[SystemConfigPart.sysvar] = Field(default=SystemConfigPart.sysvar, title="Config part", description="Identifies which configuration part this is.")
    sysVariables: list[SysVariables] = Field(default_factory=list, title="Sys variables", description="Which system variables agents can read from the 'sys' namespace. 'inputs' and 'query' are always available.")


class AgentValidationModel(BaseModel):
    type: Literal[SystemConfigPart.validation] = Field(default=SystemConfigPart.validation, title="Config part", description="Identifies which configuration part this is.")
    maxAgentRuntime: int = Field(default=600, title="Max agent runtime (seconds)", description="How long an agent may run before it is stopped.")
    maxIterationLoops: int = Field(default=1_000_000, title="Max loop iterations",
                                   description="The most iterations a 'while' or 'for' may run. A loop inside a loop is counted separately.", ge=0)
    yieldLoopsAfter: int = Field(default=1_000, title="Yield loops after", description="How many iterations a loop runs before yielding, so the runtime limit can be checked.")
    dbMaxRows: int = Field(default=10000, title="Max rows from a db call", description="The most rows a single db command may return.")
    agentMaxLength: int = Field(default=20480, title="Max agent length", description="The most characters an agent definition may contain.")
    maxLlmPrice: float = Field(default=1, title="Max LLM cost per run", description="The agent is stopped once a call takes its spend past this amount.")
    streamHeartbeat: int = Field(default=15, title="Stream heartbeat (seconds)", description="How often a noop is sent on an idle output stream, so browsers and proxies do not close it while the agent works.", ge=1)
    checkSerializationErrors: bool = Field(default=False, title="Check serialization errors", description="Every variable value must be JSON serializable. This is always checked while validating a draft; turning it on also checks it on every run and writes what it finds to the server log.")

class EvalAllowlistModel(BaseModel):
    type: Literal[SystemConfigPart.allowlist] = Field(default=SystemConfigPart.allowlist, title="Config part", description="Identifies which configuration part this is.")
    allowlist: list[str] = Field(
        default_factory=list,
        title="Expression allowlist",
        description="What agent expressions may call. These run on the server's shared event loop and must not block it - asyncio.run, for example. A coroutine is awaited only when it is the whole expression, not when it appears inside a larger one.",
    )


class OperatorMappingAction(BaseModel):
    allow: bool = Field(default=True, title="Allowed", description="Whether agent expressions may use this operator at all.")
    rewrite: str = Field(default="", title="Rewrite to", description="When allowed is True, the name of a function the operator is rewritten to. The function must be in the expression allowlist and have the right signature.")

class OperatorMappingModel(BaseModel):
    add: OperatorMappingAction = Field(default_factory=OperatorMappingAction, title="Add (+)", description="Whether the add operator is allowed in agent expressions, and how it is evaluated.")
    sub: OperatorMappingAction = Field(default_factory=OperatorMappingAction, title="Subtract (-)", description="Whether the subtraction operator is allowed in agent expressions, and how it is evaluated.")
    mult: OperatorMappingAction = Field(default_factory=OperatorMappingAction, title="Multiply (*)", description="Whether the multiplication operator is allowed in agent expressions, and how it is evaluated.")
    div: OperatorMappingAction = Field(default_factory=OperatorMappingAction, title="Divide (/)", description="Whether the division operator is allowed in agent expressions, and how it is evaluated.")
    floordiv: OperatorMappingAction = Field(default_factory=OperatorMappingAction, title="Floor divide (//)", description="Whether the floor division operator is allowed in agent expressions, and how it is evaluated.")
    mod: OperatorMappingAction = Field(default_factory=OperatorMappingAction, title="Modulo (%)", description="Whether the modulo operator is allowed in agent expressions, and how it is evaluated.")
    pow: OperatorMappingAction = Field(default_factory=OperatorMappingAction, title="Power (**)", description="Whether the power operator is allowed in agent expressions, and how it is evaluated.")
    lshift: OperatorMappingAction = Field(default_factory=OperatorMappingAction, title="Left shift (<<)", description="Whether the left shift operator is allowed in agent expressions, and how it is evaluated.")
    rshift: OperatorMappingAction = Field(default_factory=OperatorMappingAction, title="Right shift (>>)", description="Whether the right shift operator is allowed in agent expressions, and how it is evaluated.")
    matmult: OperatorMappingAction = Field(default_factory=OperatorMappingAction, title="Matrix multiply (@)", description="Whether the matrix multiplication operator is allowed in agent expressions, and how it is evaluated.")

class CompileOptions(BaseModel):
    type: Literal[SystemConfigPart.operators] = Field(default=SystemConfigPart.operators, title="Config part", description="Identifies which configuration part this is.")
    operators: OperatorMappingModel = Field(default_factory=OperatorMappingModel, title="Operators", description="Which Python operators agent expressions may use, and how each is evaluated.")
    maxComprehensionDepth: int = Field(default=4, title="Max comprehension depth", description="How deeply comprehensions may be nested in an expression.")
    maxGeneratorsInComprehension: int = Field(default=3, title="Max generators per comprehension", description="How many 'for' clauses a single comprehension may have.")


class AgentServerModel(BaseModel):
    uiPath: str = Field(default="/ui", title="UI path", description="The path the bundled UI is served at. Leave it empty to not serve the UI at all.")
    connectPageUrl: str = Field(default="", title="Connect page URL", description="The page where a user approves an integration's request for access. Leave it empty and it follows the UI path above, which is what keeps the two in step. Set a page under that path for a UI of your own, such as connect, or a full address for a UI hosted elsewhere, such as https://ui.example.com/connect. Whatever is set must point at where the UI is really served. The request is added to it as a query parameter named c.")
    allowCrossOrigin: list[str] = Field(default_factory=lambda: ["*"], title="Allowed CORS origins", description="Other origins allowed to call this API, such as https://ui.example.com.")
    docsUrl: str | None = Field(default="/docs", title="Docs URL", description="Where the API documentation is served.")
    redocUrl: str | None = Field(default="/redoc", title="ReDoc URL", description="Where the ReDoc documentation is served.")
    openapiUrl: str | None = Field(default="/openapi.json", title="OpenAPI URL", description="Where the OpenAPI schema is served.")
    logs: dict[str, JsonValue] = Field(default_factory=dict, title="Logging", description="Logging configuration for the agent server.")
    cloudPoolName: ProfileName = Field(default="default", title="Cloud connection pool", description="The connection pool used for calls to the Search2o cloud.")


class AgentServerModels(BaseModel):
    type: Literal[SystemConfigPart.servers] = Field(default=SystemConfigPart.servers, title="Config part", description="Identifies which configuration part this is.")
    servers: dict[str, AgentServerModel] = Field(default_factory=dict, title="Agent servers", description="The agent servers in this account, keyed by name. A server named 'default' is required.")

    @model_validator(mode="after")
    def validate_default_server(self) -> Self:
        if "default" not in self.servers:
            raise ValueError("A 'default' server config must be specified.")
        return self

class QueryLogging(StrEnum):
    always = auto()
    failureOnly = "failureOnly"
    none = auto()

class SearchBehavior(StrEnum):
    executeTopMatch = "executeTopMatch" # Always execute the top match (Default)
    executeOnlyMatch = "executeOnlyMatch" # When there is a single match, execute automatically. If there are more, show them to the user.
    showResults = "showResults"  # Even when there is a single match, show it to the user. Do not run automatically.

class FollowupBehavior(StrEnum):
    executeTopMatch = "executeTopMatch" # Always execute the top match. If there are no matches, execute the previous (Default)
    executeOnlyMatch = "executeOnlyMatch"  # When there is a single match, execute automatically. If there are more, show them to the user. Add the previous agent to the end, if it doesn't exist in the search results.
    showResults = "showResults" # Even when there is a single match, show it to the user. Do not run automatically. Also, append the previous agent to the list at the end, if it does not already exist in the search results.
    executePrevious = "executePrevious"  # Always execute the same agent in a conversation

class SearchOptionsModel(BaseModel):
    type: Literal[SystemConfigPart.search] = Field(default=SystemConfigPart.search, title="Config part", description="Identifies which configuration part this is.")
    tag: TagFilter = Field(default="", title="Filter tag",
                           description="Only agents carrying this tag are matched. Default is an empty string, which matches all tags.")
    searchBehavior: SearchBehavior = Field(default=SearchBehavior.executeTopMatch, title="Search behavior", description="Decides what happens when the user hits enter on a new search.")
    followupBehavior: FollowupBehavior = Field(default=FollowupBehavior.executeTopMatch, title="Followup behavior", description="Decides what happens when the user hits enter on a followup.")

class EncryptionSource(StrEnum):
    client = auto()
    cloud = auto()

class EncryptionKey(BaseModel):
    keyName: str = Field(..., title="Key name", description="The name the key is referred to by.")
    createdAt: int = Field(..., title="Created at", description="When the key was created, in epoch milliseconds.")

class EncryptionModel(BaseModel):
    type: Literal[SystemConfigPart.encryption] = Field(default=SystemConfigPart.encryption, title="Config part", description="Identifies which configuration part this is.")
    encryptionSource: EncryptionSource = Field(default=EncryptionSource.cloud, title="Encryption source", description="By default Search2o manages a key for this account. Override this to use end-to-end encryption.")
    keys: list[EncryptionKey] = Field(default_factory=list, title="Keys", description="The keys in use. The last one is current, and only the last three months of keys need to be kept.")
    keyFunction: str | None = Field(default=None, title="Key function", description="The function that returns the encryption key for a key name.")


SystemConfigModelUnion: TypeAlias = Annotated[
        AgentServerModels
        | AgentSecretsModel
        | EncryptionModel
        | AuthModel
        | CompileOptions
        | AgentValidationModel
        | EvalAllowlistModel
        | SysVar
        | SearchOptionsModel
        | ApiConnectionPoolsModel,
        Field(discriminator="type"),
]

AgentConfigModelUnion: TypeAlias = Annotated[
        LlmModel
        | ApiServerModel
        | McpServerModel
        | DbConnectionModel
        | PromptProfileModel,
        Field(discriminator="type"),
]

class AgentRuntime(BaseModel):
    updated: int | None = Field(default=None, title="Updated at", description="When this runtime configuration was produced, in epoch milliseconds.")
    updatedSystemConfigs: dict[str, SystemConfigModelUnion] = Field(default_factory=dict, title="System configuration", description="The system configuration parts that changed since the agent server last asked.")
    updatedAgentConfigs: dict[str, list[AgentConfigModelUnion]] = Field(default_factory=dict, title="Agent configuration", description="The agent configuration profiles that changed since the agent server last asked.")
    passwordHelp: str = Field(default='', title="Password help", description="The password rules text, shown wherever a password is chosen.")
    authMethod: AuthMethod = Field(default=AuthMethod.builtin, title="Sign-in method", description="How users of this account sign in, so a client knows what to offer before anyone types.")
    agentVersions: dict[str, int] = Field(default_factory=dict, title="Agent versions", description="The current version of each agent, so an agent server can drop the ones it has cached.")


class InitModel(BaseModel):
    accountName: str = Field(..., title="Account name", description="The account this agent server belongs to.")
    serverIp: str = Field(..., title="Server IP", description="The address this agent server is reached at.")
    agentServer: AgentServerModel = Field(..., title="Agent server", description="The settings this agent server starts with.")
    docsweb: str = Field("https://docs.search2o.com/docsweb", title="UI docs", description="UI uses certain dynamic fields which are served from the web.")


