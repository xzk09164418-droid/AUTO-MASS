"""Qt 客户端的后端监督器。

先探测本安装实例的后端是否已在运行
（GET /api/core/health，且 instanceId 与本数据根一致）；没有就用 .venv 的解释器拉起
``main.py --port N --no-admin-restart``，轮询健康接口直到就绪或超时。后端代码不做任何改动。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from typing import Callable

from PySide6.QtCore import (
    Property,
    QCoreApplication,
    QObject,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)
from PySide6.QtQml import QJSValue

from .events import BackendEvents

ROOT_DIR = Path(__file__).resolve().parents[2]
HEALTH_PATH = "/api/core/health"
POLL_INTERVAL_MS = 500
START_TIMEOUT_MS = 120_000
MAX_LOG_LINES = 200
# 后端日志带终端配色（ANSI 转义序列），显示前去掉
ANSI_PATTERN = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
LOG_LEVEL_PATTERN = re.compile(r"\|\s*(DEBUG|INFO|SUCCESS|WARNING|ERROR|CRITICAL)\s*\|")

# 启动阶段与进度（0–1）。后端日志里的固定标记推进进度，健康检查的 backgroundStatus 收尾。
# 后台初始化共 7 步（main.py initialize_background_services），每完成一步推进一格。
BACKGROUND_STEPS = 7
STEP_DONE_PATTERN = re.compile(r"后台初始化步骤结束: ([^，,]+)")
STAGE_MARKERS = (
    ("AUTO-MAS 后端应用程序", 0.15, "加载配置"),
    ("Application startup complete", 0.40, "核心服务就绪"),
)


def instance_id(root: Path = ROOT_DIR) -> str:
    """与 app/services/instance_identity.backend_instance_id 相同的算法。"""

    canonical = str(root.resolve()).replace("\\", "/").rstrip("/").lower()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def backend_port(root: Path = ROOT_DIR) -> int:
    instance_file = root / "config" / "HostInstance.json"
    if instance_file.exists():
        port = json.loads(instance_file.read_text(encoding="utf-8")).get("backendPort")
        if isinstance(port, int) and 1024 <= port <= 65535:
            return port
    defaults = json.loads(
        (root / "res" / "host-instance-defaults.json").read_text(encoding="utf-8")
    )
    return int(defaults["backendPort"])


def _read_instance_file() -> dict:
    path = ROOT_DIR / "config" / "HostInstance.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        return {}


def downloads_dir() -> Path:
    """用户的「下载」文件夹；取不到时退回用户目录。"""
    from PySide6.QtCore import QStandardPaths

    folder = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DownloadLocation
    )
    path = Path(folder) if folder else Path.home()
    path.mkdir(parents=True, exist_ok=True)
    return path


def python_executable(root: Path = ROOT_DIR) -> str:
    for candidate in (
        root / ".venv" / "Scripts" / "pythonw.exe",
        root / ".venv" / "Scripts" / "python.exe",
        root / "venv" / "Scripts" / "python.exe",
        root / "python" / "python.exe",
        root / ".venv" / "bin" / "python",
    ):
        if candidate.exists():
            return str(candidate)
    return sys.executable


class BackendSupervisor(QObject):
    """暴露给 QML 的连接状态：probing → starting → ready，失败为 error。"""

    statusChanged = Signal()
    logsChanged = Signal()
    eventReceived = Signal(str, dict)
    connectionChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._status = "probing"
        self._message = ""
        self._background = ""
        self._progress = 0.0
        self._stage = ""
        self._steps_done = 0
        self.startup_arguments: list[str] = []
        self._logs: deque[dict[str, str]] = deque(maxlen=MAX_LOG_LINES)
        self._port = backend_port()
        self._expected_id = instance_id()
        self._network = QNetworkAccessManager(self)
        self._process: subprocess.Popen | None = None
        self._log_path = ROOT_DIR / "debug" / "qt-backend-launcher.log"
        self._log_position = 0
        self._probe_pending = False
        self._ever_ready = False
        self._replaced = False
        self._socket = BackendEvents(self)
        self._socket.changed.connect(self.connectionChanged)
        self._socket.disconnected.connect(self._disconnected)
        self._socket.messageReceived.connect(self._event)
        self._stopping = False
        self._started_at = time.monotonic()
        self._poll = QTimer(self)
        self._poll.setInterval(POLL_INTERVAL_MS)
        self._poll.timeout.connect(self._probe)

    # ── QML 属性 ────────────────────────────────────────────────────────────
    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(str, notify=statusChanged)
    def message(self) -> str:
        return self._message

    @Property(str, notify=statusChanged)
    def backgroundStatus(self) -> str:
        return self._background

    @Property(float, notify=statusChanged)
    def progress(self) -> float:
        return self._progress

    @Property(str, notify=statusChanged)
    def stage(self) -> str:
        return self._stage

    @Property(int, constant=True)
    def port(self) -> int:
        return self._port

    @Property("QVariantList", notify=logsChanged)
    def logs(self) -> list[dict[str, str]]:
        return list(self._logs)

    @Property(bool, notify=connectionChanged)
    def connected(self) -> bool:
        return self._socket.connected

    # ── 操作 ────────────────────────────────────────────────────────────────
    @Slot()
    def start(self) -> None:
        self._stopping = False
        self._replaced = False
        self._poll.setInterval(POLL_INTERVAL_MS)
        self._set_status("probing", "")
        self._steps_done = 0
        self._progress = 0.0
        self._set_progress(0.03, self.tr("连接后端"))
        self._started_at = time.monotonic()
        self._probe(first=True)

    @Slot()
    def retry(self) -> None:
        self._logs.clear()
        self.logsChanged.emit()
        self.start()

    @Slot()
    def shutdown(self) -> None:
        """释放客户端连接；后端只通过显式 /api/core/close 正常退出。"""

        self._poll.stop()
        self._stopping = True
        self._socket.close()

    def _disconnected(self, code: int) -> None:
        # 与 Web 一致：新前端接管后让位，禁止两个窗口无限互踢。
        if code == 4001:
            self._replaced = True
        self.connectionChanged.emit()

    def _event(self, text: str) -> None:
        try:
            envelope = json.loads(text)
        except ValueError:
            return
        if not isinstance(envelope, dict):
            return
        data = envelope.get("data")
        if isinstance(envelope.get("type"), str) and isinstance(data, dict):
            self.eventReceived.emit(envelope["type"], data)

    def _connect_events(self) -> None:
        if self._stopping or self._replaced or self._socket.running:
            return
        self._socket.start(
            f"ws://127.0.0.1:{self._port}/api/core/ws", self._expected_id
        )

    def call(
        self,
        path: str,
        body: dict | None,
        callback: Callable[[dict], None],
        *,
        timeout: int = 15000,
    ) -> None:
        """客户端控制器与 QML 共用的 HTTP 入口，保留后端返回的错误说明。"""
        request = QNetworkRequest(QUrl(f"http://127.0.0.1:{self._port}{path}"))
        request.setRawHeader(b"x-auto-mas-instance", self._expected_id.encode("ascii"))
        request.setTransferTimeout(timeout)
        if body is None:
            reply = self._network.get(request)
        else:
            request.setHeader(
                QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json"
            )
            reply = self._network.post(request, json.dumps(body).encode("utf-8"))

        def done() -> None:
            raw = bytes(reply.readAll().data())
            try:
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise ValueError("响应不是对象")
            except ValueError:
                result = {"code": 0, "message": reply.errorString() or "后端响应无效"}
            if reply.error() != QNetworkReply.NetworkError.NoError:
                result["transportError"] = reply.error().value
                result["code"] = (
                    result.get("code") if result.get("code", 200) != 200 else 0
                )
                result.setdefault("message", reply.errorString())
            reply.deleteLater()
            callback(result)

        reply.finished.connect(done)

    # ── 内部 ────────────────────────────────────────────────────────────────
    def _set_status(self, status: str, message: str) -> None:
        if (status, message) != (self._status, self._message):
            self._status, self._message = status, message
            self.statusChanged.emit()

    def _set_progress(self, value: float, stage: str) -> None:
        value = max(self._progress if value < 1 else 0, value)
        if (value, stage) != (self._progress, self._stage):
            self._progress, self._stage = min(1.0, value), stage
            self.statusChanged.emit()

    def _track_stage(self, line: str) -> None:
        for marker, value, stage in STAGE_MARKERS:
            if marker in line:
                self._set_progress(value, self.tr(stage))
                return
        done = STEP_DONE_PATTERN.search(line)
        if done:
            self._steps_done += 1
            value = (
                0.40 + 0.55 * min(self._steps_done, BACKGROUND_STEPS) / BACKGROUND_STEPS
            )
            self._set_progress(
                value, self.tr("初始化：{0}").format(done.group(1).strip())
            )

    def _append_log(self, line: str) -> None:
        line = ANSI_PATTERN.sub("", line).rstrip()
        if not line:
            return
        self._track_stage(line)
        match = LOG_LEVEL_PATTERN.search(line)
        self._logs.append({"level": match.group(1) if match else "", "text": line})
        self.logsChanged.emit()

    @Slot(str, str, "QJSValue")
    def request(self, path: str, body: str, callback: QJSValue) -> None:
        """POST 后端接口；body 为 JSON 字符串，callback(text) 收到响应 JSON 字符串（失败时 code 为 0）。"""

        try:
            payload = json.loads(body or "{}")
        except ValueError:
            payload = None
        if not isinstance(payload, dict):
            if callback.isCallable():
                callback.call([QJSValue('{"code":0,"message":"请求数据无效"}')])
            return
        self.call(path, payload, lambda result: self._reply_qml(callback, result))

    @staticmethod
    def _reply_qml(callback: QJSValue, result: dict) -> None:
        if callback.isCallable():
            callback.call([QJSValue(json.dumps(result, ensure_ascii=False))])

    @Slot(str, "QJSValue")
    def get(self, path: str, callback: QJSValue) -> None:
        """GET 后端接口，统一使用实例身份和错误响应处理。"""
        self.call(path, None, lambda result: self._reply_qml(callback, result))

    @Slot(result="QVariantMap")
    def ports(self) -> dict:
        """当前实例后端端口，来自 config/HostInstance.json。"""

        stored = _read_instance_file()
        defaults = json.loads(
            (ROOT_DIR / "res" / "host-instance-defaults.json").read_text(
                encoding="utf-8"
            )
        )
        return {
            "backendPort": stored.get("backendPort", defaults["backendPort"]),
        }

    @Slot(int, result=str)
    def savePorts(self, backend_port: int) -> str:
        """保存后端端口，下次启动时生效；保留已有的其它实例信息。"""

        if not 1024 <= backend_port <= 65535:
            return "端口必须为 1024～65535 的整数"
        stored = _read_instance_file()
        stored.update(
            {
                "instanceId": stored.get("instanceId") or self._expected_id,
                "backendPort": backend_port,
            }
        )
        target = ROOT_DIR / "config" / "HostInstance.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(f".{QCoreApplication.applicationPid()}.tmp")
        temporary.write_text(
            json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(target)
        return ""

    @Slot("QJSValue")
    def exportBackup(self, callback: QJSValue) -> None:
        """导出数据备份（GET /api/setting/backup 的压缩包）到「下载」文件夹；callback(结果 JSON)。"""

        request = QNetworkRequest(
            QUrl(f"http://127.0.0.1:{self._port}/api/setting/backup")
        )
        request.setRawHeader(b"x-auto-mas-instance", self._expected_id.encode("ascii"))
        request.setTransferTimeout(600000)
        reply = self._network.get(request)

        def done() -> None:
            reply.deleteLater()
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            body = bytes(reply.readAll().data())
            if (
                reply.error() != QNetworkReply.NetworkError.NoError
                or status != 200
                or body[:2] != b"PK"
            ):
                try:
                    message = json.loads(body.decode("utf-8")).get("message", "")
                except (ValueError, UnicodeDecodeError):
                    message = reply.errorString()
                result = {"ok": False, "message": message or "导出失败"}
            else:
                target = (
                    downloads_dir()
                    / f"AUTO-MAS-backup-{time.strftime('%Y-%m-%d-%H%M%S')}.zip"
                )
                target.write_bytes(body)
                result = {"ok": True, "path": str(target)}
            if callback.isCallable():
                callback.call([QJSValue(json.dumps(result, ensure_ascii=False))])

        reply.finished.connect(done)

    def _probe(self, first: bool = False) -> None:
        self._read_process()
        if self._stopping or self._probe_pending:
            return
        self._probe_pending = True
        request = QNetworkRequest(QUrl(f"http://127.0.0.1:{self._port}{HEALTH_PATH}"))
        request.setTransferTimeout(2000)
        reply = self._network.get(request)
        reply.finished.connect(lambda: self._on_health(reply, first))

    def _on_health(self, reply: QNetworkReply, first: bool) -> None:
        self._probe_pending = False
        reply.deleteLater()
        if self._stopping:
            return
        data = None
        if reply.error() == QNetworkReply.NetworkError.NoError:
            try:
                data = json.loads(bytes(reply.readAll().data()).decode("utf-8"))
                if not isinstance(data, dict):
                    data = None
            except ValueError:
                data = None

        if data is not None and data.get("instanceId") != self._expected_id:
            self._poll.stop()
            self._set_status(
                "error",
                self.tr("端口 {0} 上运行的后端不属于本安装目录，已拒绝连接").format(
                    self._port
                ),
            )
            return

        if data is not None and data.get("ready") is not False:
            background = str(data.get("backgroundStatus") or "")
            if background != self._background:
                self._background = background
                self.statusChanged.emit()
            if data.get("backgroundError"):
                self._poll.stop()
                self._set_status("error", str(data["backgroundError"]))
                return
            if background in ("", "ready", "failed"):
                # 后台初始化走完（或旧后端不报告）才算就绪，启动动画以此收尾
                self._ever_ready = True
                self._poll.setInterval(3000)
                self._poll.start()
                self._set_progress(1.0, self.tr("就绪"))
                self._set_status("ready", "")
                self._connect_events()
                self.submit_startup()
                return
            if (time.monotonic() - self._started_at) * 1000 >= START_TIMEOUT_MS:
                self._poll.stop()
                self._set_status("error", self.tr("后端启动超时"))
                return
            # 核心接口已通、后台仍在初始化：继续轮询，进度由日志推进
            self._set_progress(0.40, self._stage or self.tr("核心服务就绪"))
            if not self._poll.isActive():
                self._set_status("starting", "")
                self._poll.start()
            return

        if first:
            self._spawn()
            return

        if self._ever_ready:
            self._set_status("error", self.tr("后端连接已断开，正在等待服务恢复"))
            return

        if (time.monotonic() - self._started_at) * 1000 >= START_TIMEOUT_MS:
            self._poll.stop()
            self._set_status("error", self.tr("后端启动超时"))

    def _spawn(self) -> None:
        self._set_status("starting", "")
        self._set_progress(0.08, self.tr("启动后端进程"))
        if self._process and self._process.poll() is None:
            # 上一次拉起的进程还活着（例如只是启动慢导致超时），继续等它
            self._poll.start()
            return
        self._stopping = False
        env = os.environ.copy()
        # 管道输出默认走系统代码页；统一成 UTF-8 并关闭缓冲，阶段标记才能及时、正确地匹配
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        # 沿用浏览器宿主的完整退出约定，源码环境也执行完整清理。
        env["AUTO_MAS_BROWSER_HOST"] = "1"
        args = [
            str(ROOT_DIR / "main.py"),
            "--port",
            str(self._port),
            "--no-admin-restart",
            *self.startup_arguments,
        ]
        self.startup_arguments.clear()
        self._append_log(f"[AUTO-MAS] {python_executable()} {' '.join(args)}")
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("ab") as output:
                self._log_position = output.tell()
                self._process = subprocess.Popen(
                    [python_executable(), *args],
                    cwd=ROOT_DIR,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if sys.platform == "win32"
                    else 0,
                    start_new_session=sys.platform != "win32",
                )
        except OSError as error:
            self._set_status("error", str(error))
            return
        self._poll.start()

    def submit_startup(self) -> None:
        """复用已有后端时，通过公开调度接口兑现命令行请求。"""
        if self._status != "ready" or not self.startup_arguments:
            return
        arguments, self.startup_arguments = self.startup_arguments, []
        queue = script = ""
        for index, argument in enumerate(arguments):
            if argument == "--run-queue" and index + 1 < len(arguments):
                queue = arguments[index + 1]
            elif argument == "--run-script" and index + 1 < len(arguments):
                script = arguments[index + 1]
        if "--auto-run" in arguments and not queue and not script:
            queue = "first"

        def result(data):
            if data.get("code", 200) != 200 or data.get("status") == "error":
                self.eventReceived.emit(
                    "system.notice",
                    {
                        "title": "启动任务失败",
                        "lines": [str(data.get("message") or "任务不可用")],
                    },
                )

        def launch(task_id):
            self.call(
                "/api/dispatch/start", {"taskId": task_id, "mode": "AutoProxy"}, result
            )

        if queue.lower() == "first":

            def first(data):
                entries = data.get("index") or []
                if entries:
                    launch(entries[0]["uid"])
                else:
                    result({"code": 0, "message": "没有可启动的队列"})

            self.call("/api/queue/get", {}, first)
        elif queue:
            launch(queue)
        if script:
            launch(script)

    def _read_process(self) -> None:
        if not self._process:
            return
        try:
            with self._log_path.open("rb") as stream:
                stream.seek(self._log_position)
                chunk = stream.read(256 * 1024)
                # 不消费未结束的一行，避免拆开 UTF-8 字符或启动阶段标记。
                end = chunk.rfind(b"\n") + 1
                self._log_position += end
                for line in chunk[:end].decode("utf-8", errors="replace").splitlines():
                    self._append_log(line)
        except OSError:
            return
        if self._process.poll() is not None and not self._ever_ready:
            self._set_status(
                "error",
                self.tr("后端进程已退出（退出码 {0}）").format(
                    self._process.returncode
                ),
            )
