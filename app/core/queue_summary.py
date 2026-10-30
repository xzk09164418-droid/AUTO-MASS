"""队列通知的统计窗口；只记录最终结果，不改变调度计划。"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import lcm


@dataclass
class SummaryWindow:
    started: datetime
    period: int | None
    fixed: frozenset[str]
    ended: datetime | None = None
    pending: set[str] = field(default_factory=set)
    finished_fixed: set[str] = field(default_factory=set)
    counts: dict[str, Counter[str]] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)
    reported: bool = False

    def record(self, key: str, name: str, outcome: str) -> None:
        self.names[key] = name
        self.counts.setdefault(key, Counter())[outcome] += 1


class QueueSummaryLedger:
    """未完成的同一队列项保留原窗口，后续执行不会覆盖此前结果。"""

    def __init__(self, started: datetime) -> None:
        self.started = started
        self.windows: list[SummaryWindow] = []
        self.owners: dict[str, SummaryWindow] = {}

    @staticmethod
    def policy(specs: dict[str, tuple[str, int]]) -> tuple[int | None, frozenset[str]]:
        fixed = frozenset(
            key for key, (mode, _) in specs.items() if mode == "fixed_time"
        )
        period = (
            None
            if fixed or not specs
            else lcm(*(minutes for _, minutes in specs.values()))
        )
        return period, fixed

    def observe(self, specs: dict[str, tuple[str, int]], due, now: datetime) -> None:
        if not self.windows:
            period, fixed = self.policy(specs)
            self.windows.append(SummaryWindow(self.started, period, fixed))
        current = self.windows[-1]
        if current.ended is not None:
            period, fixed = self.policy(specs)
            current = SummaryWindow(current.ended, period, fixed)
            self.windows.append(current)
        # 先登记到期执行，再封窗；阻塞项只登记一次，保留其原归属。
        for key, name, scheduled in due:
            if key in self.owners:
                continue
            window = next(
                (
                    w
                    for w in self.windows
                    if w.ended is not None and not w.reported and scheduled < w.ended
                ),
                current,
            )
            window.pending.add(key)
            window.names[key] = name
            self.owners[key] = window
        while (
            current.period is not None
            and (now - current.started).total_seconds() >= current.period * 60
        ):
            current.ended = current.started + timedelta(minutes=current.period)
            # 将边界之后才到期的执行转入下一窗，旧的未完成执行仍留在原窗。
            period, fixed = self.policy(specs)
            following = SummaryWindow(current.ended, period, fixed)
            for key in list(current.pending):
                scheduled = next((when for item, _, when in due if item == key), None)
                if scheduled is not None and scheduled >= current.ended:
                    current.pending.remove(key)
                    following.pending.add(key)
                    following.names[key] = current.names[key]
                    self.owners[key] = following
            self.windows.append(following)
            current = following

    def complete(self, key: str, name: str, outcome: str, now: datetime) -> None:
        window = self.owners.pop(key)
        window.pending.remove(key)
        window.record(key, name, outcome)
        if key in window.fixed:
            window.finished_fixed.add(key)
        if (
            window.ended is None
            and window.fixed
            and window.fixed <= window.finished_fixed
        ):
            window.ended = now

    def take_ready(self) -> list[SummaryWindow]:
        ready = [
            w
            for w in self.windows
            if w.ended is not None and not w.pending and not w.reported
        ]
        # 保留最新窗口用于确定下一窗口起点，标记已发窗口防止重复。
        for window in ready:
            window.reported = True
            if window is not self.windows[-1]:
                self.windows.remove(window)
        return [w for w in ready if w.counts]


def script_outcome(script) -> str:
    """按项目最终状态分类，不将中途失败或等待状态当成最终失败。"""
    statuses = [user.status for user in script.user_list]
    if script.status == "异常" or any(status == "异常" for status in statuses):
        return "failed"
    if script.status == "完成" and all(
        status in ("完成", "部分失败") for status in statuses
    ):
        return "success"
    return "unfinished"


async def send_queue_summary(window: SummaryWindow, name: str, task_info) -> None:
    from app.core import Config
    from app.core.notify import dispatch_task_report, global_target
    from app.models.notification import NotificationSummary, NotifyPayload

    if not Config.get("Notify", "IfSendStatistic") or not window.counts:
        return
    lines = [
        f"统计时间：{window.started:%Y-%m-%d %H:%M:%S} 至 {window.ended:%Y-%m-%d %H:%M:%S}"
    ]
    for key, counts in window.counts.items():
        lines.append(
            f"{window.names[key]}：成功 {counts['success']} 次，最终失败 {counts['failed']} 次，未完成 {counts['unfinished']} 次"
        )
    text = "\n".join(lines)
    await dispatch_task_report(
        NotifyPayload(
            title=f"{name} · 队列汇总",
            text=text,
            summary=NotificationSummary(text=text),
        ),
        [global_target(include_system=False)],
        task_info,
    )
