#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2024-2025 DLmaster361
#   Copyright © 2025 MoeSnowyFox
#   Copyright © 2025-2026 AUTO-MAS Team

#   This file is part of AUTO-MAS.

#   AUTO-MAS is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of
#   the License, or (at your option) any later version.

#   AUTO-MAS is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
#   the GNU Affero General Public License for more details.

#   You should have received a copy of the GNU Affero General Public License
#   along with AUTO-MAS. If not, see <https://www.gnu.org/licenses/>.

#   Contact: DLmaster_361@163.com


"""MCP 挂载、配置工具白名单与 Agent 使用提示。

复用已有 HTTP 接口，不注册新的配置路由或专项业务逻辑。
"""

import asyncio
import importlib
import os
from copy import deepcopy

import httpx
from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.utils.logger import get_logger

logger = get_logger("MCP 服务")


class McpHttpClient(httpx.AsyncClient):
    """兼容 fastapi-mcp 将无参数工具的 JSON 对象转成 None 的行为。"""

    async def request(
        self, method: str, url: httpx.URL | str, **kwargs
    ) -> httpx.Response:
        if method.upper() == "POST" and "json" in kwargs and kwargs["json"] is None:
            kwargs["json"] = {}
        return await super().request(method, url, **kwargs)


# 操作与标签过滤在 fastapi-mcp 0.4.0 中取并集，因此只用操作白名单。
# 保留既有工具名；删除、清理、发布、登录和应用更新接口不自动暴露。
MCP_INCLUDED_OPERATIONS = (
    # 仅暴露当前 General 构建可用的配置、队列和运行查询。
    "add_script_api_scripts_add_post",
    "get_script_api_scripts_get_post",
    "update_script_api_scripts_update_post",
    "add_user_api_scripts_user_add_post",
    "get_user_api_scripts_user_get_post",
    "update_user_api_scripts_user_update_post",
    "import_script_config_file_api_scripts_config_import_post",
    "get_emulator_combox_api_info_combox_emulator_post",
    "get_emulator_devices_combox_api_info_combox_emulator_devices_post",
    "add_queue_api_queue_add_post",
    "get_queues_api_queue_get_post",
    "update_queue_api_queue_update_post",
    "add_item_api_queue_item_add_post",
    "get_item_api_queue_item_get_post",
    "update_item_api_queue_item_update_post",
    "reorder_item_api_queue_item_order_post",
    "add_time_set_api_queue_time_add_post",
    "get_time_set_api_queue_time_get_post",
    "update_time_set_api_queue_time_update_post",
    "reorder_time_set_api_queue_time_order_post",
    "get_task_runtime_snapshot_api_dispatch_runtime_snapshot_get",
    "get_task_status_api_dispatch_task__task_id__get",
    "add_task_api_dispatch_start_post",
    "stop_task_api_dispatch_stop_post",
    "search_history_api_history_search_post",
)


def restrict_mcp_schema(schema: dict) -> dict:
    """收窄 MCP 契约，不改动供旧客户端使用的 HTTP 模型。"""
    schema = deepcopy(schema)
    create = schema.get("components", {}).get("schemas", {}).get("ScriptCreateIn", {})
    script_type = create.get("properties", {}).get("type")
    if script_type is not None:
        script_type["enum"] = ["General"]
        script_type["description"] = "当前构建仅支持 General 通用脚本"
    return schema


def _patch_fastapi_mcp_ref_recursion(max_depth: int = 96) -> None:
    """给 fastapi_mcp 的 $ref 解析加递归深度上限。

    库实现（openapi.utils.resolve_schema_references）在模型互相
    $ref 引用时会无限展开（A→B→A…），递归 ~1000 层即 RecursionError，
    导致 MCP 挂载失败。
    这里以相同逻辑但带深度上限的实现替换；超限的 $ref 原样保留，
    仅影响 MCP 工具 schema 的展示完整度，不再炸初始化。
    需同时替换 utils 与 convert 两处按名绑定的引用。
    """
    import fastapi_mcp.openapi.convert as _fm_convert
    from fastapi_mcp.openapi import utils as _fm_utils

    def resolve_with_depth_limit(schema_part, reference_schema, _depth=0):
        schema_part = schema_part.copy()
        if "$ref" in schema_part and _depth < max_depth:
            ref_path = schema_part["$ref"]
            # 标准 OpenAPI 引用格式："#/components/schemas/ModelName"
            if ref_path.startswith("#/components/schemas/"):
                model_name = ref_path.split("/")[-1]
                components = reference_schema.get("components") or {}
                schemas = components.get("schemas") or {}
                if model_name in schemas:
                    ref_schema = schemas[model_name].copy()
                    schema_part.pop("$ref")
                    schema_part.update(ref_schema)
        for key, value in schema_part.items():
            if isinstance(value, dict):
                schema_part[key] = resolve_with_depth_limit(
                    value, reference_schema, _depth + 1
                )
            elif isinstance(value, list):
                schema_part[key] = [
                    resolve_with_depth_limit(item, reference_schema, _depth + 1)
                    if isinstance(item, dict)
                    else item
                    for item in value
                ]
        return schema_part

    _fm_utils.resolve_schema_references = resolve_with_depth_limit
    _fm_convert.resolve_schema_references = resolve_with_depth_limit


