import QtQuick
import QtQuick.Effects
import "."

// 动态效果挡位切换过渡（标准 ↔ 增强）：
// 1. 定格当前画面（ShaderEffectSource 抓一帧），定格逐渐模糊并压上挡位铭牌；
// 2. 定格挡住画面时切换挡位，等新画面就绪（增强挡位要等 3D 阵列加载完）；
// 3. 一道斜线自左向右扫过，线后露出新画面，定格随之退去。
// 减少挡位、或不在二级界面时直接切换，不播放过渡。
Item {
    id: shift
    required property Item sceneItem
    required property var sectionView
    property string next: ""
    property string queued: ""
    property int phase: 0          // 0 空闲 · 1 抓帧 · 2 遮挡 / 等待 · 3 揭开
    property real veil: 0          // 定格的模糊与铭牌
    property real wipe: 0          // 斜线位置 0 → 1
    property int waited: 0
    readonly property bool toEnhanced: next === "enhanced"
    visible: phase > 0

    function run(m) {
        if (m === Theme.motion) return
        if (phase > 0) { queued = m; return }
        const visibleChange = sectionView.opened && (m === "enhanced" || Theme.motion === "enhanced") && m !== "reduced"
        if (!visibleChange) { Theme.motion = m; return }
        next = m; queued = ""
        veil = 0; wipe = 0; waited = 0
        phase = 1
        freeze.scheduleUpdate()
    }
    function finish() {
        phase = 0; veil = 0; wipe = 0
        if (queued && queued !== Theme.motion) { const m = queued; queued = ""; run(m) }
    }

    ShaderEffectSource {
        id: freeze
        sourceItem: shift.sceneItem
        live: false
        hideSource: false
        visible: false
        width: shift.width; height: shift.height
        onScheduledUpdateCompleted: if (shift.phase === 1) { shift.phase = 2; coverAnim.restart() }
    }

    SequentialAnimation {
        id: coverAnim
        NumberAnimation { target: shift; property: "veil"; from: 0; to: 1; duration: 320; easing.type: Easing.OutCubic }
        ScriptAction { script: { Theme.motion = shift.next; waitReady.restart() } }
    }
    // 增强：等阵列加载并飞入一段；标准：等录像带串展开。最长 10 秒后无条件揭开
    Timer {
        id: waitReady
        interval: 60; repeat: true
        onTriggered: {
            shift.waited += interval
            const ready = shift.toEnhanced ? !!shift.sectionView.arrayItem : true
            if ((ready && shift.waited >= (shift.toEnhanced ? 520 : 300)) || shift.waited > 10000) {
                stop(); shift.phase = 3; revealAnim.restart()
            }
        }
    }
    SequentialAnimation {
        id: revealAnim
        // 揭开时定格的模糊、色罩与整体不透明度同步退去，新旧画面在羽化带里逐渐过渡，不出现明暗跳变
        ParallelAnimation {
            NumberAnimation { target: shift; property: "wipe"; from: 0; to: 1; duration: 1200; easing.type: Easing.InOutSine }
            NumberAnimation { target: shift; property: "veil"; from: 1; to: 0; duration: 1200; easing.type: Easing.InOutSine }
        }
        ScriptAction { script: shift.finish() }
    }

    // 定格层：模糊 + 纸色薄罩，按斜线遮罩只保留线右侧
    Item {
        id: frozen
        anchors.fill: parent
        visible: false
        layer.enabled: shift.phase > 0
        MultiEffect {
            anchors.fill: parent
            source: freeze
            blurEnabled: true
            blur: 0.55 * shift.veil
            blurMax: 40
            autoPaddingEnabled: false
        }
        Rectangle { anchors.fill: parent; color: Theme.bg; opacity: 0.38 * shift.veil }
    }
    // 羽化带宽度：斜线后方这一段由透明渐到不透明，新画面逐渐透出
    readonly property real feather: 560
    readonly property real edge: -0.2 * width - feather + wipe * (1.4 * width + feather)     // 羽化带起点（斜线中点）的横坐标
    Item {
        id: wipeMask
        anchors.fill: parent
        visible: false
        layer.enabled: shift.phase > 0
        Rectangle {
            x: shift.edge; y: -shift.height
            width: shift.width * 3; height: shift.height * 3
            rotation: 14; transformOrigin: Item.Left
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: "transparent" }
                GradientStop { position: shift.feather / (shift.width * 3); color: "black" }
                GradientStop { position: 1; color: "black" }
            }
        }
    }
    MultiEffect {
        anchors.fill: parent
        source: frozen
        opacity: 1 - shift.wipe * shift.wipe
        maskEnabled: true
        maskSource: wipeMask
        maskThresholdMin: 0
        maskSpreadAtMin: 1
    }
    // 扫描线：墨色主线 + 橙色细线 + 斜纹带
    Item {
        visible: shift.phase === 3
        x: shift.edge + shift.feather * 0.5; y: shift.height / 2
        rotation: 14
        opacity: 0.75 * Math.sin(Math.PI * Math.min(1, shift.wipe * 1.15))
        Rectangle { x: -2; y: -shift.height * 1.5; width: 4; height: shift.height * 3; color: Theme.ink }
        Rectangle { x: -16; y: -shift.height * 1.5; width: 2; height: shift.height * 3; color: Theme.accent }
        Item {
            x: 6; y: -shift.height * 1.5; width: 18; height: shift.height * 3; clip: true
            Repeater {
                model: 140
                Rectangle { required property int index; x: 0; y: index * 24; width: 28; height: 6; rotation: -35; color: Theme.ink; opacity: 0.8 }
            }
        }
    }

    // 挡位铭牌：遮挡阶段出现，揭开开始后淡出
    Item {
        anchors.centerIn: parent
        width: 620; height: 220
        opacity: shift.veil * Math.max(0, 1 - shift.wipe * 4)
        Rectangle { anchors.fill: parent; color: Theme.paper; border.width: 1.5; border.color: Theme.ink }
        Rectangle { width: parent.width; height: 4; color: Theme.accent }
        Repeater {
            model: 4
            Item {
                required property int index
                readonly property bool isRight: index % 2 === 1
                readonly property bool isBottom: index > 1
                x: isRight ? 620 - 22 : 8; y: isBottom ? 220 - 22 : 12
                width: 14; height: 14
                Rectangle { x: parent.isRight ? 12 : 0; width: 2; height: 14; color: Theme.ink }
                Rectangle { y: parent.isBottom ? 12 : 0; width: 14; height: 2; color: Theme.ink }
            }
        }
        Text { x: 40; y: 34; text: "MOTION PROFILE  /  " + shift.next.toUpperCase(); color: Theme.accent; font.family: Theme.font; font.pixelSize: 13; font.weight: Font.Bold; font.letterSpacing: 3 }
        Text { x: 40; y: 62; text: shift.toEnhanced ? "增强" : "标准"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 56; font.weight: Font.Bold; font.letterSpacing: 6 }
        Text {
            x: 40; y: 150
            text: shift.toEnhanced ? (shift.sectionView.arrayItem ? "3D ARCHIVE  READY" : "LOADING  3D  ARCHIVE") : "CASSETTE  CHAIN  READY"
            color: Theme.muted; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Bold; font.letterSpacing: 2.6
        }
        // 等待进度：斜纹带滚动
        Item {
            x: 40; y: 176; width: 540; height: 10; clip: true
            Rectangle { anchors.fill: parent; color: "transparent"; border.width: 1; border.color: Theme.hair }
            Repeater {
                model: 70
                Rectangle {
                    required property int index
                    x: index * 9 - 18 + hatchShift.offset; y: -6; width: 3; height: 22; rotation: 35
                    color: Theme.ink; opacity: 0.8
                }
            }
            QtObject { id: hatchShift; property real offset: 0 }
            NumberAnimation { target: hatchShift; property: "offset"; from: 0; to: 18; duration: 420; loops: Animation.Infinite; running: shift.phase === 2 && Theme.richMotion }
        }
    }
    // 过渡期间挡住输入
    MouseArea { anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.AllButtons; onWheel: wheel => wheel.accepted = true }
}
