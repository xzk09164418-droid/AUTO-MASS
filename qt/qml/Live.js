.pragma library
.import "SectionData.js" as SD

// 后端实时数据 → 档案卡条目；以及按改动生成保存请求。
// 控件 spec 上的 key 为配置键（"组.字段"），enum 为分段 / 下拉的取值表；
// 保存目标 save = {path, base}：页上给默认值，表格行里的控件可单独指定（如账号、定时、队列项）。
// 条目上的 ops 把按钮名映射到接口操作（见 SectionView.runOp）。

var DAYNAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
var POWER_EN = ["NoAction", "KillSelf", "RestartSelf", "Sleep", "Hibernate", "Logoff", "Shutdown", "ShutdownForce", "Reboot"]

function B(spec, key, en, save) { spec.key = key; if (en) spec.enum = en; if (save) spec.save = save; return spec }
function idx(list, v) { var i = list.indexOf(v); return i < 0 ? 0 : i }
function mask(days) { return DAYNAMES.map(function (d) { return days && days.indexOf(d) >= 0 ? "1" : "0" }).join("") }
var OK = SD.OK, RUN = SD.RUN, WAIT = SD.WAIT, ERR = SD.ERR

// ── 取值与保存 ─────────────────────────────────────────────────────────
function valueOf(spec) {
    if (spec.c === "chips") return DAYNAMES.filter(function (d, i) { return spec.v[i] === "1" })
    if (spec.enum) return spec.enum[spec.v]
    if (spec.c === "num") return Number(spec.v)
    return spec.v
}
function setPath(obj, key, v) {
    var parts = key.split("."), o = obj
    for (var i = 0; i < parts.length - 1; i++) o = o[parts[i]] = o[parts[i]] || {}
    o[parts[parts.length - 1]] = v
}
// 遍历条目里的所有控件 spec：fn(spec, page)
function eachSpec(item, fn) {
    var pages = SD.pages(item)
    function visit(v, page) {
        if (Array.isArray(v)) { v.forEach(function (x) { visit(x, page) }); return }
        if (v && typeof v === "object" && v.c) fn(v, page)
    }
    pages.forEach(function (page) {
        page.blocks.forEach(function (b) {
            if (b.t === "kv") b.rows.forEach(function (r) { visit(r[1], page) })
            else if (b.t === "table") b.rows.forEach(function (r) { r.forEach(function (c) { visit(c, page) }) })
        })
    })
}
// 改动 → [{path, body}]：同一目标的字段合并成一个请求，data 只含改过的字段
function collect(item) {
    var groups = {}, order = []
    eachSpec(item, function (spec, page) {
        if (!spec.dirty || !spec.key) return
        var target = spec.save || page.save
        if (!target) return
        var id = JSON.stringify(target)
        if (!groups[id]) { groups[id] = { path: target.path, body: JSON.parse(JSON.stringify(target.base || {})), data: {} }; order.push(id) }
        setPath(groups[id].data, spec.key, valueOf(spec))
    })
    return order.map(function (id) { var g = groups[id]; g.body.data = g.data; return { path: g.path, body: g.body } })
}
function dirtyCount(item) { var n = 0; eachSpec(item, function (s) { if (s.dirty && s.key) n++ }); return n }
function clearDirty(item) { eachSpec(item, function (s) { s.dirty = false }) }
// 读取某个 k 标记的控件当前值（快速启动等操作用）
function pick(item, k) { var r = null; eachSpec(item, function (s) { if (s.k === k && r === null) r = valueOf(s) }); return r }

