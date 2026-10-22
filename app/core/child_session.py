"""基于 BetterGI 远程桌面（Child Session）的本地远程桌面管理、进程包装器调度与外部让渡接口。

核心职责：
1. 常驻管理本地远程桌面（Windows Child Session）连接，复用 BetterGI 的 `ChildSessionHost`
   （`WTSEnableChildSessions` + `MsRdpClient10` ActiveX `ConnectToChildSession` + `Schedule.Service`）。
2. 提供包装器（Wrapper）跨会话进程启动与监控能力：在子会话中启动 `child_session_wrapper.py`，
   实时获取子会话内脚本的 PID、运行状态与退出码（returncode），并在结束/超时时执行 3 遍 `taskkill /F /T`。
3. 外部程序借用与回传机制：
   - 外部程序可通过 HTTP API 申请借用本地远程桌面（`acquire_external_lease`）。
   - 队列在相邻两个子任务间隔自动调用 `wait_if_external_requested()`：若检测到外部程序申请连接远程桌面，
     则暂停队列推进并释放/让渡桌面分身控制权，直到外部程序停止使用并调用回传接口（`release_external_lease`）
     后恢复常驻连接并继续执行下一个子任务。
"""

from __future__ import annotations

import asyncio
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.utils.logger import get_logger

logger = get_logger("远程桌面分身")

NO_CHILD_SESSION_ID = 0xFFFFFFFF
TASK_ACTION_EXECUTE = 0
TASK_CREATE = 2
TASK_LOGON_INTERACTIVE_TOKEN = 3
TASK_RUN_LEVEL_HIGHEST = 1
TASK_RUN_USE_SESSION_ID = 0x4
FORCE_KILL_PASSES = 3


@dataclass
class ExternalDesktopLease:
    """外部程序申请使用本地远程桌面的租约记录。"""

    lease_id: str
    caller: str
    disconnect_rdp_view: bool = True
    status: str = "pending"  # "pending" | "granted" | "released"
    requested_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    granted_at: str | None = None
    expires_at_monotonic: float | None = None
    _granted_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "leaseId": self.lease_id,
            "caller": self.caller,
            "disconnectRdpView": self.disconnect_rdp_view,
            "status": self.status,
            "requestedAt": self.requested_at,
            "grantedAt": self.granted_at,
        }


class ChildSessionWrappedProcess:
    """与 `asyncio.subprocess.Process` 兼容的跨会话包装器进程句柄。"""

    def __init__(
        self,
        job_id: str,
        state_file: Path,
        session_id: int,
        command: list[str],
    ) -> None:
        self.job_id = job_id
        self.state_file = state_file
        self.stop_file = state_file.with_suffix(state_file.suffix + ".stop")
        self.session_id = session_id
        self.command = command
        self._pid: int | None = None
        self._wrapper_pid: int | None = None
        self._returncode: int | None = None
        self._status: str = "starting"
        self._error: str | None = None
        self.stdin = None
        self.stdout = None
        self.stderr = None

    @property
    def pid(self) -> int | None:
        self._refresh_from_disk()
        return self._pid or self._wrapper_pid

    @property
    def returncode(self) -> int | None:
        self._refresh_from_disk()
        return self._returncode

    def _refresh_from_disk(self) -> None:
        if not self.state_file.is_file():
            return
        try:
            raw = self.state_file.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception:
            return

        if data.get("target_pid") is not None:
            self._pid = int(data["target_pid"])
        if data.get("wrapper_pid") is not None:
            self._wrapper_pid = int(data["wrapper_pid"])
        status = str(data.get("status") or "starting")
        self._status = status
        if status in ("exited", "killed", "error"):
            rc = data.get("returncode")
            self._returncode = int(rc) if rc is not None else -1
            self._error = data.get("error")

    async def wait(self) -> int:
        while True:
            self._refresh_from_disk()
            if self._returncode is not None:
                return self._returncode
            await asyncio.sleep(0.2)

    async def communicate(self) -> tuple[bytes, bytes]:
        await self.wait()
        return b"", b""

    def terminate(self) -> None:
        with suppress(OSError):
            self.stop_file.write_text("stop", encoding="utf-8")

    def kill(self) -> None:
        self.terminate()


