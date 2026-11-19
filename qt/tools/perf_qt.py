"""Qt 客户端性能测试（用法见 qt/tools/README.md）：启动动画 + 一级索引空闲，采样 CPU（单核百分比）、GPU 3D 引擎占用，
并用 PresentMon 记录呈现模式 / 同步间隔 / 帧时间。

用法：python perf_qt.py <repo> <tools_dir> <out_dir> [额外 qt 参数...]
"""

import csv
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import psutil

repo, tools, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
extra = sys.argv[4:]
out.mkdir(parents=True, exist_ok=True)
DURATION = 34

app = subprocess.Popen(
    [str(repo / ".venv/Scripts/python.exe"), str(repo / "qt/main.py"), "--no-backend", *extra],
    cwd=repo,
)
time.sleep(1.5)
# venv 启动器会再拉起真正的解释器进程
procs = [psutil.Process(app.pid)] + psutil.Process(app.pid).children(recursive=True)
target = max(procs, key=lambda p: p.memory_info().rss)
pid = target.pid
print("qt pid", pid, target.name())

pm_csv = out / "presentmon.csv"
pm = subprocess.Popen(
    [str(tools / "PresentMon.exe"), "--process_id", str(pid), "--output_file", str(pm_csv),
     "--timed", str(DURATION - 2), "--terminate_after_timed", "--no_console_stats", "--v1_metrics"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)

counter = f"\\GPU Engine(pid_{pid}_*engtype_3D)\\Utilization Percentage"
gpu_proc = subprocess.Popen(
    ["typeperf", counter, "-si", "1", "-sc", str(DURATION - 2)],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)

cpu = []
target.cpu_percent(None)
t0 = time.monotonic()
while time.monotonic() - t0 < DURATION - 2:
    time.sleep(1)
    try:
        cpu.append((round(time.monotonic() - t0), target.cpu_percent(None)))
    except psutil.NoSuchProcess:
        break

gpu_out, _ = gpu_proc.communicate(timeout=30)
pm_out, _ = pm.communicate(timeout=60)
app.terminate()
try:
    app.wait(10)
except subprocess.TimeoutExpired:
    app.kill()

gpu = []
for line in gpu_out.splitlines():
    if line.startswith('"') and "/" in line[:12]:
        cells = [c.strip('"') for c in line.split('","')]
        vals = [float(c) for c in cells[1:] if c.replace(".", "", 1).isdigit()]
        gpu.append(round(sum(vals), 2))

frames = []
if pm_csv.exists():
    with pm_csv.open(encoding="utf-8", errors="replace") as f:
        frames = list(csv.DictReader(f))

summary = {
    "args": extra,
    "cpu_single_core_pct": {"boot(0-18s)": [c for t, c in cpu if t <= 18], "idle(18s+)": [c for t, c in cpu if t > 18]},
    "gpu_3d_pct": gpu,
    "presentmon_stdout_tail": pm_out[-400:],
    "frames": len(frames),
}
if frames:
    cols = frames[0].keys()
    def col(*names):
        return next((n for n in names if n in cols), None)
    sync = col("SyncInterval")
    mode = col("PresentMode")
    ms = col("msBetweenPresents", "MsBetweenPresents", "FrameTime")
    summary["present_modes"] = sorted({f[mode] for f in frames}) if mode else None
    summary["sync_intervals"] = sorted({f[sync] for f in frames}) if sync else None
    if ms:
        vals = [float(f[ms]) for f in frames if f[ms] not in ("", "NA")]
        summary["frame_ms"] = {
            "median": round(statistics.median(vals), 2),
            "p95": round(sorted(vals)[int(len(vals) * 0.95) - 1], 2),
            "max": round(max(vals), 2),
        }
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=1))
