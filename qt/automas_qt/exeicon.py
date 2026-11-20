"""脚本启动程序的图标：从 exe 取出 256×256 图标，供录像带上的图标唱片使用。

QML 里用 ``image://exeicon/<encodeURIComponent(路径)>`` 引用。图标同时缓存到
``config/QtIconCache/<路径哈希>.png``：程序移动或暂时不可访问时，录像带上仍保留上次的图标。
"""

from __future__ import annotations

import ctypes
import hashlib
import sys
from pathlib import Path
from urllib.parse import unquote

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtQuick import QQuickImageProvider

ROOT_DIR = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT_DIR / "config" / "QtIconCache"
ICON_SIZE = 256


def _cache_file(path: str) -> Path:
    key = hashlib.sha1(path.lower().encode("utf-8")).hexdigest()[:20]
    return CACHE_DIR / f"{key}.png"


def extract_icon(path: str, size: int = ICON_SIZE) -> QImage:
    """取 exe / dll / ico 内嵌的最大图标；失败时返回空图。仅 Windows。"""

    if sys.platform != "win32" or not path or not Path(path).exists():
        return QImage()
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    icons = (wintypes.HICON * 1)()
    ids = (wintypes.UINT * 1)()
    count = user32.PrivateExtractIconsW(str(path), 0, size, size, icons, ids, 1, 0)
    if count <= 0 or not icons[0]:
        return QImage()
    try:
        return QImage.fromHICON(icons[0])
    finally:
        user32.DestroyIcon(icons[0])


def icon_for(path: str) -> QImage:
    """先从程序本身取，取不到再用缓存；取到后更新缓存。"""

    image = extract_icon(path)
    cache = _cache_file(path)
    if not image.isNull():
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            image.save(str(cache), "PNG")
        except OSError:
            pass
        return image
    if cache.exists():
        return QImage(str(cache))
    return QImage()


def placeholder_icon() -> QImage:
    """取不到程序图标时的占位：AUTO-MAS 档案章（切角方框 + A 形折线 + 琥珀方块）。"""

    image = QImage(ICON_SIZE, ICON_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#2a2b2a"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(24, 24, 208, 208, 28, 28)
    k = 160 / 40
    p.translate(48, 48)
    pen = QPen(QColor("#ffffff"), 2.6 * k)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    frame = QPainterPath()
    frame.moveTo(9 * k, 2 * k); frame.lineTo(38 * k, 2 * k); frame.lineTo(38 * k, 26 * k)
    frame.moveTo(26 * k, 38 * k); frame.lineTo(2 * k, 38 * k); frame.lineTo(2 * k, 9 * k); frame.lineTo(9 * k, 2 * k)
    p.drawPath(frame)
    pen.setWidthF(3.25 * k)
    p.setPen(pen)
    a = QPainterPath()
    a.moveTo(10 * k, 31 * k); a.lineTo(20 * k, 9 * k); a.lineTo(30 * k, 31 * k)
    a.moveTo(14.5 * k, 23 * k); a.lineTo(25.5 * k, 23 * k)
    p.drawPath(a)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#e8701f"))
    p.drawRect(int(31 * k), int(31 * k), int(7 * k), int(7 * k))
    p.end()
    return image


class ExeIconProvider(QQuickImageProvider):
    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._memory: dict[str, QImage] = {}

    def requestImage(self, id_: str, size: QSize, requested: QSize) -> QImage:  # noqa: N802
        path = unquote(id_)
        image = self._memory.get(path)
        if image is None:
            image = icon_for(path)
            if image.isNull():
                image = placeholder_icon()
            self._memory[path] = image
        if size is not None:
            size.setWidth(image.width())
            size.setHeight(image.height())
        if requested.isValid() and requested.width() > 0 and requested.height() > 0:
            return image.scaled(requested, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return image