// ── 02 托管管理 ───────────────────────────────────────────────────────
function scripts(resp) {
    var out = []
    for (var i = 0; i < resp.index.length; i++) {
        var uid = resp.index[i].uid, c = resp.data[uid]
        if (!c || resp.index[i].type !== "GeneralConfig") continue
        var ur = resp.users && resp.users[uid] ? resp.users[uid] : { index: [], data: {} }
        out.push(general(uid, c, ur, i))
    }
    return out
}
function general(uid, c, ur, i) {
    var I = c.Info, S = c.Script, G = c.Game, R = c.Run
    var save = { path: "/api/scripts/update", base: { scriptId: uid } }
    var gameType = idx(["Emulator", "Client", "URL"], G.Type)
    var users = ur.index.map(function (u) {
        var d = ur.data[u.uid] || { Info: {}, Data: {} }
        var usave = { path: "/api/scripts/user/update", base: { scriptId: uid, userId: u.uid } }
        var rd = d.Info.RemainedDay
        var last = d.Data && d.Data.LastProxyDate && d.Data.LastProxyDate !== "2000-01-01" ? d.Data.LastProxyDate : "—"
        return [d.Info.Name, B(SD.tog(d.Info.Status), "Info.Status", null, usave), rd === -1 || rd === undefined ? "永久" : rd + " 天",
                B(SD.sel(["独立", "共享", "原生"], idx(["independent", "shared", "native"], d.Info.Base)), "Info.Base", ["independent", "shared", "native"], usave), last]
    })
    // icon：启动程序路径，录像带上显示该程序的图标唱片
    return { name: I.Name || "未命名脚本", en: "GENERAL · " + String(i + 1).padStart(2, "0"), live: true, uid: uid, icon: S.ScriptPath || "",
        accounts: ur.index.map(function (u) { return (ur.data[u.uid] && ur.data[u.uid].Info.Name) || "账号" }),
        ops: {
            "删除脚本": { confirm: "将删除脚本「" + I.Name + "」及其全部账号。", path: "/api/scripts/delete", body: { scriptId: uid }, reload: true },
            "添加账号": { path: "/api/scripts/user/add", body: { scriptId: uid }, reload: true, done: "已添加账号" },
            "立即运行": { confirm: "将立即以自动代理模式运行脚本「" + I.Name + "」。", path: "/api/dispatch/start", body: { taskId: uid, mode: "AutoProxy" }, done: "已开始运行" }
        },
        tabs: [
        { name: "程序", api: save.path, save: save, blocks: [
            SD.kv("SCRIPT", [["脚本名称", B(SD.inp(I.Name), "Info.Name"), "Info.Name"], ["根目录", B(SD.path(I.RootPath), "Info.RootPath"), "Info.RootPath"], ["启动程序", B(SD.path(S.ScriptPath), "Script.ScriptPath"), "Script.ScriptPath"], ["启动参数", B(SD.inp(S.Arguments, true), "Script.Arguments"), "Script.Arguments"], ["配置路径", B(SD.path(S.ConfigPath), "Script.ConfigPath"), "Script.ConfigPath"], ["路径类型", B(SD.seg(["文件", "文件夹"], idx(["File", "Folder"], S.ConfigPathMode)), "Script.ConfigPathMode", ["File", "Folder"]), "Script.ConfigPathMode"], ["回写配置", B(SD.seg(["从不", "成功时", "失败时", "总是"], idx(["Never", "Success", "Failure", "Always"], S.UpdateConfigMode)), "Script.UpdateConfigMode", ["Never", "Success", "Failure", "Always"]), "Script.UpdateConfigMode"]]),
            SD.kv("PROCESS", [["追踪进程", B(SD.tog(S.IfTrackProcess), "Script.IfTrackProcess"), "Script.IfTrackProcess"], ["进程名", B(SD.inp(S.TrackProcessName, true), "Script.TrackProcessName"), "Script.TrackProcessName"], ["清理范围", B(SD.seg(["跨会话强力", "仅本轮", "当前会话"], idx(["Force", "Tracked", "Session"], S.TaskKillMode)), "Script.TaskKillMode", ["Force", "Tracked", "Session"]), "Script.TaskKillMode"]])
        ], actions: ["保存", "立即运行", "删除脚本"] },
        { name: "判定", api: save.path, save: save, blocks: [
            SD.kv("LOG FILE", [["日志路径", B(SD.path(S.LogPath), "Script.LogPath"), "Script.LogPath"], ["路径日期格式", B(SD.inp(S.LogPathFormat, true), "Script.LogPathFormat"), "Script.LogPathFormat"], ["时间戳位置", [B(SD.num(S.LogTimeStart), "Script.LogTimeStart"), SD.unit("至"), B(SD.num(S.LogTimeEnd), "Script.LogTimeEnd"), SD.unit("列")], "Script.LogTimeStart / LogTimeEnd"], ["时间格式", B(SD.inp(S.LogTimeFormat, true), "Script.LogTimeFormat"), "Script.LogTimeFormat"]]),
            SD.kv("MATCH", [["成功判定", [B(SD.inp(S.SuccessLog), "Script.SuccessLog"), B(SD.seg(["关键字", "正则"], idx(["Split", "Regex"], S.SuccessLogMode)), "Script.SuccessLogMode", ["Split", "Regex"])], "Script.SuccessLog / SuccessLogMode"], ["失败判定", [B(SD.inp(S.ErrorLog), "Script.ErrorLog"), B(SD.seg(["关键字", "正则"], idx(["Split", "Regex"], S.ErrorLogMode)), "Script.ErrorLogMode", ["Split", "Regex"])], "Script.ErrorLog / ErrorLogMode"], ["日志预处理", B(SD.tog(S.LogHookEnabled), "Script.LogHookEnabled"), "Script.LogHookEnabled"], ["推送日志", B(SD.tog(S.PushLogEnabled), "Script.PushLogEnabled"), "Script.PushLogEnabled"]]),
            SD.note("关键字模式用「|」分隔多个子串，任一命中即判定；正则模式按整行匹配。预处理先于判定执行。")
        ], actions: ["保存"] },
        { name: "游戏", api: save.path, save: save, blocks: [
            SD.kv("GAME", [["随脚本启动游戏", B(SD.tog(G.Enabled), "Game.Enabled"), "Game.Enabled"], ["启动方式", B(SD.seg(["模拟器", "客户端", "URL 协议"], gameType), "Game.Type", ["Emulator", "Client", "URL"]), "Game.Type"], ["游戏路径", B(SD.path(G.Path), "Game.Path"), "Game.Path"], ["协议地址", B(SD.inp(G.URL, true), "Game.URL"), "Game.URL"], ["进程名", B(SD.inp(G.ProcessName, true), "Game.ProcessName"), "Game.ProcessName"], ["启动参数", B(SD.inp(G.Arguments, true), "Game.Arguments"), "Game.Arguments"], ["启动后等待", B(SD.num(G.WaitTime, "秒"), "Game.WaitTime"), "Game.WaitTime"], ["结束后强制关闭", B(SD.tog(G.IfForceClose), "Game.IfForceClose"), "Game.IfForceClose"]]),
            SD.kv("EMULATOR", [["模拟器", G.EmulatorId === "-" ? "未选择" : G.EmulatorId, "Game.EmulatorId"], ["实例", G.EmulatorIndex === "-" ? "未选择" : G.EmulatorIndex, "Game.EmulatorIndex"]])
        ], actions: ["保存"] },
        { name: "限制", api: save.path, save: save, blocks: [
            SD.kv("RUN LIMIT", [["单账号总时限", B(SD.num(R.HardTimeLimit, "分钟"), "Run.HardTimeLimit"), "Run.HardTimeLimit"], ["单次运行时限", B(SD.num(R.RunTimeLimit, "分钟"), "Run.RunTimeLimit"), "Run.RunTimeLimit"], ["单次重试次数", B(SD.num(R.RunTimesLimit, "次"), "Run.RunTimesLimit"), "Run.RunTimesLimit"], ["每日代理上限", B(SD.num(R.ProxyTimesLimit, "次 · 0 为不限"), "Run.ProxyTimesLimit"), "Run.ProxyTimesLimit"]]),
            SD.note("总时限包含等待游戏与全部重试；单次超时会先按清理清单结束进程，再按重启清单补跑。")
        ], actions: ["保存"] },
        { name: "账号", api: "POST /api/scripts/user/update", blocks: [
            SD.table("USERS", ["名称", "启用", "剩余天数", "配置来源", "上次代理"], users.slice(0, 9), [1.8, 1, 1, 1.2, 1.2]),
            SD.note(users.length > 9 ? "共 " + users.length + " 个账号，这里列出前 9 个。" : "配置来源：独立 = 账号单独一份脚本配置；共享 = 与同脚本账号共用；原生 = 直接使用脚本自身配置。")
        ], actions: ["保存", "添加账号"] }
    ] }
}

