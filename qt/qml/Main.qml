import QtQuick
import QtQuick.Window
import "."

// 外壳：1920×1080 参考舞台按窗口等比缩放；启动动画 → 部门索引 → 二级界面。
// 后端在启动动画播放期间并行拉起，动画结束仍未就绪时由 BackendPanel 接管。
Window {
    id: root

    property var backend: null
    property bool skipBoot: false
    property bool backendEnabled: true
    property int initialSection: 0
    property int returnAfter: 0             // 自检：进入二级界面 N 毫秒后自动返回
    property string themeMode: "system"
    property string motionMode: "standard"
    property var enhanced: null             // EnhancedComponent：3D 增强组件（可选安装）
    property real simulateLoad: 0           // >0：按真实阶段模拟一次耗时 N 秒的后端启动
    property bool booted: false

    width: 1600
    height: 900
    // 1080p 屏 200% 缩放时逻辑分辨率只有 960×540，最小尺寸不能超过它
    minimumWidth: 960
    minimumHeight: 540
    visible: true
    title: "AUTO-MAS"
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
        if (skipBoot) finishBoot()
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

        // 增强挡位的 3D 档案阵列：托管管理与调度队列共用一份常驻实例。
        // 启动完成、程序空闲后异步预加载，并在索引之下先渲染约一秒，让模型、着色器与管线提前就绪，进入时不再卡顿。
        Item {
            id: arrayHost
            anchors.fill: parent
            readonly property bool wanted: Theme.motion === "enhanced" && Theme.enhancedAvailable
            readonly property bool showing: sections.arrayMode && sections.busy
            property bool warming: false
            property bool preloaded: false
            // 索引显示期间也留在索引之下（被不透明的索引底色挡住）：3D 画面静止时不重绘，几乎不占资源，
            // 但渲染目标与管线保持就绪，点开托管管理 / 调度队列时不再卡一下
            readonly property bool parked: preloaded && !sections.busy
            z: showing ? 0 : -1
            visible: (showing || warming || parked) && arrayLoader.status === Loader.Ready
            Loader {
                id: arrayLoader
                anchors.fill: parent
                asynchronous: true
                active: arrayHost.wanted && (arrayHost.preloaded || arrayHost.showing)
                source: active ? Qt.resolvedUrl("ArchiveArray3D.qml") : ""
                onLoaded: {
                    if (root.enhanced) root.enhanced.markLoaded()
                    item.enabled = Qt.binding(() => arrayHost.showing)
                    arrayHost.warming = true
                    warmTimer.restart()
                }
            }
            Timer { id: warmTimer; interval: 1200; onTriggered: arrayHost.warming = false }
            Timer {
                interval: 1500
                running: root.booted && arrayHost.wanted && !arrayHost.preloaded
                onTriggered: arrayHost.preloaded = true
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
            api: root.backendEnabled && root.backend && root.backend.status === "ready" ? root.backend : null
            onClosed: hub.focusCurrent()
        }

        BootSequence {
            id: bootSeq
            anchors.fill: parent
            visible: !root.booted
            running: !root.skipBoot
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
}
