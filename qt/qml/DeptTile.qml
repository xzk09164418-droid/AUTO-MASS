import QtQuick
import "."

// 一级界面方块。d 为 Departments.list 中的一项；px/py 为视差偏移，intro 为入场进度。
Item {
    id: tile

    required property var d
    required property int index
    property real px: 0
    property real py: 0
    property real intro: 0
    property bool current: false
    property bool dimmed: false

    signal activated()
    signal hovered()

    readonly property bool isBlock: d.style === "block"
    readonly property bool isCard: d.style === "card"
    readonly property color textColor: isBlock ? Theme.blockText : Theme.ink
    readonly property bool hot: current || mouse.containsMouse || activeFocus

    width: d.w
    height: d.h
    x: d.x - d.w / 2 + px
    y: d.y - d.h / 2 + py
    z: hot ? 5 : 0
    opacity: intro * (dimmed && !hot ? 0.9 : 1) * (parent && parent.chrome !== undefined ? parent.chrome : 1)
    scale: (0.82 + 0.18 * intro) * (hot ? 1.05 : 1)
    activeFocusOnTab: true

    Behavior on scale { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
    Behavior on opacity { NumberAnimation { duration: 220 } }

    Accessible.role: Accessible.Button
    Accessible.name: d.n + " " + d.zh
    Keys.onReturnPressed: tile.activated()
    Keys.onEnterPressed: tile.activated()
    Keys.onSpacePressed: tile.activated()
    onActiveFocusChanged: if (activeFocus) tile.hovered()

    // 底：白卡带浅阴影，黑块带暗纹
    Rectangle {
        anchors.fill: parent
        visible: tile.isCard
        color: Theme.paper
        border.color: Qt.rgba(0, 0, 0, 0.05)
    }
    Rectangle {
        anchors.fill: parent
        visible: tile.isBlock
        gradient: Gradient {
            orientation: Gradient.Vertical
            GradientStop { position: 0; color: Theme.block }
            GradientStop { position: 0.55; color: Qt.lighter(Theme.block, 1.9) }
            GradientStop { position: 1; color: Theme.block }
        }
        border.width: tile.hot ? 2 : 0
        border.color: Theme.accent
    }
    Rectangle {
        anchors.fill: parent
        visible: tile.isCard && tile.hot
        color: "transparent"
        border.width: 2
        border.color: Theme.accent
    }

    DepartmentArt {
        department: tile.d.key
        layout: tile.d.art
        bleed: Math.min(tile.width, tile.height) * 0.18
        anchors.fill: parent
        anchors.margins: -bleed
        ink: tile.isBlock && !Theme.dark ? "#a9afb0" : tile.textColor
        accent: Theme.accent
        opacity: tile.isBlock ? 0.24 : 0.15
    }

    // PV 部门标旁的橙色角块
    Rectangle {
        visible: !!tile.d.accent
        width: 38
        height: 38
        x: parent.width - 16
        y: -26
        color: Theme.accent
        Rectangle { x: 12; y: 12; width: 14; height: 26; color: Theme.paper }
    }

    Text {
        visible: !tile.isCard && !tile.isBlock ? false : true
        x: 10
        y: 8
        text: tile.d.n
        color: tile.textColor
        opacity: 0.55
        font.family: Theme.font
        font.pixelSize: 12
        font.weight: Font.DemiBold
        font.letterSpacing: 1.2
    }

    Column {
        anchors.centerIn: parent
        spacing: 0

        Repeater {
            model: tile.d.code.split("\n")
            delegate: Item {
                required property string modelData
                required property int index
                anchors.horizontalCenter: parent.horizontalCenter
                width: codeText.implicitWidth
                height: codeText.font.pixelSize * 0.9
                Text {
                    id: codeText
                    anchors.centerIn: parent
                    text: modelData
                    color: tile.textColor
                    font.family: Theme.font
                    font.pixelSize: tile.d.size
                    font.weight: Font.Black
                    font.letterSpacing: -tile.d.size * 0.02
                }
            }
        }
        Item { width: 1; height: 8 }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: tile.d.sub
            color: tile.textColor
            font.family: Theme.font
            font.pixelSize: 11
            font.weight: Font.DemiBold
            font.letterSpacing: 0.6
        }
        Item { width: 1; height: 6 }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: tile.d.zh
            color: tile.textColor
            opacity: 0.72
            font.family: Theme.font
            font.pixelSize: 14
            font.weight: Font.DemiBold
            font.letterSpacing: 4
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onContainsMouseChanged: if (containsMouse) tile.hovered()
        onClicked: tile.activated()
    }
}