// ── 04 调度队列 ───────────────────────────────────────────────────────
// scriptOpts：[{label, value}]（/api/info/combox/script）
function queues(qresp, times, qitems, scriptOpts, scriptPaths) {
    scriptPaths = scriptPaths || {}
    var names = scriptOpts.map(function (o) { return o.label.replace(/^通用 - /, "") }), values = scriptOpts.map(function (o) { return o.value })
    var power = ["NoAction", "KillSelf", "RestartSelf", "Sleep", "Hibernate", "Logoff", "Shutdown", "ShutdownForce", "Reboot"]
    return qresp.index.map(function (q, i) {
        var qid = q.uid, I = qresp.data[qid].Info
        var save = { path: "/api/queue/update", base: { queueId: qid } }
        var ts = times[qid] || { index: [], data: {} }, it = qitems[qid] || { index: [], data: {} }
        var trows = ts.index.map(function (t) {
            var d = ts.data[t.uid].Info, s = { path: "/api/queue/time/update", base: { queueId: qid, timeSetId: t.uid } }
            return [B(SD.tog(d.Enabled), "Info.Enabled", null, s), B(SD.chips(mask(d.Days)), "Info.Days", null, s), B(SD.time(d.Time), "Info.Time", null, s)]
        })
        var irows = it.index.map(function (t) {
            var d = it.data[t.uid], s = { path: "/api/queue/item/update", base: { queueId: qid, queueItemId: t.uid } }
            var sc = d.Schedule, interval = sc.Mode === "interval"
            var next = sc.NextRunAt && sc.NextRunAt.indexOf("2000-01-01") !== 0 ? sc.NextRunAt.slice(5, 16) : "—"
            return [B(SD.sel(names, idx(values, d.Info.ScriptId)), "Info.ScriptId", values, s), B(SD.tog(sc.Enabled), "Schedule.Enabled", null, s),
                    B(SD.seg(["定时", "间隔"], interval ? 1 : 0), "Schedule.Mode", ["fixed_time", "interval"], s),
                    interval ? B(SD.num(sc.IntervalMinutes, "分钟"), "Schedule.IntervalMinutes", null, s) : B(SD.time(sc.Time), "Schedule.Time", null, s), next]
        })
        // 3D 阵列：列内各行 = 队列配置 + 各队列项（以所选脚本的启动程序图标作唱片）
        var rowNames = it.index.map(function (t) { var sid = it.data[t.uid].Info.ScriptId; return sid && values.indexOf(sid) >= 0 ? names[values.indexOf(sid)] : "未选择脚本" })
        var rowIcons = it.index.map(function (t) { return scriptPaths[it.data[t.uid].Info.ScriptId] || "" })
        return { name: I.Name, en: (I.CycleEnabled ? "QUEUE · CYCLE · " : "QUEUE · ") + String(i + 1).padStart(2, "0"), live: true, uid: qid,
            icon: "", accounts: rowNames, rowIcons: rowIcons, configRow: false,
            exclusive: I.CycleEnabled ? "cycle" : I.TimeEnabled ? "time" : "",
            ops: {
                "立即运行": { confirm: "将立即运行队列「" + I.Name + "」。", path: "/api/dispatch/start", body: { taskId: qid, mode: I.CycleEnabled ? "CycleRun" : "AutoProxy" }, done: "已开始运行" },
                "删除队列": { confirm: "将删除队列「" + I.Name + "」及其定时和队列项。", path: "/api/queue/delete", body: { queueId: qid }, reload: true },
                "添加定时": { path: "/api/queue/time/add", body: { queueId: qid }, reload: true, done: "已添加定时" },
                "添加脚本": { path: "/api/queue/item/add", body: { queueId: qid }, reload: true, done: "已添加队列项" }
            },
            tabs: [
            { name: "调度", api: save.path, save: save, blocks: [
                SD.kv("SCHEDULE", [["队列名称", B(SD.inp(I.Name), "Info.Name"), "Info.Name"], ["定时启动", B(SD.tog(I.TimeEnabled, "time"), "Info.TimeEnabled"), "Info.TimeEnabled"], ["循环队列", B(SD.tog(I.CycleEnabled, "cycle"), "Info.CycleEnabled"), "Info.CycleEnabled"], ["启动时运行", B(SD.seg(["从不", "每次", "每日首次"], idx(["Never", "Always", "DailyFirst"], I.StartUpMode)), "Info.StartUpMode", ["Never", "Always", "DailyFirst"]), "Info.StartUpMode"], ["完成后", B(SD.sel(SD.POWER, idx(power, I.AfterAccomplish)), "Info.AfterAccomplish", power), "Info.AfterAccomplish"], ["延时执行", B(SD.num(I.AfterAccomplishDelay, "分钟"), "Info.AfterAccomplishDelay"), "Info.AfterAccomplishDelay"]]),
                SD.kv("HOOKS", [["运行前脚本", B(SD.tog(I.IfScriptBeforeTask), "Info.IfScriptBeforeTask"), "Info.IfScriptBeforeTask"], ["前脚本路径", B(SD.path(I.ScriptBeforeTask), "Info.ScriptBeforeTask"), "Info.ScriptBeforeTask"], ["运行后脚本", B(SD.tog(I.IfScriptAfterTask), "Info.IfScriptAfterTask"), "Info.IfScriptAfterTask"], ["后脚本路径", B(SD.path(I.ScriptAfterTask), "Info.ScriptAfterTask"), "Info.ScriptAfterTask"]])
            ], actions: ["保存", "立即运行", "删除队列"] },
            { name: "定时", api: "POST /api/queue/time/update", blocks: [
                SD.table("TIME SET", ["启用", "周期", "时间"], trows.slice(0, 9), [1, 2.6, 1]),
                SD.note(I.CycleEnabled ? "循环队列与定时启动互斥：开启循环后，按「队列项」中各脚本自己的周期持续运行。" : "同一队列可设置多个定时；周期为空时该定时不会触发。")
            ], actions: ["保存", "添加定时"] },
            { name: "队列项", api: "POST /api/queue/item/update", blocks: [
                (function () { var t = SD.table("ITEMS", ["脚本", "参与循环", "方式", "时间 / 间隔", "下次运行"], irows.slice(0, 12), [2.4, 1.1, 1.4, 1.3, 1]); t.all = irows; t.offset = 0; return t })(),
                SD.note(irows.length > 10 ? "共 " + irows.length + " 项，这里列出前 10 项。「参与循环」「方式」「间隔」只在循环队列中生效。" : "「参与循环」「方式」「间隔」只在循环队列中生效；间隔可从上次开始或上次结束计时。")
            ], actions: ["保存", "添加脚本"] }
        ] }
    })
}

