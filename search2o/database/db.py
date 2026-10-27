# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.html.

import asyncio
import time
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


class _Pool:
    def __init__(self, connection_string: str, engine: AsyncEngine, idle_timeout: int):
        self.connection_string = connection_string
        self.engine = engine
        self.idle_timeout = idle_timeout
        self.last_used = time.monotonic()


class Database(Closable):
    _SWEEP_INTERVAL = 10

    def __init__(self, validation: AgentValidationModel):
        super().__init__()
        self.validation = validation
        self._pools: dict[tuple[str, str], _Pool] = {}
        self._sweeper: asyncio.Task | None = None

    async def _get_pool(self, profile_name: str, connection_parameters: DbConnectionPool | None,
                        connection_string: str, pool_key: str) -> _Pool:
        key = (profile_name, pool_key)
        pool = self._pools.get(key)
        replaced = None
        if pool is not None and pool.connection_string != connection_string:
            replaced, pool = pool, None
            del self._pools[key]
        try:
            if pool is None:
                if connection_parameters is None:
                    connection_parameters = DbConnectionPool()
                try:
                    engine = create_async_engine(
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
                    from search2o.common.rest_call import RestCall
                    RestCall.report_error_once("A database driver is not installed.")
                    raise ShowMessage(error_message)
                except Exception:
                    message = f"Database connection could not be created using the profile '{profile_name}'" \
                        if profile_name else "Database connection could not be created. Make sure the package exists and it is an async driver"
                    error_message = f"{message}: {SensitiveString.safe_connection_string(connection_string)}"
                    MyLogger.error(error_message)
                    from search2o.common.rest_call import RestCall
                    RestCall.report_error_once("A database connection could not be created.")
                    raise ShowMessage(error_message)
                pool = self._pools[key] = _Pool(connection_string, engine, connection_parameters.idleTimeout)
                if self._sweeper is None:
                    self._sweeper = asyncio.create_task(self._sweep())
        finally:
            if replaced is not None:
                await self._dispose(replaced)
        pool.last_used = time.monotonic()
        return pool

    async def _sweep(self) -> None:
        while True:
            await asyncio.sleep(self._SWEEP_INTERVAL)
            now = time.monotonic()
            for key, pool in list(self._pools.items()):
                if pool.idle_timeout and now - pool.last_used > pool.idle_timeout and self._pools.get(key) is pool:
                    del self._pools[key]
                    await self._dispose(pool)

    @staticmethod
    async def _dispose(pool: _Pool) -> None:
        try:
            await pool.engine.dispose()
        except Exception as e:
            MyLogger.warning(f"Error closing a database connection pool: {error_message(e)}")

    async def run_sql(self, profile_name: str, connection_parameters: DbConnectionPool | None, connection_string: str,
                      pool_key: str, sql: str, params: dict[str, Any], timeout: float | None) -> list[dict[str, Any]]:
        pool = await self._get_pool(profile_name, connection_parameters, connection_string, pool_key)
        try:
            async with m_timeout(timeout):
                async with pool.engine.begin() as connection:
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
        finally:
            pool.last_used = time.monotonic()


    async def close(self) -> None:
        if self._sweeper is not None:
            self._sweeper.cancel()
            self._sweeper = None
        pools, self._pools = list(self._pools.values()), {}
        for pool in pools:
            await self._dispose(pool)
