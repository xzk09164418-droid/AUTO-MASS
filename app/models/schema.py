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


from pathlib import PureWindowsPath
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Union,
)

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SecretStr,
    field_validator,
    model_validator,
)

from app.utils.constants import (
    BASE_INDEPENDENT,
    BASE_NATIVE,
    BASE_SHARED,
    normalize_base_source,
)


class _SchemaModel(BaseModel):
    """按需构建校验器与序列化器，减少未使用模型的启动开销。"""

    model_config = ConfigDict(defer_build=True)


class ChildSessionLeaseProcessData(_SchemaModel):
    """调用方明确授权回收的进程身份；不允许仅凭进程名称认领。"""

    pid: int = Field(gt=0)
    createdAt: float = Field(gt=0)
    sessionId: int = Field(gt=0)


class OutBase(_SchemaModel):
    code: int = Field(default=200, description="状态码")
    status: str = Field(default="success", description="操作状态")
    message: str = Field(default="操作成功", description="操作消息")


class InfoOut(OutBase):
    data: Dict[str, Any] = Field(..., description="收到的服务器数据")


class VersionOut(OutBase):
    if_need_update: bool = Field(..., description="后端代码是否需要更新")
    current_time: str = Field(..., description="后端代码当前时间戳")
    current_hash: str = Field(..., description="后端代码当前哈希值")


class NoticeOut(OutBase):
    if_need_show: bool = Field(..., description="是否需要显示公告")
    data: Dict[str, str] = Field(
        ..., description="公告信息, key为公告标题, value为公告内容"
    )


class TagItem(_SchemaModel):
    text: str = Field(..., description="标签文本")
    color: Literal[
        "red",
        "blue",
        "green",
        "yellow",
        "orange",
        "purple",
        "pink",
        "brown",
        "black",
        "white",
        "gray",
        "silver",
        "gold",
    ] = Field(..., description="标签颜色")


class ComboBoxItem(_SchemaModel):
    label: str = Field(..., description="展示值")
    value: Optional[str] = Field(..., description="实际值")


class ComboBoxOut(OutBase):
    data: List[ComboBoxItem] = Field(..., description="下拉框选项")


class BlueArchiveActivityIn(_SchemaModel):
    """碧蓝档案活动数据查询参数"""

    line_type: Literal["JP", "Globle", "CN"] = Field(
        ..., description="服务器：JP 日服 / Globle 国际服 / CN 国服（原文拼写如此）"
    )
    page: int = Field(default=1, ge=1, le=20, description="页码，从 1 开始")
    page_size: int = Field(default=50, ge=1, le=100, description="每页条数")


class GameCalendarActivityInfo(_SchemaModel):
    name: str = Field(..., min_length=1, max_length=500, description="活动名称")
    startTime: AwareDatetime = Field(..., description="活动开始时间，包含时区")
    endTime: AwareDatetime = Field(..., description="活动结束时间，包含时区")

    @model_validator(mode="after")
    def validate_period(self):
        if not self.name.strip() or self.endTime <= self.startTime:
            raise ValueError("活动名称不能为空，结束时间必须晚于开始时间")
        return self


class GameCalendarActivityUpdateIn(GameCalendarActivityInfo):
    completed: bool = Field(..., description="是否由用户标记为已完成")


# 此模型用于 FastAPI Depends()，路由注册前必须生成完整的查询参数签名。
class GameCalendarActivityScopeIn(BaseModel):
    game: Literal[
        "endfield",
        "starrail",
        "genshin",
        "zenless",
        "wutheringwaves",
        "nte",
        "reverse1999",
        "bluearchive",
        "arknights",
        "stellasora",
        "infinitynikki",
    ] = Field(..., description="首页游戏标识")
    server: Literal["cn", "jp", "global"] = Field(
        default="cn", description="碧蓝档案服务器，其它游戏忽略此字段"
    )


class GameCalendarActivityCompletionIn(
    GameCalendarActivityScopeIn, GameCalendarActivityUpdateIn
):
    pass


class GameCalendarActivitiesOut(OutBase):
    data: list[GameCalendarActivityInfo] = Field(
        default_factory=list, description="用户已完成且未过期的活动"
    )


class ConfigBackupItemOut(_SchemaModel):
    """配置备份条目"""

    time: str = Field(..., description="备份时间戳（目录名，如 20260910-104500）")
    base: Optional[str] = Field(
        default=None,
        description="备份时点的 base 来源（shared/independent/native）；无标注（旧版备份或未声明来源）为 null",
    )


class ConfigBackupListOut(OutBase):
    data: List[ConfigBackupItemOut] = Field(..., description="备份列表（时间倒序）")
    base: Optional[str] = Field(
        default=None,
        description="当前 base 来源（shared/independent/native）；无来源概念（非 base 专项）为 null",
    )


class ConfigBackupRestoreIn(_SchemaModel):
    """把指定备份恢复到目标位置（target 取值由专项池定义）"""

    scriptId: str = Field(..., description="所属脚本ID")
    userId: str = Field(..., description="目标用户ID")
    time: str = Field(..., description="备份时间戳")
    target: str = Field(
        ...,
        description="恢复目标（如 zzz-od 的 mas/onedragon、ok-nte 的 mas/native）；非法值返回 400",
    )
    force: bool = Field(
        default=False,
        description="源配置损坏时是否强制恢复（False 时返回 409 由前端二次确认，True 跳过损坏文件相关的保护步骤）",
    )


class ConfigBackupRestoreOut(OutBase):
    target: str = Field(..., description="实际执行的恢复目标")


class ConfigBackupEnsureIn(_SchemaModel):
    """按需归档目标池当前配置（编辑界面进入/退出时机，指纹去重）"""

    scriptId: str = Field(..., description="所属脚本ID")
    userId: str = Field(..., description="目标用户ID")
    target: str = Field(..., description="归档目标（取值由专项池定义）")


class ConfigBackupEnsureOut(OutBase):
    created: bool = Field(
        ..., description="本次是否新建了归档（False=指纹无变化跳过或无可归档内容）"
    )
    time: str = Field(..., description="最新备份时间戳（无任何备份为空串）")


class ConfigBackupPreviewOut(OutBase):
    """备份配置摘要（预览用，纯读不恢复；载荷结构由专项定义）"""

    time: str = Field(..., description="备份时间戳")
    target: str = Field(..., description="备份类别")
    data: dict = Field(
        ...,
        description="专项预览载荷（如 zzz-od 的 info/account/tasks/instances 或 ok-nte 的 files）",
    )


class ConfigBackupFileOut(OutBase):
    """备份内文本文件内容（只读；路径限归档内相对路径，防穿越）"""

    time: str = Field(..., description="备份时间戳")
    target: str = Field(..., description="备份类别")
    path: str = Field(..., description="归档内相对路径（如 M7A/config.yaml）")
    size: int = Field(..., description="文件字节数")
    content: str = Field(
        ...,
        description="文本内容（utf-8 兼容 BOM 读取，无法解码部分以替换符呈现；超出大小上限返回 400）",
    )


class EmulatorConfigIndexItem(_SchemaModel):
    uid: str = Field(..., description="唯一标识符")
    type: Literal["EmulatorConfig"] = Field(..., description="配置类型")


class EmulatorConfig_Info(_SchemaModel):
    Name: Optional[str] = Field(default=None, description="模拟器名称")
    Type: Optional[Literal["general", "mumu", "ldplayer", "emulator2"]] = Field(
        default=None, description="模拟器类型"
    )
    Path: Optional[str] = Field(default=None, description="模拟器路径")
    Paths: Optional[str] = Field(
        default=None, description="Emulator 2.0 纳管的模拟器路径列表（JSON）"
    )
    Slots: Optional[str] = Field(
        default=None, description="Emulator 2.0 的设备号槽位表（JSON）"
    )
    BossKey: Optional[str] = Field(default=None, description="老板键快捷键配置")
    MaxWaitTime: Optional[int] = Field(default=None, description="最大等待时间（秒）")
    ConfigGuard: Optional[bool] = Field(
        default=None, description="Emulator 2.0: 配置守卫是否开启"
    )
    Baselines: Optional[str] = Field(
        default=None, description="Emulator 2.0: 配置守卫的基准, JSON 字符串"
    )
    StableMode: Optional[bool] = Field(
        default=None, description="Emulator 2.0: 稳定模式是否开启"
    )
    ForceKillOnClose: Optional[bool] = Field(
        default=None, description="关闭 MuMu 时强力清理残留进程"
    )
    ForceKillBeforeLaunch: Optional[bool] = Field(
        default=None, description="启动 MuMu 前先关闭已在运行的实例并强力清理残留进程"
    )


class EmulatorConfig(_SchemaModel):
    Info: Optional[EmulatorConfig_Info] = Field(
        default=None, description="模拟器基础信息"
    )


class ToolsConfig_GameSign(_SchemaModel):
    Enabled: bool | None = Field(default=None, description="是否启用游戏社区")
    NotifyEnabled: bool | None = Field(default=None, description="签到后是否发送通知")
    ActivityEnabled: bool | None = Field(default=None, description="是否启用日常便笺")
    RunOnStartup: bool | None = Field(default=None, description="启动时运行")
    AutoStart: bool | None = Field(default=None, description="是否立即开始")
    LastSignDate: str | None = Field(default=None, description="上次签到日期")
    Status: str | None = Field(default=None, description="签到状态标签")
    Result: str | None = Field(default=None, description="签到结果 JSON")


class GameSignAccountGroupConfig(_SchemaModel):
    """游戏社区账号组配置"""

    Name: str | None = Field(default=None, description="账号组名称")
    Enabled: bool | None = Field(default=None, description="是否启用")
    MiyousheToken: str | None = Field(default=None, description="米游社登录凭证")
    MiyousheDeviceId: str | None = Field(
        default=None,
        description="米游社安卓设备 ID，仅用于绝区零便笺",
        repr=False,
    )
    MiyousheDeviceFp: str | None = Field(
        default=None,
        description="米游社安卓设备指纹，仅用于绝区零便笺",
        repr=False,
    )
    CloudGenshinToken: str | None = Field(
        default=None,
        description="云原神 combo token",
    )
    KuroToken: str | None = Field(default=None, description="库街区登录凭证")
    SklandToken: str | None = Field(default=None, description="森空岛登录凭证")
    TaygedoToken: str | None = Field(default=None, description="塔吉多及云异环登录凭证")
    LastSignDate: str | None = Field(default=None, description="账号组上次签到日期")


class GameSignAccountCreateOut(OutBase):
    """游戏社区账号组创建响应"""

    accountId: str = Field(default="", description="账号组 UUID")
    data: GameSignAccountGroupConfig = Field(
        default_factory=GameSignAccountGroupConfig, description="账号组配置"
    )


class GameSignAccountInstanceOut(_SchemaModel):
    """游戏社区账号组顺序项。"""

    uid: str = Field(..., description="账号组 UUID")
    type: str = Field(..., description="账号组配置类型")


class GameSignAccountDataOut(_SchemaModel):
    """动态 UUID 键对应的游戏社区账号组数据。"""

    GameSignAccount: GameSignAccountGroupConfig = Field(..., description="账号组配置")


class GameSignAccountsListOut(OutBase):
    """游戏社区账号组列表响应"""

    data: Dict[
        str,
        list[GameSignAccountInstanceOut] | GameSignAccountDataOut,
    ] = Field(default_factory=dict, description="账号组列表")


class GameSignAccountUpdateIn(_SchemaModel):
    """游戏社区账号组更新请求"""

    accountId: str = Field(..., description="账号组 UUID")
    data: GameSignAccountGroupConfig = Field(..., description="账号组配置")


class GameSignAccountDeleteIn(_SchemaModel):
    """游戏社区账号组删除请求"""

    accountId: str = Field(..., description="账号组 UUID")


class GameSignAccountReorderIn(_SchemaModel):
    """游戏社区账号组排序请求"""

    order: list[str] = Field(..., description="账号组 UUID 顺序列表")


class CommunityActivityQueryIn(_SchemaModel):
    """游戏社区日常查询请求。"""

    accountIds: list[str] | None = Field(
        default=None,
        description="指定账号组 UUID 列表；为空时查询全部已配置账号组",
    )


class CommunityActivityTaskOut(_SchemaModel):
    """日常活动中的单项任务。"""

    name: str = Field(..., description="任务名称")
    completed: int = Field(..., description="已完成数量")
    target: int = Field(..., description="目标数量")
    status: str = Field(..., description="任务状态")
    period: str = Field(default="daily", description="任务周期")


class CommunityActivityResourceOut(_SchemaModel):
    """日常活动中的可用资源。"""

    name: str = Field(..., description="资源名称")
    current: int = Field(..., description="当前数量")
    target: int = Field(..., description="容量上限")
    status: str = Field(..., description="资源状态")


