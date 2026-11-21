"""Qt 游戏活动适配，沿用 Web 主页各来源的字段与时间语义。"""

import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
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
POOL_TYPES = {0: "特许寻访", 1: "新手寻访", 2: "常驻寻访", 3: "联合寻访"}


def timestamp(value: str) -> float:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, AttributeError):
        return 0


def source_time(value: str) -> str:
    if not value:
        return ""
    text = value.strip()
    if "/" in text:
        try:
            local = datetime.strptime(text, "%Y/%m/%d %H:%M:%S")
            return local.isoformat() + "+08:00"
        except ValueError:
            return ""
    text = text.replace(" ", "T")
    if re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d)?", text):
        text += "+08:00"
    return text if timestamp(text) else ""


def sra_feed(client: httpx.Client, game: str) -> dict:
    reply = client.get(
        f"https://starrailassistant.top/api/v1/activity/{SRA[game]}.json"
    )
    reply.raise_for_status()
    raw = reply.json()
    if not isinstance(raw.get("activities"), list):
        raise ValueError("活动源格式已变化")
    activities = []
    for item in raw["activities"]:
        start, end = (
            source_time(item.get("startTime", "")),
            source_time(item.get("endTime", "")),
        )
        if not item.get("name") or not start or timestamp(end) <= timestamp(start):
            continue
        activities.append(dict(item, startTime=start, endTime=end))
    return dict(
        raw,
        activities=activities,
        startTime=source_time(raw.get("startTime", "")),
        endTime=source_time(raw.get("endTime", "")),
        source="SRA",
    )


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
        "CharacterTable",
        "ActivityTagTable",
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        activities, times, texts, pools, characters, tags = pool.map(
            lambda name: fetch(root + name + ".json"), names
        )

    def name(reference, fallback=""):
        return texts.get(str((reference or {}).get("id")), fallback)

    def items(table, *, pools=False):
        output = []
        for key, item in table.items():
            time_id = (
                item.get("clientTopTimeId" if pools else "timeId") or "time_" + key
            )
            periods = times.get(time_id, {}).get("timeRangeList") or []
            if not periods:
                continue
            period = periods[0]
            start, end = (
                source_time(period.get("openTime", "")),
                source_time(period.get("closeTime", "")),
            )
            if not end or (start and timestamp(end) <= timestamp(start)):
                continue
            image = item.get("tabImg")
            cover = (
                (
                    AKE
                    + "/public/images/assets/beyond/dynamicassets/gameplay/ui/sprites/activity/"
                    + image
                    + ".png"
                )
                if image
                else ""
            )
            up = item.get("upCharIds") or []
            if pools:
                cover = (
                    (
                        AKE
                        + "/public/images/assets/beyond/dynamicassets/gameplay/ui/sprites/charremoteicon/icon_"
                        + str(up[0])
                        + ".png"
                    )
                    if up
                    else ""
                )
            labels = (
                [POOL_TYPES.get(item.get("type"), "角色寻访")]
                if pools
                else [
                    name(tags.get(str(tag), {}).get("name"), str(tag))
                    for tag in item.get("tagIds", [])
                ]
            )
            output.append(
                dict(
                    name=name(item.get("name"), key),
                    startTime=start,
                    endTime=end,
                    cover=cover,
                    tags=labels,
                    kind=" / ".join(labels),
                    description="UP · "
                    + "、".join(
                        name(characters.get(str(char), {}).get("name"), str(char))
                        for char in up
                    )
                    if up
                    else "",
                    sortId=item.get("sortId", len(output)),
                )
            )
        return output

    # AKE manifest 版本号是数据表版本，不能用作当前活动版本的横幅。
    return dict(
        activities=items(activities), pools=items(pools, pools=True), source="AKEData"
    )


def _activity_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).strip()
    quoted = re.fullmatch(
        r'[「『“"](.+)[」』”"](?:\s*(?:限时挑战|趣味活动|签到活动|引入活动|拍照活动|限时活动|挑战活动|叙事活动))?',
        text,
    )
    return re.sub(r'[\s「」『』“”"]', "", quoted[1] if quoted else text).lower()


