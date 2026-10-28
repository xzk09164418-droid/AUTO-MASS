"""本机构建的联网功能边界，不读取用户旧配置来重新启用已移除的服务。

只限制 AUTO-MAS 自己的功能入口，不修改系统代理、防火墙，也不干预外部脚本
或游戏的网络。活动内容、社区签到、远程通知和邮箱控制仍由各自模块负责请求与错误处理。
"""

ALLOWED_NETWORK_FEATURES = frozenset(
    {"activity", "notification", "mail", "local", "community-sign"}
)


class NetworkFeatureDisabled(RuntimeError):
    """调用方请求了本构建明确停用的联网功能。"""


def network_feature_enabled(feature: str) -> bool:
    return feature in ALLOWED_NETWORK_FEATURES


def require_network_feature(feature: str) -> None:
    if not network_feature_enabled(feature):
        raise NetworkFeatureDisabled(
            "本机构建已停用该联网功能；仅保留活动内容、社区签到、邮箱控制和远程通知"
        )
