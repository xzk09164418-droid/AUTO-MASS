"""录像带串循环自检：首张向上越界接到末张、末张向下越界接回首张，过渡中途与结束各截一张。

用法：.venv/Scripts/python.exe qt/tools/selftest_chain.py <repo> <out_dir> [section]
"""
import sys
from pathlib import Path
repo = Path(sys.argv[1]); out = Path(sys.argv[2]); sec = sys.argv[3] if len(sys.argv) > 3 else "2"
sys.argv = [sys.argv[0], "--skip-boot", "--no-backend", "--section", sec, "--size", "1920x1061", "--theme", "light"]
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
orig_exec = QGuiApplication.exec
def patched_exec(self=None):
    app = QGuiApplication.instance()
    import shiboken6
    from PySide6.QtQuick import QQuickWindow
    root = ENG[0].rootObjects()[0]
    qw = shiboken6.wrapInstance(shiboken6.getCppPointer(root)[0], QQuickWindow)
    sv = root.findChild(QObject, "sections")
    def shot(name): qw.grabWindow().save(str(out / name))
    def sel(k): QMetaObject.invokeMethod(sv, "select", Q_ARG("QVariant", k), Q_ARG("QVariant", 0))
    def st(tag): print(tag, "target", sv.property("target"), flush=True)
    plan = [(2600, lambda: shot("c0.png")), (2650, lambda: st("start")),
            (2700, lambda: sel(-1)), (2860, lambda: shot("c1_mid.png")), (3500, lambda: shot("c1.png")), (3550, lambda: st("after up")),
            (3600, lambda: sel(sv.property("target") + 1)), (3760, lambda: shot("c2_mid.png")), (4400, lambda: shot("c2.png")), (4450, lambda: st("after down")),
            (4500, app.quit)]
    for ms, fn in plan: QTimer.singleShot(ms, fn)
    return orig_exec()
QGuiApplication.exec = staticmethod(patched_exec)
sys.exit(qtmain.main())
