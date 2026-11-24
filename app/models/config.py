#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
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


import calendar
import json
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any

from app.utils import get_logger
from app.utils.constants import (
    CYCLE_EMPTY_TIME,
    MATERIALS_MAP,
    RESOURCE_STAGE_INFO,
    UTC4,
    normalize_base_source,
)

from .ConfigBase import (
    ArgumentValidator,
    BoolValidator,
    ConfigBase,
    ConfigItem,
    DateTimeValidator,
    EmulatorPathValidator,
    EncryptValidator,
    FileValidator,
    FolderValidator,
    JSONValidator,
    MultipleConfig,
    MultipleOptionsValidator,
    MultipleUIDValidator,
    OptionsValidator,
    RangeValidator,
    ScriptExecutableValidator,
    StringValidator,
    URLValidator,
    UserNameValidator,
    ValidatorBase,
    VirtualConfigValidator,
)
from .schema import GeneralConfig_Script, TagItem

logger = get_logger("配置模型")


"""
脚本级和用户级的 MaaEnd 任务配置项结构相同。配置文件来源为脚本且启用快速配置时,
任务开关读取脚本配置；理智任务选项始终读取用户配置。
"""


class EmulatorConfig(ConfigBase):
    """模拟器配置"""

    def __init__(self) -> None:

        ## Info ------------------------------------------------------------
        ## 模拟器名称
        self.Info_Name = ConfigItem("Info", "Name", "新模拟器")
        ## 模拟器类型
        self.Info_Type = ConfigItem(
            "Info",
            "Type",
            "general",
            OptionsValidator(
                [
                    "general",
                    "mumu",
                    "ldplayer",
                    # Emulator 2.0: 一条配置管多条模拟器路径, 路径写在 Info_Paths,
                    # Info_Path 保持空串(EmulatorPathValidator 允许空串)
                    "emulator2",
                    # "nox",  # 以下都是骗你的, 根本没有写~~
                    # "memu",
                    # "blueStacks",
                ]
            ),
            legacy_group="Data",
        )
        ## 模拟器路径
        self.Info_Path = ConfigItem(
            "Info", "Path", "", EmulatorPathValidator(self.Info_Type)
        )
        ## Emulator 2.0 纳管的模拟器路径列表
        ## [{"pathId", "installPath", "alias", "type", "version"}]
        self.Info_Paths = ConfigItem("Info", "Paths", "[]", JSONValidator(list))
        ## Emulator 2.0 的设备号槽位表
        ## [{"slot", "pathId", "nativeIndex", "state": "active"|"tombstone"}]
        ## 槽位号在本配置内单调递增分配, 移除路径写墓碑, 号码永不复用
        self.Info_Slots = ConfigItem("Info", "Slots", "[]", JSONValidator(list))
        ## Emulator 2.0 的稳定模式：开着就把会干扰截图识别的模拟器功能压住,
        ## 启动实例前顺带确保一次, 这样新建的实例也会跟着进入安全状态。
        ## 关掉只是不再确保, **不会把那些项改回去**——不知道用户原本想要什么值。
        ## Emulator 2.0 的配置守卫：以 MAS 存的这份设置为准, 启动前与关闭后各核验一次,
        ## 对不上就写回去。与旧雷电那套「开机拍快照关机还原」不是一回事, 见 utils/emulator2/guard.py
        self.Info_ConfigGuard = ConfigItem(
            "Info", "ConfigGuard", False, BoolValidator()
        )
        ## 守卫的基准: {设备号: {字段: 值}}, 只记用户显式设过的字段
        self.Info_Baselines = ConfigItem("Info", "Baselines", "{}", JSONValidator(dict))
        self.Info_StableMode = ConfigItem("Info", "StableMode", False, BoolValidator())
        ## 老板键快捷键配置
        self.Info_BossKey = ConfigItem(
            "Info", "BossKey", "[ ]", JSONValidator(list), legacy_group="Data"
        )
        ## 最大等待时间（秒）
        self.Info_MaxWaitTime = ConfigItem(
            "Info", "MaxWaitTime", 300, RangeValidator(1, 9999), legacy_group="Data"
        )
        ## 关闭 MuMu 时强力清理残留进程
        self.Info_ForceKillOnClose = ConfigItem(
            "Info", "ForceKillOnClose", False, BoolValidator()
        )
        ## 启动 MuMu 实例前先关闭已在运行的实例并强力清理残留进程
        ## 用于已有非管理员实例导致新实例无法以管理员身份启动的场景; 会关掉全部实例, 多开慎用
        self.Info_ForceKillBeforeLaunch = ConfigItem(
            "Info", "ForceKillBeforeLaunch", False, BoolValidator()
        )

        super().__init__()


class Webhook(ConfigBase):
    """Webhook 配置"""

    def __init__(self) -> None:

        ## Info ------------------------------------------------------------
        ## Webhook 名称
        self.Info_Name = ConfigItem("Info", "Name", "新自定义 Webhook 通知")
        ## 是否启用
        self.Info_Enabled = ConfigItem("Info", "Enabled", True, BoolValidator())

        ## Data ------------------------------------------------------------
        ## Webhook URL 地址
        self.Data_Url = ConfigItem("Data", "Url", "", URLValidator())
        ## 消息模板
        self.Data_Template = ConfigItem("Data", "Template", "")
        ## 请求头
        self.Data_Headers = ConfigItem("Data", "Headers", "{ }", JSONValidator())
        ## 请求方法
        self.Data_Method = ConfigItem(
            "Data", "Method", "POST", OptionsValidator(["POST", "GET"])
        )

        super().__init__()


