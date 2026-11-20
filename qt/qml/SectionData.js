.pragma library

// 二级界面数据：每个部门若干条目（左下卡带 / 右上分页点），条目可再按功能分页。
// 字段与后端配置一一对应（app/models/config.py），key 为配置键，api 为该页提交的接口。
// 现为演示数据；接入后端时按 api 取数并回写同名字段。
//
// 块：kv / table / stats / note / log / banner / list / run
// 控件：tog / inp / num / path / seg / sel / chips / tag / mini / txt；
//      kv 的值可以是字符串、控件，或控件数组（同一行排开）。

function tog(v, x) { return { c: "tog", v: !!v, x: x || "" } }
function inp(v, mono) { return { c: "inp", v: v || "", mono: !!mono } }
function num(v, unit) { return { c: "num", v: v, unit: unit || "" } }
function time(v) { return { c: "time", v: v } }
function date(v) { return { c: "date", v: v } }
function path(v) { return { c: "path", v: v || "" } }
function seg(opts, i) { return { c: "seg", opts: opts, v: i || 0 } }
function segk(opts, i, k) { return { c: "seg", opts: opts, v: i || 0, k: k } }
function sel(opts, i, k) { return { c: "sel", opts: opts, v: i || 0, k: k || "" } }
function chips(mask) { return { c: "chips", v: mask } }
function tag(t, kind) { return { c: "tag", t: t, kind: kind } }
function mini(names) { return { c: "mini", names: names } }
function unit(t) { return { c: "unit", t: t } }

var OK = tag("完成", "ok"), RUN = tag("运行", "run"), WAIT = tag("等待", "idle"), ERR = tag("异常", "err")
var POWER = ["无动作", "退出 AUTO-MAS", "重启 AUTO-MAS", "睡眠", "休眠", "注销", "关机", "强制关机", "重启"]

function kv(title, rows) { return { t: "kv", title: title, rows: rows } }
// weights：各列宽度权重（省略时等分）
function table(title, cols, rows, weights) { return { t: "table", title: title, cols: cols, rows: rows, weights: weights } }
function stats(title, rows) { return { t: "stats", title: title, rows: rows } }
function note(text) { return { t: "note", text: text } }
function log(title, lines, tall) { return { t: "log", title: title, lines: lines, tall: !!tall } }
function banner(o) { o.t = "banner"; return o }
function list(title, rows) { return { t: "list", title: title, rows: rows } }

