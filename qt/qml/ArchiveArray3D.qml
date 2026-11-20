import QtQuick
import QtQuick3D
import QtQuick3D.Helpers
import QtQuick3D.AssetUtils
import "."

// 增强挡位：多列档案阵列（以 design/qt-demo/array.html 为基线，按 LBEILC/RhineLabUI 的实现移植，MIT）。
// 托管管理：列 = 通用脚本，列内 = 脚本配置 + 各账号；调度队列：列 = 队列，列内 = 队列配置 + 各队列项。
// 首尾按周期无缝循环，每列记住上次的选择。读取时选中的录像带抬起、镜头转向把它放到画面左侧，
// 玻璃由磨砂变清晰，露出内部的程序图标唱片（参考 Rhine Music Database 把封面放进录像带）。
//
// 画面以演示基线为准：环境光照（RoomEnvironment + 半球光烘成的 HDR）、主光与补光、软阴影、透射磨砂外壳与竖向渐变。
// 省 CPU：阵列的波浪、呼吸、涟漪、悬停与飞入都在顶点着色器里算（arraypart.vert），
// 每帧只更新弹簧、镜头与少量 uniform；实例表只在换档时重建。
// 组件在启动空闲后预加载（见 Main.qml），托管管理与调度队列共用同一份。
Item {
    id: root

    property string mode: "scripts"          // scripts / queue
    property var columns: []                 // [{ name, en, icon, accounts: [行名…], rowIcons: [每行图标…] }]
    property bool active: visible
    readonly property int laneCount: Math.max(1, columns.length)
    readonly property int lane: wrap(cellLane, laneCount)
    readonly property var column: columns.length ? columns[lane] : null
    readonly property int rowCount: column ? 1 + (column.accounts ? column.accounts.length : 0) : 1
    readonly property int row: wrap(cellRow - 12, rowCount)
    property bool detailOpen: false
    readonly property string fileId: (mode === "queue" ? "Q-" : "X-") + String(lane + 1).padStart(2, "0") + String(row).padStart(2, "0")
    property int dir: 1
    // 文案：按部门区分
    readonly property bool isQueue: mode === "queue"
    readonly property string rowName: row === 0 ? (column ? column.name + (isQueue ? " · 队列配置" : " · 脚本配置") : "")
        : (column && column.accounts ? column.accounts[row - 1] || "" : "")
    readonly property string rowIcon: !column ? "" : column.rowIcons ? column.rowIcons[row] || "" : column.icon || ""

    signal opened(int lane, int row)
    signal closed()
    signal moved(int lane, int row)
    signal flownOut()

    // ── 运动函数（与演示基线 / 原项目 motion.ts 相同；阵列部分在着色器里有同一份） ──
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
    function lin(hex) {
        const c = Qt.color(hex), f = v => v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)
        return Qt.vector3d(f(c.r), f(c.g), f(c.b))
    }

    readonly property real columnSpacing: 5.2
    readonly property real rowSpacing: 0.62
    readonly property real inspectionLift: 4.05

    // ── 状态 ──────────────────────────────────────────────────────────────
    property int cellLane: 2
    property int cellRow: 12
    property var laneMemory: ({})
    property var springs: ({ lift: { v: 0.4, vel: 0 }, rail: { v: 0, vel: 0 }, shoulder: { v: 12, vel: 0 }, focus: { v: 2, vel: 0 }, track: { v: 0, vel: 0 } })
    property var pulses: []
    property real clock: 0
    property real lastInteraction: 0
    property real idleGain: 0
    property real pulseGain: 1
    property real detail: 0
    property real clarity: 0
    property var hoverCell: null
    property var hoverLifts: ({})
    // 飞入进度（秒）：0 = 全部在画面外；≥ 1.7 = 全部落位。flyDir 为 1 飞入、-1 飞出、0 静止
    property real fly: 2
    property int flyDir: 0

    // 着色器 uniform
    property real uShoulder: 12
    property real uFocus: 2
    property real uDetail: 0
    property vector4d hover0: Qt.vector4d(0, 0, 0, 0)
    property vector4d hover1: Qt.vector4d(0, 0, 0, 0)
    property vector4d hover2: Qt.vector4d(0, 0, 0, 0)
    property var pulseVecs: [Qt.vector4d(0, 0, 0, 0), Qt.vector4d(0, 0, 0, 0), Qt.vector4d(0, 0, 0, 0), Qt.vector4d(0, 0, 0, 0), Qt.vector4d(0, 0, 0, 0), Qt.vector4d(0, 0, 0, 0)]

    // 换到另一个部门（或重新进入）：状态归位，不播放切换过渡
    function reset(laneIndex) {
        detailOpen = false
        laneMemory = ({})
        cellLane = 2 + laneIndex
        cellRow = 12
        const S = springs
        S.lift.v = 0.4; S.lift.vel = 0
        S.shoulder.v = cellRow; S.shoulder.vel = 0
        S.focus.v = cellLane; S.focus.vel = 0
        S.track.v = (cellLane - 2) * columnSpacing; S.track.vel = 0
        S.rail.v = -2.17 - (cellRow - 15.5) * rowSpacing; S.rail.vel = 0
        pulses = []
        updatePulses()
        detail = 0; clarity = 0; idleGain = 0
        hoverCell = null; hoverLifts = ({})
        lastInteraction = clock
        snapCamera = true
        rebuild()
    }
    // 后台预渲染：把镜头放到阵列取景位置画一帧（否则镜头朝向空处，阵列的着色器与管线不会被编译），
    // 再让选中的那盒以半透明渐显状态画一帧，切换时的渐显管线也提前就绪
    function prime() {
        reset(0)
        step(0.016)
        primeBlend.restart()
    }
    Timer { id: primeBlend; interval: 300; onTriggered: if (!root.active && root.blendParts.length) { root.applyAppearance(0.5); primeRestore.restart() } }
    Timer { id: primeRestore; interval: 300; onTriggered: { root.appearance = -1; root.applyAppearance(1) } }
    function flyIn() { fly = 0; flyDir = 1; running = true }
    function flyOut() { if (fly > 1.7) fly = 1.7; flyDir = -1; detailOpen = false; running = true }

    function nav(axis, d) {
        if (detailOpen || flyDir !== 0) return
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
        if (detailOpen || flyDir !== 0) return
        dir = l > cellLane || (l === cellLane && r > cellRow) ? 1 : -1
        lastInteraction = clock
        cellLane = l; cellRow = r
        changed()
    }
    function changed() {
        springs.lift.v = 0; springs.lift.vel = 0
        const p = pulses.slice(-5); p.push({ lane: cellLane, row: cellRow, time: clock }); pulses = p
        updatePulses()
        rebuild()
        moved(lane, row)
        running = true
    }
    function updatePulses() {
        const v = []
        for (let i = 0; i < 6; i++) {
            const p = pulses[i]
            v.push(p && Theme.richMotion ? Qt.vector4d(p.lane, p.row, p.time, 1) : Qt.vector4d(0, 0, 0, 0))
        }
        pulseVecs = v
    }
    function open() { if (detailOpen || flyDir !== 0) return; detailOpen = true; running = true; opened(lane, row) }
    function close() { if (!detailOpen) return; detailOpen = false; running = true; closed() }

    // ── 3D 场景 ────────────────────────────────────────────────────────────
    View3D {
        id: view
        anchors.fill: parent
        environment: ExtendedSceneEnvironment {
            backgroundMode: SceneEnvironment.Color
            clearColor: Theme.dark ? "#11181b" : "#eae5e1"
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.VeryHigh
            tonemapMode: SceneEnvironment.TonemapModeAces
            exposure: 1.05
            // 环境光照：演示基线的 RoomEnvironment（强度 0.48）+ 半球光，烘成一张 HDR（qt/tools/make_room_env.py）
            // Qt 的透射采样比 three.js 清晰（不按粗糙度模糊），透出的内层更深：环境光略提、透射降到 0.3，与演示截图逐区对齐
            probeExposure: 1.3
            lightProbe: Texture { source: Qt.resolvedUrl("../assets3d/room-env.hdr"); mappingMode: Texture.LightProbe }
            fog: Fog {
                enabled: true
                color: Theme.dark ? "#11181b" : "#eae5e1"
                depthEnabled: true
                depthNear: root.fogNear
                depthFar: root.fogFar
                depthCurve: 1
            }
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
        // 主光（投影）与补光：位置、颜色同演示基线；three.js 的光强含 1/π，Qt 不含，按 强度/π 换算
        DirectionalLight {
            id: key
            color: "#fff7ed"
            brightness: 1.4 / Math.PI
            position: Qt.vector3d(-6, 14, -5)
            castsShadow: true
            shadowMapQuality: Light.ShadowMapQualityVeryHigh
            softShadowQuality: Light.PCF16
            pcfFactor: 4
            shadowFactor: 100
            shadowBias: 3
            shadowMapFar: 120
            rotation: Quaternion.lookAt(position, Qt.vector3d(0, 0, 0), Qt.vector3d(0, 0, -1), Qt.vector3d(0, 1, 0))
        }
        DirectionalLight {
            color: "#ffffff"
            brightness: 0.6 / Math.PI
            position: Qt.vector3d(7, 8, -10)
            rotation: Quaternion.lookAt(position, Qt.vector3d(0, 0, 0), Qt.vector3d(0, 0, -1), Qt.vector3d(0, 1, 0))
        }
        Model {
            source: "#Rectangle"
            position: Qt.vector3d(0, -4.63, 0)
            eulerRotation.x: -90
            scale: Qt.vector3d(4, 4, 1)
            receivesShadows: true
            materials: PrincipledMaterial { baseColor: Theme.dark ? "#1b2428" : "#d8c9b9"; roughness: 0.95 }
        }

        Node {
            id: arrayRoot
            // 阵列：同一个模型的实例化副本（实例表位置为阵列内的绝对坐标，整体随轨道平移）
            RuntimeLoader {
                id: arrayLoader
                source: Qt.resolvedUrl("../assets3d/archive-cassette.glb")
                instancing: InstanceList { id: instances }
                onStatusChanged: if (status === RuntimeLoader.Success) { root.prepare(arrayLoader, true); parseGap.start() }
            }
            // 选中的那一盒：完整材质、档案标签、程序图标唱片
            Node {
                id: selected
                RuntimeLoader {
                    id: selectedLoader
                    // 分步加载：阵列解析完、隔一小段再解析这一份，避免一次占住主线程太久
                    source: root.arrayParsed && root.allowSelected ? Qt.resolvedUrl("../assets3d/archive-cassette.glb") : ""
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
                        metalness: 0.02
                        alphaMode: PrincipledMaterial.Mask
                        alphaCutoff: 0.5
                        cullMode: Material.NoCulling
                        baseColorMap: Texture { sourceItem: discArt }
                    }
                }
            }
        }
    }

    // 阵列部件材质：波浪等在顶点着色器里算，颜色取演示基线的阵列材质
    component PartMaterial: CustomMaterial {
        shadingMode: CustomMaterial.Shaded
        cullMode: Material.NoCulling
        vertexShader: "shaders/arraypart.vert"
        fragmentShader: "shaders/arraypart.frag"
        property vector3d uColor: Qt.vector3d(1, 1, 1)
        property real uRoughness: 0.5
        property real uMetalness: 0
        property real uTransmission: 0
        property real uThickness: 0
        property vector3d uAttenuation: Qt.vector3d(1, 1, 1)
        property real uAttenuationDistance: 1e6
        property real uClearcoat: 0
        property real uClearcoatRoughness: 0
        property real uGradient: 0
        property real uTime: root.clock
        property real uShoulder: root.uShoulder
        property real uFocus: root.uFocus
        property real uIdle: root.idleGain
        property real uPulseGain: root.pulseGain
        property real uDetail: root.uDetail
        property real uFly: root.fly
        property real uCellLane: root.cellLane
        property real uCellRow: root.cellRow
        property vector4d uPulse0: root.pulseVecs[0]
        property vector4d uPulse1: root.pulseVecs[1]
        property vector4d uPulse2: root.pulseVecs[2]
        property vector4d uPulse3: root.pulseVecs[3]
        property vector4d uPulse4: root.pulseVecs[4]
        property vector4d uPulse5: root.pulseVecs[5]
        property vector4d uHover0: root.hover0
        property vector4d uHover1: root.hover1
        property vector4d uHover2: root.hover2
    }
    PartMaterial {
        id: matShell
        uColor: root.lin("#fff7ed"); uRoughness: 0.28; uTransmission: 0.3; uThickness: 0.12
        uAttenuation: root.lin("#eee6df"); uAttenuationDistance: 2; uClearcoat: 0.3; uClearcoatRoughness: 0.25; uGradient: 1
    }
    // 其余部件不透光：用不写透射的着色器，才会画进屏幕纹理、透过磨砂外壳显出来
    PartMaterial { id: matEdges; fragmentShader: "shaders/arraypart_opaque.frag"; uColor: root.lin("#fff5e9"); uRoughness: 0.38; uMetalness: 0.02 }
    PartMaterial { id: matDiffuser; fragmentShader: "shaders/arraypart_opaque.frag"; uColor: root.lin("#806447"); uRoughness: 0.7 }
    PartMaterial { id: matIndex; fragmentShader: "shaders/arraypart_opaque.frag"; uColor: root.lin("#e4d6c5"); uRoughness: 0.52; uMetalness: 0.05 }
    PartMaterial { id: matFasteners; fragmentShader: "shaders/arraypart_opaque.frag"; uColor: Qt.vector3d(0.58, 0.6, 0.61); uRoughness: 0.19; uMetalness: 0.82 }
    readonly property var arrayMaterials: ({ Frosted_Polymer: matShell, Ivory_Edges: matEdges, Optical_Diffuser: matDiffuser, Index_Inlay: matIndex, Titanium_Fasteners: matFasteners })

    // 部件按材质顺序识别（与 glTF 材质表一一对应）
    readonly property var partNames: ["Frosted_Polymer", "Ivory_Edges", "Optical_Diffuser", "Printed_Label", "Carbon_Ink", "Internal_Ceramic", "Optical_Edges",
        "Subsurface_Optics", "Optical_Film_Edge", "Amber_Optical_Inlay", "Optical_Film", "Index_Inlay", "Case_Engraving", "Case_Engraving_Highlight",
        "Titanium_Fasteners", "Moulded_Lettering", "Champagne_Index"]
    readonly property var ringParts: ["Optical_Edges", "Internal_Ceramic", "Subsurface_Optics", "Amber_Optical_Inlay", "Optical_Film", "Optical_Film_Edge"]
    property var frostedMaterial: null
    property bool arrayParsed: false
    property bool allowSelected: true       // 后台预加载时由宿主分步放行
    Timer { id: parseGap; interval: 250; onTriggered: root.arrayParsed = true }
    // 选中的那盒：抬起过程中外壳等从阵列外观过渡到完整外观，其余内部结构渐显（同演示 applyAppearance）
    property var blendParts: []
    property var fadeParts: []
    property real appearance: -1
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
        const blend = [], fade = []
        for (const m of models) {
            const name = partNames[materials.indexOf(m.materials[0])] || ""
            const mat = m.materials[0]
            m.castsShadows = name === "Optical_Diffuser"
            m.receivesShadows = true
            m.pickable = true                   // 选中的那盒也要能点中，否则点击会穿到后面的录像带上
            // 模型自带的竖排浮雕字是原作品牌（RHINE LAB），不使用
            if (name === "Carbon_Ink" || name === "Moulded_Lettering") { m.visible = false; continue }
            if (isArray) {
                const am = arrayMaterials[name]
                if (!am) { m.visible = false; continue }
                m.pickable = true
                m.objectName = "arrayPart"          // 拾取时区分阵列实例与选中的那盒（后者的 instanceIndex 也是 0）
                m.materials = [am]
                continue
            }
            if (ringParts.indexOf(name) >= 0) { m.visible = false; continue }      // 双环换成图标唱片
            if (name === "Frosted_Polymer") { mat.transmissionFactor = 0.9; mat.thicknessFactor = 0.12; mat.roughness = 0.21; mat.indexOfRefraction = 1.46; mat.attenuationColor = "#eee6df"; mat.attenuationDistance = 2; root.frostedMaterial = mat }
            if (name === "Printed_Label") mat.baseColor = "#eae5dc"
            if (name === "Ivory_Edges") { mat.roughness = 0.31; mat.transmissionFactor = 0.65; mat.thicknessFactor = 0.04 }
            if (name === "Optical_Diffuser") { mat.transmissionFactor = 0; mat.roughness = 0.7 }
            const high = { Frosted_Polymer: "#fffdfa", Ivory_Edges: "#f0e7df", Optical_Diffuser: "#e2dad4" }[name]
            const low = { Frosted_Polymer: ["#fff7ed", 0.28, 0.3], Ivory_Edges: ["#fff5e9", 0.38, 0], Optical_Diffuser: ["#806447", 0.7, 0], Index_Inlay: ["#e4d6c5", 0.52, 0], Titanium_Fasteners: null }[name]
            if (low !== undefined) {
                if (low) blend.push({ mat: mat, low: { c: Qt.color(low[0]), r: low[1], t: low[2] }, high: { c: high ? Qt.color(high) : mat.baseColor, r: mat.roughness, t: mat.transmissionFactor } })
            } else fade.push(m)
        }
        if (!isArray) { blendParts = blend; fadeParts = fade; appearance = -1 }
        running = true
        if (!active) Qt.callLater(prime)
    }
    function applyAppearance(q) {
        for (const p of blendParts) {
            const a = p.low, b = p.high
            p.mat.baseColor = Qt.rgba(a.c.r + (b.c.r - a.c.r) * q, a.c.g + (b.c.g - a.c.g) * q, a.c.b + (b.c.b - a.c.b) * q, 1)
            p.mat.roughness = a.r + (b.r - a.r) * q
            if (p.mat !== frostedMaterial) p.mat.transmissionFactor = a.t + (b.t - a.t) * q
        }
        for (const m of fadeParts) {
            m.visible = q > 0.02
            const mat = m.materials[0]
            // 渐显期间半透明；完成后恢复不透明，外壳的透射才能折射出内部结构
            mat.opacity = q > 0.995 ? 1 : q
        }
    }

    // ── 实例表：与演示基线相同的范围（左右各 3 列、前后各 18 行，约 259 盒）。
    //    以阵列「当前滑到的位置」为中心，而不是目标格：切换行列时边缘的列 / 行随阵列平移自然移出画面，
    //    滑过半格后才换下；换档或滑过整格时重建，静态起伏烘入高度供拾取。 ──
    property var entries: []
    property var drawn: []
    readonly property int maxInstances: 7 * 37
    property int builtLane: -9999
    property int builtRow: -9999
    Component { id: entryComponent; InstanceListEntry {} }
    Component.onCompleted: {
        const list = []
        for (let i = 0; i < maxInstances; i++) list.push(entryComponent.createObject(instances, { scale: Qt.vector3d(0, 0, 0) }))
        entries = list
        instances.instances = list
        rebuild()
    }
    function visualLane() { return Math.round(springs.track.v / columnSpacing) + 2 }
    function visualRow() { return Math.round(15.5 + (-2.17 - springs.rail.v) / rowSpacing) }
    function rebuild() {
        if (!entries.length) return
        const list = []
        let i = 0
        const vl = visualLane(), vr = visualRow()
        builtLane = vl; builtRow = vr
        for (let l = vl - 3; l <= vl + 3; l++) {
            for (let r = vr - 18; r <= vr + 18; r++) {
                if (l === cellLane && r === cellRow) continue
                const st = settlingWave(r - cellRow, 26.56) * columnStrength(l, cellLane)
                const e = entries[i++]
                e.position = Qt.vector3d((l - 2) * columnSpacing, -4.6 + st, (r - 15.5) * rowSpacing)
                e.customData = Qt.vector4d(l, r, st, 0)
                if (e.scale.x !== 1) e.scale = Qt.vector3d(1, 1, 1)
                list.push({ lane: l, row: r })
            }
        }
        for (; i < entries.length; i++) if (entries[i].scale.x !== 0) entries[i].scale = Qt.vector3d(0, 0, 0)
        drawn = list
    }

    // ── 每帧更新：弹簧、镜头、选中的那盒与 uniform（阵列本身在 GPU 上动） ──────
    property bool running: true
    property bool snapCamera: true
    property real fogNear: 145
    property real fogFar: 165
    property real focusDistance: 140
    readonly property vector3d baseDirection: {
        const yaw = 59 * Math.PI / 180, el = 19 * Math.PI / 180
        return Qt.vector3d(-Math.sin(yaw) * Math.cos(el), Math.sin(el), Math.cos(yaw) * Math.cos(el))
    }
    property real cameraAimX: -0.5
    property real cameraAimY: 1.1
    property real cameraAimZ: 0.4

    function field(r, l, t) {
        let ripple = 0
        if (Theme.richMotion) for (const p of pulses) ripple += selectionWave(Math.hypot(r - p.row, (l - p.lane) * 2.2), t - p.time)
        return settlingWave(r - springs.shoulder.v, 26.56) * columnStrength(l, springs.focus.v) + idleWave(r, l, t) * idleGain + Math.max(-0.6, Math.min(0.6, ripple)) * pulseGain
    }
    function stepHover(dt) {
        const hl = Object.assign({}, hoverLifts)
        const hk = hoverCell ? hoverCell.lane + ":" + hoverCell.row : ""
        if (hk && hl[hk] === undefined) hl[hk] = 0
        for (const k in hl) {
            const target = k === hk ? 0.28 : 0
            hl[k] += (target - hl[k]) * (1 - Math.exp(-dt * 14))
            if (target === 0 && hl[k] < 0.0001) delete hl[k]
        }
        hoverLifts = hl
        const hv = Object.keys(hl).slice(-3).map(k => { const s = k.split(":"); return Qt.vector4d(+s[0], +s[1], hl[k], 0) })
        while (hv.length < 3) hv.push(Qt.vector4d(0, 0, 0, 0))
        hover0 = hv[0]; hover1 = hv[1]; hover2 = hv[2]
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
        if (pulses.length && t - pulses[0].time > 3.2) { pulses = pulses.filter(p => t - p.time < 3.2); updatePulses() }
        const idle = Theme.richMotion && !detailOpen && detail < 0.01 && t - lastInteraction > 2.5
        idleGain += ((idle ? 1 : 0) - idleGain) * (1 - Math.exp(-dt * (idle ? 0.8 : 4)))
        pulseGain += ((detailOpen ? 0 : 1) - pulseGain) * (1 - Math.exp(-dt * 8))
        // 飞入 / 飞出
        if (flyDir > 0) { fly += dt; if (fly >= 1.7) { fly = 2; flyDir = 0 } }
        else if (flyDir < 0) { fly -= dt * 1.8; if (fly <= 0) { fly = 0; flyDir = 0; flownOut() } }
        // 悬停抬起（最多三格同时在变化；没有悬停时跳过，不产生临时对象）
        if (hoverCell || Object.keys(hoverLifts).length) stepHover(dt)
        damp(S.lift, detailOpen ? inspectionLift : 0.4, Theme.richMotion ? 4.2 : 35, dt)
        const camTarget = detailOpen ? ease((S.lift.v - 0.8) / 2.4) : ease((S.lift.v - 0.4) / (inspectionLift - 0.4))
        detail += (camTarget - detail) * (1 - Math.exp(-dt * (Theme.richMotion ? 2.8 : 35)))
        const clearTarget = detailOpen && detail > 0.78 && S.lift.v > 3.3
        clarity = clearTarget ? Math.min(1, clarity + dt / 1.6) : Math.max(0, clarity - dt * 4)
        if (frostedMaterial) {
            const c = ease(clarity)
            frostedMaterial.transmissionFactor = 0.9 + (0.985 - 0.9) * c
            frostedMaterial.thicknessFactor = 0.12 + (0.018 - 0.12) * c
            frostedMaterial.attenuationDistance = 2 + (8 - 2) * c
            frostedMaterial.roughness = 0.21 + (0.025 - 0.21) * c
        }
        uShoulder = S.shoulder.v; uFocus = S.focus.v; uDetail = detail
        if (visualLane() !== builtLane || visualRow() !== builtRow) rebuild()
        const trackX = S.track.v, rail = S.rail.v
        arrayRoot.position = Qt.vector3d(-trackX, 0, rail)
        const q = ease(S.lift.v / 0.4)
        if (Math.abs(q - appearance) > 0.002) { appearance = q; applyAppearance(q) }
        const hover = hoverLifts[cellLane + ":" + cellRow] || 0
        // 与着色器里的飞入同一条路径：沿长边从右上方斜向滑入
        const fp = Math.max(0, Math.min(1, fly / 0.9)), fe = 1 - Math.pow(1 - fp, 3)
        const selY = -4.6 + field(cellRow, cellLane, t) + S.lift.v + hover + 1.5 * (1 - fe)
        selected.position = Qt.vector3d(chosenX + 26 * (1 - fe), selY, chosenZ)
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
        let detailAim = Qt.vector3d(chosenX - trackX, selY, chosenZ + rail).plus(Qt.vector3d(0, 1.85, 0))
        detailAim = detailAim.plus(right.times((0.5 - 550 / 1920) * 1920 / pixelScale)).plus(up.times((560 / 1080 - 0.5) * 1080 / pixelScale))
        const arrayAim = Qt.vector3d(-1.091, -0.045, 0.481)
        const aim = arrayAim.times(1 - detail).plus(detailAim.times(detail))
        const camPos = aim.plus(d.times(distance))
        const blend = snapCamera ? 1 : 1 - Math.exp(-dt * 5)
        snapCamera = false
        camera.position = camera.position.times(1 - blend).plus(camPos.times(blend))
        cameraAimX += (aim.x - cameraAimX) * blend; cameraAimY += (aim.y - cameraAimY) * blend; cameraAimZ += (aim.z - cameraAimZ) * blend
        camera.lookAt(Qt.vector3d(cameraAimX, cameraAimY, cameraAimZ))
        const fov = 2 * Math.atan(span / (2 * distance)) * 180 / Math.PI
        camera.fieldOfView += (fov - camera.fieldOfView) * blend
        const rendered = camera.position.minus(Qt.vector3d(cameraAimX, cameraAimY, cameraAimZ)).length()
        fogNear = rendered + 1 + (-1 - 1) * detail
        fogFar = rendered + 13 + (12 - 13) * detail
        focusDistance = rendered

        const moving = Math.abs(S.lift.vel) > 1e-4 || Math.abs(detail - camTarget) > 1e-3 || pulses.length > 0 || Math.abs(S.rail.vel) > 1e-4
            || Math.abs(S.track.vel) > 1e-4 || Math.abs(S.shoulder.vel) > 1e-4 || Object.keys(hoverLifts).length > 0 || flyDir !== 0
            || (clearTarget ? clarity < 1 : clarity > 0) || camera.position.minus(camPos).length() > 0.01
        // 空闲呼吸按显示器刷新率逐帧推进（画面优先；每帧只有少量 uniform，CPU 开销很小）
        return moving || idleGain > 0.001 || idle
    }
    FrameAnimation {
        running: root.active && root.running
        onTriggered: { if (!root.step(Math.min(0.05, frameTime))) root.running = false }
    }
    // 停止操作 2.5 秒后进入呼吸：唤醒逐帧更新
    Timer {
        interval: 2000
        repeat: true
        running: root.active && !root.running && !root.detailOpen && Theme.richMotion
        // 停止更新时时钟不走：把「上次操作」往前推，等价于计时
        onTriggered: { root.lastInteraction -= interval / 1000; if (root.clock - root.lastInteraction > 2.4) root.running = true }
    }

    // ── 拾取 ──────────────────────────────────────────────────────────────
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        enabled: !root.detailOpen && root.flyDir === 0
        function cellAt(x, y) {
            const r = view.pick(x, y)
            if (!r.objectHit) return null
            if (r.objectHit.objectName === "arrayPart") return r.instanceIndex >= 0 && r.instanceIndex < root.drawn.length ? root.drawn[r.instanceIndex] : null
            return { lane: root.cellLane, row: root.cellRow }
        }
        onPositionChanged: mouse => {
            const c = cellAt(mouse.x, mouse.y)
            const h = c && !(c.lane === root.cellLane && c.row === root.cellRow) ? c : null
            const same = (a, b) => a && b && a.lane === b.lane && a.row === b.row
            if (!same(h, root.hoverCell) && (h || root.hoverCell)) { root.hoverCell = h; root.lastInteraction = root.clock; root.running = true }
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
            Text { x: 25; y: 140; text: root.isQueue ? "QUEUE DISPATCH" : "SCRIPT CUSTODY"; color: "#878476"; font.family: Theme.font; font.pixelSize: 32 }
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
            IconDisc { anchors.fill: parent; path: root.rowIcon || "AUTO-MAS" }     // 无启动程序时由图标提供器给出档案章占位
            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 352
                spacing: 4
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: root.rowIcon ? root.rowIcon.split(/[\\/]/).pop() : "AUTO-MAS"
                    color: Qt.rgba(0.12, 0.12, 0.1, 0.82); font.family: Theme.font; font.pixelSize: 26; font.bold: true
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: root.row === 0 ? (root.column ? root.column.name : "") : root.rowName + " · " + (root.column ? root.column.name : "")
                    color: Qt.rgba(0.12, 0.12, 0.1, 0.55); font.family: Theme.font; font.pixelSize: 15
                }
            }
        }
    }

    // ── 界面（原项目的档案选择版式） ──────────────────────────────────────
    Item {
        anchors.fill: parent
        opacity: (root.detailOpen ? 0 : 1) * Math.max(0, Math.min(1, (root.fly - 0.5) / 0.6))
        visible: opacity > 0

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
                RollText { text: root.rowName; dir: root.dir; color: Theme.ink; font.family: Theme.font; font.pixelSize: 16 }
                Text { anchors.right: parent.right; text: root.row === 0 ? (root.isQueue ? "QUEUE CONFIG" : "SCRIPT CONFIG") : (root.isQueue ? "QUEUE ITEM" : "ACCOUNT"); color: "#666257"; font.family: Theme.font; font.pixelSize: 11; font.letterSpacing: 1 }
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
                // 刻度最多 12 格：行数多时以当前行为中心滑动显示
                readonly property int first: root.rowCount <= 12 ? 0 : Math.max(0, Math.min(root.rowCount - 12, root.row - 6))
                Repeater {
                    model: Math.min(root.rowCount, 12)
                    Item {
                        required property int index
                        readonly property int r: parent.first + index
                        width: 14; height: 40
                        Rectangle { x: 6; width: 2; anchors.verticalCenter: parent.verticalCenter; height: parent.r === root.row ? 33 : 12; color: parent.r === root.row ? "#24261f" : "#aaa59a"
                            Behavior on height { NumberAnimation { duration: 400 } } }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.goCell(root.cellLane, root.cellRow + parent.r - root.row) }
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
            text: (root.isQueue ? "←  →  切换队列" : "←  →  切换脚本") + "    ／    ↑  ↓  前后档案    ／    ENTER  读取"
            color: "#858077"; font.family: Theme.font; font.pixelSize: 10; font.letterSpacing: 0.9
        }
    }
}