class QueueItem(ConfigBase):
    """队列项配置"""

    related_config: dict[str, MultipleConfig] = {}

    def __init__(self) -> None:

        ## Info ------------------------------------------------------------
        ## 脚本 ID
        self.Info_ScriptId = ConfigItem(
            "Info",
            "ScriptId",
            "-",
            MultipleUIDValidator("-", self.related_config, "ScriptConfig"),
        )

        ## Schedule --------------------------------------------------------
        ## 是否参与循环调度
        self.Schedule_Enabled = ConfigItem("Schedule", "Enabled", True, BoolValidator())
        ## 循环调度模式: fixed_time 为固定时间, interval 为间隔
        self.Schedule_Mode = ConfigItem(
            "Schedule",
            "Mode",
            "fixed_time",
            OptionsValidator(["fixed_time", "interval"]),
        )
        ## 固定时间模式的执行周期
        self.Schedule_Days = ConfigItem(
            "Schedule",
            "Days",
            list(calendar.day_name),
            MultipleOptionsValidator(list(calendar.day_name)),
        )
        ## 固定时间模式的执行时间
        self.Schedule_Time = ConfigItem(
            "Schedule", "Time", "00:00", DateTimeValidator("%H:%M")
        )
        ## 间隔模式的间隔分钟数
        self.Schedule_IntervalMinutes = ConfigItem(
            "Schedule", "IntervalMinutes", 480, RangeValidator(1, 10080)
        )
        ## 间隔模式的计时基准: start 为上次开始, finish 为上次结束
        self.Schedule_IntervalAnchor = ConfigItem(
            "Schedule",
            "IntervalAnchor",
            "start",
            OptionsValidator(["start", "finish"]),
        )
        ## 下次运行时间, 空值哨兵表示由调度器按模式推算
        self.Schedule_NextRunAt = ConfigItem(
            "Schedule",
            "NextRunAt",
            CYCLE_EMPTY_TIME,
            DateTimeValidator("%Y-%m-%d %H:%M:%S"),
        )

        ## Data ------------------------------------------------------------
        ## 上次循环开始时间
        self.Data_LastCycleStartedAt = ConfigItem(
            "Data",
            "LastCycleStartedAt",
            CYCLE_EMPTY_TIME,
            DateTimeValidator("%Y-%m-%d %H:%M:%S"),
        )
        ## 上次循环结束时间
        self.Data_LastCycleFinishedAt = ConfigItem(
            "Data",
            "LastCycleFinishedAt",
            CYCLE_EMPTY_TIME,
            DateTimeValidator("%Y-%m-%d %H:%M:%S"),
        )

        super().__init__()


class TimeSet(ConfigBase):
    """时间设置配置"""

    def __init__(self) -> None:

        ## Info ------------------------------------------------------------
        ## 是否启用
        self.Info_Enabled = ConfigItem("Info", "Enabled", True, BoolValidator())
        ## 执行周期
        self.Info_Days = ConfigItem(
            "Info",
            "Days",
            list(calendar.day_name),
            MultipleOptionsValidator(list(calendar.day_name)),
        )
        ## 执行时间
        self.Info_Time = ConfigItem("Info", "Time", "00:00", DateTimeValidator("%H:%M"))

        super().__init__()


class QueueConfig(ConfigBase):
    """队列配置"""

    def __init__(self) -> None:

        ## Info ------------------------------------------------------------
        ## 队列名称
        self.Info_Name = ConfigItem("Info", "Name", "新队列")
        ## 是否启用定时启动
        self.Info_TimeEnabled = ConfigItem(
            "Info", "TimeEnabled", False, BoolValidator()
        )
        ## 是否在启动时自动运行
        self.Info_StartUpMode = ConfigItem(
            "Info",
            "StartUpMode",
            "Never",
            OptionsValidator(["Never", "Always", "DailyFirst"]),
        )
        ## 是否为循环队列: 定时与循环互斥, 循环队列按队列项各自的周期持续运行
        self.Info_CycleEnabled = ConfigItem(
            "Info", "CycleEnabled", False, BoolValidator()
        )
        ## 完成后操作
        self.Info_AfterAccomplish = ConfigItem(
            "Info",
            "AfterAccomplish",
            "NoAction",
            OptionsValidator(
                [
                    "NoAction",
                    "Shutdown",
                    "ShutdownForce",
                    "Reboot",
                    "Hibernate",
                    "Sleep",
                    "KillSelf",
                    "RestartSelf",
                    "Logoff",
                ]
            ),
        )
        ## 完成后操作的延时时长, 单位分钟, 0 表示队列结束后直接进入倒计时
        self.Info_AfterAccomplishDelay = ConfigItem(
            "Info", "AfterAccomplishDelay", 0, RangeValidator(0, 1440)
        )
        ## 队列级运行前脚本: 一次运行只执行一次, 循环队列在整个运行期间不重复执行
        self.Info_IfScriptBeforeTask = ConfigItem(
            "Info", "IfScriptBeforeTask", False, BoolValidator()
        )
        ## 队列运行前脚本路径
        self.Info_ScriptBeforeTask = ConfigItem(
            "Info", "ScriptBeforeTask", "", FileValidator()
        )
        ## 队列级运行后脚本: 运行结束后执行一次, 先于「完成后操作」
        self.Info_IfScriptAfterTask = ConfigItem(
            "Info", "IfScriptAfterTask", False, BoolValidator()
        )
        ## 队列运行后脚本路径
        self.Info_ScriptAfterTask = ConfigItem(
            "Info", "ScriptAfterTask", "", FileValidator()
        )

        ## Data ------------------------------------------------------------
        ## 上次定时启动时间
        self.Data_LastTimedStart = ConfigItem(
            "Data",
            "LastTimedStart",
            "2000-01-01 00:00",
            DateTimeValidator("%Y-%m-%d %H:%M"),
        )
        # 上次启动时运行时间
        self.Data_LastStartupTime = ConfigItem(
            "Data",
            "LastStartupTime",
            "2000-01-01",
            DateTimeValidator("%Y-%m-%d"),
        )

        self.TimeSet = MultipleConfig([TimeSet])
        self.QueueItem = MultipleConfig([QueueItem])

        super().__init__()

    async def load(self, data: dict) -> bool:
        """加载并迁移旧版调度队列配置文件"""

        info_data = data.get("Info")
        if isinstance(info_data, dict) and "StartUpMode" not in info_data:
            StartUpEnabled = info_data.get("StartUpEnabled")
            if isinstance(StartUpEnabled, bool):
                info_data["StartUpMode"] = "Always" if StartUpEnabled else "Never"

        return await super().load(data)


