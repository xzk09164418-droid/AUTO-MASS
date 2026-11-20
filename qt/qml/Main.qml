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
    property string themeMode: "system"
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
        if (skipBoot) finishBoot()
    }

    function finishBoot() {
        if (booted) return
        // 后端就绪即收尾的情况下，索引也快速入场，不再让用户等动画（须在 booted 之前设定）
        if (bootSeq.exiting || skipBoot) hub.introMs = 700
        booted = true
        if (initialSection >= 1 && initialSection <= 10)
            Qt.callLater(() => hub.open(initialSection - 1))
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
            anchors.fill: parent
            focus: true
            active: root.booted
            paused: sections.busy
            backendStatus: root.source ? root.source.status : ""
            onOpenRequested: (i, r) => sections.open(i, r)
        }

        SectionHost {
            id: sections
            anchors.fill: parent
            departments: hub.departments
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
