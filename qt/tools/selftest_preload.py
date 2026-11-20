"""增强挡位后台预加载自检：停在索引页，记录 0–9 秒的帧间隔，打印预加载前后最长的一帧。

用法：.venv/Scripts/python.exe qt/tools/selftest_preload.py <repo> [move]
  move：1–7 秒内持续模拟鼠标移动（用户在操作），预加载应顺延到停止操作之后。
"""
import sys, time
from pathlib import Path
repo = Path(sys.argv[1]); move = len(sys.argv) > 2
sys.argv = [sys.argv[0], "--skip-boot", "--no-backend", "--motion", "enhanced", "--size", "1920x1061", "--theme", "light"]
sys.path.insert(0, str(repo / "qt"))
import main as qtmain
from PySide6.QtQml import QQmlApplicationEngine as _E
ENG = []
class Eng(_E):
    def __init__(self, *a): super().__init__(*a); ENG.append(self)
qtmain.QQmlApplicationEngine = Eng
from PySide6.QtCore import QTimer, QObject
from PySide6.QtGui import QGuiApplication
import shiboken6
from PySide6.QtQuick import QQuickWindow
orig = QGuiApplication.exec
def patched(self=None):
    app = QGuiApplication.instance(); root = ENG[0].rootObjects()[0]
    win = shiboken6.wrapInstance(shiboken6.getCppPointer(root)[0], QQuickWindow)
    t0 = time.perf_counter(); frames = []
    win.frameSwapped.connect(lambda: frames.append(time.perf_counter() - t0))
    pump = QTimer(); pump.setInterval(16); pump.timeout.connect(win.update); pump.start(); patched.p = pump
    if move:
        from PySide6.QtCore import QPoint
        from PySide6.QtTest import QTest
        step = {"i": 0}
        def wiggle():
            if time.perf_counter() - t0 < 7.0:
                step["i"] += 1
                QTest.mouseMove(win, QPoint(400 + (step["i"] * 37) % 900, 300 + (step["i"] * 23) % 400))
        mv = QTimer(); mv.setInterval(100); mv.timeout.connect(wiggle); mv.start(); patched.mv = mv
    def report():
        gaps = sorted(((b - a) * 1000, a) for a, b in zip(frames, frames[1:]) if a > 1.0)
        during = [g for g, t in gaps if t < 7.0]
        print("frames", len(frames), "worst gaps (ms @ s):", [(round(g), round(t, 2)) for g, t in gaps[-5:]],
              "| worst while moving (<7s):", round(max(during)) if during else None, flush=True)
        app.quit()
    QTimer.singleShot(13000, report)
    return orig()
QGuiApplication.exec = staticmethod(patched)
sys.exit(qtmain.main())
