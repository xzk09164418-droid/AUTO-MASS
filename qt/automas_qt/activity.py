"""Qt 活动卡使用 Web 版相同的公开数据源，网络与表格解析在线程池中完成。"""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import httpx
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

SRA = {
    "starrail": "sr",
    "genshin": "ys",
    "wutheringwaves": "ww",
    "endfield": "end",
    "zenless": "zzz",
    "nte": "nte",
    "infinitynikki": "infinitynikki",
}
AKE = "https://data.akedata.wiki"


def endfield(client: httpx.Client) -> dict:
    def fetch(url):
        response = client.get(url)
        response.raise_for_status()
        return response.json()

    manifest = fetch(AKE + "/manifest.json")
    version = next(v for v in manifest["versions"] if v["id"] == manifest["latest"])
    root = AKE + "/" + version["tableCfgPath"].strip("/") + "/"
    names = [
        "ActivityTable",
        "TimeRangeTable",
        "I18nTextTable_CN",
        "GachaCharPoolTable",
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        activities, times, texts, pools = pool.map(
            lambda name: fetch(root + name + ".json"), names
        )

    def items(table, pool=False):
        out = []
        for key, item in table.items():
            time_id = item.get("clientTopTimeId" if pool else "timeId") or "time_" + key
            periods = times.get(time_id, {}).get("timeRangeList") or []
            if not periods:
                continue
            period = periods[0]

            def stamp(field):
                value = period.get(field) or ""
                return (
                    value.replace("/", "-").replace(" ", "T") + "+08:00"
                    if value
                    else ""
                )

            name = texts.get(str((item.get("name") or {}).get("id")), key)
            image = item.get("tabImg")
            cover = (
                AKE
                + "/public/images/assets/beyond/dynamicassets/gameplay/ui/sprites/activity/"
                + image
                + ".png"
                if image
                else ""
            )
            out.append(
                dict(
                    name=name,
                    startTime=stamp("openTime"),
                    endTime=stamp("closeTime"),
                    cover=cover,
                    kind="寻访" if pool else "活动",
                )
            )
        return out

    return dict(
        version=version["id"],
        activities=items(activities),
        pools=items(pools, True),
        source="AKEData",
    )


def public_feed(game: str) -> dict:
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        if game == "reverse1999":
            reply = client.get("https://api.1999.fan/api/data/activity/cn.json")
            reply.raise_for_status()

            def stamp(value):
                return (
                    datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
                    if value
                    else ""
                )

            rows = [
                dict(
                    name=item.get("name") or item.get("alias") or key,
                    startTime=stamp(item.get("start_time")),
                    endTime=stamp(item.get("end_time")),
                )
                for ver in reply.json().values()
                for key, item in (ver.get("activity") or {}).items()
            ]
            return dict(activities=rows, source="1999.fan")
        if game == "endfield":
            try:
                return endfield(client)
            except (httpx.HTTPError, KeyError, ValueError, StopIteration):
                pass
        response = client.get(
            f"https://starrailassistant.top/api/v1/activity/{SRA[game]}.json"
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload.get("activities"), list):
            raise ValueError("活动源格式已变化")
        payload["source"] = (
            "SRA（活动日程，未提供卡池）" if game == "endfield" else "SRA"
        )
        return payload


class ActivityFeed(QObject):
    received = Signal(str, int, str)

    @Slot(str, int)
    def load(self, game: str, version: int) -> None:
        if game not in SRA and game != "reverse1999":
            return

        def fetch():
            try:
                result = dict(code=200, data=public_feed(game))
            except (httpx.HTTPError, ValueError, KeyError, TypeError, OSError) as exc:
                result = dict(code=503, message=f"活动源读取失败：{exc}")
            self.received.emit(game, version, json.dumps(result, ensure_ascii=False))

        QThreadPool.globalInstance().start(QRunnable.create(fetch))
