import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic as C
import "."

// 菜单在档案卡的视觉树内展开，两层文字共用卡片的缩放和透视。
// 全部下拉（档案卡字段、表格单元格、二级页面）统一用它，视觉一致。
C.AbstractButton {
    id: field
    required property Item card
    required property var options
    required property int selectedIndex
    signal picked(int index)
    property string label: "完成后"                 // 读屏用的字段名
    property real minWidth: 0
    property bool expanded: false
    property var menuIndexes: []
    property int keyboardRow: -1
    property int hoverRow: -1
    property real reveal: expanded ? 1 : 0
    property real outlineOrigin: 0.5
    readonly property bool fullyOpen: expanded && reveal === 1
    readonly property var labelWidths: options.map(label => metrics.advanceWidth(label))
    readonly property real shortestLabel: labelWidths.length ? Math.min(...labelWidths) : 0
    readonly property real longestLabel: Math.max(0, ...labelWidths)
    readonly property int lineRow: keyboardRow >= 0 ? keyboardRow : hoverRow
    readonly property int lineIndex: fullyOpen && lineRow >= 0 ? menuIndexes[lineRow] : selectedIndex
    readonly property real maximumLineWidth: width * 0.8
    readonly property real minimumLineWidth: {
        const shortest = options[labelWidths.indexOf(shortestLabel)]
        if (!shortest) return 0
        const letters = Array.from(shortest)
        const lastCharWidth = metrics.advanceWidth(letters[letters.length - 1])
        // 线条居中，左端至少延伸到最短文字的最后一个字下方。
        return Math.min(maximumLineWidth, Math.max(lastCharWidth, width - 2 * (shortestLabel - lastCharWidth)))
    }
    property real lineWidth: openLineWidth(lineIndex)
    Behavior on lineWidth {
        enabled: Theme.richMotion
        NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
    }
    Behavior on reveal {
        enabled: Theme.richMotion
        NumberAnimation { duration: 180; easing.type: Easing.Linear }
    }
    font.family: Theme.font
    font.pixelSize: 15
    implicitWidth: Math.max(minWidth, Math.ceil(longestLabel))
    implicitHeight: 30
    padding: 0
    text: options[selectedIndex] || ""
    Accessible.role: Accessible.ComboBox
    Accessible.name: label + "：" + text

    function openLineWidth(index) {
        const span = longestLabel - shortestLabel
        const position = span > 0 && index >= 0 && index < labelWidths.length
            ? (labelWidths[index] - shortestLabel) / span : 0
        return minimumLineWidth + position * (maximumLineWidth - minimumLineWidth)
    }
    function openMenu() {
        if (options.length < 2) return
        if (reveal === 0) outlineOrigin = Math.random()
        menuIndexes = options.map((_, i) => i).filter(i => i !== selectedIndex)
        keyboardRow = -1
        hoverRow = -1
        const at = field.mapToItem(card, 0, 0)
        menu.x = at.x
        menu.y = at.y + height
        forceActiveFocus()
        expanded = true
    }
    function choose(index) {
        expanded = false
        picked(index)
    }
    onClicked: expanded ? expanded = false : openMenu()
    onHoveredChanged: if (hovered) {
        hoverRow = -1
        keyboardRow = -1
    }
    onActiveFocusChanged: if (!activeFocus) expanded = false
    onVisibleChanged: if (!visible) expanded = false
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Up || event.key === Qt.Key_Down) {
            if (!expanded) openMenu()
            const last = menuIndexes.length - 1
            if (last >= 0) keyboardRow = keyboardRow < 0 ? (event.key === Qt.Key_Down ? 0 : last)
                : Math.max(0, Math.min(last, keyboardRow + (event.key === Qt.Key_Down ? 1 : -1)))
        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) {
            if (expanded && keyboardRow >= 0) choose(menuIndexes[keyboardRow])
            else if (expanded) expanded = false
            else openMenu()
        } else if (event.key === Qt.Key_Escape && expanded) expanded = false
        else { event.accepted = false; return }
        event.accepted = true
    }
    FontMetrics { id: metrics; font: field.font }
    contentItem: Text {
        text: field.text
        font: field.font
        color: Theme.ink
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        rightPadding: 14
    }
    background: Rectangle {
        color: field.reveal > 0 || field.expanded ? Theme.paper : "transparent"
        Text {
            readonly property bool besideLabel: field.contentItem.contentWidth + 13 <= parent.width
            anchors.right: parent.right
            y: besideLabel ? (parent.height - height) / 2 : parent.height - height - 1
            text: "▾"
            font.pixelSize: besideLabel ? 13 : 9
            color: field.hovered || field.activeFocus ? Theme.accent : Theme.ink
        }
        Rectangle {
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.alignWhenCentered: false
            width: field.width + (field.lineWidth - field.width) * field.reveal
            visible: !field.fullyOpen || (field.hovered && field.keyboardRow < 0)
            height: 1.5
            color: Theme.accent
        }
    }

    Rectangle {
        id: menu
        parent: field.card
        visible: field.visible && field.reveal > 0
        enabled: field.expanded
        clip: true
        z: 19
        width: field.width
        height: field.menuIndexes.length * field.height * field.reveal
        border.width: 0
        color: Theme.paper
        Column {
            anchors.bottom: parent.bottom
            width: parent.width
            Repeater {
                model: field.menuIndexes
                C.AbstractButton {
                    id: option
                    required property int modelData
                    required property int index
                    width: menu.width
                    height: field.height
                    padding: 0
                    focusPolicy: Qt.NoFocus
                    text: field.options[modelData]
                    Accessible.role: Accessible.ListItem
                    onHoveredChanged: if (hovered) {
                        field.hoverRow = index
                        field.keyboardRow = -1
                    }
                    onClicked: field.choose(modelData)
                    background: Item {
                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.alignWhenCentered: false
                            width: field.lineWidth
                            height: 1.5
                            color: Theme.accent
                            visible: field.fullyOpen && (field.keyboardRow >= 0 ? field.keyboardRow === option.index : option.hovered)
                        }
                    }
                    contentItem: Text {
                        text: field.options[modelData]
                        font: field.font
                        color: Theme.ink
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }
    // 外框和柔边共用一条路径，画在独立层上，随卡片一同缩放和倾斜。
    Canvas {
        id: outline
        parent: field.card
        readonly property real progress: field.reveal
        readonly property color ink: Theme.block
        readonly property int margin: 5
        x: menu.x - margin - 1
        y: menu.y - field.height - margin - 1
        width: menu.width + 2 * (margin + 1)
        height: field.height * (1 + field.menuIndexes.length) + 2 * (margin + 1)
        visible: menu.visible
        z: menu.z + 1
        onProgressChanged: requestPaint()
        onInkChanged: requestPaint()
        onVisibleChanged: if (visible) requestPaint()
        onPaint: {
            const ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            const left = margin, right = width - margin
            const top = margin, bottom = top + field.height + menu.height + 2
            const origin = left + (right - left) * field.outlineOrigin
            const across = Math.min(1, progress / 0.3)
            const topLeft = origin + (left - origin) * across
            const topRight = origin + (right - origin) * across
            const side = (bottom - top) * Math.max(0, Math.min(1, (progress - 0.3) / 0.55))
            const halfBottom = (right - left) / 2 * Math.max(0, (progress - 0.85) / 0.15)
            ctx.beginPath()
            ctx.moveTo(topLeft + halfBottom, top + side)
            ctx.lineTo(topLeft, top + side)
            ctx.lineTo(topLeft, top)
            ctx.lineTo(topRight, top)
            ctx.lineTo(topRight, top + side)
            ctx.lineTo(topRight - halfBottom, top + side)
            ctx.strokeStyle = ink
            for (const [weight, alpha] of [[7, 0.04], [5, 0.08], [3, 0.14]]) {
                ctx.lineWidth = weight
                ctx.globalAlpha = alpha
                ctx.stroke()
            }
            // 擦除当前框内的柔边，再绘制清晰的框线。此画布只承载外框。
            ctx.clearRect(left, top, right - left, bottom - top)
            ctx.lineWidth = 1
            ctx.globalAlpha = 0.9
            ctx.stroke()
            ctx.globalAlpha = 1
        }
    }
    TapHandler {
        parent: field.Window.window ? field.Window.window.contentItem : null
        enabled: field.expanded
        onPressedChanged: {
            if (!pressed) return
            const p = point.position
            if (!menu.contains(menu.mapFromItem(parent, p)) && !field.contains(field.mapFromItem(parent, p)))
                field.expanded = false
        }
    }
}
