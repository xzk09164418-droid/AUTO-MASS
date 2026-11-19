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

import asyncio
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Literal,
    Optional,
)

import httpx
import truststore

# 仅用于类型标注的顶层依赖移到 TYPE_CHECKING，避免启动导入开销
if TYPE_CHECKING:
    import uvicorn
    from jinja2 import Environment

    from app.models.ConfigBase import ConfigBase
    from app.utils.config_restore import ConfigRestorePool, ConfigRestoreService

from app.core.general_only import retain_general_scripts
from app.models.config import (
    CLASS_BOOK,
    EmulatorConfig,
    GameSignAccountGroup,
    GeneralConfig,
    GeneralUserConfig,
    GlobalConfig,
    QueueConfig,
    QueueItem,
    TimeSet,
    Webhook,
)
from app.utils import get_logger, is_supervised, resource_path
from app.utils.community import next_community_account_name
from app.utils.constants import (
    TYPE_BOOK,
    UTC4,
    UTC8,
)
from app.utils.io import force_rmtree, write_file
from app.utils.paths import SOURCE_ROOT
from app.utils.platform import IS_WINDOWS

# 孤儿 venv 的宽限期：刚动过的一律不碰，避免与正在准备环境的运行抢。
MAAFW_AGENT_VENV_GRACE_SECONDS = 60 * 60
# 各专项失败诊断目录里参与保留期清理的文件后缀（诊断日志与截图）；
# 不在集合内的文件（如未来的标记/锁文件）不被自动清理触碰
DIAGNOSTIC_FILE_SUFFIXES = frozenset({".log", ".png", ".jpg"})
# 失败截图后缀（旧专项存量 PNG 与现行 JPEG 同口径）
DIAGNOSTIC_SCREENSHOT_SUFFIXES = frozenset({".png", ".jpg"})
# 单个诊断目录的失败截图总量上限，超出后按时间从旧到新回收；
# 每目录独立结算，一个专项的截图风暴不会挤掉其他专项的证据
DIAGNOSTIC_SCREENSHOT_MAX_BYTES = 10 * 1024 * 1024
# 诊断文件的统一保留天数：诊断文件不是用户数据，用固定保留期兜住无界
# 累积，不跟随历史记录保留时间设置
DIAGNOSTIC_RETENTION_DAYS = 15

#: 本进程启动时刻；启动清理只碰比它更早的半成品。
_PROCESS_STARTED_AT = time.time()

logger = get_logger("配置管理")

GAME_SIGN_RESULT_FILENAME = "GameSignResult.json"


def _load_game_sign_result_snapshot(path: Path, *, result_date: str) -> dict[str, Any]:
    """读取当天的游戏社区结果快照。"""

    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"读取游戏社区结果快照失败: {e}")
        return {}

    if not isinstance(payload, dict) or payload.get("date") != result_date:
        return {}

    result = payload.get("result")
    if not isinstance(result, dict):
        logger.warning("游戏社区结果快照格式无效，已忽略")
        return {}
    return result


def _save_game_sign_result_snapshot(
    path: Path | None, result: dict[str, Any], *, result_date: str
) -> None:
    """原子保存游戏社区结果快照（走 ``app.utils.io.write_file``）。"""

    if path is None:
        return

    try:
        write_file(path, {"date": result_date, "result": result})
    except (OSError, TypeError, ValueError) as e:
        logger.warning(f"保存游戏社区结果快照失败: {e}")


_PROXY_URL_SCHEMES = ("http://", "https://", "socks5://", "socks5h://", "socks4://")


def normalize_proxy_address(raw: str | None) -> str | None:
    """把 ``Update.ProxyAddress`` 规范成带协议的代理地址字符串。

    去首尾空白，空 → ``None``；没有协议前缀时补 ``http://``；``user:pw@`` 原样保留
    ——这是要写进子进程 ``HTTP_PROXY`` 的字符串，不是 ``httpx.Proxy``（后者会把
    userinfo 剥到 ``.auth``，``str(proxy.url)`` 会丢凭据）。
    """

    text = str(raw or "").strip()
    if not text:
        return None
    if not text.lower().startswith(_PROXY_URL_SCHEMES):
        text = f"http://{text}"
    return text


