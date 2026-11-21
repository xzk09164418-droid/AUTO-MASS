"""增强挡位阵列自检（需已安装 3D 组件）：飞入中途 / 总览 / 切列 / 读取解密，返回后进入调度队列再截一组。

用法：.venv/Scripts/python.exe qt/tools/selftest_array.py <repo> <out_dir>
"""
import sys
from pathlib import Path
repo = Path(sys.argv[1]); out = Path(sys.argv[2])
sys.argv = [sys.argv[0], "--skip-boot", "--motion", "enhanced", "--size", "1920x1061", "--theme", "light"]
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
    sv = root.findChild(QObject, "sections")
    def arr(): return sv.property("arrayItem")
    def shot(n): win.grabWindow().save(str(out / n))
    def call(m, *a): QMetaObject.invokeMethod(arr(), m, *[Q_ARG("QVariant", x) for x in a])
    def hub_open(i): QMetaObject.invokeMethod(root.findChild(QObject, "hub"), "open", Q_ARG("QVariant", i))
    def close(): QMetaObject.invokeMethod(sv, "close")
    def st(tag): print(tag, "index", sv.property("index"), "arrayItem", arr() is not None, "fly", arr().property("fly") if arr() else None, flush=True)
    plan = [(5000, lambda: st("preloaded")), (5100, lambda: hub_open(1)), (5500, lambda: shot("aq_fly.png")), (8000, lambda: shot("aq_overview.png")),
            (8200, lambda: call("nav", "lane", 1)), (9800, lambda: shot("aq_lane.png")),
            (9900, lambda: call("open")), (15500, lambda: shot("aq_detail.png")),
            (15600, lambda: print("detail", arr().property("detailOpen"), arr().property("clarity"), flush=True)),
            (15700, lambda: call("close")), (17500, close), (17800, lambda: shot("aq_out.png")), (19500, lambda: st("closed")),
            (19600, lambda: hub_open(3)), (22500, lambda: (print("shooting", flush=True), shot("aq_queue.png"), print("shot", flush=True))), (22600, lambda: st("queue")),
            (22700, lambda: print("queue mode", arr().property("mode"), arr().property("rowCount"), flush=True)), (26000, app.quit)]
    for ms, fn in plan: QTimer.singleShot(ms, fn)
    return orig()
QGuiApplication.exec = staticmethod(patched)
sys.exit(qtmain.main())
