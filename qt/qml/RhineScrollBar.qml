import QtQuick
import QtQuick.Controls.Basic as C
import "."

// 统一滚动条：细发丝轨道 + 方头滑块；悬停 / 拖动时加粗并转橙。onDark 用于常驻深底的区域（如日志块）。
C.ScrollBar {
    id: bar
    property bool onDark: false
    readonly property bool isVertical: orientation === Qt.Vertical
    readonly property bool hot: hovered || pressed
    readonly property color handle: onDark ? "#d9d6cf" : Theme.ink
    padding: 2
    minimumSize: 0.08
    implicitWidth: isVertical ? 12 : 100
    implicitHeight: isVertical ? 100 : 12
    background: Item {
        Rectangle {
            visible: bar.size < 1
            x: bar.isVertical ? (parent.width - width) / 2 : 0
            y: bar.isVertical ? 0 : (parent.height - height) / 2
            width: bar.isVertical ? 1 : parent.width
            height: bar.isVertical ? parent.height : 1
            color: bar.onDark ? "#d9d6cf" : Theme.hair
            opacity: 0.45
        }
    }
    contentItem: Item {
        implicitWidth: 6; implicitHeight: 6
        Rectangle {
            property real thick: bar.hot ? 5 : 3
            x: bar.isVertical ? (parent.width - width) / 2 : 0
            y: bar.isVertical ? 0 : (parent.height - height) / 2
            width: bar.isVertical ? thick : parent.width
            height: bar.isVertical ? parent.height : thick
            color: bar.pressed ? Theme.accent : bar.hot ? Qt.lighter(Theme.accent, 1.08) : bar.handle
            opacity: bar.policy === C.ScrollBar.AlwaysOn || bar.active || bar.hot ? (bar.hot ? 1 : 0.7) : 0
            Behavior on opacity { NumberAnimation { duration: 180 } }
            Behavior on thick { NumberAnimation { duration: 120 } }
            Behavior on color { ColorAnimation { duration: 120 } }
            // 滑块顶端的橙色刻度，呼应页签与刻度条
            Rectangle {
                visible: bar.isVertical
                anchors.horizontalCenter: parent.horizontalCenter
                width: 7; height: 2; color: Theme.accent
            }
        }
    }
}
