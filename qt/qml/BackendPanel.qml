import QtQuick
import QtQuick.Controls.Basic
import "."

// 后端连接面板。从未连上过时居中并压暗背景（应用尚不可用）；连上后又断开则停靠右上角。
Item {
    id: root

    property var backend: null
    property bool everReady: false
    readonly property string status: backend ? backend.status : ""
    readonly property bool isError: status === "error"
    readonly property bool shown: !!backend && status !== "" && status !== "ready"
    readonly property bool blocking: !everReady
    property bool logsOpen: isError

    onStatusChanged: {
        if (status === "ready") everReady = true
        if (status === "error") logsOpen = true
    }

    visible: opacity > 0
    opacity: shown ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: shown ? 300 : 200 } }

    Rectangle {
        anchors.fill: parent
        visible: root.blocking
        color: Theme.dark ? Qt.rgba(0.04, 0.07, 0.08, 0.72) : Qt.rgba(0.9, 0.89, 0.87, 0.78)
        MouseArea { anchors.fill: parent; hoverEnabled: true }   // 阻断背后的交互
    }

    Rectangle {
        id: panel
        width: Math.min(560, root.width - 48)
        height: content.implicitHeight + 48
        x: root.blocking ? (root.width - width) / 2 : root.width - width - 24
        y: root.blocking ? (root.height - height) / 2 : 24
        color: Theme.paper
        border.width: 1
        border.color: Theme.hair
        transform: Translate { y: root.shown ? 0 : (root.blocking ? 12 : -8) }

        Rectangle {
            width: parent.width
            height: 2
            color: root.isError ? Theme.error : Theme.ink
        }

        Column {
            id: content
            x: 24
            y: 24
            width: parent.width - 48
            spacing: 14

            Row {
                spacing: 12
                Text {
                    text: root.isError ? "X-ERR" : "X-000"
                    color: root.isError ? Theme.error : Theme.muted
                    font.family: Theme.font
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    font.letterSpacing: 2
                }
                Text {
                    text: "BACKEND // LINK"
                    color: Theme.muted
                    font.family: Theme.font
                    font.pixelSize: 12
                    font.letterSpacing: 2
                }
            }

            Text {
                text: root.status === "probing" ? qsTr("正在连接后端")
                    : root.status === "starting" ? qsTr("正在启动后端")
                    : qsTr("后端连接失败")
                color: Theme.ink
                font.family: Theme.font
                font.pixelSize: 24
                font.weight: Font.Bold
            }

            // 进行中：24 格刻度来回扫描
            Row {
                visible: !root.isError
                spacing: 4
                Repeater {
                    model: 24
                    Rectangle {
                        required property int index
                        width: (content.width - 23 * 4) / 24
                        height: 8
                        color: Math.abs(index - scan.pos) < 3 ? Theme.accent : Theme.hair
                        opacity: Math.abs(index - scan.pos) < 3 ? 1 : 0.5
                    }
                }
                QtObject {
                    id: scan
                    property real pos: 0
                    property NumberAnimation anim: NumberAnimation {
                        target: scan
                        property: "pos"
                        from: -3
                        to: 26
                        duration: 1600
                        loops: Animation.Infinite
                        running: root.shown && !root.isError
                    }
                }
            }

            Rectangle {
                visible: root.isError && !!root.backend && root.backend.message !== ""
                width: content.width
                height: errText.implicitHeight + 20
                color: Theme.dark ? Qt.rgba(0.85, 0.41, 0.37, 0.12) : Qt.rgba(0.71, 0.27, 0.24, 0.08)
                Rectangle { width: 3; height: parent.height; color: Theme.error }
                Text {
                    id: errText
                    x: 14
                    y: 10
                    width: parent.width - 28
                    wrapMode: Text.Wrap
                    text: root.backend ? root.backend.message : ""
                    color: Theme.ink
                    font.family: Theme.font
                    font.pixelSize: 14
                }
            }

            Row {
                width: content.width
                Text {
                    width: parent.width - toggle.width
                    text: qsTr("启动日志") + "  " + (root.backend ? root.backend.logs.length : 0)
                    color: Theme.muted
                    font.family: Theme.font
                    font.pixelSize: 12
                    font.letterSpacing: 1
                }
                Text {
                    id: toggle
                    text: root.logsOpen ? qsTr("收起") : qsTr("展开")
                    color: Theme.amber
                    font.family: Theme.font
                    font.pixelSize: 12
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.logsOpen = !root.logsOpen }
                }
            }

            ListView {
                id: logView
                visible: root.logsOpen
                width: content.width
                height: 200
                clip: true
                model: root.backend ? root.backend.logs : []
                onCountChanged: positionViewAtEnd()
                ScrollBar.vertical: ScrollBar {}
                delegate: Text {
                    required property var modelData
                    width: logView.width - 12
                    wrapMode: Text.WrapAnywhere
                    text: modelData.text
                    color: modelData.level === "ERROR" || modelData.level === "CRITICAL" ? Theme.error
                        : modelData.level === "WARNING" ? Theme.warning
                        : modelData.level === "SUCCESS" ? Theme.success : Theme.muted
                    font.family: "Consolas"
                    font.pixelSize: 11
                }
                Rectangle {
                    anchors.fill: parent
                    z: -1
                    color: Theme.bg
                }
            }

            Row {
                visible: root.isError
                spacing: 12
                Rectangle {
                    width: retryText.implicitWidth + 40
                    height: 40
                    color: retryMouse.containsMouse ? Theme.amber : Theme.ink
                    Text {
                        id: retryText
                        anchors.centerIn: parent
                        text: qsTr("重新连接")
                        color: Theme.paper
                        font.family: Theme.font
                        font.pixelSize: 14
                        font.weight: Font.Bold
                    }
                    MouseArea {
                        id: retryMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.backend.retry()
                    }
                }
            }
        }
    }
}
