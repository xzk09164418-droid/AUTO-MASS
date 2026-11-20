import QtQuick
import "."

// 左下录像带串（PV 1:19 的卡带堆）。不依赖 Qt Quick 3D：每盒卡带是普通 Item，
// 用 4×4 透视矩阵投影到画面上（与演示里 three.js 的相机参数一致：fov 30°、相机 z=12.4）。
// 串从左上斜向右下、越往下越靠近镜头；选中项放大 20%、向画面中心抽出、80% 不透明，前后卡带让开。
// 首尾相接循环：末张之后接第一张、第一张之前接末张；普通切换快速贴靠，越过首尾时带小回弹（类 iOS）。
// 只在滑动 / 入场时更新，静止后不再重绘。
Item {
    id: chain

    property var items: []
    property string deptN: ""
    property int target: 0                  // 选中条目（0..n-1）
    // 串首尾相接：pos 是不取模的绝对槽位，cur 朝它做带小回弹的非线性过渡；
    // 第 m 个槽位显示 items[m mod n]，所以末张之后紧接着就是第一张（反向同理）
    property real pos: 0
    property real cur: -8
    property real intro: 0
    property real introTarget: 0
    property int hovered: -10000            // 悬停的绝对槽位
    readonly property int count: items.length
    function wrap(m) { const n = Math.max(1, count); return ((m % n) + n) % n }
    onHoveredChanged: poke()

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

    // 切到条目 k：d 为方向（+1 向下 / -1 向上），按方向走最近的一圈；点击的槽位直接作为落点。
    // 每次切换排进队列，一步走完（基本到位）再走下一步：
    //   · 普通一步：快速贴靠（指数逼近，不回弹）；
    //   · 越过首尾的一步：只有它是队列里最后一步时，才用非线性减速 + 末尾小回弹（类 iOS），
    //     连续滚动途中越过首尾的那步和普通一步一样，不打断节奏；
    //   · 积压超过 2 步时后面每步走得更快，不丢格、尽快追上。
    property int pickedSlot: -10000
    property var queue: []                  // 待走的绝对槽位
    property real dest: 0                   // 正在走的这一步的落点
    property bool stepping: false
    property bool bouncing: false
    function goTo(k, d) {
        let m
        if (pickedSlot !== -10000 && wrap(pickedSlot) === k) m = pickedSlot
        else {
            const n = Math.max(1, count)
            let delta = ((k - wrap(Math.round(pos))) % n + n) % n
            if (d < 0 && delta > 0) delta -= n
            m = Math.round(pos) + delta
        }
        pickedSlot = -10000
        target = k
        if (m === pos) return
        pos = m
        poke()
        if (intro < 1 && introTarget === 1) { queue = []; stepping = false; bounceAnim.stop(); bouncing = false; dest = m; cur = m; return }   // 入场途中直接对位
        hovered = -10000
        const q = queue.slice(); q.push(m); queue = q
        // 正在回弹时又来了新的一步：回弹那步不再是最后一步，改为普通贴靠接着走
        if (bouncing) { bounceAnim.stop(); bouncing = false }
        if (!stepping) nextStep()
    }
    function nextStep() {
        if (!queue.length) { stepping = false; return }
        const from = dest, m = queue[0]
        queue = queue.slice(1)
        dest = m
        stepping = true
        pull(m)
        const n = Math.max(1, count)
        const crossing = n > 1 && Math.floor(from / n) !== Math.floor(m / n)
        if (crossing && queue.length === 0) {
            bouncing = true
            bounceAnim.stop()
            bounceAnim.from = cur
            bounceAnim.to = m
            bounceAnim.duration = Theme.richMotion ? 560 : 240
            bounceAnim.easing.type = Theme.richMotion ? Easing.OutBack : Easing.OutCubic
            bounceAnim.start()
        }
    }
    NumberAnimation { id: bounceAnim; target: chain; property: "cur"; easing.overshoot: 0.9
        onFinished: if (chain.bouncing) { chain.bouncing = false; chain.cur = chain.dest; chain.nextStep() } }
    FrameAnimation {
        running: chain.visible && chain.stepping && !chain.bouncing
        onTriggered: {
            const dt = Math.min(0.05, frameTime)
            // 每秒剩余比例：普通 0.0008（约 0.35 秒到位，与上一版相同）；积压时更快
            const rate = chain.queue.length >= 2 ? 1e-7 : 0.0008
            chain.cur += (chain.dest - chain.cur) * (1 - Math.pow(rate, dt))
            const near = Math.abs(chain.dest - chain.cur) < (chain.queue.length ? 0.08 : 0.0005)
            if (near) { if (!chain.queue.length) chain.cur = chain.dest; chain.nextStep() }
        }
    }
    // 滑动期间不响应悬停：卡带在指针下移动时不再反复抬起 / 落下，与滚轮动画冲突
    readonly property bool sliding: stepping || Math.abs(cur - pos) > 0.02

    // 档案抽出：选中的卡带先抬起、向镜头靠近并转正，再随串归位
    property int pullK: -10000
    property real pullP: 0
    function pull(m) {
        if (!Theme.richMotion || introTarget !== 1) return
        pullK = m
        pullAnim.restart()
    }
    SequentialAnimation {
        id: pullAnim
        NumberAnimation { target: chain; property: "pullP"; from: 0; to: 1; duration: 280; easing.type: Easing.OutCubic }
        PauseAnimation { duration: 140 }
        NumberAnimation { target: chain; property: "pullP"; to: 0; duration: 560; easing.type: Easing.InOutCubic }
    }
    // 在曲线位置上叠加呼吸、悬停抬起与抽出（m 为绝对槽位）
    function placeAt(s, m, lift) {
        const p = place(s)
        if (breath > 0)
            p.y += breath * 0.06 * (0.6 * Math.sin(clockT * Math.PI / 4 + m * 0.7) + 0.4 * Math.sin(clockT * Math.PI / 6.5 + m * 1.3))
        p.y += lift * 0.22
        if (m === pullK && pullP > 0) {
            p.y += 0.5 * pullP
            p.z += 0.8 * pullP
            p.ry *= 1 - pullP
            p.rx *= 1 - 0.6 * pullP
        }
        return p
    }
    signal picked(int k)

    readonly property real focal: (height / 2) / Math.tan(15 * Math.PI / 180)
    readonly property real camZ: 12.4
    readonly property int cw: 260           // 卡带设计尺寸（像素），对应 2.6 × 1.7 单位
    readonly property int ch: 170
    // 画面上的槽位：前后各留足够多的卡带，让它们一直延伸到窗口外、被窗口边缘遮住，而不是在画面里淡出消失
    // （条目少时按循环重复出现，与示意图一致）
    readonly property int before: 6
    readonly property int after: 8

    function open(list, n, t) {
        deptN = n
        items = list
        intro = 0
        target = t || 0
        queue = []; stepping = false; bouncing = false; bounceAnim.stop()
        pos = target
        dest = target
        cur = target
        introTarget = 1
    }
    function close() { introTarget = 0; breathGoal = 0; idleTimer.stop(); queue = []; stepping = false; bounceAnim.stop(); bouncing = false }

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

    FrameAnimation {
        running: chain.visible && Math.abs(chain.introTarget - chain.intro) > 0
        onTriggered: {
            const dt = Math.min(0.05, frameTime)
            chain.intro += (chain.introTarget - chain.intro) * (1 - Math.pow(0.004, dt))
            if (Math.abs(chain.introTarget - chain.intro) < 0.002) chain.intro = chain.introTarget
        }
    }

    Repeater {
        model: chain.count > 0 ? chain.before + chain.after + 2 : 0
        Item {
            id: cas
            required property int index
            // 绝对槽位：以当前位置为基准向两侧展开；k 为实际条目
            readonly property int m: Math.floor(chain.cur) - chain.before + index
            readonly property int k: chain.wrap(m)
            readonly property bool real: true
            readonly property real s: m - chain.cur + 9 * (1 - chain.intro)
            property real lift: hot ? 1 : 0
            Behavior on lift { enabled: Theme.richMotion; NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
            readonly property var p: chain.placeAt(s, m, lift)
            // 只有入场时整体渐显；不再随离选中位的远近淡出
            readonly property real fade: Math.min(1, chain.intro * 1.4)
            readonly property bool hot: !chain.sliding && chain.hovered === m
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
                    // 有启动程序时显示程序图标唱片，否则显示档案章
                    readonly property string iconPath: cas.real && chain.items[cas.k] && chain.items[cas.k].icon ? chain.items[cas.k].icon : ""
                    IconDisc { visible: parent.iconPath !== ""; x: 20; y: 30; width: 100; height: 100; path: parent.iconPath }
                    Emblem {
                        face: Emblem.Tape
                        visible: parent.iconPath === ""
                        x: 34; y: 44
                        width: 72; height: 72
                        ink: Theme.dark ? "#e0e3dc" : "#ffffff"
                        core: Theme.accent
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
                    onContainsMouseChanged: if (!chain.sliding) chain.hovered = containsMouse ? cas.m : (chain.hovered === cas.m ? -10000 : chain.hovered)
                    onClicked: { chain.pickedSlot = cas.m; chain.picked(cas.k) }
                }
            }
        }
    }
}
