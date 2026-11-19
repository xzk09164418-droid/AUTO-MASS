import QtQuick
import QtQuick.Window
import "."

// 外壳：1920×1080 参考舞台按窗口等比缩放；启动动画 → 部门索引 → 二级界面。
// 后端在启动动画播放期间并行拉起，动画结束仍未就绪时由 BackendPanel 接管。
Window {
    id: root

    property var backend: null
    property bool skipBoot: false
    property bool backendEnabled: true
    property int initialSection: 0
    property string themeMode: "system"
    property bool booted: false

    width: 1600
    height: 900
    minimumWidth: 1024
    minimumHeight: 600
    visible: true
    title: "AUTO-MAS"
    color: Theme.bg

    Component.onCompleted: {
        Theme.mode = themeMode
        if (skipBoot) finishBoot()
    }

    function finishBoot() {
        if (booted) return
        booted = true
        if (initialSection >= 1 && initialSection <= 10)
            Qt.callLater(() => hub.open(initialSection - 1))
        else
            hub.forceActiveFocus()
    }

    Item {
        id: stage
        width: 1920
        height: 1080
        anchors.centerIn: parent
        scale: Math.min(root.width / 1920, root.height / 1080)
        clip: true

        DepartmentHub {
            id: hub
            anchors.fill: parent
            focus: true
            active: root.booted
            paused: sections.busy
            backendStatus: root.backendEnabled && root.backend ? root.backend.status : ""
            onOpenRequested: (i, r) => sections.open(i, r)
        }

        SectionHost {
            id: sections
            anchors.fill: parent
            departments: hub.departments
            onClosed: hub.focusCurrent()
        }

        BootSequence {
            id: bootSeq
            anchors.fill: parent
            visible: !root.booted
            running: !root.skipBoot
            onFinished: root.finishBoot()
        }
    }

    Shortcut {
        sequences: ["Esc", "Space"]
        enabled: !root.booted
        onActivated: bootSeq.skip()
    }

    BackendPanel {
        anchors.fill: parent
        backend: root.backendEnabled && root.booted ? root.backend : null
    }
}