// ── 03 模拟器管理 ─────────────────────────────────────────────────────
function emulators(eresp, sresp) {
    var types = ["general", "mumu", "ldplayer", "emulator2"]
    return eresp.index.map(function (e, i) {
        var eid = e.uid, I = eresp.data[eid].Info
        var save = { path: "/api/emulator/update", base: { emulatorId: eid } }
        var devs = sresp && sresp.code === 200 && sresp.data[eid] ? sresp.data[eid] : null
        var rows = devs ? Object.keys(devs).map(function (k) {
            var d = devs[k], running = d.status === 0 || d.status === 2
            return [d.title, [OK, ERR, RUN, WAIT][d.status] || WAIT, SD.inp(d.adb_address, true),
                    { c: "mini", names: [running ? "关闭" : "启动", "显示"], ops: [
                        { path: "/api/emulator/operate", body: { emulatorId: eid, operate: running ? "close" : "open", index: k }, reload: true },
                        { path: "/api/emulator/operate", body: { emulatorId: eid, operate: "show", index: k } }] }]
        }) : []
        var cfg = [["名称", B(SD.inp(I.Name), "Info.Name"), "Info.Name"], ["类型", B(SD.seg(["通用", "MuMu", "雷电", "2.0"], idx(types, I.Type)), "Info.Type", types), "Info.Type"], ["安装路径", B(SD.path(I.Path), "Info.Path"), "Info.Path"], ["最大等待", B(SD.num(I.MaxWaitTime, "秒"), "Info.MaxWaitTime"), "Info.MaxWaitTime"], ["关闭时清理残留", B(SD.tog(I.ForceKillOnClose), "Info.ForceKillOnClose"), "Info.ForceKillOnClose"], ["启动前关闭全部", B(SD.tog(I.ForceKillBeforeLaunch), "Info.ForceKillBeforeLaunch"), "Info.ForceKillBeforeLaunch"]]
        if (I.Type === "emulator2") cfg.push(["稳定模式", B(SD.tog(I.StableMode), "Info.StableMode"), "Info.StableMode"], ["配置守卫", B(SD.tog(I.ConfigGuard), "Info.ConfigGuard"), "Info.ConfigGuard"])
        return { name: I.Name.replace(/\s*\(.*\)$/, ""), en: "EMULATOR · " + I.Type.toUpperCase(), live: true, uid: eid,
            ops: { "删除": { confirm: "将删除模拟器配置「" + I.Name + "」（不会卸载模拟器本体）。", path: "/api/emulator/delete", body: { emulatorId: eid }, reload: true }, "刷新设备": { reload: true } },
            tabs: [
            { name: "设备", api: "POST /api/emulator/operate", blocks: devs ? [
                SD.table("DEVICES", ["名称", "状态", "ADB 地址", "操作"], rows.slice(0, 9)),
                SD.stats("SUMMARY", [["实例", String(rows.length)], ["运行中", String(rows.filter(function (r) { return r[1] === OK || r[1] === RUN }).length)], ["类型", I.Type]])
            ] : [SD.kv("STATUS", [["设备状态", [ERR, "读取失败"]]]), SD.note(sresp && sresp.message ? sresp.message : "无法读取设备状态", true)],
              actions: ["刷新设备"] },
            { name: "配置", api: save.path, save: save, blocks: [SD.kv("CONFIG", cfg)], actions: ["保存", "删除"] }
        ] }
    })
}

