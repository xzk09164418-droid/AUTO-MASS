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


"""MCP 路由入口；业务工具按需在独立进程加载。"""

import os

from fastapi import FastAPI

from app.services.mcp_runtime import McpRuntime
from app.utils.logger import get_logger

logger = get_logger("MCP 服务")


async def mount_mcp(app: FastAPI, *, backend_url: str) -> None:
    if os.getenv("AUTO_MAS_ENABLE_MCP", "1") != "1":
        logger.info("MCP 服务未启用，跳过路由挂载")
        return
    runtime = McpRuntime(app, backend_url=backend_url)
    app.state.mcp_runtime = runtime
    app.add_api_route(
        "/mcp",
        runtime.handle,
        methods=["GET", "POST", "DELETE"],
        include_in_schema=False,
    )
    logger.info("MCP 入口已待命，首次访问时在独立进程加载，不阻塞调度与热键")
