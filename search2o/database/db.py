# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from search2o.common.closable import Closable
from search2o.common.exceptions import SERVICE_RETRY, ErrorInAgent, ShowMessage, error_message
from search2o.common.mtimeout import m_timeout
from search2o.common.mylogger import MyLogger
from search2o.common.sensitivestring import SensitiveString
from search2o.models.systemconfig import DbConnectionPool, AgentValidationModel


def _missing_driver_message(module_name: str | None) -> str:
    if not module_name:
        return "The database driver for this connection string is not installed."
    return f"The database driver {module_name!r} is not installed. Install it with: pip install {module_name}"


class Database(Closable):

    def __init__(self, validation: AgentValidationModel):
        super().__init__()
        self.validation = validation
        self._engine_cache: dict[str, AsyncEngine] = {}

    async def _get_engine(self, profile_name: str, connection_parameters: DbConnectionPool | None, connection_string: str) -> AsyncEngine:
        if connection_string not in self._engine_cache:
            if connection_parameters is None:
                connection_parameters = DbConnectionPool()
            try:
                self._engine_cache[connection_string] = create_async_engine(
                    connection_string,
                    pool_size=connection_parameters.poolSize,
                    max_overflow=connection_parameters.maxOverflow,
                    pool_timeout=connection_parameters.poolTimeout,
                    pool_recycle=connection_parameters.poolRecycle,
                    pool_pre_ping=connection_parameters.poolPrePing,
                    connect_args=connection_parameters.connectArgs,
                    isolation_level=connection_parameters.isolationLevel,
                    echo=False,
                    future=True,
                )
            except ModuleNotFoundError as e:
                error_message = _missing_driver_message(e.name)
                MyLogger.error(f"{error_message} Connection string: {SensitiveString.safe_connection_string(connection_string)}")
                raise ShowMessage(error_message)
            except Exception:
                message = f"Database connection could not be created using the profile '{profile_name}'" \
                    if profile_name else "Database connection could not be created. Make sure the package exists and it is an async driver"
                error_message = f"{message}: {SensitiveString.safe_connection_string(connection_string)}"
                MyLogger.error(error_message)
                raise ShowMessage(error_message)
        return self._engine_cache[connection_string]


    async def run_sql(self, profile_name: str, connection_parameters: DbConnectionPool | None, connection_string: str, sql: str, params: dict[str, Any], timeout: float | None) -> list[dict[str, Any]]:
        engine = await self._get_engine(profile_name, connection_parameters, connection_string)
        try:
            async with m_timeout(timeout):
                async with engine.begin() as connection:
                    result = await connection.execute(text(sql), params)
                    if result.returns_rows:
                        rows = []
                        for row in result.mappings():
                            rows.append(dict(row))
                            if len(rows) > self.validation.dbMaxRows:
                                raise ShowMessage(f"Database returned more than {self.validation.dbMaxRows} rows. Increase the max rows setting.")
                        return rows
                    else:
                        return []
        except TimeoutError:
            raise ShowMessage(f"Timeout trying to execute query: {sql!r}", SERVICE_RETRY)
        except ErrorInAgent:
            raise
        except Exception as e:
            raise ShowMessage(f"Error communicating with the database: {error_message(e)}", SERVICE_RETRY)


    async def close(self) -> None:
        for engine in self._engine_cache.values():
            try:
                await engine.dispose()
            except Exception:
                pass
        self._engine_cache.clear()