class AppConfig(GlobalConfig):
    VERSION = "v5.7.0"

    if TYPE_CHECKING:
        notify_env: Environment

    def __init__(self) -> None:
        super().__init__()

        self._restore_pool_resolver: (
            Callable[["ConfigBase"], list["ConfigRestorePool"]] | None
        ) = None

        logger.info("")
        logger.info("===================================")
        logger.info("AUTO-MAS 后端应用程序")
        logger.info(f"版本号:  {self.VERSION}")
        logger.info(f"工作目录:  {Path.cwd()}")
        logger.info("===================================")

        self.log_path = Path.cwd() / "debug/app.log"
        self.database_path = Path.cwd() / "data/data.db"
        self.config_path = Path.cwd() / "config"
        self.history_path = Path.cwd() / "history"
        # 检查目录
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.mkdir(parents=True, exist_ok=True)
        self.history_path.mkdir(parents=True, exist_ok=True)

        # Git 仓库延迟初始化，避免启动时导入 GitPython
        self._repo: Any = None
        self._repo_initialized = False

        self.server: Optional["uvicorn.Server"] = None
        self.power_sign: Literal[
            "NoAction",
            "Shutdown",
            "ShutdownForce",
            "Reboot",
            "Hibernate",
            "Sleep",
            "KillSelf",
            "RestartSelf",
            "Logoff",
        ] = "NoAction"
        # 电源操作前的静默延时秒数, 与 power_sign 一同由队列配置写入
        self.power_delay: int = 0
        self.temp_task: List[asyncio.Task] = []
        # 正在循环运行的队列，供配置改动前的安全检查使用
        self.running_cycle_queue_ids: set[uuid.UUID] = set()
        self._stage_refresh_task: Optional[asyncio.Task] = None
        # 上次活动关卡刷新失败的时间: 冷却期内不再重复请求远端
        self._stage_refresh_failed_at: Optional[datetime] = None
        self._game_sign_result_date = ""
        self._community_account_add_lock = asyncio.Lock()

        self._inject_truststore()

    def __getattr__(self, name: str) -> Any:
        # ConfigBase 初始化会遍历属性；用缺失属性入口避免 property 提前加载模板库。
        if name != "notify_env":
            raise AttributeError(
                f"{type(self).__name__!r} object has no attribute {name!r}"
            )

        from jinja2 import Environment, FileSystemLoader

        self.notify_env = Environment(
            loader=FileSystemLoader(str(resource_path("html")))
        )
        return self.notify_env

    @staticmethod
    def _inject_truststore() -> None:
        """等效 truststore.inject_into_ssl()，但避免其内部导入 requests (约 460ms)。

        requests / urllib3 未加载时无需 patch：后续导入会使用已替换的
        ssl.SSLContext，不必为注入证书支持提前加载 HTTP 客户端。
        """
        import ssl

        ssl.SSLContext = truststore.SSLContext  # type: ignore[misc]
        urllib3_ssl = sys.modules.get("urllib3.util.ssl_")
        if urllib3_ssl is not None:
            urllib3_ssl.SSLContext = truststore.SSLContext  # type: ignore[assignment]
        requests_adapters = sys.modules.get("requests.adapters")
        if requests_adapters is not None and (
            getattr(requests_adapters, "_preloaded_ssl_context", None) is not None
        ):
            setattr(
                requests_adapters,
                "_preloaded_ssl_context",
                truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            )

    def _get_repo(self) -> Any:
        """惰性初始化 Git 仓库，避免启动时导入 GitPython。"""
        if not self._repo_initialized:
            self._repo_initialized = True
            if (Path.cwd() / "environment/git/bin/git.exe").exists():
                os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = str(
                    Path.cwd() / "environment/git/bin/git.exe"
                )
            try:
                from git import Repo

                # .git 随源码走：受 AUTO-MAS-Runtime 监督时源码在 <app-root>/repo/，
                # 工作目录（app-root）下没有仓库，不能再按 Path.cwd() 打开
                self._repo = Repo(SOURCE_ROOT)
            except Exception as e:
                logger.warning(f"Git仓库初始化失败: {e}")
                self._repo = None
        return self._repo

    async def init_config(self) -> None:
        """初始化配置管理"""

        await asyncio.to_thread(retain_general_scripts, self.config_path)
        await self.check_data()

        await self.connect(self.config_path / "Config.json")
        await self.EmulatorConfig.connect(self.config_path / "EmulatorConfig.json")
        await self.ScriptConfig.connect(self.config_path / "ScriptConfig.json")
        await self.QueueConfig.connect(self.config_path / "QueueConfig.json")
        await self.ToolsConfig.connect(self.config_path / "ToolsConfig.json")

        # 游戏社区：连接账号组 MultipleConfig
        await self.ToolsConfig.GameSign_Accounts.connect(
            self.config_path / "GameSignAccounts.json"
        )

        # 游戏社区：恢复当天的结果快照，跨日结果不继续展示
        today = datetime.now(tz=UTC8).strftime("%Y-%m-%d")
        self.ToolsConfig._game_sign_result_data = _load_game_sign_result_snapshot(
            self.config_path / GAME_SIGN_RESULT_FILENAME,
            result_date=today,
        )
        self._game_sign_result_date = today

        from app.services import System
        from app.services.telemetry import set_telemetry_enabled

        self.bind("Start", "IfSelfStart", System.set_SelfStart)
        self.bind("Function", "IfAllowSleep", System.set_Sleep)
        self.bind("Function", "IfEnableTelemetry", set_telemetry_enabled)
        # 注册自启动会读写注册表, 不阻塞初始化; 持有引用避免被 GC 且异常不被静默吞掉
        self_start_task = asyncio.create_task(
            System.set_SelfStart(self.get("Start", "IfSelfStart"))
        )
        self.temp_task.append(self_start_task)

        def _self_start_done(t: asyncio.Task) -> None:
            if t in self.temp_task:
                self.temp_task.remove(t)
            if not t.cancelled() and t.exception() is not None:
                logger.warning(f"设置开机自启动失败: {t.exception()}")

        self_start_task.add_done_callback(_self_start_done)
        await System.set_Sleep(self.get("Function", "IfAllowSleep"))
        set_telemetry_enabled(self.get("Function", "IfEnableTelemetry"))

        self.loop = asyncio.get_running_loop()

        logger.info("程序初始化完成")

    async def check_data(self) -> None:
        """检查用户数据文件并处理数据文件版本更新"""

        # 生成主数据库
        if not self.database_path.exists():
            db = sqlite3.connect(self.database_path)
            cur = db.cursor()
            cur.execute("CREATE TABLE version(v text)")
            cur.execute("INSERT INTO version VALUES(?)", ("v1.11",))
            db.commit()
            cur.close()
            db.close()

        # 数据文件版本更新
        db = sqlite3.connect(self.database_path)
        cur = db.cursor()
        cur.execute("SELECT * FROM version WHERE True")
        version = cur.fetchall()

        if version[0][0] != "v1.11":
            logger.info(
                "数据文件版本更新开始",
            )
            if_streaming = False
            # v1.7-->v1.8
            if version[0][0] == "v1.7" or if_streaming:
                logger.info(
                    "数据文件版本更新: v1.7-->v1.8",
                )
                if_streaming = True

                if (Path.cwd() / "config/QueueConfig").exists():
                    for QueueConfig in (Path.cwd() / "config/QueueConfig").glob(
                        "*.json"
                    ):
                        with QueueConfig.open(encoding="utf-8") as f:
                            queue_config = json.load(f)

                        queue_config["QueueSet"]["TimeEnabled"] = queue_config[
                            "QueueSet"
                        ]["Enabled"]

                        for i in range(10):
                            queue_config["Queue"][f"Script_{i}"] = queue_config[
                                "Queue"
                            ][f"Member_{i + 1}"]
                            queue_config["Time"][f"Enabled_{i}"] = queue_config["Time"][
                                f"TimeEnabled_{i}"
                            ]
                            queue_config["Time"][f"Set_{i}"] = queue_config["Time"][
                                f"TimeSet_{i}"
                            ]

                        with QueueConfig.open("w", encoding="utf-8") as f:
                            json.dump(queue_config, f, ensure_ascii=False, indent=4)

                cur.execute("DELETE FROM version WHERE v = ?", ("v1.7",))
                cur.execute("INSERT INTO version VALUES(?)", ("v1.8",))
                db.commit()
            # v1.8-->v1.9
            if version[0][0] == "v1.8" or if_streaming:
                logger.info(
                    "数据文件版本更新: v1.8-->v1.9",
                )
                if_streaming = True

                # MaaConfig.Emulator.Id 依赖 EmulatorConfig；迁移时必须先加载模拟器，
                # 否则合法 UUID 会被 MultipleUIDValidator 当成失效值改成 "-"。
                await self.EmulatorConfig.connect(
                    self.config_path / "EmulatorConfig.json"
                )
                await self.ScriptConfig.connect(self.config_path / "ScriptConfig.json")
                await self.QueueConfig.connect(self.config_path / "QueueConfig.json")

                if (Path.cwd() / "config/config.json").exists():
                    (Path.cwd() / "config/config.json").rename(
                        Path.cwd() / "config/Config.json"
                    )
                await self.connect(self.config_path / "Config.json")

                script_dict: Dict[str, Optional[str]] = {"禁用": None}

                # 旧版 MAA 脚本与计划表已不再支持，迁移时跳过
                if (Path.cwd() / "config/GeneralConfig").exists():
                    for GeneralConfig in (
                        Path.cwd() / "config/GeneralConfig"
                    ).iterdir():
                        if GeneralConfig.is_dir():
                            general_config = json.loads(
                                (GeneralConfig / "config.json").read_text(
                                    encoding="utf-8"
                                )
                            )
                            general_config["Info"] = {
                                "Name": general_config["Script"]["Name"],
                                "RootPath": general_config["Script"]["RootPath"],
                            }

                            general_config["Script"]["ConfigPathMode"] = (
                                "File"
                                if "所有文件"
                                in general_config["Script"]["ConfigPathMode"]
                                else "Folder"
                            )

                            uid, sc = await self.add_script("General")
                            script_dict[GeneralConfig.name] = str(uid)
                            await sc.load(general_config)

                            for user in (GeneralConfig / "SubData").iterdir():
                                if user.is_dir() and (user / "config.json").exists():
                                    user_config = json.loads(
                                        (user / "config.json").read_text(
                                            encoding="utf-8"
                                        )
                                    )

                                    user_uid, uc = await self.add_user(str(uid))
                                    await uc.load(user_config)

                                    if (user / "ConfigFiles").exists():
                                        (Path.cwd() / f"data/{uid}/{user_uid}").mkdir(
                                            parents=True, exist_ok=True
                                        )
                                        shutil.move(
                                            user / "ConfigFiles",
                                            Path.cwd()
                                            / f"data/{uid}/{user_uid}/ConfigFile",
                                        )

                if (Path.cwd() / "config/QueueConfig").exists():
                    for QueueConfig in (Path.cwd() / "config/QueueConfig").glob(
                        "*.json"
                    ):
                        queue_config = json.loads(
                            QueueConfig.read_text(encoding="utf-8")
                        )

                        uid, qc = await self.add_queue()

                        queue_config["Info"] = queue_config["QueueSet"]
                        await qc.load(queue_config)

                        for i in range(10):
                            item_uid, item = await self.add_queue_item(str(uid))
                            time_uid, time = await self.add_time_set(str(uid))

                            await time.load(
                                {
                                    "Info": {
                                        "Enabled": queue_config["Time"][f"Enabled_{i}"],
                                        "Time": queue_config["Time"][f"Set_{i}"],
                                    }
                                }
                            )
                            await item.load(
                                {
                                    "Info": {
                                        "ScriptId": script_dict.get(
                                            queue_config["Queue"][f"Script_{i}"], "-"
                                        )
                                    }
                                }
                            )

                if (Path.cwd() / "config/QueueConfig").exists():
                    shutil.rmtree(Path.cwd() / "config/QueueConfig")
                if (Path.cwd() / "config/MaaPlanConfig").exists():
                    shutil.rmtree(Path.cwd() / "config/MaaPlanConfig")
                if (Path.cwd() / "config/MaaConfig").exists():
                    shutil.rmtree(Path.cwd() / "config/MaaConfig")
                if (Path.cwd() / "config/GeneralConfig").exists():
                    shutil.rmtree(Path.cwd() / "config/GeneralConfig")
                if (Path.cwd() / "data/gameid.txt").exists():
                    (Path.cwd() / "data/gameid.txt").unlink()
                if (Path.cwd() / "data/key").exists():
                    shutil.rmtree(Path.cwd() / "data/key")

                cur.execute("DELETE FROM version WHERE v = ?", ("v1.8",))
                cur.execute("INSERT INTO version VALUES(?)", ("v1.9",))
                db.commit()
            # v1.9-->v1.10
            if version[0][0] == "v1.9" or if_streaming:
                logger.info(
                    "数据文件版本更新: v1.9-->v1.10",
                )
                if_streaming = True

                if (Path.cwd() / "config/Config.json").exists():
                    data = json.loads(
                        (Path.cwd() / "config/Config.json").read_text(encoding="utf-8")
                    )
                    data["Data"]["LastStageUpdated"] = ""
                    data["Data"]["Stage"] = "{ }"
                    data["Function"]["IfBlockAd"] = data["Function"].get(
                        "IfSkipMumuSplashAds", False
                    )
                    (Path.cwd() / "config/Config.json").write_text(
                        json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8"
                    )

                cur.execute("DELETE FROM version WHERE v = ?", ("v1.9",))
                cur.execute("INSERT INTO version VALUES(?)", ("v1.10",))
                db.commit()
            # v1.10-->v1.11
            if version[0][0] == "v1.10" or if_streaming:
                logger.info(
                    "数据文件版本更新: v1.10-->v1.11",
                )
                if_streaming = True

                cur.execute("DELETE FROM version WHERE v = ?", ("v1.10",))
                cur.execute("INSERT INTO version VALUES(?)", ("v1.11",))
                db.commit()

            cur.close()
            db.close()
            logger.success("数据文件版本更新完成")

    async def get_git_version(self) -> tuple[bool, str, str]:
        """仅读取本地版本，不检查远端。

        保留旧返回结构；首项 True 表示本构建不触发更新，不代表已验证远端最新版。
        """

        supervised = is_supervised()
        expected_commit = os.getenv("AUTO_MAS_EXPECTED_COMMIT", "")
        if supervised and expected_commit:
            return True, expected_commit, "unknown"

        def _get_git_info():

            repo = self._get_repo()
            if repo is None:
                logger.warning("Git仓库不可用，返回默认版本信息")
                return True, "unknown", "unknown"

            # 获取当前 commit
            current_commit = repo.head.commit
            # 获取 commit 哈希
            commit_hash = current_commit.hexsha
            # 获取 commit 时间
            commit_time = datetime.fromtimestamp(current_commit.committed_date)

            return True, commit_hash, commit_time.strftime("%Y-%m-%d %H:%M:%S")

        # 在线程池中执行 Git 操作
        is_latest, commit_hash, commit_time = await self.loop.run_in_executor(
            None, _get_git_info
        )
        return is_latest or supervised, commit_hash, commit_time

    async def add_script(
        self,
        script: Literal["General"],
        script_id: str | None = None,
    ) -> tuple[uuid.UUID, GeneralConfig]:
        """添加脚本配置"""

        logger.info(f"添加脚本配置: {script}, 从 {script_id} 复制")
        if script != "General":
            raise ValueError("本版本仅支持通用脚本")

        if script_id is None:
            return await self.ScriptConfig.add(CLASS_BOOK[script])
        else:
            script_uid = uuid.UUID(script_id)

            if not isinstance(self.ScriptConfig[script_uid], CLASS_BOOK[script]):
                raise TypeError(f"脚本配置类型不匹配: {script_id} {script}")

            new_uid, new_config = await self.ScriptConfig.add(CLASS_BOOK[script])

            await new_config.load(
                await self.ScriptConfig[script_uid].toDict(regenerate_uuids=True)
            )

            # 复制用户数据
            if (Path.cwd() / f"data/{script_id}").exists():
                shutil.copytree(
                    Path.cwd() / f"data/{script_id}",
                    Path.cwd() / f"data/{new_uid}",
                    dirs_exist_ok=True,
                )
                for old_user, new_user in zip(
                    self.ScriptConfig[script_uid].UserData.keys(),
                    new_config.UserData.keys(),
                ):
                    if (Path.cwd() / f"data/{new_uid}/{old_user}").exists():
                        (Path.cwd() / f"data/{new_uid}/{old_user}").rename(
                            Path.cwd() / f"data/{new_uid}/{new_user}"
                        )

            return new_uid, new_config

    async def get_script(self, script_id: str | None) -> tuple[list, dict]:
        """获取脚本配置"""

        logger.info(f"获取脚本配置: {script_id}")

        if script_id is None:
            # 获取所有脚本配置
            data = await self.ScriptConfig.toDict()
        else:
            # 获取指定脚本配置
            data = await self.ScriptConfig.get(uuid.UUID(script_id))

        index = data.pop("instances", [])
        return list(index), data

    async def update_script(
        self, script_id: str, data: Dict[str, Dict[str, Any]]
    ) -> None:
        """更新脚本配置"""

        logger.info(f"更新脚本配置: {script_id}")

        uid = uuid.UUID(script_id)

        if self.ScriptConfig[uid].is_locked:
            raise RuntimeError(f"脚本 {script_id} 正在运行, 无法更新配置项")

        await self.ScriptConfig[uid].update(data)

    async def del_script(self, script_id: str) -> None:
        """删除脚本配置"""

        logger.info(f"删除脚本配置: {script_id}")

        uid = uuid.UUID(script_id)

        if self.ScriptConfig[uid].is_locked:
            raise RuntimeError(f"脚本 {script_id} 正在运行, 无法删除")

        # 删脚本会顺带删掉引用它的队列项；正在循环运行的队列靠下标回写状态，
        # 结构一变就会跑错脚本，两轮之间脚本没锁也要拦住。
        for queue_uid, queue in self.QueueConfig.items():
            if any(
                item.get("Info", "ScriptId") == str(uid)
                for item in queue.QueueItem.values()
            ):
                self._ensure_cycle_safe(queue_uid, "删除它引用的脚本")

        # 删除脚本相关的队列项
        for queue in self.QueueConfig.values():
            for key, value in queue.QueueItem.items():
                if value.get("Info", "ScriptId") == str(uid):
                    await queue.QueueItem.remove(key)

        await self.ScriptConfig.remove(uid)
        # 数据目录里可能有只读文件（如脚本配置目录快照带进来的 .git 对象）：裸
        # rmtree 删到它们会抛 PermissionError，而此时配置已经移除，目录残留在磁盘上、
        # 再点这个脚本还会报「配置项不存在」。目录删除是阻塞 IO（force_rmtree 内部
        # 还有 sleep 重试），放线程里跑，别让事件循环跟着等。
        script_data_dir = Path.cwd() / f"data/{uid}"
        if script_data_dir.exists():
            await asyncio.to_thread(force_rmtree, script_data_dir)

    async def reorder_script(self, index_list: list[str]) -> None:
        """重新排序脚本"""

        logger.info(f"重新排序脚本: {index_list}")

        await self.ScriptConfig.setOrder([uuid.UUID(_) for _ in index_list])

    async def import_script_from_share(
        self, script_id: str, config_key: str, version_no: Optional[int]
    ) -> None:
        """从「AUTO-MAS 配置中心」导入通用脚本配置。

        Args:
            script_id: 目标通用脚本ID。
            config_key: 配置中心的配置标识。
            version_no: 版本号, 为空表示已发布的最新版本。

        Raises:
            KeyError: 脚本不存在。
            TypeError: 脚本不是通用脚本配置。
            ConfigCenterError: 下载失败或内容不是通用脚本配置。
        """

        from app.services import ConfigCenter

        logger.info(f"从配置中心加载脚本配置: {script_id} - {config_key}")
        uid = uuid.UUID(script_id)

        if uid not in self.ScriptConfig:
            logger.error(f"{script_id} 不存在")
            raise KeyError(f"脚本 {script_id} 不存在")
        if not isinstance(self.ScriptConfig[uid], GeneralConfig):
            logger.error(f"{script_id} 不是通用脚本配置")
            raise TypeError(f"脚本 {script_id} 不是通用脚本配置")

        data = await ConfigCenter.download_template(config_key, version_no)
        await self.ScriptConfig[uid].load(data)

        logger.success(f"{script_id} 配置加载成功")

    async def build_share_config(
        self, script_id: str, config_name: str
    ) -> tuple[dict, List[Dict[str, str]]]:
        """整理待分享的通用脚本配置。

        用户数据（SubConfigsInfo）整体丢弃, 路径类配置项做占位替换, 剩下仍然可疑的内容
        以风险项返回, 由用户确认后才允许上传。

        Args:
            script_id: 目标通用脚本ID。
            config_name: 分享时使用的配置名称。

        Returns:
            脱敏后的配置字典, 以及仍需用户确认的风险项列表。

        Raises:
            KeyError: 脚本不存在。
            TypeError: 脚本不是通用脚本配置。
        """

        uid = uuid.UUID(script_id)

        if uid not in self.ScriptConfig:
            logger.error(f"{script_id} 不存在")
            raise KeyError(f"脚本 {script_id} 不存在")
        if not isinstance(self.ScriptConfig[uid], GeneralConfig):
            logger.error(f"{script_id} 不是通用脚本配置")
            raise TypeError(f"脚本 {script_id} 不是通用脚本配置")

        temp = await self.ScriptConfig[uid].toDict(if_decrypt=False)
        temp.pop("SubConfigsInfo", None)
        temp = await self.remove_privacy_info(temp, config_name)

        return temp, self.scan_privacy_risks(temp)

    async def upload_script_to_share(
        self, script_id: str, config_name: str, description: str, acknowledged: bool
    ) -> None:
        """以当前授权用户的身份把配置提交到「AUTO-MAS 配置中心」等待审核。

        Args:
            script_id: 目标通用脚本ID。
            config_name: 配置名称。
            description: 配置描述。
            acknowledged: 用户是否已确认分享前检查出的风险项。

        Raises:
            ConfigCenterError: 未授权、存在未确认的风险项或上传被拒绝。
        """

        from app.services import ConfigCenter, ConfigCenterError

        logger.info(f"上传配置到配置中心: {script_id} - {config_name}")

        config, risks = await self.build_share_config(script_id, config_name)
        if risks and not acknowledged:
            logger.warning(f"分享前检查到 {len(risks)} 项待确认内容, 已阻止上传")
            raise ConfigCenterError("配置中仍有可能泄露隐私的内容, 请确认后再分享")

        await ConfigCenter.upload_config(config_name, description, config)

    async def remove_privacy_info(self, config: dict, name: str) -> dict:
        """移除配置中可能存在的隐私信息"""

        config["Info"]["Name"] = name
        for path in ["ScriptPath", "ConfigPath", "LogPath", "TrackProcessExe"]:
            if Path(config["Script"][path]).is_relative_to(
                Path(config["Info"]["RootPath"])
            ):
                config["Script"][path] = str(
                    Path(r"C:/脚本根目录")
                    / Path(config["Script"][path]).relative_to(
                        Path(config["Info"]["RootPath"])
                    )
                )
            if IS_WINDOWS and Path(config["Script"][path]).is_relative_to(
                Path(os.environ["APPDATA"])
            ):
                config["Script"][path] = (
                    f"%APPDATA%/{Path(config['Script'][path]).relative_to(Path(os.environ['APPDATA']))}"
                )
        config["Info"]["RootPath"] = str(Path(r"C:/脚本根目录"))

        # 上面只覆盖脚本自身的路径项；游戏路径、命令行等自由文本同样会带出本机用户名，统一打码
        for items in config.values():
            if not isinstance(items, dict):
                continue
            for key, value in items.items():
                if isinstance(value, str) and value:
                    items[key] = self._mask_home_path(value)

        return config

    @staticmethod
    def _mask_home_path(value: str) -> str:
        """把值里出现的本机用户目录替换成占位符"""

        home = str(Path.home())
        if not home:
            return value

        masked = value
        for candidate in {home, home.replace("\\", "/")}:
            # 要求用户目录后面是分隔符或行尾, 否则 C:\Users\qiyin 会切掉 C:\Users\qiyinxi 的一截
            masked = re.sub(
                rf"{re.escape(candidate)}(?=[\\/]|$)",
                "%USERPROFILE%",
                masked,
                flags=re.IGNORECASE,
            )
        return masked

    def scan_privacy_risks(self, config: dict) -> List[Dict[str, str]]:
        """检查脱敏后的配置里是否还残留不该分享的内容。

        自动脱敏只能处理已知的路径项, 命令行参数、日志规则这类自由文本仍可能带出账号、
        密码、令牌或本机绝对路径, 这里把它们挑出来交给用户确认。

        Args:
            config: 已经过 remove_privacy_info 处理的配置字典。

        Returns:
            风险项列表, 每项包含配置项名称与风险说明。
        """

        placeholders = ("C:\\脚本根目录", "C:/脚本根目录", "%APPDATA%", "%USERPROFILE%")
        user_name = Path.home().name
        risks: List[Dict[str, str]] = []

        for group, items in config.items():
            if not isinstance(items, dict):
                continue
            for key, value in items.items():
                if not isinstance(value, str) or not value.strip():
                    continue

                field = f"{group}.{key}"
                if re.search(
                    r"(?i)(password|passwd|pwd|token|secret|api[_-]?key|cookie|session"
                    r"|密码|密钥|口令)\s*[=:\s]\s*\S",
                    value,
                ):
                    risks.append({"field": field, "reason": "疑似包含账号、密码或令牌"})
                    continue
                if re.search(r"://[^/\s:@]+:[^/\s@]+@", value):
                    risks.append({"field": field, "reason": "链接中带有账号密码"})
                    continue
                if len(user_name) > 2 and user_name.lower() in value.lower():
                    risks.append({"field": field, "reason": "包含本机用户名"})
                    continue

                probe = value
                for placeholder in placeholders:
                    probe = probe.replace(placeholder, "")
                # 盘符前不能再跟字母, 否则 https:// 这类协议头会被当成 C:\ 一样的盘符路径
                if re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]", probe) or "\\\\" in probe:
                    risks.append({"field": field, "reason": "包含本机绝对路径"})

        return risks

    async def get_user(
        self, script_id: str, user_id: Optional[str]
    ) -> tuple[list, dict]:
        """获取用户配置"""

        logger.info(f"获取用户配置: {script_id} - {user_id}")

        uid = uuid.UUID(script_id)

        if user_id is None:
            # 获取全部用户配置
            data = await self.ScriptConfig[uid].UserData.toDict()
        else:
            # 获取指定用户配置
            data = await self.ScriptConfig[uid].UserData.get(uuid.UUID(user_id))

        index = data.pop("instances", [])
        return list(index), data

    async def add_user(self, script_id: str) -> tuple[uuid.UUID, GeneralUserConfig]:
        """添加用户配置"""

        logger.info(f"{script_id} 添加用户配置")

        script_config = self.ScriptConfig[uuid.UUID(script_id)]

        if not isinstance(script_config, GeneralConfig):
            raise TypeError(f"不支持的脚本配置类型: {type(script_config)}")
        uid, config = await script_config.UserData.add(GeneralUserConfig)

        return uid, config

    # ════════════ 配置恢复（宿主注入池解析，门面绑定上下文） ════════════

    def set_restore_pool_resolver(
        self, resolver: Callable[["ConfigBase"], list["ConfigRestorePool"]]
    ) -> None:
        """由宿主装配恢复池解析函数，绑定仅作用于当前配置实例。"""

        self._restore_pool_resolver = resolver

    def restore_service(
        self, script_id: str, user_id: str, *, force: bool = False
    ) -> "ConfigRestoreService":
        """通过注入的解析函数取得恢复池，绑定上下文构建运行时服务。

        专项只声明池表（普通函数，显式收 :class:`RestoreContext`），由宿主
        负责选择。``force`` 随上下文下发，供专项池的恢复函数读取
        （当前仅 ZzzOd 消费）。
        """

        from app.utils.config_restore import RestoreContext, build_restore_service

        script_config = self.ScriptConfig[uuid.UUID(script_id)]
        if self._restore_pool_resolver is None:
            raise RuntimeError("配置恢复未初始化：请先由宿主装配恢复池解析函数")
        pools = self._restore_pool_resolver(script_config)
        return build_restore_service(
            RestoreContext(
                config=self,
                script_config=script_config,
                script_id=script_id,
                user_id=user_id,
                force=force,
            ),
            pools,
        )

    async def list_config_backups(
        self, script_id: str, user_id: str, target: str
    ) -> dict:
        """列出配置备份（时间倒序，每项带 base 来源标注）与当前 base 来源。

        返回 ``{"items": [{"time", "base"}], "base": 当前来源或 None}``；
        当前来源只在三态池返回（前端据此比对是否需要跨来源提示）。
        target 取值由专项池定义。
        """

        service = self.restore_service(script_id, user_id)
        return {
            "items": await service.list(target),
            "base": await service.current_base(target),
        }

    async def ensure_config_backup(
        self, script_id: str, user_id: str, target: str
    ) -> dict:
        """按需归档目标池当前配置（指纹去重，无变化自动跳过）。

        编辑界面三时机的统一入口：进入/退出编辑页（前端触发）、运行前
        （各专项任务流程调用专项归档函数，不经本方法）。
        """

        return await self.restore_service(script_id, user_id).ensure(target)

    async def restore_config_backup(
        self, script_id: str, user_id: str, ts: str, target: str, *, force: bool = False
    ) -> dict:
        """把指定备份恢复到目标位置（恢复前存底、跨来源切换由服务层自理）。

        恢复是覆盖性写配置操作：脚本锁着（任务/配置会话运行中）时拒绝，
        否则 mas 池「先换目录再回填 UserData」会在 update 处撞锁，留下
        目录已换、字段未回填的半恢复现场。

        ``force`` 随上下文下发到专项池恢复函数（当前仅 ZzzOd 消费：跳过
        注册表依赖步骤——恢复前存底 / 占用守卫），其余专项忽略。源配置
        损坏（``ConfigCorruptedError``）原样抛出，API 层转 409 交前端二次
        确认。
        """

        uid = uuid.UUID(script_id)
        if self.ScriptConfig[uid].is_locked:
            raise RuntimeError(f"脚本 {script_id} 正在运行, 无法恢复配置")

        await self.restore_service(script_id, user_id, force=force).restore(target, ts)
        return {"target": target}

    async def get_config_backup_preview(
        self, script_id: str, user_id: str, ts: str, target: str
    ) -> dict:
        """读取指定备份的配置摘要（纯读不恢复）；载荷结构由专项定义。"""

        payload = await self.restore_service(script_id, user_id).preview(target, ts)
        return {"time": ts, "target": target, "data": payload}

    async def get_config_backup_file(
        self, script_id: str, user_id: str, ts: str, target: str, path: str
    ) -> dict:
        """只读读取指定备份内一个文本文件（预览「查看原始文件」用）。

        路径限归档内相对路径（防穿越）、大小受限（1 MiB），由
        ``config_archive.read_backup_text`` 与专项池函数保证。
        """

        content = await self.restore_service(script_id, user_id).read_backup_file(
            target, ts, path
        )
        return {"time": ts, "target": target, **content}

    async def update_user(
        self,
        script_id: str,
        user_id: str,
        data: Dict[str, Dict[str, Any]],
        *,
        precondition: Callable[[], bool] | None = None,
    ) -> bool:
        """更新用户配置，返回是否写入

        ``precondition``：预处理（特调整理、密码加密等，要让出事件循环）做完、真正写入
        之前再判一次，不成立就不写。判断与写入之间不让出，期间插不进别的写入。
        """

        logger.info(f"{script_id} 更新用户配置: {user_id}")

        script_uid = uuid.UUID(script_id)
        user_uid = uuid.UUID(user_id)
        script_config = self.ScriptConfig[script_uid]
        user_config = script_config.UserData[user_uid]

        if precondition is not None and not precondition():
            return False
        await user_config.update(data)
        return True

    async def del_user(self, script_id: str, user_id: str) -> None:
        """删除用户配置"""

        logger.info(f"{script_id} 删除用户配置: {user_id}")

        script_uid = uuid.UUID(script_id)
        user_uid = uuid.UUID(user_id)
        script_config = self.ScriptConfig[script_uid]

        await script_config.UserData.remove(user_uid)
        # 与 del_script 同理：用户数据目录里可能有只读文件，裸 rmtree 删不干净还抛异常。
        user_data_dir = Path.cwd() / f"data/{script_id}/{user_id}"
        if user_data_dir.exists():
            await asyncio.to_thread(force_rmtree, user_data_dir)

    async def get_user_config_dir(self, script_id: str, user_id: str) -> Path:
        """获取用户配置目录, 不存在时创建"""

        logger.info(f"{script_id} 获取用户配置目录: {user_id}")

        script_uid = uuid.UUID(script_id)
        user_uid = uuid.UUID(user_id)
        if user_uid not in self.ScriptConfig[script_uid].UserData:
            raise ValueError("用户不存在")

        user_config_dir = Path.cwd() / f"data/{script_id}/{user_id}"
        user_config_dir.mkdir(parents=True, exist_ok=True)

        return user_config_dir

    async def reorder_user(self, script_id: str, index_list: list[str]) -> None:
        """重新排序用户"""

        logger.info(f"{script_id} 重新排序用户: {index_list}")

        script_uid = uuid.UUID(script_id)

        await self.ScriptConfig[script_uid].UserData.setOrder(
            list(map(uuid.UUID, index_list))
        )

    async def get_emulator(self, emulator_id: Optional[str]) -> tuple[list, dict]:
        """获取模拟器配置"""
        logger.info(f"获取全局模拟器设置: {emulator_id}")

        if emulator_id is None:
            data = await self.EmulatorConfig.toDict()
        else:
            data = await self.EmulatorConfig.get(uuid.UUID(emulator_id))

        index = data.pop("instances", [])
        return list(index), data

    async def add_emulator(self) -> tuple[uuid.UUID, EmulatorConfig]:
        """添加模拟器配置"""
        logger.info("添加全局模拟器配置")

        uid, config = await self.EmulatorConfig.add(EmulatorConfig)
        return uid, config

    async def update_emulator(
        self, emulator_id: str, data: Dict[str, Dict[str, Any]]
    ) -> None:
        """更新模拟器配置"""

        emulator_uid = uuid.UUID(emulator_id)

        logger.info(f"更新模拟器配置: {emulator_id}")

        await self.EmulatorConfig[emulator_uid].update(data)

    async def del_emulator(self, emulator_id: str) -> None:
        """删除模拟器配置"""

        emulator_uid = uuid.UUID(emulator_id)

        logger.info(f"删除全局模拟器配置: {emulator_id}")

        script_list = []

        for script in self.ScriptConfig.values():
            if isinstance(script, GeneralConfig):
                if script.get("Game", "Type") == "Emulator" and script.get(
                    "Game", "EmulatorId"
                ) == str(emulator_id):
                    if script.is_locked:
                        raise RuntimeError(
                            f"脚本 {script.get('Info', 'Name')} 正在使用此模拟器且被锁定, 无法完成删除"
                        )
                    script_list.append(script)

        for script in script_list:
            await script.set("Game", "EmulatorId", "-")

        await self.EmulatorConfig.remove(emulator_uid)

    async def add_queue(self) -> tuple[uuid.UUID, QueueConfig]:
        """添加调度队列"""

        logger.info("添加调度队列")

        return await self.QueueConfig.add(QueueConfig)

    async def get_queue(self, queue_id: Optional[str]) -> tuple[list, dict]:
        """获取调度队列配置"""

        logger.info(f"获取调度队列配置: {queue_id}")

        if queue_id is None:
            data = await self.QueueConfig.toDict()
        else:
            data = await self.QueueConfig.get(uuid.UUID(queue_id))

        index = data.pop("instances", [])
        return list(index), data

    async def update_queue(
        self, queue_id: str, data: Dict[str, Dict[str, Any]]
    ) -> None:
        """更新调度队列配置"""

        logger.info(f"更新调度队列配置: {queue_id}")

        queue_uid = uuid.UUID(queue_id)
        # 队列名、完成后操作这类字段改了不影响正在跑的循环，放行；
        # 只有循环开关本身不能在运行中动。
        if "CycleEnabled" in data.get("Info", {}):
            self._ensure_cycle_safe(queue_uid, "切换循环开关")

        await self.QueueConfig[queue_uid].update(data)

    async def del_queue(self, queue_id: str) -> None:
        """删除调度队列配置"""

        logger.info(f"删除调度队列配置: {queue_id}")

        queue_uid = uuid.UUID(queue_id)
        self._ensure_cycle_safe(queue_uid, "删除")

        await self.QueueConfig.remove(queue_uid)

    async def get_time_set(
        self, queue_id: str, time_set_id: Optional[str]
    ) -> tuple[list, dict]:
        """获取时间设置配置"""

        logger.info(f"获取队列的时间配置: {queue_id} - {time_set_id}")

        queue_uid = uuid.UUID(queue_id)

        if time_set_id is None:
            data = await self.QueueConfig[queue_uid].TimeSet.toDict()
        else:
            data = await self.QueueConfig[queue_uid].TimeSet.get(uuid.UUID(time_set_id))

        index = data.pop("instances", [])
        return list(index), data

    async def add_time_set(self, queue_id: str) -> tuple[uuid.UUID, TimeSet]:
        """添加时间设置配置"""

        logger.info(f"{queue_id} 添加时间设置配置")

        queue_uid = uuid.UUID(queue_id)
        uid, config = await self.QueueConfig[queue_uid].TimeSet.add(TimeSet)

        return uid, config

    async def update_time_set(
        self, queue_id: str, time_set_id: str, data: Dict[str, Dict[str, Any]]
    ) -> None:
        """更新时间设置配置"""

        logger.info(f"{queue_id} 更新时间设置配置: {time_set_id}")

        queue_uid = uuid.UUID(queue_id)
        time_set_uid = uuid.UUID(time_set_id)

        await self.QueueConfig[queue_uid].TimeSet[time_set_uid].update(data)

    async def del_time_set(self, queue_id: str, time_set_id: str) -> None:
        """删除时间设置配置"""

        logger.info(f"{queue_id} 删除时间设置配置: {time_set_id}")

        queue_uid = uuid.UUID(queue_id)
        time_set_uid = uuid.UUID(time_set_id)

        await self.QueueConfig[queue_uid].TimeSet.remove(time_set_uid)

    async def reorder_time_set(self, queue_id: str, index_list: list[str]) -> None:
        """重新排序时间设置"""

        logger.info(f"{queue_id} 重新排序时间设置: {index_list}")

        queue_uid = uuid.UUID(queue_id)

        await self.QueueConfig[queue_uid].TimeSet.setOrder(
            list(map(uuid.UUID, index_list))
        )

    async def get_queue_item(
        self, queue_id: str, queue_item_id: Optional[str]
    ) -> tuple[list, dict]:
        """获取队列项配置"""

        logger.info(f"获取队列的队列项配置: {queue_id} - {queue_item_id}")

        queue_uid = uuid.UUID(queue_id)

        if queue_item_id is None:
            data = await self.QueueConfig[queue_uid].QueueItem.toDict()
        else:
            data = await self.QueueConfig[queue_uid].QueueItem.get(
                uuid.UUID(queue_item_id)
            )

        index = data.pop("instances", [])
        return list(index), data

    async def add_queue_item(self, queue_id: str) -> tuple[uuid.UUID, QueueItem]:
        """添加队列项配置"""

        logger.info(f"{queue_id} 添加队列项配置")

        queue_uid = uuid.UUID(queue_id)
        self._ensure_cycle_safe(queue_uid, "增删队列项")

        uid, config = await self.QueueConfig[queue_uid].QueueItem.add(QueueItem)

        return uid, config

    async def update_queue_item(
        self, queue_id: str, queue_item_id: str, data: Dict[str, Dict[str, Any]]
    ) -> None:
        """更新队列项配置"""

        logger.info(f"{queue_id} 更新队列项配置: {queue_item_id}")

        queue_uid = uuid.UUID(queue_id)
        queue_item_uid = uuid.UUID(queue_item_id)
        # 循环调度参数每轮都会重读，运行中改没问题；换脚本会让任务的脚本列表
        # 与队列对不上号，必须拦住。
        if "Info" in data:
            self._ensure_cycle_safe(queue_uid, "更换队列项的脚本")

        await self.QueueConfig[queue_uid].QueueItem[queue_item_uid].update(data)

    async def del_queue_item(self, queue_id: str, queue_item_id: str) -> None:
        """删除队列项配置"""

        logger.info(f"{queue_id} 删除队列项配置: {queue_item_id}")

        queue_uid = uuid.UUID(queue_id)
        queue_item_uid = uuid.UUID(queue_item_id)
        self._ensure_cycle_safe(queue_uid, "增删队列项")

        await self.QueueConfig[queue_uid].QueueItem.remove(queue_item_uid)

    async def reorder_queue_item(self, queue_id: str, index_list: list[str]) -> None:
        """重新排序队列项"""

        logger.info(f"{queue_id} 重新排序队列项: {index_list}")

        queue_uid = uuid.UUID(queue_id)
        self._ensure_cycle_safe(queue_uid, "调整队列项顺序")

        await self.QueueConfig[queue_uid].QueueItem.setOrder(
            list(map(uuid.UUID, index_list))
        )

    def _ensure_cycle_safe(self, queue_uid: uuid.UUID, action: str) -> None:
        """拦住会打乱正在运行的循环的改动。

        任务的脚本列表在创建时就冻结了，循环靠下标回写状态；队列项的增删、
        排序、换脚本都会让下标对不上号。只拦这些，改名、改完成后操作、改循环
        周期都不受影响。
        """

        if queue_uid not in self.running_cycle_queue_ids:
            return

        queue_name = (
            self.QueueConfig[queue_uid].get("Info", "Name")
            if queue_uid in self.QueueConfig
            else str(queue_uid)
        )
        raise RuntimeError(f"循环队列 {queue_name} 正在运行，无法{action}")

    async def get_tools(self) -> Dict[str, Any]:
        """获取工具设置"""

        logger.debug("获取工具设置")

        today = datetime.now(tz=UTC8).strftime("%Y-%m-%d")
        if self._game_sign_result_date != today:
            self.ToolsConfig._game_sign_result_data = {}
            self._game_sign_result_date = today

        return await self.ToolsConfig.toDict()

    async def update_community_results(
        self, formatted: dict[str, Any], *, replace: bool = False
    ) -> None:
        """合并、持久化并广播游戏社区结果。

        Args:
            formatted: 已按平台和账号分组的签到结果。
            replace: 是否按账号 UID 替换已有结果。
        """

        from app.tools.community_sign_provider import merge_community_sign_results

        today = datetime.now(tz=UTC8).strftime("%Y-%m-%d")
        existing = (
            self.ToolsConfig._game_sign_result_data
            if self._game_sign_result_date == today
            else {}
        )
        result = merge_community_sign_results(existing, formatted, replace=replace)
        self.ToolsConfig._game_sign_result_data = result
        self._game_sign_result_date = today
        _save_game_sign_result_snapshot(
            self.config_path / GAME_SIGN_RESULT_FILENAME,
            result,
            result_date=today,
        )

        try:
            from app.core.ws import Publisher, protocol
            from app.models.schema import WSGameSignResultData

            await Publisher.send(
                id=protocol.ID_GAME_SIGN,
                type=protocol.GAMESIGN_RESULT_UPDATED,
                data=WSGameSignResultData(
                    result=json.dumps(result, ensure_ascii=False)
                ),
            )
        except Exception as e:
            logger.warning(f"广播游戏社区结果失败: {e}")

    async def update_tools(self, data: Dict[str, Dict[str, Any]]) -> None:
        """更新工具设置"""

        logger.info("更新工具设置")

        await self.ToolsConfig.update(data)

        logger.success("工具设置更新成功")

    # ==================== 游戏社区账号组 CRUD ====================

    async def get_game_sign_accounts(
        self, *, if_decrypt: bool = True
    ) -> Dict[str, Any]:
        """获取所有游戏社区账号组"""

        logger.debug("获取所有游戏社区账号组")

        return await self.ToolsConfig.GameSign_Accounts.toDict(if_decrypt=if_decrypt)

    async def add_game_sign_account(self) -> tuple[uuid.UUID, Any]:
        """添加游戏社区账号组"""

        logger.info("添加游戏社区账号组")

        async with self._community_account_add_lock:
            existing_names = []
            for account in self.ToolsConfig.GameSign_Accounts.values():
                try:
                    existing_names.append(account.get("GameSignAccount", "Name"))
                except (AttributeError, KeyError):
                    continue
            account_name = next_community_account_name(existing_names)
            uid, config = await self.ToolsConfig.GameSign_Accounts.add(
                GameSignAccountGroup
            )
            await config.set("GameSignAccount", "Name", account_name)
            return uid, config

    def _clear_game_sign_account_results(self, account_id: str) -> None:
        """清除指定游戏社区账号的结果。"""

        today = datetime.now(tz=UTC8).strftime("%Y-%m-%d")
        result = self.ToolsConfig._game_sign_result_data
        if getattr(self, "_game_sign_result_date", today) != today:
            result.clear()
            self._game_sign_result_date = today

        for platform in list(result):
            result[platform] = [
                group
                for group in result[platform]
                if group.get("account_uid") != account_id
            ]
            if not result[platform]:
                del result[platform]

        tools_file = getattr(self.ToolsConfig, "file", None)
        snapshot_path = (
            tools_file.with_name(GAME_SIGN_RESULT_FILENAME)
            if isinstance(tools_file, Path)
            else None
        )
        _save_game_sign_result_snapshot(
            snapshot_path,
            result,
            result_date=today,
        )

    async def update_game_sign_account(
        self, account_id: str, data: Dict[str, Dict[str, Any]]
    ) -> None:
        """更新游戏社区账号组配置"""

        logger.info(f"更新游戏社区账号组: {account_id}")

        account_uid = uuid.UUID(account_id)
        account = self.ToolsConfig.GameSign_Accounts[account_uid]
        from app.tools.community_sign_provider import COMMUNITY_TOKEN_FIELDS

        credential_fields = set(COMMUNITY_TOKEN_FIELDS)
        credential_changed = False

        for group, items in data.items():
            for name, value in items.items():
                if (
                    group == "GameSignAccount"
                    and name in credential_fields
                    and account.get(group, name) != value
                ):
                    credential_changed = True
                await account.set(group, name, value)

        if credential_changed:
            await account.set("GameSignAccount", "LastSignDate", "2000-01-01")
            self._clear_game_sign_account_results(account_id)

    async def delete_game_sign_account(self, account_id: str) -> None:
        """删除游戏社区账号组"""

        logger.info(f"删除游戏社区账号组: {account_id}")

        account_uid = uuid.UUID(account_id)
        await self.ToolsConfig.GameSign_Accounts.remove(account_uid)
        self._clear_game_sign_account_results(account_id)

    async def reorder_game_sign_accounts(self, order: list[str]) -> None:
        """调整游戏社区账号组顺序"""

        logger.info("调整游戏社区账号组顺序")

        await self.ToolsConfig.GameSign_Accounts.setOrder([uuid.UUID(_) for _ in order])

    def obs_replay_options(self):
        """读取 OBS 连接与保留策略，服务层不依赖全局配置。"""
        from app.services.obs_replay import ObsReplayOptions

        return ObsReplayOptions(
            port=self.get("Replay", "Port"),
            password=self.get("Replay", "Password"),
            max_replay_count=self.get("Replay", "MaxReplayCount"),
        )

    async def get_setting(self) -> Dict[str, Any]:
        """获取全局设置"""

        logger.info("获取全局设置")

        data = await self.toDict()
        replay = data.get("Replay", {})
        replay["PasswordConfigured"] = bool(replay.pop("Password", ""))
        return data

    async def update_setting(self, data: Dict[str, Dict[str, Any]]) -> None:
        """更新全局设置"""

        logger.info("更新全局设置")

        replay = data.get("Replay")
        if replay is not None:
            replay = {
                key: value
                for key, value in replay.items()
                if value is not None and key != "PasswordConfigured"
            }
            data = {**data, "Replay": replay}
        if "Hotkey" in data:
            import time

            from app.core.hotkey_capture import current_capture, wait_for_relay
            from app.core.hotkey_manager import HotkeyManager, parse_win32_hotkey

            if current_capture():
                raise ValueError("请先结束热键录制，再保存配置")
            keys = ("Enabled", "ToggleStartStop", "PreviousTask", "NextTask")
            previous = {key: self.get("Hotkey", key) for key in keys}
            proposed = {**previous, **data["Hotkey"]}
            if proposed["Enabled"]:
                bindings = [parse_win32_hotkey(proposed[key]) for key in keys[1:]]
                if len(set(bindings)) != len(bindings):
                    raise ValueError("三个任务热键不能相同")
            await self.update(data)
            try:
                changed_at = time.time()
                await HotkeyManager.reload()
                await wait_for_relay(tuple(proposed[key] for key in keys), changed_at)
            except Exception:
                await self.update({"Hotkey": previous})
                changed_at = time.time()
                await HotkeyManager.reload()
                await wait_for_relay(tuple(previous[key] for key in keys), changed_at)
                raise
        else:
            await self.update(data)

        logger.success("全局设置更新成功")

    async def get_webhook(
        self,
        script_id: Optional[str],
        user_id: Optional[str],
        webhook_id: Optional[str],
    ) -> tuple[list, dict]:
        """获取webhook配置"""

        if script_id is None and user_id is None:
            logger.info(f"获取全局webhook设置: {webhook_id}")

            if webhook_id is None:
                data = await self.Notify_CustomWebhooks.toDict()
            else:
                data = await self.Notify_CustomWebhooks.get(uuid.UUID(webhook_id))

        else:
            logger.info(f"获取webhook设置: {script_id} - {user_id} - {webhook_id}")

            script_uid = uuid.UUID(script_id)
            user_uid = uuid.UUID(user_id)

            if webhook_id is None:
                data = (
                    await self.ScriptConfig[script_uid]
                    .UserData[user_uid]
                    .Notify_CustomWebhooks.toDict()
                )
            else:
                data = (
                    await self.ScriptConfig[script_uid]
                    .UserData[user_uid]
                    .Notify_CustomWebhooks.get(uuid.UUID(webhook_id))
                )

        index = data.pop("instances", [])
        return list(index), data

    async def add_webhook(
        self, script_id: Optional[str], user_id: Optional[str]
    ) -> tuple[uuid.UUID, Webhook]:
        """添加webhook配置"""

        if script_id is None and user_id is None:
            logger.info("添加全局webhook配置")

            uid, config = await self.Notify_CustomWebhooks.add(Webhook)
            return uid, config

        else:
            logger.info(f"添加webhook配置: {script_id} - {user_id}")

            script_uid = uuid.UUID(script_id)
            user_uid = uuid.UUID(user_id)

            uid, config = (
                await self.ScriptConfig[script_uid]
                .UserData[user_uid]
                .Notify_CustomWebhooks.add(Webhook)
            )
            return uid, config

    async def update_webhook(
        self,
        script_id: Optional[str],
        user_id: Optional[str],
        webhook_id: str,
        data: Dict[str, Dict[str, Any]],
    ) -> None:
        """更新 webhook 配置"""

        webhook_uid = uuid.UUID(webhook_id)

        if script_id is None and user_id is None:
            logger.info(f"更新 webhook 全局配置: {webhook_id}")

            for group, items in data.items():
                for name, value in items.items():
                    await self.Notify_CustomWebhooks[webhook_uid].set(
                        group, name, value
                    )

        else:
            logger.info(f"更新 webhook 配置: {script_id} - {user_id} - {webhook_id}")

            script_uid = uuid.UUID(script_id)
            user_uid = uuid.UUID(user_id)

            for group, items in data.items():
                for name, value in items.items():
                    await (
                        self.ScriptConfig[script_uid]
                        .UserData[user_uid]
                        .Notify_CustomWebhooks[webhook_uid]
                        .set(group, name, value)
                    )

    async def del_webhook(
        self, script_id: Optional[str], user_id: Optional[str], webhook_id: str
    ) -> None:
        """删除 webhook 配置"""

        webhook_uid = uuid.UUID(webhook_id)

        if script_id is None and user_id is None:
            logger.info(f"删除全局 webhook 配置: {webhook_id}")

            await self.Notify_CustomWebhooks.remove(webhook_uid)

        else:
            logger.info(f"删除 webhook 配置: {script_id} - {user_id} - {webhook_id}")

            script_uid = uuid.UUID(script_id)
            user_uid = uuid.UUID(user_id)

            await (
                self.ScriptConfig[script_uid]
                .UserData[user_uid]
                .Notify_CustomWebhooks.remove(webhook_uid)
            )

    @property
    def proxy(self) -> Optional[httpx.Proxy]:
        """获取代理设置，返回适用于 httpx 的代理对象"""
        proxy_addr = normalize_proxy_address(self.get("Update", "ProxyAddress"))
        if not proxy_addr:
            return None

        try:
            logger.info(f"使用代理: {proxy_addr}")
            return httpx.Proxy(proxy_addr)
        except Exception as e:
            logger.warning(f"代理配置无效: {proxy_addr}, 错误: {e}")
            return None

    @property
    def proxy_url(self) -> Optional[str]:
        """代理地址字符串（含协议、保留 userinfo），给子进程环境变量用；不打日志。

        MFW 运行池的 uv / pip、worker 与项目 agent 都经
        ``host_environment.subprocess_proxy_scope`` 拿到它；每次准备环境都会读，
        这里不像 ``proxy`` 那样每次访问都记一行「使用代理」。
        """

        return normalize_proxy_address(self.get("Update", "ProxyAddress"))

    async def get_proxy_overview(self) -> Dict[str, Any]:
        """获取代理情况概览信息"""

        logger.info("获取代理情况概览信息")

        history_index = await self.search_history(
            "DAILY", datetime.now(tz=UTC4).date(), datetime.now(tz=UTC4).date()
        )
        if datetime.now(tz=UTC4).strftime("%Y-%m-%d") not in history_index:
            return {}
        history_data = {
            k: await self.merge_statistic_info(v)
            for k, v in history_index[
                datetime.now(tz=UTC4).strftime("%Y-%m-%d")
            ].items()
        }
        overview = {}
        for user, data in history_data.items():
            index_data = data.get("index", [])
            if index_data:
                last_proxy_date = max(
                    datetime.strptime(_["date"], "%Y-%m-%d %H:%M:%S")
                    for _ in index_data
                ).strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_proxy_date = "暂无代理数据"
            proxy_times = len(data.get("index", []))
            error_info = data.get("error_info", {})
            error_times = len(error_info)
            overview[user] = {
                "LastProxyDate": last_proxy_date,
                "ProxyTimes": proxy_times,
                "ErrorTimes": error_times,
                "ErrorInfo": error_info,
            }
        return overview

    async def get_script_combox(self):
        """获取脚本下拉框信息"""

        logger.info("开始获取脚本下拉框信息")
        data = [{"label": "未选择", "value": "-"}]
        for uid, script in self.ScriptConfig.items():
            data.append(
                {
                    "label": f"{TYPE_BOOK[type(script).__name__]} - {script.get('Info', 'Name')}",
                    "value": str(uid),
                }
            )
        logger.success("脚本下拉框信息获取成功")

        return data

    async def get_task_combox(self):
        """获取任务下拉框信息"""

        logger.info("开始获取任务下拉框信息")
        data = [{"label": "未选择", "value": None}]
        for uid, queue in self.QueueConfig.items():
            data.append(
                {
                    "label": f"队列 - {queue.get('Info', 'Name')}",
                    "value": str(uid),
                }
            )
        for uid, script in self.ScriptConfig.items():
            if not script.is_locked:
                data.append(
                    {
                        "label": f"脚本 - {TYPE_BOOK[type(script).__name__]} - {script.get('Info', 'Name')}",
                        "value": str(uid),
                    }
                )
        logger.success("任务下拉框信息获取成功")

        return data

    async def get_emulator_combox(self):
        """获取模拟器下拉框信息"""

        logger.info("开始获取模拟器下拉框信息")
        data = [{"label": "未选择", "value": "-"}]
        for uid, emulator in self.EmulatorConfig.items():
            data.append({"label": emulator.get("Info", "Name"), "value": str(uid)})
        logger.success("模拟器下拉框信息获取成功")
        return data

    async def get_emulator_devices_combox(self, emulator_id: str):
        """获取模拟器多开实例下拉框信息"""

        logger.info("开始获取模拟器下拉框信息")

        if emulator_id == "-":
            return []

        if self.EmulatorConfig[uuid.UUID(emulator_id)].get("Info", "Type") == "general":
            logger.info("通用模拟器不支持扫描多开实例, 返回空列表")
            return []

        data = [{"label": "未选择", "value": "-"}]

        from .emulator_manager import EmulatorManager

        devices = await (
            await EmulatorManager.get_emulator_instance(emulator_id)
        ).list_devices()
        for index, title in devices.items():
            data.append({"label": title, "value": index})

        logger.success("模拟器下拉框信息获取成功")

        return data

    async def get_notice(self) -> tuple[bool, Dict[str, str]]:
        """获取公告信息"""

        # 公告不属于活动内容；不再请求或展示上游公告，旧配置仍保留以便回退。
        return False, {}

    def build_history_log_path(
        self, *, script_name: str, user_name: str, log_time: datetime
    ) -> Path:
        """构建带脚本名称前缀的历史日志路径。

        Args:
            script_name: 脚本名称。
            user_name: 用户名称。
            log_time: 日志开始时间。

        Returns:
            历史日志文件路径。
        """

        safe_script_name = re.sub(r'[<>:"/\\|?*]', "_", str(script_name or "").strip())
        safe_script_name = safe_script_name.rstrip(" .") or "空白"
        time_suffix = f"-{log_time.strftime('%H-%M-%S')}.log"
        safe_script_name = safe_script_name[: 255 - len(time_suffix)]

        return (
            self.history_path
            / log_time.strftime("%Y-%m-%d")
            / user_name
            / f"{safe_script_name}{time_suffix}"
        )

    async def save_general_log(
        self, log_path: Path, logs: list, general_result: str
    ) -> None:
        """
        保存通用日志并生成对应统计数据

        :param log_path: 日志文件保存路径
        :param logs: 日志内容列表
        :param general_result: 待保存的日志结果信息
        """

        logger.info(
            f"开始处理通用日志, 日志长度: {len(logs)}, 日志标记: {general_result}"
        )

        data: Dict[str, str] = {"general_result": general_result}

        # 保存日志
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.with_suffix(".log").write_text("".join(logs), encoding="utf-8")
        log_path.with_suffix(".json").write_text(
            json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8"
        )

        logger.success(f"通用日志统计完成, 日志路径: {log_path.with_suffix('.log')}")

    async def merge_statistic_info(self, statistic_path_list: List[Path]) -> dict:
        """
        合并指定数据统计信息文件

        Args:
            statistic_path_list (List[Path]): 数据统计信息文件列表

        Returns:
            dict: 合并后的数据统计信息
        """

        data: Dict[str, Any] = {"index": {}}
        hsr_success_results = {
            "HSR 任务结束",
            "HSR 用户任务完成",
            "HSR 失败任务补跑完成",
            "HSR 本轮无需执行，已跳过",
            "HSR 脚本原生来源完成",
            # 「HSR 脚本直控完成」= 来源术语迁移前的历史存量文案, 运行时已改写为
            # 「HSR 脚本原生来源完成」, 此处仅为兼容旧历史数据保留成功判定
            "HSR 脚本直控完成",
        }
        # MaaFW 停服维护跳过的两句, 与 app/task/MaaFW/tools/embedded/signal_notice.py
        # 的 SIGNAL_USER_MESSAGES / MAINTENANCE_SKIP_MESSAGE 一致: 维护是跳过,
        # 既不算失败, 也不能显示成完成
        maafw_skip_results = {
            "游戏停服维护中，本次跳过",
            "游戏停服维护中，本次跳过（同一资源已确认在维护）",
        }

        def is_success_result(result_key: str, result_value: Any) -> bool:
            # 结果文本可能带运行阶段前缀（如 "[送货] Success!"），比对前先剥离
            if not isinstance(result_value, str):
                return False
            value = re.sub(r"^\[[^\]]+\]\s*", "", result_value)
            if value in ("Success!", "今日任务均已完成"):
                # 「今日任务均已完成」= zzz-od 原生来源/按记录跳过场景的历史存量文案,
                # 运行时已向 Success! 归一, 此处仅为兼容旧历史数据保留成功判定
                return True
            if result_key == "hsr_result" and result_value in hsr_success_results:
                return True
            return False

        def is_skip_result(result_key: str, result_value: Any) -> bool:
            # 先确认是字符串: 列表、字典等不可哈希的值做集合成员判断会抛 TypeError
            return (
                result_key == "general_result"
                and isinstance(result_value, str)
                and result_value in maafw_skip_results
            )

        for json_file in statistic_path_list:
            try:
                single_data = json.loads(json_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(
                    f"无法解析文件 {json_file}, 错误信息: {type(e).__name__}: {str(e)}"
                )
                continue

            for key in single_data.keys():
                if key not in data:
                    data[key] = {}

                # 合并公招统计
                if key == "recruit_statistics":
                    for star_level, count in single_data[key].items():
                        if star_level not in data[key]:
                            data[key][star_level] = 0
                        data[key][star_level] += count

                # 合并掉落统计
                elif key == "drop_statistics":
                    for stage, drops in single_data[key].items():
                        if stage not in data[key]:
                            data[key][stage] = {}  # 初始化关卡

                        for item, count in drops.items():
                            if item not in data[key][stage]:
                                data[key][stage][item] = 0
                            data[key][stage][item] += count

                # 合并基质统计
                elif key == "matrix_statistics":
                    for skill, weapon in single_data[key].items():
                        data[key][skill] = weapon

                # 抽数是当前资源快照，合并时使用最新一条记录
                elif key == "pull_count_statistics":
                    data[key] = single_data[key]

                # 处理理智相关字段 - 使用最后一个文件的值
                elif key in ["sanity", "sanity_full_at"]:
                    data[key] = single_data[key]

                # 录入运行结果
                elif key in [
                    "maa_result",
                    "maaend_result",
                    "src_result",
                    "general_result",
                    "hsr_result",
                ]:
                    history_time = "-".join(json_file.stem.rsplit("-", 3)[-3:])
                    actual_date = (
                        datetime.strptime(
                            f"{json_file.parent.parent.name} {history_time}",
                            "%Y-%m-%d %H-%M-%S",
                        )
                        .replace(tzinfo=UTC4)
                        .astimezone()
                    )

                    if is_success_result(key, single_data[key]):
                        status = "DONE"
                    elif is_skip_result(key, single_data[key]):
                        status = "SKIP"
                    else:
                        status = "ERROR"

                    if status == "ERROR":
                        if "error_info" not in data:
                            data["error_info"] = {}
                        data["error_info"][
                            actual_date.strftime("%Y-%m-%d %H:%M:%S")
                        ] = single_data[key]

                    data["index"][actual_date] = {
                        "date": actual_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "status": status,
                        "jsonFile": str(json_file),
                        "result": single_data[key],
                    }

        data["index"] = [data["index"][_] for _ in sorted(data["index"])]

        # 确保返回的字典始终包含 index 字段，即使为空
        result = {
            k: v
            for k, v in data.items()
            if v or (k == "matrix_statistics" and isinstance(v, dict))
        }
        if "index" not in result:
            result["index"] = []

        return result

    async def search_history(
        self,
        mode: Literal["DAILY", "WEEKLY", "MONTHLY"],
        start_date: date,
        end_date: date,
    ) -> dict:
        """
        搜索指定时间范围内的历史记录

        Args:
            mode (Literal["DAILY", "WEEKLY", "MONTHLY"]): 合并模式
            start_date (date): 开始日期
            end_date (date): 结束日期
        """

        logger.info(
            f"开始搜索历史记录, 合并模式: {mode}, 日期范围: {start_date} 至 {end_date}"
        )

        history_dict = {}

        for date_folder in self.history_path.iterdir():
            if not date_folder.is_dir():
                continue  # 只处理日期文件夹

            try:
                date = datetime.strptime(date_folder.name, "%Y-%m-%d").date()

                if not (start_date <= date <= end_date):
                    continue  # 只统计在范围内的日期

                if mode == "DAILY":
                    date_name = date.strftime("%Y-%m-%d")
                elif mode == "WEEKLY":
                    date_name = date.strftime("%G-W%V")
                elif mode == "MONTHLY":
                    date_name = date.strftime("%Y-%m")
                else:
                    raise ValueError("无效的合并模式")

                if date_name not in history_dict:
                    history_dict[date_name] = {}

                for user_folder in date_folder.iterdir():
                    if not user_folder.is_dir():
                        continue  # 只处理用户文件夹

                    # 键必须用完整目录名: 用户名本身可含点, stem/with_suffix 会把最后一个点当扩展名截断
                    if user_folder.name not in history_dict[date_name]:
                        history_dict[date_name][user_folder.name] = list(
                            user_folder.glob("*.json")
                        )
                    else:
                        history_dict[date_name][user_folder.name] += list(
                            user_folder.glob("*.json")
                        )

            except ValueError:
                logger.exception(f"非日期格式的目录: {date_folder}")

        logger.success(f"历史记录搜索完成, 共计 {len(history_dict)} 条记录")

        return {
            k: v
            for k, v in sorted(history_dict.items(), key=lambda x: x[0], reverse=True)
        }

    async def push_system_notice(
        self, *, level: str, title: str, lines: list[str]
    ) -> None:
        """发一条系统通知；主连接还没建立就先攒着，连上时随启动通知一起发。"""

        from app.core.ws import Publisher, protocol
        from app.models.schema import WSSystemNoticeData

        notice = {"level": level, "title": title, "lines": list(lines)}
        try:
            sent = await Publisher.send(
                id=protocol.ID_MAIN,
                type=protocol.SYSTEM_NOTICE,
                data=WSSystemNoticeData(**notice),
            )
        except Exception as exc:  # noqa: BLE001 - 通知发不出去不该影响业务
            logger.warning(f"系统通知发送失败，改为下次连接时发送：{exc}")
            sent = False
        if not sent:
            self.startup_notices.append(notice)

    async def flush_startup_notices(self) -> None:
        """主 WebSocket 连上后把启动期攒下的系统通知发出去，发成功的只发一次。

        连接刚建立就被替换 / 断开时发送返回 False，断开还会取消这个回调；没发出去的
        （含正在发的那条）按原顺序放回队列，由下一次连接再发，不在这里重试。
        """

        from app.core.ws import Publisher, protocol
        from app.models.schema import WSSystemNoticeData

        pending, self.startup_notices = self.startup_notices, []
        try:
            while pending:
                try:
                    sent = await Publisher.send(
                        id=protocol.ID_MAIN,
                        type=protocol.SYSTEM_NOTICE,
                        data=WSSystemNoticeData(**pending[0]),
                    )
                except Exception as exc:  # noqa: BLE001 - 与 push_system_notice 一致
                    logger.warning(f"系统通知发送失败，改为下次连接时发送：{exc}")
                    sent = False
                if not sent:
                    break
                pending.pop(0)
        finally:
            # 发送期间 push_system_notice 可能又攒进来新的，放在它们前面保持顺序
            self.startup_notices[:0] = pending

    def clean_debug_diagnostics(self) -> None:
        """清理 debug 目录下过期的失败诊断文件。

        自动扫描 ``debug/`` 下全部子目录（各专项的登录/切号/启动器失败诊断，
        新专项落盘即纳入清理，无需登记名单）：诊断日志与截图统一按固定保留
        天数清理，不跟随历史记录保留时间——诊断文件不是用户数据，解绑后任何
        配置下都不会无界累积。失败截图另受每目录独立的大小上限约束，超限
        从旧到新回收——一个专项的截图风暴不会挤掉其他专项的证据。

        纯同步文件 IO，调用方在事件循环里请经 ``asyncio.to_thread`` 执行。
        """

        cutoff = time.time() - DIAGNOSTIC_RETENTION_DAYS * 86400

        debug_root = Path.cwd() / "debug"
        if not debug_root.is_dir():
            return

        deleted_count = 0
        screenshot_deleted_count = 0
        for folder in debug_root.iterdir():
            if not folder.is_dir():
                continue

            screenshot_files: list[tuple[Path, float, int]] = []
            screenshot_size = 0
            for file in folder.iterdir():
                if (
                    not file.is_file()
                    or file.suffix.lower() not in DIAGNOSTIC_FILE_SUFFIXES
                ):
                    continue
                try:
                    file_stat = file.stat()
                except OSError as exc:
                    logger.warning(f"诊断文件清理失败: {file} - {exc}")
                    continue
                if file_stat.st_mtime < cutoff:
                    try:
                        file.unlink()
                    except OSError as exc:
                        logger.warning(f"诊断文件清理失败: {file} - {exc}")
                    else:
                        deleted_count += 1
                    continue
                if file.suffix.lower() in DIAGNOSTIC_SCREENSHOT_SUFFIXES:
                    screenshot_files.append(
                        (file, file_stat.st_mtime, file_stat.st_size)
                    )
                    screenshot_size += file_stat.st_size

            for file, _, file_size in sorted(
                screenshot_files, key=lambda item: item[1]
            ):
                if screenshot_size <= DIAGNOSTIC_SCREENSHOT_MAX_BYTES:
                    break
                try:
                    file.unlink()
                except OSError as exc:
                    logger.warning(f"失败截图清理失败: {file} - {exc}")
                    continue
                screenshot_size -= file_size
                screenshot_deleted_count += 1

        if deleted_count:
            logger.success(f"清理完成: {deleted_count} 个过期诊断文件")
        if screenshot_deleted_count:
            logger.success(f"清理完成: {screenshot_deleted_count} 个超限失败截图")

    def clean_old_history(self):
        """删除超过用户设定天数的历史记录文件（基于目录日期）。

        纯同步文件 IO，调用方在事件循环里请经 ``asyncio.to_thread`` 执行。
        """

        # 只读一次：定时器在工作线程跑本函数，循环内逐目录重读会看到扫描
        # 中途的设置变更（改成 0 时剩余目录会按 0 天 cutoff 全部删除）
        retention_days = self.get("Function", "HistoryRetentionTime")
        if retention_days == 0:
            logger.info("历史记录永久保留, 跳过历史记录清理")
            return

        logger.info("开始清理超过设定天数的历史记录")

        deleted_count = 0

        for date_folder in self.history_path.iterdir():
            if not date_folder.is_dir():
                continue  # 只处理日期文件夹

            try:
                # 只检查 `YYYY-MM-DD` 格式的文件夹
                folder_date = datetime.strptime(date_folder.name, "%Y-%m-%d").date()
                if datetime.now(tz=UTC4).date() - folder_date > timedelta(
                    days=retention_days
                ):
                    shutil.rmtree(date_folder, ignore_errors=True)
                    deleted_count += 1
                    logger.debug(f"已删除超期日志目录: {date_folder}")
            except ValueError:
                logger.warning(f"非日期格式的目录: {date_folder}")

        logger.success(f"清理完成: {deleted_count} 个日期目录")


Config = AppConfig()
