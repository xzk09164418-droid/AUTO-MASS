import QtQuick
import "."

// 热键录制（与网页版 useHotkeyCapture 同规则）：开始时请后端暂停 MAS 热键，按下组合键、全部松开后完成；
// Esc 取消，25 秒超时。存储格式为「修饰键+主键」，修饰键按 Ctrl、Win、Alt、Shift 排序、最多两个；
// 不带修饰键时只接受 F 功能键。
FocusScope {
    id: rec
    property var host                    // SectionView：call()
    property var done: null              // function(value)
    property string token: ""
    property string preview: ""
    property string error: ""
    property var held: ({})
    property var keys: []
    property bool invalid: false
    // 老板键（模拟器）：沿用网页版格式，修饰键按 Ctrl、Shift、Alt、Meta 排序，不限制必须带修饰键
    property bool bossMode: false
    readonly property bool active: visible
    visible: false
    anchors.fill: parent
    z: 60

    readonly property var modifiers: ["Ctrl", "Win", "Alt", "Shift"]
    function begin(callback) {
        done = callback; preview = ""; error = ""; held = ({}); keys = []; invalid = false; token = ""
        visible = true
        forceActiveFocus()
        timeout.restart()
        host.call("/api/dispatch/hotkey/capture", { action: "begin" }, r => {
            if (r.code === 200 && r.data && r.data.token) token = r.data.token
            else { error = r.message || "无法暂停现有热键"; }
        })
    }
    function finish(value) {
        timeout.stop()
        if (token) host.call("/api/dispatch/hotkey/capture", { action: "end", token: token }, () => {})
        token = ""
        visible = false
        if (value && done) done(value)
        done = null
    }
    Timer { id: timeout; interval: 25000; onTriggered: rec.finish("") }

    function primaryName(event) {
        const k = event.key, pad = (event.modifiers & Qt.KeypadModifier) !== 0
        if (k >= Qt.Key_A && k <= Qt.Key_Z) return String.fromCharCode(65 + k - Qt.Key_A)
        if (k >= Qt.Key_0 && k <= Qt.Key_9) return (pad ? "Numpad" : "") + String(k - Qt.Key_0)
        if (k >= Qt.Key_F1 && k <= Qt.Key_F24) return "F" + (k - Qt.Key_F1 + 1)
        if (pad) {
            const padMap = {}
            padMap[Qt.Key_Plus] = "NumpadAdd"; padMap[Qt.Key_Minus] = "NumpadSubtract"; padMap[Qt.Key_Asterisk] = "NumpadMultiply"
            padMap[Qt.Key_Slash] = "NumpadDivide"; padMap[Qt.Key_Period] = "NumpadDecimal"; padMap[Qt.Key_Enter] = "Enter"
            if (padMap[k]) return padMap[k]
        }
        const m = {}
        m[Qt.Key_Space] = "Space"; m[Qt.Key_Return] = "Enter"; m[Qt.Key_Enter] = "Enter"; m[Qt.Key_Tab] = "Tab"; m[Qt.Key_Backspace] = "Backspace"
        m[Qt.Key_Delete] = "Delete"; m[Qt.Key_Insert] = "Insert"; m[Qt.Key_Home] = "Home"; m[Qt.Key_End] = "End"; m[Qt.Key_PageUp] = "PageUp"
        m[Qt.Key_PageDown] = "PageDown"; m[Qt.Key_Left] = "Left"; m[Qt.Key_Right] = "Right"; m[Qt.Key_Up] = "Up"; m[Qt.Key_Down] = "Down"
        m[Qt.Key_CapsLock] = "CapsLock"; m[Qt.Key_Pause] = "Pause"; m[Qt.Key_Print] = "PrintScreen"; m[Qt.Key_NumLock] = "NumLock"
        m[Qt.Key_ScrollLock] = "ScrollLock"; m[Qt.Key_Minus] = "Minus"; m[Qt.Key_Equal] = "Equals"; m[Qt.Key_Comma] = "Comma"; m[Qt.Key_Period] = "Period"
        m[Qt.Key_Slash] = "Slash"; m[Qt.Key_Backslash] = "Backslash"; m[Qt.Key_Semicolon] = "Semicolon"; m[Qt.Key_Apostrophe] = "Quote"
        m[Qt.Key_BracketLeft] = "BracketLeft"; m[Qt.Key_BracketRight] = "BracketRight"; m[Qt.Key_QuoteLeft] = "Grave"
        return m[k] || ""
    }
    function isModifierKey(k) { return k === Qt.Key_Control || k === Qt.Key_Meta || k === Qt.Key_Alt || k === Qt.Key_Shift || k === Qt.Key_Super_L || k === Qt.Key_Super_R }
    Keys.onPressed: event => {
        event.accepted = true
        if (event.key === Qt.Key_Escape) { finish(""); return }
        if (event.isAutoRepeat) return
        const h = Object.assign({}, held); h[event.key] = true; held = h
        const set = keys.slice()
        const flags = [event.modifiers & Qt.ControlModifier, event.modifiers & Qt.MetaModifier, event.modifiers & Qt.AltModifier, event.modifiers & Qt.ShiftModifier]
        modifiers.forEach((name, i) => { if (flags[i] && set.indexOf(name) < 0) set.push(name) })
        if (event.key === Qt.Key_Control && set.indexOf("Ctrl") < 0) set.push("Ctrl")
        if ((event.key === Qt.Key_Meta || event.key === Qt.Key_Super_L || event.key === Qt.Key_Super_R) && set.indexOf("Win") < 0) set.push("Win")
        if (event.key === Qt.Key_Alt && set.indexOf("Alt") < 0) set.push("Alt")
        if (event.key === Qt.Key_Shift && set.indexOf("Shift") < 0) set.push("Shift")
        if (!isModifierKey(event.key)) {
            const p = primaryName(event)
            if (p) { if (set.indexOf(p) < 0) set.push(p) } else invalid = true
        }
        keys = set
        preview = set.join("+")
    }
    Keys.onReleased: event => {
        event.accepted = true
        if (event.isAutoRepeat) return
        const h = Object.assign({}, held); delete h[event.key]; held = h
        if (Object.keys(held).length) return
        const mods = modifiers.filter(m => keys.indexOf(m) >= 0)
        const primary = keys.filter(k => modifiers.indexOf(k) < 0)
        if (!keys.length) return
        if (bossMode) {
            const order = ["Ctrl", "Shift", "Alt", "Win"]
            const bm = order.filter(m => keys.indexOf(m) >= 0).map(m => m === "Win" ? "Meta" : m)
            if (primary.length !== 1) { error = "请按下修饰键加一个普通键"; keys = []; preview = ""; return }
            finish(bm.concat(primary).join("+"))
            return
        }
        if (invalid || primary.length !== 1 || mods.length > 2 || (!mods.length && !/^F\d+$/.test(primary[0]))) {
            error = "请录制修饰键加一个普通键，或单独功能键；不支持多个普通键"
            keys = []; invalid = false; preview = ""
            return
        }
        finish(mods.concat(primary).join("+"))
    }

    Rectangle { anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.45) }
    MouseArea { anchors.fill: parent; onClicked: rec.finish("") }
    Rectangle {
        anchors.centerIn: parent
        width: 560; height: 240
        color: Theme.paper
        border.width: 1.5; border.color: Theme.ink
        Rectangle { width: parent.width; height: 4; color: Theme.accent }
        Column {
            x: 32; y: 30; width: parent.width - 64; spacing: 14
            Text { text: "录制热键"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 22; font.weight: Font.Bold; font.letterSpacing: 2 }
            Text { width: parent.width; wrapMode: Text.Wrap; text: rec.token ? "请按下组合键，全部松开后完成（Esc 取消，25 秒超时）。" : "正在暂停现有热键，请稍候…"; color: Theme.muted; font.family: Theme.font; font.pixelSize: 14 }
            Text { text: rec.preview || "—"; color: Theme.ink; font.family: "Consolas"; font.pixelSize: 26 }
            Text { visible: !!rec.error; width: parent.width; wrapMode: Text.Wrap; text: rec.error; color: Theme.error; font.family: Theme.font; font.pixelSize: 13 }
        }
    }
}
