"""按实际数据根识别后端实例，不信任调用方回传的预期身份。"""

import hashlib
import json
from pathlib import Path

DEFAULT_PORTS = json.loads(
    (Path(__file__).resolve().parents[2] / "res/host-instance-defaults.json").read_text(
        encoding="utf-8"
    )
)


def configured_backend_port(*, development: bool) -> int:
    path = Path.cwd() / "config/HostInstance.json"
    if path.exists():
        port = json.loads(path.read_text(encoding="utf-8"))["backendPort"]
        if not isinstance(port, int) or not 1024 <= port <= 65535:
            raise ValueError("实例后端端口配置不合法")
        return port
    return DEFAULT_PORTS["developmentBackendPort" if development else "backendPort"]


def backend_instance_id(root: Path | None = None) -> str:
    canonical = (
        str((root or Path.cwd()).resolve()).replace("\\", "/").rstrip("/").lower()
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