// ── 10 设置 / 06 本地控制（GlobalConfig） ─────────────────────────────
function settings(g, version) {
    var save = { path: "/api/setting/update", base: {} }, api = "POST /api/setting/update"
    var F = g.Function, N = g.Notify, U = g.Update, R = g.Replay
    var keep = [7, 15, 30, 60, 90, 180, 365, 0]
    return [
        { name: "启动与界面", en: "START · UI", live: true, api: api, save: save, blocks: [SD.kv("START", [["开机自启", B(SD.tog(g.Start.IfSelfStart), "Start.IfSelfStart"), "Start.IfSelfStart"], ["启动后最小化", B(SD.tog(g.Start.IfMinimizeDirectly), "Start.IfMinimizeDirectly"), "Start.IfMinimizeDirectly"], ["显示托盘图标", B(SD.tog(g.UI.IfShowTray), "UI.IfShowTray"), "UI.IfShowTray"], ["关闭到托盘", B(SD.tog(g.UI.IfToTray), "UI.IfToTray"), "UI.IfToTray"], ["隐藏关闭按钮", B(SD.tog(g.UI.IfHideCloseButton), "UI.IfHideCloseButton"), "UI.IfHideCloseButton"], ["主题", SD.segk(["跟随系统", "浅色", "深色"], 0, "theme"), "客户端设置"], ["动态效果", SD.segk(["减少", "标准", "增强"], 1, "motion"), "客户端设置"]])], actions: ["保存"] },
        { name: "功能", en: "FUNCTION", live: true, api: api, save: save, blocks: [SD.kv("BEHAVIOR", [["历史记录保留", B(SD.sel(["7 天", "15 天", "30 天", "60 天", "90 天", "180 天", "365 天", "永久"], idx(keep, F.HistoryRetentionTime)), "Function.HistoryRetentionTime", keep), "Function.HistoryRetentionTime"], ["运行时允许睡眠", B(SD.tog(F.IfAllowSleep), "Function.IfAllowSleep"), "Function.IfAllowSleep"], ["静默模式", B(SD.tog(F.IfSilence), "Function.IfSilence"), "Function.IfSilence"], ["屏蔽模拟器广告", B(SD.tog(F.IfBlockAd), "Function.IfBlockAd"), "Function.IfBlockAd"], ["匿名遥测", B(SD.tog(F.IfEnableTelemetry), "Function.IfEnableTelemetry"), "Function.IfEnableTelemetry"], ["语音提示", B(SD.tog(g.Voice.Enabled), "Voice.Enabled"), "Voice.Enabled"], ["语音风格", B(SD.seg(["简洁", "热闹"], idx(["simple", "noisy"], g.Voice.Type)), "Voice.Type", ["simple", "noisy"]), "Voice.Type"]])], actions: ["保存"] },
        { name: "通知", en: "NOTIFY", live: true, api: api, save: save, blocks: [SD.kv("CHANNELS", [["任务结果推送", B(SD.seg(["不推送", "任何时刻", "仅失败时"], idx(["不推送", "任何时刻", "仅失败时"], N.SendTaskResultTime)), "Notify.SendTaskResultTime", ["不推送", "任何时刻", "仅失败时"]), "Notify.SendTaskResultTime"], ["发送统计", B(SD.tog(N.IfSendStatistic), "Notify.IfSendStatistic"), "Notify.IfSendStatistic"], ["系统通知", B(SD.tog(N.IfPushPlyer), "Notify.IfPushPlyer"), "Notify.IfPushPlyer"], ["邮件", B(SD.tog(N.IfSendMail), "Notify.IfSendMail"), "Notify.IfSendMail"], ["Server 酱", B(SD.tog(N.IfServerChan), "Notify.IfServerChan"), "Notify.IfServerChan"], ["Koishi", B(SD.tog(N.IfKoishiSupport), "Notify.IfKoishiSupport"), "Notify.IfKoishiSupport"], ["OpenClaw QQ", B(SD.tog(N.IfOpenClawQQ), "Notify.IfOpenClawQQ"), "Notify.IfOpenClawQQ"]])],
          ops: { "测试通知": { path: "/api/setting/test_notify", body: {}, done: "已发送测试通知" } }, actions: ["保存", "测试通知"] },
        { name: "更新", en: "UPDATE", live: true, api: api, save: save, blocks: [SD.kv("UPDATE", [["当前版本", version || "—"], ["自动更新", B(SD.tog(U.IfAutoUpdate), "Update.IfAutoUpdate"), "Update.IfAutoUpdate"], ["更新源", B(SD.sel(["GitHub", "Mirror 酱", "AutoSite", "CNB"], idx(["GitHub", "MirrorChyan", "AutoSite", "CNB"], U.Source)), "Update.Source", ["GitHub", "MirrorChyan", "AutoSite", "CNB"]), "Update.Source"], ["更新渠道", B(SD.seg(["稳定版", "测试版"], idx(["stable", "beta"], U.Channel)), "Update.Channel", ["stable", "beta"]), "Update.Channel"], ["GitHub 加速", B(SD.seg(["自动", "关闭"], idx(["Auto", "Off"], U.GitHubMirror)), "Update.GitHubMirror", ["Auto", "Off"]), "Update.GitHubMirror"], ["代理地址", B(SD.inp(U.ProxyAddress, true), "Update.ProxyAddress"), "Update.ProxyAddress"]])], actions: ["保存"] },
        { name: "录像回放", en: "REPLAY · OBS", live: true, api: api, save: save, blocks: [SD.kv("OBS", [["任务录像", B(SD.tog(R.Enabled), "Replay.Enabled"), "Replay.Enabled"], ["OBS 端口", B(SD.num(R.Port), "Replay.Port"), "Replay.Port"], ["最多保留", B(SD.num(R.MaxReplayCount, "段"), "Replay.MaxReplayCount"), "Replay.MaxReplayCount"], ["密码", R.PasswordConfigured ? "已设置" : "未设置"]]), SD.note("通过 OBS WebSocket 录制每个账号的任务过程，可在历史记录中回看。")],
          ops: { "检查连接": { path: "/api/setting/obs/check", body: {}, done: "OBS 连接正常" } }, actions: ["保存", "检查连接"] },
        { name: "高级与关于", en: "ADVANCED", live: true, api: "POST /api/setting/backup", blocks: [SD.kv("ABOUT", [["版本", version || "—"], ["字体", "MiSans（小米）· 许可见 NOTICE"], ["视觉参考", "LBEILC / RhineLabUI（MIT）"]])], actions: [] }
    ]
}
function local(g, port) {
    var save = { path: "/api/setting/update", base: {} }, api = "POST /api/setting/update"
    var C = g.ChildSession, D = g.Display, H = g.Hotkey
    var res = ["2560x1440", "1920x1080", "1600x900"]
    if (res.indexOf(C.Resolution) < 0) res.unshift(C.Resolution)
    return [
        { name: "远程桌面分身", en: "CHILD SESSION · RDP", live: true, api: api, save: save, blocks: [
            SD.kv("CHILD SESSION", [["启用分身执行", B(SD.tog(C.Enabled), "ChildSession.Enabled"), "ChildSession.Enabled"], ["宿主端口", B(SD.num(C.HostPort), "ChildSession.HostPort"), "ChildSession.HostPort"], ["分辨率", B(SD.sel(res, res.indexOf(C.Resolution)), "ChildSession.Resolution", res), "ChildSession.Resolution"], ["启动时隐藏预览", B(SD.tog(C.StartHidden), "ChildSession.StartHidden"), "ChildSession.StartHidden"], ["观看模式", B(SD.tog(C.WatchMode), "ChildSession.WatchMode"), "ChildSession.WatchMode"]]),
            SD.note("观看模式会屏蔽本机键鼠进入分身，避免误触打断任务。")
        ], actions: ["保存"] },
        { name: "虚拟显示器", en: "VIRTUAL DISPLAY", live: true, api: api, save: save, blocks: [
            SD.kv("DISPLAY", [["无人值守时挂载", B(SD.tog(D.IfEnableVirtualDisplay), "Display.IfEnableVirtualDisplay"), "Display.IfEnableVirtualDisplay"], ["刷新率", B(SD.seg(["1920×1080 @60", "1920×1080 @30"], idx(["1920x1080@60", "1920x1080@30"], D.VirtualDisplayMode)), "Display.VirtualDisplayMode", ["1920x1080@60", "1920x1080@30"]), "Display.VirtualDisplayMode"]]),
            SD.note("所有真实显示输出断开后，挂一块 1920×1080 的虚拟屏，避免游戏窗口被压小。驱动需自行安装。")
        ], ops: { "检测": { path: "/api/setting/virtual-display/check", body: {}, show: true } }, actions: ["保存", "检测"] },
        { name: "全局热键", en: "HOTKEY", live: true, api: api, save: save, blocks: [
            SD.kv("BINDINGS", [["启用全局热键", B(SD.tog(H.Enabled), "Hotkey.Enabled"), "Hotkey.Enabled"], ["启动 / 停止", B(SD.inp(H.ToggleStartStop, true), "Hotkey.ToggleStartStop"), "Hotkey.ToggleStartStop"], ["上一个托管", B(SD.inp(H.PreviousTask, true), "Hotkey.PreviousTask"), "Hotkey.PreviousTask"], ["下一个托管", B(SD.inp(H.NextTask, true), "Hotkey.NextTask"), "Hotkey.NextTask"]])
        ], ops: { "保存并重新加载": { saveFirst: true, path: "/api/dispatch/hotkey/reload", body: {}, done: "热键已重新加载" } }, actions: ["保存并重新加载"] },
        { name: "连接端口", en: "HOST", live: true, api: "GET /api/core/health", blocks: [SD.kv("PORTS", [["后端端口", String(port)], ["后端状态", [OK, "已连接"]]])], actions: [] }
    ]
}

