"""二级界面交互自检：切页签、切条目（档案抽出）、确认弹窗，各截一张图并打印状态。

用法：.venv/Scripts/python.exe qt/tools/selftest_section.py <repo> <out_dir>
"""
import sys
from pathlib import Path
repo = Path(sys.argv[1]); out = Path(sys.argv[2])
sys.argv = [sys.argv[0], "--skip-boot", "--no-backend", "--section", "2", "--size", "1920x1061", "--theme", "light", "--motion", "standard"]
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
orig_exec = QGuiApplication.exec
def patched_exec(self=None):
    app = QGuiApplication.instance()
    def find(name):
        for o in [ENG[0].rootObjects()[0]]:
            r = o.findChild(QObject, name)
            if r: return r
    import shiboken6
    from PySide6.QtQuick import QQuickWindow
    import shiboken6
    from PySide6.QtQuick import QQuickWindow
    root = ENG[0].rootObjects()[0]
    qw = shiboken6.wrapInstance(shiboken6.getCppPointer(root)[0], QQuickWindow)
    def shot(name): qw.grabWindow().save(str(out / name))
    def tab(): find("archivePanel").setProperty("tab", 3)
    def sel(): QMetaObject.invokeMethod(find("sections"), "select", Q_ARG("QVariant", 1), Q_ARG("QVariant", 0))
    def modal(): QMetaObject.invokeMethod(find("confirmModal"), "open", Q_ARG("QVariant", "BGI 每日"), Q_ARG("QVariant", "POST /api/scripts/update"))
    plan = [(2600, tab), (2700, lambda: shot("t_tab_mid.png")), (3200, lambda: shot("t_tab.png")), (3250, lambda: print("DBG", find("archivePanel").property("tabFade"), find("archivePanel").property("dec"), find("archivePanel").property("tab"), find("archivePanel").property("opacity"), flush=True)),
            (3400, sel), (3600, lambda: shot("t_pull.png")), (5600, lambda: shot("t_sel.png")), (5650, lambda: print("DBG2", find("sections").property("target"), flush=True)),
            (5800, modal), (6300, lambda: shot("t_modal.png")), (6350, lambda: print("DBG3", find("confirmModal").property("shown"), find("confirmModal").property("p"), flush=True)), (6500, app.quit)]
    for ms, fn in plan: QTimer.singleShot(ms, fn)
    return orig_exec()
QGuiApplication.exec = staticmethod(patched_exec)
sys.exit(qtmain.main())