class CommunityActivitySnapshotOut(_SchemaModel):
    """单个游戏角色的日常活动快照。"""

    account: str = Field(..., description="账号组名称")
    accountUid: str = Field(..., description="账号组 UUID")
    game: str = Field(..., description="游戏名称")
    platform: str = Field(..., description="社区平台名称")
    status: Literal["success", "empty", "limited", "unavailable", "failed"] = Field(
        ..., description="活动查询状态"
    )
    completed: int | None = Field(default=None, description="已完成数量")
    target: int | None = Field(default=None, description="目标数量")
    tasks: list[CommunityActivityTaskOut] = Field(
        default_factory=list, description="每日任务"
    )
    resources: list[CommunityActivityResourceOut] = Field(
        default_factory=list, description="可用资源"
    )
    reason: str = Field(default="", description="失败或受限原因")
    updatedAt: str = Field(default="", description="查询时间")
    roleName: str = Field(default="", description="角色名称")
    roleUid: str = Field(default="", description="角色 UID")
    server: str = Field(default="", description="角色区服")
    source: str = Field(default="", description="已确认的数据来源路径")


class CommunityActivityOut(OutBase):
    """游戏社区日常活动查询响应。"""

    data: list[CommunityActivitySnapshotOut] = Field(
        default_factory=list, description="按账号和游戏拆分的活动快照"
    )


class TaygedoLoginIn(_SchemaModel):
    """塔吉多一次性账号密码登录请求。"""

    accountId: str = Field(..., description="账号组 UUID")
    phone: str = Field(..., min_length=1, description="塔吉多账号或手机号")
    password: SecretStr = Field(..., min_length=1, description="塔吉多账号密码")


class ToolsConfig(_SchemaModel):
    GameSign: ToolsConfig_GameSign | None = Field(
        default=None, description="游戏社区签到配置"
    )


class WebhookIndexItem(_SchemaModel):
    uid: str = Field(..., description="唯一标识符")
    type: Literal["Webhook"] = Field(..., description="配置类型")


class Webhook_Info(_SchemaModel):
    Name: Optional[str] = Field(default=None, description="Webhook名称")
    Enabled: Optional[bool] = Field(default=None, description="是否启用")


class Webhook_Data(_SchemaModel):
    Url: Optional[str] = Field(default=None, description="Webhook URL")
    Template: Optional[str] = Field(default=None, description="消息模板")
    Headers: Optional[str] = Field(default=None, description="自定义请求头")
    Method: Optional[Literal["POST", "GET"]] = Field(
        default=None, description="请求方法"
    )


class Webhook(_SchemaModel):
    Info: Optional[Webhook_Info] = Field(default=None, description="Webhook基础信息")
    Data: Optional[Webhook_Data] = Field(default=None, description="Webhook配置数据")


class GlobalConfig_Function(_SchemaModel):
    HistoryRetentionTime: Optional[Literal[7, 15, 30, 60, 90, 180, 365, 0]] = Field(
        None, description="历史记录保留时间, 0表示永久保存"
    )
    IfAllowSleep: Optional[bool] = Field(default=None, description="允许休眠")
    IfSilence: Optional[bool] = Field(default=None, description="静默模式")
    IfAgreeBilibili: Optional[bool] = Field(
        default=None, description="同意哔哩哔哩用户协议"
    )
    IfBlockAd: Optional[bool] = Field(default=None, description="屏蔽模拟器广告")
    IfEnableTelemetry: Optional[bool] = Field(
        default=None, description="启用匿名错误与性能遥测"
    )
    IfPersonalMss: Optional[bool] = Field(
        default=None, description="个人版 MaaStellaSora 的专属编排（灾变防线）"
    )


class GlobalConfig_Replay(_SchemaModel):
    Enabled: Optional[bool] = Field(default=None, description="失败时保存 OBS 回放")
    Port: Optional[int] = Field(
        default=None, ge=1, le=65535, description="本机 OBS WebSocket 端口"
    )
    Password: Optional[str] = Field(
        default=None, description="OBS 密码，仅用于写入；省略时保留"
    )
    PasswordConfigured: Optional[bool] = Field(
        default=None, description="OBS 密码是否已配置，只读"
    )
    MaxReplayCount: Optional[int] = Field(
        default=None, ge=1, le=20, description="最多保留的回放副本数"
    )


class GlobalConfig_Display(_SchemaModel):
    IfEnableVirtualDisplay: Optional[bool] = Field(
        default=None,
        description="无人值守时，检测不到任何真实显示输出则临时挂载虚拟显示器（需自行安装 Parsec 虚拟显示驱动）",
    )
    VirtualDisplayMode: Optional[str] = Field(
        default=None,
        description="虚拟显示器的刷新率，分辨率固定 1920x1080；形如 1920x1080@60",
    )


class VirtualDisplayCheckResultItem(_SchemaModel):
    """检测的三段之一。分开报是有意的：给用户的下一步动作完全不同。"""

    stage: Literal["installed", "openable", "effective"] = Field(description="检测阶段")
    passed: bool = Field(description="该阶段是否通过")
    message: str = Field(description="面向用户的说明")


class VirtualDisplayCheckOut(OutBase):
    driverVersion: Optional[int] = Field(default=None, description="驱动次版本号")
    monitors: str = Field(default="", description="检测时的显示器概况")
    holding: Optional[str] = Field(
        default=None,
        description="守卫此刻挂着的虚拟显示器（设备名与模式），没挂时为空；设置页据此显示当前挂着哪块",
    )
    results: list[VirtualDisplayCheckResultItem] = Field(default_factory=list)


class VirtualDisplayDetachOut(OutBase):
    detached: bool = Field(
        default=False, description="有没有真的拆掉一块屏；没挂着时为 False"
    )


class GlobalConfig_Voice(_SchemaModel):
    Enabled: Optional[bool] = Field(default=None, description="语音功能是否启用")
    Type: Optional[Literal["simple", "noisy"]] = Field(
        default=None, description="语音类型, simple为简洁, noisy为聒噪"
    )


class GlobalConfig_Start(_SchemaModel):
    IfSelfStart: Optional[bool] = Field(
        default=None, description="是否在系统启动时自动运行"
    )
    IfMinimizeDirectly: Optional[bool] = Field(
        default=None, description="启动时是否直接最小化到托盘而不显示主窗口"
    )


class GlobalConfig_UI(_SchemaModel):
    IfShowTray: Optional[bool] = Field(default=None, description="是否常态显示托盘图标")
    IfToTray: Optional[bool] = Field(default=None, description="是否最小化到托盘")
    IfHideCloseButton: Optional[bool] = Field(
        default=None, description="是否隐藏主窗口关闭按钮"
    )


class GlobalConfig_Notify(_SchemaModel):
    SendTaskResultTime: Optional[Literal["不推送", "任何时刻", "仅失败时"]] = Field(
        default=None, description="任务结果推送时机"
    )
    IfSendStatistic: Optional[bool] = Field(
        default=None, description="是否发送统计信息"
    )
    IfSendSixStar: Optional[bool] = Field(
        default=None, description="是否发送公招六星通知"
    )
    IfPushPlyer: Optional[bool] = Field(default=None, description="是否推送系统通知")
    IfSendMail: Optional[bool] = Field(default=None, description="是否发送邮件通知")
    IfKoishiSupport: Optional[bool] = Field(
        default=None, description="是否启用Koishi支持"
    )
    KoishiServerAddress: Optional[str] = Field(
        default=None, description="Koishi服务器地址"
    )
    KoishiToken: Optional[str] = Field(default=None, description="Koishi Token")
    IfOpenClawQQ: Optional[bool] = Field(
        default=None, description="是否启用 QQ 官方机器人通知"
    )
    SMTPServerAddress: Optional[str] = Field(default=None, description="SMTP服务器地址")
    AuthorizationCode: Optional[str] = Field(default=None, description="SMTP授权码")
    FromAddress: Optional[str] = Field(default=None, description="邮件发送地址")
    ToAddress: Optional[str] = Field(default=None, description="邮件接收地址")
    IfServerChan: Optional[bool] = Field(
        default=None, description="是否使用ServerChan推送"
    )
    ServerChanKey: Optional[str] = Field(default=None, description="ServerChan推送密钥")
    IfCMCCNewMsg: Optional[bool] = Field(
        default=None, description="是否启用中国移动新消息通知"
    )
    CMCCNewMsgApiKey: Optional[str] = Field(
        default=None, description="中国移动新消息 Channel API Key"
    )


class NotifyChannelOptionOut(_SchemaModel):
    """渠道下拉选项的取值与文案键；取值保持后端配置字面量（含布尔）。"""

    value: Union[bool, str] = Field(..., description="选项值，保持后端配置字面量")
    labelKey: str = Field(..., description="选项文案的词表键")


class NotifyChannelFieldOut(_SchemaModel):
    """渠道在某个作用域暴露的一个配置字段描述。"""

    group: str = Field(..., description="配置组，如 Notify")
    name: str = Field(..., description="配置字段名")
    labelKey: str = Field(..., description="字段标签词表键")
    control: str = Field(
        ..., description="控件类型：bool/text/password/url/select/json"
    )
    options: List[NotifyChannelOptionOut] = Field(default=[], description="下拉选项")
    placeholderKey: str = Field(default="", description="占位文案词表键")
    tipKey: str = Field(default="", description="提示文案词表键")


class NotifyChannelOut(_SchemaModel):
    """一个通知渠道的展示元数据；服务无鉴权，负载不得出现任何配置值。"""

    key: str = Field(..., description="渠道标识")
    nameKey: str = Field(..., description="渠道名称词表键")
    descKey: str = Field(default="", description="渠道一句话说明词表键")
    icon: str = Field(default="", description="图标标识，policy 段为空串")
    group: str = Field(..., description="分组：builtin/custom")
    order: int = Field(..., description="排序值，与投递顺序一致")
    docUrl: Optional[str] = Field(default=None, description="使用文档链接")
    scopes: List[str] = Field(default=[], description="可用作用域：global/user")
    kind: str = Field(..., description="渲染类型：fields/custom/policy")
    customBlock: Optional[str] = Field(
        default=None, description="自定义块标识：claw:qq/webhook_list"
    )
    enableField: Optional[List[str]] = Field(
        default=None, description="启用开关的 [配置组, 字段名]"
    )
    summaryKey: Optional[str] = Field(default=None, description="卡片摘要词表键")
    summaryFields: List[str] = Field(
        default=[], description="参与摘要插值与空值判定的字段名"
    )
    fields: Dict[str, List[NotifyChannelFieldOut]] = Field(
        default={}, description="按作用域分组的字段列表"
    )


class NotifyChannelsOut(OutBase):
    """通知渠道描述表。"""

    channels: List[NotifyChannelOut] = Field(default=[], description="渠道描述列表")


class OpenClawQQQrStartOut(OutBase):
    """QQ 官方机器人二维码创建响应。"""

    sessionId: str = Field(default="", description="二维码登录会话 ID")
    qrUrl: str = Field(default="", description="用于生成二维码的登录链接")


class OpenClawQQQrCheckIn(_SchemaModel):
    """QQ 官方机器人二维码状态查询请求。"""

    sessionId: str = Field(..., min_length=1, description="二维码登录会话 ID")


class OpenClawQQQrCheckOut(OutBase):
    """QQ 官方机器人二维码及消息网关状态查询响应。"""

    sessionId: str = Field(default="", description="二维码登录会话 ID")
    state: str = Field(
        default="",
        description="轮询状态：waiting、scanned、connecting（已绑定，网关连接中）、connected（网关已就绪）、expired 或 error",
    )
    connected: bool = Field(
        default=False, description="消息网关是否已就绪；绑定成功但仍在连接时为 false"
    )


class OpenClawQQStatusOut(OutBase):
    """QQ 官方机器人通知绑定状态，不返回任何凭据。"""

    enabled: bool = Field(default=False, description="是否启用 QQ 官方机器人通知")
    connected: bool = Field(default=False, description="是否已绑定 QQ 官方机器人")
    state: str = Field(
        default="disconnected",
        description="消息网关状态：disconnected、connecting、connected 或 reconnecting",
    )


class GlobalConfig_Update(_SchemaModel):
    IfAutoUpdate: Optional[bool] = Field(default=None, description="是否自动更新")
    PauseUntil: Optional[str] = Field(
        default=None, description="暂停更新截止日期 YYYY-MM-DD，空字符串表示未暂停"
    )
    Source: Optional[Literal["GitHub", "MirrorChyan", "AutoSite", "CNB"]] = Field(
        default=None, description="更新源: GitHub源, Mirror酱源, 自建源, CNB 镜像源"
    )
    Channel: Optional[Literal["stable", "beta"]] = Field(
        default=None, description="更新渠道: 稳定版, 测试版"
    )
    ProxyAddress: Optional[str] = Field(default=None, description="网络代理地址")
    GitHubMirror: Optional[Literal["Auto", "Off"]] = Field(
        default=None,
        description=(
            "MFW 项目包从 GitHub Release 下载时的加速镜像: "
            "Auto 依次试镜像并在全部失败后回退直连, Off 只直连"
        ),
    )
    MirrorChyanCDK: Optional[str] = Field(default=None, description="Mirror酱CDK")


