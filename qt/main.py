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
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

QT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(QT_DIR))
sys.path.insert(0, str(QT_DIR.parent))

from automas_qt.activity import ActivityFeed  # noqa: E402
from automas_qt.backend import BackendSupervisor  # noqa: E402
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
    parser.add_argument("--no-backend", action="store_true", help="不连接后端，仅预览界面")
    parser.add_argument("--section", type=int, default=0, help="启动后直接进入第 N 个一级界面")
    parser.add_argument("--theme", choices=["system", "light", "dark"], default="system")
    parser.add_argument("--motion", choices=["reduced", "standard", "enhanced"], default=None,
                        help="动态效果挡位：减少 / 标准 / 增强（默认沿用上次的选择）")
    parser.add_argument("--capture", type=Path, help="截图保存路径")
    parser.add_argument("--after", type=int, default=3000, help="截图延时（毫秒）")
    parser.add_argument(
        "--simulate-load", type=float, default=0, metavar="SECONDS",
        help="不连接后端，按真实阶段模拟一次耗时 N 秒的后端启动（演示长时间加载）",
    )
    parser.add_argument("--return-after", type=int, default=0, metavar="MS",
                        help="配合 --section：进入后 N 毫秒自动返回索引（自检返回过渡用）")
    parser.add_argument("--size", help="窗口逻辑尺寸，如 1920x1080（分辨率适配测试用）")
    return parser.parse_args()


def seed_material_cache(directory: Path, revision: str) -> None:
    """为当前 Qt 版本初始化可再生成的材质缓存，采用与 Qt 写入器相同的锁。"""
    root = QStandardPaths.writableLocation(QStandardPaths.CacheLocation)
    if not root:
        return
    target = Path(root) / f"q3dshadercache-{QSysInfo.buildAbi()}" / "q3dshadercache.qsbc"
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
            revision = f"QtArrayPipeline-{qVersion()}-v1"
            cache = cache.with_name(revision + ".bin")
            seed_material_cache(directory, revision)
    os.environ.setdefault("QSG_RHI_PIPELINE_CACHE_SAVE", str(cache))
    source = cache if cache.is_file() else seed
    if source:
        os.environ.setdefault("QSG_RHI_PIPELINE_CACHE_LOAD", str(source))


def main() -> int:
    args = parse_args()
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

    backend = BackendSupervisor()
    enhanced = EnhancedComponent()
    engine = QQmlApplicationEngine()
    # 录像带上的程序图标：image://exeicon/<路径>
    engine.addImageProvider("exeicon", ExeIconProvider())
    engine.warnings.connect(
        lambda warnings: [print(w.toString(), file=sys.stderr, flush=True) for w in warnings]
    )
    locations = DesktopTools(engine)
    engine.rootContext().setContextProperty("fileLocations", locations)
    feeds = ActivityFeed(engine)
    engine.rootContext().setContextProperty("activityFeed", feeds)
    engine.setInitialProperties(
        {
            "backend": backend,
            "skipBoot": args.skip_boot,
            "backendEnabled": not (args.no_backend or args.simulate_load > 0),
            "simulateLoad": args.simulate_load,
            "initialSection": args.section,
            "returnAfter": args.return_after,
            "themeMode": args.theme,
            "motionMode": motion,
            "enhanced": enhanced,
        }
    )
    engine.load(QUrl.fromLocalFile(str(QT_DIR / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    if args.size:
        w, h = (int(v) for v in args.size.lower().split("x"))
        engine.rootObjects()[0].resize(w, h)

    if not (args.no_backend or args.simulate_load > 0):
        backend.start()
    app.aboutToQuit.connect(backend.shutdown)

    if args.capture:
        import shiboken6
        from PySide6.QtQuick import QQuickWindow

        root = engine.rootObjects()[0]
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
