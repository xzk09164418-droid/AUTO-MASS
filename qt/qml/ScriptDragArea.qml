import QtQuick

MouseArea {
    id: area
    property var shelf: null
    property var record: null
    property point start
    property bool moved: false
    signal tapped()
    preventStealing: !!shelf && shelf.sortable
    cursorShape: pressed && moved ? Qt.ClosedHandCursor : Qt.PointingHandCursor
    onPressed: mouse => {
        start = mapToItem(null, mouse.x, mouse.y)
        moved = false
    }
    onPositionChanged: mouse => {
        if (!pressed || !shelf || !shelf.sortable || !record) return
        const scene = mapToItem(null, mouse.x, mouse.y)
        if (!moved && Math.hypot(scene.x - start.x, scene.y - start.y) < Qt.styleHints.startDragDistance) return
        moved = true
        shelf.moveDrag(record, shelf.mapFromItem(null, scene))
    }
    onReleased: mouse => {
        if (moved && shelf) shelf.drop(record, mapToItem(shelf, mouse.x, mouse.y))
    }
    onClicked: if (!moved) tapped()
    onCanceled: if (moved && shelf) shelf.dragId = ""
}
