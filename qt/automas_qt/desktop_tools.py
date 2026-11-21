"""Qt 档案面板使用的本机日志、偏好和图像工具。"""

import base64
import json
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QSaveFile, Slot
from PySide6.QtGui import QGuiApplication, QImage

from .backend import ROOT_DIR
from .file_locations import FileLocations


class DesktopTools(FileLocations):
    @Slot(str, result=str)
    def qrImage(self, url: str) -> str:
        import qrcode

        if not url or len(url) > 2000:
            return ""
        code = qrcode.QRCode(border=4)
        code.add_data(url)
        try:
            matrix = code.get_matrix()
        except qrcode.exceptions.DataOverflowError:
            return ""
        size = len(matrix)
        pixels = bytes(0 if dark else 255 for row in matrix for dark in row)
        image = QImage(pixels, size, size, size, QImage.Format.Format_Grayscale8)
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        return "data:image/png;base64," + base64.b64encode(buffer.data()).decode(
            "ascii"
        )

    @Slot(str, str, result=str)
    def previewRule(self, rule: str, sample: str) -> str:
        from app.log_box.hooks import apply_hooks, compile_hook, validate_hook

        config = json.loads(rule)
        error = validate_hook(config)
        if error:
            return error
        compiled = compile_hook(config) if config.get("enabled", True) else None
        lines = []
        for line in sample.splitlines():
            output = apply_hooks(line, [compiled]) if compiled else line
            lines.append(output if output is not None else "（已丢弃）")
        return "\n".join(lines) or "无日志行"

    def _session_start(self, path: Path) -> int:
        """定位当前后端启动标记。追加日志时只扫描新增的字节。"""
        marker = "| 配置管理 | AUTO-MAS 后端应用程序".encode()
        try:
            stat = path.stat()
            previous = getattr(self, "_log_checkpoint", None)
            same = (
                previous and previous[0] == stat.st_ino and previous[1] <= stat.st_size
            )
            floor = max(0, previous[1] - len(marker)) if same else 0
            boundary = previous[2] if same else 0
            if same and previous[1] == stat.st_size:
                return boundary
            with path.open("rb") as stream:
                end = stat.st_size
                suffix = b""
                while end > floor:
                    start = max(floor, end - 128 * 1024)
                    stream.seek(start)
                    block = stream.read(end - start) + suffix
                    hit = block.rfind(marker)
                    if hit >= 0:
                        position = start + hit
                        prefix_start = max(0, position - 4096)
                        stream.seek(prefix_start)
                        prefix = stream.read(position - prefix_start)
                        boundary = prefix_start + prefix.rfind(b"\n") + 1
                        break
                    suffix = block[: len(marker)]
                    end = start
            self._log_checkpoint = (stat.st_ino, stat.st_size, boundary)
            return boundary
        except OSError:
            return 0

    @Slot(result="QVariantList")
    def logFiles(self) -> list[dict]:
        directory = ROOT_DIR / "debug"
        archives = directory / "log-archive"
        files = [
            (directory / "app.log", "后端 · 当前", True),
            (directory / "node-frontend.log", "Node · 当前", True),
        ]
        files.extend(
            (p, p.name, False) for p in sorted(archives.glob("*.log"), reverse=True)
        )
        result = [
            dict(label=label, path=str(p), current=current)
            for p, label, current in files
            if p.is_file()
        ]

        backend = directory / "app.log"
        boundary = self._session_start(backend)
        if boundary and not any(archives.glob(f"backend-before-*-{boundary}.log")):
            result.append(
                dict(
                    label="后端 · 本次启动以前",
                    path=str(backend),
                    current=False,
                    previous=True,
                )
            )
        return result

    @Slot(str, float, bool, result="QVariantMap")
    def logWindow(self, filename: str, before: float, previous: bool) -> dict:
        """读截至指定字节的日志页；返回行首偏移，用作上一页的截止位置。"""
        path = Path(filename).resolve()
        if (
            path.parent not in (ROOT_DIR / "debug", ROOT_DIR / "debug/log-archive")
            or path.suffix != ".log"
        ):
            return {"text": "未知日志文件", "start": 0, "end": 0}
        try:
            with path.open("rb") as stream:
                size = stream.seek(0, 2)
                boundary = (
                    self._session_start(path)
                    if path == ROOT_DIR / "debug/app.log"
                    else 0
                )
                floor = 0 if previous else boundary
                limit = boundary if previous else size
                end = limit if before < 0 else max(floor, min(limit, int(before)))
                start = max(floor, end - 128 * 1024)
                stream.seek(start)
                data = stream.read(end - start)
                newline = data.find(b"\n") if start > floor else -1
                if 0 <= newline < len(data) - 1:
                    start += newline + 1
                    data = data[newline + 1 :]
                return {
                    "floor": floor,
                    "text": data.decode("utf-8", errors="replace"),
                    "start": start,
                    "end": end,
                }
        except OSError:
            return {"text": "日志文件已移动或无法读取", "start": 0, "end": 0}

    @Slot(str)
    def copyText(self, text: str) -> None:
        QGuiApplication.clipboard().setText(text)

    @Slot(str, result=str)
    def quickSelection(self, fallback: str) -> str:
        folder = ROOT_DIR / "config"
        try:
            sidecar = folder / "quick-start-selection.json"
            if sidecar.exists():
                raw = json.loads(sidecar.read_text("utf-8"))
            else:
                raw = json.loads(
                    (folder / "frontend_config.json").read_text("utf-8")
                ).get("homeQuickStartSelectedTaskIds")
            if isinstance(raw, list) and all(isinstance(x, str) for x in raw):
                return json.dumps(raw)
        except (OSError, ValueError, AttributeError):
            pass
        return fallback

    @Slot(str, result=bool)
    def saveQuickSelection(self, raw: str) -> bool:
        folder = ROOT_DIR / "config"
        try:
            folder.mkdir(exist_ok=True)
            payload = json.dumps(json.loads(raw), ensure_ascii=False).encode()
            target = QSaveFile(str(folder / "quick-start-selection.json"))
            return (
                target.open(QIODevice.OpenModeFlag.WriteOnly)
                and target.write(payload) == len(payload)
                and target.commit()
            )
        except (ValueError, OSError):
            return False
