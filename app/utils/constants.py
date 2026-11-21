#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2024-2025 DLmaster361
#   Copyright © 2025 ClozyA
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


import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC4 = timezone(timedelta(hours=4))
"""东4区时区对象"""

UTC8 = timezone(timedelta(hours=8))
"""东8区时区对象"""

TYPE_BOOK = {
    "MaaConfig": "MAA",
    "SrcConfig": "SRC",
    "MaaEndConfig": "MaaEnd",
    "GeneralConfig": "通用",
    "OkwwConfig": "ok-ww",
    "OkNteConfig": "OK-NTE",
    "M9AConfig": "M9A",
    "M9AUserConfig": "M9A",
    "MaaFWConfig": "MFW",
    "HSRConfig": "HSR",
    "BetterGIConfig": "BetterGI",
    "ZzzOdConfig": "ZZZ-OD",
    "BAAHConfig": "BAAH",
    "WhimboxConfig": "奇想盒",
    "MSSConfig": "MSS",
}
"""配置类型映射表"""


ARKNIGHTS_GAME_DAY_TZ = {
    "Official": UTC4,
    "Bilibili": UTC4,
    "txwy": UTC4,
    "YoStarEN": timezone(timedelta(hours=-11)),
    "YoStarJP": timezone(timedelta(hours=5)),
    "YoStarKR": timezone(timedelta(hours=5)),
}
"""明日方舟各区服的游戏日时区：服务器当地 04:00 换日，即服务器时区减 4 小时

来源 MAA `src/MaaWpfGui/Extensions/DateTimeExtension.cs`：`_clientTypeTimezone`
中 Official / Bilibili / txwy 为 UTC+8，YoStarEN 为 UTC-7（固定偏移，不随夏令时），
YoStarJP / YoStarKR 为 UTC+9；`YjDayStartHour = 4`。
前端 `frontend/src/views/MAAUserEdit/periodMarkers.ts` 的 ARKNIGHTS_GAME_DAY_OFFSET
是同一张表，改动时两边同步。
"""


def get_game_day_tz(server: str | None) -> timezone:
    """按明日方舟区服取游戏日时区，未知或空区服回落到东4区。"""

    return ARKNIGHTS_GAME_DAY_TZ.get(server or "", UTC4)


def game_now(server: str | None) -> datetime:
    """按明日方舟区服的游戏日时区取当前时间，其日期即当前游戏日。"""

    return datetime.now(tz=get_game_day_tz(server))


EMULATOR_PATH_BOOK = {
    "mumu": {
        "name": "MuMu模拟器",
        "executables": ["MuMuManager.exe", "MuMuPlayer.exe"],
        # DisplayName 子串匹配；避免裸 "MuMu" 以防误匹配 MuMuPlugin 等。
        "registry_display_keywords": [
            "MuMu Player",
            "MuMuPlayer",
            "Netease MuMu",
            "MuMu模拟器",
            "YXArkNights",
            "YXReverse1999",
        ],
        "registry_paths": [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        ],
    },
    "ldplayer": {
        "name": "雷电模拟器",
        "executables": ["ldconsole.exe", "LDPlayer.exe", "dnplayer.exe"],
        # 关键词用完整产品名/英文，避免单字「雷电」误匹配。
        "registry_display_keywords": [
            "LDPlayer",
            "雷电模拟器",
            "leidian",
            "XuanZhi LDPlayer",
        ],
        "registry_paths": [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        ],
    },
    "nox": {
        "name": "夜神模拟器",
        # executables[0] 为多开管理器；卸载项常见旁路为 Nox.exe（同 bin 目录）
        "executables": ["MultiPlayerManager.exe", "Nox.exe", "NoxVMHandle.exe"],
        "registry_display_keywords": [
            "NoxPlayer",
            "Nox APP Player",
            "BigNox",
        ],
        "registry_paths": [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        ],
    },
    "memu": {
        "name": "逍遥模拟器",
        "executables": ["MEmuConsole.exe", "MEmu.exe", "MemuManager.exe"],
        "registry_display_keywords": [
            "MEmu",
            "Microvirt",
            "逍遥",
            "逍遥模拟器",
        ],
        "registry_paths": [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        ],
    },
    "bluestacks": {
        "name": "BlueStacks",
        # executables[0] 为多开管理器；卸载项/快捷方式常见旁路为 HD-Player.exe
        "executables": [
            "HD-MultiInstanceManager.exe",
            "HD-Player.exe",
            "BlueStacks.exe",
        ],
        "registry_display_keywords": [
            "BlueStacks",
            "BlueStacks_nxt",
            "BlueStacks X",
        ],
        "registry_paths": [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        ],
    },
}
"""模拟器文件常规路径信息"""