def _tag_proxy(config: ConfigBase, label: str = "日常", tz: tzinfo = UTC4) -> dict:
    """上次代理标签（默认使用东4区时间，tz 为游戏日时区），label 区分日常/任务文案。"""
    if (
        datetime.strptime(config.get("Data", "LastProxyDate"), "%Y-%m-%d").date()
        == datetime.now(tz=tz).date()
    ):
        return {
            "text": f"{label}：已代理{config.get('Data', 'ProxyTimes')}次",
            "color": "green",
        }
    return {"text": f"{label}：未代理", "color": "orange"}


def _tag_remained_days(config: ConfigBase) -> dict:
    """剩余天数标签。"""
    remained_day = config.get("Info", "RemainedDay")
    if remained_day == -1:
        tag_color = "gold"
    elif remained_day == 0:
        tag_color = "red"
    elif remained_day <= 3:
        tag_color = "orange"
    elif remained_day <= 7:
        tag_color = "yellow"
    elif remained_day <= 30:
        tag_color = "blue"
    else:
        tag_color = "green"
    return {
        "text": (
            f"剩余天数：{remained_day}天" if remained_day >= 0 else "剩余天数：无期限"
        ),
        "color": tag_color,
    }


def _tag_notes(config: ConfigBase) -> dict:
    """备注标签。"""
    notes = config.get("Info", "Notes")
    return {
        "text": (f"备注：{notes}" if len(notes) <= 20 else f"备注：{notes[:20]}..."),
        "color": "pink",
    }


"""周计划的七天分组名，顺序与 calendar.day_name 一致（周一到周日）。"""


"""BAAH 计划表 key 的字段默认值与长度区间"""


class BaseSourceValidator(OptionsValidator):
    """base 来源校验器：只接受 shared / independent / native，旧字面量加载时归一。"""

    def __init__(self) -> None:
        super().__init__(["shared", "independent", "native"])

    def correct(self, value: Any) -> Any:
        return super().correct(normalize_base_source(value))


class GeneralUserConfig(ConfigBase):
    """通用脚本用户配置"""

    def __init__(self) -> None:

        ## Info ------------------------------------------------------------
        ## 用户名称
        self.Info_Name = ConfigItem("Info", "Name", "新用户", UserNameValidator())
        ## 是否启用
        self.Info_Status = ConfigItem("Info", "Status", True, BoolValidator())
        ## 剩余天数
        self.Info_RemainedDay = ConfigItem(
            "Info", "RemainedDay", -1, RangeValidator(-1, 9999)
        )
        ## base 来源（shared=共享/independent=独立/native=原生）
        self.Info_Base = ConfigItem(
            "Info", "Base", "independent", BaseSourceValidator(), legacy_name="Mode"
        )
        ## 兼容旧版用户独立脚本配置
        self.Info_IfUseMasConfig = ConfigItem(
            "Info", "IfUseMasConfig", True, BoolValidator()
        )
        ## 是否在任务前执行脚本
        self.Info_IfScriptBeforeTask = ConfigItem(
            "Info", "IfScriptBeforeTask", False, BoolValidator()
        )
        ## 任务前脚本路径
        self.Info_ScriptBeforeTask = ConfigItem(
            "Info", "ScriptBeforeTask", "", FileValidator()
        )
        ## 是否在任务后执行脚本
        self.Info_IfScriptAfterTask = ConfigItem(
            "Info", "IfScriptAfterTask", False, BoolValidator()
        )
        ## 任务后脚本路径
        self.Info_ScriptAfterTask = ConfigItem(
            "Info", "ScriptAfterTask", "", FileValidator()
        )
        ## 备注
        self.Info_Notes = ConfigItem("Info", "Notes", "无")
        ## 用户标签信息
        self.Info_Tag = ConfigItem(
            "Info", "Tag", "[ ]", VirtualConfigValidator(self.getTags)
        )

        ## Data ------------------------------------------------------------
        ## 上次代理日期
        self.Data_LastProxyDate = ConfigItem(
            "Data", "LastProxyDate", "2000-01-01", DateTimeValidator("%Y-%m-%d")
        )
        ## 代理次数
        self.Data_ProxyTimes = ConfigItem(
            "Data", "ProxyTimes", 0, RangeValidator(0, 9999)
        )

        ## Notify ----------------------------------------------------------
        ## 是否启用通知
        self.Notify_Enabled = ConfigItem("Notify", "Enabled", False, BoolValidator())
        ## 是否发送统计信息
        self.Notify_IfSendStatistic = ConfigItem(
            "Notify", "IfSendStatistic", False, BoolValidator()
        )
        ## 是否发送邮件
        self.Notify_IfSendMail = ConfigItem(
            "Notify", "IfSendMail", False, BoolValidator()
        )
        ## 收件地址
        self.Notify_ToAddress = ConfigItem("Notify", "ToAddress", "")
        ## 是否启用 Server 酱
        self.Notify_IfServerChan = ConfigItem(
            "Notify", "IfServerChan", False, BoolValidator()
        )
        ## Server 酱密钥
        self.Notify_ServerChanKey = ConfigItem("Notify", "ServerChanKey", "")
        ## 自定义 Webhook 列表
        self.Notify_CustomWebhooks = MultipleConfig([Webhook])

        super().__init__()

    def getTags(self) -> str:
        """生成通用用户标签列表"""
        tags = []

        # 任务代理标签（使用东4区时间）
        tags.append(_tag_proxy(self, "任务"))

        # 剩余天数标签
        tags.append(_tag_remained_days(self))

        # 备注标签
        tags.append(_tag_notes(self))

        return json.dumps(tags, ensure_ascii=False)


def _migrate_push_log_mode(data: dict) -> None:
    """兼容旧版 Notify.PushLogEnabled 布尔开关 → 三态 PushLogMode

    旧值 False（关闭）迁移为「关闭」，保留用户之前的关闭选择；旧值 True 交由
    新默认「汇总」生效；随后清理旧键，避免其作为未知字段残留。
    """
    notify = data.get("Notify")
    if (
        isinstance(notify, dict)
        and "PushLogEnabled" in notify
        and "PushLogMode" not in notify
    ):
        if notify.get("PushLogEnabled") is False:
            notify["PushLogMode"] = "关闭"
        notify.pop("PushLogEnabled", None)