class GlobalConfig_ChildSession(_SchemaModel):
    Enabled: Optional[bool] = Field(
        default=None,
        description="是否启用基于 BetterGI 的本地远程桌面 (Child Session) 执行任务",
    )
    HostPort: Optional[int] = Field(
        default=None, ge=1024, le=65535, description="C# 远程桌面宿主 IPC 端口"
    )
    Resolution: Optional[str] = Field(
        default=None, description="远程桌面分辨率，形如 1920x1080"
    )
    StartHidden: Optional[bool] = Field(
        default=None, description="启动时是否隐藏远程桌面窗口"
    )
    WatchMode: Optional[bool] = Field(
        default=None, description="是否开启观看模式（屏蔽本机键鼠输入进入分身）"
    )


class HotkeyCaptureIn(_SchemaModel):
    action: Literal["begin", "end"]
    token: str = ""


class QueueControlIn(_SchemaModel):
    action: Literal["select", "pause", "continue"]
    queueId: str = ""
    taskId: str = ""
    token: str = ""


class GlobalConfig_Hotkey(_SchemaModel):
    Enabled: Optional[bool] = Field(default=None, description="是否启用全局热键")
    ToggleStartStop: Optional[str] = Field(
        default=None, description="全局热键：控制程序启停"
    )
    PreviousTask: Optional[str] = Field(
        default=None, description="全局热键：上一个任务"
    )
    NextTask: Optional[str] = Field(default=None, description="全局热键：下一个任务")


class GlobalConfig(_SchemaModel):
    Replay: Optional[GlobalConfig_Replay] = Field(
        default=None, description="OBS 失败回放配置"
    )
    Function: Optional[GlobalConfig_Function] = Field(
        default=None, description="功能相关配置"
    )
    Display: Optional[GlobalConfig_Display] = Field(
        default=None, description="显示器相关配置"
    )
    ChildSession: Optional[GlobalConfig_ChildSession] = Field(
        default=None, description="本地远程桌面 (Child Session) 配置"
    )
    Hotkey: Optional[GlobalConfig_Hotkey] = Field(
        default=None, description="全局热键配置"
    )
    Voice: Optional[GlobalConfig_Voice] = Field(
        default=None, description="语音相关配置"
    )
    Start: Optional[GlobalConfig_Start] = Field(
        default=None, description="启动相关配置"
    )
    UI: Optional[GlobalConfig_UI] = Field(default=None, description="界面相关配置")
    Notify: Optional[GlobalConfig_Notify] = Field(
        default=None, description="通知相关配置"
    )
    Update: Optional[GlobalConfig_Update] = Field(
        default=None, description="更新相关配置"
    )


class QueueIndexItem(_SchemaModel):
    uid: str = Field(..., description="唯一标识符")
    type: Literal["QueueConfig"] = Field(..., description="配置类型")


class QueueItemIndexItem(_SchemaModel):
    uid: str = Field(..., description="唯一标识符")
    type: Literal["QueueItem"] = Field(..., description="配置类型")


class TimeSetIndexItem(_SchemaModel):
    uid: str = Field(..., description="唯一标识符")
    type: Literal["TimeSet"] = Field(..., description="配置类型")


class QueueItem_Info(_SchemaModel):
    ScriptId: Optional[str] = Field(
        default=None, description="任务所对应的脚本ID, 为None时表示未选择"
    )


