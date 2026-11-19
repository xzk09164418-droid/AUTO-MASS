import QtQuick
import "."

// 底部刻度栏：SESSION、01–10 编号刻度、当前部门、后端状态、时钟、署名。
Item {
    id: ledger

    property var departments: []
    property int current: 0
    property string backendStatus: ""

    signal picked(int index)
    signal hoveredIndex(int index)

    height: 56

    readonly property var statusText: ({
        "": "OFFLINE PREVIEW",
        "probing": "LINK // PROBING",
        "starting": "LINK // BOOTING",
        "ready": "LINK // ESTABLISHED",
        "error": "LINK // FAILED"
    })
    readonly property color statusColor: backendStatus === "ready" ? Theme.success
        : backendStatus === "error" ? Theme.error
        : backendStatus === "" ? Theme.muted : Theme.warning

    component LedgerText: Text {
        color: Theme.muted
        font.family: Theme.font
        font.pixelSize: 12
        font.weight: Font.DemiBold
        font.letterSpacing: 2.4
    }

    Row {
        anchors.left: parent.left
        anchors.leftMargin: 48
        anchors.verticalCenter: parent.verticalCenter
        spacing: 28

        Rectangle { width: 26; height: 26; color: Theme.muted; anchors.verticalCenter: parent.verticalCenter }
        LedgerText { text: "SESSION ● AUTHORIZED"; anchors.verticalCenter: parent.verticalCenter }

        Row {
            spacing: 22
            anchors.verticalCenter: parent.verticalCenter
            Repeater {
                model: ledger.departments
                Item {
                    required property var modelData
                    required property int index
                    width: 22
                    height: 30
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.n + " " + modelData.zh
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: -6
                        text: modelData.n
                        color: Theme.muted
                        font.family: Theme.font
                        font.pixelSize: 9
                        font.weight: Font.DemiBold
                    }
                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.bottom: parent.bottom
                        width: 2
                        height: ledger.current === index ? 22 : 10
                        color: ledger.current === index ? Theme.accent : Theme.hair
                        Behavior on height { NumberAnimation { duration: 180 } }
                    }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onContainsMouseChanged: if (containsMouse) ledger.hoveredIndex(index)
                        onClicked: ledger.picked(index)
                    }
                }
            }
        }

        LedgerText {
            anchors.verticalCenter: parent.verticalCenter
            readonly property var d: ledger.departments[ledger.current]
            text: d ? "X-0" + d.n + "  " + d.zh : ""
            color: Theme.ink
        }
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: 48
        anchors.verticalCenter: parent.verticalCenter
        spacing: 28

        Row {
            spacing: 8
            anchors.verticalCenter: parent.verticalCenter
            Rectangle {
                width: 8; height: 8; radius: 4
                anchors.verticalCenter: parent.verticalCenter
                color: ledger.statusColor
            }
            LedgerText { text: ledger.statusText[ledger.backendStatus] || ledger.backendStatus.toUpperCase() }
        }
        LedgerText {
            id: clock
            anchors.verticalCenter: parent.verticalCenter
            text: Qt.formatTime(new Date(), "HH:mm:ss")
            Timer {
                interval: 1000
                repeat: true
                running: ledger.visible
                onTriggered: clock.text = Qt.formatTime(new Date(), "HH:mm:ss")
            }
        }
        LedgerText { text: "POWERED BY AUTO-MAS"; anchors.verticalCenter: parent.verticalCenter }
    }
}
