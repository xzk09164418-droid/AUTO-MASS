from __future__ import annotations

from importlib import import_module

# 热键解析和 worker 导入子模块时不需要创建运行环境；按实际访问解析公开导出。
_LAZY_EXPORTS = {
    "MaaFWDeviceConfig": ".models",
    "MaaFWResolvedPath": ".models",
    "MaaFWResourceBundlePlan": ".models",
    "MaaFWRunPlan": ".models",
    "MaaFWRunPlanError": ".run_plan",
    "MaaFWRunResult": ".models",
    "MaaFWRunnerEnvironment": ".environment",
    "MaaFWRunnerJobPayload": ".models",
    "MaaFWRunnerService": ".service",
    "MaaFWSkippedTaskPlan": ".models",
    "MaaFWTaskRunPlan": ".models",
    "build_maafw_run_plan": ".run_plan",
    "release_runner_environment": ".environment",
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
    "MaaFWDeviceConfig",
    "MaaFWResolvedPath",
    "MaaFWResourceBundlePlan",
    "MaaFWRunPlan",
    "MaaFWRunPlanError",
    "MaaFWRunResult",
    "MaaFWRunnerEnvironment",
    "MaaFWRunnerJobPayload",
    "MaaFWRunnerService",
    "MaaFWSkippedTaskPlan",
    "MaaFWTaskRunPlan",
    "build_maafw_run_plan",
    "release_runner_environment",
]
