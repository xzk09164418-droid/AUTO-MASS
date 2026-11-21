pragma Singleton
import QtQuick

// PV 色板的唯一来源。mode: system | light | dark
QtObject {
    id: theme

    property string mode: "system"
    // 动态效果挡位：reduced 减少（直接替换、无解密 / 呼吸 / 抽出）· standard 标准 · enhanced 增强（预留给 3D 档案）
    property string motion: "standard"
    readonly property bool richMotion: motion !== "reduced"
    // 运行中切换挡位走这里：Main 先定格画面，再切换并播放过渡；没有接收方时直接切换
    signal motionRequested(string next)
    property bool motionHandled: false
    function requestMotion(next) {
        if (next === motion) return
        if (motionHandled) motionRequested(next)
        else motion = next
    }
    // 3D 增强组件（Qt Quick 3D + 档案模型）为可选安装：未安装时不能选增强挡位
    property bool enhancedAvailable: false
    readonly property bool dark: mode === "dark"
        || (mode === "system" && Qt.styleHints.colorScheme === Qt.ColorScheme.Dark)

    readonly property color bg: dark ? "#11181b" : "#e6e3df"
    readonly property color paper: dark ? "#1c272c" : "#f6f4f1"
    readonly property color ink: dark ? "#e0e3dc" : "#0b0c0b"
    readonly property color muted: dark ? "#a6b0b1" : "#77756d"
    readonly property color hair: dark ? "#536166" : "#aaa59a"
    readonly property color grid: dark ? Qt.rgba(0.65, 0.69, 0.69, 0.08) : Qt.rgba(0.47, 0.45, 0.42, 0.16)
    readonly property color glow: dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(1, 1, 1, 0.75)
    readonly property color decoGrey: dark ? "#2a363b" : "#d5d2cd"
    // 黑块方块：浅色下是墨色，深色下比底色更深一档
    readonly property color block: dark ? "#070b0d" : "#0b0c0b"
    readonly property color blockText: dark ? "#e0e3dc" : "#ffffff"
    readonly property color accent: dark ? "#e07a2c" : "#e8701f"
    readonly property color amber: dark ? "#c5a16b" : "#9b7247"
    readonly property color success: dark ? "#7fa784" : "#55785a"
    readonly property color warning: dark ? "#d39a55" : "#b8752c"
    readonly property color error: dark ? "#d9695f" : "#b6453c"

    // 启动动画的场地色：PV 为白场
    readonly property color bootField: dark ? "#11181b" : "#ffffff"
    readonly property color bootInk: dark ? "#e0e3dc" : "#0b0c0b"

    // Qt 不能加载前端那套 woff2 分片；系统装有 MiSans 时用它，否则退到微软雅黑（避免中文落到宋体）
    readonly property string font: Qt.fontFamilies().indexOf("MiSans") >= 0 ? "MiSans" : "Microsoft YaHei UI"
}
