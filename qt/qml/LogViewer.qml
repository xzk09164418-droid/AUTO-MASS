import QtQuick
import "."

// 历史记录日志（与网页版 HistoryLogModal 对应）：按页显示日志行（刻度翻页，不滚动），
// 可去掉空行、打开日志文件或所在文件夹、打开失败回放；附公招 / 掉落 / 报错统计摘要。
FocusScope {
    id: viewer
    property var host
    property string title: ""
    property string logPath: ""
    property var record: ({})
    property bool stripBlank: true
    property bool loading: false
    readonly property var allLines: {
        const text = String(record.log_content || "")
        const lines = text.split(/\r?\n/)
        return stripBlank ? lines.filter(l => l.trim() !== "") : lines
    }
    readonly property int pageRows: 26
    readonly property var replays: record.replays || []
    visible: false
    anchors.fill: parent
    z: 60

    function open(jsonFile, name) {
        title = name
        logPath = jsonFile.replace(/\.json$/, ".log")
        record = ({})
        loading = true
        visible = true
        pager.pageIndex = 0
        forceActiveFocus()
        host.call("/api/history/data", { jsonPath: jsonFile }, r => {
            loading = false
            record = r.code === 200 && r.data ? r.data : { log_content: "读取失败：" + (r.message || "") }
            // 打开时停在最后一页（最新的日志）
            pager.pageIndex = Math.max(0, Math.ceil(allLines.length / pageRows) - 1)
        })
    }
    function summary() {
        const out = []
        const rec = record.recruit_statistics
        if (rec && Object.keys(rec).length) out.push("公招：" + Object.keys(rec).map(k => k + " 星 " + rec[k]).join("，"))
        const drop = record.drop_statistics
        if (drop && Object.keys(drop).length) out.push("掉落：" + Object.keys(drop).map(stage => stage + "（" + Object.keys(drop[stage]).map(i => i + "×" + drop[stage][i]).join("、") + "）").join("；"))
        const p = record.pull_count_statistics
        if (p) out.push("抽数：当前卡池可用 " + p.current_pool_total + "，下版本预计 " + p.next_pool_total)
        const err = record.error_info
        if (err && Object.keys(err).length) out.push("报错：" + Object.keys(err).map(k => k + " " + err[k]).join("；"))
        return out.join("\n")
    }
    Keys.onEscapePressed: visible = false
    Keys.onPressed: event => {
        if (event.key === Qt.Key_PageDown || event.key === Qt.Key_Right) { pager.pageIndex = Math.min(pager.pages - 1, pager.pageIndex + 1); event.accepted = true }
        else if (event.key === Qt.Key_PageUp || event.key === Qt.Key_Left) { pager.pageIndex = Math.max(0, pager.pageIndex - 1); event.accepted = true }
    }

    component Btn: Rectangle {
        property string text
        property bool enabledBtn: true
        signal clicked()
        width: t.implicitWidth + 28; height: 32
        color: "transparent"; border.width: 1.5; border.color: m.containsMouse && enabledBtn ? Theme.accent : Theme.ink
        opacity: enabledBtn ? 1 : 0.35
        Text { id: t; anchors.centerIn: parent; text: parent.text; color: m.containsMouse && parent.enabledBtn ? Theme.accent : Theme.ink; font.family: Theme.font; font.pixelSize: 13; font.weight: Font.Bold; font.letterSpacing: 1 }
        MouseArea { id: m; anchors.fill: parent; hoverEnabled: true; enabled: parent.enabledBtn; cursorShape: Qt.PointingHandCursor; onClicked: parent.clicked() }
    }

    Rectangle { anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.45) }
    MouseArea { anchors.fill: parent; onClicked: viewer.visible = false }
    WheelHandler { onWheel: event => pager.turnWheel(event.pixelDelta.y, event.angleDelta.y) }
    Rectangle {
        anchors.centerIn: parent
        width: Math.min(parent.width - 120, 1180); height: body.implicitHeight + 56
        color: Theme.paper; border.width: 1.5; border.color: Theme.ink
        MouseArea { anchors.fill: parent }
        Rectangle { width: parent.width; height: 4; color: Theme.accent }
        Column {
            id: body
            x: 32; y: 26; width: parent.width - 64; spacing: 12
            Row {
                width: parent.width; spacing: 16
                Text { text: "日志"; color: Theme.accent; font.family: Theme.font; font.pixelSize: 13; font.weight: Font.Bold; font.letterSpacing: 2.6; anchors.verticalCenter: parent.verticalCenter }
                Text { text: viewer.title; color: Theme.ink; font.family: Theme.font; font.pixelSize: 20; font.weight: Font.Bold; elide: Text.ElideRight; width: parent.width * 0.5 }
            }
            Text { visible: text !== ""; width: parent.width; wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideRight; text: viewer.summary(); color: Theme.muted; font.family: Theme.font; font.pixelSize: 13; lineHeight: 1.3 }
            Row {
                spacing: 8
                Btn { text: viewer.stripBlank ? "显示空行" : "去掉空行"; onClicked: viewer.stripBlank = !viewer.stripBlank }
                Btn { text: "打开日志文件"; onClicked: if (!fileLocations.openFile(viewer.logPath)) viewer.host.toastText("日志文件不存在") }
                Btn { text: "打开所在文件夹"; onClicked: if (!fileLocations.openFolder(viewer.logPath)) viewer.host.toastText("文件夹不存在") }
                Repeater {
                    model: viewer.replays
                    Btn {
                        required property var modelData
                        required property int index
                        text: "失败回放 " + (index + 1)
                        enabledBtn: !!modelData.filePath
                        onClicked: if (!fileLocations.openFile(modelData.filePath)) viewer.host.toastText("回放文件不存在")
                    }
                }
            }
            Rectangle {
                width: parent.width
                height: viewer.pageRows * 19 + 24
                color: "#0b0c0b"
                clip: true
                Text { visible: viewer.loading; x: 16; y: 12; text: "正在读取…"; color: "#d9d6cf"; font.family: Theme.font; font.pixelSize: 13 }
                Column {
                    x: 16; y: 12; width: parent.width - 32
                    Repeater {
                        model: viewer.allLines.slice(pager.pageIndex * viewer.pageRows, (pager.pageIndex + 1) * viewer.pageRows)
                        Text {
                            required property string modelData
                            width: parent.width
                            elide: Text.ElideRight
                            textFormat: Text.PlainText
                            text: modelData
                            color: /异常|错误|失败|ERROR/i.test(modelData) ? "#e58a7f" : /完成|成功|SUCCESS/i.test(modelData) ? "#9cc79f" : "#d9d6cf"
                            font.family: "Consolas"; font.pixelSize: 13
                        }
                    }
                }
            }
            Item {
                width: parent.width; height: 40
                PageScale { id: pager; width: parent.width / 3; pages: Math.max(1, Math.ceil(viewer.allLines.length / viewer.pageRows)) }
                Text { anchors.right: closeBtn.left; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; text: "共 " + viewer.allLines.length + " 行 · 第 " + (pager.pageIndex + 1) + " / " + pager.pages + " 页"; color: Theme.muted; font.family: Theme.font; font.pixelSize: 12 }
                Btn { id: closeBtn; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; text: "关闭"; onClicked: viewer.visible = false }
            }
        }
    }
}
