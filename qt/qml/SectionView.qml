import QtQuick
import "."
import "SectionData.js" as SD

// 二级界面（参考 PV 1:19 构图）：左上品牌与竖线、黑色部门卡、左下录像带串、上方标志剪影、
// 右侧分页点 + 档案卡 + 铭牌、底部字幕。
// 进入：被点击的方块随机选一种方式（弧线 / 拉伸 / 折叠 / 残影）飞成部门卡，
// 位置、尺寸、底色在整个过程中同时插值；返回时按同一方式飞回。
FocusScope {
    id: view

    property var departments: []
    property int index: -1
    property bool opened: false
    readonly property bool busy: index >= 0
    readonly property var d: index >= 0 ? departments[index] : null
    readonly property var conf: d ? SD.sections[d.n] : null
    readonly property var items: conf ? conf.items : []
    property int target: 0
    readonly property var item: items.length ? items[Math.min(target, items.length - 1)] : null

    property real reveal: 0         // 外围元素整体显现
    property bool landed: false     // 部门卡已由真身接替
    property real tiltX: 0
    property real tiltY: 0

    signal closed()

    visible: busy

    // ── 打开 / 关闭 ──────────────────────────────────────────────────────
    function open(i, r, tileItem) {
        index = i
        target = 0
        panel.tab = 0
        landed = false
        opened = true
        morph.start(r, tileItem, false)
        revealAnim.stop(); hideAnim.stop()
        revealAnim.start()
        chainDelay.restart()
        forceActiveFocus()
    }
    function close() {
        if (!opened) return
        opened = false
        landed = false
        revealAnim.stop()
        hideAnim.start()
        chain.close()
        morph.start(morph.tileRect, null, true)
    }
    function select(k) {
        if (!items.length) return
        const next = Math.max(0, Math.min(items.length - 1, k))
        if (next === target) return
        target = next
        panel.tab = 0
        chain.target = next
        plateSwap.restart()
    }

    Timer { id: chainDelay; interval: 260; onTriggered: chain.open(view.items, view.d.n) }
    NumberAnimation { id: revealAnim; target: view; property: "reveal"; to: 1; duration: 700; easing.type: Easing.OutCubic }
    NumberAnimation { id: hideAnim; target: view; property: "reveal"; to: 0; duration: 260 }

    Keys.onPressed: event => {
        if (!opened) return
        const k = event.key
        if (k === Qt.Key_Escape) { close(); event.accepted = true }
        else if (k === Qt.Key_Down || k === Qt.Key_Right) { select(target + 1); event.accepted = true }
        else if (k === Qt.Key_Up || k === Qt.Key_Left) { select(target - 1); event.accepted = true }
        else if (k >= Qt.Key_1 && k <= Qt.Key_9) {
            const t = k - Qt.Key_1
            if (t < SD.pages(item).length) panel.tab = t
            event.accepted = true
        }
    }
    WheelHandler {
        enabled: view.opened
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: event => view.select(view.target + (event.angleDelta.y < 0 ? 1 : -1))
    }
    HoverHandler {
        enabled: view.opened
        onPointChanged: {
            view.tiltY = (point.position.x / view.width - 0.5) * 3
            view.tiltX = -(point.position.y / view.height - 0.5) * 2
        }
    }
    // 吞掉点击，避免穿透到背后的索引
    MouseArea { anchors.fill: parent; enabled: view.opened }

    // ── 左上：品牌、竖线、数据库标签 ─────────────────────────────────────
    Rectangle {
        x: 430
        width: 2
        height: 640
        color: Theme.ink
        transformOrigin: Item.Top
        scale: 1
        opacity: view.reveal > 0 ? 1 : 0
        transform: Scale { yScale: Math.min(1, view.reveal * 1.3) }
    }
    Column {
        x: 64 - 20 * (1 - view.reveal)
        y: 122
        opacity: view.reveal
        Text { text: "AUTO-MAS"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 35; font.letterSpacing: 4 }
        Row {
            Text { text: "ANALYSIS "; color: Theme.ink; font.family: Theme.font; font.pixelSize: 35; font.letterSpacing: 4 }
            Text { text: "OS"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 35; font.weight: Font.Bold; font.letterSpacing: 4 }
        }
    }
    Column {
        x: 50
        y: 370
        spacing: 22
        opacity: view.reveal
        Rectangle { width: 14; height: 3; color: Theme.ink }
        Rectangle {
            width: dbText.implicitWidth + 12
            height: 14
            color: Theme.ink
            Text { id: dbText; anchors.centerIn: parent; text: "AUTO-MAS LOCAL DATABASE"; color: Theme.paper; font.family: Theme.font; font.pixelSize: 8; font.weight: Font.Bold; font.letterSpacing: 1 }
        }
    }

    // ── 上方：标志剪影（半调网点），切换条目时转动 ─────────────────────────
    Item {
        id: hero
        x: 690
        y: -60 + 30 * (1 - view.reveal)
        width: 380
        height: 540
        opacity: view.reveal
        Canvas {
            id: heroCanvas
            anchors.fill: parent
            renderStrategy: Canvas.Cooperative
            transform: Rotation {
                origin.x: 190
                origin.y: 300
                angle: view.target * 24
                Behavior on angle { NumberAnimation { duration: 900; easing.type: Easing.OutCubic } }
            }
            onPaint: {
                const g = getContext("2d")
                g.reset()
                g.fillStyle = Theme.dark ? "#2c383d" : "#101110"
                g.strokeStyle = g.fillStyle
                // 半尺寸版的 AUTO-MAS 圆环标志
                g.lineWidth = 48
                g.beginPath(); g.arc(190, 300, 116, 0, Math.PI * 2); g.stroke()
                g.lineWidth = 42
                g.beginPath()
                g.moveTo(190, 114); g.lineTo(190, 189)
                g.moveTo(190, 411); g.lineTo(190, 486)
                g.moveTo(4, 300); g.lineTo(79, 300)
                g.moveTo(301, 300); g.lineTo(376, 300)
                g.stroke()
                g.lineWidth = 27
                g.beginPath(); g.moveTo(118, 372); g.lineTo(262, 228); g.stroke()
                g.beginPath(); g.arc(190, 300, 32, 0, Math.PI * 2); g.fill()
                // 网点只落在标志上
                g.globalCompositeOperation = "source-atop"
                g.fillStyle = Theme.dark ? "#43525a" : "#2a2b2a"
                for (let y = 2; y < height; y += 7)
                    for (let x = 2; x < width; x += 7) g.fillRect(x, y, 2, 2)
                g.globalCompositeOperation = "source-over"
                g.fillStyle = Theme.accent
                g.beginPath(); g.arc(190, 300, 11, 0, Math.PI * 2); g.fill()
            }
            Connections { target: Theme; function onDarkChanged() { heroCanvas.requestPaint() } }
        }
        Text {
            id: heroNum
            x: 250
            y: 330
            text: String(view.target + 1).padStart(2, "0")
            color: "transparent"
            style: Text.Outline
            styleColor: Qt.rgba(Theme.ink.r, Theme.ink.g, Theme.ink.b, 0.16)
            font.family: Theme.font
            font.pixelSize: 150
            font.weight: Font.Bold
        }
    }

    // ── 左侧黑色部门卡 ───────────────────────────────────────────────────
    Item {
        id: sec
        x: 248
        y: 300
        width: 410
        height: 329
        z: 3
        Rectangle {
            x: 50
            y: view.reveal > 0.3 ? 0 : 8
            width: tabText.implicitWidth + 48
            height: 39
            color: Theme.dark ? "#2a363b" : "#e3e1dc"
            opacity: view.reveal
            Behavior on y { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
            Text { id: tabText; anchors.centerIn: parent; text: "SECTION"; color: Theme.dark ? Theme.ink : "#333333"; font.family: Theme.font; font.pixelSize: 20; font.letterSpacing: 1.2 }
        }
        Rectangle {
            id: box
            y: 39
            width: 410
            height: 290
            visible: view.landed
            gradient: Gradient {
                orientation: Gradient.Vertical
                GradientStop { position: 0; color: Theme.block }
                GradientStop { position: 0.55; color: Qt.lighter(Theme.block, 2.2) }
                GradientStop { position: 1; color: Theme.block }
            }
            Rectangle { anchors.right: parent.right; anchors.rightMargin: 18; y: 16; width: 14; height: 14; radius: 7; color: "#9a9893" }
            Column {
                id: boxText
                anchors.centerIn: parent
                opacity: view.landed ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 300 } }
                Repeater {
                    model: view.d ? view.d.code.split("\n") : []
                    Text {
                        required property string modelData
                        anchors.horizontalCenter: parent.horizontalCenter
                        height: font.pixelSize * 0.92
                        text: modelData
                        color: Theme.blockText
                        font.family: Theme.font
                        font.pixelSize: view.d && view.d.code.indexOf("\n") >= 0 ? 96 : 120
                        font.weight: Font.Black
                        verticalAlignment: Text.AlignVCenter
                    }
                }
                Item { width: 1; height: 10 }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: view.d ? view.d.sub : ""; color: Theme.blockText; font.family: Theme.font; font.pixelSize: 13; font.letterSpacing: 1.3 }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: view.d ? view.d.zh : ""; color: Theme.blockText; font.family: Theme.font; font.pixelSize: 13; topPadding: 4 }
            }
        }
    }

    // ── 左下：录像带串 + 访问等级 ───────────────────────────────────────────
    CassetteChain {
        id: chain
        x: 0
        y: 440
        width: 900
        height: 640
        z: 2
        onPicked: k => view.select(k)
    }
    Row {
        x: 0
        y: 956
        z: 4
        spacing: 26
        opacity: view.reveal
        Rectangle { y: 4; width: 46; height: 14; color: Theme.ink }
        Column {
            Text { text: view.d ? view.d.code.replace("\n", " ") + " SECTION" : ""; color: Theme.ink; font.family: Theme.font; font.pixelSize: 15; font.letterSpacing: 0.6 }
            Text { text: "[LIMITED ACCESS]"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 15; font.weight: Font.Bold; font.letterSpacing: 0.6 }
        }
    }

    // ── 右侧：分页点、档案卡、铭牌 ───────────────────────────────────────
    Row {
        id: pager
        x: 1150
        y: 58
        z: 5
        spacing: 4
        opacity: view.reveal
        Repeater {
            model: view.items.length
            Item {
                id: dot
                required property int index
                readonly property bool on: view.target === index
                width: on ? 42 : 22
                height: 22
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: String(index + 1).padStart(2, "0") + " " + (view.items[index] ? view.items[index].name : "")
                Keys.onSpacePressed: view.select(index)
                Rectangle { visible: dot.on; y: 10; width: 12; height: 2; color: Theme.accent }
                Rectangle { visible: dot.on; x: 30; y: 10; width: 12; height: 2; color: Theme.accent }
                Rectangle {
                    anchors.centerIn: parent
                    width: dot.on ? 12 : 6
                    height: width
                    radius: width / 2
                    color: dot.on ? "transparent" : Theme.accent
                    border.width: dot.on ? 2 : 0
                    border.color: Theme.accent
                    scale: dotMouse.containsMouse && !dot.on ? 1.6 : 1
                    Behavior on scale { NumberAnimation { duration: 150 } }
                }
                Rectangle { anchors.fill: parent; color: "transparent"; border.width: 2; border.color: Theme.accent; visible: dot.activeFocus }
                MouseArea { id: dotMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: view.select(dot.index) }
            }
        }
    }

    Item {
        id: glass
        x: 1150
        y: 92
        z: 5
        width: 730
        height: 800
        opacity: Math.max(0, Math.min(1, (view.reveal - 0.3) / 0.5))
        transform: [
            Rotation { origin.x: 730; origin.y: 400; axis { x: 0; y: 1; z: 0 } angle: 2 + 16 * (1 - view.reveal) + view.tiltY },
            Rotation { origin.x: 365; origin.y: 400; axis { x: 1; y: 0; z: 0 } angle: view.tiltX },
            Translate { x: 40 * (1 - view.reveal) }
        ]
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Theme.dark ? Qt.rgba(0.11, 0.15, 0.17, 0.86) : Qt.rgba(1, 1, 1, 0.78) }
                GradientStop { position: 0.6; color: Theme.dark ? Qt.rgba(0.11, 0.15, 0.17, 0.72) : Qt.rgba(0.965, 0.957, 0.945, 0.62) }
                GradientStop { position: 1; color: Theme.dark ? Qt.rgba(0.11, 0.15, 0.17, 0.82) : Qt.rgba(1, 1, 1, 0.72) }
            }
            border.width: 1
            border.color: Qt.rgba(Theme.ink.r, Theme.ink.g, Theme.ink.b, 0.14)
        }
        ArchivePanel {
            id: panel
            x: 30
            y: 20
            width: parent.width - 60
            height: parent.height - 40
            dept: view.d
            item: view.item
            itemIndex: view.target
            onToast: text => toast.show(text)
        }
    }

    Item {
        id: plate
        x: 1150
        y: 910
        z: 5
        width: 730
        height: 100
        opacity: view.reveal
        transform: Translate { x: 30 * (1 - view.reveal) }
        property real swap: 1
        SequentialAnimation {
            id: plateSwap
            PropertyAction { target: plate; property: "swap"; value: 0 }
            NumberAnimation { target: plate; property: "swap"; to: 1; duration: 350; easing.type: Easing.OutCubic }
        }
        Rectangle {
            width: 116
            height: 64
            color: Theme.block
            Column {
                anchors.centerIn: parent
                spacing: 3
                Emblem { anchors.horizontalCenter: parent.horizontalCenter; width: 34; height: 34; ink: Theme.blockText; core: Theme.accent }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "AUTO-MAS"; color: Theme.blockText; font.family: Theme.font; font.pixelSize: 6; font.weight: Font.Bold; font.letterSpacing: 1.8 }
            }
        }
        Column {
            x: 132
            y: -4 + 10 * (1 - plate.swap)
            width: parent.width - 132
            opacity: plate.swap
            Text { width: parent.width; elide: Text.ElideRight; text: view.d ? view.d.code.replace("\n", " ") + " / " + view.d.zh : ""; color: Theme.ink; font.family: Theme.font; font.pixelSize: 14; font.letterSpacing: 0.6 }
            Text { width: parent.width; elide: Text.ElideRight; text: view.item ? view.item.name : ""; color: Theme.ink; font.family: Theme.font; font.pixelSize: 34; font.weight: Font.Bold; font.letterSpacing: 0.7 }
        }
        Rectangle {
            x: 116
            y: 62
            width: (parent.width - 116) * Math.min(1, view.reveal * 1.2)
            height: 2
            color: Theme.ink
        }
        Row {
            x: 132
            y: 72 + 10 * (1 - plate.swap)
            opacity: plate.swap
            Text { text: view.d ? view.d.n + "-" + String(view.target + 1).padStart(2, "0") : ""; color: Theme.ink; font.family: Theme.font; font.pixelSize: 13; font.weight: Font.Bold; font.letterSpacing: 0.8 }
            Text { text: view.item ? "  ·  " + view.item.en : ""; color: Theme.ink; font.family: Theme.font; font.pixelSize: 13; font.letterSpacing: 0.8 }
        }
    }

    // ── 底部：字幕、POWERED BY、提示 ─────────────────────────────────────
    Text {
        width: parent.width
        y: 1026
        z: 6
        horizontalAlignment: Text.AlignHCenter
        text: view.conf ? view.conf.caption + " 共 " + view.items.length + " 项。" : ""
        color: "#ffffff"
        style: Text.Outline
        styleColor: Qt.rgba(0, 0, 0, 0.75)
        font.family: Theme.font
        font.pixelSize: 19
        font.letterSpacing: 1.5
        opacity: view.reveal
    }
    Row {
        anchors.right: parent.right
        anchors.rightMargin: 56
        y: 1044
        spacing: 40
        opacity: view.reveal
        Text { anchors.verticalCenter: parent.verticalCenter; text: "滚轮 / ↑↓ 切换条目 · 1–9 切换分页 · ESC 返回"; color: Theme.muted; font.family: Theme.font; font.pixelSize: 11; font.letterSpacing: 2 }
        Row {
            Text { text: "POWERED BY "; color: Theme.ink; font.family: Theme.font; font.pixelSize: 14; font.letterSpacing: 0.6 }
            Text { text: "AUTO-MAS"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 14; font.weight: Font.Bold; font.letterSpacing: 0.6 }
        }
    }

    Rectangle {
        id: back
        anchors.right: parent.right
        anchors.rightMargin: 56
        y: 40
        z: 7
        width: backText.implicitWidth + 36
        height: 38
        opacity: view.reveal
        color: backMouse.containsMouse || back.activeFocus ? Theme.ink : "transparent"
        border.width: 1.5
        border.color: Theme.ink
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: qsTr("返回一级界面")
        Keys.onReturnPressed: view.close()
        Keys.onSpacePressed: view.close()
        Text {
            id: backText
            anchors.centerIn: parent
            text: "← RETURN TO INDEX"
            color: backMouse.containsMouse || back.activeFocus ? Theme.paper : Theme.ink
            font.family: Theme.font
            font.pixelSize: 13
            font.weight: Font.Bold
            font.letterSpacing: 3.6
        }
        MouseArea { id: backMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: view.close() }
    }

    // ── 提示条 ─────────────────────────────────────────────────────────
    Rectangle {
        id: toast
        anchors.right: parent.right
        anchors.rightMargin: 72
        y: 980 + 10 * (1 - shownP)
        z: 40
        width: toastRow.implicitWidth + 40
        height: 44
        color: Theme.ink
        property real shownP: 0
        opacity: shownP
        function show(t) {
            toastText.text = t
            toastIn.restart()
            toastTimer.restart()
        }
        NumberAnimation { id: toastIn; target: toast; property: "shownP"; to: 1; duration: 220; easing.type: Easing.OutCubic }
        NumberAnimation { id: toastOut; target: toast; property: "shownP"; to: 0; duration: 200 }
        Timer { id: toastTimer; interval: 1800; onTriggered: toastOut.restart() }
        Row {
            id: toastRow
            anchors.centerIn: parent
            spacing: 12
            Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 10; height: 10; color: Theme.accent }
            Text { id: toastText; color: Theme.paper; font.family: Theme.font; font.pixelSize: 14; font.letterSpacing: 1.6 }
        }
    }

    // ── 过渡体：方块 ↔ 部门卡 ────────────────────────────────────────────
    Item {
        id: morph
        z: 50
        visible: false

        property string kind: "arc"
        property real sign: 1
        property bool reverse: false
        property rect tileRect: Qt.rect(0, 0, 0, 0)
        property color fromColor: "transparent"
        property real p: 0
        readonly property rect cardRect: Qt.rect(sec.x, sec.y + box.y, box.width, box.height)

        readonly property var durations: ({ arc: 720, stretch: 640, fold: 820, echo: 760 })
        readonly property var kinds: ["arc", "stretch", "fold", "echo"]

        function start(r, tileItem, rev) {
            tileRect = r
            reverse = rev
            if (!rev) {
                kind = kinds[Math.floor(Math.random() * kinds.length)]
                sign = Math.random() < 0.5 ? -1 : 1
                const st = view.d.style
                fromColor = st === "block" ? Theme.block : st === "card" ? Theme.paper : Qt.rgba(Theme.block.r, Theme.block.g, Theme.block.b, 0)
                snap.sourceItem = tileItem
                snap.scheduleUpdate()
            }
            anim.stop()
            anim.from = rev ? 1 : 0
            anim.to = rev ? 0 : 1
            anim.duration = durations[kind]
            p = anim.from
            visible = true
            anim.start()
        }

        // 三次贝塞尔缓动（与 CSS cubic-bezier 相同）
        function bezier(x1, y1, x2, y2, x) {
            if (x <= 0) return 0
            if (x >= 1) return 1
            const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx
            const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by
            let t = x
            for (let i = 0; i < 8; i++) {
                const X = ((ax * t + bx) * t + cx) * t - x
                const dX = (3 * ax * t + 2 * bx) * t + cx
                if (Math.abs(dX) < 1e-6) break
                t = Math.max(0, Math.min(1, t - X / dX))
            }
            return ((ay * t + by) * t + cy) * t
        }
        function eMove(x) { return bezier(0.7, 0, 0.2, 1, x) }
        function eSize(x) { return bezier(0.5, 0, 0.1, 1, x) }
        function eSoft(x) { return bezier(0.2, 0.8, 0.2, 1, x) }
        function clamp01(v) { return Math.max(0, Math.min(1, v)) }
        function mix(a, b, t) { return a + (b - a) * t }

        // 给定 p 的矩形：中心 cx, cy 与宽高 w, h
        function at(q) {
            q = clamp01(q)
            const a = { cx: tileRect.x + tileRect.width / 2, cy: tileRect.y + tileRect.height / 2, w: tileRect.width, h: tileRect.height }
            const b = { cx: cardRect.x + cardRect.width / 2, cy: cardRect.y + cardRect.height / 2, w: cardRect.width, h: cardRect.height }
            if (kind === "fold") {
                const p1 = eSoft(clamp01(q / 0.34)), p2 = eMove(clamp01((q - 0.14) / 0.6)), p3 = eSoft(clamp01((q - 0.6) / 0.4))
                const bar = 6
                return { cx: mix(a.cx, b.cx, p2), cy: mix(a.cy, b.cy - b.h / 2 + bar / 2, p2) + (b.h / 2 - bar / 2) * p3,
                         w: mix(a.w, b.w, p2), h: p3 > 0 ? mix(bar, b.h, p3) : mix(a.h, bar, p1) }
            }
            const m = eMove(q), s = eSize(q)
            if (kind === "stretch") {
                const k = Math.sin(Math.PI * m) * 0.45
                const dx = b.cx - a.cx, dy = b.cy - a.cy, L = Math.hypot(dx, dy) || 1, hx = Math.abs(dx) / L, hy = Math.abs(dy) / L
                const w = mix(a.w, b.w, s), h = mix(a.h, b.h, s)
                return { cx: mix(a.cx, b.cx, m), cy: mix(a.cy, b.cy, m), w: w * (1 + k * hx - k * 0.5 * hy), h: h * (1 + k * hy - k * 0.5 * hx) }
            }
            // arc / echo：沿二次贝塞尔曲线移动
            const mx = (a.cx + b.cx) / 2, my = (a.cy + b.cy) / 2, dx = b.cx - a.cx, dy = b.cy - a.cy
            const L = Math.hypot(dx, dy) || 1, off = Math.min(220, L * 0.32) * sign
            const kx = mx - dy / L * off, ky = my + dx / L * off, u = 1 - m
            return { cx: u * u * a.cx + 2 * u * m * kx + m * m * b.cx, cy: u * u * a.cy + 2 * u * m * ky + m * m * b.cy, w: mix(a.w, b.w, s), h: mix(a.h, b.h, s) }
        }
        function colorAt(q, alpha) {
            const c = eSoft(clamp01(q / 0.7))
            const f = fromColor, t = Theme.block
            return Qt.rgba(mix(f.r, t.r, c), mix(f.g, t.g, c), mix(f.b, t.b, c), mix(f.a, 1, c) * alpha)
        }

        NumberAnimation {
            id: anim
            target: morph
            property: "p"
            easing.type: Easing.Linear
            onFinished: {
                if (morph.reverse) {
                    morph.visible = false
                    view.index = -1
                    view.closed()
                } else {
                    view.landed = true
                    morph.visible = false
                }
            }
        }

        // 残影：落后主体 0.09 / 0.18 的两道淡影
        Repeater {
            model: morph.kind === "echo" ? [0.09, 0.18] : []
            Rectangle {
                required property real modelData
                readonly property real lin: morph.reverse ? 1 - morph.p : morph.p
                readonly property real gp: morph.reverse ? 1 - (lin - modelData) : lin - modelData
                readonly property var r: morph.at(gp)
                visible: lin > modelData && lin < 1
                x: r.cx - r.w / 2
                y: r.cy - r.h / 2
                width: r.w
                height: r.h
                color: morph.colorAt(gp, modelData < 0.1 ? 0.35 : 0.16)
            }
        }
        Rectangle {
            id: body
            readonly property var r: morph.at(morph.p)
            x: r.cx - r.w / 2
            y: r.cy - r.h / 2
            width: r.w
            height: r.h
            color: morph.colorAt(morph.p, 1)
            clip: true
            // 方块原有内容：等比缩放跟随并在前段淡出，文字不做非等比拉伸
            ShaderEffectSource {
                id: snap
                live: false
                hideSource: false
                width: morph.tileRect.width
                height: morph.tileRect.height
                anchors.centerIn: parent
                scale: Math.min(body.width / Math.max(1, morph.tileRect.width), body.height / Math.max(1, morph.tileRect.height))
                opacity: 1 - morph.clamp01(morph.p / 0.4)
            }
        }
    }
}
