#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2025-2026 AUTO-MAS Team
#   SPDX-License-Identifier: AGPL-3.0-or-later

"""MAS 账号区服匹配与维护跳过记账，不读取脚本内部状态。

区服到游戏维护公告的映射原先只覆盖已移除的专项（MAA / MaaEnd 等）；
通用脚本不声明区服，因此当前不会按维护公告跳过用户。保留接口供以后接入。
"""

import httpx

from app.models.ConfigBase import ConfigBase
from app.services.game_maintenance import MaintenanceWindow


def get_maintenance_message(script_config: ConfigBase) -> str:
    return f"{script_config.get('Info', 'Name')}对应的游戏正在维护"


async def get_user_maintenance(
    user_config: ConfigBase, *, proxy: httpx.Proxy | None
) -> MaintenanceWindow | None:
    return None
