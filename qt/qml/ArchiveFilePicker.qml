import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import Qt.labs.folderlistmodel
import "."

// 文件 / 目录选择：莱茵生命风格的二级页面。列表按页显示（刻度翻页条，滚轮翻页），不滚动。
RhineDialog {
    id: picker
    code: "CSTD  /  FILE SYSTEM"
    title: directories ? "选择目录" : "选择文件"
    serial: "X-002  ·  FS"
    note: directory.status === FolderListModel.Ready ? "共 " + directory.count + " 项" : ""
    width: Math.min(940, parent.width - 40)
    height: Math.min(780, parent.height - 40)
    property var current: ({})
    property string selected: ""
    property bool directories: false
    property string error: ""
    property var acceptPath
    readonly property int pageRows: 10
    function browse(value, root, folderOnly, callback) {
        directories = folderOnly; acceptPath = callback
        const info = fileLocations.locate(value, root)
        const dir = info.directory ? info : fileLocations.locate(info.parent || root, "")
        navigateTo(dir.directory ? dir : fileLocations.locate("", ""))
        if (info.file && !directories) selected = info.path
        open()
    }
    function navigateTo(info) {
        if (!info.directory) { error = "目录不存在"; return }
        current = info; pathBox.text = info.path; selected = ""; error = ""; pager.pageIndex = 0
    }
    function submit() {
        const raw = pathBox.text !== current.path ? pathBox.text : selected || (directories ? current.path : "")
        if (!raw) { error = "请选择一个文件"; return }
        const info = fileLocations.locate(raw, current.path)
        if (directories ? info.directory : info.file) { const done = acceptPath; close(); done(info.path) }
        else if (info.directory) navigateTo(info)
        else error = directories ? "请选择有效目录" : "请选择有效文件"
    }
    FolderListModel { id: directory; folder: picker.current.url || ""; showFiles: !picker.directories; showDirsFirst: true; showHidden: false }

    ColumnLayout {
        anchors.fill: parent
        spacing: 14
        // 上一级 + 路径
        RowLayout {
            Layout.fillWidth: true
            spacing: 14
            RhineButton { text: "↑ 上一级"; small: true; enabled: !!picker.current.parent && picker.current.parent !== picker.current.path; onClicked: picker.navigateTo(fileLocations.locate(picker.current.parent, "")) }
            RhineField { id: pathBox; Layout.fillWidth: true; mono: true; onAccepted: picker.submit() }
        }
        // 盘符：分段按钮，当前盘为墨色底
        Row {
            spacing: -1.5
            Repeater {
                model: picker.opened ? fileLocations.drives() : []
                Rectangle {
                    id: drive
                    required property string modelData
                    readonly property bool on: String(picker.current.path || "").toUpperCase().startsWith(modelData.replace(/\/$/, "").toUpperCase())
                    width: driveText.implicitWidth + 30; height: 30
                    color: on ? Theme.ink : driveMouse.containsMouse ? Theme.grid : "transparent"
                    border.width: 1.5; border.color: Theme.ink
                    Text { id: driveText; anchors.centerIn: parent; text: drive.modelData.replace(/\/$/, ""); color: drive.on ? Theme.paper : Theme.ink; font.family: Theme.font; font.pixelSize: 13; font.weight: Font.Bold; font.letterSpacing: 1.6 }
                    MouseArea { id: driveMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: picker.navigateTo(fileLocations.locate(drive.modelData, "")) }
                }
            }
        }
        // 列表：表头 + 按页的行
        Item {
            id: listArea
            Layout.fillWidth: true
            Layout.preferredHeight: 30 + picker.pageRows * 36
            WheelHandler { onWheel: event => pager.turnWheel(event.pixelDelta.y, event.angleDelta.y) }
            Row {
                height: 30
                Text { width: 56; height: 30; verticalAlignment: Text.AlignVCenter; leftPadding: 8; text: "#"; color: Theme.muted; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Bold; font.letterSpacing: 2 }
                Text { width: 86; height: 30; verticalAlignment: Text.AlignVCenter; text: "类型"; color: Theme.muted; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Bold; font.letterSpacing: 2 }
                Text { height: 30; verticalAlignment: Text.AlignVCenter; text: "名称"; color: Theme.muted; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Bold; font.letterSpacing: 2 }
            }
            Rectangle { y: 29; width: parent.width; height: 2; color: Theme.ink }
            Text {
                y: 50; x: 8
                visible: directory.status === FolderListModel.Ready && directory.count === 0
                text: picker.directories ? "没有子目录" : "这个目录是空的"
                color: Theme.muted; font.family: Theme.font; font.pixelSize: 14
            }
            Column {
                id: rowsCol
                y: 31
                width: parent.width
                transform: Translate { id: rowsShift }
                Connections {
                    target: pager
                    function onPageIndexChanged() { if (Theme.richMotion) pageSwap.restart() }
                }
                ParallelAnimation {
                    id: pageSwap
                    NumberAnimation { target: rowsCol; property: "opacity"; from: 0.2; to: 1; duration: 200 }
                    NumberAnimation { target: rowsShift; property: "x"; from: 20; to: 0; duration: 280; easing.type: Easing.OutCubic }
                }
                Repeater {
                    model: Math.max(0, Math.min(picker.pageRows, directory.count - pager.pageIndex * picker.pageRows))
                    Rectangle {
                        id: row
                        required property int index
                        readonly property int at: pager.pageIndex * picker.pageRows + index
                        readonly property string path: directory.get(at, "filePath") || ""
                        readonly property string name: directory.get(at, "fileName") || ""
                        readonly property bool isDir: !!directory.get(at, "fileIsDir")
                        readonly property bool chosen: picker.selected === path
                        width: rowsCol.width; height: 36
                        color: chosen ? Theme.ink : rowMouse.containsMouse ? Qt.rgba(Theme.ink.r, Theme.ink.g, Theme.ink.b, 0.06) : "transparent"
                        Rectangle { visible: row.chosen; width: 4; height: parent.height; color: Theme.accent }
                        Text { x: 8; width: 48; height: parent.height; verticalAlignment: Text.AlignVCenter; text: String(row.at + 1).padStart(2, "0"); color: row.chosen ? Theme.accent : Theme.muted; font.family: Theme.font; font.pixelSize: 13 }
                        Rectangle {
                            x: 56; anchors.verticalCenter: parent.verticalCenter
                            width: typeText.implicitWidth + 14; height: 20
                            color: row.isDir ? (row.chosen ? Theme.paper : Theme.ink) : "transparent"
                            border.width: 1; border.color: row.chosen ? Theme.paper : Theme.ink
                            Text { id: typeText; anchors.centerIn: parent; text: row.isDir ? "目录" : "文件"; color: row.isDir ? (row.chosen ? Theme.ink : Theme.paper) : (row.chosen ? Theme.paper : Theme.ink); font.family: Theme.font; font.pixelSize: 11; font.weight: Font.Bold; font.letterSpacing: 1.2 }
                        }
                        Text { x: 142; width: parent.width - 150; height: parent.height; verticalAlignment: Text.AlignVCenter; elide: Text.ElideMiddle; text: row.name; color: row.chosen ? Theme.paper : Theme.ink; font.family: Theme.font; font.pixelSize: 15; font.weight: row.isDir ? Font.DemiBold : Font.Normal }
                        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.hair; opacity: 0.7 }
                        MouseArea {
                            id: rowMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { picker.selected = row.path; picker.error = "" }
                            onDoubleClicked: if (row.isDir) picker.navigateTo(fileLocations.locate(row.path, "")); else picker.submit()
                        }
                    }
                }
            }
        }
        PageScale { id: pager; Layout.preferredWidth: listArea.width / 3; Layout.preferredHeight: 40; pages: Math.max(1, Math.ceil(directory.count / picker.pageRows)) }
        Item { Layout.fillHeight: true }
        // 选中项 + 操作
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Text { Layout.fillWidth: true; elide: Text.ElideMiddle; text: picker.error || picker.selected || picker.current.path || ""; color: picker.error ? Theme.error : Theme.muted; font.family: picker.error ? Theme.font : "Consolas"; font.pixelSize: 13 }
            RhineButton { text: "取消"; onClicked: picker.close() }
            RhineButton { text: "选择"; primary: true; onClicked: picker.submit() }
        }
    }
}