class GeneralRecoveryListValidator(ValidatorBase):
    """复用清单契约校验，错误配置不得静默清空后退回原清理方式。"""

    def __init__(self, field: str) -> None:
        self.field = field

    def validate(self, value: Any) -> bool:
        if not isinstance(value, list):
            return False
        try:
            GeneralConfig_Script.model_validate({self.field: value})
            return True
        except ValueError:
            return False

    def correct(self, value: Any) -> Any:
        if not self.validate(value):
            raise ValueError(
                f"{self.field} 清单配置不合法，请检查路径、进程名和主体设置"
            )
        return value


class GeneralConfig(ConfigBase):
    """通用配置"""

    related_config: dict[str, MultipleConfig] = {}

    def __init__(self) -> None:

        ## Info ------------------------------------------------------------
        ## 脚本名称
        self.Info_Name = ConfigItem("Info", "Name", "新通用脚本")
        ## 根目录路径
        self.Info_RootPath = ConfigItem("Info", "RootPath", "", FileValidator())

        ## Script ----------------------------------------------------------
        ## 脚本路径
        self.Script_ScriptPath = ConfigItem(
            "Script", "ScriptPath", "", ScriptExecutableValidator()
        )
        ## 脚本参数
        self.Script_Arguments = ConfigItem("Script", "Arguments", "")
        ## 原生启动工作目录；留空使用程序目录
        self.Script_WorkingDirectory = ConfigItem(
            "Script", "WorkingDirectory", "", FolderValidator()
        )
        ## 首轮也使用有序启动清单
        self.Script_UseLaunchListOnFirstRun = ConfigItem(
            "Script", "UseLaunchListOnFirstRun", False, BoolValidator()
        )
        ## 自定义清理清单；留空时沿用原版进程清理
        self.Script_TaskKill = ConfigItem(
            "Script", "TaskKill", [], GeneralRecoveryListValidator("TaskKill")
        )
        ## 自定义清理范围：本轮、当前会话全部匹配、跨会话强力清理
        self.Script_TaskKillMode = ConfigItem(
            "Script",
            "TaskKillMode",
            "Force",
            OptionsValidator(["Force", "Tracked", "Session"]),
        )
        ## 重试与超时补跑的有序启动清单；留空时使用原启动配置
        self.Script_Restart = ConfigItem(
            "Script", "Restart", [], GeneralRecoveryListValidator("Restart")
        )
        ## 是否追踪进程
        self.Script_IfTrackProcess = ConfigItem(
            "Script", "IfTrackProcess", False, BoolValidator()
        )
        ## 追踪进程的名称
        self.Script_TrackProcessName = ConfigItem("Script", "TrackProcessName", "")
        ## 追踪进程的文件路径
        self.Script_TrackProcessExe = ConfigItem("Script", "TrackProcessExe", "")
        ## 追踪进程的启动命令行参数
        self.Script_TrackProcessCmdline = ConfigItem(
            "Script", "TrackProcessCmdline", "", ArgumentValidator()
        )
        self.Script_ConfigPath = ConfigItem("Script", "ConfigPath", "", FileValidator())
        ## 配置路径模式
        self.Script_ConfigPathMode = ConfigItem(
            "Script", "ConfigPathMode", "File", OptionsValidator(["File", "Folder"])
        )
        ## 更新配置模式
        self.Script_UpdateConfigMode = ConfigItem(
            "Script",
            "UpdateConfigMode",
            "Never",
            OptionsValidator(["Never", "Success", "Failure", "Always"]),
        )
        ## 日志路径
        self.Script_LogPath = ConfigItem("Script", "LogPath", "", FileValidator())
        ## 日志路径格式
        self.Script_LogPathFormat = ConfigItem("Script", "LogPathFormat", "%Y-%m-%d")
        ## 日志时间戳开始位置
        self.Script_LogTimeStart = ConfigItem(
            "Script", "LogTimeStart", 1, RangeValidator(1, 9999)
        )
        ## 日志时间戳结束位置
        self.Script_LogTimeEnd = ConfigItem(
            "Script", "LogTimeEnd", 1, RangeValidator(1, 9999)
        )
        ## 日志时间格式
        self.Script_LogTimeFormat = ConfigItem(
            "Script", "LogTimeFormat", "%Y-%m-%d %H:%M:%S"
        )
        ## 日志预处理启用开关：关闭时保留规则配置，行为与未配置预处理完全一致
        self.Script_LogHookEnabled = ConfigItem(
            "Script", "LogHookEnabled", False, BoolValidator()
        )
        ## 日志预处理规则（JSON 数组，每项形如 {"type":"drop|replace",...}）；
        ## 预处理先于任务日志、推送日志采集与成功/失败判定执行，丢弃的行不进入下游
        self.Script_LogHookRules = ConfigItem("Script", "LogHookRules", "")
        ## 成功日志匹配
        self.Script_SuccessLog = ConfigItem("Script", "SuccessLog", "")
        ## 成功日志匹配模式：Split = 「|」分隔关键字子串包含；Regex = 正则表达式
        self.Script_SuccessLogMode = ConfigItem(
            "Script", "SuccessLogMode", "Split", OptionsValidator(["Split", "Regex"])
        )
        ## 错误日志匹配
        self.Script_ErrorLog = ConfigItem("Script", "ErrorLog", "")
        ## 错误日志匹配模式：Split = 「|」分隔关键字子串包含；Regex = 正则表达式
        self.Script_ErrorLogMode = ConfigItem(
            "Script", "ErrorLogMode", "Split", OptionsValidator(["Split", "Regex"])
        )
        ## 推送日志启用开关：关闭后保留高级正则配置，但不会实际采集推送日志
        self.Script_PushLogEnabled = ConfigItem(
            "Script", "PushLogEnabled", False, BoolValidator()
        )
        ## 推送日志高级模式（JSON 数组，每项形如 {"type":"regex|multiline",...}）
        self.Script_PushLogPatterns = ConfigItem("Script", "PushLogPatterns", "")

        ## Game ------------------------------------------------------------
        ## 是否启用游戏
        self.Game_Enabled = ConfigItem("Game", "Enabled", False, BoolValidator())
        ## 游戏类型
        self.Game_Type = ConfigItem(
            "Game", "Type", "Emulator", OptionsValidator(["Emulator", "Client", "URL"])
        )
        ## 游戏路径
        self.Game_Path = ConfigItem("Game", "Path", "", FileValidator())
        ## 自定义协议URL
        self.Game_URL = ConfigItem("Game", "URL", "")
        ## 游戏进程名称
        self.Game_ProcessName = ConfigItem("Game", "ProcessName", "")
        ## 游戏启动参数
        self.Game_Arguments = ConfigItem("Game", "Arguments", "")
        ## 等待时间（秒）
        self.Game_WaitTime = ConfigItem("Game", "WaitTime", 0, RangeValidator(0, 9999))
        ## 是否强制关闭
        self.Game_IfForceClose = ConfigItem(
            "Game", "IfForceClose", False, BoolValidator()
        )
        ## 模拟器 ID
        self.Game_EmulatorId = ConfigItem(
            "Game",
            "EmulatorId",
            "-",
            MultipleUIDValidator("-", self.related_config, "EmulatorConfig"),
        )
        ## 模拟器索引
        self.Game_EmulatorIndex = ConfigItem("Game", "EmulatorIndex", "-")

        ## Run -------------------------------------------------------------
        ## 仅在跟踪启动程序自身时按退出码判定失败
        self.Run_CheckExitCode = ConfigItem(
            "Run", "CheckExitCode", False, BoolValidator()
        )
        ## 超时或日志停滞后是否允许额外补跑
        self.Run_TimeoutRecoveryEnabled = ConfigItem(
            "Run", "TimeoutRecoveryEnabled", True, BoolValidator()
        )
        ## 单账号运行总时限（分钟），包含等待和全部重试
        self.Run_HardTimeLimit = ConfigItem(
            "Run", "HardTimeLimit", 120, RangeValidator(1, 9999)
        )
        ## 代理次数限制
        self.Run_ProxyTimesLimit = ConfigItem(
            "Run", "ProxyTimesLimit", 0, RangeValidator(0, 9999)
        )
        ## 运行次数限制
        self.Run_RunTimesLimit = ConfigItem(
            "Run", "RunTimesLimit", 3, RangeValidator(1, 9999)
        )
        ## 运行时间限制（分钟）
        self.Run_RunTimeLimit = ConfigItem(
            "Run", "RunTimeLimit", 10, RangeValidator(1, 9999)
        )

        self.UserData = MultipleConfig([GeneralUserConfig])

        super().__init__()


