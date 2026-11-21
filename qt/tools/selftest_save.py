"""保存自检（连真实后端）：设置 → 启动与界面，点两次「隐藏关闭按钮」（值回到原样但记为改动）再保存；
请求只含这一项且值不变，不会改动用户配置。"""
import sys
from pathlib import Path
repo = Path(sys.argv[1])
sys.argv = [sys.argv[0], "--skip-boot", "--section", "10", "--size", "1920x1061", "--theme", "light"]
sys.path.insert(0, str(repo / "qt"))
import main as qtmain
from PySide6.QtQml import QQmlApplicationEngine as _E
ENG = []
class Eng(_E):
    def __init__(self, *a):
        super().__init__(*a); ENG.append(self)
qtmain.QQmlApplicationEngine = Eng
from PySide6.QtCore import QTimer, QObject, QMetaObject, QPointF, Qt, QPoint, Q_ARG
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
import shiboken6
from PySide6.QtQuick import QQuickWindow, QQuickItem
orig = QGuiApplication.exec
def patched(self=None):
    app = QGuiApplication.instance()
    root = ENG[0].rootObjects()[0]
    win = shiboken6.wrapInstance(shiboken6.getCppPointer(root)[0], QQuickWindow)
    def find(name): return root.findChild(QObject, name)
    def click():
        def walk(it):
            for c in it.childItems():
                yield c
                yield from walk(c)
        items = [o for o in walk(win.contentItem()) if o.objectName().startswith("tog:")]
        if not items: print("no tog items; sample names:", [o.objectName() for o in root.findChildren(QObject) if o.objectName()][:15], flush=True)
        t = next((o for o in items if o.objectName() == "tog:UI.IfHideCloseButton"), None)
        if not t: print("toggle not found", flush=True); return
        p = t.mapToScene(QPointF(t.width() / 2 - 20, t.height() / 2))
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(int(p.x()), int(p.y())))
    def unsaved(tag): print(tag, "unsaved =", find("archivePanel").property("unsaved"), flush=True)
    def save(): QMetaObject.invokeMethod(find("sections"), "save", Q_ARG("QVariant", None))
    def toast(): print("toast:", find("toastText").property("text"), flush=True)
    plan = [(5000, click), (5400, lambda: unsaved("after 1 click")), (5600, click), (6000, lambda: unsaved("after 2 clicks")),
            (6200, save), (7500, toast), (7600, lambda: unsaved("after save")), (7800, app.quit)]
    for ms, fn in plan: QTimer.singleShot(ms, fn)
    return orig()
QGuiApplication.exec = staticmethod(patched)
sys.exit(qtmain.main())
