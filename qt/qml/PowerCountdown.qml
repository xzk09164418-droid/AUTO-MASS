import QtQuick
import "SectionData.js" as SD
import "."

// 电源操作倒计时（与网页版 GlobalPowerCountdown 相同）：任务完成后准备关机 / 睡眠等时弹出，
// 可在倒计时结束前取消。平时不显示；每 2 秒查询一次后端快照。
Item {
    id: pc
    property var api: null
    property bool active: false
    property string operation: ""
    property int remaining: 0
    property bool cancelling: false
    readonly property var names: ({ NoAction: "无动作", KillSelf: "退出 AUTO-MAS", RestartSelf: "重启 AUTO-MAS", Sleep: "睡眠", Hibernate: "休眠", Logoff: "注销", Shutdown: "关机", ShutdownForce: "强制关机", Reboot: "重启" })
    anchors.fill: parent
    visible: active
    z: 90

    function poll() {
        if (!api) { active = false; return }
        api.get("/api/dispatch/power/countdown-snapshot", text => {
            let r = null
            try { r = JSON.parse(text) } catch (e) {}
            if (!r) return
            active = !!r.active
            operation = r.operation || ""
            remaining = r.remaining || 0
        })
    }
    Timer { interval: 2000; repeat: true; running: !!pc.api; triggeredOnStart: true; onTriggered: pc.poll() }
    // 两次查询之间本地递减，读数连续
    Timer { interval: 1000; repeat: true; running: pc.active && pc.remaining > 0; onTriggered: pc.remaining = Math.max(0, pc.remaining - 1) }
    function cancel() {
        if (!api || cancelling) return
        cancelling = true
        api.request("/api/dispatch/cancel/power", "{}", text => {
            cancelling = false
            active = false
            poll()
        })
    }

    Rectangle { anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.5) }
    MouseArea { anchors.fill: parent }
    Rectangle {
        anchors.centerIn: parent
        width: 600; height: 300
        color: Theme.paper
        border.width: 1.5; border.color: Theme.ink
        Rectangle { width: parent.width; height: 4; color: Theme.accent }
        Column {
            x: 36; y: 34; width: parent.width - 72; spacing: 12
            Text { text: "即将" + (pc.names[pc.operation] || pc.operation || "执行电源操作"); color: Theme.ink; font.family: Theme.font; font.pixelSize: 24; font.weight: Font.Bold; font.letterSpacing: 2 }
            Text { text: "任务已完成，倒计时结束后执行。需要继续使用电脑时请取消。"; color: Theme.muted; font.family: Theme.font; font.pixelSize: 14 }
            Row {
                spacing: 10
                Text { text: String(pc.remaining); color: Theme.accent; font.family: Theme.font; font.pixelSize: 64; font.weight: Font.Light }
                Text { anchors.baseline: parent.children[0].baseline; text: "秒"; color: Theme.muted; font.family: Theme.font; font.pixelSize: 18 }
            }
        }
        Rectangle {
            anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 28
            width: 140; height: 44
            color: cancelMouse.containsMouse ? Theme.accent : Theme.ink
            Text { anchors.centerIn: parent; text: pc.cancelling ? "正在取消…" : "取消"; color: Theme.paper; font.family: Theme.font; font.pixelSize: 16; font.weight: Font.Bold; font.letterSpacing: 2 }
            MouseArea { id: cancelMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pc.cancel() }
        }
    }
}