class QueueItem_Schedule(_SchemaModel):
    Enabled: Optional[bool] = Field(default=None, description="是否参与循环调度")
    Mode: Optional[Literal["fixed_time", "interval"]] = Field(
        default=None, description="循环调度模式, 固定时间或间隔"
    )
    Days: Optional[
        List[
            Literal[
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
        ]
    ] = Field(default=None, description="固定时间模式的执行周期, 可多选")
    Time: Optional[str] = Field(
        default=None, description="固定时间模式的执行时间, 格式为HH:MM"
    )
    IntervalMinutes: Optional[int] = Field(
        default=None, description="间隔模式的间隔分钟数"
    )
    IntervalAnchor: Optional[Literal["start", "finish"]] = Field(
        default=None, description="间隔模式的计时基准, 上次开始或上次结束"
    )
    NextRunAt: Optional[str] = Field(
        default=None, description="下次运行时间, 格式为YYYY-MM-DD HH:MM:SS"
    )


class QueueItem_Data(_SchemaModel):
    LastCycleStartedAt: Optional[str] = Field(
        default=None, description="上次循环开始时间"
    )
    LastCycleFinishedAt: Optional[str] = Field(
        default=None, description="上次循环结束时间"
    )


class QueueItem(_SchemaModel):
    Info: Optional[QueueItem_Info] = Field(default=None, description="队列项")
    Schedule: Optional[QueueItem_Schedule] = Field(
        default=None, description="队列项的循环调度配置"
    )
    Data: Optional[QueueItem_Data] = Field(
        default=None, description="队列项的循环运行数据"
    )


class TimeSet_Info(_SchemaModel):
    Enabled: Optional[bool] = Field(default=None, description="是否启用")
    Days: Optional[
        List[
            Literal[
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
        ]
    ] = Field(default=None, description="执行周期, 可多选")
    Time: Optional[str] = Field(default=None, description="时间设置, 格式为HH:MM")


class TimeSet(_SchemaModel):
    Info: Optional[TimeSet_Info] = Field(default=None, description="时间项")


class QueueConfig_Info(_SchemaModel):
    Name: Optional[str] = Field(default=None, description="队列名称")
    TimeEnabled: Optional[bool] = Field(default=None, description="是否启用定时")
    StartUpMode: Optional[Literal["Never", "Always", "DailyFirst"]] = Field(
        default=None, description="启动时运行模式"
    )
    CycleEnabled: Optional[bool] = Field(
        default=None, description="是否为循环队列, 与定时互斥"
    )
    AfterAccomplish: Optional[
        Literal[
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
    ] = Field(default=None, description="完成后操作")
    AfterAccomplishDelay: Optional[int] = Field(
        default=None, ge=0, le=1440, description="完成后操作的延时时长(分钟)"
    )
    IfScriptBeforeTask: Optional[bool] = Field(
        default=None, description="是否在队列运行前执行脚本"
    )
    ScriptBeforeTask: Optional[str] = Field(
        default=None, description="队列运行前脚本路径"
    )
    IfScriptAfterTask: Optional[bool] = Field(
        default=None, description="是否在队列运行后执行脚本"
    )
    ScriptAfterTask: Optional[str] = Field(
        default=None, description="队列运行后脚本路径"
    )


class QueueConfig(_SchemaModel):
    Info: Optional[QueueConfig_Info] = Field(default=None, description="队列信息")


class ScriptIndexItem(_SchemaModel):
    uid: str = Field(..., description="唯一标识符")
    type: Literal["GeneralConfig"] = Field(..., description="配置类型")

    activityGame: str | None = Field(
        default=None, description="对应的游戏活动标识，无游戏归属时为空"
    )


class UserIndexItem(_SchemaModel):
    uid: str = Field(..., description="唯一标识符")
    type: Literal["GeneralUserConfig"] = Field(..., description="配置类型")


class UserConfigInfoBase(_SchemaModel):
    """用户配置 Info 的公共基类：兼容旧请求的 ``Mode`` 来源字段。

    旧「脚本/用户/直控」来源已迁移为 ``Base``（shared/independent/native），
    存量调用方仍可能提交 ``Info.Mode``；在解析前归一，避免字段被静默丢弃、
    接口返回成功但来源实际未变。
    """

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_base(cls, data: Any) -> Any:
        if not isinstance(data, dict) or data.get("Base") is not None:
            return data
        base = normalize_base_source(data.get("Mode"))
        if not base:
            return data
        if base not in (BASE_SHARED, BASE_INDEPENDENT, BASE_NATIVE):
            raise ValueError(f"未知的配置来源: {data.get('Mode')!r}")
        return {**data, "Base": base}


class GeneralUserConfig_Notify(_SchemaModel):
    Enabled: Optional[bool] = Field(default=None, description="是否启用通知")
    IfSendStatistic: Optional[bool] = Field(
        default=None, description="是否发送统计信息"
    )
    IfSendMail: Optional[bool] = Field(default=None, description="是否发送邮件通知")
    ToAddress: Optional[str] = Field(default=None, description="邮件接收地址")
    IfServerChan: Optional[bool] = Field(
        default=None, description="是否使用Server酱推送"
    )
    ServerChanKey: Optional[str] = Field(default=None, description="ServerChanKey")


class GeneralUserConfig_Info(UserConfigInfoBase):
    Name: Optional[str] = Field(default=None, description="用户名")
    Status: Optional[bool] = Field(default=None, description="用户状态")
    RemainedDay: Optional[int] = Field(default=None, description="剩余天数")
    Base: Optional[Literal["shared", "independent", "native"]] = Field(
        default=None,
        description="base 来源（shared=共享、independent=独立、native=脚本原生配置）",
    )
    IfUseMasConfig: Optional[bool] = Field(
        default=None, description="兼容旧版用户独立配置开关"
    )
    IfScriptBeforeTask: Optional[bool] = Field(
        default=None, description="是否在任务前执行脚本"
    )
    ScriptBeforeTask: Optional[str] = Field(default=None, description="任务前脚本路径")
    IfScriptAfterTask: Optional[bool] = Field(
        default=None, description="是否在任务后执行脚本"
    )
    ScriptAfterTask: Optional[str] = Field(default=None, description="任务后脚本路径")
    Notes: Optional[str] = Field(default=None, description="备注")
    Tag: Optional[str] = Field(
        default=None, description="用户标签列表（JSON字符串，TagItem的dict列表）"
    )


class GeneralUserConfig_Data(_SchemaModel):
    LastProxyDate: Optional[str] = Field(default=None, description="上次代理日期")
    ProxyTimes: Optional[int] = Field(default=None, description="代理次数")


class GeneralUserConfig(_SchemaModel):
    Info: Optional[GeneralUserConfig_Info] = Field(default=None, description="用户信息")
    Data: Optional[GeneralUserConfig_Data] = Field(default=None, description="用户数据")
    Notify: Optional[GeneralUserConfig_Notify] = Field(
        default=None, description="单独通知"
    )


class GeneralConfig_Info(_SchemaModel):
    Name: Optional[str] = Field(default=None, description="脚本名称")
    RootPath: Optional[str] = Field(default=None, description="脚本根目录")


class GeneralOwnershipPromptData(_SchemaModel):
    requestId: str
    scriptId: str
    scriptName: str
    reason: str
    automated: bool = Field(description="定时运行已跳过，不等待选择")


class GeneralOwnershipPromptsOut(OutBase):
    data: list[GeneralOwnershipPromptData]


class GeneralOwnershipAnswerIn(_SchemaModel):
    requestId: str
    edit: bool = Field(description="是：跳过本次并修改；否：保留原配置")


class GeneralTaskKillData(_SchemaModel):
    Name: str = Field(min_length=1, description="精确匹配的进程名")
    Path: str = Field(min_length=1, description="精确匹配的可执行文件绝对路径")

    @model_validator(mode="after")
    def validate_target(self) -> "GeneralTaskKillData":
        path = PureWindowsPath(self.Path)
        if not path.is_absolute() or any(c in self.Path for c in '*?"'):
            raise ValueError("清理路径必须是无通配符的完整绝对路径")
        if path.name.casefold() != self.Name.casefold():
            raise ValueError("进程名必须与清理路径的文件名一致")
        return self


class GeneralRestartData(_SchemaModel):
    Path: str = Field(min_length=1, description="启动程序绝对路径")
    Arguments: str = Field(default="", description="启动参数")
    WorkingDirectory: str = Field(default="", description="工作目录，留空使用程序目录")
    WaitSeconds: int = Field(default=50, ge=0, le=9999, description="启动后等待秒数")
    IsMain: bool = Field(default=False, description="是否为脚本主体入口")

    @model_validator(mode="after")
    def validate_entry(self) -> "GeneralRestartData":
        for path in (self.Path, self.WorkingDirectory):
            if path and (
                not PureWindowsPath(path).is_absolute() or any(c in path for c in '*?"')
            ):
                raise ValueError("启动路径和工作目录必须为无通配符的绝对路径")
        if self.IsMain and self.WaitSeconds < 10:
            raise ValueError("脚本主体等待时间不能少于 10 秒")
        return self


class GeneralConfig_Script(_SchemaModel):
    TaskKill: Optional[list[GeneralTaskKillData]] = Field(
        default=None, description="自定义清理清单，留空沿用原清理"
    )
    TaskKillMode: Optional[Literal["Tracked", "Session", "Force"]] = Field(
        default=None, description="本轮进程、当前会话全部匹配、跨会话强力清理"
    )
    Restart: Optional[list[GeneralRestartData]] = Field(
        default=None, description="重试及补跑启动清单"
    )

    @field_validator("Restart")
    @classmethod
    def validate_restart(
        cls, value: list[GeneralRestartData] | None
    ) -> list[GeneralRestartData] | None:
        if value and sum(item.IsMain for item in value) != 1:
            raise ValueError("非空启动清单必须且只能标记一个脚本主体")
        return value

    ScriptPath: Optional[str] = Field(default=None, description="脚本可执行文件路径")
    Arguments: Optional[str] = Field(default=None, description="脚本启动附加命令参数")
    IfTrackProcess: Optional[bool] = Field(
        default=None, description="是否追踪脚本子进程"
    )
    TrackProcessName: Optional[str] = Field(default=None, description="追踪进程名称")
    TrackProcessExe: Optional[str] = Field(default=None, description="追踪进程文件路径")
    TrackProcessCmdline: Optional[str] = Field(
        default=None, description="追踪进程启动命令行参数"
    )
    ConfigPath: Optional[str] = Field(default=None, description="配置文件路径")
    ConfigPathMode: Optional[Literal["File", "Folder"]] = Field(
        default=None, description="配置文件类型: 单个文件, 文件夹"
    )
    UpdateConfigMode: Optional[Literal["Never", "Success", "Failure", "Always"]] = (
        Field(
            default=None,
            description="更新配置时机, 从不, 仅成功时, 仅失败时, 任务结束时",
        )
    )
    LogPath: Optional[str] = Field(default=None, description="日志文件路径")
    LogPathFormat: Optional[str] = Field(default=None, description="日志文件名格式")
    LogTimeStart: Optional[int] = Field(default=None, description="日志时间戳开始位置")
    LogTimeEnd: Optional[int] = Field(default=None, description="日志时间戳结束位置")
    LogTimeFormat: Optional[str] = Field(default=None, description="日志时间戳格式")
    LogHookEnabled: Optional[bool] = Field(
        default=None, description="日志预处理启用开关"
    )
    LogHookRules: Optional[str] = Field(
        default=None,
        description='日志预处理规则(JSON 数组，每项形如 {"type":"drop|replace","match":正则,"replace":替换文本})；先于任务日志、推送采集与成功/失败判定执行',
    )
    SuccessLog: Optional[str] = Field(default=None, description="成功时日志")
    SuccessLogMode: Optional[Literal["Split", "Regex"]] = Field(
        default=None, description="成功时日志匹配模式: 关键字子串包含, 正则表达式"
    )
    ErrorLog: Optional[str] = Field(default=None, description="错误时日志")
    ErrorLogMode: Optional[Literal["Split", "Regex"]] = Field(
        default=None, description="错误时日志匹配模式: 关键字子串包含, 正则表达式"
    )
    PushLogEnabled: Optional[bool] = Field(
        default=None, description="推送日志采集启用开关"
    )
    PushLogPatterns: Optional[str] = Field(
        default=None,
        description="推送日志高级模式匹配(JSON 数组，每项为 PushLogPattern 对象：type 为 split/regex/multiline，按类型使用对应字段)",
    )


class GeneralConfig_Game(_SchemaModel):
    Enabled: Optional[bool] = Field(
        default=None, description="游戏/模拟器相关功能是否启用"
    )
    Type: Optional[Literal["Emulator", "Client", "URL"]] = Field(
        default=None, description="类型: 模拟器, PC端, URL协议"
    )
    Path: Optional[str] = Field(default=None, description="游戏/模拟器程序路径")
    URL: Optional[str] = Field(default=None, description="自定义协议URL")
    ProcessName: Optional[str] = Field(default=None, description="游戏进程名称")
    Arguments: Optional[str] = Field(default=None, description="游戏/模拟器启动参数")
    WaitTime: Optional[int] = Field(default=None, description="游戏/模拟器等待启动时间")
    IfForceClose: Optional[bool] = Field(
        default=None, description="是否强制关闭游戏/模拟器进程"
    )
    EmulatorId: Optional[str] = Field(default=None, description="模拟器ID")
    EmulatorIndex: Optional[str] = Field(default=None, description="模拟器多开实例索引")


class GeneralConfig_Run(_SchemaModel):
    HardTimeLimit: Optional[int] = Field(
        default=None,
        ge=1,
        le=9999,
        description="单账号运行总时限（分钟），包含等待和全部重试",
    )
    ProxyTimesLimit: Optional[int] = Field(default=None, description="每日代理次数限制")
    RunTimesLimit: Optional[int] = Field(default=None, description="重试次数限制")
    RunTimeLimit: Optional[int] = Field(default=None, description="日志超时限制")


class GeneralConfig(_SchemaModel):
    Info: Optional[GeneralConfig_Info] = Field(default=None, description="脚本基础信息")
    Script: Optional[GeneralConfig_Script] = Field(default=None, description="脚本配置")
    Game: Optional[GeneralConfig_Game] = Field(default=None, description="游戏配置")
    Run: Optional[GeneralConfig_Run] = Field(default=None, description="运行配置")


class ReplayRecord(_SchemaModel):
    replayId: str = Field(..., description="回放唯一标识")
    taskId: str | None = Field(default=None, description="调度任务标识")
    scriptId: str | None = Field(default=None, description="脚本标识")
    userId: str | None = Field(default=None, description="账号标识")
    scriptName: str = Field(default="", description="脚本名称")
    userName: str = Field(default="", description="账号名称")
    failedAt: str = Field(..., description="失败时间")
    reason: str = Field(..., description="失败原因")
    filePath: str = Field(default="", description="MAS 保存的回放副本")
    historyPaths: list[str] = Field(
        default_factory=list, description="本轮关联历史记录"
    )


class ObsReplayCheckOut(OutBase):
    connected: bool = False
    replayActive: bool = False
    version: str = ""
    directory: str = ""


class ObsReplaySaveOut(OutBase):
    replay: ReplayRecord | None = None


class ReplayListOut(OutBase):
    replays: list[ReplayRecord] = Field(default_factory=list)
    directory: str = ""


class HistoryIndexItem(_SchemaModel):
    date: str = Field(..., description="日期")
    status: Literal["DONE", "SKIP", "ERROR"] = Field(
        ..., description="状态: DONE 完成, SKIP 跳过(如停服维护), ERROR 失败"
    )
    jsonFile: str = Field(..., description="对应JSON文件")
    result: Optional[str] = Field(
        default=None, description="运行结果文本，可能带运行阶段前缀"
    )


class PullCountStatistics(_SchemaModel):
    resource_pulls: int = Field(..., description="资源折算抽数")
    carry_over_pulls: int = Field(..., description="可留到下版本的凭证抽数")
    next_pool_shop_pulls: int = Field(..., description="下版本商店抽数")
    next_pool_signin_pulls: int = Field(..., description="下版本签到抽数")
    current_pool_total: int = Field(..., description="当前卡池可用抽数")
    next_pool_total: int = Field(..., description="下版本卡池预计总抽数")


class HistoryData(_SchemaModel):
    replays: list[ReplayRecord] = Field(
        default_factory=list, description="本轮失败回放"
    )
    index: Optional[List[HistoryIndexItem]] = Field(
        default=None, description="历史记录索引列表"
    )
    recruit_statistics: Optional[Dict[str, int]] = Field(
        default=None, description="公招统计数据, key为星级, value为对应的公招数量"
    )
    drop_statistics: Optional[Dict[str, Dict[str, int]]] = Field(
        default=None,
        description="掉落统计数据, 格式为 { '关卡号': { '掉落物': 数量 } }",
    )
    matrix_statistics: Optional[Dict[str, str]] = Field(
        default=None, description="基质统计数据, key为技能组合, value为符合武器名称"
    )
    pull_count_statistics: Optional[PullCountStatistics] = Field(
        default=None, description="MaaEnd 抽数计算统计"
    )
    error_info: Optional[Dict[str, str]] = Field(
        default=None, description="报错信息, key为时间戳, value为错误描述"
    )
    log_content: Optional[str] = Field(
        default=None, description="日志内容, 仅在提取单条历史记录数据时返回"
    )


class ScriptCreateIn(_SchemaModel):
    type: Literal["General"] = Field(..., description="脚本类型: 仅支持通用脚本")
    scriptId: str | None = Field(
        default=None, description="直接从该脚本ID复制创建, 仅在复制创建时使用"
    )


class ScriptCreateOut(OutBase):
    scriptId: str = Field(..., description="新创建的脚本ID")
    data: GeneralConfig = Field(..., description="脚本配置数据")


class ScriptGetIn(_SchemaModel):
    scriptId: Optional[str] = Field(
        default=None, description="脚本ID, 未携带时表示获取所有脚本数据"
    )

    includeUsers: bool = Field(default=False, description="同时返回各脚本的用户列表")


class ScriptGetOut(OutBase):
    index: List[ScriptIndexItem] = Field(..., description="脚本索引列表")
    data: Dict[
        str,
        GeneralConfig,
    ] = Field(..., description="脚本数据字典, key来自于index列表的uid")
    users: Optional[Dict[str, "UserGetOut"]] = Field(
        default=None, description="用户列表，key 为脚本 ID，仅按需返回"
    )


class ScriptUpdateIn(_SchemaModel):
    scriptId: str = Field(..., description="脚本ID")
    data: GeneralConfig = Field(..., description="脚本更新数据")


class ScriptDeleteIn(_SchemaModel):
    scriptId: str = Field(..., description="脚本ID")


class ScriptReorderIn(_SchemaModel):
    indexList: List[str] = Field(..., description="脚本ID列表, 按新顺序排列")


class ShareTemplateListIn(_SchemaModel):
    page: int = Field(default=1, ge=1, description="页码, 从 1 开始")
    pageSize: int = Field(default=20, ge=1, le=100, description="每页条数")
    keyword: Optional[str] = Field(default=None, description="搜索关键字")


class ShareTemplateItem(_SchemaModel):
    projectKey: str = Field(..., description="配置中心项目标识")
    categoryKey: str = Field(..., description="配置中心分类标识")
    configKey: str = Field(..., description="配置中心配置标识")
    displayName: str = Field(..., description="配置名称")
    description: str = Field(default="", description="配置描述")
    ownerUsername: str = Field(default="", description="分享者用户名")
    publishedVersionNo: Optional[int] = Field(
        default=None, description="已发布的版本号"
    )
    publishedAt: str = Field(default="", description="发布时间")
    updatedAt: str = Field(default="", description="更新时间")


class ShareTemplateListOut(OutBase):
    items: List[ShareTemplateItem] = Field(
        default_factory=list, description="配置模板列表"
    )
    page: int = Field(default=1, description="当前页码")
    pageSize: int = Field(default=20, description="每页条数")
    total: int = Field(default=0, description="模板总数")
    hasNext: bool = Field(default=False, description="是否还有下一页")


class ScriptShareInspectIn(_SchemaModel):
    scriptId: str = Field(..., description="脚本ID")
    config_name: str = Field(..., min_length=1, max_length=64, description="配置名称")


class ScriptTemplateImportIn(_SchemaModel):
    scriptId: str = Field(..., description="脚本ID")
    configKey: str = Field(..., description="配置中心配置标识")
    versionNo: Optional[int] = Field(
        default=None, ge=1, description="版本号, 为空表示已发布的最新版本"
    )


class ScriptUploadIn(_SchemaModel):
    scriptId: str = Field(..., description="脚本ID")
    config_name: str = Field(..., min_length=1, max_length=64, description="配置名称")
    description: str = Field(..., min_length=1, max_length=500, description="描述")
    acknowledged: bool = Field(
        default=False, description="是否已确认分享前检查出的隐私风险项"
    )


class ShareRiskItem(_SchemaModel):
    field: str = Field(..., description="存在风险的配置项")
    reason: str = Field(..., description="风险说明")


class ShareInspectOut(OutBase):
    risks: List[ShareRiskItem] = Field(
        default_factory=list, description="分享前检查出的隐私风险项"
    )


class ShareAuthStatusOut(OutBase):
    authStatus: Literal["idle", "pending", "authorized", "denied", "expired"] = Field(
        ..., description="配置中心授权状态"
    )
    username: str = Field(default="", description="已授权用户的用户名")
    displayName: str = Field(default="", description="已授权用户的显示名")
    userCode: str = Field(default="", description="待用户在浏览器确认的短授权码")
    verificationUri: str = Field(default="", description="浏览器授权页地址")
    expiresIn: int = Field(default=0, description="剩余有效秒数")
    interval: int = Field(default=5, description="建议的轮询间隔秒数")


class ShareAppearanceCategoryIn(_SchemaModel):
    categoryKey: Literal["theme", "mascot"] = Field(
        default="theme", description="资源分类: theme 主题, mascot 独立桌宠"
    )


class ShareAppearanceUploadIn(ShareAppearanceCategoryIn):
    zipPath: str = Field(..., description="本地外观 ZIP 路径")
    displayName: str = Field(
        default="", max_length=60, description="外观名称, 只在新建时使用"
    )
    description: str = Field(default="", max_length=2000, description="外观描述")
    changeNote: str = Field(default="", max_length=500, description="变更说明")
    fileId: Optional[int] = Field(
        default=None, description="已上传文件的 ID, 非空表示给该文件发新版本"
    )
    coverPath: Optional[str] = Field(
        default=None,
        description="封面图片路径, coverMode 为 custom 时使用",
    )
    coverMode: Optional[Literal["package", "custom", "inherit"]] = Field(
        default=None,
        description="封面来源: package 用外观包的 preview, custom 用 coverPath, inherit 沿用分享站上的封面 (只能用于新版本); 为空时有 coverPath 按 custom, 否则按 package",
    )

    @field_validator("displayName", mode="before")
    @classmethod
    def strip_display_name(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def check_target(self) -> "ShareAppearanceUploadIn":
        if self.fileId is None and not self.displayName:
            raise ValueError("新建外观时名称不能为空")
        if self.coverMode == "inherit" and self.fileId is None:
            raise ValueError("只有发新版本时才能沿用分享站上的封面")
        if self.coverMode == "custom" and not self.coverPath:
            raise ValueError("请选择封面图片")
        return self


class ShareAppearanceUploadOut(OutBase):
    fileId: int = Field(default=0, description="分享站文件 ID")
    fileKey: str = Field(default="", description="分享站文件标识")
    versionNo: int = Field(default=0, description="本次上传的版本号")
    reviewStatus: Literal["pending", "approved"] = Field(
        default="pending", description="审核状态, 管理员上传自动通过"
    )
    isNewFile: bool = Field(default=False, description="是否新建了文件")
    appearanceId: str = Field(default="", description="外观 ID")
    reason: Optional[
        Literal["pendingLimit", "conflict", "tooLarge", "categoryMismatch"]
    ] = Field(
        default=None,
        description="上传拒绝的类别: pendingLimit 待审核数超限, conflict 名称被占用或内容未变, tooLarge 超过体积上限, categoryMismatch 更新目标与分类不符",
    )


class ShareAppearanceUploadItem(_SchemaModel):
    appearanceId: str = Field(..., description="外观 ID")
    fileId: int = Field(..., description="分享站文件 ID")
    fileKey: str = Field(default="", description="分享站文件标识")
    displayName: str = Field(default="", description="外观名称")
    updatedAt: str = Field(default="", description="最近一次上传时间")


class ShareAppearanceUploadsOut(OutBase):
    data: List[ShareAppearanceUploadItem] = Field(
        default_factory=list, description="当前登录账号的外观上传记录"
    )


class ShareAppearanceMineItem(_SchemaModel):
    fileId: int = Field(..., description="分享站文件 ID")
    fileKey: str = Field(default="", description="分享站文件标识")
    displayName: str = Field(default="", description="外观名称")
    description: str = Field(default="", description="外观描述")
    status: str = Field(default="", description="文件状态")
    publishedVersionNo: Optional[int] = Field(
        default=None, description="已发布的版本号, 没有已发布版本时为空"
    )
    latestVersionNo: int = Field(default=0, description="最新版本号")
    latestReviewStatus: Optional[Literal["pending", "approved", "rejected"]] = Field(
        default=None, description="最新版本的审核状态"
    )
    latestReviewComment: str = Field(
        default="", description="最新版本的审核意见, 没有则为空"
    )
    latestHasCover: bool = Field(default=False, description="最新版本是否带封面")
    updatedAt: str = Field(default="", description="最近更新时间")


class ShareAppearanceMineOut(OutBase):
    data: List[ShareAppearanceMineItem] = Field(
        default_factory=list, description="当前账号在分享站上的全部外观"
    )


class ShareAppearanceCoverIn(_SchemaModel):
    fileId: int = Field(..., description="分享站文件 ID")
    versionNo: Optional[int] = Field(
        default=None,
        ge=1,
        description="版本号, 为空表示最新版本; inheritable 为真时忽略",
    )
    inheritable: bool = Field(
        default=False,
        description="为真时取发新版本不带封面时分享站会沿用的那张: 最近一个未被驳回且带封面的版本",
    )


class ShareAppearanceCoverOut(OutBase):
    dataUrl: str = Field(default="", description="封面图片的 data URL")
    versionNo: Optional[int] = Field(
        default=None, description="封面所在的版本号, 取最新版本时为空"
    )


class ShareAppearanceDescriptionIn(_SchemaModel):
    fileId: int = Field(..., description="分享站文件 ID")
    description: str = Field(..., max_length=2000, description="新的外观描述")


class ShareAppearanceDescriptionOut(OutBase):
    data: Optional[ShareAppearanceMineItem] = Field(
        default=None, description="更新后的外观"
    )


class UserInBase(_SchemaModel):
    scriptId: str = Field(..., description="所属脚本ID")


class ScriptConfigImportIn(UserInBase):
    userId: Optional[str] = Field(
        default=None, description="用户ID, 未携带时导入到脚本级配置文件"
    )


class UserConfigDirIn(UserInBase):
    userId: str = Field(..., description="用户ID")


class UserConfigDirOut(OutBase):
    path: Optional[str] = Field(default=None, description="用户配置目录绝对路径")


class UserGetIn(UserInBase):
    userId: Optional[str] = Field(
        default=None, description="用户ID, 未携带时表示获取所有用户数据"
    )


class UserGetOut(OutBase):
    index: List[UserIndexItem] = Field(..., description="用户索引列表")
    data: Dict[
        str,
        GeneralUserConfig,
    ] = Field(..., description="用户数据字典, key来自于index列表的uid")


class UserCreateOut(OutBase):
    userId: str = Field(..., description="新创建的用户ID")
    data: GeneralUserConfig = Field(..., description="用户配置数据")


class UserUpdateIn(UserInBase):
    userId: str = Field(..., description="用户ID")
    data: GeneralUserConfig = Field(..., description="用户更新数据")


class UserDeleteIn(UserInBase):
    userId: str = Field(..., description="用户ID")


class UserReorderIn(UserInBase):
    indexList: List[str] = Field(..., description="用户ID列表, 按新顺序排列")


class UserSetIn(UserInBase):
    userId: str = Field(..., description="用户ID")
    jsonFile: str = Field(..., description="JSON文件路径, 用于导入自定义基建文件")


class EmulatorGetIn(_SchemaModel):
    emulatorId: Optional[str] = Field(
        default=None, description="模拟器ID, 未携带时表示获取所有模拟器数据"
    )


class EmulatorGetOut(OutBase):
    index: List[EmulatorConfigIndexItem] = Field(..., description="模拟器索引列表")
    data: Dict[str, EmulatorConfig] = Field(
        ..., description="模拟器数据字典, key来自于index列表的uid"
    )


class EmulatorCreateOut(OutBase):
    emulatorId: str = Field(..., description="新创建的模拟器 ID")
    data: EmulatorConfig = Field(..., description="模拟器配置数据")


class EmulatorUpdateIn(_SchemaModel):
    emulatorId: str = Field(..., description="模拟器 ID")
    data: EmulatorConfig = Field(..., description="模拟器更新数据")


class EmulatorDeleteIn(_SchemaModel):
    emulatorId: str = Field(..., description="模拟器 ID")


class EmulatorOperateIn(_SchemaModel):
    emulatorId: str = Field(..., description="模拟器 ID")
    operate: Literal["open", "close", "show", "hide"] = Field(
        ..., description="操作类型"
    )
    index: str = Field(..., description="模拟器索引")


class DeviceStatus(_SchemaModel):
    """设备状态枚举"""

    ONLINE: int = Field(default=0, description="设备在线")
    OFFLINE: int = Field(default=1, description="设备离线")
    STARTING: int = Field(default=2, description="设备开启中")
    CLOSEING: int = Field(default=3, description="设备关闭中")
    ERROR: int = Field(default=4, description="错误")
    NOT_FOUND: int = Field(default=5, description="未找到设备")
    UNKNOWN: int = Field(default=10, description="未知状态")


class DeviceInfo(_SchemaModel):
    """设备信息"""

    title: str = Field(..., description="设备标题/名称")
    status: int = Field(..., description="设备状态, 参考DeviceStatus枚举值")
    adb_address: str = Field(..., description="ADB连接地址")


class EmulatorStatusOut(OutBase):
    data: Dict[str, Dict[str, DeviceInfo]] = Field(
        ...,
        description="模拟器状态信息, 外层key为模拟器ID, 内层key为设备索引, value为设备信息",
    )


class EmulatorSearchResult(_SchemaModel):
    type: str = Field(..., description="模拟器类型")
    path: str = Field(..., description="模拟器路径")
    name: str = Field(..., description="模拟器名称")


class EmulatorSearchOut(OutBase):
    emulators: List[EmulatorSearchResult] = Field(
        default_factory=list, description="搜索到的模拟器列表"
    )


# ---- Emulator 2.0 ----------------------------------------------------------
# 一条配置纳管多条模拟器路径, 实例合并成一张设备表。设备号由本配置统一编排,
# 脚本绑定用的就是它; 模拟器自己的实例索引另外给出, 两者不一定对得上。


class Emulator2SearchIn(_SchemaModel):
    emulatorId: Optional[str] = Field(
        default=None, description="配置ID, 携带时会标出已添加过的路径"
    )


class Emulator2SearchItem(_SchemaModel):
    type: str = Field(..., description="模拟器类型")
    version: str = Field(default="", description="探测到的版本号")
    installPath: str = Field(..., description="安装目录")
    alias: str = Field(default="", description="安装别名, 默认取目录名")
    supported: bool = Field(..., description="能否加入 Emulator 2.0")
    reason: str = Field(
        ...,
        description=(
            "判定原因: ok 可添加 / version_too_old 版本太旧 / planned 后续版本接入 / "
            "unsupported 暂不支持 / already_added 已添加 / "
            "not_found 找不到模拟器程序 / probe_failed 版本认不出 / "
            "components_missing 魔改 AVD 根目录里组件不全 (要用完整的模拟器内测包) / "
            "test_package_required 根目录里的模拟器不是魔改 AVD 内测包里的自编版 / "
            "test_package_outdated 魔改 AVD 内测包编号太旧或读不到, 要换新包"
        ),
    )
    instanceCount: Optional[int] = Field(default=None, description="实例数量")


class Emulator2SearchOut(OutBase):
    emulators: List[Emulator2SearchItem] = Field(
        default_factory=list, description="搜索结果, 不可添加的也会列出并说明原因"
    )


class Emulator2DevicesIn(_SchemaModel):
    emulatorId: str = Field(..., description="配置ID")
    withSettings: bool = Field(
        default=True,
        description="是否连四项设置与稳定模式一起读; 状态轮询传 false, 只取在线状态与 ADB 地址",
    )


class Emulator2PathAddIn(_SchemaModel):
    emulatorId: str = Field(..., description="配置ID")
    installPath: str = Field(..., description="模拟器安装目录")
    alias: Optional[str] = Field(default=None, description="安装别名")


class Emulator2SlotAssignment(_SchemaModel):
    slot: str = Field(..., description="设备号")
    nativeIndex: str = Field(..., description="模拟器自己的实例索引")


class Emulator2PathAddOut(OutBase):
    ok: bool = Field(default=False, description="是否添加成功")
    reason: str = Field(default="", description="失败原因枚举, 与搜索结果同一套")
    pathId: str = Field(default="", description="路径标识, 由安装目录派生")
    alias: str = Field(default="", description="安装别名")
    type: str = Field(default="", description="模拟器类型")
    version: str = Field(default="", description="探测到的版本号")
    assignedSlots: List[Emulator2SlotAssignment] = Field(
        default_factory=list, description="本次新分配的设备号"
    )
    revivedSlots: List[str] = Field(
        default_factory=list, description="重新添加同一路径时沿用的原设备号"
    )


class Emulator2PathRemoveIn(_SchemaModel):
    emulatorId: str = Field(..., description="配置ID")
    pathId: str = Field(..., description="路径标识")


class Emulator2AffectedScript(_SchemaModel):
    scriptId: str = Field(..., description="脚本ID")
    name: str = Field(..., description="脚本名称")
    slot: str = Field(..., description="绑定的设备号")
    running: bool = Field(default=False, description="是否正在运行")


class Emulator2PathRemovePreviewOut(OutBase):
    slots: List[str] = Field(default_factory=list, description="将会失效的设备号")
    affectedScripts: List[Emulator2AffectedScript] = Field(
        default_factory=list, description="受影响的脚本"
    )


class Emulator2PathRemoveOut(OutBase):
    ok: bool = Field(default=False, description="是否移除成功")
    tombstonedSlots: List[str] = Field(
        default_factory=list,
        description="已失效并保留的设备号, 不会再分配给其他设备",
    )
    affectedScripts: List[Emulator2AffectedScript] = Field(
        default_factory=list, description="受影响的脚本"
    )


class Emulator2InstanceCreateIn(_SchemaModel):
    emulatorId: str = Field(..., description="配置ID")
    pathId: str = Field(..., description="在哪条模拟器安装下新建")
    name: Optional[str] = Field(
        default=None, description="新实例名称, 留空由模拟器自己命名"
    )
    memoryMb: Optional[int] = Field(
        default=None,
        description="仅魔改 AVD: 内存 MB, 可选 3072 / 4096 / 5120 / 6144; 留空为 6144",
    )
    cpu: Optional[int] = Field(
        default=None, description="仅魔改 AVD: CPU 核数, 可选 2 / 4 / 6, 留空为 6"
    )
    fps: Optional[int] = Field(
        default=None,
        description="仅魔改 AVD: 帧率 (hw.lcd.vsync), 可选 30 / 60, 留空为 60",
    )
    dataPartitionGb: Optional[int] = Field(
        default=None,
        description="仅魔改 AVD: 数据盘上限 GB (16–512), 按实际写入增长, 留空为 64",
    )


class Emulator2InstanceCreateOut(OutBase):
    ok: bool = Field(default=False, description="是否新建成功")
    reason: str = Field(default="", description="失败原因枚举")
    slot: str = Field(default="", description="新实例分到的设备号")
    nativeIndex: str = Field(default="", description="模拟器自己的实例索引")


class Emulator2InstanceDeleteIn(_SchemaModel):
    emulatorId: str = Field(..., description="配置ID")
    slot: str = Field(..., description="要删除的设备号")


class Emulator2StoreOpenIn(_SchemaModel):
    emulatorId: str = Field(..., description="配置ID")
    slot: str = Field(..., description="要打开游戏中心的设备号")


class Emulator2StoreOpenOut(OutBase):
    ok: bool = Field(default=False, description="游戏中心是否已在前台")
    reason: str = Field(
        default="",
        description=(
            "结局原因码: launched / already-running / no-store / not-installed"
            " / no-adb / boot-timeout / launch-timeout"
        ),
    )


class Emulator2InstanceDeletePreviewOut(OutBase):
    ok: bool = Field(default=False, description="设备号是否有效")
    reason: str = Field(default="", description="失败原因枚举")
    affectedScripts: List[Emulator2AffectedScript] = Field(
        default_factory=list, description="绑定了该设备号的脚本"
    )


class Emulator2InstanceDeleteOut(OutBase):
    ok: bool = Field(default=False, description="是否删除成功")
    reason: str = Field(default="", description="失败原因枚举")


class Emulator2SettingField(_SchemaModel):
    """一个设置项的值和它的来历。

    ``state`` 必须四态分开：``.config`` 里没有 ``cpuCount`` 的实例照样跑在雷电默认的
    6 核上，把「默认值」显示成「已保存」就是在声称用户设过一个他没设过的值。
    """

    value: Optional[int] = Field(default=None, description="当前值, 未设置时为 null")
    state: str = Field(
        default="unset",
        description="saved 用户保存过 / default 模拟器默认 / unset 未设置 / unreadable 读不出",
    )


class Emulator2SettingsApplyIn(_SchemaModel):
    emulatorId: str = Field(..., description="模拟器配置ID")
    slot: str = Field(..., description="设备号")
    changes: Dict[str, int] = Field(
        ..., description="要写入的字段; 只提交用户改过的, 其余键原样保留"
    )
    expected: Dict[str, Optional[int]] = Field(
        default_factory=dict,
        description="表单打开时看到的值; 对不上说明文件被改过, 拒绝覆盖",
    )


class Emulator2SettingsApplyOut(OutBase):
    ok: bool = Field(default=False, description="是否写入成功")
    conflicts: List[str] = Field(
        default_factory=list, description="编辑期间被改动的字段名"
    )
    applied: Dict[str, int] = Field(default_factory=dict, description="真正落盘的字段")


class Emulator2GuardCaptureOut(OutBase):
    slots: List[str] = Field(default_factory=list, description="记下基准的设备号")
    count: int = Field(default=0, description="记下基准的设备台数")


class Emulator2StableModeIn(_SchemaModel):
    emulatorId: str = Field(..., description="模拟器配置ID")
    slots: List[str] = Field(
        default_factory=list, description="要处理的设备号; 留空表示全部"
    )


class Emulator2SettingsApplyAllIn(_SchemaModel):
    emulatorId: str = Field(..., description="模拟器配置ID")
    changes: Dict[str, int] = Field(..., description="要写到全部实例上的字段")


class Emulator2BatchResult(_SchemaModel):
    slot: str = Field(..., description="设备号")
    ok: bool = Field(default=False, description="该设备是否写入成功")
    message: str = Field(default="", description="失败原因")


class Emulator2SettingsApplyAllOut(OutBase):
    results: List[Emulator2BatchResult] = Field(
        default_factory=list, description="逐台结果"
    )
    okCount: int = Field(default=0, description="成功台数")
    failCount: int = Field(default=0, description="失败台数")


class Emulator2PathItem(_SchemaModel):
    pathId: str = Field(..., description="路径标识")
    installPath: str = Field(..., description="安装目录")
    alias: str = Field(default="", description="安装别名")
    type: str = Field(default="", description="模拟器类型")
    version: str = Field(default="", description="版本号")
    slots: List[str] = Field(default_factory=list, description="该路径占用的设备号")


class Emulator2DeviceItem(_SchemaModel):
    slot: str = Field(..., description="设备号, 脚本绑定用它")
    pathId: str = Field(..., description="所属路径标识")
    alias: str = Field(default="", description="所属安装的别名")
    realType: str = Field(
        default="", description="设备的真实模拟器类型, 不是配置的类型"
    )
    nativeIndex: str = Field(..., description="模拟器自己的实例索引")
    availability: str = Field(
        default="ok",
        description="ok 正常 / missing 这次没枚举到 / unavailable 该安装暂时不可达",
    )
    title: str = Field(default="", description="实例名称")
    status: int = Field(default=5, description="设备状态码")
    adbAddress: str = Field(default="", description="ADB 地址")
    settings: Dict[str, Emulator2SettingField] = Field(
        default_factory=dict,
        description="已保存设置, 下次启动使用; 不是运行中实例的当前配置",
    )
    stableMode: bool = Field(
        default=False, description="稳定模式是否已生效(所有干扰项都处在安全状态)"
    )
    stableUnsafe: List[str] = Field(
        default_factory=list, description="还没进入安全状态的项"
    )


class Emulator2DevicesOut(OutBase):
    paths: List[Emulator2PathItem] = Field(
        default_factory=list, description="已纳管的模拟器路径"
    )
    devices: List[Emulator2DeviceItem] = Field(
        default_factory=list, description="合并后的设备列表"
    )


# ---- Emulator 2.0 · 魔改 AVD（Android Emulator / AVD）---------------------
# 没有厂商管理器: 用户选一个根目录 (解压好的模拟器内测包, 组件全部自带, MAS 不下载),
# 组件齐了按普通路径 ``/paths/add`` 纳管 (installPath = 根目录)。


class Emulator2AvdRootIn(_SchemaModel):
    root: str = Field(..., description="魔改 AVD 根目录 (解压好的模拟器内测包)")


class Emulator2AvdStatusIn(Emulator2AvdRootIn):
    refresh: bool = Field(
        default=False,
        description="跳过硬件加速与 Vulkan 检查的缓存重新查; 用户点「检查」时传 true",
    )


class Emulator2AvdComponentItem(_SchemaModel):
    id: str = Field(
        ...,
        description="组件标识: platform-tools / emulator / system-image / launcher",
    )
    name: str = Field(..., description="组件名称")
    version: str = Field(default="", description="装着的版本; 没装为空")
    installed: bool = Field(default=False, description="是否已就绪")
    optional: bool = Field(
        default=False, description="是否可选组件 (轻量桌面), 可选组件缺失不影响添加"
    )
    localSdk: bool = Field(
        default=False,
        description="是否取自 mas-avd.json 的 sdkRoot 指定的本地 SDK",
    )
    testPackage: bool = Field(
        default=False,
        description="仅 Android 模拟器: 根目录里是魔改 AVD 内测包的自编版, 已就绪",
    )
    needsTestPackage: bool = Field(
        default=False,
        description="仅 Android 模拟器: 根目录里没有模拟器、不是自编版或内测包太旧",
    )
    build: Optional[str] = Field(
        default=None,
        description="仅 Android 模拟器: 内测包编号 (source.properties 的 Pkg.BuildId, 如 mas-19); 不是自编版或读不到为 null",
    )
    outdatedTestPackage: bool = Field(
        default=False,
        description="仅 Android 模拟器: 是自编版, 但内测包编号低于最低要求或读不到, 要换新包",
    )


class Emulator2AvdPrecheckItem(_SchemaModel):
    """魔改 AVD 开机前电脑检查的一项。拦截项不满足时开机直接被拒绝, 原因同 reason + advice。"""

    id: str = Field(
        ...,
        description="检查项: path / components / emulator / acceleration / vulkan / disk / memory",
    )
    title: str = Field(..., description="检查项名称")
    ok: Optional[bool] = Field(
        default=None, description="是否满足; null 表示现在查不了 (如模拟器组件还没装)"
    )
    blocking: bool = Field(
        default=True, description="不满足时是否拒绝开机; 显卡 Vulkan 只提示不拦截"
    )
    reason: str = Field(default="", description="检查结果或不满足的原因")
    advice: str = Field(default="", description="不满足时给用户的处理建议")


class Emulator2AvdStatusOut(OutBase):
    root: str = Field(default="", description="根目录")
    ready: bool = Field(default=False, description="必需组件是否齐全, 齐了才能添加")
    components: List[Emulator2AvdComponentItem] = Field(
        default_factory=list, description="组件清单"
    )
    missing: List[str] = Field(
        default_factory=list,
        description="缺着的必需组件名称 (含不合格的模拟器); 要用完整的模拟器内测包",
    )
    accelerationOk: Optional[bool] = Field(
        default=None, description="硬件加速 (WHPX) 是否可用; null 表示还查不了"
    )
    accelerationDetail: str = Field(
        default="", description="硬件加速检查结果或不可用的原因与建议"
    )
    prechecks: List[Emulator2AvdPrecheckItem] = Field(
        default_factory=list,
        description=(
            "开机前电脑检查: 目录路径、组件、模拟器版本、硬件虚拟化、显卡 Vulkan、磁盘、内存 (内存按默认档实例估), "
            "每项给 ok、原因、建议"
        ),
    )


class Emulator2AvdInstanceIn(_SchemaModel):
    emulatorId: str = Field(..., description="Emulator 2.0 配置 ID")
    slot: str = Field(..., description="设备号")


class Emulator2AvdInstanceOptionsOut(OutBase):
    memoryMb: Optional[int] = Field(
        default=None, description="内存 MB, 每次开机用 -memory 传"
    )
    cpu: Optional[int] = Field(default=None, description="CPU 核数")
    fps: Optional[int] = Field(
        default=None, description="帧率 (hw.lcd.vsync), 下次开机生效"
    )
    dataPartitionGb: Optional[int] = Field(default=None, description="数据盘上限 GB")
    initialized: bool = Field(
        default=False, description="首次开机初始化是否已完成 (去预装 / 装轻量桌面等)"
    )
    launcher: str = Field(default="", description="当前桌面包名, pixel 为原生桌面")
    renderer: str = Field(default="", description="首次开机记录的渲染器 (GLES 行)")
    softwareRenderer: bool = Field(
        default=False,
        description="是否在用软件渲染 (SwiftShader); 为 true 时应提示用户更新显卡驱动",
    )
    consolePort: int = Field(default=0, description="控制台端口")
    adbPort: int = Field(default=0, description="adb 端口")
    grpcPort: int = Field(default=0, description="gRPC 端口 (带 token 鉴权)")


class Emulator2AvdApkInstallIn(_SchemaModel):
    emulatorId: str = Field(..., description="Emulator 2.0 配置 ID")
    slot: str = Field(..., description="设备号, 实例必须已开机")
    apkPath: str = Field(
        ..., description="本机 .apk 文件的完整路径; .xapk / 拆分安装包不支持"
    )


class Emulator2AvdApkInstallOut(OutBase):
    ok: bool = Field(default=False, description="是否安装成功")
    reason: str = Field(default="", description="ok 安装成功")
    result: str = Field(default="", description="adb install 的结果行 (Success)")


class WebhookInBase(_SchemaModel):
    scriptId: Optional[str] = Field(
        default=None, description="所属脚本ID, 获取全局设置的Webhook数据时无需携带"
    )
    userId: Optional[str] = Field(
        default=None, description="所属用户ID, 获取全局设置的Webhook数据时无需携带"
    )


class WebhookGetIn(WebhookInBase):
    webhookId: Optional[str] = Field(
        default=None, description="Webhook ID, 未携带时表示获取所有Webhook数据"
    )


class WebhookGetOut(OutBase):
    index: List[WebhookIndexItem] = Field(..., description="Webhook索引列表")
    data: Dict[str, Webhook] = Field(
        ..., description="Webhook数据字典, key来自于index列表的uid"
    )


class WebhookCreateOut(OutBase):
    webhookId: str = Field(..., description="新创建的Webhook ID")
    data: Webhook = Field(..., description="Webhook配置数据")


class WebhookUpdateIn(WebhookInBase):
    webhookId: str = Field(..., description="Webhook ID")
    data: Webhook = Field(..., description="Webhook更新数据")


class WebhookDeleteIn(WebhookInBase):
    webhookId: str = Field(..., description="Webhook ID")


class WebhookTestIn(WebhookInBase):
    data: Webhook = Field(..., description="Webhook配置数据")


class QueueCreateOut(OutBase):
    queueId: str = Field(..., description="新创建的队列ID")
    data: QueueConfig = Field(..., description="队列配置数据")


# 队列首屏立即使用，提前构建请求与响应，避免首次进入页面时额外等待。
class QueueGetIn(BaseModel):
    queueId: Optional[str] = Field(
        default=None, description="队列ID, 未携带时表示获取所有队列数据"
    )


class QueueGetOut(OutBase):
    model_config = ConfigDict(defer_build=False)

    index: List[QueueIndexItem] = Field(..., description="队列索引列表")
    data: Dict[str, QueueConfig] = Field(
        ..., description="队列数据字典, key来自于index列表的uid"
    )


class QueueUpdateIn(_SchemaModel):
    queueId: str = Field(..., description="队列ID")
    data: QueueConfig = Field(..., description="队列更新数据")


class QueueDeleteIn(_SchemaModel):
    queueId: str = Field(..., description="队列ID")


class QueueSetInBase(_SchemaModel):
    queueId: str = Field(..., description="所属队列ID")


class TimeSetGetIn(QueueSetInBase):
    timeSetId: Optional[str] = Field(
        default=None, description="时间设置ID, 未携带时表示获取所有时间设置数据"
    )


class TimeSetGetOut(OutBase):
    index: List[TimeSetIndexItem] = Field(..., description="时间设置索引列表")
    data: Dict[str, TimeSet] = Field(
        ..., description="时间设置数据字典, key来自于index列表的uid"
    )


class TimeSetCreateOut(OutBase):
    timeSetId: str = Field(..., description="新创建的时间设置ID")
    data: TimeSet = Field(..., description="时间设置配置数据")


class TimeSetUpdateIn(QueueSetInBase):
    timeSetId: str = Field(..., description="时间设置ID")
    data: TimeSet = Field(..., description="时间设置更新数据")


class TimeSetDeleteIn(QueueSetInBase):
    timeSetId: str = Field(..., description="时间设置ID")


class TimeSetReorderIn(QueueSetInBase):
    indexList: List[str] = Field(..., description="时间设置ID列表, 按新顺序排列")


class QueueItemGetIn(QueueSetInBase):
    queueItemId: Optional[str] = Field(
        default=None, description="队列项ID, 未携带时表示获取所有队列项数据"
    )


class QueueItemGetOut(OutBase):
    index: List[QueueItemIndexItem] = Field(..., description="队列项索引列表")
    data: Dict[str, QueueItem] = Field(
        ..., description="队列项数据字典, key来自于index列表的uid"
    )


class QueueItemCreateOut(OutBase):
    queueItemId: str = Field(..., description="新创建的队列项ID")
    data: QueueItem = Field(..., description="队列项配置数据")


class QueueItemUpdateIn(QueueSetInBase):
    queueItemId: str = Field(..., description="队列项ID")
    data: QueueItem = Field(..., description="队列项更新数据")


class QueueItemDeleteIn(QueueSetInBase):
    queueItemId: str = Field(..., description="队列项ID")


class QueueItemReorderIn(QueueSetInBase):
    indexList: List[str] = Field(..., description="队列项ID列表, 按新顺序排列")


class DispatchIn(_SchemaModel):
    taskId: str = Field(
        ...,
        description="目标任务ID, 设置类任务可选对应脚本ID或用户ID, 代理类任务可选对应队列ID或脚本ID",
    )


class TaskCreateIn(DispatchIn):
    mode: Literal["AutoProxy", "ScriptConfig", "Update", "CycleRun"] = Field(
        ...,
        description="任务模式; CycleRun 为循环运行, 仅接受循环队列, 其脚本按 AutoProxy 执行",
    )
    resumeFromScriptId: str | None = Field(
        default=None,
        description="可选：仅对队列任务生效；从指定脚本ID开始执行（之前的脚本将被标记为跳过）",
    )
    userId: str | None = Field(
        default=None,
        description="可选：仅对脚本的自动代理任务生效；只运行该脚本下的这一个用户",
    )
    userIds: list[str] | None = Field(
        default=None,
        description="可选：仅对脚本的自动代理任务生效；只运行指定的多个用户",
    )
    queueUserIds: dict[str, list[str]] | None = Field(
        default=None,
        description="可选：仅对队列任务生效；按脚本ID指定本次要运行的用户；未列出的脚本不限, 空列表表示该脚本本次整项跳过",
    )
    viewOnly: bool = Field(
        default=False,
        description="可选：仅 ScriptConfig 生效；只读查看会话（不注入基线、不回读字段），用于预览历史备份",
    )
    instanceIdx: int | None = Field(
        default=None,
        description="可选：仅 ScriptConfig 生效；直控指定会话窗口打开的原生实例（临时切换活跃，会话结束还原）",
    )


class TaskCreateOut(OutBase):
    taskId: str = Field(..., description="新创建的任务ID")


class WSEnvelope(_SchemaModel):
    """主 WebSocket 统一消息信封, 前后端均按 id + type 路由"""

    id: str = Field(
        ...,
        description="路由ID, 标识任务、请求或业务会话, 如 Main、TaskManager、任务UUID",
    )
    type: str = Field(
        ...,
        description="消息类别, 点分小写命名, 如 task.info.updated、backend.shutdown.ready",
    )
    data: Dict[str, JsonValue] = Field(
        default_factory=dict,
        description="消息数据, 关键消息使用对应的 WS*Data 模型构造",
    )

    @field_validator("id", "type")
    @classmethod
    def validate_route_field(cls, value: str) -> str:
        """路由字段必须为非空字符串，并统一去除首尾空白。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("WebSocket 路由 id/type 不能为空")
        return normalized


class WSTaskNoticeData(_SchemaModel):
    """任务提示消息数据 (type=task.notice)"""

    level: Literal["info", "warning", "error"] = Field(..., description="提示级别")
    message: str = Field(..., description="提示内容")
    messageKey: Optional[str] = Field(
        default=None, description="可选的前端翻译键；旧客户端仍使用 message"
    )


class WSTaskConfigDiscardedData(_SchemaModel):
    """配置会话改动被丢弃的消息数据 (type=task.config.discarded)

    reason 是机器可读原因，正文由前端按语言本地化：structure=队列结构或配置
    方案与基线不一致, unreadable=读取落盘配置失败, not_written=原生程序没写出
    完整配置。
    """

    reason: Literal["structure", "unreadable", "not_written"] = Field(
        ..., description="丢弃原因"
    )


class WSSystemNoticeData(_SchemaModel):
    """系统通知数据 (type=system.notice, id=Main)：启动期攒下、主连接建立后发出。"""

    level: Literal["info", "warning", "error"] = Field(..., description="提示级别")
    title: str = Field(..., description="标题")
    lines: List[str] = Field(default_factory=list, description="正文，每项一行")


class WSEmulatorOperationData(_SchemaModel):
    """模拟器操作结束通知 (type=emulator.operation.finished, id=EmulatorManager)

    启动 / 关闭是后台任务, 接口一调用就返回; 界面靠这条消息知道那一次操作什么时候真正结束。
    """

    emulatorId: str = Field(..., description="模拟器配置 ID")
    index: str = Field(..., description="设备索引 (Emulator 2.0 下是设备号)")
    operate: Literal["open", "close", "show", "hide"] = Field(
        ..., description="操作类型"
    )
    ok: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="失败原因; 成功时为空")


class WSTaskUserInfoData(_SchemaModel):
    """任务快照中的用户状态。"""

    user_id: str = Field(..., description="用户 ID")
    name: str = Field(..., description="用户名称")
    status: str = Field(..., description="用户执行状态")


class WSTaskScriptInfoData(_SchemaModel):
    """任务快照中的脚本状态。"""

    script_id: str = Field(..., description="脚本 ID")
    name: str = Field(..., description="脚本名称")
    status: str = Field(..., description="脚本执行状态")
    userList: List[WSTaskUserInfoData] = Field(
        default_factory=list, description="脚本下的用户状态"
    )


class WSTaskCyclePreviewData(_SchemaModel):
    """循环运行的一个待运行条目。"""

    queueItemId: str = Field(..., description="队列项 ID")
    scriptId: str = Field(..., description="脚本 ID")
    scriptName: str = Field(..., description="脚本名称")
    nextRunAt: str = Field(..., description="下次运行时间, 格式为YYYY-MM-DD HH:MM:SS")
    isDue: bool = Field(default=False, description="是否已到运行时间")
    isRunning: bool = Field(default=False, description="是否正在运行")


class WSTaskInfoUpdatedData(_SchemaModel):
    """任务信息全量快照 (type=task.info.updated)。"""

    task_info: List[WSTaskScriptInfoData] = Field(
        default_factory=list, description="任务脚本与用户状态"
    )
    cycleNextList: List[WSTaskCyclePreviewData] = Field(
        default_factory=list, description="循环运行的待运行条目, 仅循环任务非空"
    )


class WSTaskLogUpdatedData(_SchemaModel):
    """任务日志更新 (type=task.log.updated), 按序号增量推送。"""

    log: str = Field(default="", description="append 为真时是新增片段, 否则是完整日志")
    seq: int = Field(default=0, description="推送序号, 每个任务独立, 从 1 起单调递增")
    append: bool = Field(default=False, description="是否追加到已有日志, 否则整体替换")
    firstLine: int = Field(
        default=1,
        description="log 第一行在完整日志里的行号, 供界面显示真实行号; append 时忽略",
    )


class WSTaskScriptIdentityData(_SchemaModel):
    """任务关联的脚本静态标识。"""

    scriptId: str = Field(..., description="脚本 ID")
    scriptType: str = Field(..., description="脚本类型键")


class TaskRuntimeSnapshotItem(_SchemaModel):
    """一个运行中任务的 HTTP 初始快照。"""

    taskId: str = Field(..., description="任务 ID")
    mode: Literal["AutoProxy", "ScriptConfig", "Update"] = Field(
        ..., description="脚本执行模式; 循环运行的脚本同样按 AutoProxy 执行"
    )
    isCycle: bool = Field(default=False, description="是否为循环运行任务")
    queueId: Optional[str] = Field(default=None, description="调度队列 ID")
    scriptId: Optional[str] = Field(default=None, description="脚本 ID")
    userId: Optional[str] = Field(default=None, description="用户 ID")
    stopping: bool = Field(default=False, description="任务是否正在停止")
    scripts: List[WSTaskScriptIdentityData] = Field(
        default_factory=list, description="任务关联的脚本静态标识"
    )
    task_info: List[WSTaskScriptInfoData] = Field(
        default_factory=list, description="任务脚本与用户状态"
    )
    cycleNextList: List[WSTaskCyclePreviewData] = Field(
        default_factory=list, description="循环运行的待运行条目, 仅循环任务非空"
    )
    log: str = Field(default="", description="已推送的脚本日志, 与下一条增量推送衔接")
    logSeq: int = Field(default=0, description="已推送日志对应的推送序号")
    logFirstLine: int = Field(default=1, description="快照日志首行在完整日志里的行号")


# 首屏立即请求的快照提前构建，不把启动开销转移到首次状态查询。
class TaskRuntimeSnapshot(BaseModel):
    """任务运行与定时队列 HTTP 初始快照。"""

    tasks: List[TaskRuntimeSnapshotItem] = Field(default_factory=list)
    scheduledScripts: List[WSTaskScriptIdentityData] = Field(
        default_factory=list, description="已启用定时队列关联的脚本静态标识"
    )


class TaskStatusOut(OutBase):
    """按 taskId 单点查询一个任务的状态, 不携带日志。"""

    taskId: str = Field(..., description="任务 ID")
    status: Literal["running", "success", "error", "cancelled"] = Field(
        ..., description="任务状态; running 为运行中, 其余为终态"
    )
    detail: Optional[str] = Field(default=None, description="任务结果描述")
    error: Optional[str] = Field(default=None, description="任务错误信息")
    mode: Optional[Literal["AutoProxy", "ScriptConfig", "Update"]] = Field(
        default=None, description="任务模式"
    )
    isCycle: bool = Field(default=False, description="是否为循环运行任务")
    queueId: Optional[str] = Field(default=None, description="调度队列 ID")
    scriptId: Optional[str] = Field(default=None, description="脚本 ID")
    userId: Optional[str] = Field(default=None, description="用户 ID")
    stopping: bool = Field(default=False, description="任务是否正在停止")
    finishedAt: Optional[str] = Field(
        default=None,
        description="任务结束时间, 格式为YYYY-MM-DD HH:MM:SS, 运行中为空",
    )


class WSTaskCompletedData(_SchemaModel):
    """任务完成消息数据 (type=task.completed)"""

    result: str = Field(..., description="任务结果描述")
    outcome: Literal["success", "error", "cancelled"] = Field(
        ..., description="机器可读的任务结果"
    )
    error: Optional[str] = Field(default=None, description="任务错误信息")
    task_info: List[WSTaskScriptInfoData] = Field(..., description="任务信息全量快照")


class WSTaskCreatedData(_SchemaModel):
    """新任务创建通知数据 (id=TaskManager, type=task.created)"""

    taskId: str = Field(..., description="新任务ID")
    mode: Literal["AutoProxy", "ScriptConfig", "Update", "CycleRun"] = Field(
        ..., description="任务模式, 与创建请求一致"
    )
    scripts: List[WSTaskScriptIdentityData] = Field(
        default_factory=list, description="任务关联的脚本静态标识"
    )
    queueId: Optional[str] = Field(default=None, description="所属调度队列ID")
    taskName: Optional[str] = Field(default=None, description="任务名称")
    taskType: Optional[str] = Field(default=None, description="任务类型")


class WSPowerCountdownData(_SchemaModel):
    """电源倒计时更新数据 (id=Main, type=power.countdown.updated)"""

    operation: str = Field(..., description="待执行的电源操作")
    remaining: int = Field(..., description="剩余秒数")


class PowerCountdownSnapshot(BaseModel):
    """当前电源倒计时 HTTP 初始快照。"""

    active: bool = Field(default=False, description="是否正在倒计时")
    operation: Optional[str] = Field(default=None, description="待执行电源操作")
    remaining: int = Field(default=0, ge=0, description="剩余秒数")


class WSPowerSignData(_SchemaModel):
    """电源标志更新数据 (id=Main, type=power.sign.updated)"""

    signal: str = Field(..., description="电源操作信号")


class WSDisplayMonitorRectData(_SchemaModel):
    """一块显示器的工作区（去掉任务栏），物理像素、桌面坐标。"""

    left: int = Field(..., description="左边界")
    top: int = Field(..., description="上边界")
    right: int = Field(..., description="右边界")
    bottom: int = Field(..., description="下边界")


class WSDisplayDetachPromptData(_SchemaModel):
    """真实显示器回来了但有任务在跑, 问用户要不要拆虚拟屏 (id=Main, type=display.detach.prompt)

    虚拟屏是主显示器, 回来的真实屏只是第二块, 任务栏和主窗口都留在看不见的那块上,
    所以弹窗必须放到 `monitor` 指的那块屏上, 前端据此把它摆到该屏右下角。
    """

    returned: list[str] = Field(..., description="回来的真实显示设备名列表")
    monitor: Optional[WSDisplayMonitorRectData] = Field(
        default=None,
        description="回来那块屏的工作区; 读不到时为空, 前端自行挑一块非主显示器",
    )


class WSGameSignResultData(_SchemaModel):
    """游戏签到结果广播数据 (id=GameSign, type=gamesign.result.updated)

    result 为 JSON 序列化后的签到结果合并数据, 与 GET 快照接口返回一致。
    """

    result: str = Field(..., description="JSON 序列化的签到结果数据")


class WSUpdateProgressData(_SchemaModel):
    """更新下载进度数据 (id=Update, type=update.progress)"""

    downloaded_size: int = Field(..., description="已下载字节数")
    file_size: int = Field(..., description="文件总字节数")
    speed: float = Field(..., description="下载速度 (B/s)")
    source: str = Field(..., description="下载源")


class WSUpdateCompletedData(_SchemaModel):
    """更新下载完成数据 (id=Update, type=update.completed)。"""

    file: str = Field(..., description="已下载更新包路径")


class WSUpdateFailedData(_SchemaModel):
    """更新下载失败数据 (id=Update, type=update.failed)。"""

    message: str = Field(..., description="失败原因")


class UpdateDownloadSnapshot(_SchemaModel):
    """更新下载 HTTP 初始快照。"""

    status: Literal[
        "idle",
        "downloading",
        "switchingSource",
        "completed",
        "failed",
        "cancelled",
    ] = Field(default="idle")
    version: Optional[str] = Field(default=None, description="当前下载版本")
    source: Optional[str] = Field(default=None, description="当前下载源")
    downloaded_size: int = Field(default=0, ge=0)
    file_size: int = Field(default=0, ge=0)
    speed: float = Field(default=0, ge=0)
    file: Optional[str] = Field(default=None, description="完成后的更新包路径")
    message: Optional[str] = Field(default=None, description="失败或状态说明")


class PowerIn(_SchemaModel):
    signal: Literal[
        "NoAction",
        "Shutdown",
        "ShutdownForce",
        "Reboot",
        "Hibernate",
        "Sleep",
        "KillSelf",
        "RestartSelf",
        "Logoff",
    ] = Field(..., description="电源操作信号")


class PowerOut(OutBase):
    signal: Literal[
        "NoAction",
        "Shutdown",
        "ShutdownForce",
        "Reboot",
        "Hibernate",
        "Sleep",
        "KillSelf",
        "RestartSelf",
        "Logoff",
    ] = Field(..., description="电源操作信号")


class HistorySearchIn(_SchemaModel):
    mode: Literal["DAILY", "WEEKLY", "MONTHLY"] = Field(..., description="合并模式")
    start_date: str = Field(..., description="开始日期, 格式YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期, 格式YYYY-MM-DD")


class HistorySearchOut(OutBase):
    data: Dict[str, Dict[str, HistoryData]] = Field(
        ...,
        description="历史记录索引数据字典, 格式为 { '日期': { '用户名': [历史记录信息] } }",
    )


class HistoryDataGetIn(_SchemaModel):
    jsonPath: str = Field(..., description="需要提取数据的历史记录JSON文件")


class HistoryDataGetOut(OutBase):
    data: HistoryData = Field(..., description="历史记录数据")


class ToolsGetOut(OutBase):
    data: ToolsConfig = Field(..., description="工具配置数据")


class ToolsUpdateIn(_SchemaModel):
    data: ToolsConfig = Field(..., description="工具配置需要更新的数据")


class SettingGetOut(OutBase):
    data: GlobalConfig = Field(..., description="全局设置数据")


class SettingUpdateIn(_SchemaModel):
    data: GlobalConfig = Field(..., description="全局设置需要更新的数据")


class UpdateCheckIn(_SchemaModel):
    current_version: str = Field(..., description="当前前端版本号")
    if_force: bool = Field(default=False, description="是否强制拉取更新信息")


class UpdateCheckOut(OutBase):
    if_need_update: bool = Field(..., description="是否需要更新前端")
    latest_version: str = Field(..., description="最新前端版本号")
    update_info: Dict[str, Dict[str, List[str]]] = Field(
        ...,
        description="版本更新信息：版本号 -> 分类 -> 条目，只含比当前版本新的版本段，按版本号降序",
    )


# ============== 日志模式调试相关模型 ==============


class PushLogPattern(_SchemaModel):
    """推送日志采集模式配置（split/regex/multiline 三种模式按 type 区分，各模式使用对应字段）"""

    type: Literal["split", "regex", "multiline"] = Field(..., description="匹配类型")
    name: Optional[str] = Field(
        default=None, description="规则标题（供分享站展示/说明）"
    )
    enabled: Optional[bool] = Field(
        default=None, description="单条规则启用/停用开关：停用时保留配置但不参与采集"
    )
    logType: Optional[str] = Field(default=None, description="日志类型：普通/失败")
    match: Optional[str] = Field(default=None, description="split 模式的匹配关键字")
    head: Optional[str] = Field(default=None, description="split 模式的首部关键字")
    headInclude: Optional[bool] = Field(
        default=None, description="split 模式是否包含首部关键字"
    )
    tail: Optional[str] = Field(default=None, description="split 模式的尾部关键字")
    tailInclude: Optional[bool] = Field(
        default=None, description="split 模式是否包含尾部关键字"
    )
    extract: Optional[str] = Field(
        default=None, description="regex 模式的提取正则（split/regex 通用）"
    )
    start: Optional[str] = Field(default=None, description="multiline 模式的起始行正则")
    end: Optional[str] = Field(default=None, description="multiline 模式的结束行正则")
    maxLines: Optional[int] = Field(
        default=None, description="multiline 模式的最大跨行数"
    )


class PatternDebugIn(_SchemaModel):
    """日志模式调试请求"""

    pattern: PushLogPattern = Field(..., description="待调试的推送日志模式配置")
    logText: str = Field(default="", description="待调试的多行日志文本")


class PatternDebugResultItem(_SchemaModel):
    """单行/单窗口调试结果"""

    idx: int = Field(..., description="行号或窗口序号")
    hit: bool = Field(..., description="是否命中")
    extracted: str = Field(default="", description="提取后的文本")
    line: str = Field(default="", description="原始日志行（多行模式为空）")
    error: Optional[str] = Field(default=None, description="该行/窗口的错误信息")


class PatternDebugOut(OutBase):
    """日志模式调试响应"""

    configError: Optional[str] = Field(
        default=None, description="配置级错误（正则/表达式语法错误等）"
    )
    isMultiline: bool = Field(default=False, description="是否为多行聚合模式")
    results: List[PatternDebugResultItem] = Field(
        default_factory=list, description="逐行/逐窗口调试结果"
    )


class GeneralNativeConfigReadIn(_SchemaModel):
    scriptId: str = Field(description="通用脚本 ID")
    file: str = Field(
        default="", description="配置目录内的相对文件名；单文件模式可留空"
    )


class GeneralNativeConfigWriteIn(GeneralNativeConfigReadIn):
    content: str = Field(max_length=2 * 1024 * 1024, description="原生配置文本")
    revision: str = Field(description="读取时的文件指纹，防止覆盖外部修改")


class GeneralNativeConfigOut(OutBase):
    files: list[str] = Field(default_factory=list)
    file: str = ""
    content: str = ""
    revision: str = ""


# 外部程序占用协议。业务规则由 core 持有，schema 只声明公开格式。
class ExternalHoldEnvelopeIn(_SchemaModel):
    payload: str = Field(
        ...,
        min_length=1,
        max_length=16384,
        description="UTF-8 JSON 的无填充 Base64URL 编码",
    )
    signature: str = Field(
        ...,
        pattern=r"^[0-9a-f]{64}$",
        description="对 payload 原文计算的 HMAC-SHA256 小写十六进制签名",
    )


class ExternalHoldCommandIn(_SchemaModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    requestId: str = Field(..., min_length=1, max_length=128)
    callerId: str = Field(..., min_length=1, max_length=80)
    action: Literal["acquire", "release", "status"]
    scriptId: str = Field(..., min_length=1, max_length=36)
    holdId: str = Field(..., min_length=1, max_length=128)
    issuedAt: AwareDatetime = Field(
        ..., description="UTC 签发时间，允许过去 5 分钟或未来 1 分钟"
    )
    ttlSeconds: int | None = Field(
        default=None, ge=1, le=86400, description="申请时必填；从签发时间开始计算"
    )


class ExternalHoldInfo(_SchemaModel):
    holdId: str
    callerId: str
    scriptId: str
    state: Literal["stopping", "active", "released", "expired", "failed"]
    expiresAt: float = Field(..., description="UTC Unix 秒")
    message: str = ""


class ExternalHoldOut(OutBase):
    requestId: str = ""
    hold: ExternalHoldInfo | None = None
    remainingHolds: int = 0


class ExternalControlSettingsIn(_SchemaModel):
    enabled: bool = False
    email: str = Field(default="", max_length=254)
    authorizationCode: SecretStr | None = Field(
        default=None, description="留空保留已有授权码"
    )
    callerId: str | None = Field(default=None, min_length=1, max_length=80)
    callerSecret: SecretStr | None = Field(
        default=None, description="新增或轮换调用方密钥，至少 32 字符"
    )
    removeCaller: bool = False


class ExternalControlSettingsData(_SchemaModel):
    enabled: bool = False
    email: str = ""
    hasAuthorizationCode: bool = False
    callers: list[str] = Field(default_factory=list)


class ExternalControlSnapshotOut(OutBase):
    settings: ExternalControlSettingsData = Field(
        default_factory=ExternalControlSettingsData
    )
    holds: list[ExternalHoldInfo] = Field(default_factory=list)
    results: list[ExternalHoldOut] = Field(default_factory=list)
    mailError: str = ""


class ExternalHoldForceReleaseIn(_SchemaModel):
    callerId: str
    holdId: str


class ExternalControlContractOut(OutBase):
    backendUrl: str = Field(
        default="",
        description="本机 Python 后端直连地址，不是前端代理或远程桌面宿主地址",
    )
    schemas: dict[str, Any] = Field(
        default_factory=dict, description="当前后端公开输入模型的 JSON Schema"
    )
