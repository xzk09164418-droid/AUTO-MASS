import QtQuick
import "."

// 二级页面用按钮：与档案卡操作栏同一样式（线框、粗体字距；主按钮墨色底；悬停转橙）
Rectangle {
    id: btn
    property string text: ""
    property bool primary: false
    property bool danger: false
    property bool small: false
    signal clicked()
    readonly property bool hot: mouse.containsMouse && enabled
    implicitWidth: label.implicitWidth + (small ? 22 : 40)
    implicitHeight: small ? 30 : 40
    width: implicitWidth; height: implicitHeight
    opacity: enabled ? 1 : 0.35
    color: primary ? (hot ? Theme.accent : Theme.ink) : "transparent"
    border.width: 1.5
    border.color: hot ? (danger ? Theme.error : Theme.accent) : Theme.ink
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: text
    Keys.onReturnPressed: if (enabled) clicked()
    Keys.onSpacePressed: if (enabled) clicked()
    Rectangle { anchors.fill: parent; anchors.margins: -4; color: "transparent"; border.width: 2; border.color: Theme.accent; visible: btn.activeFocus }
    Text {
        id: label
        anchors.centerIn: parent
        text: btn.text
        color: btn.primary ? (btn.hot ? "#ffffff" : Theme.paper) : btn.hot ? (btn.danger ? Theme.error : Theme.accent) : Theme.ink
        font.family: Theme.font
        font.pixelSize: btn.small ? 12 : 14
        font.weight: Font.Bold
        font.letterSpacing: btn.small ? 1 : 2
    }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (btn.enabled) btn.clicked() }
}
