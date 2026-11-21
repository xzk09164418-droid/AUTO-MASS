"""本地选择器的路径解析；目录内容由 Qt 的 FolderListModel 异步加载。"""

from pathlib import Path

from PySide6.QtCore import QDir, QObject, QUrl, Slot
from PySide6.QtGui import QDesktopServices


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

    @Slot(str, result=bool)
    def openFile(self, value: str) -> bool:
        """用系统默认程序打开文件（历史日志、失败回放等）。"""
        path = Path(value or "")
        return path.is_file() and QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.absolute())))

    @Slot(str, result=bool)
    def openFolder(self, value: str) -> bool:
        """打开文件所在的文件夹；传入的是文件夹时直接打开它。"""
        path = Path(value or "")
        folder = path if path.is_dir() else path.parent
        return folder.is_dir() and QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.absolute())))

    @Slot(result=str)
    def exportLogs(self) -> str:
        """把 logs/ 与 debug/ 打包到「下载」文件夹（与网页版「打包日志」相同的范围），返回压缩包路径；失败返回空串。"""
        import time
        import zipfile

        from .backend import ROOT_DIR, downloads_dir

        target = downloads_dir() / f"AUTO-MAS-logs-{time.strftime('%Y-%m-%d-%H%M%S')}.zip"
        try:
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                for name in ("logs", "debug"):
                    folder = ROOT_DIR / name
                    if not folder.is_dir():
                        continue
                    for file in folder.rglob("*"):
                        if file.is_file():
                            try:
                                archive.write(file, Path(name) / file.relative_to(folder))
                            except OSError:
                                continue
        except OSError:
            return ""
        return str(target)
