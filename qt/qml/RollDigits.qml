import QtQuick
import "."

// 逐位滚动：只有变化的字符滚动（时钟、编号）。
Row {
    id: rd

    property string text: ""
    property int dir: 1
    property bool live: true
    property color color: Theme.ink
    property font font
    property int style: Text.Normal
    property color styleColor: "transparent"

    Accessible.role: Accessible.StaticText
    Accessible.name: text

    Repeater {
        model: rd.text.length
        RollText {
            required property int index
            text: rd.text.charAt(index)
            dir: rd.dir
            live: rd.live
            color: rd.color
            font: rd.font
            style: rd.style
            styleColor: rd.styleColor
        }
    }
}
