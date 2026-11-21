import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import Qt.labs.folderlistmodel
import "."

C.Popup {
    id: picker
    parent: C.Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(660, parent.width - 24); height: Math.min(530,parent.height - 24)
    modal: true; focus: true; padding: 20
    background: Rectangle { color: Theme.paper; border.width: 2; border.color: Theme.ink }
    property var current: ({})
    property string selected: ""
    property bool directories: false
    property string error: ""
    property var acceptPath
    function browse(value, root, folderOnly, callback) {
        directories = folderOnly; acceptPath = callback
        const info = fileLocations.locate(value,root)
        const dir = info.directory ? info : fileLocations.locate(info.parent || root,"")
        navigateTo(dir.directory ? dir : fileLocations.locate("",""))
        if (info.file && !directories) selected = info.path
        open()
    }
    function navigateTo(info) {
        if (!info.directory) { error = "目录不存在"; return }
        current = info; pathBox.text = info.path; selected = ""; error = ""; files.positionViewAtBeginning()
    }
    function submit() {
        const raw = pathBox.text !== current.path ? pathBox.text : selected || (directories ? current.path : "")
        if (!raw) { error = "请选择一个文件"; return }
        const info = fileLocations.locate(raw,current.path)
        if (directories ? info.directory : info.file) { const done = acceptPath; close(); done(info.path) }
        else if (info.directory) navigateTo(info)
        else error = directories ? "请选择有效目录" : "请选择有效文件"
    }
    FolderListModel { id: directory; folder: picker.current.url || ""; showFiles: !picker.directories; showDirsFirst: true }
    contentItem: ColumnLayout {
        spacing: 8
        Text { text: "CSTD  /  FILE SYSTEM"; color: Theme.accent; font.letterSpacing: 2; font.bold: true }
        Text { text: picker.directories ? "选择目录" : "选择文件"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 24; font.bold: true }
        RowLayout {
            C.Button { text: "↑"; onClicked: picker.navigateTo(fileLocations.locate(picker.current.parent,"")) }
            C.TextField { id: pathBox; Layout.fillWidth: true; selectByMouse: true; onAccepted: picker.submit() }
        }
        Row { spacing: 6; Repeater { model: picker.opened ? fileLocations.drives() : []; C.Button { required property string modelData; text: modelData; onClicked: picker.navigateTo(fileLocations.locate(modelData,"")) } } }
        ListView {
            id: files; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            model: directory
            C.ScrollBar.vertical: C.ScrollBar {}
            delegate: Rectangle {
                required property string filePath
                required property string fileName
                required property bool fileIsDir
                width: files.width - 12; height: 31
                color: picker.selected === filePath ? Theme.grid : "transparent"
                Text { anchors.verticalCenter: parent.verticalCenter; width: parent.width; elide: Text.ElideMiddle; color: Theme.ink; font.family: Theme.font; text: (fileIsDir ? "▸  " : "   ") + fileName }
                MouseArea {
                    anchors.fill: parent
                    onClicked: { picker.selected=filePath; picker.error="" }
                    onDoubleClicked: if (fileIsDir) picker.navigateTo(fileLocations.locate(filePath,"")); else picker.submit()
                }
            }
        }
        Text { Layout.fillWidth: true; elide: Text.ElideMiddle; text: picker.error || picker.selected || picker.current.path || ""; color: picker.error ? Theme.error : Theme.muted }
        RowLayout { Layout.alignment: Qt.AlignRight
            C.Button { text: "取消"; onClicked: picker.close() }
            C.Button { text: "选择"; onClicked: picker.submit() }
        }
    }
}

