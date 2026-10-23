"""MCP 的独立 stdio 工作进程，不加载或运行任务调度器。"""

import asyncio
import base64
import json
import sys

# stdout 专用于协议，依赖包的终端输出保留在 stderr。
wire = sys.stdout.buffer
sys.stdout = sys.stderr


async def main() -> None:
    import httpx
    from fastapi import FastAPI

    from app.services.mcp_tools import build_mcp

    def emit(message):
        wire.write(json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n")
        wire.flush()

    initial = json.loads(await asyncio.to_thread(sys.stdin.buffer.readline))
    if initial.get("version") != 1:
        raise ValueError("不支持的 MCP stdio 协议版本")
    app = FastAPI(
        title=initial["schema"]["info"]["title"],
        version=initial["schema"]["info"]["version"],
    )
    mcp, backend_client = await build_mcp(
        app, schema_document=initial["schema"], backend_url=initial["backendUrl"]
    )
    requests = {}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://mcp"
    ) as transport:

        async def serve(message):
            try:
                response = await transport.request(
                    message["method"],
                    message["path"]
                    + ("?" + message["query"] if message["query"] else ""),
                    headers=message["headers"],
                    content=base64.b64decode(message["body"]),
                )
                emit(
                    {
                        "id": message["id"],
                        "status": response.status_code,
                        "headers": dict(response.headers),
                        "body": base64.b64encode(response.content).decode("ascii"),
                    }
                )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                emit(
                    {
                        "id": message["id"],
                        "status": 500,
                        "headers": {"content-type": "application/json"},
                        "body": base64.b64encode(
                            json.dumps({"detail": str(error)}).encode()
                        ).decode("ascii"),
                    }
                )
            finally:
                requests.pop(message["id"], None)

        emit({"kind": "ready", "toolCount": len(mcp.tools)})
        try:
            while line := await asyncio.to_thread(sys.stdin.buffer.readline):
                message = json.loads(line)
                if message.get("kind") == "cancel":
                    task = requests.get(message["id"])
                    if task is not None:
                        task.cancel()
                elif message.get("kind") == "request":
                    requests[message["id"]] = asyncio.create_task(serve(message))
        finally:
            for task in tuple(requests.values()):
                task.cancel()
            await asyncio.gather(*tuple(requests.values()), return_exceptions=True)
            await mcp._http_transport.shutdown()
            await backend_client.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        wire.write(
            json.dumps({"kind": "error", "error": str(error)}).encode("utf-8") + b"\n"
        )
        wire.flush()
        raise