// ── 07 签到 ───────────────────────────────────────────────────────────
function sign(tools, accounts) {
    var G = tools.GameSign, save = { path: "/api/tools/update", base: {} }
    var ids = accounts.instances || []
    function has(t) { return t && t.indexOf("损坏") < 0 }
    var rows = ids.map(function (a) {
        var d = accounts[a.uid].GameSignAccount, s = { path: "/api/tools/sign/account/update", base: { accountId: a.uid } }
        return [d.Name, B(SD.tog(d.Enabled), "Enabled", null, s), has(d.MiyousheToken) ? OK : WAIT, has(d.SklandToken) ? OK : d.SklandToken ? ERR : WAIT, has(d.KuroToken) ? OK : WAIT, has(d.TaygedoToken) ? OK : WAIT]
    })
    var results = []
    try {
        var r = JSON.parse(G.Result || "{}")
        Object.keys(r).forEach(function (plat) {
            (r[plat] || []).forEach(function (acc) {
                var games = acc.games || []
                var bad = games.filter(function (x) { return x.success === false || x.status === "failed" }).length
                results.push([plat, acc.account_alias || "—", bad ? ERR : OK, games.length + " 项"])
            })
        })
    } catch (e) {}
    var status = ""
    try { status = JSON.parse(G.Status || "{}").text || "" } catch (e) {}
    return [
        { name: "签到设置", en: "SIGN", live: true, api: "POST /api/tools/update", save: save, blocks: [SD.kv("SIGN", [["启用签到", B(SD.tog(G.Enabled), "GameSign.Enabled"), "GameSign.Enabled"], ["启动时签到", B(SD.tog(G.RunOnStartup), "GameSign.RunOnStartup"), "GameSign.RunOnStartup"], ["每日自动签到", B(SD.tog(G.AutoStart), "GameSign.AutoStart"), "GameSign.AutoStart"], ["结果通知", B(SD.tog(G.NotifyEnabled), "GameSign.NotifyEnabled"), "GameSign.NotifyEnabled"], ["活动查询", B(SD.tog(G.ActivityEnabled), "GameSign.ActivityEnabled"), "GameSign.ActivityEnabled"], ["上次签到", (G.LastSignDate || "—") + (status ? " · " + status : "")]])],
          ops: { "立即签到": { confirm: "将立即为所有启用的账号组执行签到。", path: "/api/tools/sign", body: {}, done: "签到已开始", reload: true } }, actions: ["保存", "立即签到"] },
        { name: "账号组", en: "ACCOUNTS", live: true, api: "POST /api/tools/sign/account/update", blocks: [SD.table("GROUPS", ["账号组", "启用", "米游社", "森空岛", "库街区", "塔吉多"], rows.slice(0, 9)), SD.note("各平台凭据通过扫码登录写入账号组；「异常」表示凭据已损坏，需要重新登录。")], actions: ["保存"] },
        { name: "签到结果", en: "RESULT", live: true, api: "GET /api/tools/get", blocks: results.length ? [SD.table("LAST RUN", ["平台", "账号组", "结果", "内容"], results.slice(0, 10))] : [SD.note("暂无签到结果。")], actions: [] }
    ]
}