RESOURCE_STAGE_INFO = [
    {"value": "-", "text": "禁用", "days": [1, 2, 3, 4, 5, 6, 7]},
    {"value": "*", "text": "当前/上次", "days": [1, 2, 3, 4, 5, 6, 7]},
    {"value": "1-7", "text": "1-7", "days": [1, 2, 3, 4, 5, 6, 7]},
    {"value": "R8-11", "text": "R8-11", "days": [1, 2, 3, 4, 5, 6, 7]},
    {"value": "12-17-HARD", "text": "12-17-HARD", "days": [1, 2, 3, 4, 5, 6, 7]},
    {"value": "LS-6", "text": "经验-6/5", "days": [1, 2, 3, 4, 5, 6, 7]},
    {"value": "CE-6", "text": "龙门币-6/5", "days": [2, 4, 6, 7]},
    {"value": "AP-5", "text": "红票-5", "days": [1, 4, 6, 7]},
    {"value": "CA-5", "text": "技能-5", "days": [2, 3, 5, 7]},
    {"value": "SK-5", "text": "碳-5", "days": [1, 3, 5, 6]},
    {"value": "PR-A-1", "text": "奶/盾芯片", "days": [1, 4, 5, 7]},
    {"value": "PR-A-2", "text": "奶/盾芯片组", "days": [1, 4, 5, 7]},
    {"value": "PR-B-1", "text": "术/狙芯片", "days": [1, 2, 5, 6]},
    {"value": "PR-B-2", "text": "术/狙芯片组", "days": [1, 2, 5, 6]},
    {"value": "PR-C-1", "text": "先/辅芯片", "days": [3, 4, 6, 7]},
    {"value": "PR-C-2", "text": "先/辅芯片组", "days": [3, 4, 6, 7]},
    {"value": "PR-D-1", "text": "近/特芯片", "days": [2, 3, 6, 7]},
    {"value": "PR-D-2", "text": "近/特芯片组", "days": [2, 3, 6, 7]},
]
"""常规资源关信息"""


