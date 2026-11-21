"""增强挡位进入阵列时的卡顿自检：记录帧间隔，打印点击后 2 秒内的最长一帧。

用法：.venv/Scripts/python.exe qt/tools/selftest_stall.py <repo> <打开时刻毫秒> [部门序号]
  部门序号从 0 起算。用较早的打开时刻（如 300）覆盖预热尚未完成的情况。
"""
import sys, time
from pathlib import Path
repo = Path(sys.argv[1]); at = int(sys.argv[2]); dept = int(sys.argv[3]) if len(sys.argv) > 3 else 1; motion = sys.argv[4] if len(sys.argv) > 4 else "enhanced"
sys.argv = [sys.argv[0], "--skip-boot", "--no-backend", "--motion", motion, "--size", "1920x1061", "--theme", "light"]
sys.path.insert(0, str(repo / "qt"))
import main as qtmain
from PySide6.QtQml import QQmlApplicationEngine as _E
ENG = []
class Eng(_E):
    def __init__(self, *a):
        super().__init__(*a); ENG.append(self)
qtmain.QQmlApplicationEngine = Eng
from PySide6.QtCore import QTimer, QObject, QMetaObject, Q_ARG, Qt
from PySide6.QtGui import QGuiApplication
import shiboken6
from PySide6.QtQuick import QQuickWindow
orig = QGuiApplication.exec
def patched(self=None):
    app = QGuiApplication.instance()
    root = ENG[0].rootObjects()[0]
    win = shiboken6.wrapInstance(shiboken6.getCppPointer(root)[0], QQuickWindow)
    frames = []
    win.frameSwapped.connect(lambda: frames.append(time.perf_counter()), Qt.DirectConnection)
    mark = {}
    def go():
        mark["t"] = time.perf_counter()
        QMetaObject.invokeMethod(root.findChild(QObject, "hub"), "open", Q_ARG("QVariant", dept))
    def report():
        t0 = mark["t"]
        samples = frames.copy()
        # 计入跨过采样终点的长帧，否则超过两秒的卡顿反而会从结果里消失。
        gaps = [b - a for a, b in zip(samples, samples[1:]) if b >= t0 and a < t0 + 2]
        first = next((f for f in samples if f >= t0), None)
        if first is None or samples[-1] < t0 + 2:
            QTimer.singleShot(100, report)
            return
        print(f"open@{at}ms: intervals={len(gaps)} max gap={max(gaps, default=0) * 1000:.0f}ms first frame after {(first - t0) * 1000:.0f}ms", flush=True)
        app.quit()
    QTimer.singleShot(at, go)
    QTimer.singleShot(at + 2500, report)
    return orig()
QGuiApplication.exec = staticmethod(patched)
sys.exit(qtmain.main())
