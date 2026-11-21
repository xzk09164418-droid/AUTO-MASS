import QtQuick
import QtQuick.Controls.Basic as C
import "."

// 刻度翻页条（取自主页任务对象）：当前页是一根高的橙色刻度并标出页码，其余页按与当前页的距离疏密排开。
// 列表超出一页时用它翻页，不再滚动。pageIndex 为目标页，visualPage 为动画中的连续页坐标。
Item {
    id: scaleBar
    property int pages: 1
    property int pageIndex: 0
    property real visualPage: pageIndex
    onPagesChanged: pageIndex = Math.max(0, Math.min(pageIndex, pages - 1))

    component PageTransition: NumberAnimation {
        duration: 300
        easing.type: Easing.BezierSpline
        easing.bezierCurve: [0.22, 0.68, 0.18, 1, 1, 1]
    }
    Behavior on visualPage { enabled: Theme.richMotion; PageTransition {} }

    // 滚轮逐格翻页：触控板的连续位移累积到一格再翻
    property real wheelRemainder: 0
    function turnWheel(pixelDelta, angleDelta) {
        if (!pixelDelta && !angleDelta) return false
        const delta = pixelDelta ? pixelDelta / 48 : angleDelta / 120
        if (wheelRemainder * delta < 0) wheelRemainder = 0
        wheelRemainder += delta
        const steps = Math.trunc(wheelRemainder)
        wheelRemainder -= steps
        pageIndex = Math.max(0, Math.min(pages - 1, pageIndex - steps))
        resetWheel.restart()
        return true
    }
    Timer { id: resetWheel; interval: 250; onTriggered: scaleBar.wheelRemainder = 0 }

    visible: pages > 1
    height: 40
    readonly property real tickWidth: 2
    readonly property int count: Math.min(pages, Math.max(2, Math.floor(width / 10)))
    readonly property int first: Math.max(0, Math.min(pages - count, Math.round(visualPage) - Math.floor(count / 2)))
    // 相邻刻度的净距按二项概率分配；预留最小间隙，使尾部仍可逐页点击。
    readonly property var positions: {
        if (count < 2) return [0]
        const gaps = count - 1
        const p = (visualPage - first + 0.5) / count
        const weights = [Math.pow(1 - p, gaps - 1)]
        for (let k = 1; k < gaps; k++)
            weights.push(weights[k - 1] * (gaps - k) / k * p / (1 - p))
        const free = width - count * tickWidth
        const minimum = Math.min(6, free / gaps)
        const weighted = free - minimum * gaps
        const points = [0]
        for (let i = 0; i < gaps - 1; i++)
            points.push(points[i] + tickWidth + minimum + weighted * weights[i])
        points.push(width - tickWidth)
        return points
    }

    Repeater {
        model: scaleBar.count
        C.AbstractButton {
            id: tick
            required property int index
            readonly property int number: scaleBar.first + index + 1
            readonly property bool current: number === scaleBar.pageIndex + 1
            readonly property real center: scaleBar.positions[index] + scaleBar.tickWidth / 2
            x: index === 0 ? 0 : (center + scaleBar.positions[index - 1] + scaleBar.tickWidth / 2) / 2
            width: (index === scaleBar.count - 1 ? scaleBar.width
                   : (center + scaleBar.positions[index + 1] + scaleBar.tickWidth / 2) / 2) - x
            padding: 0
            height: 40
            Accessible.name: "第 " + number + " 页，共 " + scaleBar.pages + " 页"
            Accessible.selected: current
            C.ToolTip.visible: hovered && !current
            C.ToolTip.delay: 300
            C.ToolTip.text: "第 " + number + " 页"
            onClicked: scaleBar.pageIndex = number - 1
            contentItem: Item {
                Text {
                    x: Math.max(0, Math.min(scaleBar.width - width, tick.center - width / 2)) - tick.x
                    visible: tick.current
                    y: 1
                    text: String(tick.number).padStart(2, "0")
                    font.family: Theme.font
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    color: tick.hovered || tick.visualFocus ? Theme.accent : Theme.muted
                }
                Rectangle {
                    x: scaleBar.positions[tick.index] - tick.x
                    anchors.bottom: parent.bottom
                    width: scaleBar.tickWidth
                    height: tick.current ? 22 : 10
                    color: tick.current ? Theme.accent : Theme.hair
                    Behavior on height { enabled: Theme.richMotion; PageTransition {} }
                    Behavior on color { enabled: Theme.richMotion; ColorAnimation { duration: 180 } }
                }
            }
        }
    }
}
