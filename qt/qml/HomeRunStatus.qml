import QtQuick
import QtQuick.Controls.Basic as C
import "."

Item {
    id: status
    required property var runs
    property int latest: -1
    property int latestChild: 0
    function boundedY(y) {
        return Math.max(0, Math.min(list.contentHeight - list.height, y))
    }
    function scrollBy(amount) {
        if (bar.pressed) return
        followMotion.stop()
        list.contentY = boundedY(list.contentY + amount)
    }
    function follow() {
        if (pointer.hovered || bar.pressed || latest < 0 || latest >= groups.count) return
        const group = groups.itemAt(latest)
        if (!group) return
        const top = group.y + (group.split ? group.headingHeight + Math.min(latestChild, group.steps.count - 1) * 54 : 0)
        const y = boundedY(Math.min(top, Math.max(list.contentY, top + 54 - list.height)))
        if (followMotion.running && followMotion.to === y) return
        followMotion.stop()
        if (!Theme.richMotion) list.contentY = y
        else if (Math.abs(y - list.contentY) > 0.5) {
            followMotion.from = list.contentY
            followMotion.to = y
            followMotion.start()
        }
    }
    NumberAnimation { id: followMotion; target: list; property: "contentY"; duration: 180; easing.type: Easing.OutCubic }
    Connections {
        target: status.runs
        function onAdvanced(row, child) {
            status.latest = row
            status.latestChild = child
            Qt.callLater(status.follow)
        }
    }
    HoverHandler { id: pointer; onHoveredChanged: if (hovered) followMotion.stop() }
    Text { y: 6; text: runs.snapshotError || (runs.api && !runs.snapshotReady ? "正在同步…" : "待命"); visible: !groups.count || !!runs.snapshotError; color: Theme.muted; font.family: Theme.font; font.pixelSize: 15 }
    Flickable {
        id: list
        anchors.fill: parent
        anchors.topMargin: runs.snapshotError ? 26 : 0
        clip: true
        interactive: false
        contentWidth: width
        contentHeight: stack.implicitHeight
        boundsBehavior: Flickable.StopAtBounds
        C.ScrollBar.vertical: C.ScrollBar {
            id: bar
            policy: list.contentHeight > list.height ? C.ScrollBar.AlwaysOn : C.ScrollBar.AlwaysOff
            interactive: true
            onPressedChanged: if (pressed) followMotion.stop()
            width: 10
            contentItem: Rectangle { implicitWidth: 5; color: Theme.accent }
        }
        Column {
            id: stack
            width: list.width - 16
            Repeater {
                id: groups
                model: status.runs.rows
                delegate: Column {
                    id: group
                    required property string label
                    required property string status
                    required property real fraction
                    required property string phase
                    required property var steps
                    readonly property bool split: steps.count > 1
                    readonly property int headingHeight: 28
                    width: list.width - 16

                    Item {
                        visible: group.split
                        width: parent.width
                        height: group.headingHeight
                        Text { x: 4; width: parent.width - groupState.width - 12; text: group.label; elide: Text.ElideRight; color: Theme.ink; font.family: Theme.font; font.pixelSize: 15; font.bold: true }
                        Text { id: groupState; anchors.right: parent.right; text: group.phase === "ended" || group.status === "正在停止" ? group.status : group.steps.count + " 项"; color: Theme.muted; font.family: Theme.font; font.pixelSize: 13 }
                    }
                    ProgressLine {
                        visible: !group.split
                        title: group.label
                        stateText: group.status
                        progress: group.fraction
                    }
                    Repeater {
                        model: group.split ? group.steps : null
                        ProgressLine {
                            required property int index
                            required property string name
                            required property string state
                            required property string account
                            required property real progressValue
                            title: String(index + 1).padStart(2,"0") + "   " + name
                            stateText: group.phase === "ended" && !["完成","异常","跳过"].includes(state)
                                ? "队列已结束" : account && state === "运行" ? state + " · " + account : state
                            progress: progressValue
                            inset: 16
                        }
                    }
                }
            }
        }
    }

    component ProgressLine: Item {
        required property string title
        required property string stateText
        required property real progress
        property int inset: 4
        width: parent.width
        height: 54
        Text { id: nameText; x: inset; width: parent.width * 0.62 - inset; elide: Text.ElideRight; text: parent.title; color: Theme.ink; font.family: Theme.font; font.pixelSize: 15; font.bold: true }
        Text { anchors.left: nameText.right; anchors.right: parent.right; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight; text: parent.stateText; color: Theme.muted; font.family: Theme.font; font.pixelSize: 14 }
        Rectangle {
            x: parent.inset; y: 30; width: parent.width - x; height: 4; color: Theme.grid
            Rectangle { height: parent.height; width: parent.width * progress; color: Theme.accent }
        }
    }
}
