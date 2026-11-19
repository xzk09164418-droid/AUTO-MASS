import QtQuick
import "."

// 二级界面容器：从被点击的方块原地展开成整屏，Esc / 返回按钮收回原位。
// 各部门的二级界面下一轮再设计，这里先放占位。
FocusScope {
    id: host

    property var departments: []
    property int index: -1
    property rect origin: Qt.rect(0, 0, 0, 0)
    property bool opened: false
    readonly property bool busy: panel.visible
    readonly property var d: index >= 0 ? departments[index] : null

    signal closed()

    function open(i, r) {
        index = i
        origin = r
        panel.x = r.x; panel.y = r.y; panel.width = r.width; panel.height = r.height
        panel.visible = true
        opened = true
        closeAnim.stop()
        openAnim.restart()
        forceActiveFocus()
    }

    function close() {
        if (!opened) return
        opened = false
        openAnim.stop()
        closeAnim.restart()
    }

    Keys.onEscapePressed: close()

    Rectangle {
        id: panel
        visible: false
        color: host.opened ? Theme.paper : Theme.block
        clip: true
        Behavior on color { ColorAnimation { duration: 380 } }

        Item {
            id: body
            anchors.fill: parent
            anchors.margins: 0
            opacity: host.opened ? 1 : 0
            Behavior on opacity {
                SequentialAnimation {
                    PauseAnimation { duration: host.opened ? 420 : 0 }
                    NumberAnimation { duration: 220 }
                }
            }

            Item {
                x: 96
                y: 72
                width: parent.width - 192
                height: parent.height - 144

                Row {
                    id: head
                    spacing: 28
                    Text {
                        anchors.baseline: code.baseline
                        text: host.d ? host.d.n : ""
                        color: Theme.muted
                        font.family: Theme.font
                        font.pixelSize: 64
                        font.weight: Font.Light
                    }
                    Text {
                        id: code
                        text: host.d ? host.d.code.replace("\n", " ") : ""
                        color: Theme.ink
                        font.family: Theme.font
                        font.pixelSize: 88
                        font.weight: Font.Black
                    }
                    Text {
                        anchors.baseline: code.baseline
                        text: host.d ? host.d.zh : ""
                        color: Theme.ink
                        font.family: Theme.font
                        font.pixelSize: 32
                        font.weight: Font.Bold
                        font.letterSpacing: 6
                    }
                }
                Rectangle {
                    anchors.top: head.bottom
                    anchors.topMargin: 18
                    width: parent.width
                    height: 2
                    color: Theme.ink
                }

                Rectangle {
                    id: back
                    anchors.right: parent.right
                    y: 16
                    width: backText.implicitWidth + 44
                    height: 46
                    color: backMouse.containsMouse || back.activeFocus ? Theme.ink : "transparent"
                    border.width: 1.5
                    border.color: Theme.ink
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Button
                    Accessible.name: qsTr("返回一级界面")
                    Keys.onReturnPressed: host.close()
                    Text {
                        id: backText
                        anchors.centerIn: parent
                        text: "← RETURN TO INDEX"
                        color: backMouse.containsMouse || back.activeFocus ? Theme.paper : Theme.ink
                        font.family: Theme.font
                        font.pixelSize: 15
                        font.weight: Font.Bold
                        font.letterSpacing: 4
                    }
                    MouseArea {
                        id: backMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: host.close()
                    }
                }

                Text {
                    id: note
                    y: head.height + 64
                    text: qsTr("二级界面将在下一轮设计。")
                    color: Theme.muted
                    font.family: Theme.font
                    font.pixelSize: 22
                    font.letterSpacing: 2
                }

                Grid {
                    anchors.top: note.bottom
                    anchors.topMargin: 40
                    columns: 3
                    Repeater {
                        model: 6
                        Rectangle {
                            required property int index
                            width: (body.width - 192) / 3
                            height: 180
                            color: "transparent"
                            border.width: 1
                            border.color: Theme.hair
                            Text {
                                x: 18
                                y: 18
                                text: "MODULE A-0" + (index + 1)
                                color: Theme.muted
                                font.family: Theme.font
                                font.pixelSize: 13
                                font.letterSpacing: 2.6
                            }
                        }
                    }
                }
            }
        }
    }

    ParallelAnimation {
        id: openAnim
        NumberAnimation { target: panel; property: "x"; to: 0; duration: 550; easing.type: Easing.InOutQuart }
        NumberAnimation { target: panel; property: "y"; to: 0; duration: 550; easing.type: Easing.InOutQuart }
        NumberAnimation { target: panel; property: "width"; to: host.width; duration: 550; easing.type: Easing.InOutQuart }
        NumberAnimation { target: panel; property: "height"; to: host.height; duration: 550; easing.type: Easing.InOutQuart }
    }

    SequentialAnimation {
        id: closeAnim
        PauseAnimation { duration: 120 }
        ParallelAnimation {
            NumberAnimation { target: panel; property: "x"; to: host.origin.x; duration: 520; easing.type: Easing.InOutQuart }
            NumberAnimation { target: panel; property: "y"; to: host.origin.y; duration: 520; easing.type: Easing.InOutQuart }
            NumberAnimation { target: panel; property: "width"; to: host.origin.width; duration: 520; easing.type: Easing.InOutQuart }
            NumberAnimation { target: panel; property: "height"; to: host.origin.height; duration: 520; easing.type: Easing.InOutQuart }
        }
        ScriptAction {
            script: {
                panel.visible = false
                host.closed()
            }
        }
    }
}
