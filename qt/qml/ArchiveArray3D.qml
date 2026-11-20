import QtQuick
import QtQuick3D
import QtQuick3D.Helpers
import QtQuick3D.AssetUtils
import "."

// 增强挡位：多列档案阵列（以 design/qt-demo/array.html 为基线，按 LBEILC/RhineLabUI 的实现移植，MIT）。
// 列 = 通用脚本，列内 = 脚本配置 + 各账号；首尾按周期无缝循环，每列记住上次的选择。
// 读取时选中的录像带抬起、镜头转向把它放到画面左侧，玻璃由磨砂变清晰，露出内部的程序图标唱片
// （参考 Rhine Music Database 把封面放进录像带）。只在运动、波浪、呼吸期间逐帧更新。
Item {
    id: root

    property var columns: []                 // [{ name, en, icon, accounts: [名称…] }]
    property bool active: visible
    readonly property int laneCount: Math.max(1, columns.length)
    readonly property int lane: wrap(cellLane, laneCount)
    readonly property var column: columns.length ? columns[lane] : null
    readonly property int rowCount: column ? 1 + (column.accounts ? column.accounts.length : 0) : 1
    readonly property int row: wrap(cellRow - 12, rowCount)
    property bool detailOpen: false
    readonly property string fileId: "X-" + String(lane + 1).padStart(2, "0") + String(row).padStart(2, "0")
    property int dir: 1

    signal opened(int lane, int row)
    signal closed()
    signal moved(int lane, int row)

    // ── 运动函数（与演示基线 / 原项目 motion.ts 相同） ─────────────────────
    function wrap(v, n) { return ((v % n) + n) % n }
    function smooth(t) { t = Math.max(0, Math.min(1, t)); return t * t * t * (10 + t * (-15 + 6 * t)) }
    function ease(t) { t = Math.max(0, Math.min(1, t)); return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2 }
    function bell(x, w) { return Math.exp(-0.5 * (x / w) * (x / w)) }
    function settlingWave(distance, time) {
        const age = time - 25.05 - Math.abs(distance) * 0.065
        const envelope = Math.max(-0.42, 2.15 - 0.17 * (Math.sqrt(distance * distance + 1) - 1))
        const ring = age > 0 ? Math.sin(age * 5.1) * Math.exp(-age * 1.3) : 0
        return envelope * (smooth(age / 0.62) + 0.18 * ring * smooth(age / 0.16))
    }
    function selectionWave(distance, age) {
        if (age < 0 || age > 3.2) return 0
        return 0.8 * smooth(age / 0.2) * Math.exp(-age * 1.15) * Math.cos((distance - age * 8) * 0.58) * bell(distance - age * 8, 3.4)
    }
    function columnStrength(l, focus) { return 0.25 + 0.75 * bell(l - focus, 0.55) }
    function idleWave(r, l, t) { return 0.075 * Math.sin(t * Math.PI / 4 + r * 0.3 - l * 0.45) + 0.027 * Math.sin(t * Math.PI * 2 / 13 - r * 0.17 + l * 0.3) }
    function damp(s, target, rate, dt) {
        const delta = s.v - target, impulse = s.vel + rate * delta, decay = Math.exp(-rate * dt)
        s.v = target + (delta + impulse * dt) * decay
        s.vel = (s.vel - rate * impulse * dt) * decay
    }

    readonly property real columnSpacing: 5.2
    readonly property real rowSpacing: 0.62
    readonly property real inspectionLift: 4.05

    // ── 状态 ──────────────────────────────────────────────────────────────
    property int cellLane: 2
    property int cellRow: 12
    property var laneMemory: ({})
    property var springs: ({ lift: { v: 0, vel: 0 }, rail: { v: 0, vel: 0 }, shoulder: { v: 12, vel: 0 }, focus: { v: 2, vel: 0 }, track: { v: 0, vel: 0 } })
    property var pulses: []
    property real clock: 0
    property real lastInteraction: 0
    property real idleGain: 0
    property real pulseGain: 1
    property real detail: 0
    property real clarity: 0
    property var hoverCell: null
    property var hoverLifts: ({})

    function nav(axis, d) {
        if (detailOpen) return
        lastInteraction = clock
        dir = d
        if (axis === "row") cellRow += d
        else {
            const m = Object.assign({}, laneMemory)
            m[wrap(cellLane, laneCount)] = cellRow
            laneMemory = m
            cellLane += d
            const r = laneMemory[wrap(cellLane, laneCount)]
            if (r !== undefined) cellRow = r
        }
        changed()
    }
    function goCell(l, r) {
        if (detailOpen) return
        dir = l > cellLane || (l === cellLane && r > cellRow) ? 1 : -1
        lastInteraction = clock
        cellLane = l; cellRow = r
        changed()
    }
    function changed() {
        breathingOnly = false
        springs.lift.v = 0; springs.lift.vel = 0
        const p = pulses.slice(-5); p.push({ lane: cellLane, row: cellRow, time: clock }); pulses = p
        moved(lane, row)
        running = true
    }
    function open() { if (detailOpen) return; detailOpen = true; breathingOnly = false; running = true; opened(lane, row) }
    function close() { if (!detailOpen) return; detailOpen = false; breathingOnly = false; running = true; closed() }

    // ── 3D 场景 ────────────────────────────────────────────────────────────
    View3D {
        id: view
        anchors.fill: parent
        environment: ExtendedSceneEnvironment {
            backgroundMode: SceneEnvironment.Color
            clearColor: Theme.dark ? "#11181b" : "#eae5e1"
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.Medium
            tonemapMode: SceneEnvironment.TonemapModeAces
            exposure: 1.05
            fog: Fog {
                enabled: true
                color: Theme.dark ? "#11181b" : "#eae5e1"
                depthEnabled: true
                depthNear: root.fogNear
                depthFar: root.fogFar
            }
            // 环境光遮蔽：档案板之间的阴影层次（原项目为共享深度的 AO）
            aoStrength: 55
            aoDistance: 18
            aoSoftness: 40
            aoSampleRate: 1
            depthOfFieldEnabled: true
            depthOfFieldFocusDistance: root.focusDistance
            depthOfFieldFocusRange: 30
            depthOfFieldBlurAmount: 2 + 2 * root.detail
        }

        PerspectiveCamera {
            id: camera
            clipNear: 5
            clipFar: 300
            fieldOfView: 3
            position: Qt.vector3d(-62.26, 35.98, 43.28)
        }
        // 主光（投影）+ 补光；主光的环境色近似原项目的半球光
        DirectionalLight {
            id: key
            color: "#fff7ed"
            // Qt Quick 3D 没有原项目的环境贴图（RoomEnvironment）：用较亮的环境色 + 两盏补光近似它的柔和照明
            ambientColor: Theme.dark ? "#3a4448" : "#b9b0a5"
            brightness: 1.0
            eulerRotation: Qt.vector3d(-62, -130, 0)
            castsShadow: true
            shadowMapQuality: Light.ShadowMapQualityMedium
            shadowFactor: 45
            pcfFactor: 4
            shadowMapFar: 120
        }
        DirectionalLight { color: "#ffffff"; brightness: 0.55; eulerRotation: Qt.vector3d(-35, 145, 0) }
        DirectionalLight { color: "#fffaf3"; brightness: 0.45; eulerRotation: Qt.vector3d(-20, -60, 0) }
        Model {
            source: "#Rectangle"
            position: Qt.vector3d(0, -4.63, 0)
            eulerRotation.x: -90
            scale: Qt.vector3d(4, 4, 1)
            receivesShadows: true
            materials: PrincipledMaterial { baseColor: Theme.dark ? "#1b2428" : "#d8c9b9"; roughness: 0.95 }
        }

        // 阵列：同一个模型的实例化副本
        RuntimeLoader {
            id: arrayLoader
            source: Qt.resolvedUrl("../assets3d/archive-cassette.glb")
            instancing: InstanceList { id: instances }
            onStatusChanged: if (status === RuntimeLoader.Success) root.prepare(arrayLoader, true)
        }
        // 选中的那一盒：完整材质、档案标签、程序图标唱片
        Node {
            id: selected
            RuntimeLoader {
                id: selectedLoader
                source: Qt.resolvedUrl("../assets3d/archive-cassette.glb")
                onStatusChanged: if (status === RuntimeLoader.Success) root.prepare(selectedLoader, false)
            }
            Model {
                id: labelPlate
                source: "#Rectangle"
                position: Qt.vector3d(-1.36, 3.04, 0.255)
                scale: Qt.vector3d(0.0099, 0.0046, 1)
                materials: PrincipledMaterial {
                    lighting: PrincipledMaterial.NoLighting
                    alphaMode: PrincipledMaterial.Blend
                    baseColorMap: Texture { sourceItem: labelArt }
                }
            }
            Model {
                id: disc
                source: "#Rectangle"
                position: Qt.vector3d(0.22, 1.86, 0.12)
                scale: Qt.vector3d(0.0264, 0.0264, 1)
                materials: PrincipledMaterial {
                    roughness: 0.55
                    alphaMode: PrincipledMaterial.Mask
                    alphaCutoff: 0.5
                    cullMode: Material.NoCulling
                    baseColorMap: Texture { sourceItem: discArt }
                }
            }
        }
    }

    // 部件按材质顺序识别（与 glTF 材质表一一对应）
    readonly property var partNames: ["Frosted_Polymer", "Ivory_Edges", "Optical_Diffuser", "Printed_Label", "Carbon_Ink", "Internal_Ceramic", "Optical_Edges",
        "Subsurface_Optics", "Optical_Film_Edge", "Amber_Optical_Inlay", "Optical_Film", "Index_Inlay", "Case_Engraving", "Case_Engraving_Highlight",
        "Titanium_Fasteners", "Moulded_Lettering", "Champagne_Index"]
    readonly property var ringParts: ["Optical_Edges", "Internal_Ceramic", "Subsurface_Optics", "Amber_Optical_Inlay", "Optical_Film", "Optical_Film_Edge"]
    readonly property var arrayParts: ["Frosted_Polymer", "Ivory_Edges", "Titanium_Fasteners", "Index_Inlay", "Optical_Diffuser"]
    property var frostedMaterial: null
    function prepare(loader, isArray) {
        const materials = [], models = []
        function walk(n) {
            for (let i = 0; i < n.children.length; i++) {
                const c = n.children[i]
                if (c.baseColor !== undefined && c.materials === undefined) materials.push(c)
                if (c.materials !== undefined) models.push(c)
                walk(c)
            }
        }
        walk(loader)
        for (const m of models) {
            const name = partNames[materials.indexOf(m.materials[0])] || ""
            const mat = m.materials[0]
            m.castsShadows = name === "Optical_Diffuser"
            m.receivesShadows = true
            // 模型自带的竖排浮雕字是原作品牌（RHINE LAB），不使用
            if (name === "Carbon_Ink" || name === "Moulded_Lettering") { m.visible = false; continue }
            // 没有环境贴图时金属会发黑：紧固件降低金属度
            if (name === "Titanium_Fasteners") { mat.metalness = 0.25; mat.roughness = 0.45 }
            if (isArray) {
                m.pickable = true
                // 阵列只保留外壳、边、紧固件、索引和漫射层，颜色取原项目的阵列值
                if (arrayParts.indexOf(name) < 0) { m.visible = false; continue }
                // Qt 的透射会把内层深色漫射板透出来：阵列外壳改为不透光的暖白，观感接近原项目的磨砂
                if (name === "Frosted_Polymer") { mat.baseColor = "#f7efe4"; mat.transmissionFactor = 0; mat.roughness = 0.34; mat.clearcoatAmount = 0.3; mat.clearcoatRoughnessAmount = 0.25 }
                if (name === "Optical_Diffuser") mat.baseColor = "#806447"
                if (name === "Ivory_Edges") { mat.transmissionFactor = 0; mat.baseColor = "#fff5e9"; mat.roughness = 0.38 }
                if (name === "Index_Inlay") { mat.baseColor = "#e4d6c5"; mat.metalness = 0.05 }
            } else {
                if (ringParts.indexOf(name) >= 0) { m.visible = false; continue }      // 双环换成图标唱片
                if (name === "Frosted_Polymer") { mat.baseColor = "#fffdfa"; mat.transmissionFactor = 0.9; mat.thicknessFactor = 0.12; mat.roughness = 0.21; mat.indexOfRefraction = 1.46; root.frostedMaterial = mat }
                if (name === "Printed_Label") mat.baseColor = "#eae5dc"
                if (name === "Ivory_Edges") { mat.baseColor = "#f0e7df"; mat.roughness = 0.31; mat.transmissionFactor = 0.65; mat.thicknessFactor = 0.04 }
                if (name === "Optical_Diffuser") { mat.baseColor = "#e2dad4"; mat.transmissionFactor = 0; mat.roughness = 0.7 }
            }
        }
        running = true
    }

    // ── 每帧更新 ──────────────────────────────────────────────────────────
    property bool running: true
    property real fogNear: 145
    property real fogFar: 165
    property real focusDistance: 140
    property var entries: []
    readonly property int maxInstances: 5 * 30
    Component { id: entryComponent; InstanceListEntry {} }
    Component.onCompleted: {
        const list = []
        for (let i = 0; i < maxInstances; i++) list.push(entryComponent.createObject(instances, { scale: Qt.vector3d(0, 0, 0) }))
        entries = list
        instances.instances = list
    }

    readonly property vector3d baseDirection: {
        const yaw = 59 * Math.PI / 180, el = 19 * Math.PI / 180
        return Qt.vector3d(-Math.sin(yaw) * Math.cos(el), Math.sin(el), Math.cos(yaw) * Math.cos(el))
    }
    property var drawn: []
    property real cameraAimX: -0.5
    property real cameraAimY: 1.1
    property real cameraAimZ: 0.4

    function field(r, l, t) {
        let ripple = 0
        if (Theme.richMotion) for (const p of pulses) ripple += selectionWave(Math.hypot(r - p.row, (l - p.lane) * 2.2), t - p.time)
        return settlingWave(r - springs.shoulder.v, 26.56) * columnStrength(l, springs.focus.v) + idleWave(r, l, t) * idleGain + Math.max(-0.6, Math.min(0.6, ripple)) * pulseGain
    }
    function step(dt) {
        clock += dt
        const t = clock
        const S = springs
        const chosenX = (cellLane - 2) * columnSpacing, chosenZ = (cellRow - 15.5) * rowSpacing
        damp(S.shoulder, cellRow, 5, dt)
        damp(S.focus, cellLane, 4, dt)
        damp(S.track, chosenX, 3.7, dt)
        damp(S.rail, -2.17 - chosenZ, 3.7, dt)
        pulses = pulses.filter(p => t - p.time < 3.2)
        const idle = Theme.richMotion && !detailOpen && detail < 0.01 && t - lastInteraction > 2.5
        idleGain += ((idle ? 1 : 0) - idleGain) * (1 - Math.exp(-dt * (idle ? 0.8 : 4)))
        pulseGain += ((detailOpen ? 0 : 1) - pulseGain) * (1 - Math.exp(-dt * 8))
        // 悬停抬起
        const hl = Object.assign({}, hoverLifts)
        const hk = hoverCell ? hoverCell.lane + ":" + hoverCell.row : ""
        if (hk && hl[hk] === undefined) hl[hk] = 0
        for (const k in hl) {
            const target = k === hk ? 0.28 : 0
            hl[k] += (target - hl[k]) * (1 - Math.exp(-dt * 14))
            if (target === 0 && hl[k] < 0.0001) delete hl[k]
        }
        hoverLifts = hl
        damp(S.lift, detailOpen ? inspectionLift : 0.4, Theme.richMotion ? 4.2 : 35, dt)
        const camTarget = detailOpen ? ease((S.lift.v - 0.8) / 2.4) : ease((S.lift.v - 0.4) / (inspectionLift - 0.4))
        detail += (camTarget - detail) * (1 - Math.exp(-dt * (Theme.richMotion ? 2.8 : 35)))
        const clearTarget = detailOpen && detail > 0.78 && S.lift.v > 3.3
        clarity = clearTarget ? Math.min(1, clarity + dt / 1.6) : Math.max(0, clarity - dt * 4)
        if (frostedMaterial) {
            const c = ease(clarity)
            frostedMaterial.transmissionFactor = 0.9 + (0.985 - 0.9) * c
            frostedMaterial.thicknessFactor = 0.12 + (0.018 - 0.12) * c
            frostedMaterial.roughness = 0.21 + (0.025 - 0.21) * c
        }
        const trackX = S.track.v, rail = S.rail.v
        const q = ease(S.lift.v / 0.4)
        const hover = hoverLifts[cellLane + ":" + cellRow] || 0
        const selY = -4.6 + field(cellRow, cellLane, t) + S.lift.v + hover
        selected.position = Qt.vector3d(chosenX - trackX, selY, chosenZ + rail)
        selected.eulerRotation.x = (field(cellRow + 0.5, cellLane, t) - field(cellRow - 0.5, cellLane, t)) * 0.024 * (1 - detail) * (1 - q) * 57.2958
        disc.opacity = q
        labelPlate.opacity = q

        // 镜头：长焦，阵列 140 单位外取景；读取时拉近到 72，录像带放到画面左侧
        const d = baseDirection.times(1 - detail).plus(Qt.vector3d(-0.277, 0.238, 0.931).times(detail)).normalized()
        const distance = 140 + (72 - 140) * detail
        const span = 7.33 + (5.9 - 7.33) * detail
        const right = Qt.vector3d(0, 1, 0).crossProduct(d).normalized()
        const up = d.crossProduct(right).normalized()
        const pixelScale = 1080 / span
        let detailAim = selected.position.plus(Qt.vector3d(0, 1.85, 0))
        detailAim = detailAim.plus(right.times((0.5 - 550 / 1920) * 1920 / pixelScale)).plus(up.times((560 / 1080 - 0.5) * 1080 / pixelScale))
        const arrayAim = Qt.vector3d(-1.091, -0.045, 0.481)
        const aim = arrayAim.times(1 - detail).plus(detailAim.times(detail))
        const camPos = aim.plus(d.times(distance))
        const blend = 1 - Math.exp(-dt * 5)
        camera.position = camera.position.times(1 - blend).plus(camPos.times(blend))
        cameraAimX += (aim.x - cameraAimX) * blend; cameraAimY += (aim.y - cameraAimY) * blend; cameraAimZ += (aim.z - cameraAimZ) * blend
        camera.lookAt(Qt.vector3d(cameraAimX, cameraAimY, cameraAimZ))
        const fov = 2 * Math.atan(span / (2 * distance)) * 180 / Math.PI
        camera.fieldOfView += (fov - camera.fieldOfView) * blend
        const rendered = camera.position.minus(Qt.vector3d(cameraAimX, cameraAimY, cameraAimZ)).length()
        fogNear = rendered + 5 + (-1 - 5) * detail
        fogFar = rendered + 25 + (12 - 25) * detail
        focusDistance = rendered

        // 阵列实例：当前列左右各 3 列、当前行前后 18 行（跳过选中的那一格）
        const list = []
        let i = 0
        // 只画视野内：当前列左右各 2 列、当前行前 16 行到后 12 行
        for (let l = cellLane - 2; l <= cellLane + 2; l++) {
            for (let r = cellRow - 16; r <= cellRow + 12; r++) {
                if (l === cellLane && r === cellRow) continue
                if (i >= maxInstances) break
                const x = (l - 2) * columnSpacing - trackX
                const z = (r - 15.5) * rowSpacing + rail
                if (Math.abs(x) > 19 || z < -16 || z > 14) continue
                const hv = hoverLifts[l + ":" + r] || 0
                const y = -4.6 + field(r, l, t) + hv
                const slope = field(r + 0.5, l, t) - field(r - 0.5, l, t)
                const e = entries[i]
                e.position = Qt.vector3d(x, y, z)
                e.eulerRotation = Qt.vector3d(slope * 0.024 * (1 - detail) * 57.2958, 0, 0)
                e.scale = Qt.vector3d(1, 1, 1)
                list.push({ lane: l, row: r })
                i++
            }
        }
        for (let k = i; k < entries.length; k++) if (entries[k].scale.x !== 0) entries[k].scale = Qt.vector3d(0, 0, 0)
        drawn = list
        const moving = Math.abs(S.lift.vel) > 1e-4 || Math.abs(detail - camTarget) > 1e-3 || pulses.length > 0 || Math.abs(S.rail.vel) > 1e-4
            || Math.abs(S.track.vel) > 1e-4 || Object.keys(hoverLifts).length > 0
            || (clearTarget ? clarity < 1 : clarity > 0) || camera.position.minus(camPos).length() > 0.01
        // 只剩空闲呼吸时降为每秒 12 次更新（呼吸周期 8 / 13 秒、幅度不到卡片高度 3%，看不出台阶）
        breathingOnly = !moving && (idleGain > 0.001 || idle)
        return moving || breathingOnly
    }
    property bool breathingOnly: false
    FrameAnimation {
        running: root.active && root.running && !root.breathingOnly
        onTriggered: { if (!root.step(Math.min(0.05, frameTime))) root.running = false }
    }
    Timer {
        interval: 80
        repeat: true
        running: root.active && root.running && root.breathingOnly
        onTriggered: { if (!root.step(0.08)) root.running = false }
    }
    // 停止操作 2.5 秒后进入呼吸：唤醒逐帧更新
    Timer {
        interval: 2000
        repeat: true
        running: root.active && !root.running && !root.detailOpen && Theme.richMotion
        onTriggered: if (root.clock - root.lastInteraction > 2.4) root.running = true
    }

    // ── 拾取 ──────────────────────────────────────────────────────────────
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        enabled: !root.detailOpen
        function cellAt(x, y) {
            const r = view.pick(x, y)
            if (!r.objectHit) return null
            if (r.instanceIndex >= 0 && r.instanceIndex < root.drawn.length) return root.drawn[r.instanceIndex]
            return { lane: root.cellLane, row: root.cellRow }
        }
        onPositionChanged: mouse => {
            const c = cellAt(mouse.x, mouse.y)
            const h = c && !(c.lane === root.cellLane && c.row === root.cellRow) ? c : null
            const same = (a, b) => a && b && a.lane === b.lane && a.row === b.row
            if (!same(h, root.hoverCell) && (h || root.hoverCell)) { root.hoverCell = h; root.lastInteraction = root.clock; root.breathingOnly = false; root.running = true }
            cursorShape = c ? Qt.PointingHandCursor : Qt.ArrowCursor
        }
        onExited: if (root.hoverCell) { root.hoverCell = null; root.running = true }
        onClicked: mouse => {
            const c = cellAt(mouse.x, mouse.y)
            if (!c) return
            if (c.lane === root.cellLane && c.row === root.cellRow) root.open()
            else root.goCell(c.lane, c.row)
        }
    }

    // ── 贴图来源：档案标签与图标唱片（离屏渲染） ──────────────────────────
    Item {
        x: -4000
        width: 1024
        height: 440
        Rectangle {
            id: labelArt
            width: 1024; height: 440
            color: "#e6e2d9"
            Rectangle { x: 12; y: 12; width: 1000; height: 6; color: "#171713" }
            Rectangle { x: 12; y: 419; width: 1000; height: 3; color: "#171713" }
            Text { x: 22; y: 30; text: "AUTO-MAS"; color: "#171713"; font.family: Theme.font; font.pixelSize: 81; font.bold: true }
            Text { x: 25; y: 140; text: "SCRIPT CUSTODY"; color: "#878476"; font.family: Theme.font; font.pixelSize: 32 }
            Text { x: 22; y: 230; text: "NO." + String(root.lane * 10 + root.row + 1).padStart(3, "0"); color: "#171713"; font.family: Theme.font; font.pixelSize: 130; font.bold: true }
            Rectangle { x: 782; y: 32; width: 221; height: 39; color: "#171713"; Text { x: 27; anchors.verticalCenter: parent.verticalCenter; text: "A M / S C"; color: "#eee9de"; font.family: Theme.font; font.pixelSize: 24 } }
            Text { x: 830; y: 84; text: "INFO"; color: "#171713"; font.family: Theme.font; font.pixelSize: 64; font.bold: true }
            Emblem { x: 820; y: 250; width: 92; height: 92; ink: "#171713"; core: Theme.accent; lineWidth: 2.6 }
            Mark { x: 915; y: 254; width: 84; height: 84; ink: "#171713" }
        }
    }
    Item {
        x: -4000
        y: 600
        width: 512
        height: 512
        Item {
            id: discArt
            width: 512; height: 512
            IconDisc { anchors.fill: parent; path: root.column && root.column.icon ? root.column.icon : "" }
            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 352
                spacing: 4
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: root.column && root.column.icon ? root.column.icon.split(/[\\/]/).pop() : "AUTO-MAS"
                    color: Qt.rgba(0.12, 0.12, 0.1, 0.82); font.family: Theme.font; font.pixelSize: 26; font.bold: true
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: root.row === 0 ? (root.column ? root.column.name : "") : (root.column && root.column.accounts ? root.column.accounts[root.row - 1] + " · " + root.column.name : "")
                    color: Qt.rgba(0.12, 0.12, 0.1, 0.55); font.family: Theme.font; font.pixelSize: 15
                }
            }
        }
    }

    // ── 界面（原项目的档案选择版式） ──────────────────────────────────────
    Item {
        anchors.fill: parent
        opacity: root.detailOpen ? 0 : 1
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 300 } }

        Column {
            x: 970; y: 471
            spacing: 0
            Row {
                spacing: 16
                Text { text: "INTERNAL DATABASE"; color: "#77756d"; font.family: Theme.font; font.pixelSize: 12; font.letterSpacing: 1.3 }
                Text { text: "／"; color: "#77756d"; font.family: Theme.font; font.pixelSize: 12 }
                RollText { text: root.column ? root.column.name : ""; dir: root.dir; color: "#77756d"; font.family: Theme.font; font.pixelSize: 12; font.letterSpacing: 1.3 }
            }
            Item { width: 1; height: 22 }
            Row {
                spacing: 10
                Text { text: "FILE NUMBER:"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 28; font.weight: Font.Bold }
                RollText { text: root.fileId; dir: root.dir; color: Theme.ink; font.family: Theme.font; font.pixelSize: 28; font.weight: Font.Bold }
                Text { text: "↗"; color: Theme.ink; opacity: 0.5; font.pixelSize: 20; anchors.verticalCenter: parent.verticalCenter
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.open() } }
            }
            Item { width: 1; height: 55 }
            Item {
                width: 950; height: 1
                Rectangle { x: 57; width: parent.width - 57; height: 1; color: "#504b41" }
                Rectangle { x: -4; y: -3; width: 6; height: 6; color: "#282a24" }
            }
            Item { width: 1; height: 22 }
            Item {
                x: 58; width: 652; height: 22
                RollText { text: root.row === 0 ? (root.column ? root.column.name + " · 脚本配置" : "") : (root.column && root.column.accounts ? root.column.accounts[root.row - 1] : ""); dir: root.dir; color: Theme.ink; font.family: Theme.font; font.pixelSize: 16 }
                Text { anchors.right: parent.right; text: root.row === 0 ? "SCRIPT CONFIG" : "ACCOUNT"; color: "#666257"; font.family: Theme.font; font.pixelSize: 11; font.letterSpacing: 1 }
            }
            Item { width: 1; height: 58 }
            Row {
                x: 58
                spacing: 70
                Text { text: "ACCESS FILE"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 14; font.letterSpacing: 1 }
                Text { text: "→"; color: Theme.ink; font.pixelSize: 24; anchors.verticalCenter: parent.verticalCenter }
                MouseArea { x: -10; y: -10; width: 260; height: 50; cursorShape: Qt.PointingHandCursor; onClicked: root.open() }
            }
        }
        // 左下：列内序号
        Column {
            x: 60; y: 1080 - 115 - 92
            Text { text: "ARCHIVE / SELECT"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 11; font.letterSpacing: 1.7 }
            Item { width: 1; height: 16 }
            Row {
                spacing: 21
                RollDigits { text: String(root.row + 1).padStart(2, "0"); dir: root.dir; color: Theme.ink; font.family: Theme.font; font.pixelSize: 58 }
                Text { anchors.bottom: parent.bottom; anchors.bottomMargin: 8; text: "/"; color: "#8f8a80"; font.family: Theme.font; font.pixelSize: 32; font.weight: Font.Light }
                Text { anchors.bottom: parent.bottom; anchors.bottomMargin: 10; text: String(root.rowCount).padStart(2, "0"); color: "#726f67"; font.family: Theme.font; font.pixelSize: 22 }
            }
        }
        // 底部：上下翻档 + 刻度
        Row {
            x: 504; y: 1080 - 131 - 46
            spacing: 33
            Text { width: 46; height: 46; text: "↑"; color: Theme.ink; font.pixelSize: 28; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.nav("row", -1) } }
            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 12
                Repeater {
                    model: root.rowCount
                    Item {
                        required property int index
                        width: 14; height: 40
                        Rectangle { x: 6; width: 2; anchors.verticalCenter: parent.verticalCenter; height: index === root.row ? 33 : 12; color: index === root.row ? "#24261f" : "#aaa59a"
                            Behavior on height { NumberAnimation { duration: 400 } } }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.goCell(root.cellLane, root.cellRow + index - root.row) }
                    }
                }
            }
            Text { width: 46; height: 46; text: "↓"; color: Theme.ink; font.pixelSize: 28; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.nav("row", 1) } }
        }
        // 底部：列切换
        Row {
            x: 1005; y: 1080 - 131 - 46
            spacing: 24
            Text { width: 46; height: 46; text: "←"; color: Theme.ink; font.pixelSize: 24; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.nav("lane", -1) } }
            Column {
                anchors.verticalCenter: parent.verticalCenter
                width: 160
                spacing: 7
                RollText { text: "COLUMN " + String(root.lane + 1).padStart(2, "0") + " / " + String(root.laneCount).padStart(2, "0"); dir: root.dir; color: "#726f67"; font.family: Theme.font; font.pixelSize: 10; font.letterSpacing: 1.2 }
                RollText { text: root.column ? root.column.name : ""; dir: root.dir; color: Theme.ink; font.family: Theme.font; font.pixelSize: 15 }
            }
            Text { width: 46; height: 46; text: "→"; color: Theme.ink; font.pixelSize: 24; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.nav("lane", 1) } }
        }
        Text {
            x: 505; y: 1080 - 60 - 12
            text: "←  →  切换脚本    ／    ↑  ↓  前后档案    ／    ENTER  读取"
            color: "#858077"; font.family: Theme.font; font.pixelSize: 10; font.letterSpacing: 0.9
        }
    }
}
