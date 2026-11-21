import QtQuick
import "."

// 通用暂存区（与托管管理的「暂存录像卡」同一套交互）：把要调整顺序的条目拖进暂存区，
// 再从暂存区拖回目标位置（落在某项的前半 / 后半即插到它之前 / 之后），松开后保存新顺序。
// 暂存区常态不显示，拖动的卡片进入范围时才用橙色小圆角矩形框出；已暂存的条目始终可见。
//
// 排序组由各处注册：register(name, {ids, label(id), target(point) → {id, side} | null, commit(ids), locked()})。
// 拖动对象 record 带 sortId 与 sortGroup；ScriptDragArea 按 shelf 接口（sortable / moveDrag / drop / dragId）调用这里。
Item {
    id: dock
    property var groups: ({})
    property var parked: []                 // [{sortId, sortGroup, name, code}]
    property string dragId: ""
    property var dragRecord: null
    property point pointer
    property int revision: 0                // 注册变化时刷新绑定
    readonly property bool sortable: true
    readonly property rect area: Qt.rect(750, 535, 342, 275)
    signal message(string text)

    function register(name, group) { const g = Object.assign({}, groups); g[name] = group; groups = g; revision++ }
    function unregister(name, group) { if (groups[name] !== group) return; const g = Object.assign({}, groups); delete g[name]; groups = g; revision++ }
    function reset() { parked = []; dragId = ""; dragRecord = null }
    function overDock(p) { return p.x >= area.x && p.x <= area.x + area.width && p.y >= area.y && p.y <= area.y + area.height }
    function groupOf(record) { return record && record.sortGroup ? groups[record.sortGroup] : null }
    function isParked(record) { return parked.some(r => r.sortGroup === record.sortGroup && r.sortId === record.sortId) }
    function usable(record) { const g = groupOf(record); return !!g && !(g.locked && g.locked()) }
    // 当前可见的暂存条目：只显示已注册（当前画面上）的排序组
    readonly property var shown: { revision; return parked.filter(r => !!groups[r.sortGroup]) }

    function moveDrag(record, point) {
        if (!record || !record.sortId || !usable(record)) return
        pointer = point
        dragRecord = record
        dragId = record.sortGroup + "/" + record.sortId
    }
    function hint() {
        if (!dragRecord) return ""
        if (overDock(pointer)) return isParked(dragRecord) ? "" : "松开以暂存"
        if (!isParked(dragRecord)) return "拖入暂存区后再放到目标位置"
        const t = groupOf(dragRecord) && groupOf(dragRecord).target(pointer)
        if (!t || t.id === dragRecord.sortId) return ""
        return "插入到「" + groupOf(dragRecord).label(t.id) + (t.side < 0 ? "」之前" : "」之后")
    }
    function drop(record, point) {
        dragId = ""; dragRecord = null
        const g = groupOf(record)
        if (!record || !g || !usable(record)) return
        if (!isParked(record)) {
            if (overDock(point)) parked = parked.concat([record])
            return
        }
        if (overDock(point)) return
        const t = g.target(point)
        if (!t || t.id === record.sortId) return
        const ids = g.ids().filter(id => id !== record.sortId)
        const at = ids.indexOf(t.id)
        if (at < 0) return
        ids.splice(at + (t.side > 0 ? 1 : 0), 0, record.sortId)
        g.commit(ids, ok => {
            if (ok) parked = parked.filter(r => !(r.sortGroup === record.sortGroup && r.sortId === record.sortId))
        })
    }

    // 范围框：只在拖动的卡片进入范围时出现
    Rectangle {
        x: dock.area.x; y: dock.area.y; width: dock.area.width; height: dock.area.height
        radius: 4
        color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.06)
        border.width: 2
        border.color: Theme.accent
        visible: !!dock.dragRecord && dock.overDock(dock.pointer)
        Text { x: 12; y: 10; text: "暂存区  /  " + dock.shown.length; color: Theme.accent; font.family: Theme.font; font.pixelSize: 14; font.weight: Font.Bold }
    }
    // 已暂存的条目：在范围内自上而下排开，条目多时压缩间距（不滚动）
    Repeater {
        model: dock.shown
        Rectangle {
            id: chip
            required property var modelData
            required property int index
            readonly property real step: Math.min(50, (dock.area.height - 56) / Math.max(1, dock.shown.length))
            x: dock.area.x + 12 + 10 * (index % 4)
            y: dock.area.y + 38 + index * step
            width: dock.area.width - 60; height: 44
            color: Theme.paper
            border.width: 1.5
            border.color: chipDrag.containsMouse ? Theme.accent : Theme.ink
            opacity: dock.dragRecord && dock.dragRecord.sortId === modelData.sortId && dock.dragRecord.sortGroup === modelData.sortGroup ? 0.3 : 1
            Rectangle { width: 4; height: parent.height; color: Theme.accent }
            Text { x: 14; anchors.verticalCenter: parent.verticalCenter; text: chip.modelData.code || ""; color: Theme.accent; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Bold }
            Text { x: 56; width: parent.width - 66; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight; text: chip.modelData.name; color: Theme.ink; font.family: Theme.font; font.pixelSize: 15; font.weight: Font.DemiBold }
            ScriptDragArea { id: chipDrag; anchors.fill: parent; shelf: dock; record: chip.modelData; hoverEnabled: true }
        }
    }
    // 跟随指针的拖动卡
    Rectangle {
        visible: !!dock.dragRecord
        x: dock.pointer.x - width / 2; y: dock.pointer.y - height / 2
        width: 260; height: 44
        color: Theme.paper; border.width: 2; border.color: Theme.accent
        z: 10
        Rectangle { width: 4; height: parent.height; color: Theme.accent }
        Text { x: 14; anchors.verticalCenter: parent.verticalCenter; text: dock.dragRecord ? dock.dragRecord.code || "" : ""; color: Theme.accent; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Bold }
        Text { x: 56; width: parent.width - 66; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight; text: dock.dragRecord ? dock.dragRecord.name : ""; color: Theme.ink; font.family: Theme.font; font.pixelSize: 15; font.weight: Font.DemiBold }
        Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.top; anchors.bottomMargin: 4; text: dock.hint(); color: Theme.ink; font.family: Theme.font; font.pixelSize: 13; font.bold: true }
    }
}
