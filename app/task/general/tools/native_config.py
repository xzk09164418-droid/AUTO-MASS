"""通用原生配置只做文件读写，不解释外部程序的配置语义。"""

import hashlib
import os
import tempfile
from pathlib import Path

from app.models.config import GeneralConfig
from app.task.general.tools.backup_archive import archive_native_backup

MAX_TEXT_BYTES = 2 * 1024 * 1024


def config_root(script: GeneralConfig) -> tuple[Path, str]:
    raw = str(script.get("Script", "ConfigPath") or "").strip()
    if raw in ("", "."):
        raise ValueError("请先选择源程序的配置文件或配置目录")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path(str(script.get("Info", "RootPath") or ".")) / path
    mode = str(script.get("Script", "ConfigPathMode"))
    path = path.resolve(strict=True)
    if (mode == "File" and not path.is_file()) or (
        mode == "Folder" and not path.is_dir()
    ):
        raise ValueError("配置路径与文件/目录类型不匹配")
    if mode not in ("File", "Folder"):
        raise ValueError("不支持的配置路径类型")
    return path, mode


def selected_file(root: Path, mode: str, name: str) -> Path:
    if mode == "File":
        if name and name != root.name:
            raise ValueError("只能编辑已选择的配置文件")
        return root
    relative = Path(name)
    if not name or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("请选择配置目录内的文件")
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("配置文件必须位于已选择的配置目录内")
    return path


def read_text(path: Path) -> tuple[bytes, str]:
    if path.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError("配置文件超过 2 MB，请使用源程序设置界面编辑")
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise ValueError("该文件不是 UTF-8 文本，请使用源程序设置界面编辑")
    try:
        return raw, raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("仅支持 UTF-8 文本，请使用源程序设置界面编辑") from error


def read_config(script: GeneralConfig, name: str) -> dict:
    root, mode = config_root(script)
    if mode == "Folder" and not name:
        files = []
        for path in root.rglob("*"):
            if path.is_file() and path.resolve().is_relative_to(root):
                files.append(path.relative_to(root).as_posix())
                if len(files) > 500:
                    raise ValueError("配置目录超过 500 个文件，请缩小选择范围")
        return {"files": sorted(files)}
    path = selected_file(root, mode, name)
    raw, content = read_text(path)
    return {
        "file": path.name if mode == "File" else path.relative_to(root).as_posix(),
        "content": content,
        "revision": hashlib.sha256(raw).hexdigest(),
    }


def write_config(
    script_id: str, script: GeneralConfig, name: str, content: str, revision: str
) -> dict:
    root, mode = config_root(script)
    path = selected_file(root, mode, name)
    raw, original = read_text(path)
    if hashlib.sha256(raw).hexdigest() != revision:
        raise ValueError("源配置已被其他程序修改，请重新打开后再保存")
    if "\r\n" in original:
        content = content.replace("\r\n", "\n").replace("\n", "\r\n")
    encoded = content.encode(
        "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    )
    if len(encoded) > MAX_TEXT_BYTES:
        raise ValueError("配置内容超过 2 MB")
    archive_native_backup(script_id, root, mode)
    descriptor, temporary = tempfile.mkstemp(prefix=".automas-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if path.read_bytes() != raw:
            raise ValueError("源配置已被其他程序修改，请重新打开后再保存")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return read_config(script, name)