// ── 08 历史记录 ───────────────────────────────────────────────────────
function history(resp, filter) {
    var data = resp && resp.data ? resp.data : {}
    var dates = Object.keys(data).sort().reverse()
    var total = 0, okN = 0, errN = 0
    var items = dates.slice(0, 20).map(function (date) {
        var users = data[date], rows = []
        Object.keys(users).forEach(function (u) {
            (users[u].index || []).forEach(function (h) {
                total++
                if (h.status === "DONE") okN++
                else if (h.status === "ERROR") errN++
                rows.push([h.date.slice(11, 16) || h.date, u, h.status === "DONE" ? OK : h.status === "ERROR" ? ERR : WAIT, h.result || ""])
            })
        })
        return { name: date, en: "HISTORY", live: true, api: "POST /api/history/search", blocks: [
            SD.stats("SUMMARY", [["记录", String(rows.length)], ["成功", String(rows.filter(function (r) { return r[2] === OK }).length)], ["异常", String(rows.filter(function (r) { return r[2] === ERR }).length)]]),
            SD.table("RECORDS", ["时间", "账号", "结果", "说明"], rows.slice(0, 9))], actions: [] }
    })
    var q = { name: "查询", en: "SEARCH", live: true, api: "POST /api/history/search", blocks: [
        SD.kv("FILTER", [["开始日期", { c: "date", v: filter.start, k: "start" }, "start_date"], ["结束日期", { c: "date", v: filter.end, k: "end" }, "end_date"], ["合并方式", { c: "seg", opts: ["按日", "按周", "按月"], v: filter.mode, k: "mode", enum: ["DAILY", "WEEKLY", "MONTHLY"] }, "mode"]]),
        SD.stats("RANGE", [["记录", String(total)], ["成功", String(okN)], ["异常", String(errN)]]),
        SD.note(dates.length ? "" : "这个时间范围内没有历史记录。", !dates.length)
    ], ops: { "查询": { query: true } }, actions: ["查询"] }
    return [q].concat(items)
}

