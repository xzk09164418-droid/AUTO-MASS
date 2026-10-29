#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2024-2025 DLmaster361
#   Copyright © 2025 MoeSnowyFox
#   Copyright © 2025-2026 AUTO-MAS Team

#   This file is part of AUTO-MAS.

#   AUTO-MAS is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of
#   the License, or (at your option) any later version.

#   AUTO-MAS is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
#   the GNU Affero General Public License for more details.

#   You should have received a copy of the GNU Affero General Public License
#   along with AUTO-MAS. If not, see <https://www.gnu.org/licenses/>.

#   Contact: DLmaster_361@163.com


import argparse
import ctypes
import logging
import os
import sys
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import perf_counter
from typing import Any

current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))
if __name__ == "__main__" and os.getenv("AUTO_MAS_SUPERVISED") != "1":
    os.chdir(current_dir)

from app.utils import (  # noqa: E402
    get_logger,
    is_supervised,
    resource_path,
    sanitize_log_message,
)
from app.utils.platform import IS_WINDOWS, is_admin  # noqa: E402

logger = get_logger("主程序")

# 清理启动链路（Runtime → uv run → 后端）注入的 Python/uv 环境变量。
_leaked_venv = os.environ.pop("VIRTUAL_ENV", None)
for _leaked_env in ("UV", "UV_PROJECT_ENVIRONMENT", "UV_RUN_RECURSION_DEPTH"):
    os.environ.pop(_leaked_env, None)
if _leaked_venv is not None:
    logger.info(f"已清理启动链路注入的环境变量: VIRTUAL_ENV={_leaked_venv}")
    _venv_scripts = os.path.normcase(
        os.path.join(_leaked_venv, "Scripts" if os.name == "nt" else "bin").rstrip(
            "\\/"
        )
    )
    _path_entries = os.environ.get("PATH", "").split(os.pathsep)
    _kept_entries = [
        _entry
        for _entry in _path_entries
        if os.path.normcase(_entry.rstrip("\\/")) != _venv_scripts
    ]
    if _kept_entries != _path_entries:
        os.environ["PATH"] = os.pathsep.join(_kept_entries)
        logger.info(f"已从 PATH 摘除启动链路注入的段: {_venv_scripts}")

from app.services.instance_identity import (  # noqa: E402
    DEFAULT_PORTS,
    configured_backend_port,
)

DEFAULT_HTTP_PORT = DEFAULT_PORTS["backendPort"]
DEV_HTTP_PORT = DEFAULT_PORTS["developmentBackendPort"]
SUPERVISED_PORT_ENV = "AUTO_MAS_SUPERVISED_PORT"
SUPERVISED_PORT_MIN = 1024
BACKGROUND_ERROR_MESSAGE_MAX = 300
BACKGROUND_WARNINGS_MAX = 20


class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        if record.name == "uvicorn.access":
            level = "DEBUG"
        sanitized_message = sanitize_log_message(record.getMessage())
        logger.opt(depth=6, exception=record.exc_info).log(level, sanitized_message)


logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
    logging.getLogger(name).handlers = [InterceptHandler()]
    logging.getLogger(name).propagate = False


def parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AUTO-MAS 后端服务（支持前后端分离模式，也支持通过启动参数无窗口直接运行任务）",
        add_help=True,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="指定后端 HTTP/WS 监听端口（默认 36163）",
    )
    parser.add_argument(
        "--headless",
        "--no-window",
        dest="headless",
        action="store_true",
        help="无窗口静默运行模式（不打开前端窗口，远程桌面在系统托盘静默运行）",
    )
    parser.add_argument(
        "--run-queue",
        dest="run_queue",
        default="",
        help="后端就绪后立即自动启动指定队列 ID（传入 first 表示启动第一个队列）",
    )
    parser.add_argument(
        "--run-script",
        dest="run_script",
        default="",
        help="后端就绪后立即自动启动指定脚本任务 ID",
    )
    parser.add_argument(
        "--auto-run",
        dest="auto_run",
        action="store_true",
        help="后端就绪后自动触发首个调度队列运行",
    )
    parser.add_argument(
        "--no-admin-restart",
        dest="no_admin_restart",
        action="store_true",
        help="禁用自动提权重启（由外层启动器或无头脚本托管时使用）",
    )
    args, _ = parser.parse_known_args(argv)
    return args


