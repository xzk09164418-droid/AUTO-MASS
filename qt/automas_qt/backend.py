"""Qt 客户端的后端监督器。

职责与 frontend/server.js 中的 Node 宿主一致：先探测本安装实例的后端是否已在运行
（GET /api/core/health，且 instanceId 与本数据根一致）；没有就用 .venv 的解释器拉起
``main.py --port N --no-admin-restart``，轮询健康接口直到就绪或超时。后端代码不做任何改动。
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import deque
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QObject,
    QProcess,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

ROOT_DIR = Path(__file__).resolve().parents[2]
HEALTH_PATH = "/api/core/health"
POLL_INTERVAL_MS = 500
START_TIMEOUT_MS = 120_000
MAX_LOG_LINES = 200
LOG_LEVEL_PATTERN = re.compile(r"\|\s*(DEBUG|INFO|SUCCESS|WARNING|ERROR|CRITICAL)\s*\|")


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

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._status = "probing"
        self._message = ""
        self._background = ""
        self._logs: deque[dict[str, str]] = deque(maxlen=MAX_LOG_LINES)
        self._port = backend_port()
        self._expected_id = instance_id()
        self._network = QNetworkAccessManager(self)
        self._process: QProcess | None = None
        self._stopping = False
        self._elapsed = 0
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

    @Property(int, constant=True)
    def port(self) -> int:
        return self._port

    @Property("QVariantList", notify=logsChanged)
    def logs(self) -> list[dict[str, str]]:
        return list(self._logs)

    # ── 操作 ────────────────────────────────────────────────────────────────
    @Slot()
    def start(self) -> None:
        self._set_status("probing", "")
        self._elapsed = 0
        self._probe(first=True)

    @Slot()
    def retry(self) -> None:
        self._logs.clear()
        self.logsChanged.emit()
        self.start()

    @Slot()
    def shutdown(self) -> None:
        """只结束本客户端自己拉起的后端进程。"""

        self._poll.stop()
        self._stopping = True
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.terminate()
            if not self._process.waitForFinished(5000):
                self._process.kill()

    # ── 内部 ────────────────────────────────────────────────────────────────
    def _set_status(self, status: str, message: str) -> None:
        if (status, message) != (self._status, self._message):
            self._status, self._message = status, message
            self.statusChanged.emit()

    def _append_log(self, line: str) -> None:
        line = line.rstrip()
        if not line:
            return
        match = LOG_LEVEL_PATTERN.search(line)
        self._logs.append({"level": match.group(1) if match else "", "text": line})
        self.logsChanged.emit()

    def _probe(self, first: bool = False) -> None:
        request = QNetworkRequest(QUrl(f"http://127.0.0.1:{self._port}{HEALTH_PATH}"))
        request.setTransferTimeout(2000)
        reply = self._network.get(request)
        reply.finished.connect(lambda: self._on_health(reply, first))

    def _on_health(self, reply: QNetworkReply, first: bool) -> None:
        reply.deleteLater()
        data = None
        if reply.error() == QNetworkReply.NetworkError.NoError:
            try:
                data = json.loads(bytes(reply.readAll().data()).decode("utf-8"))
            except ValueError:
                data = None

        if data is not None and data.get("instanceId") != self._expected_id:
            self._poll.stop()
            self._set_status(
                "error",
                self.tr("端口 {0} 上运行的后端不属于本安装目录，已拒绝连接").format(self._port),
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
            self._poll.stop()
            self._set_status("ready", "")
            return

        if first:
            self._spawn()
            return

        self._elapsed += POLL_INTERVAL_MS
        if self._elapsed >= START_TIMEOUT_MS:
            self._poll.stop()
            self._set_status("error", self.tr("后端启动超时"))

    def _spawn(self) -> None:
        self._set_status("starting", "")
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            # 上一次拉起的进程还活着（例如只是启动慢导致超时），继续等它
            self._poll.start()
            return
        self._stopping = False
        process = QProcess(self)
        process.setWorkingDirectory(str(ROOT_DIR))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_process)
        process.finished.connect(self._on_process_finished)
        process.errorOccurred.connect(self._on_process_error)
        self._process = process
        args = [str(ROOT_DIR / "main.py"), "--port", str(self._port), "--no-admin-restart"]
        self._append_log(f"[AUTO-MAS] {python_executable()} {' '.join(args)}")
        process.start(python_executable(), args)
        self._poll.start()

    def _read_process(self) -> None:
        if not self._process:
            return
        chunk = bytes(self._process.readAllStandardOutput().data()).decode(
            "utf-8", errors="replace"
        )
        for line in chunk.splitlines():
            self._append_log(line)

    def _on_process_finished(self, code: int, _status: QProcess.ExitStatus) -> None:
        if self._stopping:
            return
        self._poll.stop()
        self._set_status("error", self.tr("后端进程已退出（退出码 {0}）").format(code))

    def _on_process_error(self, _error: QProcess.ProcessError) -> None:
        if self._process and not self._stopping:
            self._poll.stop()
            self._set_status("error", self._process.errorString())