async def build_mcp(
    app: FastAPI, *, schema_document: dict | None = None, backend_url: str | None = None
):
    """后台挂载配置工具，保持 /mcp 与 AUTO_MAS_ENABLE_MCP 开关兼容。"""

    # 仅生成白名单工具所需的 schema；真实 HTTP 请求仍经过完整应用和原有中间件。
    # 模块先在事件循环导入，线程仅负责已经解析好的构造函数，避免并发冷导入。
    if os.getenv("AUTO_MAS_ENABLE_MCP", "1") == "1":
        importlib.import_module("mcp")
        await asyncio.sleep(0)
        fastapi_mcp = importlib.import_module("fastapi_mcp")
        await asyncio.sleep(0)
        _patch_fastapi_mcp_ref_recursion()

        schema_app = FastAPI(
            title=app.title, version=app.version, description=app.description
        )
        schema_app.openapi_version = app.openapi_version
        schema_app.router.routes = [
            route
            for route in app.routes
            if isinstance(route, APIRoute)
            and (route.operation_id or route.unique_id) in MCP_INCLUDED_OPERATIONS
        ]
        http_client = McpHttpClient(
            trust_env=False,
            transport=None
            if backend_url
            else httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url=backend_url or "http://apiserver",
            timeout=10.0,
        )
        server_module = importlib.import_module("fastapi_mcp.server")
        original_openapi = server_module.get_openapi
        schema_document = restrict_mcp_schema(schema_document or schema_app.openapi())
        if schema_document is not None:
            # 独立工作进程使用主服务提供的公开契约，不导入业务路由或配置。
            server_module.get_openapi = lambda **kwargs: schema_document
        try:
            mcp = await asyncio.to_thread(
                fastapi_mcp.FastApiMCP,
                schema_app,
                http_client=http_client,
                name="AUTO-MAS MCP",
                description=(
                    "当前构建仅支持 General 通用脚本，不提供 MaaFramework、OCR 或专项配置工具。"
                    "创建 General 脚本并设置外部程序路径，配置用户、队列、队列项和定时项，最后按需试运行。"
                    "创建接口返回新 ID 和默认配置；修改时只提交需要变更的字段，使用查询返回的真实 ID。"
                    "保存后回读核对；检查业务 code，失败时不要猜测 ID、字段或选项。"
                    "任务创建成功仅表示已受理，不代表脚本运行成功。"
                    "运行快照只包含当前任务；任务结束后按 taskId 查任务状态取终态，"
                    "更早的结果查历史索引中的 DONE/ERROR，没有匹配记录时不能判定成功。"
                ),
                describe_full_response_schema=False,
                describe_all_responses=False,
                # 仅暴露通用配置与试运行能力；新增 HTTP 接口不会自动成为工具。
                # fastapi-mcp 的操作与标签过滤取并集，白名单不能再搭配标签过滤。
                include_operations=list(MCP_INCLUDED_OPERATIONS),
            )
            # 0.4.0 在工具清单为空时不会清空调用映射，仍需按实际清单收敛。
            tool_names = {tool.name for tool in mcp.tools}
            missing_operations = set(MCP_INCLUDED_OPERATIONS) - tool_names
            if missing_operations:
                raise RuntimeError(
                    f"MCP 白名单包含不存在的 operation: {sorted(missing_operations)}"
                )
            mcp.operation_map = {
                name: operation
                for name, operation in mcp.operation_map.items()
                if name in tool_names
            }
            for tool in mcp.tools:
                if tool.name == "get_task_status_api_dispatch_task__task_id__get":
                    tool.description += (
                        "\n\n按 taskId 单点查询一个任务：运行中返回 running，已结束返回"
                        "success/error/cancelled 及结果文本与错误信息，不返回日志。"
                        "code=404 表示该 id 既不在运行中，也不在最近完成的记录里，"
                        "结果未知，不要判成功。"
                    )
                elif tool.name == "search_history_api_history_search_post":
                    tool.description += (
                        "\n\n用于查询已结束运行的结果，建议按运行日期使用 DAILY 模式。"
                        "按用户和记录时间核对 index 中的 status（DONE/ERROR）与 result。"
                        "该接口不按 taskId 精确检索，按 taskId 取终态请用任务状态查询；"
                        "记录缺失或无法唯一对应时，结果仍未知，"
                        "不能把任务从运行快照消失视为成功。"
                    )
            mcp.mount_http(router=app)
            logger.info(f"MCP 服务已挂载，共 {len(mcp.tools)} 个工具")
            return mcp, http_client
        except BaseException:
            await http_client.aclose()
            raise
        finally:
            server_module.get_openapi = original_openapi

    else:
        logger.info("MCP 服务未启用，跳过路由挂载")
