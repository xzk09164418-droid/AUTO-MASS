import QtQuick
import QtQuick.Controls.Basic as C
import "."

// 弹出的二级页面统一外框（文件选择、清单编辑、配置编辑等）：
// 顶部橙色条、编号与分区代码、大标题、右上斜纹带与刻度、四角折角、底部编号栏，背景铺浅网格。
C.Popup {
    id: dialog
    property string code: ""            // 如 "CSTD / FILE SYSTEM"
    property string title: ""
    property string serial: "X-000"
    property string note: ""             // 标题右侧的小字（如当前数量）
    default property alias body: bodyArea.data
    parent: C.Overlay.overlay
    anchors.centerIn: parent
    modal: true
    focus: true
    padding: 0
    C.Overlay.modal: Component { Rectangle { color: Theme.dark ? Qt.rgba(0, 0, 0, 0.55) : Qt.rgba(0.12, 0.12, 0.11, 0.42) } }

    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.richMotion ? 220 : 0 }
            NumberAnimation { target: frameShift; property: "y"; from: 14; to: 0; duration: Theme.richMotion ? 300 : 0; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition { NumberAnimation { property: "opacity"; to: 0; duration: Theme.richMotion ? 160 : 0 } }

    background: Item {
        transform: Translate { id: frameShift }
        Rectangle { anchors.fill: parent; color: Theme.paper; border.width: 1.5; border.color: Theme.ink }
        // 浅网格
        Canvas {
            anchors.fill: parent; anchors.margins: 2
            opacity: 0.5
            onPaint: {
                const ctx = getContext("2d"); ctx.reset()
                ctx.strokeStyle = Theme.grid; ctx.lineWidth = 1
                for (let x = 40; x < width; x += 40) { ctx.beginPath(); ctx.moveTo(x + 0.5, 0); ctx.lineTo(x + 0.5, height); ctx.stroke() }
                for (let y = 40; y < height; y += 40) { ctx.beginPath(); ctx.moveTo(0, y + 0.5); ctx.lineTo(width, y + 0.5); ctx.stroke() }
            }
            Connections { target: Theme; function onDarkChanged() { parent.requestPaint() } }
        }
        Rectangle { width: parent.width; height: 4; color: Theme.accent }
        // 右上斜纹带
        Item {
            anchors.right: parent.right; anchors.rightMargin: 28; y: 24
            width: 132; height: 14; clip: true
            Repeater {
                model: 18
                Rectangle { required property int index; x: index * 9 - 10; y: -6; width: 3; height: 28; rotation: 35; color: Theme.ink; opacity: 0.85 }
            }
        }
        // 四角折角
        Repeater {
            model: 4
            Item {
                required property int index
                readonly property bool isRight: index % 2 === 1
                readonly property bool isBottom: index > 1
                x: isRight ? parent.width - 22 : 8; y: isBottom ? parent.height - 22 : 12
                width: 14; height: 14
                Rectangle { x: parent.isRight ? 12 : 0; width: 2; height: 14; color: Theme.ink }
                Rectangle { y: parent.isBottom ? 12 : 0; width: 14; height: 2; color: Theme.ink }
            }
        }
        // 底部编号栏
        Rectangle { x: 28; width: parent.width - 56; y: parent.height - 34; height: 1; color: Theme.hair }
        Text { x: 28; y: parent.height - 26; text: dialog.serial; color: Theme.accent; font.family: Theme.font; font.pixelSize: 10; font.weight: Font.Bold; font.letterSpacing: 2.4 }
        Text { anchors.right: parent.right; anchors.rightMargin: 28; y: parent.height - 26; text: "AUTO-MAS  //  ANALYSIS OS"; color: Theme.muted; font.family: Theme.font; font.pixelSize: 10; font.weight: Font.Bold; font.letterSpacing: 2.4 }
    }

    contentItem: Item {
        transform: Translate { y: frameShift.y }
        Text { x: 32; y: 26; text: dialog.code; color: Theme.accent; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Bold; font.letterSpacing: 2.8 }
        Row {
            x: 32; y: 46; spacing: 16
            Text { id: titleText; text: dialog.title; color: Theme.ink; font.family: Theme.font; font.pixelSize: 28; font.weight: Font.Bold; font.letterSpacing: 1.4 }
            Text { anchors.baseline: titleText.baseline; text: dialog.note; color: Theme.muted; font.family: Theme.font; font.pixelSize: 13; font.letterSpacing: 1.2 }
        }
        Rectangle { x: 32; y: 92; width: 36; height: 2; color: Theme.ink }
        Item {
            id: bodyArea
            x: 32; y: 108
            width: parent.width - 64
            height: parent.height - y - 46
        }
    }
}
