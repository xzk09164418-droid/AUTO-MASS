"""在 Windows x64 上以离线录像带场景重新生成当前 Qt 版本的 D3D11 着色器。"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import (
    QMetaObject,
    QObject,
    QStandardPaths,
    QSysInfo,
    QTimer,
    qVersion,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlExpression, qmlContext

QT_DIR = Path(__file__).resolve().parents[1]


def render(staging: Path) -> int:
    """沿用客户端场景与采样设置，生成器独立存储缓存。"""
    sys.path.insert(0, str(QT_DIR))
    import main as client

    def prepare() -> None:
        QGuiApplication.setApplicationName("QtArrayShaderBake")
        base = Path(QStandardPaths.writableLocation(QStandardPaths.CacheLocation))
        material = (
            base / f"q3dshadercache-{QSysInfo.buildAbi()}" / "q3dshadercache.qsbc"
        )
        (staging / "material-path").write_text(str(material), encoding="utf-8")
        os.environ["QSG_RHI_BACKEND"] = "d3d11"
        os.environ["QT_QUICK3D_NO_SHADER_CACHE_LOAD"] = "1"
        os.environ["QSG_RHI_PIPELINE_CACHE_LOAD"] = str(staging / "empty.pipeline")
        os.environ["QSG_RHI_PIPELINE_CACHE_SAVE"] = str(staging / "array.pipeline")
        QTimer.singleShot(4500, inspect)
        QTimer.singleShot(30000, QGuiApplication.quit)

    def dark_scene(scene: QObject) -> None:
        # 深色阵列有额外点光，需要另一组管线；在同一个设备上烘入同一份缓存。
        theme = QQmlExpression(qmlContext(scene), scene, 'Theme.mode = "dark"; Theme.dark')
        enabled, _ = theme.evaluate()
        if theme.hasError() or not enabled:
            print(theme.error().toString(), file=sys.stderr)
            QGuiApplication.quit()
            return
        QTimer.singleShot(2000, finish)

    def finish() -> None:
        (staging / "rendered").touch()
        QGuiApplication.quit()

    def inspect() -> None:
        for window in QGuiApplication.topLevelWindows():
            section = window.findChild(QObject, "sections")
            scene = section.property("arrayItem") if section else None
            if scene and QMetaObject.invokeMethod(scene, "open"):
                QTimer.singleShot(1800, lambda: dark_scene(scene))
                return
        QTimer.singleShot(250, inspect)

    client.configure_graphics_cache = prepare
    sys.argv = [
        __file__,
        "--skip-boot",
        "--no-backend",
        "--section",
        "2",
        "--motion",
        "enhanced",
        "--theme",
        "light",
        "--size",
        "1280x720",
    ]
    return client.main()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", type=Path, help=argparse.SUPPRESS)
    parser.add_argument(
        "--output",
        type=Path,
        default=QT_DIR / "assets3d/shaders" / f"d3d11-{qVersion()}-x64",
    )
    args = parser.parse_args()
    if sys.platform != "win32" or QSysInfo.buildAbi() != "x86_64-little_endian-llp64":
        parser.error("生成 D3D11 着色器需要 Windows x64 的 Qt")
    if args.render:
        return render(args.render)
    with tempfile.TemporaryDirectory() as temp:
        staging = Path(temp)
        subprocess.run([sys.executable, __file__, "--render", temp], check=True)
        if not (staging / "rendered").exists():
            raise RuntimeError("未能进入增强场景，请检查 Qt Quick 3D 组件")
        material = Path((staging / "material-path").read_text(encoding="utf-8"))
        pipeline = staging / "array.pipeline"
        if not material.stat().st_size or not pipeline.stat().st_size:
            raise RuntimeError("Qt 未生成着色器")
        args.output.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(material, args.output / "array.qsbc")
        shutil.copyfile(pipeline, args.output / "array.pipeline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