MATERIALS_MAP = {
    "3141": "源石碎片",
    "3003": "赤金",
    "4006": "采购凭证",
    "3301": "技巧概要·卷1",
    "3302": "技巧概要·卷2",
    "3303": "技巧概要·卷3",
    "30051": "双酮",
    "30052": "酮凝集",
    "30053": "酮凝集组",
    "30054": "酮阵列",
    "30041": "异铁碎片",
    "30042": "异铁",
    "30043": "异铁组",
    "30044": "异铁块",
    "30021": "代糖",
    "30022": "糖",
    "30023": "糖组",
    "30024": "糖聚块",
    "30031": "酯原料",
    "30032": "聚酸酯",
    "30033": "聚酸酯组",
    "30034": "聚酸酯块",
    "30061": "破损装置",
    "30062": "装置",
    "30063": "全新装置",
    "30064": "改量装置",
    "30011": "源岩",
    "30012": "固源岩",
    "30013": "固源岩组",
    "30014": "提纯源岩",
    "30103": "RMA70-12",
    "30104": "RMA70-24",
    "30093": "研磨石",
    "30094": "五水研磨石",
    "30083": "轻锰矿",
    "30084": "三水锰矿",
    "30073": "扭转醇",
    "30074": "白马醇",
    "31013": "凝胶",
    "31014": "聚合凝胶",
    "31023": "炽合金",
    "31024": "炽合金块",
    "31033": "晶体元件",
    "31034": "晶体电路",
    "31043": "半自然溶剂",
    "31044": "精炼溶剂",
    "31053": "化合切削液",
    "31054": "切削原液",
    "31063": "转质盐组",
    "31064": "转质盐聚块",
    "31073": "褐素纤维",
    "31074": "固化纤维板",
    "31083": "环烃聚质",
    "31084": "环烃预制体",
    "31093": "类凝结核",
    "31094": "手性屈光体",
    "31103": "液化高能气体",
    "31104": "液化醚吸聚体",
    "31113": "电极单元",
    "31114": "聚能动力单元",
    "30115": "聚合剂",
    "30125": "双极纳米片",
    "30135": "D32钢",
    "30145": "晶体电子单元",
    "30155": "烧结核凝晶",
    "30165": "重相位对映体",
    "3105": "龙骨",
    "3401": "家具零件",
    "3131": "基础加固建材",
    "3132": "进阶加固建材",
    "3133": "高级加固建材",
    "3112": "碳",
    "3113": "碳素",
    "3114": "碳素组",
    "32001": "芯片助剂",
    "3213": "先锋双芯片",
    "3223": "近卫双芯片",
    "3233": "重装双芯片",
    "3243": "狙击双芯片",
    "3253": "术师双芯片",
    "3263": "医疗双芯片",
    "3273": "辅助双芯片",
    "3283": "特种双芯片",
    "3212": "先锋芯片组",
    "3222": "近卫芯片组",
    "3232": "重装芯片组",
    "3242": "狙击芯片组",
    "3252": "术师芯片组",
    "3262": "医疗芯片组",
    "3272": "辅助芯片组",
    "3282": "特种芯片组",
    "3211": "先锋芯片",
    "3221": "近卫芯片",
    "3231": "重装芯片",
    "3241": "狙击芯片",
    "3251": "术师芯片",
    "3261": "医疗芯片",
    "3271": "辅助芯片",
    "3281": "特种芯片",
    "PR-A": "医疗/重装芯片",
    "PR-B": "术师/狙击芯片",
    "PR-C": "先锋/辅助芯片",
    "PR-D": "近卫/特种芯片",
}
"""掉落物索引表"""


TIME_FIELDS = {
    "%Y": "year",
    "%m": "month",
    "%d": "day",
    "%H": "hour",
    "%M": "minute",
    "%S": "second",
    "%f": "microsecond",
}
"""时间字段映射表"""

RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}
"""Windows保留名称列表"""

ILLEGAL_CHARS = set('<>:"/\\|?*')
"""文件名非法字符集合"""

KEYBOARD_KEYS = frozenset(
    [
        "\t",
        "\n",
        "\r",
        " ",
        "!",
        '"',
        "#",
        "$",
        "%",
        "&",
        "'",
        "(",
        ")",
        "*",
        "+",
        ",",
        "-",
        ".",
        "/",
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        ":",
        ";",
        "<",
        "=",
        ">",
        "?",
        "@",
        "[",
        "\\",
        "]",
        "^",
        "_",
        "`",
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "q",
        "r",
        "s",
        "t",
        "u",
        "v",
        "w",
        "x",
        "y",
        "z",
        "{",
        "|",
        "}",
        "~",
        "accept",
        "add",
        "alt",
        "altleft",
        "altright",
        "apps",
        "backspace",
        "browserback",
        "browserfavorites",
        "browserforward",
        "browserhome",
        "browserrefresh",
        "browsersearch",
        "browserstop",
        "capslock",
        "clear",
        "convert",
        "ctrl",
        "ctrlleft",
        "ctrlright",
        "decimal",
        "del",
        "delete",
        "divide",
        "down",
        "end",
        "enter",
        "esc",
        "escape",
        "execute",
        "f1",
        "f10",
        "f11",
        "f12",
        "f13",
        "f14",
        "f15",
        "f16",
        "f17",
        "f18",
        "f19",
        "f2",
        "f20",
        "f21",
        "f22",
        "f23",
        "f24",
        "f3",
        "f4",
        "f5",
        "f6",
        "f7",
        "f8",
        "f9",
        "final",
        "fn",
        "hanguel",
        "hangul",
        "hanja",
        "help",
        "home",
        "insert",
        "junja",
        "kana",
        "kanji",
        "launchapp1",
        "launchapp2",
        "launchmail",
        "launchmediaselect",
        "left",
        "modechange",
        "multiply",
        "nexttrack",
        "nonconvert",
        "num0",
        "num1",
        "num2",
        "num3",
        "num4",
        "num5",
        "num6",
        "num7",
        "num8",
        "num9",
        "numlock",
        "pagedown",
        "pageup",
        "pause",
        "pgdn",
        "pgup",
        "playpause",
        "prevtrack",
        "print",
        "printscreen",
        "prntscrn",
        "prtsc",
        "prtscr",
        "return",
        "right",
        "scrolllock",
        "select",
        "separator",
        "shift",
        "shiftleft",
        "shiftright",
        "sleep",
        "space",
        "stop",
        "subtract",
        "tab",
        "up",
        "volumedown",
        "volumemute",
        "volumeup",
        "win",
        "winleft",
        "winright",
        "yen",
        "command",
        "option",
        "optionleft",
        "optionright",
    ]
)
"""键盘按键名称集合 (与 pyautogui.KEYBOARD_KEYS 一致, 内联以避免启动时导入 pyautogui)"""

