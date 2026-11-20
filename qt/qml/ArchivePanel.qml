import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic as C
import "."
import "SectionData.js" as SD

// 右侧档案卡：条目的功能分页 + 数据块 + 操作按钮。
// 交互是二级界面的主体：所有控件都可操作，字段名悬停显示对应的后端配置键。
Item {
    id: panel

    property var dept: null
    property var item: null
    property int itemIndex: 0
    property int tab: 0
    signal toast(string text)

    readonly property var pages: item ? SD.pages(item) : []
    readonly property var page: pages.length ? pages[Math.min(tab, pages.length - 1)] : null

    // 当前显示的页（切换时先淡出旧页再换内容）
    property var shown: null
    property string excl: ""                 // 队列：定时启动与循环队列互斥

    // 快速启动的模拟运行
    property string runState: "idle"
    property real runPct: 0
    property string runTitle: "待命"
    property string runText: "选择任务后开始执行"
    property string queueName: SD.TASKS[0]
    property var statOverride: ({})

    function refresh() {
        if (!page) return
        if (shown === null) { apply(); return }
        swapOut.restart()
    }
    function apply() {
        runTimer.stop()
        runState = "idle"; runPct = 0; runTitle = "待命"; runText = "选择任务后开始执行"; statOverride = ({})
        excl = item && item.exclusive ? item.exclusive : ""
        shown = page
        content.opacity = 1
        content.y = 0
    }
    onPageChanged: refresh()

    SequentialAnimation {
        id: swapOut
        ParallelAnimation {
            NumberAnimation { target: content; property: "opacity"; to: 0; duration: 140 }
            NumberAnimation { target: content; property: "y"; to: -10; duration: 140; easing.type: Easing.InCubic }
        }
        ScriptAction { script: panel.apply() }
    }

    function act(name) {
        const api = shown ? shown.api : ""
        if (name === "开始执行") startRun()
        else if (name === "停止" || name === "停止任务") { runTimer.stop(); runState = "idle"; runPct = 0; runTitle = "已停止"; runText = "队列已手动停止"; toast("队列已停止 · POST /api/dispatch/stop") }
        else if (/删除/.test(name)) toast("演示：删除前会二次确认")
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
        property bool local: spec.v
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
        property int cur: spec.v
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
        implicitWidth: Math.max(140, contentWidthHint + 40)
        property real contentWidthHint: 0
        font.family: Theme.font
        font.pixelSize: 15
        onActivated: if (spec.k === "queue") panel.queueName = currentText
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
                MouseArea { id: chipMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: chip.on = !chip.on }
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
        Component { id: cInp; Field { text: ctl.spec.v; mono: ctl.spec.mono } }
        Component {
            id: cNum
            Row {
                spacing: 8
                Field { width: 76; text: String(ctl.spec.v); horizontalAlignment: Text.AlignRight; validator: IntValidator { bottom: 0; top: 99999 } }
                Text { visible: ctl.spec.unit !== ""; anchors.verticalCenter: parent.verticalCenter; text: ctl.spec.unit; color: Theme.muted; font.family: Theme.font; font.pixelSize: 13 }
            }
        }
        Component { id: cTime; Field { width: ctl.spec.c === "date" ? 150 : 90; text: ctl.spec.v; mono: true; inputMask: ctl.spec.c === "date" ? "9999-99-99" : "99:99" } }
        Component {
            id: cPath
            RowLayout {
                spacing: 10
                Field { Layout.fillWidth: true; text: ctl.spec.v; mono: true }
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
                        text: modelData
                        small: true
                        onClicked: {
                            if (text === "启动" || text === "关闭") {
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
        property var value
        spacing: 10
        Repeater {
            model: Array.isArray(parent.value) ? parent.value : [parent.value]
            Ctl { required property var modelData; spec: modelData }
        }
    }

    // ── 数据块 ──────────────────────────────────────────────────────────
    component KvBlock: Column {
        property var b
        Repeater {
            model: parent.b.rows
            Item {
                id: kvRow
                required property var modelData
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
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.hair; opacity: 0.7 }
            }
        }
        Rectangle { y: 0; width: parent.width; height: 1; color: Theme.hair; opacity: 0.7 }
    }
    component TableBlock: Column {
        id: tb
        property var b
        readonly property real colW: (width - 44) / b.cols.length
        Item {
            width: parent.width
            height: 34
            Row {
                anchors.fill: parent
                Text { width: 44; height: 34; verticalAlignment: Text.AlignVCenter; leftPadding: 6; text: "#"; color: Theme.muted; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Bold; font.letterSpacing: 2 }
                Repeater {
                    model: tb.b.cols
                    Text { required property string modelData; width: tb.colW; height: 34; verticalAlignment: Text.AlignVCenter; leftPadding: 6; text: modelData; color: Theme.muted; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Bold; font.letterSpacing: 2 }
                }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 2; color: Theme.ink }
        }
        Repeater {
            model: tb.b.rows
            Item {
                id: tr
                required property var modelData
                required property int index
                width: tb.width
                height: 44
                Rectangle { anchors.fill: parent; color: Theme.ink; opacity: trHover.hovered ? 0.05 : 0 }
                HoverHandler { id: trHover }
                Row {
                    anchors.fill: parent
                    Text { width: 44; height: parent.height; verticalAlignment: Text.AlignVCenter; leftPadding: 6; text: String(tr.index + 1).padStart(2, "0"); color: Theme.muted; font.family: Theme.font; font.pixelSize: 14 }
                    Repeater {
                        model: tr.modelData
                        Item {
                            required property var modelData
                            width: tb.colW
                            height: tr.height
                            Cell { x: 6; width: parent.width - 12; anchors.verticalCenter: parent.verticalCenter; value: parent.modelData }
                        }
                    }
                }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.hair; opacity: 0.7 }
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
                text: panel.shown ? panel.shown.api || "" : ""
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
                    model: panel.pages.length > 1 ? panel.pages : []
                    Rectangle {
                        id: tabBtn
                        required property var modelData
                        required property int index
                        readonly property bool on: panel.tab === index
                        width: tabRow.implicitWidth + 32
                        height: 38
                        color: on ? Theme.ink : "transparent"
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
                            Text { anchors.baseline: tabName.baseline; text: String(tabBtn.index + 1).padStart(2, "0"); color: tabBtn.on ? Theme.accent : Theme.hair; font.family: Theme.font; font.pixelSize: 10; font.weight: Font.Bold }
                            Text { id: tabName; text: tabBtn.modelData.name; color: tabBtn.on ? Theme.paper : tabMouse.containsMouse ? Theme.ink : Theme.muted; font.family: Theme.font; font.pixelSize: 15; font.weight: Font.DemiBold; font.letterSpacing: 1.2 }
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
            y: tabBar.y + tabBar.height + 16
            width: parent.width
            spacing: 16
            Repeater {
                model: panel.shown ? panel.shown.blocks : []
                Column {
                    id: blk
                    required property var modelData
                    required property int index
                    width: body.width
                    spacing: 8
                    opacity: 0
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
                        onClicked: panel.act(modelData)
                    }
                }
            }
        }
    }

    readonly property real bodyBottom: body.y + body.implicitHeight
}
