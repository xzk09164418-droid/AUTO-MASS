"""按需启动 MCP 工作进程，以 stdio 转发 HTTP；不阻塞任务事件循环。"""

import asyncio
import base64
import json
import os
import sys
import uuid
from contextlib import suppress

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute

from app.utils.logger import get_logger
from app.utils.platform.common.process_runner import create_subprocess
from app.utils.platform.process import platform_process

logger = get_logger("MCP 进程")


class McpRuntime:
    def __init__(self, app: FastAPI, *, backend_url: str):
        self.app = app
        self.backend_url = backend_url
        self.process = None
        self.reader_task = None
        self.ready = None
        self.pending: dict[str, asyncio.Future] = {}
        self.start_lock = asyncio.Lock()
        self.write_lock = asyncio.Lock()
        self.closing = False

    async def _write(self, message: dict) -> None:
        content = json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n"
        async with self.write_lock:
            self.process.stdin.write(content)
            await self.process.stdin.drain()

    async def _read(self) -> None:
        try:
            while line := await self.process.stdout.readline():
                message = json.loads(line)
                if message.get("kind") == "ready":
                    if not self.ready.done():
                        self.ready.set_result(message)
                    continue
                if message.get("kind") == "error":
                    raise RuntimeError(message.get("error", "MCP 工作进程错误"))
                future = self.pending.get(message.get("id"))
                if future is not None and not future.done():
                    future.set_result(message)
            raise RuntimeError("MCP 工作进程已退出")
        except Exception as error:
            if not self.closing:
                logger.error(f"MCP 工作进程异常: {error}")
            if self.ready is not None and not self.ready.done():
                self.ready.set_exception(error)
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(error)

    async def _start(self) -> None:
        async with self.start_lock:
            if self.closing:
                raise RuntimeError("后端正在退出")
            if (
                self.process is not None
                and self.process.returncode is None
                and not self.reader_task.done()
            ):
                await asyncio.wait_for(asyncio.shield(self.ready), timeout=45)
                return
            if self.process is not None:
                await self._stop_process()
            from app.services.mcp_tools import MCP_INCLUDED_OPERATIONS

            schema_app = FastAPI(
                title=self.app.title,
                version=self.app.version,
                description=self.app.description,
            )
            schema_app.openapi_version = self.app.openapi_version
            schema_app.router.routes = [
                route
                for route in self.app.routes
                if isinstance(route, APIRoute)
                and (route.operation_id or route.unique_id) in MCP_INCLUDED_OPERATIONS
            ]
            schema = await asyncio.to_thread(schema_app.openapi)
            self.process = await create_subprocess(
                sys.executable,
                "-m",
                "app.services.mcp_worker",
                cwd=os.getcwd(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=None,
                limit=16 * 1024 * 1024,
            )
            self.ready = asyncio.get_running_loop().create_future()
            self.reader_task = asyncio.create_task(self._read())
            await self._write(
                {"version": 1, "schema": schema, "backendUrl": self.backend_url}
            )
            try:
                await asyncio.wait_for(asyncio.shield(self.ready), timeout=45)
            except BaseException:
                await self._stop_process()
                raise
            logger.info(f"MCP 工具已在独立进程就绪，PID: {self.process.pid}")

    async def handle(self, request: Request) -> Response:
        request_id = uuid.uuid4().hex
        future = None
        try:
            await self._start()
            future = asyncio.get_running_loop().create_future()
            self.pending[request_id] = future
            await self._write(
                {
                    "kind": "request",
                    "id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "query": request.url.query,
                    "headers": list(request.headers.items()),
                    "body": base64.b64encode(await request.body()).decode("ascii"),
                }
            )
            result = await future
            return Response(
                content=base64.b64decode(result["body"]),
                status_code=result["status"],
                headers=result["headers"],
            )
        except Exception as error:
            logger.error(f"MCP 请求失败: {error}")
            return JSONResponse(
                status_code=503,
                content={"detail": "MCP 服务暂不可用，请查看后端日志后重试"},
            )
        finally:
            self.pending.pop(request_id, None)
            if future is not None and (not future.done() or future.cancelled()):
                future.cancel()
                with suppress(Exception):
                    await self._write({"kind": "cancel", "id": request_id})

    async def _stop_process(self) -> None:
        process = self.process
        if process is not None:
            if process.stdin is not None:
                process.stdin.close()
            try:
                await asyncio.wait_for(process.wait(), timeout=3)
            except asyncio.TimeoutError:
                await platform_process.kill_process(process.pid, kill_tree=True)
                await process.wait()
        if self.reader_task is not None:
            self.reader_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.reader_task

    async def close(self) -> None:
        self.closing = True
        await self._stop_process()
