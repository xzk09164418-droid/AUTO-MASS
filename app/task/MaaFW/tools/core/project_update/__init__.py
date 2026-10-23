from __future__ import annotations

from importlib import import_module

# 启动维护只需文件与载荷工具，按实际访问再加载网络更新流程。
_LAZY_EXPORTS = {
    "ALERT_LOG_PREFIX": ".updater",
    "MaaFWMirrorCdkStatus": ".updater",
    "MaaFWProjectUpdateCandidate": ".updater",
    "MaaFWProjectUpdateDiscovery": ".updater",
    "MaaFWProjectUpdateError": ".updater",
    "MaaFWProjectUpdateResult": ".updater",
    "UpdateApplyError": ".apply",
    "apply_maafw_project_update": ".updater",
    "can_check_project_update": ".updater",
    "classify_precheck_failure": ".precheck_memo",
    "clear_runtime_precheck": ".precheck_memo",
    "detect_maafw_project_shell_hint": ".updater",
    "discover_maafw_project_update": ".updater",
    "precheck_memo_path": ".precheck_memo",
    "project_state_dir_for": ".apply",
    "query_mirrorchyan_cdk_status": ".updater",
    "read_runtime_precheck": ".precheck_memo",
    "update_maafw_project_if_needed": ".updater",
    "write_runtime_precheck": ".precheck_memo",
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(_LAZY_EXPORTS[name], __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))


__all__ = [
    "ALERT_LOG_PREFIX",
    "MaaFWMirrorCdkStatus",
    "MaaFWProjectUpdateCandidate",
    "MaaFWProjectUpdateDiscovery",
    "MaaFWProjectUpdateError",
    "MaaFWProjectUpdateResult",
    "UpdateApplyError",
    "apply_maafw_project_update",
    "can_check_project_update",
    "classify_precheck_failure",
    "clear_runtime_precheck",
    "detect_maafw_project_shell_hint",
    "discover_maafw_project_update",
    "precheck_memo_path",
    "project_state_dir_for",
    "query_mirrorchyan_cdk_status",
    "read_runtime_precheck",
    "update_maafw_project_if_needed",
    "write_runtime_precheck",
]
