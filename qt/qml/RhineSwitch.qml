import QtQuick
import "."

// 二级页面用开关：与档案卡开关同一样式（方形滑块，开为橙色）
Item {
    id: sw
    property bool checked: false
    property string text: ""
    signal toggled()
    implicitWidth: track.width + 10 + label.implicitWidth
    implicitHeight: 24
    activeFocusOnTab: true
    Accessible.role: Accessible.CheckBox
    Accessible.checked: checked
    function flip() { checked = !checked; toggled() }
    Keys.onSpacePressed: flip()
    Rectangle {
        id: track
        anchors.verticalCenter: parent.verticalCenter
        width: 34; height: 16
        color: "transparent"; border.width: 1.5
        border.color: mouse.containsMouse || sw.activeFocus ? Theme.accent : Theme.ink
        Rectangle { y: 3; x: sw.checked ? 19 : 3; width: 11; height: 10; color: sw.checked ? Theme.accent : Theme.muted; Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } } }
    }
    Text { id: label; x: track.width + 10; anchors.verticalCenter: parent.verticalCenter; text: sw.text || (sw.checked ? "开" : "关"); color: Theme.ink; font.family: Theme.font; font.pixelSize: 14 }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: sw.flip() }
}
