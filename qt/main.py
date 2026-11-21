"""AUTO-MAS Qt 客户端入口。

用法：
    .venv\\Scripts\\python.exe qt\\main.py
    .venv\\Scripts\\python.exe qt\\main.py --skip-boot            # 跳过启动动画
    .venv\\Scripts\\python.exe qt\\main.py --no-backend           # 不探测/拉起后端（只看界面）
    .venv\\Scripts\\python.exe qt\\main.py --simulate-load 30     # 模拟 30 秒的后端启动（演示长时间加载）
    .venv\\Scripts\\python.exe qt\\main.py --capture out.png --after 3000   # 定时截图后退出（自检用）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import (
    QIODevice,
    QLockFile,
    QSaveFile,
    QStandardPaths,
    QSysInfo,
    QTimer,
    QUrl,
    qVersion,
)
from PySide6.QtGui import QGuiApplication, QIcon, QSurfaceFormat
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

QT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(QT_DIR))
sys.path.insert(0, str(QT_DIR.parent))

from automas_qt.activity import ActivityFeed  # noqa: E402
from automas_qt.backend import BackendSupervisor, instance_id  # noqa: E402
from automas_qt.client import ClientController  # noqa: E402
from automas_qt.desktop_tools import DesktopTools  # noqa: E402
from automas_qt.enhanced import (  # noqa: E402
    EnhancedComponent,
    preload_libraries_async,
    saved_motion,
)
from automas_qt.exeicon import ExeIconProvider  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AUTO-MAS Qt 客户端")
    parser.add_argument("--skip-boot", action="store_true", help="跳过启动动画")
    parser.add_argument(
        "--no-backend", action="store_true", help="不连接后端，仅预览界面"
    )
    parser.add_argument(
        "--no-browser",
        "--headless",
        "--no-window",
        dest="hidden",
        action="store_true",
        help="仅启动托盘和后端",
    )
    parser.add_argument("--auto-run", action="store_true", help="启动默认队列")
    parser.add_argument("--run-queue", default="", help="启动指定队列")
    parser.add_argument("--run-script", default="", help="启动指定脚本")
    parser.add_argument(
        "--section", type=int, default=0, help="启动后直接进入第 N 个一级界面"
    )
    parser.add_argument(
        "--theme", choices=["system", "light", "dark"], default="system"
    )
    parser.add_argument(
        "--motion",
        choices=["reduced", "standard", "enhanced"],
        default=None,
        help="动态效果挡位：减少 / 标准 / 增强（默认沿用上次的选择）",
    )
    parser.add_argument("--capture", type=Path, help="截图保存路径")
    parser.add_argument("--after", type=int, default=3000, help="截图延时（毫秒）")
    parser.add_argument(
        "--simulate-load",
        type=float,
        default=0,
        metavar="SECONDS",
        help="不连接后端，按真实阶段模拟一次耗时 N 秒的后端启动（演示长时间加载）",
    )
    parser.add_argument(
        "--return-after",
        type=int,
        default=0,
        metavar="MS",
        help="配合 --section：进入后 N 毫秒自动返回索引（自检返回过渡用）",
    )
    parser.add_argument("--size", help="窗口逻辑尺寸，如 1920x1080（分辨率适配测试用）")
    return parser.parse_args()


def seed_material_cache(directory: Path, revision: str) -> None:
    """为当前 Qt 版本初始化可再生成的材质缓存，采用与 Qt 写入器相同的锁。"""
    root = QStandardPaths.writableLocation(QStandardPaths.CacheLocation)
    if not root:
        return
    target = (
        Path(root) / f"q3dshadercache-{QSysInfo.buildAbi()}" / "q3dshadercache.qsbc"
    )
    marker = target.with_name(f"{revision}.ready")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if marker.exists() and target.is_file():
            return
        lock = QLockFile(str(target) + ".lck")
        if not lock.tryLock(0):
            return
        data = (directory / "array.qsbc").read_bytes()
        output = QSaveFile(str(target))
        if (
            output.open(QIODevice.WriteOnly)
            and output.write(data) == len(data)
            and output.commit()
        ):
            marker.touch()
    except OSError:
        # 只读环境仍可使用 Qt 自带的运行时编译。
        return


def configure_graphics_cache() -> None:
    """首次运行使用随包着色器，后续启动复用本机积累的渲染管线。"""
    cache = QT_DIR.parent / "config" / "QtPipelineCache.bin"
    seed = None
    if (
        sys.platform == "win32"
        and QSysInfo.buildAbi() == "x86_64-little_endian-llp64"
        and os.environ.get("QSG_RHI_BACKEND", "d3d11").lower() == "d3d11"
    ):
        directory = QT_DIR / "assets3d" / "shaders" / f"d3d11-{qVersion()}-x64"
        if (directory / "array.pipeline").is_file():
            seed = directory / "array.pipeline"
            revision = f"QtArrayPipeline-{qVersion()}-v6-rhine"
            cache = cache.with_name(revision + ".bin")
            seed_material_cache(directory, revision)
    os.environ.setdefault("QSG_RHI_PIPELINE_CACHE_SAVE", str(cache))
    source = cache if cache.is_file() else seed
    if source:
        os.environ.setdefault("QSG_RHI_PIPELINE_CACHE_LOAD", str(source))


def main() -> int:
    args = parse_args()
    if sys.stderr is None or sys.stdout is None:
        log = QT_DIR.parent / "debug/qt-client.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        output = log.open("a", encoding="utf-8", buffering=1)
        sys.stderr = sys.stderr or output
        sys.stdout = sys.stdout or output
    motion = args.motion or saved_motion()
    # 增强挡位：后台线程先把 3D 相关 DLL 映射进来，之后预加载 3D 阵列时主线程不再为读盘卡顿
    if motion == "enhanced":
        preload_libraries_async()
    # 显式要求垂直同步：交换链按显示器刷新节拍呈现，避免圆环等大幅运动时撕裂
    fmt = QSurfaceFormat.defaultFormat()
    fmt.setSwapInterval(1)
    # 4× 多重采样：旋转的玻璃卡、透视卡带、斜线等边缘不再出现锯齿
    fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication(sys.argv)
    app.setApplicationName("AUTO-MASS")
    app.setOrganizationName("AUTO-MAS")
    configure_graphics_cache()
    icon = QT_DIR.parent / "res" / "icons" / "AUTO-MAS.ico"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    live = not (args.no_backend or args.simulate_load > 0)
    server = None
    if live and not args.capture:
        name = "AUTO-MAS-Qt-" + instance_id()[:24]
        socket = QLocalSocket()
        socket.connectToServer(name)
        if socket.waitForConnected(500):
            socket.write(
                (
                    json.dumps(
                        {
                            "show": not args.hidden,
                            "queue": args.run_queue,
                            "script": args.run_script,
                            "auto": args.auto_run,
                        }
                    )
                    + "\n"
                ).encode()
            )
            socket.waitForBytesWritten(500)
            socket.disconnectFromServer()
            return 0
        QLocalServer.removeServer(name)
        server = QLocalServer(app)
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not server.listen(name):
            print("Qt 客户端已在启动，请稍后重试", file=sys.stderr)
            return 1

    backend = BackendSupervisor()
    if args.auto_run:
        backend.startup_arguments.append("--auto-run")
    if args.run_queue:
        backend.startup_arguments.extend(["--run-queue", args.run_queue])
    if args.run_script:
        backend.startup_arguments.extend(["--run-script", args.run_script])
    enhanced = EnhancedComponent()
    # 网络活动任务可能晚于界面释放完成，服务归应用所有，重建界面时继续复用。
    feeds = ActivityFeed(app)
    locations = DesktopTools(app)
    client = ClientController(backend, app) if live and not args.capture else None
    app.setQuitOnLastWindowClosed(client is None)
    engines = []

    def show_frontend() -> None:
        if engines:
            return
        engine = QQmlApplicationEngine()
        engine.addImageProvider("exeicon", ExeIconProvider())
        engine.warnings.connect(
            lambda warnings: [
                print(w.toString(), file=sys.stderr, flush=True) for w in warnings
            ]
        )
        engine.rootContext().setContextProperty("fileLocations", locations)
        engine.rootContext().setContextProperty("activityFeed", feeds)
        # Python 包装器也保留到引擎销毁，避免上下文对象被提前回收。
        engine._services = (locations, feeds)
        engine.setInitialProperties(
            {
                "backend": backend,
                "client": client,
                "skipBoot": args.skip_boot or backend.status == "ready",
                "backendEnabled": live,
                "simulateLoad": args.simulate_load,
                "initialSection": args.section,
                "returnAfter": args.return_after,
                "themeMode": args.theme,
                "motionMode": motion,
                "enhanced": enhanced,
            }
        )
        engine.load(QUrl.fromLocalFile(str(QT_DIR / "qml/Main.qml")))
        if not engine.rootObjects():
            return
        engines.append(engine)
        if client:
            client.window = engine.rootObjects()[0]
        if args.size:
            w, h = (int(v) for v in args.size.lower().split("x"))
            engine.rootObjects()[0].resize(w, h)

    def release_frontend() -> None:
        if client:
            client.window = None
        for engine in engines:
            for window in engine.rootObjects():
                window.hide()
            engine.deleteLater()
        engines.clear()

    if client:
        client.showRequested.connect(show_frontend)
        client.releaseRequested.connect(release_frontend)
        client.quitRequested.connect(app.quit)
        if server:

            def activate_existing() -> None:
                connection = server.nextPendingConnection()
                connection.disconnected.connect(connection.deleteLater)

                def received() -> None:
                    if not connection.canReadLine():
                        return
                    try:
                        message = json.loads(bytes(connection.readLine()).decode())
                        if not isinstance(message, dict):
                            return
                        for key, flag in (
                            ("queue", "--run-queue"),
                            ("script", "--run-script"),
                        ):
                            if isinstance(message.get(key), str) and message[key]:
                                backend.startup_arguments.extend([flag, message[key]])
                        if message.get("auto") is True:
                            backend.startup_arguments.append("--auto-run")
                        backend.submit_startup()
                        if message.get("show") is True:
                            client.show_window()
                    except (ValueError, UnicodeDecodeError):
                        pass
                    finally:
                        connection.disconnectFromServer()

                connection.readyRead.connect(received)
                received()

            server.newConnection.connect(activate_existing)
    if not (client and (args.hidden or client.start_hidden)):
        show_frontend()
        if not engines:
            return 1

    if live:
        backend.start()
    app.aboutToQuit.connect(backend.shutdown)

    if args.capture:
        import shiboken6
        from PySide6.QtQuick import QQuickWindow

        root = engines[0].rootObjects()[0]
        window = shiboken6.wrapInstance(shiboken6.getCppPointer(root)[0], QQuickWindow)

        def capture() -> None:
            try:
                window.grabWindow().save(str(args.capture))
            finally:
                app.quit()

        QTimer.singleShot(abs(args.after), capture)

    return QGuiApplication.exec()


if __name__ == "__main__":
    sys.exit(main())
