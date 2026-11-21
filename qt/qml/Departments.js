.pragma library

// 一级界面 01–10（不含计划管理），主页居中。坐标为 1920×1080 舞台中心点。
// style: card 白卡 / block 黑块 / bare 直接排字；depth 越大，鼠标视差越明显
// art 以卡片宽高为单位指定图形中心 (x, y) 和相对宽度 w。
var list = [
    { n: "01", key: "home", art: { x: 0.76, y: 0.25, w: 1.50 },          code: "MAIN\nOVRV", sub: "MAIN OVERVIEW SECTION",      zh: "主页",       x: 960,  y: 540, w: 340, h: 340, style: "block", size: 112, depth: 4,  center: true },
    { n: "02", key: "scripts", art: { x: 0.25, y: 0.76, w: 0.90 },       code: "CSTD",       sub: "SCRIPT CUSTODY SECTION",     zh: "托管管理",   x: 600,  y: 300, w: 200, h: 200, style: "card",  size: 62,  depth: 16 },
    { n: "03", key: "emulators", art: { x: 0.16, y: 0.53, w: 0.49 },     code: "EMUL",       sub: "EMULATOR SECTION",           zh: "模拟器管理", x: 560,  y: 560, w: 260, h: 130, style: "bare",  size: 84,  depth: 22, accent: true },
    { n: "04", key: "queue", art: { x: 0.37, y: 0.85, w: 1.42 },         code: "QUE",        sub: "QUEUE DISPATCH SECTION",     zh: "调度队列",   x: 270,  y: 720, w: 220, h: 220, style: "block", size: 70,  depth: 12 },
    { n: "05", key: "scheduler", art: { x: 0.16, y: 0.22, w: 1.55 },     code: "SCHD",       sub: "SCHEDULING CONTROL SECTION", zh: "调度中心",   x: 300,  y: 330, w: 230, h: 230, style: "card",  size: 66,  depth: 10 },
    { n: "06", key: "localControls", art: { x: 0.82, y: 0.50, w: 1.04 }, code: "LOCL",       sub: "LOCAL CONTROL SECTION",      zh: "本地控制",   x: 1320, y: 300, w: 200, h: 200, style: "card",  size: 60,  depth: 18 },
    { n: "07", key: "gamesign", art: { x: 0.77, y: 0.26, w: 0.59 },      code: "SIGN",       sub: "COMMUNITY SIGN SECTION",     zh: "签到",       x: 1640, y: 300, w: 270, h: 170, style: "card",  size: 70,  depth: 10 },
    { n: "08", key: "history", art: { x: 0.79, y: 0.72, w: 0.56 },       code: "HIST",       sub: "HISTORICAL RECORD SECTION",  zh: "历史记录",   x: 1430, y: 560, w: 280, h: 130, style: "bare",  size: 92,  depth: 24 },
    // 资源商店已删除，09 改为主页的游戏活动轮播（原首页 A-04 FIELD INTELLIGENCE）
    { n: "09", key: "activity", art: { x: 0.48, y: 0.86, w: 1.34 },      code: "INTL",       sub: "FIELD INTELLIGENCE SECTION", zh: "游戏活动",   x: 1330, y: 800, w: 190, h: 190, style: "card",  size: 54,  depth: 14 },
    { n: "10", key: "settings", art: { x: 0.75, y: 0.78, w: 0.85 },      code: "SYS",        sub: "SYSTEM CONFIG SECTION",      zh: "设置",       x: 1650, y: 760, w: 200, h: 200, style: "block", size: 74,  depth: 8 }
]

// 纯装饰方块（PV 里的空白卡、条纹卡）
var decos = [
    { kind: "inset",  x: 760,  y: 820, w: 150, h: 150, depth: 20, blur: 0 },
    { kind: "stripe", x: 1775, y: 545, w: 140, h: 140, depth: 28, blur: 0.3 },
    { kind: "plain",  x: 120,  y: 520, w: 90,  h: 90,  depth: 6,  blur: 0.6 }
]
