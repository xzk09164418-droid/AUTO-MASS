"""AUTO-MAS Qt 客户端入口。

用法：
    .venv\\Scripts\\python.exe qt\\main.py
    .venv\\Scripts\\python.exe qt\\main.py --skip-boot            # 跳过启动动画
    .venv\\Scripts\\python.exe qt\\main.py --no-backend           # 不探测/拉起后端（只看界面）
    .venv\\Scripts\\python.exe qt\\main.py --capture out.png --after 3000   # 定时截图后退出（自检用）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine

QT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(QT_DIR))

from automas_qt.backend import BackendSupervisor  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AUTO-MAS Qt 客户端")
    parser.add_argument("--skip-boot", action="store_true", help="跳过启动动画")
    parser.add_argument("--no-backend", action="store_true", help="不连接后端，仅预览界面")
    parser.add_argument("--section", type=int, default=0, help="启动后直接进入第 N 个一级界面")
    parser.add_argument("--theme", choices=["system", "light", "dark"], default="system")
    parser.add_argument("--capture", type=Path, help="截图保存路径")
    parser.add_argument("--after", type=int, default=3000, help="截图延时（毫秒）")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = QGuiApplication(sys.argv)
    app.setApplicationName("AUTO-MAS")
    app.setOrganizationName("AUTO-MAS")
    icon = QT_DIR.parent / "res" / "icons" / "AUTO-MAS.ico"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    backend = BackendSupervisor()
    engine = QQmlApplicationEngine()
    engine.warnings.connect(
        lambda warnings: [print(w.toString(), file=sys.stderr, flush=True) for w in warnings]
    )
    engine.setInitialProperties(
        {
            "backend": backend,
            "skipBoot": args.skip_boot,
            "backendEnabled": not args.no_backend,
            "initialSection": args.section,
            "themeMode": args.theme,
        }
    )
    engine.load(QUrl.fromLocalFile(str(QT_DIR / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1

    if not args.no_backend:
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

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
