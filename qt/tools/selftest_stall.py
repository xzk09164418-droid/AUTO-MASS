"""增强挡位进入阵列时的卡顿自检：记录帧间隔，打印点击后 2 秒内的最长一帧。

用法：.venv/Scripts/python.exe qt/tools/selftest_stall.py <repo> <打开时刻毫秒> [部门序号]
  打开时刻 ≥ 3000 时 3D 组件已在空闲时预加载；很早打开（如 300）则相当于没有预加载。
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
from PySide6.QtCore import QTimer, QObject, QMetaObject, Q_ARG
from PySide6.QtGui import QGuiApplication
import shiboken6
from PySide6.QtQuick import QQuickWindow
orig = QGuiApplication.exec
def patched(self=None):
    app = QGuiApplication.instance()
    root = ENG[0].rootObjects()[0]
    win = shiboken6.wrapInstance(shiboken6.getCppPointer(root)[0], QQuickWindow)
    frames = []
    win.frameSwapped.connect(lambda: frames.append(time.perf_counter()))
    mark = {}
    def go():
        mark["t"] = time.perf_counter()
        QMetaObject.invokeMethod(root.findChild(QObject, "hub"), "open", Q_ARG("QVariant", dept))
    def report():
        t0 = mark["t"]
        fs = [f for f in frames if t0 - 0.05 <= f <= t0 + 2.0]
        gaps = [b - a for a, b in zip(fs, fs[1:])]
        first = fs[0] - t0 if fs else -1
        print(f"open@{at}ms: frames={len(fs)} max gap={max(gaps) * 1000 if gaps else -1:.0f}ms first frame after {first * 1000:.0f}ms", flush=True)
        app.quit()
    QTimer.singleShot(at, go)
    QTimer.singleShot(at + 2500, report)
    return orig()
QGuiApplication.exec = staticmethod(patched)
sys.exit(qtmain.main())
