import QtQuick
import "."

// 部门索引的随机方块（PV 0–27 秒网格上闪现的小方块）。
// 方块吸附 96px 网格，避开部门方块、品牌区与底栏；按"闪入 → 停留 → 闪出 → 换位"循环。
// 由 Timer 逐步推进，只在状态变化时重绘，空闲时不占用持续帧。
Item {
    id: field

    property bool active: false
    property var avoid: []          // [{x, y, w, h}] 中心点坐标的矩形
    property int count: 10
    property real px: 0             // 视差位移（跟随部门方块的远景层）
    property real py: 0

    readonly property int cell: 96
    readonly property int cols: Math.floor(width / cell)
    readonly property int rows: Math.floor(height / cell)
    property var freeCells: []
    property var taken: ({})

    function computeFree() {
        const out = []
        const pad = 18
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                const x0 = c * cell, y0 = r * cell, x1 = x0 + cell, y1 = y0 + cell
                if (r === 0 || c === 0 || c === cols - 1) continue   // 画面边缘
                if (y1 > height - 110) continue                 // 底栏
                if (x0 < 430 && y0 < 230) continue               // 左上品牌
                let hit = false
                for (const a of avoid) {
                    if (x1 > a.x - a.w / 2 - pad && x0 < a.x + a.w / 2 + pad
                        && y1 > a.y - a.h / 2 - pad - 40 && y0 < a.y + a.h / 2 + pad) { hit = true; break }
                }
                if (!hit) out.push(r * 1000 + c)
            }
        }
        freeCells = out
    }

    function claim(prev) {
        if (prev >= 0) delete taken[prev]
        for (let tries = 0; tries < 12 && freeCells.length; tries++) {
            const k = freeCells[Math.floor(Math.random() * freeCells.length)]
            if (!taken[k]) { taken[k] = true; return k }
        }
        return -1
    }

    onWidthChanged: computeFree()
    onHeightChanged: computeFree()
    onAvoidChanged: computeFree()

    transform: Translate { x: field.px; y: field.py }

    Repeater {
        model: field.count
        delegate: Item {
            id: blk
            required property int index

            property int key: -1
            property int kind: 0
            property var script: []
            property int step: 0
            property bool lit: false

            readonly property var sizes: [[48, 48], [96, 96], [24, 24], [96, 48], [96, 96], [48, 48]]
            x: key < 0 ? 0 : (key % 1000) * field.cell + (kind === 2 ? 36 : kind === 0 || kind === 5 ? 24 : 0)
            y: key < 0 ? 0 : Math.floor(key / 1000) * field.cell + (kind === 2 ? 36 : kind === 0 || kind === 5 ? 24 : kind === 3 ? 24 : 0)
            width: sizes[kind][0]
            height: sizes[kind][1]
            visible: lit && key >= 0

            // 一轮：闪入（亮灭交替）→ 停留 → 闪出 → 隐藏等待；每项为 [亮?, 毫秒]
            function plan() {
                const hold = 1600 + Math.random() * 3400
                const rest = 500 + Math.random() * 3200
                script = [[1, 60], [0, 50], [1, 70], [0, 40], [1, hold], [0, 60], [1, 50], [0, rest]]
                step = 0
            }
            function relocate() {
                key = field.claim(key)
                kind = Math.floor(Math.random() * 6)
                opacity = kind === 2 ? 1 : 0.55 + Math.random() * 0.35
            }
            function advance() {
                if (step >= script.length || key < 0) { relocate(); plan() }
                const s = script[step++]
                lit = s[0] === 1
                ticker.interval = s[1]
                ticker.restart()
            }

            Timer {
                id: ticker
                running: false
                onTriggered: if (field.active) blk.advance()
            }
            Connections {
                target: field
                function onActiveChanged() {
                    if (field.active) {
                        // 错开首轮出现时间，避免同时亮起
                        blk.lit = false
                        blk.step = blk.script.length   // 下一步重新选位
                        ticker.interval = 200 + blk.index * 260 + Math.random() * 600
                        ticker.restart()
                    } else {
                        ticker.stop()
                    }
                }
            }
            Component.onCompleted: { plan(); if (field.active) { ticker.interval = 200 + index * 260; ticker.start() } }

            // 0 墨色小方块
            Rectangle { anchors.fill: parent; visible: blk.kind === 0; color: Theme.block }
            // 1 白卡 + 灰色内芯
            Rectangle {
                anchors.fill: parent
                visible: blk.kind === 1
                color: Theme.paper
                Rectangle { anchors.centerIn: parent; width: 36; height: 36; color: Theme.decoGrey }
            }
            // 2 琥珀小点
            Rectangle { anchors.fill: parent; visible: blk.kind === 2; color: Theme.accent }
            // 3 条纹块
            Rectangle {
                anchors.fill: parent
                visible: blk.kind === 3
                color: Theme.block
                Rectangle { width: parent.width; height: 20; anchors.verticalCenter: parent.verticalCenter; color: Theme.paper }
            }
            // 4 空框 + 角标
            Item {
                anchors.fill: parent
                visible: blk.kind === 4
                Rectangle { anchors.fill: parent; color: "transparent"; border.width: 1.5; border.color: Theme.ink; opacity: 0.6 }
                Rectangle { x: -1; y: -1; width: 14; height: 3; color: Theme.ink }
                Rectangle { x: -1; y: -1; width: 3; height: 14; color: Theme.ink }
                Rectangle { x: parent.width - 13; y: parent.height - 2; width: 14; height: 3; color: Theme.ink }
                Rectangle { x: parent.width - 2; y: parent.height - 13; width: 3; height: 14; color: Theme.ink }
            }
            // 5 十字准星
            Item {
                anchors.fill: parent
                visible: blk.kind === 5
                Rectangle { x: 23; width: 2; height: parent.height; color: Theme.ink }
                Rectangle { y: 23; height: 2; width: parent.width; color: Theme.ink }
            }
        }
    }
}
