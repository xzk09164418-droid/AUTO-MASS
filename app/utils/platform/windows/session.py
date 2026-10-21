"""Windows 进程会话查询，供桌面执行与进程匹配共用。"""

import ctypes
import os

EXECUTION_SESSION_ENV = "AUTO_MAS_EXECUTION_SESSION_ID"


def get_process_session_id(pid: int | None = None) -> int:
    """读取实际会话编号；查询失败不能当作当前桌面继续执行。"""
    session_id = ctypes.c_uint()
    if not ctypes.windll.kernel32.ProcessIdToSessionId(
        pid if pid is not None else os.getpid(), ctypes.byref(session_id)
    ):
        raise ctypes.WinError()
    return session_id.value


def in_execution_session(pid: int | None = None) -> bool:
    """未启用隔离时维持原行为，启用后只匹配指定的执行会话。"""
    expected = os.environ.get(EXECUTION_SESSION_ENV)
    if expected is None:
        return True
    try:
        return get_process_session_id(pid) == int(expected)
    except OSError:
        return False
