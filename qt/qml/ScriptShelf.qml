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
        if (!online) preview = list
        else if (view.d && view.d.key === "scripts") view.setLive("scripts",list)
        else view.live = Object.assign({},view.live,{scripts:list})
    }
    function acknowledge(request) {
        const body = request.body
        const record = records.find(s => s.uid === body.scriptId)
        if (!record || !record.src) return
        const accounts = record.src.ur
        const data = body.userId ? accounts.data[body.userId] : record.src.c
        if (!data) return
        for (const group of Object.keys(body.data))
            data[group] = Object.assign({}, data[group], body.data[group])
        const next = Object.assign({}, record)
        if (body.userId) {
            next.accounts = accounts.index.map(u => accounts.data[u.uid]?.Info?.Name || "账号")
            const page = next.tabs.find(t => t.userId === body.userId)
            if (page) page.sortLabel = data.Info.Name || page.name
        } else {
            next.name = data.Info.Name || "未命名脚本"
            next.icon = data.Script.ScriptPath || ""
            next.ops["删除脚本"].confirm = "将删除脚本「" + next.name + "」及其全部账号。"
        }
        store(records.map(s => s.uid === record.uid ? next : s))
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
        // 与「RETURN TO INDEX」同一样式：透明底、1.5 线框、粗体字距；输入内容时收窄字距
        placeholderText: "SEARCH"; leftPadding: 38; Accessible.name: "搜索脚本或账号"; selectByMouse: true
        opacity: shelf.view.reveal
        font.family: Theme.font; font.pixelSize: 13; font.weight: Font.Bold; font.letterSpacing: text ? 1 : 3.6
        color: Theme.ink
        placeholderTextColor: Theme.ink
        verticalAlignment: TextInput.AlignVCenter
        background: Rectangle { color: "transparent"; border.color: search.activeFocus ? Theme.accent : Theme.ink; border.width: 1.5 }
        Item {
            x: 14; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16
            Rectangle { width: 11; height: 11; radius: 6; color: "transparent"; border.color: Theme.ink; border.width: 1.5 }
            Rectangle { x: 9.5; y: 9.5; width: 6; height: 1.5; rotation: 45; transformOrigin: Item.Left; color: Theme.ink }
        }
        Keys.onEscapePressed: { clear(); shelf.view.forceActiveFocus() }
        onAccepted: shelf.view.forceActiveFocus()
    }
    // 新建 / 复制：放在铭牌下方右侧，与「RETURN TO INDEX」同一种按钮样式
    Row {
        x: shelf.backButton.x + shelf.backButton.width - width
        y: 980
        spacing: 10
        opacity: shelf.view.reveal
        ShelfButton { text: "＋ 新建脚本"; enabled: shelf.ready && !shelf.writing; onClicked: shelf.create(false) }
        ShelfButton { text: "复制脚本"; enabled: shelf.ready && !shelf.writing && !!shelf.view.item; onClicked: shelf.create(true) }
    }
    component ShelfButton: Rectangle {
        id: button
        property string text
        signal clicked()
        readonly property bool hot: buttonMouse.containsMouse || activeFocus
        width: buttonText.implicitWidth + 32
        height: 32
        opacity: enabled ? 1 : 0.4
        color: hot && enabled ? Theme.ink : "transparent"
        border.width: 1.5
        border.color: Theme.ink
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: text
        Keys.onReturnPressed: if (enabled) clicked()
        Keys.onSpacePressed: if (enabled) clicked()
        Text {
            id: buttonText
            anchors.centerIn: parent
            text: button.text
            color: button.hot && button.enabled ? Theme.paper : Theme.ink
            font.family: Theme.font
            font.pixelSize: 13
            font.weight: Font.Bold
            font.letterSpacing: 2.4
        }
        MouseArea { id: buttonMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (button.enabled) button.clicked() }
    }
    Rectangle {
        id: dock
        objectName: "scriptDock"
        x: 750; y: 535; width: 342; height: 275
        visible: shelf.sortableMode
        // 暂存区常态不显示：拖动的录像卡进入范围时才用橙色小圆角矩形框出；已暂存的卡始终可见
        readonly property bool hot: !!shelf.dragId && shelf.overDock(shelf.pointer)
        radius: 4
        color: hot ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.06) : "transparent"
        border.width: hot ? 2 : 0
        border.color: Theme.accent
        Text { x: 12; y: 10; visible: dock.hot; text: "暂存录像卡  /  " + shelf.stack.length; color: Theme.accent; font.family: Theme.font; font.pixelSize: 14; font.weight: Font.Bold }
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
        visible: shelf.sortableMode && !shelf.filtered.length && !shelf.stack.length
        x: 256; y: 720; text: shelf.query ? "没有匹配的脚本" : "暂无脚本"
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
