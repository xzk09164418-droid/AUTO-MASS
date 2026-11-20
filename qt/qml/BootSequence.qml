import QtQuick
import QtQuick.Effects
import "."
import "Tracks.js" as T

// 启动动画：复刻 PV 0–27 秒的段落结构，标志与文字替换为 AUTO-MAS。
// 一切画面状态都是帧号 frame（25fps）的纯函数，便于逐帧校准、跳帧与重播；不依赖视频文件。
//   0–38    黑场标志（替代原片片头）
//   41–82   接入输入
//   82–182  标志绘制 → 左移 → 品牌三行 → 收至左上角
//   190–285 身份确认
//   285–375 授权圆环（后端未就绪时停在 362 帧等待，圆环缓慢转动）
//   381–425 欢迎
//   420–452 原背景色由中心铺满 → 交给部门索引
// 时钟由 FrameAnimation 驱动，每帧随垂直同步推进；底部进度条与后端启动阶段同步。
Item {
    id: boot

    signal finished()

    property bool running: false
    property real frame: 0
    readonly property real fps: 25
    readonly property int endFrame: 452

    readonly property color field: Theme.bootField
    readonly property color ink: Theme.bootInk

    // 后端启动同步：未就绪时动画停在授权段等待
    property bool backendReady: true
    property real backendProgress: 1
    property string backendStage: ""
    readonly property int holdFrame: 362
    property real idle: 0
    property bool done: false

    // 长时间加载：停帧超过 1 秒后显出启动日志、耗时与提示；圆环转入呼吸
    property var stageLog: []
    onBackendStageChanged: {
        if (backendStage && stageLog[stageLog.length - 1] !== backendStage)
            stageLog = stageLog.concat([backendStage]).slice(-9)
    }
    readonly property bool waiting: !backendReady && frame >= holdFrame - 0.001
    property real waitShow: waiting && idle > 1.0 ? 1 : 0
    Behavior on waitShow { NumberAnimation { duration: 360; easing.type: Easing.OutCubic } }
    function clockText(sec) {
        const m = Math.floor(sec / 60), s = Math.floor(sec % 60)
        return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s
    }

    // 后端到 100% 即以最短方式收尾：不再等动画走完，原背景色由中心铺满后直接进入主页
    property bool quickExitOnReady: false
    property bool exiting: false
    property real exitP: 0
    function quickExit() {
        if (exiting || done) return
        exiting = true
        exitAnim.start()
    }
    onBackendReadyChanged: if (backendReady && quickExitOnReady && running) quickExit()
    NumberAnimation {
        id: exitAnim
        target: boot
        property: "exitP"
        from: 0
        to: 1
        duration: 380
        easing.type: Easing.InOutCubic
        onFinished: {
            boot.done = true
            boot.finished()
        }
    }

    function skip() {
        done = true
        frame = endFrame
        finished()
    }

    function replay() {
        frame = 0
        idle = 0
        done = false
        exiting = false
        exitP = 0
        stageLog = backendStage ? [backendStage] : []
    }

    FrameAnimation {
        id: clock
        running: boot.running && !boot.done && !boot.exiting
        onTriggered: {
            const step = Math.min(frameTime, 0.1) * boot.fps
            if (!boot.backendReady && boot.frame >= boot.holdFrame - 0.001) {
                boot.frame = boot.holdFrame
                boot.idle += frameTime
                return
            }
            let next = boot.frame + step
            if (!boot.backendReady) next = Math.min(next, boot.holdFrame)
            if (next >= boot.endFrame) {
                boot.frame = boot.endFrame
                boot.done = true
                boot.finished()
                return
            }
            boot.frame = next
        }
    }

    component BootText: Text {
        color: boot.ink
        font.family: Theme.font
        font.bold: true
        font.pixelSize: 22
        font.letterSpacing: 7
    }

    Item {
        id: content
        anchors.fill: parent
        layer.enabled: boot.frame > 420
        layer.effect: MultiEffect {
            blurEnabled: true
            blurMax: 24
            blur: 0.6 * T.ramp(boot.frame, 420, 446)
        }

        Rectangle {
            anchors.fill: parent
            color: boot.field
        }

        // ── 接入输入 ──────────────────────────────────────────────────────
        BootText {
            readonly property string full: "ACCESSING  AUTO-MAS  TERMINAL"
            anchors.horizontalCenter: parent.horizontalCenter
            y: 520
            visible: boot.frame >= 41 && boot.frame < 82
            text: T.typed(full, boot.frame, 41, 1) + (Math.floor(boot.frame / 6) % 2 === 0 ? " ▌" : "  ")
        }

        // ── 标志绘制与品牌 ────────────────────────────────────────────────
        Mark {
            width: 200
            height: 200
            x: 860 - 250 * T.easeOut(T.ramp(boot.frame, 130, 152))
            y: 440
            ink: boot.ink
            core: Theme.accent
            lineWidth: 2.6
            visible: boot.frame >= 82
            opacity: 1 - T.ramp(boot.frame, 160, 168)
            progress: T.easeInOut(T.ramp(boot.frame, 82, 115))
            tickOpacity: T.ramp(boot.frame, 108, 112)
            coreScale: T.track([[112, 0], [117, 1.18], [121, 1]], boot.frame)
        }

        Item {
            id: brand
            readonly property real move: T.easeInOut(T.ramp(boot.frame, 160, 182))
            x: 870 + (59 - 870) * move
            y: 470 + (64 - 470) * move
            scale: 1 - 0.1 * move
            transformOrigin: Item.TopLeft
            visible: boot.frame >= 136

            Column {
                Repeater {
                    model: [
                        { text: "AUTO-MAS", size: 46, spacing: 2.5, weight: Font.Bold },
                        { text: "SCRIPT CUSTODY INFORMATION", size: 15, spacing: 1.6, weight: Font.DemiBold },
                        { text: "ANALYSIS OS", size: 35, spacing: 6, weight: Font.Bold }
                    ]
                    delegate: Text {
                        required property var modelData
                        required property int index
                        readonly property real enter: T.ramp(boot.frame, 136 + index * 2, 154 + index * 2)
                        text: modelData.text
                        color: boot.ink
                        font.family: Theme.font
                        font.pixelSize: modelData.size
                        font.letterSpacing: modelData.spacing
                        font.weight: modelData.weight
                        opacity: T.ramp(boot.frame, 136 + index * 2, 139 + index * 2)
                        transform: Translate { x: 120 * (1 - T.easeOut(enter)) }
                    }
                }
            }
        }

        // ── 身份确认 ──────────────────────────────────────────────────────
        Column {
            anchors.horizontalCenter: parent.horizontalCenter
            y: 470
            spacing: 22
            visible: boot.frame >= 190 && boot.frame < 285

            BootText {
                anchors.horizontalCenter: parent.horizontalCenter
                text: T.typed("ID CONFIRMED : OPERATOR", boot.frame, 190, 1)
            }
            BootText {
                anchors.horizontalCenter: parent.horizontalCenter
                text: T.typed("REQUEST RECEIVED", boot.frame, 223, 1)
            }
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 12
                Ring {
                    anchors.verticalCenter: parent.verticalCenter
                    radius: 8
                    stroke: 3
                    sweep: 270
                    color: boot.ink
                    visible: boot.frame >= 262
                    rotation: (boot.frame - 262) * 24
                }
                BootText {
                    text: T.typed("START PROCESSING...", boot.frame, 249, 1)
                }
            }
        }

        // ── 授权圆环 ──────────────────────────────────────────────────────
        Item {
            id: auth
            anchors.fill: parent
            visible: boot.frame >= 285 && boot.frame < 375

            Item {
                id: jumpGroup
                x: 960
                y: 540
                scale: T.steps(boot.frame, 320, 3, [1.08, 0.94, 1.05, 0.98, 1])
                    * (1 + 0.014 * Math.sin(boot.idle * 2.4) * boot.waitShow)

                Ring {
                    x: -width / 2
                    y: -height / 2
                    radius: 220
                    stroke: 30
                    color: boot.ink
                    scale: 3 - 2 * T.easeOut(T.ramp(boot.frame, 285, 312))
                }
                Ring {
                    x: -width / 2
                    y: -height / 2
                    radius: 220
                    stroke: 8
                    color: boot.field
                    scale: 2.4 - 1.4 * T.easeOut(T.ramp(boot.frame, 288, 320))
                    rotation: -200 * T.easeOut(T.ramp(boot.frame, 288, 320))
                }
                Ring {
                    x: -width / 2
                    y: -height / 2
                    radius: 160
                    stroke: 5
                    sweep: 80
                    color: boot.ink
                    rotation: -420 * T.easeOut(T.ramp(boot.frame, 295, 375)) - boot.idle * 40
                }
                // 橙色节点沿外环绕行
                Item {
                    rotation: 540 * T.easeOut(T.ramp(boot.frame, 297, 375)) + boot.idle * 60
                    Rectangle {
                        width: 26
                        height: 26
                        radius: 13
                        x: -13
                        y: -233
                        color: Theme.accent
                    }
                }
            }

            // 中央大点闪变后缩小
            Rectangle {
                readonly property real s: T.steps(boot.frame, 340, 4, [1, 0.4, 1.2, 0.6, 0.42])
                width: 52 * s
                height: width
                radius: width / 2
                x: 960 - width / 2
                y: 540 - height / 2
                color: boot.ink
            }

            // 六颗小点绕中心
            Item {
                x: 960
                y: 540
                visible: boot.frame >= 345
                rotation: 300 * T.ramp(boot.frame, 345, 395) + boot.idle * 90
                Repeater {
                    model: 6
                    Rectangle {
                        required property int index
                        width: 10
                        height: 10
                        radius: 5
                        color: boot.ink
                        visible: boot.frame >= 345 + index * 3
                        x: 35 * Math.cos(index * Math.PI / 3) - 5
                        y: 35 * Math.sin(index * Math.PI / 3) - 5
                    }
                }
            }

            // 两侧小圆：原位反向旋转并补全弧段
            Repeater {
                model: [{ cx: 600, dir: 1, end: 332 }, { cx: 1320, dir: -1, end: 339 }]
                Ring {
                    required property var modelData
                    readonly property real p: T.easeOut(T.ramp(boot.frame, 325, 370))
                    x: modelData.cx - width / 2
                    y: 540 - height / 2
                    radius: 56
                    stroke: 6
                    color: boot.ink
                    sweep: 330 * p
                    rotation: modelData.dir * modelData.end * p
                    visible: boot.frame >= 325
                }
            }

            // 等待面板：右侧启动日志（已完成 / 进行中），左侧耗时
            Item {
                id: waitPanel
                anchors.fill: parent
                opacity: boot.waitShow
                visible: opacity > 0.01

                Column {
                    x: 1470
                    y: 360
                    width: 360
                    spacing: 0
                    transform: Translate { x: 30 * (1 - boot.waitShow) }

                    Row {
                        spacing: 10
                        Rectangle { width: 14; height: 3; color: Theme.accent; anchors.verticalCenter: parent.verticalCenter }
                        BootText { text: "BACKEND // STARTUP LOG"; font.pixelSize: 13; font.letterSpacing: 3 }
                    }
                    Rectangle { width: 360; height: 1.5; color: boot.ink; opacity: 0.8 }
                    Item { width: 1; height: 8 }
                    Repeater {
                        model: boot.stageLog
                        Item {
                            required property string modelData
                            required property int index
                            readonly property bool last: index === boot.stageLog.length - 1
                            width: 360
                            height: 30
                            Text {
                                width: 40
                                y: 6
                                text: parent.last ? "" : "OK"
                                color: Theme.success
                                font.family: Theme.font
                                font.pixelSize: 12
                                font.weight: Font.Bold
                                font.letterSpacing: 1.5
                            }
                            Ring {
                                visible: parent.last
                                x: 4
                                y: 7
                                radius: 7
                                stroke: 2.5
                                sweep: 270
                                color: Theme.accent
                                rotation: boot.idle * 400
                            }
                            Text {
                                x: 44
                                y: 4
                                width: 316
                                elide: Text.ElideRight
                                text: parent.modelData
                                color: boot.ink
                                opacity: parent.last ? 1 : 0.55
                                font.family: Theme.font
                                font.pixelSize: 15
                                font.weight: parent.last ? Font.Bold : Font.Normal
                                font.letterSpacing: 1
                            }
                            Rectangle { y: 29; width: 360; height: 1; color: boot.ink; opacity: 0.12 }
                        }
                    }
                }

                Column {
                    x: 150
                    y: 420
                    spacing: 6
                    transform: Translate { x: -30 * (1 - boot.waitShow) }
                    BootText { text: "ELAPSED"; font.pixelSize: 13; font.letterSpacing: 4; opacity: 0.6 }
                    BootText {
                        text: boot.clockText(boot.holdFrame / boot.fps + boot.idle)
                        font.pixelSize: 64
                        font.weight: Font.Light
                        font.bold: false
                        font.letterSpacing: 3
                    }
                    Rectangle { width: 220; height: 2; color: boot.ink }
                    BootText {
                        text: Math.round(boot.shownProgress * 100) + "% · " + (boot.stageLog.length) + " STAGES"
                        font.pixelSize: 13
                        font.letterSpacing: 2.5
                        opacity: 0.6
                    }
                }

                BootText {
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: 890
                    font.pixelSize: 14
                    font.letterSpacing: 3
                    opacity: Math.max(0, Math.min(1, (boot.idle - 12) / 1)) * 0.65
                    text: "后端启动较慢 · 点击任意处可先进入界面，就绪后自动连接"
                }
            }

            BootText {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 840
                font.pixelSize: 18
                font.letterSpacing: 7
                visible: boot.frame >= 357
                opacity: boot.backendReady ? 1 : 0.35
                text: boot.backendReady ? "AUTHORIZATION GRANTED" : "AUTHORIZING ..."
            }
        }

        // ── 欢迎 ─────────────────────────────────────────────────────────
        Column {
            anchors.horizontalCenter: parent.horizontalCenter
            y: 380
            spacing: 14
            visible: boot.frame >= 381

            BootText {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "WELCOME TO"
                font.pixelSize: 64
                font.letterSpacing: 9
            }
            Item {
                anchors.horizontalCenter: parent.horizontalCenter
                width: nameText.implicitWidth + 80
                height: nameText.implicitHeight
                // 黑底横向扫过，名称以场地色显现于黑底之上
                Rectangle {
                    height: parent.height
                    width: parent.width * T.track([[385, 0], [389, 0.72], [397, 0.97], [407, 1]], boot.frame)
                    color: boot.ink
                }
                BootText {
                    id: nameText
                    anchors.centerIn: parent
                    text: "AUTO-MAS"
                    color: boot.field
                    font.pixelSize: 96
                    font.letterSpacing: 11
                }
            }
            BootText {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "INTERNAL DATABASE"
                font.pixelSize: 42
                font.letterSpacing: 12
                visible: T.within(boot.frame, [[398, 401], [404, 407], [410, 9999]])
            }
        }
    }

    // ── 收尾：原背景色由中心铺满（不缩放） ─────────────────────────────────
    Rectangle {
        readonly property real p: Math.max(T.easeInOut(T.ramp(boot.frame, 420, 446)), boot.exitP)
        z: 100
        width: 2300 * p
        height: width
        radius: width / 2
        x: (parent.width - width) / 2
        y: (parent.height - height) / 2
        color: Theme.bg
        visible: p > 0
    }

    // ── 启动进度：与后端启动阶段同步 ─────────────────────────────────────
    Item {
        id: progressStrip
        x: (parent.width - 520) / 2
        y: 968
        width: 520
        height: 40
        opacity: T.ramp(boot.frame, 41, 52) * (1 - T.ramp(boot.frame, 412, 424))
        visible: opacity > 0

        Text {
            text: "BOOT // " + (boot.backendStage || "STANDBY")
            color: boot.ink
            opacity: 0.7
            font.family: Theme.font
            font.pixelSize: 13
            font.weight: Font.DemiBold
            font.letterSpacing: 2.6
        }
        Text {
            anchors.right: parent.right
            text: Math.round(boot.shownProgress * 100) + "%"
            color: boot.ink
            opacity: 0.7
            font.family: Theme.font
            font.pixelSize: 13
            font.weight: Font.DemiBold
            font.letterSpacing: 1.5
        }
        Rectangle {
            y: 26
            width: parent.width
            height: 2
            color: Qt.rgba(boot.ink.r, boot.ink.g, boot.ink.b, 0.15)
            Rectangle {
                width: parent.width * boot.shownProgress
                height: parent.height
                color: Theme.accent
            }
        }
    }

    // 进度条平滑追赶后端的实际进度
    property real shownProgress: 0
    Behavior on shownProgress { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
    onBackendProgressChanged: shownProgress = backendProgress
    Component.onCompleted: {
        shownProgress = backendProgress
        if (backendStage) stageLog = [backendStage]
    }

    // ── 黑场标志 ─────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 1 - T.ramp(boot.frame, 32, 38)
        visible: opacity > 0
        Mark {
            anchors.centerIn: parent
            width: 120
            height: 120
            ink: "#ffffff"
            core: Theme.accent
            opacity: T.ramp(boot.frame, 3, 25)
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: boot.skip()
    }

    Text {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 48
        text: "SKIP ▸"
        opacity: 1 - T.ramp(boot.frame, 418, 428)
        color: Theme.muted
        font.family: Theme.font
        font.pixelSize: 14
        font.letterSpacing: 4
        font.weight: Font.DemiBold
    }
}
