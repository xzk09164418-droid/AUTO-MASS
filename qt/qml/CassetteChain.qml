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
    function close() { introTarget = 0 }

    // 曲线：s 为相对选中位置的槽位
    function place(s) {
        const f = Math.max(0, 1 - Math.abs(s))
        const e = f * f * (3 - 2 * f)
        const t = s + Math.sign(s) * Math.min(1, Math.abs(s)) * 0.95
        return { x: -1.2 + 0.74 * t + 1.1 * e, y: -0.7 - 0.66 * t + 0.55 * e, z: 0.3 * t + 0.9 * e,
                 rx: -0.18 + 0.1 * e, ry: 0.5 - 0.38 * e, rz: 0.05 - 0.05 * e, sc: 1 + 0.2 * e, focus: e }
    }

    function mul(a, b) {
        const r = new Array(16)
        for (let i = 0; i < 4; i++)
            for (let j = 0; j < 4; j++)
                r[i * 4 + j] = a[i * 4] * b[j] + a[i * 4 + 1] * b[4 + j] + a[i * 4 + 2] * b[8 + j] + a[i * 4 + 3] * b[12 + j]
        return r
    }
    // 局部像素 (u, v) → 画面坐标的投影矩阵；zoff 为卡带内的前后层（单位）
    function matrix(p, zoff) {
        const sx = 2.6 / cw, sy = 1.7 / ch
        const A = [sx, 0, 0, -1.3, 0, -sy, 0, 0.85, 0, 0, 1, zoff, 0, 0, 0, 1]
        const S = [p.sc, 0, 0, 0, 0, p.sc, 0, 0, 0, 0, p.sc, 0, 0, 0, 0, 1]
        const cx = Math.cos(p.rx), sxr = Math.sin(p.rx), cy = Math.cos(p.ry), syr = Math.sin(p.ry), cz = Math.cos(p.rz), szr = Math.sin(p.rz)
        const Rx = [1, 0, 0, 0, 0, cx, -sxr, 0, 0, sxr, cx, 0, 0, 0, 0, 1]
        const Ry = [cy, 0, syr, 0, 0, 1, 0, 0, -syr, 0, cy, 0, 0, 0, 0, 1]
        const Rz = [cz, -szr, 0, 0, szr, cz, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        const T = [1, 0, 0, p.x, 0, 1, 0, p.y, 0, 0, 1, p.z - camZ, 0, 0, 0, 1]
        const P = [focal, 0, -width / 2, 0, 0, -focal, -height / 2, 0, 0, 0, 0, 0, 0, 0, -1, 0]
        const m = mul(P, mul(T, mul(Rx, mul(Ry, mul(Rz, mul(S, A))))))
        return Qt.matrix4x4(m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10], m[11], m[12], m[13], m[14], m[15])
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
            readonly property var p: chain.place(s)
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
