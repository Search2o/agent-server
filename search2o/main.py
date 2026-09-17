# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

import asyncio
import errno
import inspect
import logging
import sys
from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi import Request
from fastapi.exceptions import RequestValidationError, HTTPException, ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse

from search2o.api.admin import admin_router
from search2o.api.auth import auth_router
from search2o.api.dev import dev_router
from search2o.api.exec import exec_router
from search2o.api.owner import owner_router
from search2o.api.reports import reports_router
from search2o.api.user import user_router
from search2o.common.enums import CookieKey
from search2o.common.exceptions import ErrorFromCloudException, ErrorInAgent, InitializationError
from search2o.common.jsonvalidation import JsonValidator
from search2o.common.rest_call import RestCall
from search2o.config.buildconfig import BuildConfig
from search2o.config.config import Config
from search2o.execution.init import Init
from search2o.execution.runtime import Runtime
from search2o.models.apimodels import BaseResponseModel, ErrorResponseModel


_DEFAULT_PORT = 9020


def _startup_banner(host: str, port: int) -> None:
    conf = Config.init_model.agentServer
    base = f"http://{host}:{port}"
    entries = [("Account", Runtime.account_name), ("Serving", base)]
    if conf.uiPath:
        entries.append(("UI", f"{base}/{conf.uiPath.strip('/')}/"))
    for label, path in (("Swagger", conf.docsUrl), ("ReDoc", conf.redocUrl), ("OpenAPI", conf.openapiUrl)):
        if path:
            entries.append((label, f"{base}{path}"))
    width = max(len(label) for label, _ in entries) + 1
    lines = [f"Search2o agent server {Config.client_version}"]
    lines += [f"  {(label + ':'):<{width}} {value}" for label, value in entries if value]
    lines.append("  Press CTRL+C to stop.")
    print("\n".join(lines), flush=True)


@asynccontextmanager
async def lifespan(app1: FastAPI):
    try:
        await Init.init_all()
        yield
    finally:
        await Init.close_all()


def _validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content = BaseResponseModel(success=False,
                                    error=ErrorResponseModel(message=JsonValidator.error_text(exc))).model_dump()
    )

def _http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content = BaseResponseModel(success=False, error=ErrorResponseModel(message=exc.detail)).model_dump()
    )

def _call_failed_exception_handler(request: Request, exc: ErrorFromCloudException):
    cause = str(exc.__cause__) if exc.__cause__ else None
    response = JSONResponse(
        status_code=exc.status_code,
        content = BaseResponseModel(success=False, error=ErrorResponseModel(message=exc.detail, cause=cause, data=exc.errorData or {})).model_dump()
    )
    return response

async def _response_validation_exception_handler(request: Request, exc: ResponseValidationError):
    message = "Unexpected validation error. We have recorded this and will fix it soon."
    await RestCall.report_error(request, message, exc)
    return JSONResponse(
        status_code=500,
        content = BaseResponseModel(success=False, error=ErrorResponseModel(message=message)).model_dump()
    )


def _error_in_agent_exception_handler(request: Request, exc: ErrorInAgent):
    return JSONResponse(
        status_code=422,
        content = BaseResponseModel(success=False,
                                    error=ErrorResponseModel(message=exc.message(), path=exc.path)).model_dump())

async def _generic_exception_handler(request: Request, exc: Exception):
    message = "Unexpected error. We have recorded this and will fix it soon."
    await RestCall.report_error(request, message,exc)
    return JSONResponse(
        status_code=500,
        content = BaseResponseModel(success=False, error=ErrorResponseModel(message=message)).model_dump()
    )

def _custom_generate_unique_id(route: APIRoute) -> str:
    return route.name

def _add_global_security(fast_api: FastAPI):
    def custom_openapi():
        if fast_api.openapi_schema:
            return fast_api.openapi_schema
        schema = get_openapi(
            title=fast_api.title,
            version=fast_api.version,
            description=fast_api.description,
            license_info=fast_api.license_info,
            contact=fast_api.contact,
            routes=fast_api.routes,
            servers=fast_api.servers,
            terms_of_service=fast_api.terms_of_service
        )
        comps = schema.setdefault("components", {})
        sec = comps.setdefault("securitySchemes", {})
        sec["bearerAuth"] = {"type": "http", "scheme": "bearer"}
        sec["cookieAuth"] = {"type": "apiKey", "in": "cookie", "name": CookieKey.cookieName}
        schema["security"] = [
            {"cookieAuth": []},
            {"bearerAuth": []},
        ]
        fast_api.openapi_schema = schema
        return schema

    fast_api.openapi = custom_openapi