// ── 01 主页 / 05 调度中心 ─────────────────────────────────────────────
function home(taskOpts, snapshot, power) {
    var opts = taskOpts.filter(function (o) { return o.value })
    var labels = opts.map(function (o) { return o.label }), values = opts.map(function (o) { return o.value })
    var tasks = snapshot && snapshot.tasks ? snapshot.tasks : []
    return [
        { name: "快速启动", en: "QUICK START", live: true, api: "POST /api/dispatch/start", blocks: [
            SD.kv("START", [["任务对象", { c: "sel", opts: labels.length ? labels : ["没有可运行的任务"], v: 0, k: "task", enum: values }, "taskId"], ["运行模式", { c: "seg", opts: ["自动代理", "设置脚本", "循环运行"], v: 0, k: "mode", enum: ["AutoProxy", "ScriptConfig", "CycleRun"] }, "mode"], ["完成后", { c: "sel", opts: SD.POWER, v: idx(POWER_EN, power), k: "power", enum: POWER_EN }, "POST /api/dispatch/set/power"]]),
            SD.stats("NOW", [["运行中任务", String(tasks.length)], ["可运行对象", String(opts.length)], ["完成后", SD.POWER[idx(POWER_EN, power)]]]),
            { t: "run", title: "RUN STATUS" }
        ], ops: { "开始执行": { start: true }, "停止": { stopAll: true } }, actions: ["开始执行", "停止"] },
        { name: "代理状态", en: "PROXY STATUS", live: true, api: "GET /api/dispatch/runtime-snapshot", blocks: [
            SD.stats("NOW", [["运行中任务", String(tasks.length)], ["定时关联脚本", String((snapshot.scheduledScripts || []).length)], ["正在停止", String(tasks.filter(function (t) { return t.stopping }).length)]]),
            tasks.length ? SD.table("TASKS", ["任务", "模式", "状态"], tasks.slice(0, 9).map(function (t) { return [t.taskId.slice(0, 8), t.mode, t.stopping ? WAIT : RUN] })) : SD.note("当前没有运行中的任务。")
        ], ops: { "刷新": { reload: true } }, actions: ["刷新"] }
    ]
}
// ── 05 调度中心：每个运行中的任务（通常是一条队列）一张卡，第一张是总览 ──────────
var STATUS_TAG = { "完成": OK, "运行": RUN, "等待": WAIT, "异常": ERR, "跳过": SD.tag("跳过", "idle"), "已暂停": SD.tag("已暂停", "idle"), "外部占用，等待释放": SD.tag("外部占用", "idle"), "任务被用户手动中止": SD.tag("已中止", "err") }
function statusTag(s) { return STATUS_TAG[s] || SD.tag(s || "—", "idle") }
function taskProgress(t) {
    var list = t.task_info || [], done = 0
    for (var i = 0; i < list.length; i++) if (["完成", "跳过", "异常"].indexOf(list[i].status) >= 0) done++
    var cur = null
    for (var j = 0; j < list.length; j++) if (list[j].status === "运行") { cur = list[j]; break }
    return { done: done, total: list.length, current: cur }
}
function logLines(text, max) {
    var lines = String(text || "").split(/\r?\n/).filter(function (x) { return x.trim() !== "" }).slice(-max)
    return lines.map(function (x) {
        var m = x.match(/^(\S+\s+\S+|\S+)\s+(.*)$/)
        var kind = /异常|错误|失败|ERROR/i.test(x) ? "e" : /完成|成功|SUCCESS/i.test(x) ? "s" : ""
        return m && /\d{1,2}:\d{2}/.test(m[1]) ? [m[1].slice(-8), m[2], kind] : ["", x, kind]
    })
}
function dispatchCenter(snapshot, queueNames) {
    queueNames = queueNames || {}
    var tasks = snapshot && snapshot.tasks ? snapshot.tasks : []
    var api = "GET /api/dispatch/runtime-snapshot"
    if (!tasks.length) return [{ name: "调度空闲", en: "IDLE", live: true, api: api, blocks: [SD.kv("TASK", [["状态", [WAIT, "没有运行中的任务"]], ["定时关联脚本", String((snapshot.scheduledScripts || []).length) + " 个"]])], ops: { "刷新": { reload: true } }, actions: ["刷新"] }]
    function title(t, i) { return t.queueId && queueNames[t.queueId] ? queueNames[t.queueId] : (t.mode === "ScriptConfig" ? "脚本设置" : t.mode === "Update" ? "更新" : "任务 " + String(i + 1).padStart(2, "0")) }
    // 总览：所有同时运行的任务并排列出，一眼看到各自进行到哪
    var overview = { name: "总览", en: "OVERVIEW · " + tasks.length + " RUNNING", live: true, api: api, blocks: [
        SD.stats("RUNNING", [["运行中", String(tasks.filter(function (t) { return !t.stopping }).length)], ["正在停止", String(tasks.filter(function (t) { return t.stopping }).length)],
            ["循环队列", String(tasks.filter(function (t) { return t.isCycle }).length)], ["定时关联脚本", String((snapshot.scheduledScripts || []).length)]]),
        SD.table("TASKS", ["队列 / 任务", "当前脚本", "进度", "状态"], tasks.map(function (t, i) {
            var p = taskProgress(t)
            return [title(t, i) + (t.isCycle ? " · 循环" : ""), p.current ? p.current.name : "—", p.done + " / " + p.total, t.stopping ? [WAIT, "正在停止"] : p.current ? RUN : WAIT]
        }), [2, 2, 0.9, 1.1])
    ], ops: { "刷新": { reload: true }, "全部停止": { confirm: "将停止全部 " + tasks.length + " 个运行中的任务。", path: "/api/dispatch/stop", body: { taskId: "ALL" }, reload: true } }, actions: ["刷新", "全部停止"] }
    return [overview].concat(tasks.map(function (t, i) {
        var p = taskProgress(t)
        var scripts = (t.task_info || []).map(function (s) {
            var users = s.userList || [], ud = users.filter(function (u) { return u.status === "完成" }).length
            var cu = users.filter(function (u) { return u.status === "运行" })[0]
            return [s.name, statusTag(s.status), users.length ? ud + " / " + users.length : "—", cu ? cu.name : "—"]
        })
        var tabs = [
            { name: "执行", api: api, blocks: [
                SD.kv("TASK", [["队列", title(t, i)], ["模式", t.mode + (t.isCycle ? " · 循环" : "")], ["状态", t.stopping ? [WAIT, "正在停止"] : [RUN, "运行中"]],
                    ["当前脚本", p.current ? p.current.name : "—"], ["进度", p.done + " / " + p.total + " 个脚本"]]),
                SD.table("SCRIPTS", ["脚本", "状态", "账号", "当前账号"], scripts.slice(0, 9), [2.4, 1, 0.8, 1.4])
            ], actions: ["停止任务", "上一个托管", "下一个托管"] },
            { name: "日志", api: api, blocks: [SD.log("LOG · " + (p.current ? p.current.name : title(t, i)), logLines(t.log, 22), true)], actions: ["停止任务"] }
        ]
        if (t.isCycle && (t.cycleNextList || []).length)
            tabs.push({ name: "循环", api: api, blocks: [SD.table("NEXT", ["脚本", "下次运行", "状态"], t.cycleNextList.slice(0, 10).map(function (c) {
                return [c.scriptName, c.nextRunAt.slice(5, 16), c.isRunning ? RUN : c.isDue ? SD.tag("到点", "run") : WAIT]
            }), [2.4, 1.4, 1])], actions: ["停止任务"] })
        return { name: title(t, i), en: t.mode.toUpperCase() + (t.isCycle ? " · CYCLE" : "") + " · " + String(i + 1).padStart(2, "0"), live: true,
            ops: { "停止任务": { confirm: "将停止「" + title(t, i) + "」。", path: "/api/dispatch/stop", body: { taskId: t.taskId }, reload: true },
                   "上一个托管": { path: "/api/dispatch/navigation/previous", body: {} }, "下一个托管": { path: "/api/dispatch/navigation/next", body: {} } },
            tabs: tabs }
    }))
}
