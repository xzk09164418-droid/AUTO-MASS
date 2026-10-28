"""对旧客户端保留明确的停用响应，阻止进入下载、在线资源等有副作用的路由。"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.requests import HTTPConnection

from app.utils.network_policy import NetworkFeatureDisabled, require_network_feature

DISABLED_PREFIXES = ("/api/share/",)
DISABLED_PATHS = frozenset(
    {
        "/api/update/check",
        "/api/update/download",
        "/api/update/switch-to-cnb",
        "/api/update/install",
        "/api/scripts/import/web",
        "/api/scripts/Upload/web",
        "/api/scripts/share/inspect",
        "/api/tools/community/activity/query",
    }
)


async def enforce_network_policy(connection: HTTPConnection) -> None:
    # 全局依赖也会用于 WebSocket；它只承载本机实时消息，不按 HTTP 路由拦截。
    if connection.scope["type"] != "http":
        return
    path = connection.url.path.rstrip("/")
    if path in DISABLED_PATHS or any(
        (path + "/").startswith(prefix) for prefix in DISABLED_PREFIXES
    ):
        require_network_feature("removed")


async def network_feature_disabled_response(
    request: Request, error: NetworkFeatureDisabled
) -> JSONResponse:
    """使用同一业务错误封装；旧客户端也能明确知道功能被停用。"""
    return JSONResponse(
        status_code=403, content={"code": 403, "status": "error", "message": str(error)}
    )
