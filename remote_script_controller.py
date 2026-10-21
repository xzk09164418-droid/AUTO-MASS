"""AUTO-MAS 本地远程桌面脚本运行控制程序 (CLI / SDK / 守护进程入口)。

整合特性：
1. 基于 BetterGI 的本地远程桌面 (Windows Child Session) 常驻连接与 C# 宿主联动
2. 外部程序借用远程桌面 (`acquire`) 与停止使用时机回传 (`release`) 接口，队列相邻子任务间隔自动检查并让渡
3. 包装器模式 (`child_session_wrapper.py`) 获取子会话内脚本运行状态与退出码
4. 保留全部游戏专项适配器、多用户切换、队列定时/循环调度、消息通知，并新增系统全局热键（启停、上/下一个任务）
5. 任务超时设定为“从任务开始到结束”的总上限时间（含全部重试），同时保留有日志模式下的日志停滞超时
6. 功能精简：不强制要求填写日志路径（日志路径为空时，日志超时自动失效，只要在上限时间内自行退出不限返回码即视为成功；超过上限时间强制调用 `taskkill /F /T` 强杀 3 遍并视为失败）；移除配置回写，仅通过外部程序自身的启动参数控制启停
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


def _api_request(
    port: int,
    endpoint: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"http://127.0.0.1:{port}{endpoint}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30.0) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


async def run_standalone_script_task(
    executable: str,
    arguments: list[str],
    *,
    log_path: str = "",
    success_log: str = "",
    error_log: str = "",
    log_stall_minutes: float = 10.0,
    hard_limit_minutes: float = 120.0,
    retries: int = 3,
    use_child_session: bool = True,
) -> dict[str, Any]:
    """直接以重构后的双模超时与远程桌面包装器逻辑运行单个外部脚本任务（含重试与 3 遍 taskkill /F /T）。"""
    from app.services import System
    from app.utils import ProcessManager, compile_log_signs, get_logger

    logger = get_logger("独立脚本控制器")
    exe_path = Path(executable).resolve()
    has_log = bool(log_path.strip())
    total_budget_seconds = hard_limit_minutes * 60.0
    started_monotonic = time.monotonic()

    def remaining_seconds() -> float:
        return max(0.0, total_budget_seconds - (time.monotonic() - started_monotonic))

    async def force_cleanup(pm: ProcessManager) -> None:
        await pm.kill()
        await System.kill_process(exe_path, kill_tree=True)

    pm = ProcessManager()
    success_matcher = compile_log_signs(success_log, "Split")
    error_matcher = compile_log_signs(error_log, "Split")

    try:
        async with asyncio.timeout(total_budget_seconds):
            for attempt in range(1, max(1, retries) + 1):
                if remaining_seconds() <= 0:
                    break
                logger.info(
                    f"开始执行任务 [{exe_path.name}] (尝试 {attempt}/{retries}, "
                    f"剩余总上限时间: {remaining_seconds():.1f}s, 远程桌面={use_child_session})"
                )
                await force_cleanup(pm)
                await pm.open_process(
                    exe_path,
                    *arguments,
                    cwd=exe_path.parent,
                    use_child_session=use_child_session,
                )

                if not has_log:
                    # 无日志模式：日志超时自动失效，只要在上限时间内自行退出（不限返回码）即视为成功
                    while await pm.is_running():
                        await asyncio.sleep(0.3)
                    rc = pm.returncode
                    await force_cleanup(pm)
                    logger.success(
                        f"无日志模式：脚本已在总上限时间内自行退出 (退出码={rc})，判定为成功"
                    )
                    return {
                        "status": "success",
                        "mode": "no_log",
                        "attempt": attempt,
                        "returncode": rc,
                        "elapsedSeconds": round(time.monotonic() - started_monotonic, 2),
                    }
                else:
                    # 有日志模式：保留原 Auto-MAS 判定逻辑 + 日志停滞超时
                    target_log = Path(log_path).resolve()
                    last_mtime = target_log.stat().st_mtime if target_log.is_file() else 0.0
                    last_progress_at = time.monotonic()
                    attempt_outcome = "running"

                    while True:
                        content = ""
                        if target_log.is_file():
                            stat = target_log.stat()
                            if stat.st_mtime != last_mtime:
                                last_mtime = stat.st_mtime
                                last_progress_at = time.monotonic()
                            content = target_log.read_text(encoding="utf-8", errors="replace")

                        if success_matcher.search(content) is not None:
                            attempt_outcome = "success"
                            break
                        err_hit = error_matcher.search(content)
                        if err_hit is not None:
                            attempt_outcome = f"error_log:{err_hit}"
                            break
                        if time.monotonic() - last_progress_at > log_stall_minutes * 60.0:
                            attempt_outcome = "log_stalled_timeout"
                            break
                        if not await pm.is_running():
                            if success_matcher.configured:
                                attempt_outcome = "exited_before_success_log"
                            else:
                                attempt_outcome = "success"
                            break
                        await asyncio.sleep(0.5)

                    rc = pm.returncode
                    await force_cleanup(pm)
                    if attempt_outcome == "success":
                        return {
                            "status": "success",
                            "mode": "with_log",
                            "attempt": attempt,
                            "returncode": rc,
                            "elapsedSeconds": round(time.monotonic() - started_monotonic, 2),
                        }
                    logger.warning(f"第 {attempt} 次尝试未成功: {attempt_outcome}")
                    if attempt < retries:
                        await asyncio.sleep(3.0)

            return {
                "status": "failed",
                "reason": "retries_exhausted",
                "elapsedSeconds": round(time.monotonic() - started_monotonic, 2),
            }
    except TimeoutError:
        logger.warning(
            f"任务超过总上限时间 ({hard_limit_minutes} 分钟)，正在执行 3 遍 taskkill /F /T 强制清理..."
        )
        await force_cleanup(pm)
        return {
            "status": "failed",
            "reason": "hard_time_limit_exceeded",
            "elapsedSeconds": round(time.monotonic() - started_monotonic, 2),
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AUTO-MAS 远程桌面脚本控制程序 (支持服务端启动、单脚本控制、远程桌面租约与热键指令)"
    )
    parser.add_argument("--port", type=int, default=36163, help="AUTO-MAS 后端 HTTP 端口 (默认 36163)")
    sub = parser.add_subparsers(dest="subcommand")

    # 1. 启动完整 AUTO-MAS 服务
    sub.add_parser("serve", help="启动完整 AUTO-MAS 后台服务（含常驻远程桌面、队列调度与全局热键）")

    # 2. 直接运行外部脚本任务
    run_p = sub.add_parser("run-script", help="直接运行并监控单个外部脚本（支持远程桌面包装器与双模超时）")
    run_p.add_argument("executable", help="外部脚本或程序可执行文件路径")
    run_p.add_argument("--args", nargs="*", default=[], help="传递给外部程序的启动参数")
    run_p.add_argument("--log-path", default="", help="可选日志文件路径（留空则仅以在上限时间内自行退出作为成功条件）")
    run_p.add_argument("--success-log", default="", help="可选成功日志关键字")
    run_p.add_argument("--error-log", default="", help="可选异常日志关键字")
    run_p.add_argument("--log-timeout", type=float, default=10.0, help="日志未刷新超时分钟数（仅填写日志路径时生效）")
    run_p.add_argument("--hard-timeout", type=float, default=120.0, help="从任务开始到结束的总上限时间（分钟，含全部重试）")
    run_p.add_argument("--retries", type=int, default=3, help="最大尝试次数")
    run_p.add_argument("--local-desktop", action="store_true", help="在当前主桌面而非本地远程桌面分身中运行")

    # 3. 外部程序申请借用本地远程桌面
    acq_p = sub.add_parser("acquire-desktop", help="外部程序申请使用本地远程桌面（队列将在子任务间隔让渡桌面）")
    acq_p.add_argument("--caller", required=True, help="外部程序名称或标识")
    acq_p.add_argument("--keep-rdp-view", action="store_true", help="保持 AUTO-MAS 的 RDP 预览窗口不断开")
    acq_p.add_argument("--wait", action="store_true", help="等待当前正在运行的子任务结束并完成让渡后再返回")

    # 4. 外部程序停止使用远程桌面后回传
    rel_p = sub.add_parser("release-desktop", help="外部程序停止使用本地远程桌面后回传释放，恢复队列运行")
    rel_p.add_argument("--lease-id", default=None, help="申请时返回的 leaseId")
    rel_p.add_argument("--caller", default=None, help="外部程序名称或标识")

    # 5. 任务导航与启停控制
    nav_p = sub.add_parser("control", help="发送启停或上/下一个任务指令")
    nav_p.add_argument("action", choices=["toggle", "prev", "next", "status"], help="控制动作")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand or args.subcommand == "serve":
        import main as server_main

        server_main.main()
        return 0

    if args.subcommand == "run-script":
        result = asyncio.run(
            run_standalone_script_task(
                args.executable,
                list(args.args),
                log_path=args.log_path,
                success_log=args.success_log,
                error_log=args.error_log,
                log_stall_minutes=args.log_timeout,
                hard_limit_minutes=args.hard_timeout,
                retries=args.retries,
                use_child_session=not args.local_desktop,
            )
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") == "success" else 1

    if args.subcommand == "acquire-desktop":
        resp = _api_request(
            args.port,
            "/api/child-session/acquire",
            method="POST",
            payload={
                "caller": args.caller,
                "disconnectRdpView": not args.keep_rdp_view,
                "waitForGrant": bool(args.wait),
            },
        )
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return 0

    if args.subcommand == "release-desktop":
        resp = _api_request(
            args.port,
            "/api/child-session/release",
            method="POST",
            payload={"leaseId": args.lease_id, "caller": args.caller},
        )
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return 0

    if args.subcommand == "control":
        if args.action == "status":
            resp = _api_request(args.port, "/api/child-session/status", method="GET")
        elif args.action == "toggle":
            resp = _api_request(args.port, "/api/dispatch/navigation/toggle", method="POST", payload={})
        elif args.action == "prev":
            resp = _api_request(args.port, "/api/dispatch/navigation/previous", method="POST", payload={})
        else:
            resp = _api_request(args.port, "/api/dispatch/navigation/next", method="POST", payload={})
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
