"""重返未来 1999 公开日程的活动字段，Qt 卡片与后台日历共用。"""

from datetime import datetime, timezone


def _stamp(value: object) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        return ""
    try:
        return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return ""


def activities_for_version(version: dict) -> list[dict[str, str]]:
    items = version.get("activity")
    if not isinstance(items, dict):
        return []
    kinds = {"MainStory": "主线活动", "SideStory": "限时活动"}
    keys = {"combat": "版本活动", "compat": "版本活动", "re-release": "复刻活动", "anecdote": "轶事活动"}
    rows = []
    for key, item in items.items():
        if not isinstance(item, dict):
            continue
        start, end = _stamp(item.get("start_time")), _stamp(item.get("end_time"))
        if not start or not end or item["end_time"] <= item["start_time"]:
            continue
        name = next((v.strip() for v in (item.get("name"), item.get("alias"))
                     if isinstance(v, str) and v.strip() and v.strip().lower() not in keys), "")
        name = name or kinds.get(str(item.get("event_type"))) or keys.get(key, "限时活动")
        rows.append({"name": name, "startTime": start, "endTime": end})
    return rows
