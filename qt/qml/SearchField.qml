import QtQuick
import QtQuick.Controls.Basic as C
import "."

// 二级页面右上的搜索框：与「RETURN TO INDEX」同一样式（透明底、1.5 线框、粗体字距），输入内容时收窄字距。
// badge：右侧的小字（如「2 / 5」「无匹配」），miss 为真时转为错误色。
C.TextField {
    id: field
    property string badge: ""
    property bool miss: false
    signal leave()
    placeholderText: "SEARCH"
    leftPadding: 38
    rightPadding: badgeText.text ? badgeText.implicitWidth + 22 : 12
    selectByMouse: true
    font.family: Theme.font
    font.pixelSize: 13
    font.weight: Font.Bold
    font.letterSpacing: text ? 1 : 3.6
    color: Theme.ink
    placeholderTextColor: Theme.ink
    selectionColor: Theme.accent
    selectedTextColor: "#ffffff"
    verticalAlignment: TextInput.AlignVCenter
    background: Rectangle {
        color: field.activeFocus ? Qt.rgba(Theme.paper.r, Theme.paper.g, Theme.paper.b, 0.85) : "transparent"
        border.color: field.miss && field.text ? Theme.error : field.activeFocus ? Theme.accent : Theme.ink
        border.width: 1.5
    }
    Item {
        x: 14; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16
        Rectangle { width: 11; height: 11; radius: 6; color: "transparent"; border.color: field.activeFocus ? Theme.accent : Theme.ink; border.width: 1.5 }
        Rectangle { x: 9.5; y: 9.5; width: 6; height: 1.5; rotation: 45; transformOrigin: Item.Left; color: field.activeFocus ? Theme.accent : Theme.ink }
    }
    Text {
        id: badgeText
        anchors.right: parent.right; anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        text: field.text ? field.badge : ""
        color: field.miss && field.text ? Theme.error : Theme.accent
        font.family: Theme.font; font.pixelSize: 11; font.weight: Font.Bold; font.letterSpacing: 1
    }
    Keys.onEscapePressed: { clear(); leave() }
}
