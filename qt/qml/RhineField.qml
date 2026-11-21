import QtQuick
import QtQuick.Controls.Basic as C
import "."

// 二级页面用输入框：与档案卡输入框同一样式（只有下划线，聚焦转橙）
C.TextField {
    id: fld
    property bool mono: false
    font.family: mono ? "Consolas" : Theme.font
    font.pixelSize: mono ? 14 : 15
    color: Theme.ink
    selectionColor: Theme.accent
    selectedTextColor: "#ffffff"
    placeholderTextColor: Theme.muted
    selectByMouse: true
    leftPadding: 2; rightPadding: 2; topPadding: 4; bottomPadding: 4
    implicitHeight: 32
    background: Rectangle {
        color: "transparent"
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1.5; color: fld.activeFocus ? Theme.accent : fld.hovered ? Theme.ink : Theme.hair }
    }
}
