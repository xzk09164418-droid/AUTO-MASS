import QtQuick
import QtQuick3D
import "."

// 增强挡位：录像带串的真 3D 版本（Qt Quick 3D，可选组件）。
// 位置、呼吸、悬停抬起、档案抽出都沿用 CassetteChain 的 placeAt，只把绘制换成实体卡带：
// 半透明磨砂外壳（带厚度与光照）+ 正面档案章与编号（2D 内容直接贴在 3D 平面上）。
// 只在数值变化时重绘（Qt Quick 3D 按需渲染），静止时不占用持续帧。
Item {
    id: root

    property Item chain: null
    readonly property var items: chain ? chain.items : []

    // Rx·Ry·Rz（与 three.js 'XYZ' 欧拉顺序一致）→ 四元数
    function quat(rx, ry, rz) {
        const cx = Math.cos(rx / 2), sx = Math.sin(rx / 2), cy = Math.cos(ry / 2), sy = Math.sin(ry / 2), cz = Math.cos(rz / 2), sz = Math.sin(rz / 2)
        return Qt.quaternion(cx * cy * cz - sx * sy * sz, sx * cy * cz + cx * sy * sz, cx * sy * cz - sx * cy * sz, cx * cy * sz + sx * sy * cz)
    }

    View3D {
        id: view
        anchors.fill: parent
        renderMode: View3D.Offscreen
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
            tonemapMode: SceneEnvironment.TonemapModeNone
        }

        PerspectiveCamera {
            position: Qt.vector3d(0, 0, root.chain ? root.chain.camZ : 12.4)
            fieldOfView: 30
            clipNear: 1
            clipFar: 60
        }
        DirectionalLight { eulerRotation.x: -38; eulerRotation.y: -24; brightness: 1.5; color: "#fffaf2" }
        DirectionalLight { eulerRotation.x: 10; eulerRotation.y: 160; brightness: 0.35 }
        DirectionalLight { brightness: 0.55 }

        Repeater3D {
            model: root.chain ? root.items.length + root.chain.pad * 2 : 0
            delegate: Node {
                id: cas
                required property int index
                readonly property int k: index - root.chain.pad
                readonly property bool real: k >= 0 && k < root.items.length
                readonly property real s: k - root.chain.cur - root.chain.over + 9 * (1 - root.chain.intro)
                readonly property bool hot: real && root.chain.hovered === k
                property real lift: hot ? 1 : 0
                Behavior on lift { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
                readonly property var p: root.chain.placeAt(s, k, lift)
                readonly property real fade: Math.max(0, Math.min(1, 1.8 - Math.abs(s) / 4.2)) * Math.min(1, root.chain.intro * 1.4)
                visible: fade > 0.01
                position: Qt.vector3d(p.x, p.y, p.z)
                rotation: root.quat(p.rx, p.ry, p.rz)
                scale: Qt.vector3d(p.sc, p.sc, p.sc)

                // 外壳：2.6 × 1.7 × 0.26，选中 80% 不透明
                Model {
                    source: "#Cube"
                    pickable: cas.real
                    property int k: cas.k
                    scale: Qt.vector3d(0.026, 0.017, 0.0026)
                    materials: PrincipledMaterial {
                        baseColor: Theme.dark ? "#3a474c" : "#f3f1ec"
                        roughness: 0.38
                        metalness: 0
                        opacity: Math.min(0.8, 0.32 + 0.48 * cas.p.focus + (cas.hot ? 0.12 : 0)) * cas.fade
                        alphaMode: PrincipledMaterial.Blend
                    }
                }
                // 磨砂内窗：略凹进正面
                Model {
                    source: "#Rectangle"
                    position: Qt.vector3d(0, 0, 0.132)
                    scale: Qt.vector3d(0.0246, 0.0156, 1)
                    materials: PrincipledMaterial {
                        baseColor: "#ffffff"
                        roughness: 0.6
                        opacity: (cas.real ? 0.28 + 0.12 * cas.p.focus : 0.18) * cas.fade
                        alphaMode: PrincipledMaterial.Blend
                        lighting: PrincipledMaterial.NoLighting
                    }
                }
                // 正面内容：2D 内容按 1 像素 = 0.01 单位贴在外壳前
                Node {
                    position: Qt.vector3d(0, 0, 0.136)
                    scale: Qt.vector3d(0.01, 0.01, 0.01)
                    Item {
                        x: -130
                        y: -85
                        width: 260
                        height: 170
                        opacity: (cas.real ? 0.75 + 0.25 * cas.p.focus : 0.5) * cas.fade
                        Rectangle { anchors.fill: parent; color: "transparent"; border.width: 1.5; border.color: cas.hot ? Theme.accent : Theme.dark ? "#6d7b80" : "#9e9a90"; radius: 7 }
                        Rectangle {
                            x: 24; y: 34
                            width: 92; height: 92
                            color: Theme.dark ? "#11181b" : "#2a2b2a"
                            Emblem { anchors.centerIn: parent; width: 72; height: 72; ink: Theme.dark ? "#e0e3dc" : "#ffffff"; core: Theme.accent; lineWidth: 3.2; curve: false }
                        }
                        Column {
                            visible: cas.real
                            x: 134; y: 48
                            spacing: 6
                            Text { text: root.chain.deptN + "-" + String(cas.k + 1).padStart(2, "0"); color: Theme.ink; font.family: Theme.font; font.pixelSize: 15; font.weight: Font.Bold }
                            Text { width: 116; elide: Text.ElideRight; text: cas.real ? root.items[cas.k].name : ""; color: Theme.ink; font.family: Theme.font; font.pixelSize: 19; font.weight: Font.Bold }
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
                }
            }
        }
    }

    // 拾取：悬停与点击都用 3D 射线命中
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        cursorShape: root.chain && root.chain.hovered >= 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
        function hitAt(x, y) {
            const r = view.pick(x, y)
            return r.objectHit && r.objectHit.k !== undefined ? r.objectHit.k : -1
        }
        onPositionChanged: mouse => { const k = hitAt(mouse.x, mouse.y); if (root.chain.hovered !== k) root.chain.hovered = k }
        onExited: root.chain.hovered = -1
        onClicked: mouse => { const k = hitAt(mouse.x, mouse.y); if (k >= 0) root.chain.picked(k) }
    }
}