def restart_as_admin():
    """以管理员权限重启当前进程"""
    if IS_WINDOWS:
        executable = sys.executable.removesuffix(".exe")
        executable += ".exe"
        extra_args = " ".join(f'"{a}"' for a in sys.argv[1:])
        cmd_line = f'"{os.path.realpath(sys.argv[0])}" {extra_args}'.strip()
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            executable,
            cmd_line,
            None,
            0 if "--headless" in sys.argv or "--no-window" in sys.argv else 1,
        )
        sys.exit(0 if result > 32 else result)


def is_development_environment() -> bool:
    raw = str(os.getenv("AUTO_MAS_ENV", "")).strip().lower()
    if raw in {"dev", "development"}:
        return True
    return (current_dir / ".env").is_file()


def is_hosted_launch() -> bool:
    raw = str(os.getenv("AUTO_MAS_DEV", "")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def should_restart_as_admin(
    *,
    supervised: bool,
    admin: bool,
    hosted_launch: bool,
    development_environment: bool,
    no_admin_restart: bool = False,
) -> bool:
    if supervised or no_admin_restart:
        return False
    return not (admin or hosted_launch or development_environment)


def resolve_http_port(development_environment: bool, cli_port: int = 0) -> int:
    if 1 <= cli_port <= 65535:
        return cli_port

    raw = str(os.getenv("AUTO_MAS_HTTP_PORT", "")).strip()

    if is_supervised():
        if raw:
            logger.info(
                f"受监督模式下端口由运行时注入，已忽略 AUTO_MAS_HTTP_PORT={raw}"
            )
        return _resolve_supervised_port()

    if raw:
        try:
            port = int(raw)
        except ValueError:
            port = 0
        if 1 <= port <= 65535:
            return port
        logger.warning(f"AUTO_MAS_HTTP_PORT 取值无效，已忽略: {raw}")

    return configured_backend_port(development=development_environment)


def _resolve_supervised_port() -> int:
    raw = os.getenv(SUPERVISED_PORT_ENV)
    if raw is None:
        logger.warning(
            f"受监督模式下未注入 {SUPERVISED_PORT_ENV}，回退 {DEFAULT_HTTP_PORT}"
        )
        return DEFAULT_HTTP_PORT

    try:
        port = int(str(raw).strip())
    except ValueError:
        port = 0
    if SUPERVISED_PORT_MIN <= port <= 65535:
        return port

    logger.warning(f"{SUPERVISED_PORT_ENV} 取值无效，回退 {DEFAULT_HTTP_PORT}: {raw!r}")
    return DEFAULT_HTTP_PORT


@logger.catch
def main(argv: list[str] | None = None):
    cli_args = parse_cli_args(argv)
    if cli_args.headless:
        os.environ["AUTO_MAS_HEADLESS"] = "1"

    development_environment = is_development_environment()
    if development_environment:
        os.environ["AUTO_MAS_ENV"] = "development"

    supervised = is_supervised()
    admin = is_admin()
    if should_restart_as_admin(
        supervised=supervised,
        admin=admin,
        hosted_launch=is_hosted_launch(),
        development_environment=development_environment,
        no_admin_restart=bool(cli_args.no_admin_restart or cli_args.headless),
    ):
        restart_as_admin()
    elif supervised and not admin:
        logger.warning(
            "受监督模式下不自行提权，当前非管理员，依赖模拟器/窗口操作的功能可能受限"
        )

    import asyncio

    from app.core.desktop_runtime import relay_to_execution_session

    relay_returncode = asyncio.run(
        relay_to_execution_session(
            list(sys.argv[1:] if argv is None else argv),
            http_port=resolve_http_port(development_environment, cli_args.port),
        )
    )
    if relay_returncode is not None:
        raise SystemExit(relay_returncode)

    # 主桌面只校验会话配置并转发，不重复加载实际后端使用的业务服务。
    from app.core import Config
    from app.core.restore_bindings import resolve_restore_pools
    from app.services.telemetry import (
        init_sentry,
        is_telemetry_enabled,
        resolve_sentry_dist,
    )

    Config.set_restore_pool_resolver(resolve_restore_pools)

    init_sentry(
        release=Config.VERSION,
        development=development_environment,
        enabled=is_telemetry_enabled(Path.cwd() / "config" / "Config.json"),
        dist=resolve_sentry_dist(current_dir),
    )

    from contextlib import asynccontextmanager, suppress

    import uvicorn
    from fastapi import Depends, FastAPI
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from app.core import Config, MainTimer, TaskManager

        await Config.init_config()
        from app.core.external_control_mail import run_mail_control
        from app.core.external_holds import external_holds

        await external_holds.initialize()
        external_mail_task = asyncio.create_task(
            run_mail_control(lambda sid: uuid.UUID(sid) in Config.ScriptConfig),
            name="external-control-mail",
        )

        from app.core.desktop_runtime import watch_execution_session

        desktop_watch = asyncio.create_task(watch_execution_session())

        # 默认强制开启远程桌面托盘隐藏模式，避免打扰主桌面
        with suppress(Exception):
            if Config.get("ChildSession", "StartHidden") is None:
                await Config.set("ChildSession", "StartHidden", True)

        from app.api.ws_command import execute_ws_command
        from app.core.notify_channels import initialize_notification_channels

        initialize_notification_channels(command_executor=execute_ws_command)

        background_task: asyncio.Task | None = None

        async def initialize_background_services() -> None:
            warnings: list[str] = []

            async def run_step(
                name: str, step: Callable[[], Awaitable[Any]]
            ) -> str | None:
                started = perf_counter()
                try:
                    await step()
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    logger.exception(f"后台初始化步骤失败: {name}")
                    message = str(error)
                    if len(message) > BACKGROUND_ERROR_MESSAGE_MAX:
                        message = message[:BACKGROUND_ERROR_MESSAGE_MAX] + "…"
                    return f"{name}（{type(error).__name__}: {message}）"
                finally:
                    logger.info(
                        f"后台初始化步骤结束: {name}，耗时 {perf_counter() - started:.3f} 秒"
                    )
                return None

            async def run_optional_step(
                name: str, step: Callable[[], Awaitable[Any]]
            ) -> None:
                failure = await run_step(name, step)
                if failure is not None:
                    warnings.append(failure)

            async def mount_mcp() -> None:
                from app.api.mcp import mount_mcp as mount_mcp_server

                await mount_mcp_server(
                    app, backend_url=f"http://127.0.0.1:{Config.server.config.port}"
                )

            async def start_desktop_guard() -> None:
                from app.core.desktop_guard import DesktopGuard

                await DesktopGuard.start()

            async def start_child_session() -> None:
                from app.core.child_session import ChildSessionManager

                await ChildSessionManager.start()

            async def start_hotkeys() -> None:
                from app.core.hotkey_manager import HotkeyManager

                await HotkeyManager.start()

            async def init_stage_info() -> None:
                await Config.get_stage(wait_stale=False)

            async def start_notifications() -> None:
                from app.services.notification import Notify

                await Notify.start()

            async def run_cli_startup_tasks() -> None:
                """当通过启动参数传入 --run-queue / --run-script / --auto-run 时，无窗口直接启动对应任务。"""
                target_queue = str(cli_args.run_queue or "").strip()
                target_script = str(cli_args.run_script or "").strip()
                if cli_args.auto_run and not target_queue and not target_script:
                    target_queue = "first"

                if target_queue:
                    target_id = None
                    if target_queue.lower() == "first" and Config.QueueConfig:
                        target_id = next(iter(Config.QueueConfig.keys()))
                    elif target_queue.lower() != "first":
                        try:
                            target_id = uuid.UUID(target_queue)
                        except ValueError:
                            pass
                    if target_id is not None and target_id in Config.QueueConfig:
                        logger.info(
                            f"启动参数触发队列直接运行 (无窗口模式): Queue={target_id}"
                        )
                        await TaskManager.add_task("AutoProxy", str(target_id))
                    else:
                        logger.warning(f"启动参数指定的队列不存在: {target_queue}")

                if target_script:
                    try:
                        script_id = uuid.UUID(target_script)
                    except ValueError:
                        script_id = None
                    if script_id is not None and script_id in Config.ScriptConfig:
                        logger.info(
                            f"启动参数触发单脚本直接运行 (无窗口模式): Script={target_script}"
                        )
                        await TaskManager.add_task("AutoProxy", target_script)
                    else:
                        logger.warning(f"启动参数指定的脚本不存在: {target_script}")

            app.state.background_status = "running"
            try:
                # 先确认执行会话，再并发启动核心服务；调度器不依赖 MCP。
                await run_optional_step("本地远程桌面分身", start_child_session)
                async with asyncio.TaskGroup() as startup:
                    startup.create_task(
                        run_optional_step("桌面显示输出守卫", start_desktop_guard)
                    )
                    startup.create_task(
                        run_optional_step("全局热键服务", start_hotkeys)
                    )
                    startup.create_task(
                        run_optional_step("通知渠道", start_notifications)
                    )
                    startup.create_task(
                        run_optional_step("活动关卡信息获取", init_stage_info)
                    )

                from app.core.desktop_recovery import DesktopRecovery

                recovered = await DesktopRecovery.restore()
                timer_error = await run_step("主业务定时器", MainTimer.start)
                if not recovered:
                    await run_optional_step("启动参数直接运行任务", run_cli_startup_tasks)

                if timer_error is None:
                    logger.info("后端核心服务已就绪，继续配置按需服务入口")
                await run_optional_step("MCP 服务挂载", mount_mcp)

                if (Path.cwd() / "AUTO-MAS-Setup.exe").exists():
                    try:
                        (Path.cwd() / "AUTO-MAS-Setup.exe").unlink()
                    except Exception as e:
                        logger.error(f"删除AUTO-MAS-Setup.exe失败: {e}")
                if (Path.cwd() / "AUTO_MAA.exe").exists():
                    try:
                        (Path.cwd() / "AUTO_MAA.exe").unlink()
                    except Exception as e:
                        logger.error(f"删除AUTO_MAA.exe失败: {e}")

                if len(warnings) > BACKGROUND_WARNINGS_MAX:
                    omitted = len(warnings) - (BACKGROUND_WARNINGS_MAX - 1)
                    warnings[BACKGROUND_WARNINGS_MAX - 1 :] = [
                        f"另有 {omitted} 项失败，详见日志"
                    ]
                app.state.background_warnings = warnings
                if warnings:
                    logger.warning(f"部分后台服务启动失败: {'；'.join(warnings)}")
                if timer_error is not None:
                    app.state.background_error = timer_error
                    app.state.background_status = "failed"
                    logger.error(f"后台初始化失败: {timer_error}")
                else:
                    app.state.background_status = "ready"
                    if not warnings:
                        logger.info("后端后台初始化完成")
            except asyncio.CancelledError:
                app.state.background_status = "cancelled"
                raise
            except Exception as error:
                app.state.background_status = "failed"
                app.state.background_error = f"{type(error).__name__}: {error}"
                logger.exception(f"后台初始化失败: {app.state.background_error}")

        app.state.background_status = "starting"
        app.state.background_error = None
        app.state.background_warnings = []
        background_task = asyncio.create_task(initialize_background_services())

        async def shutdown_services() -> None:
            from app.core.ws import Dispatcher, MainConnection
            from app.runtime_tasks import RuntimeTasks
            from app.services import Matomo, System, Updater

            external_mail_task.cancel()
            with suppress(asyncio.CancelledError):
                await external_mail_task

            mcp_runtime = getattr(app.state, "mcp_runtime", None)
            if mcp_runtime is not None:
                await mcp_runtime.close()

            if background_task is not None and not background_task.done():
                background_task.cancel()
                with suppress(asyncio.CancelledError):
                    await background_task
            maintenance = getattr(app.state, "maafw_startup_maintenance", None)
            if maintenance is not None and not maintenance.done():
                maintenance.cancel()
                with suppress(asyncio.CancelledError):
                    await maintenance

            await MainConnection.begin_shutdown()
            await Dispatcher.shutdown()
            await MainConnection.cancel_hook_tasks()

            with suppress(RuntimeError):
                await System.cancel_power_task()

            await MainTimer.stop()
            await TaskManager.stop_task("ALL")

            desktop_watch.cancel()
            with suppress(asyncio.CancelledError):
                await desktop_watch

            from app.core.child_session import ChildSessionManager
            from app.core.desktop_guard import DesktopGuard
            from app.core.hotkey_manager import HotkeyManager

            await HotkeyManager.stop()
            await ChildSessionManager.stop()
            await DesktopGuard.stop()

            with suppress(RuntimeError):
                await System.cancel_power_task()
            await Updater.cancel_download(notify=False)
            from app.services.obs_replay import ObsReplay

            await ObsReplay.stop()
            await RuntimeTasks.shutdown()
            from app.core.notify import shutdown_community_notifications

            await shutdown_community_notifications()
            from app.services.notification import Notify

            await Notify.stop()
            await Matomo.close()
            logger.info("AUTO-MAS 后端服务清理完成")

        from app.core.lifecycle import ShutdownCoordinator

        ShutdownCoordinator.set_teardown(shutdown_services)
        try:
            yield
        finally:
            await ShutdownCoordinator.run_teardown()
            logger.info("AUTO-MAS 后端程序关闭")

    from fastapi.middleware.cors import CORSMiddleware

    from app.api import (
        child_session_router,
        core_router,
        dispatch_router,
        emulator2_router,
        emulator_router,
        history_router,
        info_router,
        ocr_router,
        openclaw_qq_router,
        plan_router,
        qr_login_router,
        queue_router,
        scripts_router,
        setting_router,
        share_router,
        skland_qr_router,
        tools_router,
        update_router,
    )
    from app.api.network_policy import (
        enforce_network_policy,
        network_feature_disabled_response,
    )
    from app.utils.network_policy import NetworkFeatureDisabled

    app = FastAPI(
        dependencies=[Depends(enforce_network_policy)],
        title="AUTO-MAS",
        description="API for managing automation scripts, plans, and tasks",
        version="1.0.0",
        lifespan=lifespan,
    )

    from app.api.instance_guard import InstanceIdentityMiddleware

    app.add_middleware(InstanceIdentityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(NetworkFeatureDisabled, network_feature_disabled_response)
    app.include_router(core_router)
    app.include_router(child_session_router)
    app.include_router(info_router)
    app.include_router(scripts_router)
    app.include_router(plan_router)
    app.include_router(emulator_router)
    app.include_router(emulator2_router)
    app.include_router(queue_router)
    app.include_router(dispatch_router)
    app.include_router(history_router)
    app.include_router(tools_router)
    app.include_router(setting_router)
    app.include_router(share_router)
    app.include_router(update_router)
    app.include_router(ocr_router)
    app.include_router(openclaw_qq_router)
    app.include_router(qr_login_router)

    if skland_qr_router is not None:
        app.include_router(skland_qr_router)

    app.mount(
        "/api/res/materials",
        StaticFiles(directory=str(resource_path("images", "materials"))),
        name="materials",
    )
    app.mount(
        "/api/res/sounds",
        StaticFiles(directory=str(resource_path("sounds"))),
        name="sounds",
    )

    webui_dir = current_dir / "frontend" / "webui"
    if webui_dir.is_dir():

        @app.get("/", include_in_schema=False)
        async def serve_root_webui():
            return FileResponse(str(webui_dir / "index.html"))

        app.mount(
            "/webui",
            StaticFiles(directory=str(webui_dir), html=True),
            name="webui",
        )

    async def run_server():
        http_port = resolve_http_port(development_environment, cli_args.port)
        logger.info(f"后端监听端口: {http_port} (无窗口模式={bool(cli_args.headless)})")
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=http_port,
            log_level="info",
            log_config=None,
            ws_ping_interval=20.0,
            ws_ping_timeout=20.0,
        )
        server = uvicorn.Server(config)

        from app.core import Config

        Config.server = server
        await server.serve()

    asyncio.run(run_server())


if __name__ == "__main__":
    main()