class GameSignAccountGroup(ConfigBase):
    """游戏社区账号组配置"""

    def __init__(self) -> None:

        ## GameSignAccount - 账号组名称
        self.Name = ConfigItem("GameSignAccount", "Name", "用户 1", StringValidator())
        ## GameSignAccount - 是否启用（该用户是否参与签到）
        self.Enabled = ConfigItem("GameSignAccount", "Enabled", True, BoolValidator())
        ## GameSignAccount - 米游社登录凭证 (DPAPI 加密)
        self.MiyousheToken = ConfigItem(
            "GameSignAccount", "MiyousheToken", "", EncryptValidator()
        )
        ## GameSignAccount - 米游社安卓设备 ID (DPAPI 加密，仅用于绝区零便笺)
        self.MiyousheDeviceId = ConfigItem(
            "GameSignAccount", "MiyousheDeviceId", "", EncryptValidator()
        )
        ## GameSignAccount - 米游社安卓设备指纹 (DPAPI 加密，仅用于绝区零便笺)
        self.MiyousheDeviceFp = ConfigItem(
            "GameSignAccount", "MiyousheDeviceFp", "", EncryptValidator()
        )
        ## GameSignAccount - 云原神 combo token (DPAPI 加密)
        self.CloudGenshinToken = ConfigItem(
            "GameSignAccount", "CloudGenshinToken", "", EncryptValidator()
        )
        ## GameSignAccount - 库街区登录凭证 (DPAPI 加密)
        self.KuroToken = ConfigItem(
            "GameSignAccount", "KuroToken", "", EncryptValidator()
        )
        ## GameSignAccount - 森空岛登录凭证 (DPAPI 加密)
        self.SklandToken = ConfigItem(
            "GameSignAccount", "SklandToken", "", EncryptValidator()
        )
        ## GameSignAccount - 塔吉多及云异环登录凭证 (DPAPI 加密)
        ## 支持 refreshToken 纯文本或包含 cloudToken/cloudUserId 的 JSON。
        self.TaygedoToken = ConfigItem(
            "GameSignAccount", "TaygedoToken", "", EncryptValidator()
        )
        ## GameSignAccount - 上次签到日期 (按用户隔离，防止重复触发)
        self.LastSignDate = ConfigItem(
            "GameSignAccount",
            "LastSignDate",
            "2000-01-01",
            DateTimeValidator("%Y-%m-%d"),
        )

        super().__init__()


class ToolsConfig(ConfigBase):
    """工具配置"""

    def __init__(self) -> None:

        ## GameSign - 启用签到
        self.GameSign_Enabled = ConfigItem(
            "GameSign", "Enabled", False, BoolValidator()
        )
        ## GameSign - 签到后发送通知
        self.GameSign_NotifyEnabled = ConfigItem(
            "GameSign", "NotifyEnabled", False, BoolValidator()
        )
        ## GameSign - 启用日常便笺
        self.GameSign_ActivityEnabled = ConfigItem(
            "GameSign", "ActivityEnabled", True, BoolValidator()
        )
        ## GameSign - 启动时运行
        self.GameSign_RunOnStartup = ConfigItem(
            "GameSign", "RunOnStartup", False, BoolValidator()
        )
        ## GameSign - 是否立即开始
        self.GameSign_AutoStart = ConfigItem(
            "GameSign", "AutoStart", False, BoolValidator()
        )
        ## GameSign - 账号组 (MultipleConfig)
        self.GameSign_Accounts = MultipleConfig([GameSignAccountGroup])
        ## GameSign - 上次签到日期 (防止重复触发)
        self.GameSign_LastSignDate = ConfigItem(
            "GameSign", "LastSignDate", "2000-01-01", DateTimeValidator("%Y-%m-%d")
        )
        ## GameSign - 签到状态标签 (虚拟字段)
        self.GameSign_Status = ConfigItem(
            "GameSign",
            "Status",
            "-",
            VirtualConfigValidator(self.game_sign_status),
        )
        ## GameSign - 签到结果详情 (虚拟字段)
        self.GameSign_Result = ConfigItem(
            "GameSign",
            "Result",
            "{}",
            VirtualConfigValidator(self.game_sign_result),
        )

        self._game_sign_result_data: dict = {}

        super().__init__()

    def game_sign_status(self) -> str:
        """游戏社区状态标签"""

        if not self.get("GameSign", "Enabled"):
            return TagItem(text="未启用", color="gray").model_dump_json()
        return TagItem(text="已启用", color="green").model_dump_json()

    def game_sign_result(self) -> str:
        """游戏社区结果 JSON"""

        return json.dumps(self._game_sign_result_data, ensure_ascii=False)