def create_app():
    from search2o.common.exceptions import ErrorFromCloudException
    conf = Config.init_model.agentServer
    fast_api = FastAPI(version=Config.client_version,
                       title="Search2o",
                       description="Search2o Agent Server",
                       separate_input_output_schemas=False,
                       contact={
                      "name": "Search2o",
                      "url": "https://search2o.com",
                      "email": "info@search2o.com"
                  },
                       license_info={
                    "name": "Proprietary",
                    "url": "https://search2o.com/legal/license.txt"
                  },
                       terms_of_service="https://search2o.com/legal/terms.html",
                       servers=[{ "url": "/" }],
                       docs_url=conf.docsUrl,
                       redoc_url=conf.redocUrl,
                       openapi_url=conf.openapiUrl,
                       exception_handlers={
                      RequestValidationError: _validation_exception_handler,
                      ErrorFromCloudException: _call_failed_exception_handler,
                      HTTPException: _http_exception_handler,
                      ResponseValidationError: _response_validation_exception_handler,
                      ErrorInAgent: _error_in_agent_exception_handler,
                      Exception: _generic_exception_handler
                  },
                       lifespan=lifespan,
                       generate_unique_id_function=_custom_generate_unique_id
                       )

    if conf.allowCrossOrigin:
        fast_api.add_middleware(
            CORSMiddleware,
            allow_origins=conf.allowCrossOrigin,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    _add_global_security(fast_api)

    @fast_api.api_route("/health", methods=["GET", "HEAD"], include_in_schema=False)
    async def health():
        return {"status": "ok"}

    fast_api.include_router(auth_router)
    fast_api.include_router(dev_router)
    fast_api.include_router(exec_router)
    fast_api.include_router(admin_router)
    fast_api.include_router(user_router)
    fast_api.include_router(reports_router)
    fast_api.include_router(owner_router)

    if conf.uiPath:
        package_dir = Path(__file__).resolve().parent
        ui_dir = package_dir / "ui"
        if ui_dir.is_dir():
            fast_api.mount(f"/{conf.uiPath.strip('/')}", StaticFiles(directory=str(ui_dir), html=True), name="ui")

    return fast_api


def _quiet_log_config() -> dict:
    config = deepcopy(uvicorn.config.LOGGING_CONFIG)
    loggers = config.setdefault("loggers", {})
    loggers.setdefault("uvicorn.error", {})["level"] = "WARNING"
    loggers["httpx"] = {"level": "WARNING", "propagate": True}
    return config


def _uvicorn_config(args: list[str]) -> uvicorn.Config:
    try:
        context = uvicorn.main.make_context("search2o", args)
    except Exception as exc:  # click usage errors carry their own rendering and exit code
        show = getattr(exc, "show", None)
        if show is None:
            raise
        show()
        raise SystemExit(getattr(exc, "exit_code", 2)) from None
    params = dict(context.params)
    params["headers"] = [header.split(":", 1) for header in params.get("headers") or ()]
    if params.get("log_config") is None:
        params["log_config"] = _quiet_log_config()
    if params.get("app_dir"):
        sys.path.insert(0, params["app_dir"])
    accepted = inspect.signature(uvicorn.Config).parameters
    return uvicorn.Config(**{k: v for k, v in params.items() if k in accepted})

class _PortInUse(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        self.hit = False

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, OSError) and record.msg.errno == errno.EADDRINUSE:
            self.hit = True
            return False
        return True


class _Server(uvicorn.Server):
    async def startup(self, sockets=None) -> None:
        in_use = _PortInUse()
        logger = logging.getLogger("uvicorn.error")
        if not self.config.uds:
            logger.addFilter(in_use)
        try:
            await super().startup(sockets=sockets)
        except SystemExit:
            if not in_use.hit:
                raise
            port = self.config.port
            taken = (f"Search2o's default port {port}" if port == _DEFAULT_PORT else f"Port {port}")
            raise SystemExit(f"{taken} is already in use. "
                             f"Please start it in an available port: search2o --port XXXX") from None
        finally:
            logger.removeFilter(in_use)
        _startup_banner(self.config.host, self.config.port)


def cli():
    if sys.version_info < (3, 12):
        raise SystemExit("Search2o requires Python 3.12+.")

    _DISALLOWED = {
        "--reload",
        "--reload-dir",
        "--reload-include",
        "--reload-exclude",
        "--reload-delay",
        "--factory",
        "--workers"
    }

    disallowed = [a for a in sys.argv[1:] if a.split("=", 1)[0] in _DISALLOWED]
    if disallowed:
        raise SystemExit("These options are not supported: " + ", ".join(sorted(set(disallowed))))

    try:
        asyncio.run(BuildConfig.fetch_and_build())
    except InitializationError as e:
        print(e)
        return

    user_args = sys.argv[1:]
    port_args = [] if any(a == "--port" or a.startswith("--port=") for a in user_args) else ["--port", str(_DEFAULT_PORT)]
    config = _uvicorn_config(["search2o.main:create_app", "--factory", *user_args, *port_args])
    asyncio.run(_Server(config).serve())


if __name__ == "__main__":
    cli()