MIRROR_ERROR_INFO = {
    1001: "获取版本信息的URL参数不正确",
    7001: "填入的 CDK 已过期",
    7002: "填入的 CDK 错误",
    7003: "填入的 CDK 今日下载次数已达上限",
    7004: "填入的 CDK 类型和待下载的资源不匹配",
    7005: "填入的 CDK 已被封禁",
    8001: "对应架构和系统下的资源不存在",
    8002: "错误的系统参数",
    8003: "错误的架构参数",
    8004: "错误的更新通道参数",
    1: "未知错误类型",
}
"""MirrorChyan错误代码映射表"""

DEFAULT_DATETIME = datetime.strptime("2000-01-01 00:00:00", "%Y-%m-%d %H:%M:%S")
"""默认日期时间"""


SKLAND_SM_CONFIG = {
    "organization": "UWXspnCCJN4sfYlNfqps",
    "appId": "default",
    "publicKey": "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCmxMNr7n8ZeT0tE1R9j/mPixoinPkeM+k4VGIn/s0k7N5rJAfnZ0eMER+QhwFvshzo0LNmeUkpR8uIlU/GEVr8mN28sKmwd2gpygqj0ePnBmOW4v0ZVwbSYK+izkhVFk2V/doLoMbWy6b+UnA8mkjvg0iYWRByfRsK2gdl7llqCwIDAQAB",
    "protocol": "https",
    "apiHost": "fp-it.portal101.cn",
    "apiPath": "/deviceprofile/v4",
}
"""数美科技配置"""

BROWSER_ENV = {
    "plugins": "MicrosoftEdgePDFPluginPortableDocumentFormatinternal-pdf-viewer1,MicrosoftEdgePDFViewermhjfbmdgcfjbbpaeojofohoefgiehjai1",
    "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    "canvas": "259ffe69",  # 基于浏览器的canvas获得的值
    "timezone": -480,  # 时区
    "platform": "Win32",
    "url": "https://www.skland.com/",  # 固定值
    "referer": "",
    "res": "1920_1080_24_1.25",  # 屏幕宽度_高度_色深_window.devicePixelRatio
    "clientSize": "0_0_1080_1920_1920_1080_1920_1080",
    "status": "0011",  # 不知道在干啥
}
"""浏览器环境模拟"""