class GlobalConfig(ConfigBase):
    """全局配置"""

    def __init__(self):
        ## Replay -----------------------------------------------------------
        ## 连接已运行的 OBS，在自动代理最终失败时保存回放。
        self.Replay_Enabled = ConfigItem("Replay", "Enabled", False, BoolValidator())
        ## OBS WebSocket 仅连接本机。
        self.Replay_Port = ConfigItem("Replay", "Port", 4455, RangeValidator(1, 65535))
        ## OBS 认证密码按现有敏感配置规则加密落盘。
        self.Replay_Password = ConfigItem("Replay", "Password", "", EncryptValidator())
        ## MAS 副本的保留数量，不清理 OBS 原文件。
        self.Replay_MaxReplayCount = ConfigItem(
            "Replay", "MaxReplayCount", 3, RangeValidator(1, 20)
        )

        ## Function ---------------------------------------------------------
        ## 历史记录保留时间（天）
        self.Function_HistoryRetentionTime = ConfigItem(
            "Function",
            "HistoryRetentionTime",
            0,
            OptionsValidator([7, 15, 30, 60, 90, 180, 365, 0]),
        )
        ## 是否允许睡眠
        self.Function_IfAllowSleep = ConfigItem(
            "Function", "IfAllowSleep", False, BoolValidator()
        )
        ## 是否启用静默模式
        self.Function_IfSilence = ConfigItem(
            "Function", "IfSilence", False, BoolValidator()
        )
        ## 是否同意 Bilibili 协议
        self.Function_IfAgreeBilibili = ConfigItem(
            "Function", "IfAgreeBilibili", False, BoolValidator()
        )
        ## 是否屏蔽模拟器广告
        self.Function_IfBlockAd = ConfigItem(
            "Function", "IfBlockAd", False, BoolValidator()
        )
        ## 个人版 MSS 的专属编排（灾变防线），只对个人版项目生效，
        ## 普通版 MSS 与其它脚本都会忽略它。
        self.Function_IfPersonalMss = ConfigItem(
            "Function", "IfPersonalMss", False, BoolValidator()
        )

        ## Display ----------------------------------------------------------
        ## 无人值守时是否允许 MAS 挂载虚拟显示器。
        ## 所有真实显示输出都断开后 Windows 只保留一块占位的幻影屏，它照旧上报正常的
        ## 分辨率但背后没有输出；冷启动时更会起在很小的分辨率上，把被托管的 PC 端游戏
        ## 窗口压小并被游戏写进自己的配置，之后每轮都在同一处失败。挂一块真实的虚拟屏
        ## 可从源头断掉。
        ## 需要用户自行安装 Parsec 虚拟显示驱动，MAS 不分发驱动。
        self.Display_IfEnableVirtualDisplay = ConfigItem(
            "Display", "IfEnableVirtualDisplay", False, BoolValidator()
        )
        ## 虚拟显示器的刷新率（分辨率固定 1920x1080）。
        ## 分辨率固定是因为只有它 Windows 给 100% 缩放，再高会被自动上缩放，游戏窗口
        ## 又要面对 DPI 虚拟化。取值必须在驱动 advertise 的模式表里，否则会被 BADMODE 拒绝。
        self.Display_VirtualDisplayMode = ConfigItem(
            "Display",
            "VirtualDisplayMode",
            "1920x1080@60",
            OptionsValidator(["1920x1080@60", "1920x1080@30"]),
        )

        ## ChildSession -----------------------------------------------------
        ## 是否启用基于 BetterGI 的本地远程桌面（Child Session）执行任务
        self.ChildSession_Enabled = ConfigItem(
            "ChildSession", "Enabled", False, BoolValidator()
        )
        ## C# 远程桌面宿主 IPC 端口
        self.ChildSession_HostPort = ConfigItem(
            "ChildSession", "HostPort", 36165, RangeValidator(1024, 65535)
        )
        ## 远程桌面分辨率
        self.ChildSession_Resolution = ConfigItem(
            "ChildSession", "Resolution", "2560x1440"
        )
        ## 启动时是否隐藏远程桌面预览窗口
        self.ChildSession_StartHidden = ConfigItem(
            "ChildSession", "StartHidden", False, BoolValidator()
        )
        ## 是否开启观看模式（屏蔽本机键鼠进入桌面分身）
        self.ChildSession_WatchMode = ConfigItem(
            "ChildSession", "WatchMode", True, BoolValidator()
        )

        ## Hotkey -----------------------------------------------------------
        ## 是否启用系统全局热键
        self.Hotkey_Enabled = ConfigItem("Hotkey", "Enabled", True, BoolValidator())
        ## 全局热键：控制程序启停
        self.Hotkey_ToggleStartStop = ConfigItem(
            "Hotkey", "ToggleStartStop", "Ctrl+Alt+S"
        )
        ## 全局热键：切换到上一个任务
        self.Hotkey_PreviousTask = ConfigItem("Hotkey", "PreviousTask", "Ctrl+Alt+Left")
        ## 全局热键：切换到下一个任务
        self.Hotkey_NextTask = ConfigItem("Hotkey", "NextTask", "Ctrl+Alt+Right")

        ## Voice ------------------------------------------------------------
        ## 是否启用语音
        self.Voice_Enabled = ConfigItem("Voice", "Enabled", False, BoolValidator())
        ## 语音类型
        self.Voice_Type = ConfigItem(
            "Voice", "Type", "simple", OptionsValidator(["simple", "noisy"])
        )

        ## Start ------------------------------------------------------------
        ## 是否自动启动
        self.Start_IfSelfStart = ConfigItem(
            "Start", "IfSelfStart", False, BoolValidator()
        )
        ## 是否启动时直接最小化
        self.Start_IfMinimizeDirectly = ConfigItem(
            "Start", "IfMinimizeDirectly", False, BoolValidator()
        )

        ## UI ---------------------------------------------------------------
        ## 是否显示托盘图标
        self.UI_IfShowTray = ConfigItem("UI", "IfShowTray", False, BoolValidator())
        ## 是否关闭到托盘
        self.UI_IfToTray = ConfigItem("UI", "IfToTray", False, BoolValidator())
        ## 是否隐藏主窗口关闭按钮
        self.UI_IfHideCloseButton = ConfigItem(
            "UI", "IfHideCloseButton", False, BoolValidator()
        )

        ## Notify -----------------------------------------------------------
        ## 任务结果推送时间
        self.Notify_SendTaskResultTime = ConfigItem(
            "Notify",
            "SendTaskResultTime",
            "不推送",
            OptionsValidator(["不推送", "任何时刻", "仅失败时"]),
        )
        ## 是否发送统计信息
        self.Notify_IfSendStatistic = ConfigItem(
            "Notify", "IfSendStatistic", False, BoolValidator()
        )
        ## 是否发送六星通知
        self.Notify_IfSendSixStar = ConfigItem(
            "Notify", "IfSendSixStar", False, BoolValidator()
        )
        ## 是否推送系统通知
        self.Notify_IfPushPlyer = ConfigItem(
            "Notify", "IfPushPlyer", False, BoolValidator()
        )
        ## 是否发送邮件
        self.Notify_IfSendMail = ConfigItem(
            "Notify", "IfSendMail", False, BoolValidator()
        )
        ## 是否发送Koishi通知
        self.Notify_IfKoishiSupport = ConfigItem(
            "Notify", "IfKoishiSupport", False, BoolValidator()
        )
        ## Koishi WebSocket 服务器地址
        self.Notify_KoishiServerAddress = ConfigItem(
            "Notify",
            "KoishiServerAddress",
            "ws://localhost:5140/AUTO_MAS",
            URLValidator(),
        )
        ## Koishi Token
        self.Notify_KoishiToken = ConfigItem("Notify", "KoishiToken", "")
        ## 是否启用 QQ 官方机器人通知（凭据由扫码登录流程管理）
        self.Notify_IfOpenClawQQ = ConfigItem(
            "Notify", "IfOpenClawQQ", False, BoolValidator()
        )
        ## QQ 官方机器人应用 ID（由扫码登录响应返回）
        self.Notify_OpenClawQQAppId = ConfigItem("Notify", "OpenClawQQAppId", "")
        ## QQ 官方机器人客户端密钥（由扫码登录响应返回）
        self.Notify_OpenClawQQClientSecret = ConfigItem(
            "Notify", "OpenClawQQClientSecret", "", EncryptValidator()
        )
        ## QQ 官方机器人目标用户 OpenID（由扫码登录响应返回）
        self.Notify_OpenClawQQTargetOpenId = ConfigItem(
            "Notify", "OpenClawQQTargetOpenId", ""
        )
        ## SMTP 服务器地址
        self.Notify_SMTPServerAddress = ConfigItem("Notify", "SMTPServerAddress", "")
        ## 邮箱授权码
        self.Notify_AuthorizationCode = ConfigItem(
            "Notify", "AuthorizationCode", "", EncryptValidator()
        )
        ## 发件地址
        self.Notify_FromAddress = ConfigItem("Notify", "FromAddress", "")
        ## 收件地址
        self.Notify_ToAddress = ConfigItem("Notify", "ToAddress", "")
        ## 是否启用 Server 酱
        self.Notify_IfServerChan = ConfigItem(
            "Notify", "IfServerChan", False, BoolValidator()
        )
        ## Server 酱密钥
        self.Notify_ServerChanKey = ConfigItem("Notify", "ServerChanKey", "")
        ## 是否启用中国移动新消息通知
        self.Notify_IfCMCCNewMsg = ConfigItem(
            "Notify", "IfCMCCNewMsg", False, BoolValidator()
        )
        ## 中国移动新消息 Channel API Key
        self.Notify_CMCCNewMsgApiKey = ConfigItem(
            "Notify", "CMCCNewMsgApiKey", "", EncryptValidator()
        )
        ## 自定义 Webhook 列表
        self.Notify_CustomWebhooks = MultipleConfig([Webhook])

        ## Update -----------------------------------------------------------
        ## 是否自动更新
        self.Update_IfAutoUpdate = ConfigItem(
            "Update", "IfAutoUpdate", False, BoolValidator()
        )
        ## 暂停更新截止日期（YYYY-MM-DD，空串表示未暂停）
        self.Update_PauseUntil = ConfigItem("Update", "PauseUntil", "")
        ## 更新源
        self.Update_Source = ConfigItem(
            "Update",
            "Source",
            "GitHub",
            OptionsValidator(["GitHub", "MirrorChyan", "AutoSite", "CNB"]),
        )
        ## 更新频道
        self.Update_Channel = ConfigItem(
            "Update", "Channel", "stable", OptionsValidator(["stable", "beta"])
        )
        ## 代理地址
        self.Update_ProxyAddress = ConfigItem("Update", "ProxyAddress", "")
        ## GitHub 加速镜像
        ## **只影响 MFW 项目包从 GitHub Release 下载这一条路**（脚本的
        ## `Update.Source` 选 GitHub 时）：国内直连 GitHub 常年 100 多 KB/s，
        ## 359MB 的全量包要四十分钟。`Auto` 依次试镜像、全部失败再回直连；
        ## `Off` 只直连。MAS 自身的更新与初始化 clone 走前端 mirrorService，
        ## 不读这一项；Mirror 酱是另一个源，也不受它影响。
        self.Update_GitHubMirror = ConfigItem(
            "Update", "GitHubMirror", "Auto", OptionsValidator(["Auto", "Off"])
        )
        ## 镜像站 CDK
        self.Update_MirrorChyanCDK = ConfigItem(
            "Update", "MirrorChyanCDK", "", EncryptValidator()
        )

        ## Data -------------------------------------------------------------
        ## 上次关卡更新时间
        self.Data_LastStageUpdated = ConfigItem(
            "Data",
            "LastStageUpdated",
            "2000-01-01 00:00:00",
            DateTimeValidator("%Y-%m-%d %H:%M:%S"),
        )
        ## 关卡数据的版本标识符
        self.Data_StageETag = ConfigItem("Data", "StageETag", "")
        ## 关卡信息数据
        self.Data_StageData = ConfigItem(
            "Data", "StageData", "{ }", JSONValidator(), legacy_name="Stage"
        )
        ## 关卡信息
        self.Data_Stage = ConfigItem(
            "Data", "Stage", "-", VirtualConfigValidator(self.getStage)
        )
        ## 上次公告更新时间
        self.Data_LastNoticeUpdated = ConfigItem(
            "Data",
            "LastNoticeUpdated",
            "2000-01-01 00:00:00",
            DateTimeValidator("%Y-%m-%d %H:%M:%S"),
        )
        ## 公告的版本标识符
        self.Data_NoticeETag = ConfigItem("Data", "NoticeETag", "")
        ## 是否显示公告
        self.Data_IfShowNotice = ConfigItem(
            "Data", "IfShowNotice", True, BoolValidator()
        )
        ## 公告内容
        self.Data_Notice = ConfigItem("Data", "Notice", "{ }", JSONValidator())
        ## 上次维护信息检查时间
        self.Data_LastMaintenanceUpdated = ConfigItem(
            "Data",
            "LastMaintenanceUpdated",
            "2000-01-01 00:00:00",
            DateTimeValidator("%Y-%m-%d %H:%M:%S"),
        )
        ## 维护信息的版本标识符
        self.Data_MaintenanceETag = ConfigItem("Data", "MaintenanceETag", "")
        ## 维护信息内容
        self.Data_Maintenance = ConfigItem(
            "Data",
            "Maintenance",
            '{"schema_version": 1, "games": {}}',
            JSONValidator(),
        )
        ## 分享站外观上传记录：{用户名: {外观 ID: {fileId, fileKey, displayName, updatedAt}}}
        self.Data_ShareAppearanceUploads = ConfigItem(
            "Data", "ShareAppearanceUploads", "{}", JSONValidator()
        )
        super().__init__()

        ## 模拟器配置列表
        self.EmulatorConfig = MultipleConfig([EmulatorConfig])
        ## 脚本配置列表（顺序与 CLASS_BOOK 一致）
        self.ScriptConfig = MultipleConfig(list(CLASS_BOOK.values()))
        ## 队列配置列表
        self.QueueConfig = MultipleConfig([QueueConfig])
        ## 启动期攒下、主连接建立后一次性发出的系统通知
        self.startup_notices: list[dict[str, Any]] = []
        ## 工具箱配置
        self.ToolsConfig = ToolsConfig()

        GeneralConfig.related_config["EmulatorConfig"] = self.EmulatorConfig
        QueueItem.related_config["ScriptConfig"] = self.ScriptConfig

    def getStage(self) -> str:
        """获取关卡信息"""

        try:
            raw_stage_data = json.loads(self.get("Data", "StageData"))
            if "Official" in raw_stage_data:
                stage_data_by_server = {
                    server: data.get("sideStoryStage", {})
                    for server, data in raw_stage_data.items()
                    if isinstance(data, dict)
                }
            else:
                stage_data_by_server = {"Official": raw_stage_data}

            all_stage_data = {}
            for server, server_stage_data in stage_data_by_server.items():
                activity_stage_drop_info = []
                activity_stage_combox = []

                for side_story in server_stage_data.values():
                    activity = side_story["Activity"]
                    activity_timezone = timezone(
                        timedelta(hours=activity.get("TimeZone", 8))
                    )
                    if (
                        datetime.strptime(
                            activity["UtcStartTime"], "%Y/%m/%d %H:%M:%S"
                        ).replace(tzinfo=activity_timezone)
                        < datetime.now(tz=activity_timezone)
                        < datetime.strptime(
                            activity["UtcExpireTime"], "%Y/%m/%d %H:%M:%S"
                        ).replace(tzinfo=activity_timezone)
                    ):
                        for stage in side_story["Stages"]:
                            activity_stage_combox.append(
                                {"label": stage["Display"], "value": stage["Value"]}
                            )

                            if "SSReopen" not in stage["Display"]:
                                if stage["Drop"] in MATERIALS_MAP:
                                    drop_id = stage["Drop"]
                                elif "玉" in stage["Drop"]:
                                    drop_id = "30012"
                                else:
                                    drop_id = "NotFound"

                                activity_stage_drop_info.append(
                                    {
                                        "Display": stage["Display"],
                                        "Value": stage["Value"],
                                        "Drop": drop_id,
                                        "DropName": MATERIALS_MAP.get(
                                            stage["Drop"], stage["Drop"]
                                        ),
                                        "Activity": activity,
                                    }
                                )

                stage_data = {"Info": activity_stage_drop_info}

                for day in range(0, 8):
                    res_stage = []

                    for stage in RESOURCE_STAGE_INFO:
                        if day in stage["days"] or day == 0:
                            res_stage.append(
                                {"label": stage["text"], "value": stage["value"]}
                            )

                    stage_data[calendar.day_name[day - 1] if day > 0 else "ALL"] = (
                        res_stage[0:1] + activity_stage_combox + res_stage[1:]
                    )

                all_stage_data[server] = stage_data
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning(
                f"解析活动关卡信息失败, 按空关卡处理: {type(e).__name__}: {e}"
            )
            return "{ }"

        return json.dumps(all_stage_data, ensure_ascii=False)


CLASS_BOOK = {"General": GeneralConfig}
"""配置类映射表: 脚本类型键 → 配置类, GlobalConfig 的脚本配置列表由此派生"""

"""计划表注册表"""
