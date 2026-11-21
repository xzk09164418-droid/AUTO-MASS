"""调度中心多队列同时运行的演示：注入一份模拟的运行快照（不启动任何真实任务），依次截图。

用法：.venv/Scripts/python.exe qt/tools/demo_dispatch.py <repo> <out_dir> [standard|enhanced]
截图：dispatch_overview / dispatch_q1 / dispatch_q1_log / dispatch_cycle / dispatch_cycle_next
"""
import json
import sys
from pathlib import Path

repo = Path(sys.argv[1]); out = Path(sys.argv[2]); motion = sys.argv[3] if len(sys.argv) > 3 else "standard"
sys.argv = [sys.argv[0], "--skip-boot", "--section", "5", "--motion", motion, "--size", "1920x1061", "--theme", "light"]
sys.path.insert(0, str(repo / "qt"))
import main as qtmain  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine as _E  # noqa: E402

ENG = []


class Eng(_E):
    def __init__(self, *a):
        super().__init__(*a)
        ENG.append(self)


qtmain.QQmlApplicationEngine = Eng
from PySide6.QtCore import QMetaObject, QObject, QTimer, Q_ARG  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402


def user(name, status):
    return {"user_id": name, "name": name, "status": status}


def script(name, status, users=()):
    return {"script_id": name, "name": name, "status": status, "userList": list(users)}


def log(*lines):
    return "\n".join(lines)


SNAPSHOT = {
    "queueNames": {"q-daily": "日常托管", "q-weekly": "周常收尾", "q-night": "夜间循环"},
    "scheduledScripts": [{"scriptId": f"s{i}", "scriptType": "General"} for i in range(6)],
    "tasks": [
        {
            "taskId": "t-daily", "mode": "AutoProxy", "isCycle": False, "queueId": "q-daily", "stopping": False,
            "scripts": [], "cycleNextList": [], "logSeq": 0,
            "task_info": [
                script("事先准备：最小化窗口", "完成"),
                script("1.游戏更新", "完成"),
                script("2.米游社签到", "完成", [user("主号", "完成"), user("小号", "完成")]),
                script("3.启用游戏1080p启动参数", "运行", [user("主号", "完成"), user("小号", "运行"), user("三号", "等待")]),
                script("崩铁前：1080p窗口化与输入法", "等待"),
                script("March7thAssistant", "等待", [user("主号", "等待"), user("小号", "等待")]),
                script("崩铁后：恢复显示设置", "等待"),
            ],
            "log": log(
                "2026-11-20 21:02:11 [日常托管] 开始执行队列，共 7 个脚本",
                "2026-11-20 21:02:12 事先准备：最小化窗口 完成",
                "2026-11-20 21:03:40 1.游戏更新 完成（无可用更新）",
                "2026-11-20 21:05:02 2.米游社签到 主号 签到成功",
                "2026-11-20 21:05:09 2.米游社签到 小号 签到成功",
                "2026-11-20 21:05:10 3.启用游戏1080p启动参数 开始",
                "2026-11-20 21:05:31 3.启用游戏1080p启动参数 主号 完成",
                "2026-11-20 21:05:33 3.启用游戏1080p启动参数 小号 运行中…",
            ),
        },
        {
            "taskId": "t-weekly", "mode": "AutoProxy", "isCycle": False, "queueId": "q-weekly", "stopping": False,
            "scripts": [], "cycleNextList": [], "logSeq": 0,
            "task_info": [
                script("绝区零一条龙", "完成", [user("主号", "完成")]),
                script("新 MaaEnd 脚本", "异常", [user("主号", "异常")]),
                script("BetterGI", "运行", [user("主号", "运行")]),
                script("7.异环自动化", "等待"),
            ],
            "log": log(
                "2026-11-20 21:00:02 [周常收尾] 开始执行队列，共 4 个脚本",
                "2026-11-20 21:12:47 绝区零一条龙 主号 完成",
                "2026-11-20 21:13:05 新 MaaEnd 脚本 主号 异常：未找到游戏窗口，已按重试次数结束",
                "2026-11-20 21:13:06 BetterGI 主号 开始",
                "2026-11-20 21:14:21 BetterGI 主号 自动秘境 第 2 轮",
            ),
        },
        {
            "taskId": "t-night", "mode": "AutoProxy", "isCycle": True, "queueId": "q-night", "stopping": False,
            "scripts": [], "logSeq": 0,
            "task_info": [
                script("8.0 鸣潮配置校正", "完成"),
                script("8.1 鸣潮启动准备", "运行", [user("主号", "运行")]),
                script("8.2 鸣潮自动化", "等待", [user("主号", "等待")]),
            ],
            "cycleNextList": [
                {"queueItemId": "i1", "scriptId": "a", "scriptName": "8.1 鸣潮启动准备", "nextRunAt": "2026-11-20 21:10:00", "isDue": True, "isRunning": True},
                {"queueItemId": "i2", "scriptId": "b", "scriptName": "8.2 鸣潮自动化", "nextRunAt": "2026-11-20 21:20:00", "isDue": False, "isRunning": False},
                {"queueItemId": "i3", "scriptId": "c", "scriptName": "8.0 鸣潮配置校正", "nextRunAt": "2026-11-21 05:00:00", "isDue": False, "isRunning": False},
            ],
            "log": log(
                "2026-11-20 21:00:00 [夜间循环] 循环运行开始",
                "2026-11-20 21:01:15 8.0 鸣潮配置校正 完成",
                "2026-11-20 21:10:00 8.1 鸣潮启动准备 到点，开始",
            ),
        },
    ],
}

orig = QGuiApplication.exec


def patched(self=None):
    app = QGuiApplication.instance()
    import shiboken6
    from PySide6.QtQuick import QQuickWindow
    root = ENG[0].rootObjects()[0]
    win = shiboken6.wrapInstance(shiboken6.getCppPointer(root)[0], QQuickWindow)
    sv = root.findChild(QObject, "sections")
    panel = root.findChild(QObject, "archivePanel")
    pump = QTimer(); pump.setInterval(30); pump.timeout.connect(lambda: win.grabWindow()); pump.start()
    patched.pump = pump

    def inject():
        from PySide6.QtQml import QJSValue  # noqa: F401
        engine = ENG[0]
        sv.setProperty("demoSnapshot", engine.toScriptValue(json.loads(json.dumps(SNAPSHOT))))
        QMetaObject.invokeMethod(sv, "fetchLive", Q_ARG("QVariant", "scheduler"))

    def shot(name):
        win.grabWindow().save(str(out / f"{name}.png"))

    def sel(k):
        QMetaObject.invokeMethod(sv, "select", Q_ARG("QVariant", k), Q_ARG("QVariant", 0))

    plan = [
        (2500, inject),
        (5500, lambda: shot("dispatch_overview")),
        (5600, lambda: sel(1)), (7600, lambda: shot("dispatch_q1")),
        (7700, lambda: panel.setProperty("tab", 1)), (9200, lambda: shot("dispatch_q1_log")),
        (9300, lambda: sel(3)), (11300, lambda: shot("dispatch_cycle")),
        (11400, lambda: panel.setProperty("tab", 2)), (12900, lambda: shot("dispatch_cycle_next")),
        (13000, lambda: print("items", sv.property("items") and len(sv.property("items").toVariant() if hasattr(sv.property("items"), "toVariant") else sv.property("items")), flush=True)),
        (13200, app.quit),
    ]
    for ms, fn in plan:
        QTimer.singleShot(ms, fn)
    return orig()


QGuiApplication.exec = staticmethod(patched)
sys.exit(qtmain.main())