// 通用脚本：程序 / 判定 / 游戏 / 限制 / 账号。c 为后端 GeneralConfig 结构 {Info, Script, Game, Run}，
// users 为 [{name, status, remained, base, last}]；字段键与 /api/scripts/get 返回一致。
function idx(list, v, d) { var i = list.indexOf(v); return i < 0 ? (d || 0) : i }
function general(name, en, c, users, live) {
    var api = "POST /api/scripts/update"
    var I = c.Info, S = c.Script, G = c.Game, R = c.Run
    var gameType = idx(["Emulator", "Client", "URL"], G.Type, 1)
    return { name: name, en: en, live: !!live, icon: c.Script.ScriptPath || "", accounts: users.map(function (u) { return u.name }), tabs: [
        { name: "程序", api: api, blocks: [
            kv("SCRIPT", [["脚本名称", inp(I.Name), "Info.Name"], ["根目录", path(I.RootPath), "Info.RootPath"], ["启动程序", path(S.ScriptPath), "Script.ScriptPath"], ["启动参数", inp(S.Arguments, true), "Script.Arguments"], ["配置路径", path(S.ConfigPath), "Script.ConfigPath"], ["路径类型", seg(["文件", "文件夹"], idx(["File", "Folder"], S.ConfigPathMode)), "Script.ConfigPathMode"], ["回写配置", seg(["从不", "成功时", "失败时", "总是"], idx(["Never", "Success", "Failure", "Always"], S.UpdateConfigMode)), "Script.UpdateConfigMode"]]),
            kv("PROCESS", [["追踪进程", tog(S.IfTrackProcess), "Script.IfTrackProcess"], ["进程名", inp(S.TrackProcessName, true), "Script.TrackProcessName"], ["清理范围", seg(["跨会话强力", "仅本轮", "当前会话"], idx(["Force", "Tracked", "Session"], S.TaskKillMode)), "Script.TaskKillMode"]])
        ], actions: ["保存", "复制脚本", "删除脚本"] },
        { name: "判定", api: api, blocks: [
            kv("LOG FILE", [["日志路径", path(S.LogPath), "Script.LogPath"], ["路径日期格式", inp(S.LogPathFormat, true), "Script.LogPathFormat"], ["时间戳位置", [num(S.LogTimeStart), unit("至"), num(S.LogTimeEnd), unit("列")], "Script.LogTimeStart / LogTimeEnd"], ["时间格式", inp(S.LogTimeFormat, true), "Script.LogTimeFormat"]]),
            kv("MATCH", [["成功判定", [inp(S.SuccessLog), seg(["关键字", "正则"], idx(["Split", "Regex"], S.SuccessLogMode))], "Script.SuccessLog / SuccessLogMode"], ["失败判定", [inp(S.ErrorLog), seg(["关键字", "正则"], idx(["Split", "Regex"], S.ErrorLogMode))], "Script.ErrorLog / ErrorLogMode"], ["日志预处理", tog(S.LogHookEnabled), "Script.LogHookEnabled"], ["推送日志", tog(S.PushLogEnabled), "Script.PushLogEnabled"]]),
            note("关键字模式用「|」分隔多个子串，任一命中即判定；正则模式按整行匹配。预处理先于判定执行。")
        ], actions: ["保存", "测试匹配"] },
        { name: "游戏", api: api, blocks: [
            kv("GAME", [["随脚本启动游戏", tog(G.Enabled), "Game.Enabled"], ["启动方式", seg(["模拟器", "客户端", "URL 协议"], gameType), "Game.Type"], [gameType === 2 ? "协议地址" : "游戏路径", gameType === 2 ? inp(G.URL, true) : path(G.Path), gameType === 2 ? "Game.URL" : "Game.Path"], ["进程名", inp(G.ProcessName, true), "Game.ProcessName"], ["启动参数", inp(G.Arguments, true), "Game.Arguments"], ["启动后等待", num(G.WaitTime, "秒"), "Game.WaitTime"], ["结束后强制关闭", tog(G.IfForceClose), "Game.IfForceClose"]]),
            kv("EMULATOR", [["模拟器", G.EmulatorId === "-" ? "未选择" : G.EmulatorId, "Game.EmulatorId"], ["实例", G.EmulatorIndex === "-" ? "未选择" : G.EmulatorIndex, "Game.EmulatorIndex"]])
        ], actions: ["保存"] },
        { name: "限制", api: api, blocks: [
            kv("RUN LIMIT", [["单账号总时限", num(R.HardTimeLimit, "分钟"), "Run.HardTimeLimit"], ["单次运行时限", num(R.RunTimeLimit, "分钟"), "Run.RunTimeLimit"], ["单次重试次数", num(R.RunTimesLimit, "次"), "Run.RunTimesLimit"], ["每日代理上限", num(R.ProxyTimesLimit, "次 · 0 为不限"), "Run.ProxyTimesLimit"]]),
            note("总时限包含等待游戏与全部重试；单次超时会先按清理清单结束进程，再按重启清单补跑。")
        ], actions: ["保存", "恢复默认"] },
        { name: "账号", api: "POST /api/scripts/user/update", blocks: [
            table("USERS", ["名称", "启用", "剩余天数", "配置来源", "上次代理"], users.slice(0, 8).map(function (u) { return [u.name, tog(u.status), u.remained, sel(["独立", "共享", "原生"], u.base), u.last] })),
            note(users.length > 8 ? "共 " + users.length + " 个账号，这里列出前 8 个。" : "配置来源：独立 = 账号单独一份脚本配置；共享 = 与同脚本账号共用；原生 = 直接使用脚本自身配置。")
        ], actions: ["添加账号", "设置脚本", "删除所选"] }
    ] }
}

