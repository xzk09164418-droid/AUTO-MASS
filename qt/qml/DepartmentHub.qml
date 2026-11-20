import QtQuick
import QtQuick.Shapes
import "."
import "Departments.js" as Depts

// 一级界面：部门索引（对应 PV 1:00–1:12 的科室总览）。
// 入场编排：中央主页先出现 → 四条斜线由中心向四角展开 → 其余方块按编号依次显现，
// 标签直接停在主页上（不再逐个框选 01–10）；之后网格上随机闪现 PV 开场式的小方块。
FocusScope {
    id: hub

    property bool active: false
    readonly property int centerIndex: departments.findIndex(d => d.center)
    property int current: centerIndex
    property bool paused: false          // 二级界面打开时暂停视差与漂浮
    property string backendStatus: ""
    property bool sectioned: false       // 二级界面打开：方块、斜线、标签、底栏淡出
    property real chrome: sectioned ? 0 : 1
    Behavior on chrome { NumberAnimation { duration: 280 } }

    signal openRequested(int index, rect r)

    readonly property var departments: Depts.list
    readonly property var decorations: Depts.decos

    // 视差：目标 tx/ty 来自鼠标，mx/my 每帧平滑跟随；clock 驱动空闲漂浮
    property real tx: 0
    property real ty: 0
    property real mx: 0
    property real my: 0
    property real clock: 0
    property real intro: 0               // 0→1 整体入场时间轴
    property int introMs: 2400           // 加载完成即收尾时缩短为快速入场

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

    property int hiddenIndex: -1         // 过渡体正替身飞行的方块
    function tileItem(i) { return tiles.itemAt(i) }
    // 方块当前在画面上的矩形（含视差与悬停放大），过渡体以此为起止点
    function liveTileRect(i) {
        const t = tiles.itemAt(i)
        return t ? t.mapToItem(hub, 0, 0, t.width, t.height) : tileRect(i)
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
        NumberAnimation { target: hub; property: "intro"; from: 0; to: 1; duration: hub.introMs; easing.type: Easing.Linear }
        ScriptAction { script: { hub.current = hub.centerIndex; if (!hub.paused) hub.focusCurrent() } }   // 已进入二级界面时不抢焦点
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
    // 空闲停帧：鼠标静止 2.5 秒后漂浮幅度收为 0、视差追平，帧回调随之停下（不再持续渲染）
    property real floatAmp: 0
    property real stillFor: 0
    readonly property bool settled: floatAmp < 0.001 && stillFor > 2.5
        && Math.abs(tx - mx) < 0.001 && Math.abs(ty - my) < 0.001

    FrameAnimation {
        id: frameLoop
        running: hub.active && !hub.paused && hub.visible
            && Qt.application.state === Qt.ApplicationActive && !hub.settled
        onTriggered: {
            const dt = Math.min(frameTime, 0.1)
            hub.mx += (hub.tx - hub.mx) * Math.min(1, dt * 5)
            hub.my += (hub.ty - hub.my) * Math.min(1, dt * 5)
            hub.stillFor += dt
            const goal = hub.stillFor > 2.5 ? 0 : 1
            hub.floatAmp += (goal - hub.floatAmp) * Math.min(1, dt * 2.5)
            if (Math.abs(goal - hub.floatAmp) < 0.001) hub.floatAmp = goal
            if (Math.abs(hub.tx - hub.mx) < 0.001) hub.mx = hub.tx
            if (Math.abs(hub.ty - hub.my) < 0.001) hub.my = hub.ty
            hub.clock += dt
        }
    }

    HoverHandler {
        onPointChanged: {
            // 方块随视差移动时 Qt 会重发悬停事件；只有鼠标真的移动才算唤醒
            const nx = (point.position.x / hub.width - 0.5) * 2
            const ny = (point.position.y / hub.height - 0.5) * 2
            if (Math.abs(nx - hub.tx) < 1e-4 && Math.abs(ny - hub.ty) < 1e-4) return
            hub.tx = nx
            hub.ty = ny
            hub.stillFor = 0
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
        opacity: hub.intro * hub.chrome
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
        opacity: hub.intro * hub.chrome
    }
    Column {
        x: 59
        y: 64
        opacity: 0.32 * hub.chrome
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
        opacity: hub.chrome
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
            x: modelData.x - width / 2 - hub.mx * dp + Math.sin(hub.clock / 2.6 + index) * dp * 0.15 * hub.floatAmp
            y: modelData.y - height / 2 - hub.my * dp + Math.cos(hub.clock / 3.1 + index * 1.7) * dp * 0.15 * hub.floatAmp
            opacity: Math.max(0, Math.min(1, (hub.intro - 0.5) / 0.3)) * (1 - modelData.blur * 0.5) * hub.chrome

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

    // ── 随机闪现的小方块（PV 开场网格元素） ─────────────────────────────────
    RandomBlocks {
        anchors.fill: parent
        // 窗口失焦仍继续（计时器开销极小），最小化 / 隐藏时停下
        active: hub.active && hub.intro >= 1 && !hub.paused && hub.visible
            && Qt.application.state !== Qt.ApplicationHidden
            && Qt.application.state !== Qt.ApplicationSuspended
        avoid: hub.departments.concat(hub.decorations)
        px: -hub.mx * 3
        py: -hub.my * 3
        opacity: Math.max(0, Math.min(1, (hub.intro - 0.85) / 0.15))
    }

    // ── 部门方块 ────────────────────────────────────────────────────────
    Repeater {
        id: tiles
        model: hub.departments
        DeptTile {
            readonly property real dp: d.depth
            d: modelData
            required property var modelData
            px: -hub.mx * dp + Math.sin(hub.clock / 2.6 + index) * dp * 0.15 * hub.floatAmp
            py: -hub.my * dp + Math.cos(hub.clock / 3.1 + index * 1.7) * dp * 0.15 * hub.floatAmp
            intro: hub.tileIntro(index)
            visible: hub.chrome > 0 && hub.hiddenIndex !== index
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
        opacity: hub.intro >= 1 && !hub.sectioned ? 1 : 0
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
                text: "ACCESS // " + searching.d.zh
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
        opacity: hub.intro * hub.chrome
        onPicked: i => hub.open(i)
        onHoveredIndex: i => hub.current = i
    }
}
