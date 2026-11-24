#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2025-2026 AUTO-MAS Team
#   SPDX-License-Identifier: AGPL-3.0-or-later

"""后台游戏日历取数，复用首页已使用的公开活动源。"""

from collections.abc import Mapping

import httpx

from app.tools.sra_activity import fetch_sra_activities
from app.tools.reverse1999_calendar import activities_for_version

# 与首页游戏键对应；后台使用中文档，避免切换界面语言改变活动标识。
CALENDAR_GAMES = {
    "endfield": ("end", "明日方舟：终末地"),
    "starrail": ("sr", "崩坏：星穹铁道"),
    "genshin": ("ys", "原神"),
    "zenless": ("zzz", "绝区零"),
    "wutheringwaves": ("ww", "鸣潮"),
    "nte": ("nte", "异环"),
    "reverse1999": ("", "重返未来：1999"),
    "bluearchive": ("ba-cn", "碧蓝档案"),
    "arknights": ("ak", "明日方舟"),
    "stellasora": ("xtlr", "星塔旅人"),
    "infinitynikki": ("infinitynikki", "无限暖暖"),
}
BLUEARCHIVE_SERVERS = {
    "cn": ("ba-cn", "国服"),
    "jp": ("ba-jp", "日服"),
    "global": ("ba-global", "国际服"),
}
REVERSE1999_URL = "https://api.1999.fan/api/data/activity/cn.json"


async def fetch_calendar_activities(source: str) -> list[Mapping[str, object]] | None:
    """查询完整活动列表；取数失败由定时器隔离，下次检查再重试。"""

    if source:
        # 明日方舟、终末地、星塔旅人复用首页的 SRA 备用源，无需打开首页。
        data = await fetch_sra_activities(source)
        items = data.get("activities") if data is not None else None
        return items if isinstance(items, list) else None

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(REVERSE1999_URL)
    response.raise_for_status()
    versions = response.json()
    if not isinstance(versions, dict):
        raise ValueError("1999 活动数据格式无效")

    activities: list[Mapping[str, object]] = []
    for version in versions.values():
        if isinstance(version, dict):
            activities.extend(activities_for_version(version))
    return activities