// 演示数据转成后端结构
function demoGeneral(o) {
    var c = {
        Info: { Name: o.name, RootPath: o.root },
        Script: { ScriptPath: o.exe, Arguments: o.args || "", ConfigPath: o.cfg, ConfigPathMode: o.folder ? "Folder" : "File", UpdateConfigMode: "Success",
                  IfTrackProcess: !!o.track, TrackProcessName: o.track || "", TaskKillMode: "Force", LogPath: o.log, LogPathFormat: "%Y-%m-%d",
                  LogTimeStart: 1, LogTimeEnd: 19, LogTimeFormat: "%Y-%m-%d %H:%M:%S", SuccessLog: o.ok, SuccessLogMode: "Split",
                  ErrorLog: o.err, ErrorLogMode: "Split", LogHookEnabled: false, PushLogEnabled: true },
        Game: { Enabled: !!o.game, Type: ["Emulator", "Client", "URL"][o.gameType === undefined ? 1 : o.gameType], Path: o.game || "", URL: "",
                ProcessName: o.gameProc || "", Arguments: "", WaitTime: 30, IfForceClose: true, EmulatorId: "-", EmulatorIndex: "-" },
        Run: { HardTimeLimit: 120, RunTimeLimit: o.limit || 60, RunTimesLimit: 3, ProxyTimesLimit: 0 }
    }
    var users = o.users.map(function (u) { return { name: u[0], status: u[1], remained: u[2], base: u[3], last: u[4] } })
    return general(o.name, o.en, c, users, false)
}

// 模拟器：设备 / 配置（EmulatorConfig，/api/emulator/operate）
function emulator(o) {
    var cfg = [["名称", inp(o.name), "Info.Name"], ["类型", seg(["通用", "MuMu", "雷电", "2.0"], o.type), "Info.Type"], ["安装路径", path(o.path), "Info.Path"], ["最大等待", num(300, "秒"), "Info.MaxWaitTime"], ["老板键", inp("Alt+Q", true), "Info.BossKey"], ["关闭时清理残留", tog(false), "Info.ForceKillOnClose"], ["启动前关闭全部", tog(false), "Info.ForceKillBeforeLaunch"]]
    if (o.type === 3) cfg.push(["稳定模式", tog(true), "Info.StableMode"], ["配置守卫", tog(true), "Info.ConfigGuard"])
    var running = o.devices.filter(function (d) { return d[1] === RUN }).length
    return { name: o.name, en: o.en, tabs: [
        { name: "设备", api: "POST /api/emulator/operate", blocks: [
            table("DEVICES", ["名称", "状态", "ADB 地址", "操作"], o.devices.map(function (d) { return [d[0], d[1], inp(d[2], true), mini([d[1] === RUN ? "关闭" : "启动", "显示"])] })),
            stats("SUMMARY", [["实例", String(o.devices.length)], ["运行中", String(running)], ["被任务占用", running ? "1" : "0"]])
        ], actions: ["刷新设备", "全部关闭"] },
        { name: "配置", api: "POST /api/emulator/update", blocks: [kv("CONFIG", cfg)], actions: ["保存", "自动搜索", "删除"] }
    ] }
}

// 调度队列：调度 / 定时 / 队列项（QueueConfig、TimeSet、QueueItem）
var SCRIPTS = ["BGI 每日", "鸣潮日常", "星铁清体力", "自定义脚本"]
function queue(o) {
    return { name: o.name, en: o.en, exclusive: o.cycle ? "cycle" : "time", tabs: [
        { name: "调度", api: "POST /api/queue/update", blocks: [
            kv("SCHEDULE", [["队列名称", inp(o.name), "Info.Name"], ["定时启动", tog(!o.cycle, "time"), "Info.TimeEnabled"], ["循环队列", tog(!!o.cycle, "cycle"), "Info.CycleEnabled"], ["启动时运行", seg(["从不", "每次", "每日首次"], o.startup || 0), "Info.StartUpMode"], ["完成后", sel(POWER, o.after || 0), "Info.AfterAccomplish"], ["延时执行", num(0, "分钟"), "Info.AfterAccomplishDelay"]]),
            kv("HOOKS", [["运行前脚本", tog(false), "Info.IfScriptBeforeTask"], ["前脚本路径", path(""), "Info.ScriptBeforeTask"], ["运行后脚本", tog(!!o.afterScript), "Info.IfScriptAfterTask"], ["后脚本路径", path(o.afterScript), "Info.ScriptAfterTask"]])
        ], actions: ["保存", "立即运行", "删除队列"] },
        { name: "定时", api: "POST /api/queue/time/update", blocks: [
            table("TIME SET", ["启用", "周期", "时间"], o.times.map(function (t) { return [tog(t[0]), chips(t[1]), time(t[2])] }), [1, 2.6, 1]),
            note(o.cycle ? "循环队列与定时启动互斥：开启循环后，按「队列项」中各脚本自己的周期持续运行。" : "同一队列可设置多个定时；周期为空时该定时不会触发。")
        ], actions: ["添加定时", "删除所选"] },
        { name: "队列项", api: "POST /api/queue/item/update", blocks: [
            table("ITEMS", ["脚本", "参与循环", "方式", "时间 / 间隔", "下次运行"], o.items.map(function (it) { return [sel(SCRIPTS, it[0]), tog(it[1]), seg(["定时", "间隔"], it[2]), it[2] ? num(it[3], "分钟") : time(it[3]), it[4]] }), [2.4, 1.1, 1.4, 1.3, 1]),
            note("「参与循环」「方式」「间隔」只在循环队列中生效；间隔可从上次开始或上次结束计时。")
        ], actions: ["添加脚本", "上移", "下移", "删除所选"] }
    ] }
}

