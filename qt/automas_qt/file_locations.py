"""本地选择器的路径解析；目录内容由 Qt 的 FolderListModel 异步加载。"""

from pathlib import Path

from PySide6.QtCore import QDir, QObject, QUrl, Slot


class FileLocations(QObject):
    @Slot(result="QStringList")
    def drives(self) -> list[str]:
        return [drive.absoluteFilePath() for drive in QDir.drives()]

    @Slot(str, str, result="QVariantMap")
    def locate(self, value: str, base: str) -> dict:
        try:
            path = Path(value or ".").expanduser()
            if not path.is_absolute():
                path = Path(base or Path.home()) / path
            path = path.absolute()
            return {
                "path": str(path),
                "url": QUrl.fromLocalFile(str(path)),
                "parent": str(path.parent),
                "directory": path.is_dir(),
                "file": path.is_file(),
            }
        except (OSError, ValueError, RuntimeError):
            return {}
