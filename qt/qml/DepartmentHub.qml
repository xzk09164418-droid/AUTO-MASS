import QtQuick
import QtQuick.Shapes
import "."
import "Departments.js" as Depts

// 一级界面：部门索引（对应 PV 1:00–1:12 的科室总览）。
// 入场编排：中央调度中心先出现（"以总辖构件科为首"）→ 四条斜线由中心向四角展开
// → 其余方块按编号依次显现 → SEARCHING 标签扫过各方块后停回中央。
FocusScope {
    id: hub

    property bool active: false
    readonly property int centerIndex: departments.findIndex(d => d.center)
    property int current: centerIndex
    property bool paused: false          // 二级界面打开时暂停视差与漂浮
    property string backendStatus: ""
    property bool scanning: false

    signal openRequested(int index, rect r)

    readonly property var departments: Depts.list
    readonly property var decorations: Depts.decos

    // 视差：目标 tx/ty 来自鼠标，mx/my 每帧平滑跟随；clock 驱动空闲漂浮
    property real tx: 0
    property real ty: 0
    property real mx: 0
    property real my: 0
    property real clock: 0
    property real intro: 0               // 0→1 整体入场时间轴（约 2.4 秒）

    function tileRect(i) {
        const d = departments[i]
        return Qt.rect(d.x - d.w / 2, d.y - d.h / 2, d.w, d.h)
    }

    function select(i) {
        current = (i + departments.length) % departments.length
    }

    function open(i) {
        select(i)
        openRequested(i, tileRect(i))
    }

    function focusCurrent() {
        tiles.itemAt(current).forceActiveFocus()
    }

    // 方块 i 的入场进度：中央先出，其余按编号错开
    function tileIntro(i) {
        const start = departments[i].center ? 0 : 0.28 + 0.045 * (i < centerIndex ? i : i - 1)
        return Math.max(0, Math.min(1, (intro - start) / 0.22))
    }

    onActiveChanged: if (active) introAnim.restart()

    SequentialAnimation {
        id: introAnim
        NumberAnimation { target: hub; property: "intro"; from: 0; to: 1; duration: 2400; easing.type: Easing.Linear }
        // 标签依次扫过各方块，再停回中央（由 scanTimer 逐格推进）
        ScriptAction { script: hub.scanning = true }
    }

    Timer {
        id: scanTimer
        property int step: 0
        interval: 110
        repeat: true
        running: hub.scanning
        onTriggered: {
            if (step < hub.departments.length) {
                hub.current = step
                step++
            } else {
                hub.current = hub.centerIndex
                step = 0
                hub.scanning = false
                hub.focusCurrent()
            }
        }
    }

    Keys.onPressed: event => {
        if (event.key >= Qt.Key_1 && event.key <= Qt.Key_9) {
            select(event.key - Qt.Key_1); focusCurrent(); event.accepted = true
        } else if (event.key === Qt.Key_0) {
            select(9); focusCurrent(); event.accepted = true
        } else if (event.key === Qt.Key_Right || event.key === Qt.Key_Down) {
            select(current + 1); focusCurrent(); event.accepted = true
        } else if (event.key === Qt.Key_Left || event.key === Qt.Key_Up) {
            select(current - 1); focusCurrent(); event.accepted = true
        }
    }

    // 帧驱动跟随垂直同步；窗口不活跃、二级界面打开或未入场时停帧
    FrameAnimation {
        running: hub.active && !hub.paused && hub.visible
            && Qt.application.state === Qt.ApplicationActive
        onTriggered: {
            hub.mx += (hub.tx - hub.mx) * Math.min(1, frameTime * 5)
            hub.my += (hub.ty - hub.my) * Math.min(1, frameTime * 5)
            hub.clock += frameTime
        }
    }

    HoverHandler {
        onPointChanged: {
            hub.tx = (point.position.x / hub.width - 0.5) * 2
            hub.ty = (point.position.y / hub.height - 0.5) * 2
        }
    }

    // ── 背景：径向渐亮 + 网格 ──────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Theme.bg }
            GradientStop { position: 0.5; color: Qt.lighter(Theme.bg, Theme.dark ? 1.15 : 1.03) }
            GradientStop { position: 1; color: Theme.bg }
        }
    }
    Repeater {
        model: 21
        Rectangle { required property int index; x: index * 96; width: 1; height: hub.height; color: Theme.grid }
    }
    Repeater {
        model: 12
        Rectangle { required property int index; y: index * 96; height: 1; width: hub.width; color: Theme.grid }
    }

    // 远景装饰：右上大圆环、间隔字母、左上虚化品牌
    Rectangle {
        x: 1920 - 410 - hub.mx * 4
        y: -260 - hub.my * 4
        width: 560
        height: 560
        radius: 280
        color: "transparent"
        border.width: 70
        border.color: Theme.glow
        opacity: hub.intro
    }
    Text {
        x: 1500
        y: 170
        text: "A   U   T   O"
        color: Theme.glow
        font.family: Theme.font
        font.pixelSize: 30
        font.weight: Font.Bold
        font.letterSpacing: 18
        opacity: hub.intro
    }
    Column {
        x: 59
        y: 64
        opacity: 0.32
        Text { text: "AUTO-MAS"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 41; font.letterSpacing: 2.2; font.weight: Font.Bold }
        Text { text: "SCRIPT CUSTODY INFORMATION"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 14; font.letterSpacing: 1.4; font.weight: Font.DemiBold }
        Text { text: "ANALYSIS OS"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 32; font.letterSpacing: 5.4; font.weight: Font.Bold }
    }
    Repeater {
        model: [Qt.point(470, 150), Qt.point(1760, 640), Qt.point(680, 900)]
        Item {
            required property point modelData
            x: modelData.x - 30
            y: modelData.y - 30
            width: 60
            height: 60
            opacity: 0.5 * hub.intro
            Rectangle { x: 29; width: 2; height: 60; color: Theme.glow }
            Rectangle { y: 29; height: 2; width: 60; color: Theme.glow }
        }
    }

    // ── 四条斜线：由中央方块四角向画面四角展开 ─────────────────────────────
    Shape {
        id: diag
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        readonly property real p: Math.max(0, Math.min(1, (hub.intro - 0.12) / 0.3))
        readonly property real e: 1 - Math.pow(1 - p, 3)
        ShapePath {
            strokeColor: Theme.dark ? Theme.hair : "#3a3a36"
            strokeWidth: 1.4
            fillColor: "transparent"
            startX: 790; startY: 370
            PathLine { x: 790 - 790 * diag.e; y: 370 - 370 * diag.e }
            PathMove { x: 1130; y: 370 }
            PathLine { x: 1130 + 790 * diag.e; y: 370 - 370 * diag.e }
            PathMove { x: 790; y: 710 }
            PathLine { x: 790 - 790 * diag.e; y: 710 + 370 * diag.e }
            PathMove { x: 1130; y: 710 }
            PathLine { x: 1130 + 790 * diag.e; y: 710 + 370 * diag.e }
        }
    }

    // ── 装饰方块 ────────────────────────────────────────────────────────
    Repeater {
        model: hub.decorations
        Item {
            required property var modelData
            required property int index
            readonly property real dp: modelData.depth
            width: modelData.w
            height: modelData.h
            x: modelData.x - width / 2 - hub.mx * dp + Math.sin(hub.clock / 2.6 + index) * dp * 0.15
            y: modelData.y - height / 2 - hub.my * dp + Math.cos(hub.clock / 3.1 + index * 1.7) * dp * 0.15
            opacity: Math.max(0, Math.min(1, (hub.intro - 0.5) / 0.3)) * (1 - modelData.blur * 0.5)

            Rectangle { anchors.fill: parent; color: modelData.kind === "stripe" ? Theme.block : Theme.paper }
            Rectangle {
                visible: modelData.kind === "inset"
                anchors.centerIn: parent
                width: parent.width * 0.4
                height: width
                color: Theme.decoGrey
            }
            Rectangle {
                visible: modelData.kind === "stripe"
                width: parent.width
                height: parent.height * 0.55
                anchors.verticalCenter: parent.verticalCenter
                color: Theme.paper
            }
        }
    }

    // ── 部门方块 ────────────────────────────────────────────────────────
    Repeater {
        id: tiles
        model: hub.departments
        DeptTile {
            readonly property real dp: d.depth
            d: modelData
            required property var modelData
            px: -hub.mx * dp + Math.sin(hub.clock / 2.6 + index) * dp * 0.15
            py: -hub.my * dp + Math.cos(hub.clock / 3.1 + index * 1.7) * dp * 0.15
            intro: hub.tileIntro(index)
            current: hub.current === index
            dimmed: true
            onHovered: hub.current = index
            onActivated: hub.open(index)
        }
    }

    // ── SEARCHING 标签：跟随当前方块 ─────────────────────────────────────
    Row {
        id: searching
        readonly property var d: hub.departments[hub.current]
        x: d.x - width / 2
        y: d.y - d.h / 2 - height - 14
        z: 10
        opacity: hub.intro >= 1 ? 1 : 0
        Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        Behavior on y { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 300 } }

        Rectangle { width: 14; height: 10; color: Theme.ink; anchors.verticalCenter: parent.verticalCenter }
        Rectangle {
            width: label.implicitWidth + 28
            height: label.implicitHeight + 8
            color: Theme.paper
            border.width: 1.5
            border.color: Theme.ink
            Text {
                id: label
                anchors.centerIn: parent
                text: hub.scanning ? "SEARCHING" : "ACCESS // " + searching.d.zh
                color: Theme.ink
                font.family: Theme.font
                font.pixelSize: 13
                font.weight: Font.Bold
                font.letterSpacing: 1
            }
        }
    }

    Ledger {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        departments: hub.departments
        current: hub.current
        backendStatus: hub.backendStatus
        opacity: hub.intro
        onPicked: i => hub.open(i)
        onHoveredIndex: i => hub.current = i
    }
}
