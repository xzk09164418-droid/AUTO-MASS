import QtQuick
import QtQuick.Controls.Basic as C
import "."
import "Live.js" as Live
import "SectionData.js" as SD

Item {
    id: shelf
    required property var view
    required property var chain
    required property Item backButton
    property var preview: SD.sections["02"].items.map((s,i) => Live.previewScript(s,"preview-"+i,i))
    readonly property bool online: view.onlineHome
    readonly property var records: online ? (view.live.scripts || []) : preview
    readonly property bool ready: !online || (!!view.api && !!view.live.scripts && view.liveState === "ok")
    property bool writing: false
    readonly property bool sortable: visible && !view.arrayMode && ready && !writing
    property var parked: []
    property string dragId: ""
    property point pointer
    readonly property string query: search.text.trim().toLowerCase()
    readonly property bool typing: search.activeFocus
    readonly property var filtered: records.filter(s => (!sortableMode || !parked.includes(s.uid)) &&
        (!query || [s.name,s.uid,...(s.accounts || [])].some(v => String(v).toLowerCase().includes(query))))
    readonly property bool sortableMode: !view.arrayMode
    readonly property var stack: parked.map(id => records.find(s => s.uid === id)).filter(Boolean)
    readonly property var dragged: records.find(s => s.uid === dragId)
    signal message(string text)

    function reset() { dragId = ""; parked = []; search.clear() }
    onVisibleChanged: if (!visible) reset()
    onSortableModeChanged: reset()

    function store(list) {
        if (online) view.setLive("scripts",list)
        else preview = list
    }
    function focusRecord(id) {
        if (!visible) return
        const i = filtered.findIndex(s => s.uid === id)
        if (i >= 0) view.select(i)
    }
    function create(copy) {
        if (writing || !ready || (copy && !view.item)) return
        const source = copy ? view.item : null
        function finish(entry) {
            store(records.filter(s => s.uid !== entry.uid).concat(entry))
            if (visible) { search.clear(); focusRecord(entry.uid); view.forceActiveFocus() }
            writing = false
            message(copy ? "已复制脚本" : "已新建脚本")
        }
        if (!online) {
            const entry = copy ? Live.copyScript(source) : Live.previewScript(SD.demoGeneral({name:"新脚本",exe:"",root:"",cfg:"",users:[]}),"",records.length)
            entry.uid = "preview-" + Date.now()
            finish(entry)
            return
        }
        writing = true
        const body = {type:"General"}
        if (source) body.scriptId = source.uid
        view.call("/api/scripts/add",body,r => {
            if (r.code !== 200 || !r.scriptId) { writing = false; message(r.message || "创建失败"); return }
            const id = r.scriptId
            view.call("/api/scripts/get",{scriptId:id,includeUsers:true},result => {
                const entry = result.code === 200 && Live.scripts(result).find(s => s.uid === id)
                if (!entry) {
                    writing = false
                    message("脚本已创建，正在重新读取列表")
                    view.fetchLive("scripts")
                    return
                }
                finish(entry)
            })
        })
    }
    function moveDrag(record, point) { pointer = point; dragId = record.uid }
    function overDock(p) { return dock.contains(dock.mapFromItem(shelf,p)) }
    function scrollDock(amount) {
        stagedList.contentY = Math.max(0, Math.min(stagedList.contentHeight - stagedList.height, stagedList.contentY + amount))
    }
    function insertSide(p) {
        if (!filtered.length) return !query && p.x < 710 && p.y > 470 ? 1 : 0
        return chain.insertSide(shelf,p)
    }
    function drop(record,p) {
        dragId = ""
        if (!record || !sortable) return
        if (!parked.includes(record.uid)) {
            if (overDock(p)) parked = parked.concat(record.uid)
            return
        }
        const side = insertSide(p)
        if (!side) return
        const anchor = view.item
        const list = records.filter(s => s.uid !== record.uid)
        const at = anchor ? list.findIndex(s => s.uid === anchor.uid) : list.length
        list.splice(at + (anchor && side > 0 ? 1 : 0),0,record)
        function accept() {
            store(list)
            parked = parked.filter(id => id !== record.uid)
            focusRecord(record.uid)
        }
        if (!online) { accept(); return }
        writing = true
        view.call("/api/scripts/order",{indexList:list.map(s => s.uid)},r => {
            writing = false
            if (r.code === 200) accept()
            else message(r.message || "排序保存失败，请重试")
        })
    }

    C.TextField {
        id: search
        objectName: "scriptSearch"
        anchors.right: shelf.right
        anchors.rightMargin: shelf.width - shelf.backButton.x + 14
        y: shelf.backButton.y; width: 198; height: shelf.backButton.height
        placeholderText: "SEARCH"; leftPadding: 40; Accessible.name: "搜索脚本或账号"; selectByMouse: true
        font.family: Theme.font; font.pixelSize: 15; color: Theme.ink
        placeholderTextColor: Theme.muted
        background: Rectangle { color: Theme.paper; border.color: Theme.ink; border.width: 3 }
        Item {
            x: 13; anchors.verticalCenter: parent.verticalCenter; width: 18; height: 18
            Rectangle { width: 13; height: 13; radius: 7; color: "transparent"; border.color: Theme.ink; border.width: 2 }
            Rectangle { x: 11; y: 11; width: 8; height: 2; rotation: 45; transformOrigin: Item.Left; color: Theme.ink }
        }
        Keys.onEscapePressed: { clear(); shelf.view.forceActiveFocus() }
        onAccepted: shelf.view.forceActiveFocus()
    }
    Row {
        x: 755; y: 475; spacing: 8
        ShelfButton { text: "＋ 新建脚本"; enabled: shelf.ready && !shelf.writing; onClicked: shelf.create(false) }
        ShelfButton { text: "复制脚本"; enabled: shelf.ready && !shelf.writing && !!shelf.view.item; onClicked: shelf.create(true) }
    }
    component ShelfButton: C.Button {
        id: button
        leftPadding: 14; rightPadding: 14; implicitHeight: 36
        font.family: Theme.font; font.pixelSize: 14
        opacity: enabled ? 1 : 0.45
        contentItem: Text { text: button.text; font: button.font; color: Theme.ink; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { color: Theme.paper; border.color: button.hovered || button.activeFocus ? Theme.accent : Theme.ink }
    }
    Rectangle {
        id: dock
        objectName: "scriptDock"
        x: 750; y: 535; width: 342; height: 275
        visible: shelf.sortableMode
        color: "transparent"
        border.color: shelf.dragId && shelf.overDock(shelf.pointer) ? Theme.accent : Theme.grid
        Text { x: 12; y: 10; text: "暂存录像卡  /  " + shelf.stack.length; color: Theme.muted; font.family: Theme.font; font.pixelSize: 14 }
        Text { anchors.centerIn: parent; visible: shelf.stack.length === 0; text: "拖入录像卡以调整顺序"; color: Theme.muted; font.pixelSize: 15 }
        ListView {
            id: stagedList
            anchors.fill: parent; anchors.margins: 12; anchors.topMargin: 38
            clip: true; model: shelf.stack
            C.ScrollBar.vertical: C.ScrollBar {}
            delegate: Item {
                required property var modelData
                required property int index
                width: ListView.view.width
                height: index === shelf.stack.length - 1 ? 174 : 48
                CassetteFace {
                    x: 4 + 10 * (parent.index % 4)
                    record: modelData
                    code: "02-" + String(shelf.records.indexOf(modelData) + 1).padStart(2,"0")
                    ScriptDragArea { anchors.fill: parent; shelf: dock.parent; record: modelData }
                }
            }
        }
    }
    Text {
        visible: shelf.sortableMode && !shelf.filtered.length
        x: 256; y: 720; text: shelf.query ? "没有匹配的脚本" : shelf.stack.length ? "拖回此处" : "暂无脚本"
        color: Theme.muted; font.family: Theme.font
    }
    CassetteFace {
        visible: !!shelf.dragged; x: shelf.pointer.x - width/2; y: shelf.pointer.y - height/2
        record: shelf.dragged || null
        code: "02-" + String(shelf.records.indexOf(record) + 1).padStart(2,"0")
        highlighted: true
        Text {
            anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.top
            color: Theme.ink; font.bold: true
            text: !shelf.dragged ? "" : shelf.overDock(shelf.pointer) ? "松开以暂存" :
                  shelf.parked.includes(shelf.dragId) && shelf.insertSide(shelf.pointer) ? (shelf.insertSide(shelf.pointer)<0 ? "插入选中卡之前":"插入选中卡之后") : ""
        }
    }
}
