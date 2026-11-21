import QtQuick
import QtQuick.Window
import "."

// 外壳：1920×1080 参考舞台按窗口等比缩放；启动动画 → 部门索引 → 二级界面。
// 后端在启动动画播放期间并行拉起，动画结束仍未就绪时由 BackendPanel 接管。
Window {
    id: root

    property var backend: null
    property var client: null
    property bool skipBoot: false
    property bool backendEnabled: true
    property int initialSection: 0
    property int returnAfter: 0             // 自检：进入二级界面 N 毫秒后自动返回
    property string themeMode: "system"
    property string motionMode: "standard"
    property var enhanced: null             // EnhancedComponent：3D 增强组件（可选安装）
    property real simulateLoad: 0           // >0：按真实阶段模拟一次耗时 N 秒的后端启动
    property bool booted: false
    // --skip-boot 只在后端已就绪时直接跳过；后端还在启动时仍由启动动画的授权段承接等待（显示实时进度），就绪后快速收尾
    property bool bootHold: false

    property var uiOptions: ({})
    flags: Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowMinMaxButtonsHint
        | (uiOptions.IfHideCloseButton ? Qt.CustomizeWindowHint : Qt.WindowCloseButtonHint)
    onClosing: event => {
        if (client) { event.accepted = false; client.close_window() }
    }

    width: 1600
    height: 900
    // 1080p 屏 200% 缩放时逻辑分辨率只有 960×540，最小尺寸不能超过它
    minimumWidth: 960
    minimumHeight: 540
    visible: true
    title: "AUTO-MASS"
    color: Theme.bg

    // 启动进度的数据源：真实后端 / 模拟后端 / 无（离线预览）
    readonly property var source: simulateLoad > 0 ? sim : (backendEnabled ? backend : null)

    QtObject {
        id: sim
        property string status: "starting"
        property real progress: 0.03
        property string stage: "连接后端"
        property real t: 0
        // [时间占比, 进度, 阶段]：与 BackendSupervisor 的真实阶段一致
        readonly property var plan: [
            [0.00, 0.03, "连接后端"], [0.04, 0.08, "启动后端进程"], [0.12, 0.15, "加载配置"],
            [0.25, 0.40, "核心服务就绪"], [0.36, 0.479, "初始化：本地远程桌面分身"],
            [0.48, 0.557, "初始化：桌面显示输出守卫"], [0.55, 0.636, "初始化：全局热键服务"],
            [0.66, 0.714, "初始化：通知渠道"], [0.80, 0.793, "初始化：主业务定时器"],
            [0.88, 0.871, "初始化：启动参数直接运行任务"], [0.96, 0.95, "初始化：MCP 服务挂载"],
            [1.00, 1.0, "就绪"]
        ]
    }
    Timer {
        interval: 100
        repeat: true
        running: root.simulateLoad > 0 && sim.status !== "ready"
        onTriggered: {
            sim.t += 0.1
            const f = sim.t / root.simulateLoad
            let cur = sim.plan[0]
            for (const p of sim.plan) if (f >= p[0]) cur = p
            sim.progress = cur[1]
            sim.stage = cur[2]
            if (f >= 1) sim.status = "ready"
        }
    }

    Component.onCompleted: {
        Theme.mode = themeMode
        Theme.enhancedAvailable = !!enhanced && enhanced.installed
        Theme.motion = motionMode === "enhanced" && !Theme.enhancedAvailable ? "standard" : motionMode
        Theme.motionHandled = true
        if (skipBoot) {
            if (!source || source.status === "ready") finishBoot()
            else { bootHold = true; bootSeq.clockBase = 0; bootSeq.frame = bootSeq.holdFrame }
        }
    }

    function finishBoot() {
        if (booted) return
        // 后端就绪即收尾的情况下，索引也快速入场，不再让用户等动画（须在 booted 之前设定）
        if (bootSeq.exiting || skipBoot) hub.introMs = 700
        booted = true
        if (initialSection >= 1 && initialSection <= 10)
            Qt.callLater(() => {
                hub.open(initialSection - 1)
                if (returnAfter > 0) returnTimer.start()
            })
        else
            hub.forceActiveFocus()
    }

    Item {
        id: stage
        width: 1920
        height: 1080
        anchors.centerIn: parent
        scale: Math.min(root.width / 1920, root.height / 1080)
        clip: true

        Item {
        id: scene
        anchors.fill: parent
        DepartmentHub {
            id: hub
            objectName: "hub"
            anchors.fill: parent
            focus: true
            active: root.booted
            paused: sections.busy
            sectioned: sections.busy && !sections.returning
            backendStatus: root.source ? root.source.status : ""
            onOpenRequested: (i, r) => sections.open(i, r, hub.tileItem(i))
        }

        // 各部门共享场景；首次加载后在索引背后短暂预渲染。
        Item {
            id: arrayHost
            anchors.fill: parent
            readonly property bool wanted: Theme.motion === "enhanced" && Theme.enhancedAvailable
            readonly property bool showing: sections.arrayMode && sections.busy
            // 组件异步孵化。预过滤光照与预转换网格可直接上传，索引下预热的场景随后复用。
            readonly property bool ready: arrayLoader.status === Loader.Ready
            z: showing ? 0 : -1
            visible: ready && (showing || (wanted && warmup.running))
            Timer { id: warmup; interval: 500 }
            Loader {
                id: arrayLoader
                anchors.fill: parent
                asynchronous: true
                // 首次使用增强后，标准挡位停放同一场景；减少挡位释放它。
                property bool loadedOnce: false
                active: arrayHost.wanted || (loadedOnce && Theme.motion === "standard" && Theme.enhancedAvailable)
                source: "ArchiveArray3D.qml"
                onLoaded: {
                    loadedOnce = true
                    if (root.enhanced) root.enhanced.markLoaded()
                    item.viewportScale = Qt.binding(() => stage.scale)
                    item.enabled = Qt.binding(() => arrayHost.showing)
                    // 只在显示时逐帧推进；预渲染与停靠期间画面静止，不占用 CPU
                    item.active = Qt.binding(() => arrayHost.showing)
                    if (!arrayHost.showing) { warmup.restart(); item.prime() }
                }
            }
        }

        SectionView {
            objectName: "sections"
            id: sections
            anchors.fill: parent
            departments: hub.departments
            hub: hub
            enhanced: root.enhanced
            arrayHostItem: arrayLoader.status === Loader.Ready ? arrayLoader.item : null
            onlineHome: root.backendEnabled
            api: root.backendEnabled && root.backend && root.backend.status === "ready" ? root.backend : null
            onUiSettings: patch => root.uiOptions = Object.assign({},root.uiOptions,patch)
            onClosed: hub.focusCurrent()
        }
        }

        // ── 动态效果挡位切换（标准 ↔ 增强）：定格当前画面 → 切换 → 等新画面就绪 → 斜线扫过、定格模糊退去 ──
        MotionShift {
            id: motionShift
            anchors.fill: parent
            z: 50
            sceneItem: scene
            sectionView: sections
        }

        BootSequence {
            id: bootSeq
            anchors.fill: parent
            visible: !root.booted
            running: !root.skipBoot || root.bootHold
            // 有后端（或模拟后端）时，加载到 100% 立即收尾；离线预览仍完整播放
            quickExitOnReady: root.source !== null
            // 后端未就绪时停在授权段；出错也放行，交给 BackendPanel 呈现
            backendReady: !root.source || root.source.status === "ready" || root.source.status === "error"
            backendProgress: root.source ? root.source.progress : 1
            backendStage: root.source ? root.source.stage : "OFFLINE PREVIEW"
            onFinished: root.finishBoot()
        }
    }

    Connections {
        target: Theme
        function onMotionRequested(next) { motionShift.run(next) }
        function onMotionChanged() { if (Theme.motion === "reduced") arrayLoader.loadedOnce = false }
        function onEnhancedAvailableChanged() { if (!Theme.enhancedAvailable) arrayLoader.loadedOnce = false }
    }

    Connections {
        target: root.enhanced
        function onChanged() { Theme.enhancedAvailable = root.enhanced.installed }
    }

    Timer { id: returnTimer; interval: root.returnAfter; onTriggered: sections.close() }

    // 上次运行离开了增强挡位：本次启动加载完毕、空闲 8 秒后在后台删除 3D 组件文件（本次未加载 3D 才执行）
    Timer {
        interval: 8000
        running: root.booted && !!root.enhanced && root.enhanced.state === "pending-remove" && Theme.motion !== "enhanced"
        onTriggered: root.enhanced.cleanupPending()
    }

    Shortcut {
        sequences: ["Esc", "Space"]
        enabled: !root.booted
        onActivated: bootSeq.skip()
    }

    BackendPanel {
        anchors.fill: parent
        backend: root.backendEnabled && root.booted ? root.backend : null
    }

    // 电源操作倒计时：只在后端准备关机 / 睡眠等时出现，可取消
    PowerCountdown {
        api: root.backendEnabled && root.booted && root.backend && root.backend.status === "ready" ? root.backend : null
    }
}
