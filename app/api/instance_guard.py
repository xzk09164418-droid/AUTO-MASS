"""拒绝携带其他安装身份的 HTTP/WS 请求，身份由后端实际数据根决定。"""

import os

from starlette.responses import JSONResponse

from app.services.instance_identity import backend_instance_id


class InstanceIdentityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in {"http", "websocket"}:
            expected = dict(scope.get("headers", [])).get(b"x-auto-mas-instance")
            protected = os.getenv("AUTO_MAS_BROWSER_HOST") == "1" and scope.get(
                "path"
            ) in {
                "/api/core/close",
                "/api/core/ws",
            }
            if (protected and not expected) or (
                expected
                and expected.decode("ascii", errors="replace") != backend_instance_id()
            ):
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                else:
                    response = JSONResponse(
                        {
                            "code": 409,
                            "status": "error",
                            "message": "后端不属于请求指定的安装实例",
                        },
                        status_code=409,
                    )
                    await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
