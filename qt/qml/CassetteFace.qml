import QtQuick
import "."

Item {
    id: tape
    required property var record
    required property string code
    property real emphasis: 1
    property real alpha: 1
    property bool highlighted: false
    width: 260; height: 170
    Rectangle {
        anchors.fill: parent
        radius: 7
        color: Theme.dark ? "#3a474c" : "#f3f1ec"
        border.width: 1.5
        border.color: tape.highlighted ? Theme.accent : Theme.dark ? "#6d7b80" : "#9e9a90"
        opacity: Math.min(0.8, 0.32 + 0.48 * tape.emphasis + (tape.highlighted ? 0.12 : 0)) * tape.alpha
    }
    Item {
        anchors.fill: parent
        opacity: (0.75 + 0.25 * tape.emphasis) * tape.alpha
        Rectangle {
            x: 7; y: 7
            width: parent.width - 14; height: parent.height - 14
            color: Qt.rgba(1, 1, 1, Theme.dark ? 0.08 : 0.35)
            border.width: 1
            border.color: Qt.rgba(0.16, 0.16, 0.14, 0.28)
        }
        Repeater {
            model: [Qt.point(15, 15), Qt.point(245, 15), Qt.point(15, 155), Qt.point(245, 155)]
            Rectangle { required property point modelData; x: modelData.x - 2.5; y: modelData.y - 2.5; width: 5; height: 5; radius: 2.5; color: Qt.rgba(0.16, 0.16, 0.14, 0.5) }
        }
        // 有启动程序时显示程序图标唱片，否则按所属部门（编号前两位）显示对应的默认标志
        readonly property string iconPath: tape.record ? tape.record.icon || "" : ""
        readonly property var logos: ["01_archive", "02_custody", "03_emulator", "04_queue", "05_scheduler",
            "06_local", "07_sign", "08_history", "09_activity", "10_settings"]
        readonly property string logo: logos[parseInt(tape.code) - 1] || "11_cassette"
        IconDisc { visible: parent.iconPath !== ""; x: 20; y: 30; width: 100; height: 100; path: parent.iconPath }
        Image {
            visible: parent.iconPath === ""
            x: 14; y: 24
            width: 112; height: 112
            source: Qt.resolvedUrl("../assets/logos/png/" + parent.logo + ".png")
            sourceSize: Qt.size(256, 256)
            fillMode: Image.PreserveAspectFit
            smooth: true; mipmap: true
            opacity: 0.92
        }
        Column {
            visible: !!tape.record
            x: 134; y: 48
            spacing: 6
            Text { text: tape.code; color: Theme.ink; opacity: 0.85; font.family: Theme.font; font.pixelSize: 15; font.weight: Font.Bold }
            Text {
                width: 116
                elide: Text.ElideRight
                text: tape.record ? tape.record.name : ""
                color: Theme.ink
                font.family: Theme.font
                font.pixelSize: 19
                font.weight: Font.Bold
            }
            Rectangle { width: 96; height: 2; color: Theme.ink; opacity: 0.45 }
        }

    }

}