DES_RULE = {
    "appId": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "uy7mzc4h",
        "obfuscated_name": "xx",
    },
    "box": {
        "is_encrypt": 0,
        "obfuscated_name": "jf",
    },
    "canvas": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "snrn887t",
        "obfuscated_name": "yk",
    },
    "clientSize": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "cpmjjgsu",
        "obfuscated_name": "zx",
    },
    "organization": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "78moqjfc",
        "obfuscated_name": "dp",
    },
    "os": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "je6vk6t4",
        "obfuscated_name": "pj",
    },
    "platform": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "pakxhcd2",
        "obfuscated_name": "gm",
    },
    "plugins": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "v51m3pzl",
        "obfuscated_name": "kq",
    },
    "pmf": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "2mdeslu3",
        "obfuscated_name": "vw",
    },
    "protocol": {
        "is_encrypt": 0,
        "obfuscated_name": "protocol",
    },
    "referer": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "y7bmrjlc",
        "obfuscated_name": "ab",
    },
    "res": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "whxqm2a7",
        "obfuscated_name": "hf",
    },
    "rtype": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "x8o2h2bl",
        "obfuscated_name": "lo",
    },
    "sdkver": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "9q3dcxp2",
        "obfuscated_name": "sc",
    },
    "status": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "2jbrxxw4",
        "obfuscated_name": "an",
    },
    "subVersion": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "eo3i2puh",
        "obfuscated_name": "ns",
    },
    "svm": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "fzj3kaeh",
        "obfuscated_name": "qr",
    },
    "time": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "q2t3odsk",
        "obfuscated_name": "nb",
    },
    "timezone": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "1uv05lj5",
        "obfuscated_name": "as",
    },
    "tn": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "x9nzj1bp",
        "obfuscated_name": "py",
    },
    "trees": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "acfs0xo4",
        "obfuscated_name": "pi",
    },
    "ua": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "k92crp1t",
        "obfuscated_name": "bj",
    },
    "url": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "y95hjkoo",
        "obfuscated_name": "cf",
    },
    "version": {
        "is_encrypt": 0,
        "obfuscated_name": "version",
    },
    "vpw": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "r9924ab5",
        "obfuscated_name": "ca",
    },
}
"""DES加密规则"""


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
"""匹配ANSI控制字符的正则表达式"""

TASK_MODE_ZH = {
    "AutoProxy": "自动代理",
    "ScriptConfig": "脚本配置",
}
"""任务模式中文映射表"""

APPDATA_PATH = Path(os.getenv("APPDATA") or "")
"""APPDATA路径"""

FORBIDDEN_PATH_PREFIXES: tuple[Path, ...] = tuple(
    Path(env_value).resolve()
    for key in ("SystemRoot",)
    for env_value in [os.environ.get(key, r"C:\Windows")]
    if env_value and Path(env_value).is_dir()
)
"""禁止作为配置路径的前缀目录（自身、子目录或父目录均非法，如系统目录；校验时另含当前工作目录）"""

FORBIDDEN_PATH_EXACT: tuple[Path, ...] = tuple(
    Path(env_value).resolve()
    for key in ("ProgramFiles", "ProgramFiles(x86)")
    for env_value in [os.environ.get(key, "")]
    if env_value and Path(env_value).is_dir()
)
"""禁止精确匹配的目录根（仅根目录非法，子目录如软件配置路径仍允许）"""

EMULATOR_SPLASH_ADS_PATH_BOOK = {
    "mumu": [
        APPDATA_PATH / "Netease/MuMuPlayer-12.0/data/startupImage",
        APPDATA_PATH / "Netease/MuMuPlayer/data/startupImage",
    ],
    "ldplayer": [APPDATA_PATH / "leidian9/cache"],
}
"""模拟器启动时广告路径"""

CYCLE_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
"""循环队列时间字段的持久化格式"""

CYCLE_EMPTY_TIME = "2000-01-01 00:00:00"
"""循环队列时间字段的空值哨兵，表示「尚未推算」而非某个真实时刻"""

BASE_SHARED = "shared"
"""base 来源：脚本级共享配置（旧字面量「脚本」/「简洁」）"""

BASE_INDEPENDENT = "independent"
"""base 来源：用户独立配置（旧字面量「用户」/「详细」/「自定义」）"""

BASE_NATIVE = "native"
"""base 来源：脚本原生配置（旧字面量「直控」）"""

LEGACY_BASE_SOURCES = {
    "脚本": BASE_SHARED,
    "用户": BASE_INDEPENDENT,
    "直控": BASE_NATIVE,
    "简洁": BASE_SHARED,
    "详细": BASE_INDEPENDENT,
    "自定义": BASE_INDEPENDENT,
}
"""旧配置来源字面量 → base 来源：只出现在存量数据与旧备份里，读取时归一"""


def normalize_base_source(value: object) -> str:
    """把配置来源值归一为 base 来源三态（shared / independent / native）。

    无法识别的值原样返回，由调用方决定是否回落；空值返回空串。
    """

    text = str(value or "").strip()
    return LEGACY_BASE_SOURCES.get(text, text)


BASE_SOURCE_LABELS = {
    BASE_SHARED: "共享",
    BASE_INDEPENDENT: "独立",
    BASE_NATIVE: "原生",
}
"""base 来源三态的展示词表（后端预览等无前端 i18n 处使用）"""
