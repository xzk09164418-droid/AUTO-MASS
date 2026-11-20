import QtQuick
import "."

// 部门索引上的随机方块（PV 0–27 秒画面里零散出现的小方块）。
// 不吸附网格：位置与尺寸随机，由避让算法排开部门方块、标签、品牌区、底栏与其他方块；
// 每 2–10 秒出现一个，停留数秒后离场；入场与离场各自从多种动画中随机选取。
// 只在动画进行时重绘，静止停留期间不占用持续帧。
Item {
    id: field

    property bool active: false
    property var avoid: []          // [{x, y, w, h}] 中心点坐标的矩形
    property real px: 0             // 视差位移
    property real py: 0

    readonly property int margin: 48
    readonly property int gap: 26    // 与其他物体保持的最小间距

    transform: Translate { x: field.px; y: field.py }

    function rand(a, b) { return a + Math.random() * (b - a) }

    // 与任一障碍或在场方块相交（含间距）即视为冲突
    function blocked(x, y, w, h, self) {
        if (x < margin || y < margin || x + w > width - margin || y + h > height - 120) return true
        if (x < 440 && y < 240) return true                                   // 左上品牌
        for (const a of avoid) {
            const l = a.x - a.w / 2 - gap, t = a.y - a.h / 2 - gap - 44  // 上方留出标签高度
            const r = a.x + a.w / 2 + gap, b = a.y + a.h / 2 + gap
            if (x + w > l && x < r && y + h > t && y < b) return true
        }
        for (let i = 0; i < pool.count; i++) {
            const o = pool.itemAt(i)
            if (!o || o === self || !o.busy) continue
            if (x + w > o.x - gap && x < o.x + o.width + gap && y + h > o.y - gap && y < o.y + o.height + gap) return true
        }
        return false
    }

    // 拒绝采样：随机取点，冲突则重试；全部失败时本轮跳过
    function findSpot(w, h, self) {
        for (let tries = 0; tries < 60; tries++) {
            const x = Math.round(rand(margin, width - margin - w))
            const y = Math.round(rand(margin, height - 120 - h))
            if (!blocked(x, y, w, h, self)) return Qt.point(x, y)
        }
        return null
    }

    function spawn() {
        for (let i = 0; i < pool.count; i++) {
            const b = pool.itemAt(i)
            if (b && !b.busy) { b.launch(); return }
        }
    }

    Timer {
        id: scheduler
        running: field.active
        repeat: true
        interval: 2600
        onTriggered: {
            field.spawn()
            interval = Math.round(field.rand(2000, 10000))
        }
    }

    Repeater {
        id: pool
        model: 4
        delegate: Item {
            id: blk
            required property int index

            property bool busy: false
            property int kind: 0
            property int mode: 0        // 动画方式：0 淡入 1 缩放 2 横向擦除 3 纵向擦除 4 闪烁 5 滑入
            property int exitMode: 0
            property int dir: 1
            property real p: 0          // 0 隐藏 → 1 完全显现
            visible: busy && p > 0

            function launch() {
                kind = Math.floor(Math.random() * 6)
                const base = kind === 2 ? field.rand(14, 30) : field.rand(36, 120)
                const w = Math.round(kind === 3 ? base * 1.8 : base)
                const h = Math.round(kind === 3 ? base * 0.8 : base)
                const spot = field.findSpot(w, h, blk)
                if (!spot) return
                width = w
                height = h
                x = spot.x
                y = spot.y
                mode = Math.floor(Math.random() * 6)
                exitMode = Math.floor(Math.random() * 6)
                dir = Math.random() < 0.5 ? -1 : 1
                opacity = kind === 2 ? 1 : field.rand(0.55, 0.9)
                enterAnim.duration = mode === 4 ? 420 : Math.round(field.rand(260, 700))
                exitAnim.duration = exitMode === 4 ? 380 : Math.round(field.rand(240, 620))
                hold.duration = Math.round(field.rand(2500, 7000))
                busy = true
                life.restart()
            }

            SequentialAnimation {
                id: life
                NumberAnimation { id: enterAnim; target: blk; property: "p"; from: 0; to: 1; easing.type: Easing.OutCubic }
                PauseAnimation { id: hold }
                ScriptAction { script: { blk.mode = blk.exitMode; blk.dir = -blk.dir } }
                NumberAnimation { id: exitAnim; target: blk; property: "p"; from: 1; to: 0; easing.type: Easing.InCubic }
                ScriptAction { script: blk.busy = false }
            }
            Connections {
                target: field
                function onActiveChanged() {
                    if (!field.active && blk.busy) { life.stop(); blk.p = 0; blk.busy = false }
                }
            }

            // 动画方式到外观的映射
            readonly property real fade: mode === 0 || mode === 5 ? p
                : mode === 4 ? (p >= 0.8 || Math.floor(p * 5) % 2 === 1 ? 1 : 0) : 1
            readonly property real grow: mode === 1 ? p : 1
            readonly property real wipeX: mode === 2 ? p : 1
            readonly property real wipeY: mode === 3 ? p : 1

            Item {
                id: clipBox
                clip: blk.mode === 2 || blk.mode === 3
                width: blk.width * blk.wipeX
                height: blk.height * blk.wipeY
                x: blk.dir < 0 ? blk.width - width : 0
                y: blk.dir < 0 ? blk.height - height : 0
                opacity: blk.fade
                scale: blk.grow
                transform: Translate { y: blk.mode === 5 ? 22 * (1 - blk.p) * blk.dir : 0 }

                Item {
                    width: blk.width
                    height: blk.height
                    x: -clipBox.x
                    y: -clipBox.y

                    // 0 墨色方块
                    Rectangle { anchors.fill: parent; visible: blk.kind === 0; color: Theme.block }
                    // 1 白卡 + 灰色内芯
                    Rectangle {
                        anchors.fill: parent
                        visible: blk.kind === 1
                        color: Theme.paper
                        Rectangle { anchors.centerIn: parent; width: parent.width * 0.38; height: width; color: Theme.decoGrey }
                    }
                    // 2 琥珀小块
                    Rectangle { anchors.fill: parent; visible: blk.kind === 2; color: Theme.accent }
                    // 3 条纹块
                    Rectangle {
                        anchors.fill: parent
                        visible: blk.kind === 3
                        color: Theme.block
                        Rectangle { width: parent.width; height: parent.height * 0.42; anchors.verticalCenter: parent.verticalCenter; color: Theme.paper }
                    }
                    // 4 空框 + 角标
                    Item {
                        anchors.fill: parent
                        visible: blk.kind === 4
                        Rectangle { anchors.fill: parent; color: "transparent"; border.width: 1.5; border.color: Theme.ink; opacity: 0.6 }
                        Rectangle { width: 14; height: 3; color: Theme.ink }
                        Rectangle { width: 3; height: 14; color: Theme.ink }
                        Rectangle { x: parent.width - 14; y: parent.height - 3; width: 14; height: 3; color: Theme.ink }
                        Rectangle { x: parent.width - 3; y: parent.height - 14; width: 3; height: 14; color: Theme.ink }
                    }
                    // 5 十字准星
                    Item {
                        anchors.fill: parent
                        visible: blk.kind === 5
                        Rectangle { x: parent.width / 2 - 1; width: 2; height: parent.height; color: Theme.ink }
                        Rectangle { y: parent.height / 2 - 1; height: 2; width: parent.width; color: Theme.ink }
                    }
                }
            }
        }
    }
}
