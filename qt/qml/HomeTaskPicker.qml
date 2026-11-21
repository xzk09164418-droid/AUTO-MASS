import QtQuick
import QtQuick.Controls.Basic as C
import "."

Column {
    id: picker
    required property real cardWidth
    required property var options
    required property var selected
    signal toggled(string value)
    property int pageIndex: 0
    readonly property int pageSize: 6
    readonly property int pages: Math.ceil(options.length / pageSize)
    onPagesChanged: pageIndex = Math.max(0, Math.min(pageIndex, pages - 1))

    // 列表位移和刻度分布共用连续页坐标，连续翻页时从当前画面接续。
    property real visualPage: pageIndex
    component PageTransition: NumberAnimation {
        duration: 300
        easing.type: Easing.BezierSpline
        easing.bezierCurve: [0.22, 0.68, 0.18, 1, 1, 1]
    }
    Behavior on visualPage { enabled: Theme.richMotion; PageTransition {} }

    property real wheelRemainder: 0
    function turnWheel(pixelDelta, angleDelta) {
        if (!pixelDelta && !angleDelta) return
        const delta = pixelDelta ? pixelDelta / 48 : angleDelta / 120
        if (wheelRemainder * delta < 0) wheelRemainder = 0
        wheelRemainder += delta
        const steps = Math.trunc(wheelRemainder)
        wheelRemainder -= steps
        pageIndex = Math.max(0, Math.min(pages - 1, pageIndex - steps))
        resetWheel.restart()
    }
    Timer { id: resetWheel; interval: 250; onTriggered: picker.wheelRemainder = 0 }

    Item {
        id: viewport
        width: parent.width
        height: Math.ceil(Math.min(picker.options.length, picker.pageSize) / 2) * 30
        clip: true
        Repeater {
            model: picker.pages
            Loader {
                id: page
                required property int index
                width: viewport.width
                height: viewport.height
                x: (index - picker.visualPage) * width
                active: Math.abs(index - picker.visualPage) < 1
                enabled: index === picker.pageIndex
                sourceComponent: Grid {
                    columns: 2
                    Repeater {
                        model: picker.options.slice(page.index * picker.pageSize, (page.index + 1) * picker.pageSize)
                        C.CheckBox {
                            required property var modelData
                            width: picker.width / 2
                            height: 30
                            leftPadding: 4
                            spacing: 8
                            text: modelData.label
                            checked: picker.selected.includes(modelData.value)
                            onClicked: picker.toggled(modelData.value)
                            indicator: Rectangle {
                                x: 4; y: (parent.height - height) / 2
                                width: 13; height: 13
                                color: parent.checked ? Theme.ink : "transparent"
                                border.color: parent.activeFocus ? Theme.accent : Theme.hair
                                Text { anchors.centerIn: parent; text: "✓"; visible: parent.parent.checked; color: Theme.paper; font.pixelSize: 11 }
                            }
                            contentItem: Text {
                                leftPadding: 22
                                text: parent.text
                                color: Theme.ink
                                font.family: Theme.font
                                font.pixelSize: 15
                                elide: Text.ElideRight
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle { color: parent.hovered ? Theme.grid : "transparent" }
                        }
                    }
                }
            }
        }
    }
    Text { visible: !picker.options.length; text: "没有可运行的任务"; color: Theme.muted; font.family: Theme.font; font.pixelSize: 15 }
    Item {
        id: scaleBar
        visible: picker.pages > 1
        width: picker.cardWidth / 3
        height: 40
        readonly property real tickWidth: 2
        readonly property int count: Math.min(picker.pages, Math.max(2, Math.floor(width / 10)))
        readonly property int first: Math.max(0, Math.min(picker.pages - count, Math.round(picker.visualPage) - Math.floor(count / 2)))
        // 相邻刻度的净距按二项概率分配；预留最小间隙，使尾部仍可逐页点击。
        readonly property var positions: {
            if (count < 2) return [0]
            const gaps = count - 1
            const p = (picker.visualPage - first + 0.5) / count
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
                readonly property bool current: number === picker.pageIndex + 1
                readonly property real center: scaleBar.positions[index] + scaleBar.tickWidth / 2
                x: index === 0 ? 0 : (center + scaleBar.positions[index - 1] + scaleBar.tickWidth / 2) / 2
                width: (index === scaleBar.count - 1 ? scaleBar.width
                       : (center + scaleBar.positions[index + 1] + scaleBar.tickWidth / 2) / 2) - x
                padding: 0
                height: 40
                Accessible.name: "第 " + number + " 页，共 " + picker.pages + " 页"
                Accessible.selected: current
                C.ToolTip.visible: hovered && !current
                C.ToolTip.delay: 300
                C.ToolTip.text: "第 " + number + " 页"
                onClicked: picker.pageIndex = number - 1
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
}
