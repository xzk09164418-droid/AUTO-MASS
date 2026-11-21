"""将增强模式的源模型和光照转换为 Qt Quick 3D 可直接读取的资源。"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import PySide6
from PySide6.QtCore import QLibraryInfo

ASSETS = Path(__file__).resolve().parents[1] / "assets3d"
PARTS = (
    "Frosted_Polymer", "Ivory_Edges", "Optical_Diffuser", "Index_Inlay",
    "Titanium_Fasteners", "Printed_Label", "Case_Engraving",
    "Case_Engraving_Highlight", "Champagne_Index",
)


def main() -> None:
    """保留源模型中的部件名称，以便场景按名称引用网格。"""
    binaries = QLibraryInfo.path(QLibraryInfo.LibraryPath.BinariesPath)
    search = os.pathsep.join([binaries, str(Path(PySide6.__file__).parent), os.environ.get("PATH", "")])
    executable = shutil.which("balsam", path=search)
    if not executable:
        raise SystemExit("当前 Qt 安装中未找到 balsam")
    with tempfile.TemporaryDirectory() as temp:
        output = Path(temp)
        for source in ("archive-cassette.glb", "room-env.hdr"):
            subprocess.run([executable, "-o", temp, str(ASSETS / source)], check=True)
        scene = (output / "Archive_cassette.qml").read_text(encoding="utf-8")
        sources = dict(re.findall(r'objectName: "([\w]+)\.\d+"\s+source: "(meshes/[^"]+)"', scene))
        meshes = [(output / sources[name], ASSETS / "cassette" / f"{name}.mesh") for name in PARTS]
        (ASSETS / "cassette").mkdir(exist_ok=True)
        for source, destination in meshes:
            shutil.copyfile(source, destination)
        shutil.copyfile(output / "room-env.ktx", ASSETS / "room-env.ktx")


if __name__ == "__main__":
    main()
