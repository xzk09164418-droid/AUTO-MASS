import QtQuick
import "."

// 左下录像带串（PV 1:19 的卡带堆）。不依赖 Qt Quick 3D：每盒卡带是普通 Item，
// 用 4×4 透视矩阵投影到画面上（与演示里 three.js 的相机参数一致：fov 30°、相机 z=12.4）。
// 串从左上斜向右下、越往下越靠近镜头；选中项放大 20%、向画面中心抽出、80% 不透明，前后卡带让开。
// 只在滑动 / 入场时逐帧更新，静止后不再重绘。
Item {
    id: chain

    property var items: []
    property string deptN: ""
    property int target: 0
    property real cur: -8
    property real intro: 0
    property real introTarget: 0
    property int hovered: -1
    onHoveredChanged: poke()
    onTargetChanged: { poke(); pull(target) }

    // 借鉴 RhineLabUI：停止操作 2.5 秒后渐入呼吸起伏（8 秒与 13 秒周期叠加，相邻错相）
    property real breath: 0
    property real breathGoal: 0
    property real clockT: 0
    // 呼吸用 15Hz 计时器推进：不占用逐帧动画，只在数值变化时重绘（呼吸缓慢、幅度小，15Hz 看不出台阶）
    Timer {
        interval: 66
        repeat: true
        running: chain.visible && (chain.breath > 0 || chain.breathGoal > 0)
        onTriggered: {
            chain.breath += (chain.breathGoal - chain.breath) * 0.06
            if (Math.abs(chain.breathGoal - chain.breath) < 0.002) chain.breath = chain.breathGoal
            chain.clockT += 0.066
        }
    }
    function poke() { breathGoal = 0; idleTimer.restart() }
    Timer {
        id: idleTimer
        interval: 2500
        running: chain.visible && chain.introTarget === 1 && Theme.richMotion
        onTriggered: chain.breathGoal = 1
    }

    // 档案抽出：选中的卡带先抬起、向镜头靠近并转正，再随串归位
    property int pullK: -1
    property real pullP: 0
    function pull(k) {
        if (!Theme.richMotion || introTarget !== 1) return
        pullK = k
        pullAnim.restart()
    }
    SequentialAnimation {
        id: pullAnim
        NumberAnimation { target: chain; property: "pullP"; from: 0; to: 1; duration: 280; easing.type: Easing.OutCubic }
        PauseAnimation { duration: 140 }
        NumberAnimation { target: chain; property: "pullP"; to: 0; duration: 560; easing.type: Easing.InOutCubic }
    }
    // 在曲线位置上叠加呼吸、悬停抬起与抽出
    function placeAt(s, k, lift) {
        const p = place(s)
        if (breath > 0)
            p.y += breath * 0.06 * (0.6 * Math.sin(clockT * Math.PI / 4 + k * 0.7) + 0.4 * Math.sin(clockT * Math.PI / 6.5 + k * 1.3))
        p.y += lift * 0.22
        if (k === pullK && pullP > 0) {
            p.y += 0.5 * pullP
            p.z += 0.8 * pullP
            p.ry *= 1 - pullP
            p.rx *= 1 - 0.6 * pullP
        }
        return p
    }
    signal picked(int k)

    readonly property int pad: 3
    readonly property real focal: (height / 2) / Math.tan(15 * Math.PI / 180)
    readonly property real camZ: 12.4
    readonly property int cw: 260           // 卡带设计尺寸（像素），对应 2.6 × 1.7 单位
    readonly property int ch: 170

    function open(list, n) {
        deptN = n
        items = list
        target = 0
        cur = -8
        intro = 0
        introTarget = 1
    }
    function close() { introTarget = 0; breathGoal = 0; idleTimer.stop() }

    // 曲线：s 为相对选中位置的槽位
    function place(s) {
        const f = Math.max(0, 1 - Math.abs(s))
        const e = f * f * (3 - 2 * f)
        const t = s + Math.sign(s) * Math.min(1, Math.abs(s)) * 0.95
        return { x: -1.2 + 0.74 * t + 1.1 * e, y: -0.7 - 0.66 * t + 0.55 * e, z: 0.3 * t + 0.9 * e,
                 rx: -0.18 + 0.1 * e, ry: 0.5 - 0.38 * e, rz: 0.05 - 0.05 * e, sc: 1 + 0.2 * e, focus: e }
    }

    // 局部像素 (u, v) → 画面坐标的投影矩阵；zoff 为卡带内的前后层（单位）。
    // 展开成闭式计算，不产生中间数组（呼吸时每秒更新 15 次，避免周期性垃圾回收的卡顿）。
    function matrix(p, zoff) {
        const cxr = Math.cos(p.rx), sxr = Math.sin(p.rx), cyr = Math.cos(p.ry), syr = Math.sin(p.ry), czr = Math.cos(p.rz), szr = Math.sin(p.rz)
        // R = Rx · Ry · Rz
        const r00 = cyr * czr, r01 = -cyr * szr, r02 = syr
        const r10 = cxr * szr + sxr * syr * czr, r11 = cxr * czr - sxr * syr * szr, r12 = -sxr * cyr
        const r20 = sxr * szr - cxr * syr * czr, r21 = sxr * czr + cxr * syr * szr, r22 = cxr * cyr
        const ku = p.sc * 2.6 / cw, kv = -p.sc * 1.7 / ch
        // u、v 方向列向量与原点（相机坐标）
        const ax = r00 * ku, ay = r10 * ku, az = r20 * ku
        const bx = r01 * kv, by = r11 * kv, bz = r21 * kv
        const ox = p.sc * (-1.3 * r00 + 0.85 * r01 + zoff * r02) + p.x
        const oy = p.sc * (-1.3 * r10 + 0.85 * r11 + zoff * r12) + p.y
        const oz = p.sc * (-1.3 * r20 + 0.85 * r21 + zoff * r22) + p.z - camZ
        const f = focal, hx = width / 2, hy = height / 2
        return Qt.matrix4x4(f * ax - hx * az, f * bx - hx * bz, 0, f * ox - hx * oz,
                            -f * ay - hy * az, -f * by - hy * bz, 0, -f * oy - hy * oz,
                            0, 0, 0, 0,
                            -az, -bz, 0, -oz)
    }

    readonly property bool moving: Math.abs(target - cur) > 0 || Math.abs(introTarget - intro) > 0
    FrameAnimation {
        running: chain.visible && chain.moving
        onTriggered: {
            const dt = Math.min(0.05, frameTime)
            chain.cur += (chain.target - chain.cur) * (1 - Math.pow(0.0008, dt))
            chain.intro += (chain.introTarget - chain.intro) * (1 - Math.pow(0.004, dt))
            if (Math.abs(chain.target - chain.cur) < 0.0005) chain.cur = chain.target
            if (Math.abs(chain.introTarget - chain.intro) < 0.002) chain.intro = chain.introTarget
        }
    }

    Repeater {
        model: chain.items.length + chain.pad * 2
        Item {
            id: cas
            required property int index
            readonly property int k: index - chain.pad
            readonly property bool real: k >= 0 && k < chain.items.length
            readonly property real s: k - chain.cur + 9 * (1 - chain.intro)
            property real lift: hot ? 1 : 0
            Behavior on lift { enabled: Theme.richMotion; NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
            readonly property var p: chain.placeAt(s, k, lift)
            readonly property real fade: Math.max(0, Math.min(1, 1.8 - Math.abs(s) / 4.2)) * Math.min(1, chain.intro * 1.4)
            readonly property bool hot: real && chain.hovered === k
            visible: fade > 0.01
            z: 100 + s * 4

            // 背板：表现卡带厚度
            Rectangle {
                width: chain.cw
                height: chain.ch
                radius: 7
                color: Theme.dark ? "#2b363b" : "#c9c5bd"
                opacity: (0.35 + 0.35 * cas.p.focus) * cas.fade
                transform: Matrix4x4 { matrix: cas.visible ? chain.matrix(cas.p, -0.13) : Qt.matrix4x4() }
            }
            // 正面：磨砂外壳 + 内窗 + 标志 + 编号与名称
            Item {
                width: chain.cw
                height: chain.ch
                transform: Matrix4x4 { matrix: cas.visible ? chain.matrix(cas.p, 0.13) : Qt.matrix4x4() }

                Rectangle {
                    anchors.fill: parent
                    radius: 7
                    color: Theme.dark ? "#3a474c" : "#f3f1ec"
                    border.width: 1.5
                    border.color: cas.hot ? Theme.accent : Theme.dark ? "#6d7b80" : "#9e9a90"
                    opacity: Math.min(0.8, 0.32 + 0.48 * cas.p.focus + (cas.hot ? 0.12 : 0)) * cas.fade
                }
                Item {
                    anchors.fill: parent
                    opacity: (cas.real ? 0.75 + 0.25 * cas.p.focus : 0.5) * cas.fade
                    Rectangle {
                        x: 7; y: 7
                        width: parent.width - 14; height: parent.height - 14
                        color: Qt.rgba(1, 1, 1, Theme.dark ? 0.08 : 0.35)
                        border.width: 1
                        border.color: Qt.rgba(0.16, 0.16, 0.14, 0.28)
                    }
                    Repeater {
                        model: [Qt.point(15, 15), Qt.point(245, 15), Qt.point(15, 155), Qt.point(245, 155)]
                        Rectangle { required property point modelData; x: modelData.x - 2.5; y: modelData.y - 2.5; width: 5; height: 5; radius: 2.5; color: Qt.rgba(0.16, 0.16, 0.14, 0.5) }
                    }
                    Emblem {
                        x: 34; y: 44
                        width: 72; height: 72
                        ink: Theme.dark ? "#e0e3dc" : "#ffffff"
                        core: Theme.accent
                        lineWidth: 3.2
                        curve: false
                        Rectangle { anchors.fill: parent; anchors.margins: -10; z: -1; color: Theme.dark ? "#11181b" : "#2a2b2a"; opacity: 0.85 }
                    }
                    Column {
                        visible: cas.real
                        x: 134; y: 48
                        spacing: 6
                        Text { text: chain.deptN + "-" + String(cas.k + 1).padStart(2, "0"); color: Theme.ink; opacity: 0.85; font.family: Theme.font; font.pixelSize: 15; font.weight: Font.Bold }
                        Text {
                            width: 116
                            elide: Text.ElideRight
                            text: cas.real ? chain.items[cas.k].name : ""
                            color: Theme.ink
                            font.family: Theme.font
                            font.pixelSize: 19
                            font.weight: Font.Bold
                        }
                        Rectangle { width: 96; height: 2; color: Theme.ink; opacity: 0.45 }
                    }
                    Column {
                        visible: !cas.real
                        x: 134; y: 68
                        spacing: 10
                        Rectangle { width: 86; height: 6; color: Theme.ink; opacity: 0.25 }
                        Rectangle { width: 60; height: 4; color: Theme.ink; opacity: 0.25 }
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: cas.real && cas.fade > 0.3
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onContainsMouseChanged: chain.hovered = containsMouse ? cas.k : (chain.hovered === cas.k ? -1 : chain.hovered)
                    onClicked: chain.picked(cas.k)
                }
            }
        }
    }
}