def merge_endfield(
    sra: dict | None, ake: dict | None, errors: dict, pending: set
) -> dict:
    now = datetime.now(timezone.utc).timestamp()
    primary = sra or ake or {}
    result = dict(primary)
    result["activities"] = []
    candidates = (ake or {}).get("activities", [])
    for item in primary.get("activities", []):
        if timestamp(item["endTime"]) <= now:
            continue
        if not sra and timestamp(item["startTime"]) > now:
            continue
        row = dict(item)
        if sra:
            matches = [
                candidate
                for candidate in candidates
                if _activity_name(candidate["name"]) == _activity_name(item["name"])
                and timestamp(candidate["startTime"]) == timestamp(item["startTime"])
                and abs(timestamp(candidate["endTime"]) - timestamp(item["endTime"]))
                <= 1
            ]
            duplicates = [
                other
                for other in sra["activities"]
                if _activity_name(other["name"]) == _activity_name(item["name"])
                and timestamp(other["startTime"]) == timestamp(item["startTime"])
            ]
            row["cover"] = (
                matches[0]["cover"] if len(matches) == len(duplicates) == 1 else ""
            )
        result["activities"].append(row)
    result["pools"] = [
        row
        for row in (ake or {}).get("pools", [])
        if timestamp(row["startTime"]) <= now < timestamp(row["endTime"])
    ]
    result["poolsLoading"] = "ake" in pending
    result["poolError"] = errors.get("ake", "")
    result["activityError"] = errors.get("sra", "")
    result["source"] = "SRA / AKEData" if sra else "AKEData"
    return result


def public_feed(game: str) -> dict:
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        if game != "reverse1999":
            return sra_feed(client, game)
        reply = client.get("https://api.1999.fan/api/data/activity/cn.json")
        reply.raise_for_status()
        data = reply.json()
        now = datetime.now(timezone.utc).timestamp() * 1000
        versions = [
            (key, value) for key, value in data.items() if isinstance(value, dict)
        ]
        active = [
            v
            for v in versions
            if (v[1].get("start_time") or 0) <= now < (v[1].get("end_time") or 0)
        ]
        upcoming = sorted(
            [v for v in versions if (v[1].get("start_time") or 0) > now],
            key=lambda v: v[1]["start_time"],
        )
        ended = sorted(versions, key=lambda v: v[1].get("end_time") or 0, reverse=True)
        if not (active or upcoming or ended):
            raise ValueError("没有可用的版本日程")
        key, version = (active or upcoming or ended)[0]

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
            for key, item in (version.get("activity") or {}).items()
        ]
        return dict(
            version=key,
            versionName=version.get("version_name", ""),
            startTime=stamp(version.get("start_time")),
            endTime=stamp(version.get("end_time")),
            cover="https://re.bluepoch.com/assets/img/BG.jpg",
            activities=rows,
            source="1999.fan",
        )


class ActivityFeed(QObject):
    received = Signal(str, int, str)

    @Slot(str, int)
    def load(self, game: str, version: int) -> None:
        if game not in SRA and game != "reverse1999":
            return

        def emit(result):
            self.received.emit(game, version, json.dumps(result, ensure_ascii=False))

        def fetch():
            if game != "endfield":
                try:
                    emit(dict(code=200, data=public_feed(game)))
                except (
                    httpx.HTTPError,
                    ValueError,
                    KeyError,
                    TypeError,
                    OSError,
                ) as exc:
                    emit(dict(code=503, message=f"活动源读取失败：{exc}"))
                return
            values, errors, pending = {}, {}, {"sra", "ake"}
            with (
                httpx.Client(timeout=15, follow_redirects=True) as client,
                ThreadPoolExecutor(max_workers=2) as pool,
            ):
                futures = {
                    pool.submit(sra_feed, client, game): "sra",
                    pool.submit(endfield, client): "ake",
                }
                for future in as_completed(futures):
                    source = futures[future]
                    pending.remove(source)
                    try:
                        values[source] = future.result()
                    except (
                        httpx.HTTPError,
                        ValueError,
                        KeyError,
                        TypeError,
                        OSError,
                        StopIteration,
                    ) as exc:
                        errors[source] = f"{source.upper()} 读取失败：{exc}"
                    if values:
                        emit(
                            dict(
                                code=200,
                                partial=bool(pending),
                                data=merge_endfield(
                                    values.get("sra"),
                                    values.get("ake"),
                                    errors,
                                    pending,
                                ),
                            )
                        )
                    elif not pending:
                        emit(dict(code=503, message="；".join(errors.values())))

        QThreadPool.globalInstance().start(QRunnable.create(fetch))
