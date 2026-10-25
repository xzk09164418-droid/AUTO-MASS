"""主桌面只监听热键，通过已有调度接口转交分身内的任务后端。"""

import argparse
import asyncio
import json
from pathlib import Path

import httpx
import psutil

from app.core.hotkey_manager import _HotkeyManager
from app.utils.logger import get_logger

logger = get_logger("主桌面热键")


class DesktopHotkeyRelay(_HotkeyManager):
    def __init__(self, client: httpx.AsyncClient) -> None:
        super().__init__()
        self.client = client
        self.bindings = (False, "Ctrl+Alt+S", "Ctrl+Alt+Left", "Ctrl+Alt+Right")

    def _read_config_bindings(self) -> tuple[bool, str, str, str]:
        return self.bindings

    async def _forward(self, action: str) -> dict:
        response = await self.client.post(f"/api/dispatch/navigation/{action}", json={})
        response.raise_for_status()
        result = response.json()
        if result.get("code") != 200:
            raise RuntimeError(result.get("message", "热键操作失败"))
        return result.get("data", {})

    async def trigger_toggle_start_stop(self) -> dict:
        return await self._forward("toggle")

    async def trigger_previous_task(self) -> dict:
        return await self._forward("previous")

    async def trigger_next_task(self) -> dict:
        return await self._forward("next")


async def run_hotkey_relay(port: int, parent: psutil.Process | None = None) -> None:
    """跟随配置变更重新注册，父启动器退出时注销全部热键。"""
    config_path = Path("config/Config.json")
    async with httpx.AsyncClient(
        base_url=f"http://127.0.0.1:{port}", timeout=120, trust_env=False
    ) as client:
        relay = DesktopHotkeyRelay(client)
        last_error = None
        try:
            while parent is None or parent.is_running():
                try:
                    config = json.loads(config_path.read_text(encoding="utf-8"))
                    hotkey = config.get("Hotkey", {})
                    bindings = (
                        bool(hotkey.get("Enabled", True)),
                        str(hotkey.get("ToggleStartStop") or "Ctrl+Alt+S"),
                        str(hotkey.get("PreviousTask") or "Ctrl+Alt+Left"),
                        str(hotkey.get("NextTask") or "Ctrl+Alt+Right"),
                    )
                    if bindings != relay.bindings or (
                        bindings[0] and not relay._running
                    ):
                        relay.bindings = bindings
                        await relay.reload()
                    last_error = None
                except (OSError, ValueError, RuntimeError) as error:
                    if str(error) != last_error:
                        logger.warning(f"主桌面热键未就绪: {error}")
                        last_error = str(error)
                await asyncio.sleep(2)
        finally:
            await relay.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-pid", required=True, type=int)
    args, backend_args = parser.parse_known_args()
    if backend_args[:1] == ["--"]:
        backend_args = backend_args[1:]
    # 端口与正常后端共用解析规则，避免开发模式和命令行指定端口不一致。
    from main import is_development_environment, parse_cli_args, resolve_http_port

    cli = parse_cli_args(backend_args)
    asyncio.run(
        run_hotkey_relay(
            resolve_http_port(is_development_environment(), cli.port),
            psutil.Process(args.parent_pid),
        )
    )
