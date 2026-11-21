"""使用已有 websockets 依赖连接主消息流，不要求可选 Qt Addons。"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal
from websockets.exceptions import ConnectionClosed, WebSocketException
from websockets.sync.client import ClientConnection, connect


class BackendEvents(QObject):
    changed = Signal()
    messageReceived = Signal(str)
    disconnected = Signal(int)

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.connected = False
        self._thread: threading.Thread | None = None
        self._connection: ClientConnection | None = None
        self._cancel = threading.Event()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _emit(self, signal, *args) -> None:
        try:
            signal.emit(*args)
        except RuntimeError:
            # 应用退出时 C++ 对象可能先销毁；后台线程不再向已释放的 UI 投递。
            pass

    def start(self, url: str, identity: str) -> None:
        if self.running:
            return
        cancelled = self._cancel = threading.Event()

        def receive() -> None:
            code = 1006
            channel = None
            try:
                with connect(
                    url,
                    additional_headers={"x-auto-mas-instance": identity},
                    proxy=None,
                    open_timeout=5,
                    close_timeout=2,
                    ping_interval=15,
                    ping_timeout=30,
                    max_size=8 * 1024 * 1024,
                ) as channel:
                    self._connection = channel
                    if cancelled.is_set():
                        return
                    self.connected = True
                    self._emit(self.changed)
                    for message in channel:
                        if cancelled.is_set():
                            break
                        if isinstance(message, str):
                            self._emit(self.messageReceived, message)
            except ConnectionClosed as error:
                code = error.rcvd.code if error.rcvd else 1006
            except (OSError, TimeoutError, WebSocketException):
                pass
            finally:
                if channel is not None:
                    code = channel.close_code or code
                self._connection = None
                self.connected = False
                self._emit(self.disconnected, code)
                self._emit(self.changed)

        self._thread = threading.Thread(
            target=receive, name="qt-backend-events", daemon=True
        )
        self._thread.start()

    def close(self) -> None:
        self._cancel.set()
        if self._connection is not None:
            # 关闭握手也不阻塞 Qt 主线程。
            threading.Thread(target=self._connection.close, daemon=True).start()