class _ChildSessionManager:
    """管理基于 BetterGI 的常驻本地远程桌面（Child Session）、包装器启动与外部程序借用让渡。"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._host_process: asyncio.subprocess.Process | None = None
        self._leases: dict[str, ExternalDesktopLease] = {}
        self._in_subtask_execution: int = 0
        self._rdp_view_disconnected_for_external: bool = False
        self._all_leases_released_event = asyncio.Event()
        self._all_leases_released_event.set()
        self._state_dir = Path("data") / "child_session_jobs"

    @property
    def enabled(self) -> bool:
        try:
            from app.core import Config

            return bool(Config.get("ChildSession", "Enabled"))
        except Exception:
            return False

    @property
    def host_port(self) -> int:
        try:
            from app.core import Config

            return int(Config.get("ChildSession", "HostPort") or 36165)
        except Exception:
            return 36165

    @property
    def desktop_resolution(self) -> tuple[int, int]:
        try:
            from app.core import Config

            raw = str(Config.get("ChildSession", "Resolution") or "2560x1440")
            w_str, _, h_str = raw.lower().partition("x")
            return max(200, int(w_str)), max(200, int(h_str))
        except Exception:
            return (2560, 1440)

    def _host_url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.host_port}/{path.lstrip('/')}"

    def _http_call_sync(
        self,
        path: str,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> dict[str, Any] | None:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        req = urllib.request.Request(
            self._host_url(path),
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return json.loads(body) if body else {"ok": True}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return None

    async def _http_call(
        self,
        path: str,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> dict[str, Any] | None:
        return await asyncio.to_thread(
            self._http_call_sync, path, method, payload, timeout
        )

    @staticmethod
    def wts_enable_child_sessions() -> bool:
        """直接调用 wtsapi32.dll 启用 Windows Child Sessions（对齐 BGI ChildSessionNativeMethods）。"""
        if os.name != "nt":
            return False
        try:
            wtsapi32 = ctypes.windll.wtsapi32
            enabled = ctypes.c_bool(False)
            if wtsapi32.WTSIsChildSessionsEnabled(ctypes.byref(enabled)) and enabled.value:
                return True
            return bool(wtsapi32.WTSEnableChildSessions(True))
        except Exception as exc:
            logger.warning(f"调用 WTSEnableChildSessions 失败: {exc}")
            return False

    @staticmethod
    def wts_get_child_session_id() -> int | None:
        """直接调用 wtsapi32.dll 获取当前活跃的 Child Session ID。"""
        if os.name != "nt":
            return None
        try:
            session_id = ctypes.c_uint(NO_CHILD_SESSION_ID)
            ok = ctypes.windll.wtsapi32.WTSGetChildSessionId(ctypes.byref(session_id))
            if ok and session_id.value != NO_CHILD_SESSION_ID:
                return int(session_id.value)
        except Exception:
            pass
        return None

    @staticmethod
    def wts_terminate_child_session(wait: bool = True) -> int | None:
        """注销当前 Child Session（对齐 BGI TerminateChildSession）。"""
        sid = _ChildSessionManager.wts_get_child_session_id()
        if sid is None or os.name != "nt":
            return None
        try:
            ctypes.windll.wtsapi32.WTSLogoffSession(0, ctypes.c_uint(sid), bool(wait))
            return sid
        except Exception as exc:
            logger.warning(f"注销 Child Session {sid} 失败: {exc}")
            return None

    @staticmethod
    def _compile_host_executable_sync() -> Path | None:
        """若尚未生成 AutoMas.ChildSessionHost.exe，使用 Windows 内置 csc.exe 或 dotnet 自动编译。"""
        if os.name != "nt":
            return None

        host_dir = Path("res/ChildSessionHost").resolve()
        if not host_dir.is_dir():
            return None

        target_exe = host_dir / "AutoMas.ChildSessionHost.exe"
        cs_files = sorted(str(p) for p in host_dir.glob("*.cs"))
        if not cs_files:
            return None

        windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
        csc_candidates = [
            windir / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe",
            windir / "Microsoft.NET" / "Framework" / "v4.0.30319" / "csc.exe",
        ]
        icon_path = Path("res/icons/AUTO-MAS.ico").resolve()

        for csc in csc_candidates:
            if csc.is_file():
                cmd = [
                    str(csc),
                    "/nologo",
                    "/target:winexe",
                    "/platform:x64",
                    "/optimize+",
                    f"/out:{target_exe}",
                    "/r:System.dll",
                    "/r:System.Core.dll",
                    "/r:System.Drawing.dll",
                    "/r:System.Windows.Forms.dll",
                    "/r:Microsoft.CSharp.dll",
                ]
                if icon_path.is_file():
                    cmd.append(f"/win32icon:{icon_path}")
                cmd.extend(cs_files)
                try:
                    proc = subprocess.run(
                        cmd,
                        cwd=str(host_dir),
                        capture_output=True,
                        text=True,
                        timeout=30,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    if proc.returncode == 0 and target_exe.is_file():
                        logger.success(f"已使用系统内置 csc.exe 自动编译远程桌面宿主: {target_exe}")
                        return target_exe
                    logger.warning(f"csc.exe 编译返回码 {proc.returncode}: {proc.stdout} {proc.stderr}")
                except Exception as exc:
                    logger.warning(f"调用 csc.exe 编译远程桌面宿主失败: {exc}")

        dotnet_bin = shutil.which("dotnet")
        if dotnet_bin:
            try:
                proc = subprocess.run(
                    [dotnet_bin, "build", "-c", "Release"],
                    cwd=str(host_dir),
                    capture_output=True,
                    text=True,
                    timeout=60,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                built = host_dir / "bin" / "Release" / "net8.0-windows" / "AutoMas.ChildSessionHost.exe"
                if proc.returncode == 0 and built.is_file():
                    return built.resolve()
            except Exception as exc:
                logger.warning(f"调用 dotnet build 编译远程桌面宿主失败: {exc}")

        return None

    @classmethod
    def _find_host_executable(cls) -> Path | None:
        candidates = [
            Path("res/ChildSessionHost/AutoMas.ChildSessionHost.exe"),
            Path("res/ChildSessionHost/bin/Release/net8.0-windows/AutoMas.ChildSessionHost.exe"),
            Path("res/ChildSessionHost/bin/Debug/net8.0-windows/AutoMas.ChildSessionHost.exe"),
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        return cls._compile_host_executable_sync()

    async def start(self) -> None:
        """启动常驻远程桌面宿主（当配置启用时自动拉起并保持连接）。"""
        if os.name != "nt" or not self.enabled:
            return
        await self.ensure_connected()

    async def stop(self) -> None:
        """关闭远程桌面宿主服务。"""
        if os.name != "nt":
            return
        # 任务后端退出时不能关闭自己所在的桌面；宿主生命周期由主桌面桥接管理。
        from app.utils.platform.windows.session import EXECUTION_SESSION_ENV

        if os.environ.get(EXECUTION_SESSION_ENV) is not None:
            return
        with suppress(Exception):
            await self._http_call("/shutdown", method="POST", payload={}, timeout=3.0)
        if self._host_process is not None and self._host_process.returncode is None:
            with suppress(Exception):
                self._host_process.terminate()
                await asyncio.wait_for(self._host_process.wait(), timeout=3.0)
        self._host_process = None

    async def ensure_host_running(self, *, force_visible: bool = False) -> dict[str, Any] | None:
        """确保 C# 远程桌面宿主进程已启动且 HTTP IPC 可达。"""
        if os.name != "nt":
            return None

        status = await self._http_call("/status", method="GET", timeout=2.0)
        if status is not None:
            return status

        from app.utils.platform.windows.session import EXECUTION_SESSION_ENV

        if os.environ.get(EXECUTION_SESSION_ENV) is not None:
            raise RuntimeError("主桌面 RDP 宿主不可用，不能在执行会话中创建嵌套子桌面")

        if self._host_process is not None and self._host_process.returncode is None:
            logger.warning("远程桌面宿主仍在运行但尚未响应，请检查宿主启动状态，跳过重复启动")
            return None

        host_exe = await asyncio.to_thread(self._find_host_executable)
        if host_exe is None:
            return None

        width, height = self.desktop_resolution
        args = [
            str(host_exe),
            "--port",
            str(self.host_port),
            "--width",
            str(width),
            "--height",
            str(height),
        ]
        if not force_visible:
            try:
                from app.core import Config

                if Config.get("ChildSession", "StartHidden"):
                    args.append("--hidden")
            except Exception:
                pass

        logger.info(f"正在启动 BetterGI 风格远程桌面宿主: {args}")
        self._host_process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        for _ in range(30):
            await asyncio.sleep(0.2)
            status = await self._http_call("/status", method="GET", timeout=1.5)
            if status is not None:
                return status
        return None

    async def ensure_connected(self) -> int | None:
        """确保常驻本地远程桌面已建立连接，并返回 ChildSessionId。"""
        if os.name != "nt":
            return None

        async with self._lock:
            status = await self.ensure_host_running()
            if status is not None:
                sid = status.get("childSessionId")
                from app.utils.platform.windows.session import (
                    EXECUTION_SESSION_ENV,
                    get_process_session_id,
                )

                expected = os.environ.get(EXECUTION_SESSION_ENV)
                if expected is not None and (
                    sid != int(expected) or get_process_session_id() != int(expected)
                ):
                    raise RuntimeError("RDP 执行会话已改变，请重新启动主程序")
                if sid is not None and status.get("connectedState") == 1:
                    return int(sid)
                width, height = self.desktop_resolution
                conn_resp = await self._http_call(
                    "/connect",
                    method="POST",
                    payload={"width": width, "height": height},
                    timeout=65.0,
                )
                if conn_resp and conn_resp.get("childSessionId") is not None:
                    if expected is not None and conn_resp["childSessionId"] != int(expected):
                        raise RuntimeError("RDP 重连后执行会话已改变，请重新启动主程序")
                    return int(conn_resp["childSessionId"])

            # 回退：直接通过 wtsapi32 读取已建立的 ChildSessionId
            await asyncio.to_thread(self.wts_enable_child_sessions)
            return await asyncio.to_thread(self.wts_get_child_session_id)

    @staticmethod
    def _launch_via_task_scheduler_sync(
        session_id: int,
        executable_path: str,
        arguments: str,
        working_directory: str,
    ) -> None:
        """Python 原生调用 Schedule.Service COM 在目标 Child Session 启动进程（与 BGI 逻辑完全一致）。"""
        import win32com.client  # type: ignore[import-untyped]

        scheduler = win32com.client.Dispatch("Schedule.Service")
        scheduler.Connect()
        root_folder = scheduler.GetFolder("\\")
        task_def = scheduler.NewTask(0)

        task_def.RegistrationInfo.Author = "AUTO-MAS"
        task_def.RegistrationInfo.Description = (
            f"临时启动 {Path(executable_path).name} 到 Child Session {session_id}"
        )
        task_def.Settings.Enabled = True
        task_def.Settings.Hidden = True
        task_def.Settings.AllowDemandStart = True
        task_def.Settings.DisallowStartIfOnBatteries = False
        task_def.Settings.StopIfGoingOnBatteries = False
        task_def.Settings.ExecutionTimeLimit = "PT0S"

        task_def.Principal.LogonType = TASK_LOGON_INTERACTIVE_TOKEN
        task_def.Principal.RunLevel = TASK_RUN_LEVEL_HIGHEST

        action = task_def.Actions.Create(TASK_ACTION_EXECUTE)
        action.Path = executable_path
        action.Arguments = arguments
        action.WorkingDirectory = working_directory

        task_name = f"AutoMAS-ChildSession-Launch-{uuid.uuid4().hex}"
        try:
            registered = root_folder.RegisterTaskDefinition(
                task_name,
                task_def,
                TASK_CREATE,
                None,
                None,
                TASK_LOGON_INTERACTIVE_TOKEN,
                None,
            )
            running = registered.RunEx(None, TASK_RUN_USE_SESSION_ID, int(session_id), None)
            # 进入运行态即可清理任务定义，不固定等待 15 秒。
            deadline = time.monotonic() + 15.0
            while running is not None and time.monotonic() < deadline:
                if int(running.State) == 4:
                    break
                time.sleep(0.1)
        finally:
            with suppress(Exception):
                root_folder.DeleteTask(task_name, 0)

    async def launch_in_child_session(
        self,
        program: Path | str,
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> ChildSessionWrappedProcess:
        """通过包装器模式（Wrapper）在本地远程桌面（Child Session）中启动程序并跟踪运行状态与退出码。"""

        session_id = await self.ensure_connected()
        if session_id is None:
            raise RuntimeError("未能获取可用的本地远程桌面 (Child Session) 会话 ID")

        self._state_dir.mkdir(parents=True, exist_ok=True)
        job_id = uuid.uuid4().hex
        state_file = (self._state_dir / f"job_{job_id}.json").resolve()
        env_file: Path | None = None
        if env:
            env_file = (self._state_dir / f"job_{job_id}.env.json").resolve()
            env_file.write_text(json.dumps(env, ensure_ascii=False), encoding="utf-8")

        wrapper_script = Path(__file__).resolve().parents[1] / "utils" / "platform" / "windows" / "child_session_wrapper.py"
        resolved_cwd = str((cwd or (Path(program).parent if Path(program).is_file() else Path.cwd())).resolve())
        target_cmd = [str(program), *[str(a) for a in args]]

        wrapper_args_list = [
            str(wrapper_script),
            "--state-file",
            str(state_file),
            "--cwd",
            resolved_cwd,
        ]
        if env_file is not None:
            wrapper_args_list.extend(["--env-file", str(env_file)])
        wrapper_args_list.append("--")
        wrapper_args_list.extend(target_cmd)

        quoted_args = subprocess.list2cmdline(wrapper_args_list)
        python_exe = sys.executable
        pythonw_exe = Path(python_exe).with_name("pythonw.exe")
        if pythonw_exe.is_file():
            python_exe = str(pythonw_exe)

        # 优先通过 C# ChildSessionHost 的 /launch 接口触发 Schedule.Service，若不可达则走 Python COM
        resp = await self._http_call(
            "/launch",
            method="POST",
            payload={
                "executablePath": python_exe,
                "arguments": quoted_args,
                "workingDirectory": str(Path.cwd().resolve()),
            },
            timeout=40.0,
        )
        if not resp or not resp.get("ok"):
            await asyncio.to_thread(
                self._launch_via_task_scheduler_sync,
                session_id,
                python_exe,
                quoted_args,
                str(Path.cwd().resolve()),
            )

        wrapped = ChildSessionWrappedProcess(
            job_id=job_id,
            state_file=state_file,
            session_id=session_id,
            command=target_cmd,
        )

        # 等待包装器落盘初始状态文件（最多 10 秒）
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if state_file.is_file():
                wrapped._refresh_from_disk()
                data = json.loads(state_file.read_text(encoding="utf-8"))
                if data.get("session_id") != session_id:
                    wrapped.terminate()
                    raise RuntimeError("进程包装器未在指定的 RDP 子会话启动")
                if wrapped._status == "error":
                    raise RuntimeError(f"RDP 子会话启动失败: {wrapped._error}")
                break
            await asyncio.sleep(0.1)
        else:
            wrapped.terminate()
            raise RuntimeError("RDP 子会话进程启动超时，未收到包装器状态")

        logger.info(
            f"已在远程桌面 (Session={session_id}) 通过包装器启动进程: {target_cmd}, PID={wrapped.pid}"
        )
        return wrapped

    # ==================== 外部程序借用远程桌面与回传机制 ====================

    def _prune_expired_leases(self) -> None:
        now = time.monotonic()
        expired_ids = [
            lid
            for lid, lease in self._leases.items()
            if lease.expires_at_monotonic is not None and now >= lease.expires_at_monotonic
        ]
        for lid in expired_ids:
            lease = self._leases.pop(lid, None)
            if lease is not None:
                logger.warning(f"外部远程桌面租约已超时自动释放: caller={lease.caller}, leaseId={lid}")
        if not self._leases:
            self._all_leases_released_event.set()

    def has_external_lease_requests(self) -> bool:
        """检查当前是否有外部程序正在申请或正在使用本地远程桌面。"""
        self._prune_expired_leases()
        return bool(self._leases)

    def list_leases(self) -> list[dict[str, Any]]:
        self._prune_expired_leases()
        return [lease.to_dict() for lease in self._leases.values()]

    async def acquire_external_lease(
        self,
        caller: str,
        *,
        disconnect_rdp_view: bool = True,
        timeout_seconds: float = 3600.0,
        wait_for_grant: bool = False,
        wait_timeout: float = 300.0,
    ) -> ExternalDesktopLease:
        """供外部程序申请连接/使用本地远程桌面。

        - 若当前没有正在执行的子任务（处于空闲或子任务间隔），立即批准（`status="granted"`）；
        - 若当前有子任务正在运行，则记为 `status="pending"`，在当前子任务结束、进入下一个子任务前
          的间隔处自动让渡并切换为 `status="granted"`。
        """
        self._prune_expired_leases()
        lease_id = str(uuid.uuid4())
        expires_at = time.monotonic() + timeout_seconds if timeout_seconds > 0 else None
        lease = ExternalDesktopLease(
            lease_id=lease_id,
            caller=caller or "external",
            disconnect_rdp_view=disconnect_rdp_view,
            status="pending",
            expires_at_monotonic=expires_at,
        )
        self._leases[lease_id] = lease
        self._all_leases_released_event.clear()
        logger.info(
            f"收到外部程序 [{lease.caller}] 的本地远程桌面使用申请 (leaseId={lease_id}, "
            f"disconnectRdpView={disconnect_rdp_view})"
        )

        if self._in_subtask_execution == 0:
            await self._grant_pending_leases()

        if wait_for_grant and lease.status != "granted":
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(lease._granted_event.wait(), timeout=wait_timeout)

        return lease

    async def _grant_pending_leases(self) -> None:
        self._prune_expired_leases()
        if not self._leases:
            return

        need_disconnect = any(lease.disconnect_rdp_view for lease in self._leases.values())
        callers = ", ".join(sorted({lease.caller for lease in self._leases.values()}))

        if need_disconnect and not self._rdp_view_disconnected_for_external:
            await self._http_call(
                "/disconnect",
                method="POST",
                payload={"caller": callers, "disconnectRdpView": True},
                timeout=5.0,
            )
            self._rdp_view_disconnected_for_external = True

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for lease in self._leases.values():
            if lease.status == "pending":
                lease.status = "granted"
                lease.granted_at = now_str
                lease._granted_event.set()

    async def release_external_lease(
        self,
        *,
        lease_id: str | None = None,
        caller: str | None = None,
    ) -> list[str]:
        """外部程序停止使用本地远程桌面时的回传接口。

        释放对应的租约；当所有外部租约均已释放时，自动通知 C# 宿主重连常驻 RDP 画面并唤醒队列继续执行。
        """
        self._prune_expired_leases()
        released: list[str] = []

        for lid, lease in list(self._leases.items()):
            if (lease_id and lid == lease_id) or (caller and lease.caller == caller) or (
                not lease_id and not caller
            ):
                self._leases.pop(lid, None)
                released.append(lid)
                logger.info(f"外部程序 [{lease.caller}] 已回传释放远程桌面租约 (leaseId={lid})")

        if not self._leases:
            if self._rdp_view_disconnected_for_external:
                self._rdp_view_disconnected_for_external = False
                if self.enabled:
                    await self._http_call("/reconnect", method="POST", payload={}, timeout=30.0)
            self._all_leases_released_event.set()

        return released

    async def wait_if_external_requested(self, boundary_label: str = "子任务间隔") -> bool:
        """在队列相邻两个子任务间隔调用：检查是否有其他程序需要连接该远程桌面，并在其停止使用回传后继续。

        Returns:
            bool: 若期间发生了让渡等待则返回 True，未发生返回 False。
        """
        self._prune_expired_leases()
        if not self._leases:
            return False

        callers = ", ".join(sorted({lease.caller for lease in self._leases.values()}))
        logger.info(
            f"[{boundary_label}] 检测到外部程序 ({callers}) 需要使用本地远程桌面，"
            "正在让渡远程桌面并暂停后续任务，等待外部程序停止使用回传..."
        )
        await self._grant_pending_leases()

        while self.has_external_lease_requests():
            try:
                await asyncio.wait_for(self._all_leases_released_event.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self._prune_expired_leases()

        logger.info(f"[{boundary_label}] 外部程序已停止使用本地远程桌面并完成回传，恢复任务队列执行")
        return True

    def enter_subtask(self) -> None:
        self._in_subtask_execution += 1

    def exit_subtask(self) -> None:
        self._in_subtask_execution = max(0, self._in_subtask_execution - 1)

    async def get_status(self) -> dict[str, Any]:
        self._prune_expired_leases()
        host_status = await self._http_call("/status", method="GET", timeout=2.0)
        sid = (
            host_status.get("childSessionId")
            if host_status
            else await asyncio.to_thread(self.wts_get_child_session_id)
        )
        return {
            "enabled": self.enabled,
            "hostPort": self.host_port,
            "childSessionId": sid,
            "hostConnected": bool(host_status and host_status.get("connectedState") == 1),
            "hostStatus": host_status,
            "inSubtaskExecution": self._in_subtask_execution > 0,
            "activeLeases": self.list_leases(),
        }


ChildSessionManager = _ChildSessionManager()
