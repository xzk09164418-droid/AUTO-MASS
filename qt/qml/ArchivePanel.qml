import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic as C
import QtQuick.Effects
import "."
import "SectionData.js" as SD
import "Live.js" as Live

// 右侧档案卡：条目的功能分页 + 数据块 + 操作按钮。
// 交互是二级界面的主体：所有控件都可操作，字段名悬停显示对应的后端配置键。
Item {
    id: panel

    property var dept: null
    property var item: null
    property int itemIndex: 0
    property int tab: 0
    signal toast(string text)
    signal confirmDelete(string name, string api)
    signal requestEnhanced()
    // 实时条目的按钮与行内操作交给 SectionView 调后端
    signal liveAction(string name)
    signal liveOp(var op)
    property bool saving: false
    property int edits: 0                   // 控件改动计数（驱动「未保存 N 处」）
    readonly property int unsaved: { edits; return item && item.live ? Live.dirtyCount(item) : 0 }
    signal motionChosen(string motion)      // 用户切换了动态效果挡位（记住选择；离开增强挡位时标记延后删除）
    onTabChanged: if (item) item._tab = tab

    readonly property var pages: item ? SD.pages(item) : []
    readonly property var page: pages.length ? pages[Math.min(tab, pages.length - 1)] : null

    // 当前显示的页（切换时先淡出旧页再换内容）
    property var shown: null
    property string excl: ""                 // 队列：定时启动与循环队列互斥
    onExclChanged: if (item && item.exclusive !== undefined && item.exclusive !== excl) item.exclusive = excl

    // 快速启动的模拟运行
    property string runState: "idle"
    property real runPct: 0
    property string runTitle: "待命"
    property string runText: "选择任务后开始执行"
    property string queueName: SD.TASKS[0]
    property var statOverride: ({})

    property var lastItem: null
    property int blockCount: 0
    property real dec: 1            // 解密进度 0→1（借鉴 RhineLabUI 的同步解密）
    property real tabFade: 1
    property int tickets: 0         // 遮挡条依次退开的序号
    function ticket() { return tickets++ }
    // 解密服务于加载：先快速合拢（对角线与磨砂罩上，0→0.45），数据还在读取时停在合拢状态等待；
    // 一旦就绪立即退开（0.45→1，约 0.3 秒），不再按固定 1.5 秒走完
    property bool loading: false
    readonly property real holdAt: 0.45
    function startDec() {
        decIn.stop(); decOut.stop()
        if (!Theme.richMotion) { dec = 1; return }
        dec = 0
        decIn.restart()
    }
    function finishDec() { if (!loading && !decIn.running && dec < 1 && !decOut.running) decOut.restart() }
    onLoadingChanged: finishDec()
    NumberAnimation { id: decIn; target: panel; property: "dec"; to: panel.holdAt; duration: 160; easing.type: Easing.Linear; onFinished: panel.finishDec() }
    NumberAnimation { id: decOut; target: panel; property: "dec"; to: 1; duration: 300; easing.type: Easing.Linear }
    NumberAnimation { id: tabFadeAnim; target: panel; property: "tabFade"; from: 0; to: 1; duration: 150 }

    // 换条目：淡出后重新解密；换页签：只换正文与操作并 150ms 淡入
    function refresh() {
        if (!page) return
        if (shown === null) { lastItem = item; apply(); startDec(); return }
        if (item !== lastItem) { lastItem = item; swapOut.restart(); return }
        apply()
        if (Theme.richMotion) tabFadeAnim.restart()
    }
    function apply() {
        runTimer.stop()
        runState = "idle"; runPct = 0; runTitle = "待命"; runText = "选择任务后开始执行"; statOverride = ({})
        excl = item && item.exclusive !== undefined ? item.exclusive : ""
        tickets = 0
        // 先清零再给数量，保证换页时数据块全部重建（入场动画、遮挡条序号随之重置）
        blockCount = 0
        shown = page
        blockCount = page.blocks.length
        content.opacity = 1
        content.y = 0
    }
    onPageChanged: refresh()
    // 数据块内容在原对象上改动后（如队列项表格换窗口），整页重建
    // 当前页里可滚动的表格（没有则为 null）；鼠标是否在档案卡上
    property Item scrollTable: null
    readonly property bool hovered: cardHover.hovered
    HoverHandler { id: cardHover }
    function rebuild() { if (page) { apply(); if (Theme.richMotion) tabFadeAnim.restart() } }

    SequentialAnimation {
        id: swapOut
        ParallelAnimation {
            NumberAnimation { target: content; property: "opacity"; to: 0; duration: 140 }
            NumberAnimation { target: content; property: "y"; to: -10; duration: 140; easing.type: Easing.InCubic }
        }
        ScriptAction { script: { panel.apply(); panel.startDec() } }
    }

    function act(name) {
        const api = shown ? shown.api : ""
        if (item && item.live) { liveAction(name); return }
        if (name === "开始执行") startRun()
        else if (name === "停止" || name === "停止任务") { runTimer.stop(); runState = "idle"; runPct = 0; runTitle = "已停止"; runText = "队列已手动停止"; toast("队列已停止 · POST /api/dispatch/stop") }
        else if (/删除/.test(name)) confirmDelete(item ? item.name : "", api)
        else if (/保存/.test(name)) toast("已保存 · " + api)
        else toast("演示：" + name + " · " + api)
    }

    readonly property var runSteps: ["主号 · BGI 每日", "小号 · BGI 每日", "鸣潮主号 · 鸣潮日常", "星铁 · 星铁清体力"]
    property int runN: 0
    function startRun() {
        runN = 0
        runState = "run"; runPct = 4; runTitle = "运行"; runText = queueName + " · " + runSteps[0]
        runTimer.restart()
        toast("已开始执行：" + queueName + " · POST /api/dispatch/start")
    }
    Timer {
        id: runTimer
        interval: 700
        repeat: true
        onTriggered: {
            panel.runN++
            const total = panel.runSteps.length * 3
            if (panel.runN >= total) {
                stop()
                panel.runState = "done"; panel.runPct = 100; panel.runTitle = "完成"; panel.runText = panel.queueName + " · 本轮全部完成"
                panel.statOverride = { done: "8", left: "0" }
                return
            }
            panel.runPct = Math.round(panel.runN / total * 100)
            panel.runText = panel.queueName + " · " + panel.runSteps[Math.floor(panel.runN / 3)]
        }
    }

    // ── 外观小件 ─────────────────────────────────────────────────────────
    component Label: Text {
        color: Theme.ink
        font.family: Theme.font
        font.pixelSize: 15
        verticalAlignment: Text.AlignVCenter
    }
    component BlockHead: RowLayout {
        property string title: ""
        width: parent ? parent.width : 0
        height: 24
        spacing: 12
        Rectangle { implicitWidth: 14; implicitHeight: 2; color: Theme.accent }
        Text { text: parent.title; color: Theme.muted; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Bold; font.letterSpacing: 2.6 }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.hair }
    }
    component Btn: Rectangle {
        id: btn
        property string text: ""
        property bool primary: false
        property bool danger: false
        property bool small: false
        signal clicked()
        implicitWidth: btnText.implicitWidth + (small ? 20 : 40)
        implicitHeight: small ? 28 : 40
        color: primary ? (btnMouse.containsMouse ? Theme.accent : Theme.ink) : "transparent"
        border.width: 1.5
        border.color: btnMouse.containsMouse ? (danger ? Theme.error : Theme.accent) : (primary ? Theme.ink : Theme.ink)
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: text
        Keys.onReturnPressed: clicked()
        Keys.onSpacePressed: clicked()
        Rectangle { anchors.fill: parent; anchors.margins: -4; color: "transparent"; border.width: 2; border.color: Theme.accent; visible: btn.activeFocus }
        Text {
            id: btnText
            anchors.centerIn: parent
            text: btn.text
            color: btn.primary ? (btnMouse.containsMouse ? "#ffffff" : Theme.paper) : btnMouse.containsMouse ? (btn.danger ? Theme.error : Theme.accent) : Theme.ink
            font.family: Theme.font
            font.pixelSize: btn.small ? 12 : 14
            font.weight: Font.Bold
            font.letterSpacing: btn.small ? 1 : 2
        }
        MouseArea { id: btnMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: btn.clicked() }
    }

    // ── 控件 ────────────────────────────────────────────────────────────
    component Tog: Item {
        id: tg
        property var spec
        objectName: "tog:" + (spec && spec.key ? spec.key : "")
        property bool local: spec.v
        onLocalChanged: if (spec.v !== local) { spec.v = local; spec.dirty = true; panel.edits++ }
        readonly property bool on: spec.x ? panel.excl === spec.x : local
        implicitWidth: 72
        implicitHeight: 24
        activeFocusOnTab: true
        Accessible.role: Accessible.CheckBox
        Accessible.checked: on
        function flip() {
            if (spec.x) {
                const other = spec.x === "time" ? "cycle" : "time"
                if (tg.on) panel.excl = ""
                else {
                    if (panel.excl === other) panel.toast(spec.x === "time" ? "已关闭循环队列：定时与循环互斥" : "已关闭定时启动：定时与循环互斥")
                    panel.excl = spec.x
                }
                if (panel.item) Live.eachSpec(panel.item, function (sp) {
                    if (sp.x) { const v = panel.excl === sp.x; if (sp.v !== v) { sp.v = v; sp.dirty = true } }
                })
                panel.edits++
            } else local = !local
        }
        Keys.onSpacePressed: flip()
        Keys.onReturnPressed: flip()
        Rectangle {
            id: track
            y: 4
            width: 34
            height: 16
            color: "transparent"
            border.width: 1.5
            border.color: tgMouse.containsMouse || tg.activeFocus ? Theme.accent : Theme.ink
            Rectangle {
                y: 3
                x: tg.on ? 19 : 3
                width: 11
                height: 10
                color: tg.on ? Theme.accent : Theme.muted
                Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
            }
        }
        Text { x: 42; anchors.verticalCenter: track.verticalCenter; text: tg.on ? "开" : "关"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 14 }
        MouseArea { id: tgMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: tg.flip() }
    }
    component Field: C.TextField {
        id: fld
        property bool mono: false
        font.family: mono ? "Consolas" : Theme.font
        font.pixelSize: mono ? 14 : 15
        color: Theme.ink
        selectionColor: Theme.accent
        selectedTextColor: "#ffffff"
        leftPadding: 2
        rightPadding: 2
        topPadding: 4
        bottomPadding: 4
        implicitHeight: 30
        background: Rectangle {
            color: "transparent"
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1.5; color: fld.activeFocus ? Theme.accent : fld.hovered ? Theme.ink : Theme.hair }
        }
    }
    component Seg: Row {
        id: sg
        property var spec
        readonly property var motions: ["reduced", "standard", "enhanced"]
        readonly property var themes: ["system", "light", "dark"]
        property int cur: spec.k === "motion" ? Math.max(0, motions.indexOf(Theme.motion))
            : spec.k === "theme" ? Math.max(0, themes.indexOf(Theme.mode)) : spec.v
        // 动态效果挡位：直接改 Theme.motion；增强挡位需要另行安装的 3D 组件
        onCurChanged: if (spec.k === "theme") { Theme.mode = themes[cur] }
        else if (spec.k !== "motion") { if (spec.v !== cur) { spec.v = cur; spec.dirty = true; panel.edits++ } }
        else if (motions[cur] !== Theme.motion) {
            if (cur === 2 && !Theme.enhancedAvailable) {
                // 组件缺失：先回到当前挡位，二次确认后再下载
                cur = Math.max(0, motions.indexOf(Theme.motion))
                panel.requestEnhanced()
                return
            }
            Theme.motion = motions[cur]
            panel.toast("动态效果：" + spec.opts[cur])
            panel.motionChosen(motions[cur])
        }
        Repeater {
            model: sg.spec.opts
            Rectangle {
                id: sb
                required property string modelData
                required property int index
                readonly property bool on: sg.cur === index
                width: sbText.implicitWidth + 24
                height: 28
                color: on ? Theme.ink : "transparent"
                border.width: 1.5
                border.color: Theme.ink
                activeFocusOnTab: true
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData
                Accessible.checked: on
                Keys.onSpacePressed: sg.cur = index
                // 相邻按钮共用边线
                x: index * -1.5
                Rectangle { anchors.fill: parent; anchors.margins: -3; color: "transparent"; border.width: 2; border.color: Theme.accent; visible: sb.activeFocus }
                Text {
                    id: sbText
                    anchors.centerIn: parent
                    text: sb.modelData
                    color: sb.on ? Theme.paper : sbMouse.containsMouse ? Theme.accent : Theme.ink
                    font.family: Theme.font
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                }
                MouseArea { id: sbMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: sg.cur = sb.index }
            }
        }
    }
    component Sel: C.ComboBox {
        id: cb
        property var spec
        model: spec.opts
        currentIndex: spec.v
        implicitHeight: 30
        implicitWidth: Math.max(110, contentWidthHint + 40)
        property real contentWidthHint: 0
        font.family: Theme.font
        font.pixelSize: 15
        onActivated: {
            if (spec.v !== currentIndex) { spec.v = currentIndex; spec.dirty = true; panel.edits++ }
            if (spec.k === "queue") panel.queueName = currentText
        }
        Component.onCompleted: {
            let w = 0
            for (const o of spec.opts) w = Math.max(w, metrics.advanceWidth(o))
            contentWidthHint = w
            if (spec.k === "queue") panel.queueName = currentText
        }
        FontMetrics { id: metrics; font: cb.font }
        contentItem: Text {
            leftPadding: 2
            text: cb.displayText
            color: Theme.ink
            font: cb.font
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        indicator: Text {
            x: cb.width - width - 4
            anchors.verticalCenter: parent.verticalCenter
            text: "▾"
            color: cb.hovered ? Theme.accent : Theme.ink
            font.pixelSize: 13
        }
        background: Rectangle {
            color: "transparent"
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1.5; color: cb.activeFocus || cb.hovered ? Theme.accent : Theme.ink }
        }
        delegate: C.ItemDelegate {
            required property string modelData
            required property int index
            width: cb.width
            highlighted: cb.highlightedIndex === index
            contentItem: Text { text: modelData; color: highlighted ? Theme.paper : Theme.ink; font: cb.font; verticalAlignment: Text.AlignVCenter }
            background: Rectangle { color: highlighted ? Theme.ink : Theme.paper }
        }
        popup.background: Rectangle { color: Theme.paper; border.width: 1.5; border.color: Theme.ink }
    }
    component Chips: Row {
        id: ch
        property var spec
        spacing: 4
        Repeater {
            model: ["一", "二", "三", "四", "五", "六", "日"]
            Rectangle {
                id: chip
                required property string modelData
                required property int index
                property bool on: ch.spec.v[index] === "1"
                width: 30
                height: 28
                color: on ? Theme.ink : "transparent"
                border.width: 1.5
                border.color: on ? Theme.ink : chipMouse.containsMouse ? Theme.accent : Theme.hair
                Text { anchors.centerIn: parent; text: chip.modelData; color: chip.on ? Theme.paper : Theme.muted; font.family: Theme.font; font.pixelSize: 13; font.weight: Font.DemiBold }
                MouseArea { id: chipMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: {
                    chip.on = !chip.on
                    const m = ch.spec.v.split("")
                    m[chip.index] = chip.on ? "1" : "0"
                    ch.spec.v = m.join("")
                    ch.spec.dirty = true; panel.edits++
                } }
            }
        }
    }
    component Tag: Rectangle {
        property var spec
        readonly property color tint: spec.kind === "ok" ? Theme.success : spec.kind === "err" ? Theme.error
            : spec.kind === "warn" ? Theme.warning : spec.kind === "run" ? Theme.ink : Theme.muted
        implicitWidth: tagText.implicitWidth + 18
        implicitHeight: 22
        color: spec.kind === "run" ? Theme.ink : "transparent"
        border.width: 1
        border.color: tint
        Text { id: tagText; anchors.centerIn: parent; text: parent.spec.t; color: parent.spec.kind === "run" ? Theme.paper : parent.tint; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Bold; font.letterSpacing: 1.4 }
    }

    // 正文遮挡条：解密时按序号依次向右退开
    component Redact: Rectangle {
        property int idx: 0
        Component.onCompleted: idx = Math.min(24, panel.ticket())
        // 只在揭开阶段（dec 0.45→1）依次退开，跟随加载而不是固定时长
        readonly property real t: Math.max(0, Math.min(1, ((panel.dec - panel.holdAt) / (1 - panel.holdAt) - idx * 0.02) / 0.5))
        readonly property real k: 1 - (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)
        visible: panel.dec < 1 && k > 0
        x: 0
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width * 0.7
        height: Math.max(8, Math.min(16, parent.height * 0.36))
        color: Theme.ink
        z: 10
        transform: Scale { origin.x: width; xScale: k }
    }

    // 单个控件：按 spec.c 选择；字符串直接排字
    component Ctl: Loader {
        id: ctl
        property var spec
        readonly property bool stretch: typeof spec === "object" && (spec.c === "inp" || spec.c === "path")
        Layout.fillWidth: stretch
        Layout.alignment: Qt.AlignVCenter
        sourceComponent: typeof spec !== "object" ? cText
            : spec.c === "tog" ? cTog : spec.c === "inp" ? cInp : spec.c === "num" ? cNum
            : spec.c === "time" || spec.c === "date" ? cTime : spec.c === "path" ? cPath
            : spec.c === "seg" ? cSeg : spec.c === "sel" ? cSel : spec.c === "chips" ? cChips
            : spec.c === "tag" ? cTag : spec.c === "mini" ? cMini : spec.c === "unit" ? cUnit : cText
        Component { id: cText; Label { text: String(ctl.spec); elide: Text.ElideRight } }
        Component { id: cUnit; Text { text: ctl.spec.t; color: Theme.muted; font.family: Theme.font; font.pixelSize: 13 } }
        Component { id: cTog; Tog { spec: ctl.spec } }
        Component { id: cInp; Field { text: ctl.spec.v; mono: ctl.spec.mono; onTextEdited: { ctl.spec.v = text; ctl.spec.dirty = true; panel.edits++ } } }
        Component {
            id: cNum
            Row {
                spacing: 8
                Field { width: 76; text: String(ctl.spec.v); horizontalAlignment: Text.AlignRight; onTextEdited: { ctl.spec.v = Number(text); ctl.spec.dirty = true; panel.edits++ } validator: IntValidator { bottom: 0; top: 99999 } }
                Text { visible: ctl.spec.unit !== ""; anchors.verticalCenter: parent.verticalCenter; text: ctl.spec.unit; color: Theme.muted; font.family: Theme.font; font.pixelSize: 13 }
            }
        }
        Component { id: cTime; Field { width: ctl.spec.c === "date" ? 150 : 90; text: ctl.spec.v; mono: true; inputMask: ctl.spec.c === "date" ? "9999-99-99" : "99:99"; onTextEdited: { ctl.spec.v = text; ctl.spec.dirty = true; panel.edits++ } } }
        Component {
            id: cPath
            RowLayout {
                spacing: 10
                Field { Layout.fillWidth: true; text: ctl.spec.v; mono: true; onTextEdited: { ctl.spec.v = text; ctl.spec.dirty = true; panel.edits++ } }
                Btn { text: "浏览"; small: true; onClicked: panel.toast("演示：打开文件选择框") }
            }
        }
        Component { id: cSeg; Seg { spec: ctl.spec } }
        Component { id: cSel; Sel { spec: ctl.spec } }
        Component { id: cChips; Chips { spec: ctl.spec } }
        Component { id: cTag; Tag { spec: ctl.spec } }
        Component {
            id: cMini
            Row {
                spacing: 6
                Repeater {
                    model: ctl.spec.names
                    Btn {
                        required property string modelData
                        required property int index
                        text: modelData
                        small: true
                        onClicked: {
                            if (ctl.spec.ops && ctl.spec.ops[index]) panel.liveOp(ctl.spec.ops[index])
                            else if (text === "启动" || text === "关闭") {
                                panel.toast(text + "模拟器实例 · POST /api/emulator/operate")
                                text = text === "启动" ? "关闭" : "启动"
                            } else if (text === "录制") panel.toast("演示：按下新的组合键")
                            else panel.toast("演示：" + text)
                        }
                    }
                }
            }
        }
    }
    // 一格内容：单个控件或控件数组
    component Cell: RowLayout {
        id: cell
        property var value
        readonly property var list: value && typeof value === "object" && !value.c && value.length !== undefined ? value : [value]
        spacing: 10
        Repeater {
            model: cell.list.length
            Ctl { required property int index; spec: cell.list[index]; Layout.maximumWidth: cell.width }
        }
    }

    // ── 数据块 ──────────────────────────────────────────────────────────
    component KvBlock: Column {
        id: kvb
        property var b
        Repeater {
            model: kvb.b.rows.length
            Item {
                id: kvRow
                required property int index
                readonly property var modelData: kvb.b.rows[index]
                width: parent.width
                height: 42
                Text {
                    id: kvLabel
                    x: 4
                    width: 146
                    height: parent.height
                    verticalAlignment: Text.AlignVCenter
                    text: kvRow.modelData[0]
                    color: Theme.muted
                    font.family: Theme.font
                    font.pixelSize: 14
                    font.letterSpacing: 0.8
                    elide: Text.ElideRight
                    HoverHandler { id: keyHover; enabled: !!kvRow.modelData[2] }
                    C.ToolTip.visible: keyHover.hovered
                    C.ToolTip.text: kvRow.modelData[2] || ""
                    C.ToolTip.delay: 300
                }
                Cell {
                    x: 150
                    width: parent.width - 154
                    anchors.verticalCenter: parent.verticalCenter
                    value: kvRow.modelData[1]
                }
                Item { x: 154; width: parent.width - 158; height: parent.height; Redact {} }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.hair; opacity: 0.7 }
            }
        }
        Rectangle { y: 0; width: parent.width; height: 1; color: Theme.hair; opacity: 0.7 }
    }
    component TableBlock: Column {
        id: tb
        property var b
        // 可滚动的长表（队列项）：一次显示 12 行，鼠标在档案卡上时滚轮滚动
        readonly property int pageRows: 12
        readonly property bool scrollable: !!b.all && b.all.length > pageRows
        property int off: b.offset || 0
        readonly property var rows: b.all ? b.all.slice(off, off + pageRows) : b.rows
        function scroll(d) {
            if (!scrollable) return false
            const next = Math.max(0, Math.min(b.all.length - pageRows, off + d))
            if (next === off) return true
            off = next
            b.offset = off
            return true
        }
        Component.onCompleted: if (scrollable) panel.scrollTable = tb
        Component.onDestruction: if (panel.scrollTable === tb) panel.scrollTable = null
        readonly property var weights: b.weights && b.weights.length === b.cols.length ? b.weights : b.cols.map(() => 1)
        readonly property real wsum: weights.reduce((a, x) => a + x, 0)
        function colW(i) { return (width - 44) * weights[i] / wsum }
        Item {
            width: parent.width
            height: 34
            Row {
                anchors.fill: parent
                Text { width: 44; height: 34; verticalAlignment: Text.AlignVCenter; leftPadding: 6; text: "#"; color: Theme.muted; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Bold; font.letterSpacing: 2 }
                Repeater {
                    model: tb.b.cols
                    Text { required property string modelData; required property int index; width: tb.colW(index); height: 34; verticalAlignment: Text.AlignVCenter; leftPadding: 6; text: modelData; color: Theme.muted; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Bold; font.letterSpacing: 2 }
                }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.hair }
            // 下划线 180ms 移到当前页签
            Rectangle {
                readonly property Item on: tabRep.count > panel.tab ? tabRep.itemAt(panel.tab) : null
                anchors.bottom: parent.bottom
                x: on ? on.x : 0
                width: on ? on.width - 14 : 0
                height: 2
                color: Theme.ink
                Behavior on x { enabled: Theme.richMotion; NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                Behavior on width { enabled: Theme.richMotion; NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
            }
        }
        Item {
            width: tb.width
            height: tb.rows.length * 44
            // 滚动条：一根橙色矩形，不加边框与衬底
            Rectangle {
                visible: tb.scrollable
                x: tb.width + 6
                width: 3
                height: parent.height * tb.pageRows / Math.max(1, tb.b.all ? tb.b.all.length : 1)
                y: parent.height * tb.off / Math.max(1, tb.b.all ? tb.b.all.length : 1)
                color: Theme.accent
                Behavior on y { enabled: Theme.richMotion; NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
            }
        Column {
        Repeater {
            model: tb.rows.length
            Item {
                id: tr
                required property int index
                readonly property var modelData: tb.rows[index]
                width: tb.width
                height: 44
                Rectangle { anchors.fill: parent; color: Theme.ink; opacity: trHover.hovered ? 0.05 : 0 }
                HoverHandler { id: trHover }
                Row {
                    anchors.fill: parent
                    Text { width: 44; height: parent.height; verticalAlignment: Text.AlignVCenter; leftPadding: 6; text: String(tb.off + tr.index + 1).padStart(2, "0"); color: tb.off + tr.index === tb.b.focus ? Theme.accent : Theme.muted; font.family: Theme.font; font.pixelSize: 14 }
                    Repeater {
                        model: tr.modelData.length
                        Item {
                            required property int index
                            readonly property var modelData: tr.modelData[index]
                            width: tb.colW(index)
                            clip: true
                            height: tr.height
                            Cell { x: 6; width: parent.width - 12; anchors.verticalCenter: parent.verticalCenter; value: parent.modelData }
                            Item { x: 6; width: parent.width - 12; height: parent.height; Redact {} }
                        }
                    }
                }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.hair; opacity: 0.7 }
            }
        }
        }
        }
    }
    component StatsBlock: Row {
        id: sb
        property var b
        Repeater {
            model: sb.b.rows
            Rectangle {
                required property var modelData
                width: sb.width / sb.b.rows.length
                height: 74
                color: "transparent"
                border.width: 1
                border.color: Qt.rgba(Theme.hair.r, Theme.hair.g, Theme.hair.b, 0.7)
                Text {
                    x: 14; y: 6
                    text: modelData[2] && panel.statOverride[modelData[2]] !== undefined ? panel.statOverride[modelData[2]] : modelData[1]
                    color: Theme.ink; font.family: Theme.font; font.pixelSize: 32; font.weight: Font.Light
                }
                Text { x: 14; y: 48; text: modelData[0]; color: Theme.muted; font.family: Theme.font; font.pixelSize: 12; font.letterSpacing: 2.4 }
                Item { x: 14; y: 8; width: 90; height: 38; Redact {} }
            }
        }
    }
    component NoteBlock: Item {
        property var b
        implicitHeight: noteText.implicitHeight + 8
        Rectangle { width: 3; height: parent.height; color: Theme.accent }
        Text { id: noteText; x: 14; y: 4; width: parent.width - 14; text: parent.b.text; wrapMode: Text.Wrap; lineHeight: 1.35; color: Theme.muted; font.family: Theme.font; font.pixelSize: 13 }
    }
    component LogBlock: Rectangle {
        property var b
        implicitHeight: b.tall ? 470 : 170
        color: "#0b0c0b"
        clip: true
        Column {
            x: 16; y: 12
            spacing: 4
            Repeater {
                model: parent.parent.b.lines
                Text {
                    required property var modelData
                    textFormat: Text.PlainText
                    text: modelData[0] + "  " + modelData[1]
                    color: modelData[2] === "s" ? "#9cc79f" : modelData[2] === "e" ? "#e58a7f" : "#d9d6cf"
                    font.family: "Consolas"
                    font.pixelSize: 13
                }
            }
        }
    }
    component BannerBlock: Rectangle {
        property var b
        implicitHeight: 170
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: b.c[0] }
            GradientStop { position: 0.55; color: b.c[1] }
            GradientStop { position: 1; color: b.c[2] }
        }
        Rectangle {
            x: 24; y: 20
            width: vText.implicitWidth + 20; height: 24
            color: "transparent"; border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.7)
            Text { id: vText; anchors.centerIn: parent; text: "● " + parent.parent.b.v; color: "#ffffff"; font.family: Theme.font; font.pixelSize: 13; font.weight: Font.Bold; font.letterSpacing: 2 }
        }
        Text { x: 24; anchors.bottom: parent.bottom; anchors.bottomMargin: 18; text: parent.b.title; color: "#ffffff"; font.family: Theme.font; font.pixelSize: 32; font.weight: Font.Bold; font.letterSpacing: 3 }
        Column {
            anchors.right: parent.right; anchors.rightMargin: 22; anchors.bottom: parent.bottom; anchors.bottomMargin: 18
            Text { anchors.right: parent.right; text: "活动剩余时间"; color: "#ffffff"; font.family: Theme.font; font.pixelSize: 12; font.letterSpacing: 2 }
            Text { anchors.right: parent.right; text: parent.parent.b.left; color: "#ffffff"; font.family: Theme.font; font.pixelSize: 30; font.weight: Font.Bold }
        }
    }
    component ListBlock: Column {
        property var b
        Repeater {
            model: parent.b.rows
            Item {
                required property var modelData
                width: parent.width
                height: 42
                Text { x: 4; height: parent.height; verticalAlignment: Text.AlignVCenter; text: modelData[0]; color: Theme.muted; font.family: Theme.font; font.pixelSize: 15 }
                Label { x: 90; height: parent.height; text: modelData[1] }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.hair; opacity: 0.7 }
            }
        }
    }
    component RunBlock: Column {
        property var b
        spacing: 10
        Rectangle { width: parent.width; height: 1; color: Theme.hair; opacity: 0.7 }
        Rectangle {
            width: parent.width; height: 6
            color: Qt.rgba(Theme.ink.r, Theme.ink.g, Theme.ink.b, 0.1)
            Rectangle { height: parent.height; width: parent.width * panel.runPct / 100; color: Theme.accent; Behavior on width { NumberAnimation { duration: 500 } } }
        }
        Row {
            spacing: 16
            Rectangle {
                width: rt.implicitWidth + 20; height: 24
                color: panel.runState === "run" ? Theme.ink : "transparent"
                border.width: 1.5
                border.color: panel.runState === "done" ? Theme.success : Theme.ink
                Text { id: rt; anchors.centerIn: parent; text: panel.runTitle; color: panel.runState === "run" ? Theme.paper : panel.runState === "done" ? Theme.success : Theme.ink; font.family: Theme.font; font.pixelSize: 13; font.weight: Font.Bold; font.letterSpacing: 2.4 }
            }
            Label { height: 24; text: panel.runText }
        }
    }

    // ── 版面 ────────────────────────────────────────────────────────────
    Item {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        height: parent.height

        // 头：编号 / 条目名 · 接口
        Item {
            id: meta
            width: parent.width
            height: 18
            Text {
                text: panel.dept && panel.item ? ("X-0" + panel.dept.n + "    " + panel.dept.n + "-" + String(panel.itemIndex + 1).padStart(2, "0") + "    " + panel.item.name) : ""
                color: Theme.muted
                font.family: Theme.font
                font.pixelSize: 12
                font.weight: Font.Bold
                font.letterSpacing: 2.6
                Text { text: panel.dept ? "X-0" + panel.dept.n : ""; color: Theme.accent; font: parent.font }
            }
            Text {
                anchors.right: parent.right
                text: (panel.unsaved > 0 ? "● 未保存 " + panel.unsaved + " 处    " : "") + (panel.shown ? panel.shown.api || "" : "")
                color: Theme.muted
                font.family: "Consolas"
                font.pixelSize: 12
            }
        }

        // 功能分页
        Item {
            id: tabBar
            visible: panel.pages.length > 1
            y: meta.height + 12
            width: parent.width
            height: visible ? 40 : 0
            Row {
                spacing: 2
                Repeater {
                    id: tabRep
                    model: panel.pages.length > 1 ? panel.pages : []
                    Rectangle {
                        id: tabBtn
                        required property var modelData
                        required property int index
                        readonly property bool on: panel.tab === index
                        width: tabRow.implicitWidth + 28
                        height: 38
                        color: "transparent"
                        activeFocusOnTab: true
                        Accessible.role: Accessible.PageTab
                        Accessible.name: modelData.name
                        Keys.onSpacePressed: panel.tab = index
                        Keys.onReturnPressed: panel.tab = index
                        Rectangle { anchors.fill: parent; anchors.margins: 2; color: "transparent"; border.width: 2; border.color: Theme.accent; visible: tabBtn.activeFocus }
                        Row {
                            id: tabRow
                            anchors.centerIn: parent
                            spacing: 7
                            Text { anchors.baseline: tabName.baseline; text: String(tabBtn.index + 1).padStart(2, "0"); color: tabBtn.on ? Theme.accent : Theme.hair; font.family: Theme.font; font.pixelSize: 10; font.weight: Font.Bold; Behavior on color { ColorAnimation { duration: 180 } } }
                            Text { id: tabName; text: tabBtn.modelData.name; color: tabBtn.on || tabMouse.containsMouse ? Theme.ink : Theme.muted; font.family: Theme.font; font.pixelSize: 15; font.weight: Font.DemiBold; font.letterSpacing: 1.2; Behavior on color { ColorAnimation { duration: 180 } } }
                        }
                        MouseArea { id: tabMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: panel.tab = tabBtn.index }
                    }
                }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 2; color: Theme.ink }
        }

        // 数据块：逐块错开显现
        Column {
            id: body
            opacity: panel.tabFade
            y: tabBar.y + tabBar.height + 16
            width: parent.width
            spacing: 16
            Repeater {
                model: panel.blockCount
                Column {
                    id: blk
                    required property int index
                    readonly property var modelData: panel.shown.blocks[index]
                    width: body.width
                    spacing: 8
                    opacity: 0
                    // 说明文字默认不显示（各页不再附解释），只保留标记为 keep 的状态提示
                    visible: !(blk.modelData.t === "note" && !blk.modelData.keep)
                    transform: Translate { id: blkShift; y: 14 }
                    Component.onCompleted: enter.start()
                    SequentialAnimation {
                        id: enter
                        PauseAnimation { duration: 40 + blk.index * 60 }
                        ParallelAnimation {
                            NumberAnimation { target: blk; property: "opacity"; to: 1; duration: 300 }
                            NumberAnimation { target: blkShift; property: "y"; to: 0; duration: 420; easing.type: Easing.OutCubic }
                        }
                    }
                    BlockHead { visible: !!blk.modelData.title; title: blk.modelData.title || "" }
                    Loader {
                        width: parent.width
                        sourceComponent: blk.modelData.t === "kv" ? kvC : blk.modelData.t === "table" ? tableC
                            : blk.modelData.t === "stats" ? statsC : blk.modelData.t === "note" ? noteC
                            : blk.modelData.t === "log" ? logC : blk.modelData.t === "banner" ? bannerC
                            : blk.modelData.t === "list" ? listC : runC
                        Component { id: kvC; KvBlock { b: blk.modelData } }
                        Component { id: tableC; TableBlock { b: blk.modelData } }
                        Component { id: statsC; StatsBlock { b: blk.modelData } }
                        Component { id: noteC; NoteBlock { b: blk.modelData } }
                        Component { id: logC; LogBlock { b: blk.modelData } }
                        Component { id: bannerC; BannerBlock { b: blk.modelData } }
                        Component { id: listC; ListBlock { b: blk.modelData } }
                        Component { id: runC; RunBlock { b: blk.modelData } }
                    }
                }
            }
        }

        // 操作
        Item {
            opacity: panel.tabFade
            anchors.bottom: parent.bottom
            width: parent.width
            height: 56
            Rectangle { width: parent.width; height: 1; color: Theme.hair }
            Row {
                anchors.bottom: parent.bottom
                spacing: 10
                Repeater {
                    model: panel.shown ? panel.shown.actions : []
                    Btn {
                        required property string modelData
                        required property int index
                        text: modelData
                        primary: index === 0
                        danger: /删除|停止|注销|卸下/.test(modelData)
                        enabled: !(panel.saving && modelData === "保存")
                        onClicked: panel.act(modelData)
                    }
                }
            }
        }
    }

    readonly property real bodyBottom: body.y + body.implicitHeight

    // ── 解密层：对角线合拢 → 保持（等待数据）→ 收束；磨砂自上而下退去 ──
    Item {
        id: decLayer
        anchors.fill: parent
        visible: panel.dec < 1
        z: 20
        function ease(t) { t = Math.max(0, Math.min(1, t)); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2 }
        readonly property real clearP: panel.dec < 0.45 ? 0 : ease((panel.dec - 0.45) / 0.55)

        ShaderEffectSource {
            id: contentSrc
            sourceItem: content
            live: decLayer.visible
            hideSource: false
            visible: false
            width: content.width
            height: content.height
        }
        Item {
            id: frostComp
            anchors.fill: parent
            visible: false
            layer.enabled: decLayer.visible
            Rectangle { anchors.fill: parent; color: Theme.paper; opacity: 0.95 }
            MultiEffect { anchors.fill: parent; source: contentSrc; blurEnabled: true; blur: 0.8; blurMax: 32; opacity: 0.8 }
        }
        Item {
            id: maskItem
            anchors.fill: parent
            visible: false
            layer.enabled: decLayer.visible
            Rectangle {
                width: parent.width
                height: parent.height * 2.24
                y: decLayer.clearP * parent.height * 1.24 - parent.height * 0.24
                gradient: Gradient {
                    GradientStop { position: 0; color: "transparent" }
                    GradientStop { position: 0.107; color: "black" }
                    GradientStop { position: 1; color: "black" }
                }
            }
        }
        MultiEffect {
            anchors.fill: parent
            source: frostComp
            maskEnabled: true
            maskSource: maskItem
            maskThresholdMin: 0
            maskSpreadAtMin: 1
        }

        Item {
            id: diag
            anchors.centerIn: parent
            width: Math.hypot(parent.width, parent.height)
            height: 3
            rotation: Math.atan2(parent.height, parent.width) * 180 / Math.PI
            readonly property real half: width / 2
            readonly property real g: decLayer.ease(panel.dec / 0.32)
            readonly property real s: decLayer.ease((panel.dec - 0.55) / 0.25)
            opacity: panel.dec < 0.78 ? 1 : Math.max(0, 1 - (panel.dec - 0.78) / 0.22)
            Rectangle { x: diag.half * diag.s; width: Math.max(0, diag.half * (diag.g - diag.s)); height: 3; color: Theme.ink }
            Rectangle { x: diag.width - diag.half * diag.g; width: Math.max(0, diag.half * (diag.g - diag.s)); height: 3; color: Theme.ink }
        }
    }
}
