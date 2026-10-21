import asyncio
import os
import subprocess

from ..common.process_runner import ProcessRunner

# 强制清理时连续执行 taskkill /F /T 的次数（需求：到时或结束时直接调用 taskkill /F /T 强杀 3 遍）
FORCE_KILL_PASSES = 3


class WindowsProcessPlatform:
    # 后端被 AUTO-MAS-Runtime 用 Job Object 监督（KILL_ON_JOB_CLOSE，且允许
    # breakaway）时，子进程默认都留在 Job 里：MAA.exe、各专项脚本进程、MaaFW
    # agent、taskkill/schtasks 之类的工具调用，在后端被硬杀或宿主崩溃时都要
    # 能被 Job 一并回收，不能变成孤儿。所以 creation_flags 只有基础标志，
    # 不带 CREATE_BREAKAWAY_FROM_JOB。
    #
    # 按 Runtime 契约 C8（游戏与模拟器不随后端退出）和 D-3 决策（AUTO-MAS 只在
    # 拉起游戏/模拟器时带 CREATE_BREAKAWAY_FROM_JOB），脱离标志单独放在
    # breakaway_flags 里，由 ProcessManager.open_process / ProcessRunner.run_process
    # 的 breakaway=True 调用点按需叠加——目前只有模拟器控制台、general 脚本
    # 的游戏客户端和 MaaFW DirectExe 桌面游戏三处，其余调用点一律默认 False，
    # 不要把它加回全局标志。
    #
    # 父进程若恰好处在一个不允许 breakaway 的 Job 里，带这个标志的
    # CreateProcess 会以 ERROR_ACCESS_DENIED（WinError 5）失败；
    # process_runner.create_subprocess 对此有去掉该位重试一次的兜底。
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    breakaway_flags = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
    # 自更新时接替当前进程的安装程序必须活过后端退出，因此这组标志固定带
    # 脱离位。注意 DETACHED_PROCESS 本身不会让子进程脱离 Job，必须靠
    # CREATE_BREAKAWAY_FROM_JOB 才行，不要以为 DETACHED_PROCESS 已经处理了
    # 这件事。
    detached_flags = (
        getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
    )

    async def open_protocol(self, protocol_url: str) -> None:
        if hasattr(os, "startfile"):
            os.startfile(protocol_url)

    async def kill_process(
        self,
        pid: int,
        kill_tree: bool = True,
        passes: int = FORCE_KILL_PASSES,
    ) -> tuple[bool, str]:
        """用 taskkill /F /T 连续强杀进程（默认强杀 3 遍），返回 (是否成功, 失败原因)。"""

        args = ["taskkill", "/F"]
        if kill_tree:
            args.append("/T")
        args.extend(["/PID", str(pid)])

        any_succeeded = False
        last_error = ""
        total_passes = max(1, int(passes))

        for attempt in range(total_passes):
            result = await ProcessRunner.run_process(*args)
            if result.returncode == 0:
                any_succeeded = True
            else:
                output = result.stderr.strip() or result.stdout.strip() or "无错误信息"
                last_error = f"返回码: {result.returncode}, 原因: {output}"
            if attempt + 1 < total_passes:
                await asyncio.sleep(0.1)

        if any_succeeded:
            return True, ""
        return False, last_error

    async def kill_process_by_image_name(
        self,
        image_name: str,
        kill_tree: bool = True,
        passes: int = FORCE_KILL_PASSES,
    ) -> tuple[bool, str]:
        """按映像名（/IM）连续调用 taskkill /F /T 强杀 3 遍（覆盖本地及 Child Session 子会话进程）。"""

        args = ["taskkill", "/F"]
        if kill_tree:
            args.append("/T")
        args.extend(["/IM", str(image_name)])

        any_succeeded = False
        last_error = ""
        total_passes = max(1, int(passes))

        for attempt in range(total_passes):
            result = await ProcessRunner.run_process(*args)
            if result.returncode == 0:
                any_succeeded = True
            else:
                output = result.stderr.strip() or result.stdout.strip() or "无错误信息"
                last_error = f"返回码: {result.returncode}, 原因: {output}"
            if attempt + 1 < total_passes:
                await asyncio.sleep(0.1)

        if any_succeeded:
            return True, ""
        return False, last_error
