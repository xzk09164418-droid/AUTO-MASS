import QtQuick
import "."

// 滚动文字（借鉴 RhineLabUI 的 Rolling Number）：text 变化时新字自下方滚入、旧字向上滚出，
// 宽度同步过渡（460ms）；dir = -1 时反向。live 为 false 或减少动态效果时直接替换。
// 快速连续输入只显示「当前所见 → 最新目标」一段过渡，不排队播放中间值。
Item {
    id: rt

    property string text: ""
    property int dir: 1
    property bool live: true
    property color color: Theme.ink
    property alias font: cur.font
    property int style: Text.Normal
    property color styleColor: "transparent"
    property int duration: 460

    property string shown: ""
    property real p: 1

    clip: true
    implicitHeight: cur.implicitHeight
    width: cur.implicitWidth
    height: implicitHeight
    Behavior on width {
        enabled: rt.live && Theme.richMotion
        NumberAnimation { duration: rt.duration; easing.type: Easing.OutCubic }
    }

    Component.onCompleted: shown = text
    onTextChanged: {
        if (text === shown) return
        if (!live || !Theme.richMotion || !visible) {
            anim.stop(); old.text = ""; shown = text; p = 1
            return
        }
        old.text = shown
        shown = text
        anim.restart()
    }

    NumberAnimation { id: anim; target: rt; property: "p"; from: 0; to: 1; duration: rt.duration; easing.type: Easing.OutCubic }

    Text {
        id: old
        y: -rt.dir * rt.height * rt.p
        opacity: 1 - rt.p
        visible: text !== "" && rt.p < 1
        color: rt.color
        font: cur.font
        style: rt.style
        styleColor: rt.styleColor
        Accessible.ignored: true
    }
    Text {
        id: cur
        y: rt.dir * rt.height * (1 - rt.p)
        opacity: rt.p
        text: rt.shown
        color: rt.color
        style: rt.style
        styleColor: rt.styleColor
    }
}
