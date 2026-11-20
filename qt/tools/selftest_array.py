"""增强挡位阵列自检（需已安装 3D 组件）：总览截图 → 切列截图 → 读取并等待解密后截图。

用法：.venv/Scripts/python.exe qt/tools/selftest_array.py <repo> <out_dir>
"""
import sys
from pathlib import Path
repo = Path(sys.argv[1]); out = Path(sys.argv[2])
sys.argv = [sys.argv[0], "--skip-boot", "--section", "2", "--motion", "enhanced", "--size", "1920x1061", "--theme", "light"]
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
    def arr(): return root.findChild(QObject, "sections").property("arrayItem")
    def shot(n): win.grabWindow().save(str(out / n))
    def call(m, *a): QMetaObject.invokeMethod(arr(), m, *[Q_ARG("QVariant", x) for x in a])
    plan = [(6000, lambda: shot("aq_overview.png")), (6200, lambda: call("nav", "lane", 1)), (8000, lambda: shot("aq_lane.png")),
            (8200, lambda: call("open")), (14000, lambda: shot("aq_detail.png")),
            (14100, lambda: print("detail", arr().property("detailOpen"), arr().property("clarity"), flush=True)), (14300, app.quit)]
    for ms, fn in plan: QTimer.singleShot(ms, fn)
    return orig()
QGuiApplication.exec = staticmethod(patched)
sys.exit(qtmain.main())
