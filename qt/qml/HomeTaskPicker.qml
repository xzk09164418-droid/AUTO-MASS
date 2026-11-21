import QtQuick
import QtQuick.Controls.Basic as C
import "."

Column {
    id: picker
    required property real cardWidth
    required property var options
    required property var selected
    signal toggled(string value)
    property alias pageIndex: pageScale.pageIndex
    readonly property int pageSize: 6
    readonly property int pages: Math.ceil(options.length / pageSize)
    // 列表位移和刻度分布共用连续页坐标，连续翻页时从当前画面接续。
    readonly property real visualPage: pageScale.visualPage
    function turnWheel(pixelDelta, angleDelta) { pageScale.turnWheel(pixelDelta, angleDelta) }

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
    PageScale {
        id: pageScale
        width: picker.cardWidth / 3
        pages: picker.pages
    }
}