var TASKS = ["日常托管 · 队列", "周常收尾 · 队列", "夜间循环 · 循环队列", "BGI 每日 · 脚本"]

var sections = {
    "01": { caption: "主页：快速启动队列或脚本，查看各账号的代理状态。", items: [
        { name: "快速启动", en: "QUICK START", api: "POST /api/dispatch/start", blocks: [
            kv("START", [["任务对象", sel(TASKS, 0, "queue"), "taskId"], ["运行模式", seg(["自动代理", "设置脚本", "循环运行"], 0), "mode"], ["完成后", sel(POWER, 0), "POST /api/dispatch/set/power"], ["上次运行", "今天 06:00 · 全部完成"], ["下次定时", "今天 18:00 · 日常托管"]]),
            stats("TODAY", [["今日已代理", "6", "done"], ["待运行", "2", "left"], ["异常", "0"]]),
            { t: "run", title: "RUN STATUS" }
        ], actions: ["开始执行", "停止"] },
        { name: "代理状态", en: "PROXY STATUS", api: "GET /api/dispatch/runtime-snapshot", blocks: [
            stats("NOW", [["运行中队列", "1"], ["运行中账号", "1"], ["本轮剩余", "3"]]),
            table("ACCOUNTS", ["账号", "托管", "上次代理", "今日", "状态"], [["主号", "BGI 每日", "06:12", "1 / 2", OK], ["小号", "BGI 每日", "昨天", "0 / 2", RUN], ["鸣潮主号", "鸣潮日常", "06:40", "1 / 1", OK], ["星铁", "星铁清体力", "06:52", "1 / 2", ERR], ["默认", "自定义脚本", "周日", "0 / 1", WAIT]])
        ], actions: ["刷新", "查看历史记录"] }
    ] },
    "02": { caption: "通用脚本托管：程序、日志判定、游戏启动、运行限制与账号，按功能分页。", items: [
        demoGeneral({ name: "BGI 每日", en: "GENERAL · RDP", root: "D:\\BetterGI", exe: "D:\\BetterGI\\BetterGI.exe", args: "--startOneDragon", cfg: "D:\\BetterGI\\User\\config.json", track: "BetterGI.exe", log: "D:\\BetterGI\\log\\better-genshin-impact%Y%m%d.log", ok: "一条龙完成", err: "任务异常|ERROR", game: "D:\\Genshin Impact\\YuanShen.exe", gameProc: "YuanShen.exe", users: [["主号", true, "永久", 0, "今天 06:12"], ["小号", true, "30 天", 0, "昨天 06:30"], ["测试号", false, "—", 1, "—"]] }),
        demoGeneral({ name: "鸣潮日常", en: "GENERAL", root: "D:\\ok-ww", exe: "D:\\ok-ww\\ok-ww.exe", args: "-t 1 -e", cfg: "D:\\ok-ww\\configs", folder: true, log: "D:\\ok-ww\\logs\\ok-script.log", ok: "任务完成", err: "Exception", game: "D:\\Wuthering Waves\\launcher.exe", gameProc: "Client-Win64-Shipping.exe", users: [["鸣潮主号", true, "永久", 2, "今天 06:40"]] }),
        demoGeneral({ name: "星铁清体力", en: "GENERAL", root: "D:\\M7A", exe: "D:\\M7A\\March7th Assistant.exe", cfg: "D:\\M7A\\config.yaml", track: "March7th Assistant.exe", log: "D:\\M7A\\logs\\%Y-%m-%d.log", ok: "任务完成", err: "ERROR", game: "D:\\Star Rail\\StarRail.exe", gameProc: "StarRail.exe", limit: 45, users: [["星铁", true, "12 天", 0, "今天 06:52"], ["星铁小号", false, "—", 0, "—"]] }),
        demoGeneral({ name: "自定义脚本", en: "GENERAL", root: "C:\\Tools", exe: "C:\\Tools\\daily.bat", cfg: "", log: "C:\\Tools\\daily.log", ok: "done", err: "fail", gameType: 2, users: [["默认", true, "永久", 0, "周日 22:10"]] })
    ] },
    "03": { caption: "模拟器：实例启动、关闭、显示与设备检测；配置与 2.0 稳定模式。", items: [
        emulator({ name: "MuMu 12", en: "EMULATOR", type: 1, path: "D:\\MuMuPlayer-12.0", devices: [["MuMu-0", RUN, "127.0.0.1:16384"], ["MuMu-1", WAIT, "127.0.0.1:16416"], ["MuMu-2", WAIT, "127.0.0.1:16448"]] }),
        emulator({ name: "雷电 9", en: "EMULATOR", type: 2, path: "D:\\leidian\\LDPlayer9", devices: [["雷电-0", WAIT, "emulator-5554"]] }),
        emulator({ name: "Android AVD", en: "EMULATOR 2.0", type: 3, path: "C:\\Android\\Sdk", devices: [["Pixel_7", WAIT, "emulator-5556"], ["Tablet", WAIT, "emulator-5558"]] })
    ] },
    "04": { caption: "调度队列：定时与循环、启动时运行、完成后动作与队列项。", items: [
        queue({ name: "日常托管", en: "QUEUE", startup: 2, afterScript: "C:\\Tools\\after.bat", times: [[true, "1111111", "06:00"], [true, "1111111", "18:00"]], items: [[0, true, 0, "06:00", "今天 18:00"], [1, true, 0, "06:30", "明天 06:30"], [2, true, 0, "06:45", "明天 06:45"]] }),
        queue({ name: "周常收尾", en: "QUEUE", after: 3, times: [[true, "0000001", "22:00"]], items: [[3, true, 0, "22:00", "周日 22:00"]] }),
        queue({ name: "夜间循环", en: "QUEUE · CYCLE", cycle: true, after: 6, times: [[false, "0000000", "23:30"]], items: [[0, true, 1, 480, "今天 23:30"], [2, false, 1, 240, "—"]] })
    ] },
    "05": { caption: "调度中心：执行面板、任务总览、托管切换与实时日志。", items: [
        { name: "主执行面板", en: "PANEL 01", tabs: [
            { name: "总览", api: "GET /api/dispatch/runtime-snapshot", blocks: [
                kv("TASK", [["任务", "队列 · 日常托管"], ["模式", "自动代理"], ["状态", [RUN, "已运行 02:13"]], ["完成后", "无动作 · 可在主页修改"]]),
                table("TASK TREE", ["托管", "账号", "状态"], [["BGI 每日", "主号", OK], ["BGI 每日", "小号", RUN], ["鸣潮日常", "鸣潮主号", WAIT], ["星铁清体力", "星铁", WAIT]])
            ], actions: ["停止任务", "上一个托管", "下一个托管"] },
            { name: "日志", api: "WS /api/core/ws", blocks: [
                log("LIVE LOG", [["06:00:02", "队列开始：日常托管"], ["06:00:03", "本地远程桌面分身：连接中"], ["06:00:05", "BGI 每日 · 主号：启动 BetterGI.exe --startOneDragon"], ["06:00:41", "等待游戏窗口 YuanShen.exe"], ["06:03:10", "日志：开始执行一条龙"], ["06:12:40", "主号 · 一条龙完成 → Success!", "s"], ["06:12:42", "清理进程：BetterGI.exe、YuanShen.exe"], ["06:12:44", "BGI 每日 · 小号：启动中…"], ["06:13:20", "等待游戏窗口 YuanShen.exe"]], true)
            ], actions: ["停止任务", "清空日志"] }
        ] },
        { name: "面板 02", en: "PANEL 02", api: "POST /api/dispatch/start", blocks: [
            kv("TASK", [["任务对象", sel(["未选择"].concat(TASKS), 0), "taskId"], ["运行模式", seg(["自动代理", "设置脚本", "循环运行"], 0), "mode"], ["状态", [WAIT, "空闲"]]]),
            log("LOG", [["—", "选择队列或脚本后开始执行"]])
        ], actions: ["开始执行", "关闭面板"] }
    ] },
    "06": { caption: "本地控制：远程桌面分身、虚拟显示器、全局热键与连接端口。", items: [
        { name: "远程桌面分身", en: "CHILD SESSION · RDP", api: "POST /api/setting/update", blocks: [
            kv("CHILD SESSION", [["启用分身执行", tog(true), "ChildSession.Enabled"], ["宿主端口", num(36165), "ChildSession.HostPort"], ["分辨率", sel(["2560x1440", "1920x1080", "1600x900"], 0), "ChildSession.Resolution"], ["启动时隐藏预览", tog(false), "ChildSession.StartHidden"], ["观看模式", tog(true), "ChildSession.WatchMode"]]),
            kv("STATUS", [["会话", [WAIT, "已登录 · 空闲"]], ["占用", "无任务占用"]]),
            note("观看模式会屏蔽本机键鼠进入分身，避免误触打断任务。")
        ], actions: ["打开分身", "重新连接", "注销会话"] },
        { name: "虚拟显示器", en: "VIRTUAL DISPLAY", api: "POST /api/setting/virtual-display/check", blocks: [
            kv("DISPLAY", [["无人值守时挂载", tog(true), "Display.IfEnableVirtualDisplay"], ["刷新率", seg(["1920×1080 @60", "1920×1080 @30"], 0), "Display.VirtualDisplayMode"], ["驱动", "Parsec 虚拟显示驱动 · 已安装"], ["当前状态", "未挂载 · 有真实显示输出"]]),
            note("所有真实显示输出断开后，挂一块 1920×1080 的虚拟屏，避免游戏窗口被压小。驱动需自行安装。")
        ], actions: ["检测", "立即卸下"] },
        { name: "全局热键", en: "HOTKEY", api: "POST /api/dispatch/hotkey/reload", blocks: [
            kv("BINDINGS", [["启用全局热键", tog(true), "Hotkey.Enabled"], ["启动 / 停止", [inp("Ctrl+Alt+S", true), mini(["录制"])], "Hotkey.ToggleStartStop"], ["上一个托管", [inp("Ctrl+Alt+Left", true), mini(["录制"])], "Hotkey.PreviousTask"], ["下一个托管", [inp("Ctrl+Alt+Right", true), mini(["录制"])], "Hotkey.NextTask"]])
        ], actions: ["保存并重新加载"] },
        { name: "连接端口", en: "HOST", api: "GET /api/info/version", blocks: [kv("PORTS", [["页面端口", "36262"], ["后端端口", "36263"], ["实例标识", "372fa7a8…"], ["后端状态", [OK, "已连接"]]])], actions: ["复制地址"] }
    ] },
    "07": { caption: "游戏社区签到：签到设置、账号组与签到结果。", items: [
        { name: "签到设置", en: "SIGN", api: "POST /api/tools/update", blocks: [
            kv("SIGN", [["启用签到", tog(true), "GameSign.Enabled"], ["启动时签到", tog(true), "GameSign.RunOnStartup"], ["每日自动签到", tog(true), "GameSign.AutoStart"], ["结果通知", tog(false), "GameSign.NotifyEnabled"], ["活动查询", tog(true), "GameSign.ActivityEnabled"], ["上次签到", "今天 08:00 · 全部成功"]])
        ], actions: ["立即签到"] },
        { name: "账号组", en: "ACCOUNTS", api: "POST /api/tools/sign/account/update", blocks: [
            table("GROUPS", ["账号组", "启用", "米游社", "森空岛", "库街区", "塔吉多"], [["用户 1", tog(true), OK, OK, WAIT, WAIT], ["用户 2", tog(true), OK, WAIT, OK, WAIT], ["用户 3", tog(false), WAIT, WAIT, WAIT, WAIT]]),
            note("各平台凭据通过扫码登录写入账号组，签到时按组依次执行。")
        ], actions: ["添加账号组", "扫码登录", "删除所选"] },
        { name: "签到结果", en: "RESULT", api: "POST /api/tools/sign", blocks: [
            table("TODAY", ["平台", "账号组", "结果", "时间"], [["米游社 · 原神", "用户 1", OK, "08:00:12"], ["米游社 · 星铁", "用户 1", OK, "08:00:15"], ["森空岛", "用户 1", OK, "08:00:18"], ["库街区", "用户 2", ERR, "需要重新登录"], ["米游社 · 原神", "用户 2", OK, "08:00:24"]])
        ], actions: ["重新签到失败项"] }
    ] },
    "08": { caption: "历史记录：按日、周、月合并查看每个账号的代理结果与日志。", items: [
        { name: "查询", en: "SEARCH", api: "POST /api/history/search", blocks: [
            kv("FILTER", [["开始日期", date("2026-11-14"), "start_date"], ["结束日期", date("2026-11-20"), "end_date"], ["合并方式", seg(["按日", "按周", "按月"], 0), "mode"]]),
            stats("RANGE", [["代理次数", "41"], ["成功", "38"], ["异常", "3"]])
        ], actions: ["查询", "导出"] },
        { name: "11-20", en: "TODAY", api: "POST /api/history/data", blocks: [stats("SUMMARY", [["代理次数", "6"], ["成功", "5"], ["异常", "1"]]), table("RECORDS", ["时间", "账号", "托管", "结果"], [["06:12", "主号", "BGI 每日", OK], ["06:30", "小号", "BGI 每日", OK], ["06:40", "鸣潮主号", "鸣潮日常", OK], ["06:52", "星铁", "星铁清体力", ERR]])], actions: ["查看日志", "查看录像"] },
        { name: "11-19", en: "HISTORY", api: "POST /api/history/data", blocks: [stats("SUMMARY", [["代理次数", "8"], ["成功", "8"], ["异常", "0"]]), table("RECORDS", ["时间", "账号", "托管", "结果"], [["06:10", "主号", "BGI 每日", OK], ["06:31", "小号", "BGI 每日", OK], ["18:02", "鸣潮主号", "鸣潮日常", OK]])], actions: ["查看日志", "查看录像"] },
        { name: "11-18", en: "HISTORY", api: "POST /api/history/data", blocks: [stats("SUMMARY", [["代理次数", "7"], ["成功", "6"], ["异常", "1"]]), table("RECORDS", ["时间", "账号", "托管", "结果"], [["06:15", "小号", "BGI 每日", ERR], ["06:40", "主号", "BGI 每日", OK]])], actions: ["查看日志", "查看录像"] }
    ] },
    "09": { caption: "游戏活动：版本、活动时间、剩余时间与卡池。", items: [
        { name: "终末地", en: "ENDFIELD", api: "POST /api/info/endfield/version-art", blocks: [banner({ v: "1.6 版本", title: "丹青渡", left: "6 天 5 时", c: ["#203030", "#5b6a4c", "#d6c28c"] }), kv("PERIOD", [["活动时间", "10/15 12:00 – 11/26 06:00"]]), list("POOLS", [["特许", "烟火邀星河"], ["武器", "丹青长卷"]])], actions: ["打开活动页"] },
        { name: "崩坏：星穹铁道", en: "STAR RAIL", api: "POST /api/info/stella/activity", blocks: [banner({ v: "3.7 版本", title: "向星而行", left: "12 天 3 时", c: ["#1a1d3a", "#4a3f7a", "#d9a8c7"] }), kv("PERIOD", [["活动时间", "11/12 – 12/02"]])], actions: ["打开活动页"] },
        { name: "原神", en: "GENSHIN", api: "POST /api/tools/community/activity/query", blocks: [banner({ v: "6.2 版本", title: "霜夜灵嗣", left: "20 天", c: ["#1d3346", "#3f6f8a", "#e3d3a1"] }), kv("PERIOD", [["活动时间", "11/19 – 12/30"]])], actions: ["打开活动页"] },
        { name: "鸣潮", en: "WUTHERING", api: "POST /api/tools/community/activity/query", blocks: [banner({ v: "2.8 版本", title: "回声之岸", left: "4 天 11 时", c: ["#16242a", "#2f5d5e", "#b9d3c5"] }), kv("PERIOD", [["活动时间", "10/30 – 11/24"]])], actions: ["打开活动页"] },
        { name: "明日方舟", en: "ARKNIGHTS", api: "POST /api/info/arknights/activity", blocks: [banner({ v: "SIDE STORY", title: "新活动", left: "9 天", c: ["#222222", "#555555", "#bbbbbb"] }), kv("PERIOD", [["活动时间", "11/14 – 11/28"]])], actions: ["打开活动页"] }
    ] },
    "10": { caption: "设置：启动与界面、功能、通知、更新、录像与关于。", items: [
        { name: "启动与界面", en: "START · UI", api: "POST /api/setting/update", blocks: [kv("START", [["开机自启", tog(true), "Start.IfSelfStart"], ["启动后最小化", tog(false), "Start.IfMinimizeDirectly"], ["显示托盘图标", tog(true), "UI.IfShowTray"], ["关闭到托盘", tog(true), "UI.IfToTray"], ["隐藏关闭按钮", tog(false), "UI.IfHideCloseButton"], ["主题", seg(["跟随系统", "浅色", "深色"], 0)], ["动态效果", segk(["减少", "标准", "增强"], 1, "motion")], ["语言", sel(["简体中文", "English"], 0)]])], actions: ["保存", "恢复默认"] },
        { name: "功能", en: "FUNCTION", api: "POST /api/setting/update", blocks: [kv("BEHAVIOR", [["历史记录保留", sel(["7 天", "15 天", "30 天", "60 天", "90 天", "180 天", "365 天", "永久"], 7), "Function.HistoryRetentionTime"], ["运行时允许睡眠", tog(false), "Function.IfAllowSleep"], ["静默模式", tog(false), "Function.IfSilence"], ["屏蔽模拟器广告", tog(true), "Function.IfBlockAd"], ["匿名遥测", tog(true), "Function.IfEnableTelemetry"], ["语音提示", tog(false), "Voice.Enabled"], ["语音风格", seg(["简洁", "热闹"], 0), "Voice.Type"]])], actions: ["保存"] },
        { name: "通知", en: "NOTIFY", api: "POST /api/setting/update", blocks: [kv("CHANNELS", [["任务结果推送", seg(["不推送", "任何时刻", "仅失败时"], 2), "Notify.SendTaskResultTime"], ["发送统计", tog(true), "Notify.IfSendStatistic"], ["系统通知", tog(true), "Notify.IfPushPlyer"], ["邮件", tog(false), "Notify.IfSendMail"], ["Server 酱", tog(true), "Notify.IfServerChan"], ["Koishi", tog(false), "Notify.IfKoishiSupport"], ["OpenClaw QQ", tog(false), "Notify.IfOpenClawQQ"], ["自定义 Webhook", "2 个 · 已启用 1 个", "Notify.CustomWebhooks"]])], actions: ["测试通知", "管理 Webhook"] },
        { name: "更新", en: "UPDATE", api: "POST /api/setting/update", blocks: [kv("UPDATE", [["当前版本", "v5.7.0"], ["自动更新", tog(true), "Update.IfAutoUpdate"], ["更新源", sel(["GitHub", "Mirror 酱", "AutoSite", "CNB"], 0), "Update.Source"], ["更新渠道", seg(["稳定版", "测试版"], 0), "Update.Channel"], ["GitHub 加速", seg(["自动", "关闭"], 0), "Update.GitHubMirror"], ["代理地址", inp("", true), "Update.ProxyAddress"]])], actions: ["检查更新", "暂停更新 7 天"] },
        { name: "录像回放", en: "REPLAY · OBS", api: "POST /api/setting/obs/save", blocks: [kv("OBS", [["任务录像", tog(false), "Replay.Enabled"], ["OBS 端口", num(4455), "Replay.Port"], ["最多保留", num(20, "段"), "Replay.MaxReplayCount"]]), note("通过 OBS WebSocket 录制每个账号的任务过程，可在历史记录中回看。")], actions: ["检查连接", "保存"] },
        { name: "高级与关于", en: "ADVANCED", api: "POST /api/setting/backup", blocks: [kv("ADVANCED", [["日志导出", "打包 logs / debug"], ["数据备份", "导出全部配置"], ["字体", "MiSans（小米）· 许可见 NOTICE"], ["视觉参考", "LBEILC / RhineLabUI（MIT）"]])], actions: ["导出日志", "导出备份", "查看许可"] }
    ] }
}

// 条目的功能分页；无分页的条目视作只有一页
function pages(item) {
    return item.tabs ? item.tabs : [{ name: item.name, api: item.api, blocks: item.blocks, actions: item.actions, save: item.save, ops: item.ops }]
}
