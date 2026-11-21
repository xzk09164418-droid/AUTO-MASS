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
    if (spec.bossKey) return JSON.stringify(spec.v.trim() ? [spec.v.trim()] : [])
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
        if (spec.skipEmpty && spec.v === "") return        // 留空表示不修改（如已设置的密码）
        var target = spec.save || page.save
        if (!target) return
        var id = JSON.stringify(target)
        if (!groups[id]) { groups[id] = { path: target.path, body: JSON.parse(JSON.stringify(target.base || {})), data: {} }; order.push(id) }
        setPath(groups[id].data, spec.key, valueOf(spec))
    })
    return order.map(function (id) { var g = groups[id]; g.body.data = g.data; return { path: g.path, body: g.body } })
}
function fieldValue(item,key) {
    var result = null
    eachSpec(item, function(spec) { if (spec.key === key) result=valueOf(spec) })
    return result
}
function dirtyCount(item) { var n = 0; eachSpec(item, function (s) { if (s.dirty && s.key) n++ }); return n }
function clearDirty(item) { eachSpec(item, function (s) { s.dirty = false }) }
// 读取某个 k 标记的控件当前值（快速启动等操作用）
function pick(item, k) { var r = null; eachSpec(item, function (s) { if (s.k === k && r === null) r = valueOf(s) }); return r }

// ── 交互条件 ───────────────────────────────────────────────────────────
// 与网页版一致：有的控件只在另一个控件取某些值时可用（如开启前置脚本后才能选路径），
// 有的在任务运行时锁定、结束后恢复。W(spec, dep, test)：dep 为另一个控件 spec，test(值) 为真时可用。
// 开关 + 路径同排：路径只在开关打开时可用
function tp(toggle, field) { return [toggle, W(field, toggle)] }
function W(spec, dep, test) { spec.dep = dep; spec.need = test || function (v) { return !!v }; return spec }
function is() { var list = Array.prototype.slice.call(arguments); return function (v) { return list.indexOf(v) >= 0 } }
function isNot() { var list = Array.prototype.slice.call(arguments); return function (v) { return list.indexOf(v) < 0 } }
// 控件当前是否不可用：locked 为当前条目是否处于运行锁定
function isOff(item, spec, locked, env) {
    if (!spec || typeof spec !== "object") return false
    if (spec.off) return true
    if (spec.when && !spec.when(env || {})) return true
    if (locked && (spec.lock || (item && item.lockAll && spec.key))) return true
    for (var s = spec; s && s.dep; s = s.dep) if (!s.need(valueOf(s.dep))) return true
    return false
}
// 行是否显示：row[3] 为函数时按其返回值（随未保存的改动即时切换）
function rowShown(row) { return typeof row[3] !== "function" || row[3]() }
// 操作按钮是否不可用：op.lock 运行时锁定；op.off 当前不可用；op.when() 为假时不可用
function opOff(op, locked, env) { return !!op && (!!op.off || (locked && !!op.lock) || (!!op.when && !op.when(env || {}))) }

// 运行快照（/api/dispatch/runtime-snapshot）→ 某脚本的配置是否锁定（与网页版 isScriptConfigLocked 同口径）
function scriptLocked(tasks, scriptId) {
    function running(s) { return s === "运行" || s === "运行中" }
    return (tasks || []).some(function (t) {
        var info = t.task_info || []
        var infoRunning = info.some(function (x) { return x.script_id === scriptId && (running(x.status) || (x.userList || []).some(function (u) { return running(u.status) })) })
        if (t.isCycle) return infoRunning || (t.cycleNextList || []).some(function (c) { return c.scriptId === scriptId && c.isRunning })
        if (t.queueId) return infoRunning
        return t.scriptId === scriptId || (t.scripts || []).some(function (s) { return s.scriptId === scriptId })
    })
}
// 循环队列正在运行：类型、脚本增删换、删除队列都锁定
function queueLocked(tasks, queueId) { return (tasks || []).some(function (t) { return t.isCycle && t.queueId === queueId }) }
function itemLocked(key, item, tasks) {
    if (!item || !item.live || !item.uid) return false
    if (key === "scripts") return scriptLocked(tasks, item.uid)
    if (key === "queue") return queueLocked(tasks, item.uid)
    return false
}

// ── 02 托管管理 ───────────────────────────────────────────────────────
var emulatorOptions = []   // /api/info/combox/emulator：托管脚本「模拟器」下拉
function scripts(resp, emus) {
    if (emus) emulatorOptions = emus.filter(function (o) { return o.value && o.value !== "-" })
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
    var src = { c: c, ur: ur, i: i }
    var save = { path: "/api/scripts/update", base: { scriptId: uid } }
    var gameType = idx(["Emulator", "Client", "URL"], G.Type)
    var accounts = ur.index.map(function (u,n) {
        const data = ur.data[u.uid] || {}, info = data.Info || {}, notify = data.Notify || {}
        const target = {path:"/api/scripts/user/update",base:{scriptId:uid,userId:u.uid}}
        const nEnabled = B(SD.tog(notify.Enabled),"Notify.Enabled")
        return {name:"账号" + (n+1), userId:u.uid, sortId:u.uid, sortGroup:"users:" + uid, sortLabel:info.Name || ("账号" + (n+1)), save:target, api:target.path, blocks:[
            SD.kv("基本资料",[
                ["账号名称", B(SD.inp(info.Name),"Info.Name")], ["启用代理", B(SD.tog(info.Status),"Info.Status")],
                ["剩余天数（-1 永久）", B(Object.assign(SD.num(info.RemainedDay ?? -1),{min:-1}),"Info.RemainedDay")],
                ["备注", B(SD.inp(info.Notes),"Info.Notes")],
                ["配置来源", B(SD.sel(["独立","共享","原生"],idx(["independent","shared","native"],info.Base)),"Info.Base",["independent","shared","native"])]
            ]),
            // 开关与路径 / 地址同排，一页放得下，不需要滚动
            SD.kv("额外脚本",[
                ["前置脚本",tp(B(SD.tog(info.IfScriptBeforeTask),"Info.IfScriptBeforeTask"),B(SD.path(info.ScriptBeforeTask),"Info.ScriptBeforeTask"))],
                ["后置脚本",tp(B(SD.tog(info.IfScriptAfterTask),"Info.IfScriptAfterTask"),B(SD.path(info.ScriptAfterTask),"Info.ScriptAfterTask"))]
            ]),
            // 未启用通知时各渠道不可用；渠道开启后才能填写地址 / 密钥
            SD.kv("通知设置",[
                ["启用通知",nEnabled],
                ["发送统计",W(B(SD.tog(notify.IfSendStatistic),"Notify.IfSendStatistic"),nEnabled)],
                ["邮件通知",tp(W(B(SD.tog(notify.IfSendMail),"Notify.IfSendMail"),nEnabled),B(SD.inp(notify.ToAddress),"Notify.ToAddress")),"收信邮箱"],
                ["Server 酱",tp(W(B(SD.tog(notify.IfServerChan),"Notify.IfServerChan"),nEnabled),B(Object.assign(SD.inp(notify.ServerChanKey),{secret:true}),"Notify.ServerChanKey")),"推送密钥"]
            ])
        ],actions:["保存","Webhook","添加账号","删除账号"],ops:{"删除账号":{path:"/api/scripts/user/delete",body:target.base,confirm:"删除该账号？",reload:true,lock:true}}}
    })
    // icon：启动程序路径，录像带上显示该程序的图标唱片
    // 游戏：按启动方式显示对应字段（客户端：路径 / 参数 / 等待 / 强制关闭；模拟器：模拟器与实例；URL：协议地址与进程名）
    var gType = B(SD.seg(["模拟器", "客户端", "URL 协议"], gameType), "Game.Type", ["Emulator", "Client", "URL"])
    function gameIs(t) { return function () { return valueOf(gType) === t } }
    var emuNames = ["未选择"].concat(emulatorOptions.map(function (o) { return o.label })), emuValues = ["-"].concat(emulatorOptions.map(function (o) { return o.value }))
    if (G.EmulatorId && emuValues.indexOf(G.EmulatorId) < 0) { emuNames.push("已失效的模拟器"); emuValues.push(G.EmulatorId) }
    var emu = B(SD.sel(emuNames, idx(emuValues, G.EmulatorId)), "Game.EmulatorId", emuValues)
    var emuIndex = W(B(SD.inp(G.EmulatorIndex === "-" ? "" : G.EmulatorIndex, true), "Game.EmulatorIndex"), emu, function (v) { return !!v && v !== "-" })
    var trackOn = B(SD.tog(S.IfTrackProcess),"Script.IfTrackProcess")
    function tracking() { return !!valueOf(trackOn) }
    return { name: I.Name || "未命名脚本", en: "GENERAL · " + String(i + 1).padStart(2, "0"), live: true, uid: uid, icon: S.ScriptPath || "", src: src,
        // 任务运行中整卡锁定（与网页版相同），结束后自动解锁
        lockAll: true, lockNote: "任务运行中，配置已锁定",
        accounts: ur.index.map(function (u) { return (ur.data[u.uid] && ur.data[u.uid].Info.Name) || "账号" }),
        ops: {
            "删除脚本": { confirm: "将删除脚本「" + I.Name + "」及其全部账号。", path: "/api/scripts/delete", body: { scriptId: uid }, reload: true, lock: true },
            "添加账号": { path: "/api/scripts/user/add", body: { scriptId: uid }, reload: true, done: "已添加账号", lock: true },
            "Webhook": { lock: true },
            "立即运行": { confirm: "将立即以自动代理模式运行脚本「" + I.Name + "」。", path: "/api/dispatch/start", body: { taskId: uid, mode: "AutoProxy" }, done: "已开始运行", lock: true }
        },
        tabs: [
        { name: "程序", api: save.path, save: save, blocks: [
            SD.kv("基本信息", [["托管名称", B(SD.inp(I.Name), "Info.Name")], ["脚本根目录", B(Object.assign(SD.path(I.RootPath),{browse:"选择文件夹"}), "Info.RootPath")]]),
            SD.kv("源程序配置", [
                ["原生配置类型", B(SD.seg(["单个配置文件","配置目录"],idx(["File","Folder"],S.ConfigPathMode)), "Script.ConfigPathMode",["File","Folder"])],
                // 「选择配置路径」与编辑、打开设置放在同一行
                ["原生配置路径", B(Object.assign(SD.path(S.ConfigPath),{noBrowse:true}), "Script.ConfigPath")],
                ["", Object.assign(SD.mini(["选择配置路径","编辑并写回原文件","打开源程序设置"]),{commands:true,lock:true})]
            ])
        ], actions: ["保存", "添加账号", "立即运行", "删除脚本"] },
        // 原「配置」一页有 17 行，按「启动 / 日志 / 规则」拆成三页，各页不需要滚动
        { name: "启动", api: save.path, save: save, blocks: [
            SD.kv("启动程序", [
                ["启动程序", B(SD.path(S.ScriptPath),"Script.ScriptPath")], ["启动参数",B(SD.inp(S.Arguments,true),"Script.Arguments")],
                ["回写配置", B(SD.seg(["从不","成功时","失败时","总是"],idx(["Never","Success","Failure","Always"],S.UpdateConfigMode)), "Script.UpdateConfigMode",["Never","Success","Failure","Always"])]
            ]),
            // 开启追踪后才显示追踪条件
            SD.kv("进程追踪", [
                ["追踪子进程",trackOn], ["进程名",B(SD.inp(S.TrackProcessName),"Script.TrackProcessName"),"",tracking],
                ["进程程序路径",B(SD.path(S.TrackProcessExe),"Script.TrackProcessExe"),"",tracking], ["命令行匹配",B(SD.inp(S.TrackProcessCmdline),"Script.TrackProcessCmdline"),"",tracking]
            ])
        ], actions: ["保存"] },
        { name: "日志", api: save.path, save: save, blocks: [
            SD.kv("日志文件", [["日志路径", B(SD.path(S.LogPath), "Script.LogPath"), "Script.LogPath"], ["路径日期格式", B(SD.inp(S.LogPathFormat, true), "Script.LogPathFormat"), "Script.LogPathFormat"], ["时间戳位置", [B(SD.num(S.LogTimeStart), "Script.LogTimeStart"), SD.unit("至"), B(SD.num(S.LogTimeEnd), "Script.LogTimeEnd"), SD.unit("列")], "Script.LogTimeStart / LogTimeEnd"], ["时间格式", B(SD.inp(S.LogTimeFormat, true), "Script.LogTimeFormat"), "Script.LogTimeFormat"]]),
            SD.kv("结果判定", [["成功判定", [B(SD.inp(S.SuccessLog), "Script.SuccessLog"), B(SD.seg(["关键字", "正则"], idx(["Split", "Regex"], S.SuccessLogMode)), "Script.SuccessLogMode", ["Split", "Regex"])], "Script.SuccessLog / SuccessLogMode"], ["失败判定", [B(SD.inp(S.ErrorLog), "Script.ErrorLog"), B(SD.seg(["关键字", "正则"], idx(["Split", "Regex"], S.ErrorLogMode)), "Script.ErrorLogMode", ["Split", "Regex"])], "Script.ErrorLog / ErrorLogMode"]])
        ], actions: ["保存"] },
        { name: "规则", api: save.path, save: save, blocks: [
            SD.kv("日志预处理", [["启用预处理", B(SD.tog(S.LogHookEnabled), "Script.LogHookEnabled"), "Script.LogHookEnabled"], ["预处理规则",B(SD.inp(S.LogHookRules,true),"Script.LogHookRules")]]),
            SD.kv("日志推送", [["启用推送", B(SD.tog(S.PushLogEnabled), "Script.PushLogEnabled"), "Script.PushLogEnabled"], ["推送规则",B(SD.inp(S.PushLogPatterns,true),"Script.PushLogPatterns")]])
        ], ops:{"预处理规则":{workspace:"预处理规则",lock:true},"推送规则":{workspace:"推送规则",lock:true}},
          actions:["预处理规则","推送规则","保存"] },
        { name: "限制", api: save.path, save: save, blocks: [
            SD.kv("运行限制", [["单账号总时限", B(SD.num(R.HardTimeLimit, "分钟"), "Run.HardTimeLimit"), "Run.HardTimeLimit"], ["单次运行时限", B(SD.num(R.RunTimeLimit, "分钟"), "Run.RunTimeLimit"), "Run.RunTimeLimit"], ["单次重试次数", B(SD.num(R.RunTimesLimit, "次"), "Run.RunTimesLimit"), "Run.RunTimesLimit"], ["每日代理上限", B(SD.num(R.ProxyTimesLimit, "次 · 0 为不限"), "Run.ProxyTimesLimit"), "Run.ProxyTimesLimit"]]),
            SD.kv("清理与恢复", [
                ["清理范围",B(SD.seg(["跨会话强力","仅本轮","当前会话"],idx(["Force","Tracked","Session"],S.TaskKillMode)),"Script.TaskKillMode",["Force","Tracked","Session"])],
                ["清理清单", B({c:"entries", v:S.TaskKill || [], kind:"cleanup"},"Script.TaskKill")],
                ["重启清单", B({c:"entries", v:S.Restart || [], kind:"restart"},"Script.Restart")]
            ])
        ], actions: ["保存"] },
        { name: "游戏", api: save.path, save: save, blocks: [
            SD.kv("游戏启动", [["随脚本启动游戏", B(SD.tog(G.Enabled), "Game.Enabled"), "Game.Enabled"], ["启动方式", gType, "Game.Type"],
                ["游戏路径", B(Object.assign(SD.path(G.Path), { browse: "选择文件" }), "Game.Path"), "Game.Path", gameIs("Client")],
                ["模拟器", emu, "Game.EmulatorId · 在「模拟器管理」中添加", gameIs("Emulator")],
                ["模拟器实例", [emuIndex, Object.assign(SD.mini(["选择实例"]), {ops:[{workspace:"选择实例",lock:true,when:()=>!!valueOf(emu) && valueOf(emu)!=="-",emulator:emu,index:emuIndex}]})], "Game.EmulatorIndex · 先选择模拟器，再填写实例编号", gameIs("Emulator")],
                ["协议地址", B(SD.inp(G.URL, true), "Game.URL"), "Game.URL", gameIs("URL")],
                ["启动参数", B(SD.inp(G.Arguments, true), "Game.Arguments"), "Game.Arguments", gameIs("Client")],
                ["启动后等待", B(SD.num(G.WaitTime, "秒"), "Game.WaitTime"), "Game.WaitTime", gameIs("Client")],
                ["结束后强制关闭", B(SD.tog(G.IfForceClose), "Game.IfForceClose"), "Game.IfForceClose", gameIs("Client")],
                ["进程名", B(SD.inp(G.ProcessName, true), "Game.ProcessName"), "Game.ProcessName", gameIs("URL")]])
        ], actions: ["保存"] }
    ].concat(accounts) }
}

// 「复制脚本」（演示模式）：按原始数据重建，保留控件之间的依赖关系
function copyScript(item) {
    var c = JSON.parse(JSON.stringify(item.src.c)), ur = JSON.parse(JSON.stringify(item.src.ur))
    c.Info.Name = (c.Info.Name || "") + " · 副本"
    var copy = general("", c, ur, item.src.i)
    copy.live = item.live
    return copy
}
function previewScript(raw, id, index) {
    const item = general(id,raw.config,raw.users,index)
    item.live = false
    item.en = raw.en || item.en
    return item
}

// ── 04 调度队列 ───────────────────────────────────────────────────────
// scriptOpts：[{label, value}]（/api/info/combox/script）
function queues(qresp, times, qitems, scriptOpts, scriptPaths) {
    scriptPaths = scriptPaths || {}
    var names = scriptOpts.map(function (o) { return o.label.replace(/^通用 - /, "") }), values = scriptOpts.map(function (o) { return o.value })
    var power = ["NoAction", "KillSelf", "RestartSelf", "Sleep", "Hibernate", "Logoff", "Shutdown", "ShutdownForce", "Reboot"]
    // 还没有队列时留一张空卡，用来新建第一条队列
    if (!qresp.index.length) return [{ name: "暂无队列", en: "QUEUE · 00", live: true, uid: "", icon: "", accounts: [], configRow: false, api: "POST /api/queue/add",
        blocks: [SD.note("还没有调度队列", true)],
        ops: { "新建队列": { path: "/api/queue/add", body: {}, reload: true, done: "已新建队列" } }, actions: ["新建队列"] }]
    return qresp.index.map(function (q, i) {
        var qid = q.uid, I = qresp.data[qid].Info
        var save = { path: "/api/queue/update", base: { queueId: qid } }
        var ts = times[qid] || { index: [], data: {} }, it = qitems[qid] || { index: [], data: {} }
        // 行尾「删除」：确认后删除该定时 / 队列项并重新读取；lock 为真时循环运行期间不可用
        function remover(path, body, what, lock) {
            var m = SD.mini(["删除"]); m.ops = [{ confirm: "将删除这条" + what + "。", path: path, body: body, reload: true, done: "已删除" + what, lock: !!lock }]; return m
        }
        var cycle = !!I.CycleEnabled
        var trows = ts.index.map(function (t) {
            var d = ts.data[t.uid].Info, s = { path: "/api/queue/time/update", base: { queueId: qid, timeSetId: t.uid } }
            return [B(SD.tog(d.Enabled), "Info.Enabled", null, s), B(SD.chips(mask(d.Days)), "Info.Days", null, s), B(SD.time(d.Time), "Info.Time", null, s),
                    remover("/api/queue/time/delete", { queueId: qid, timeSetId: t.uid }, "定时")]
        })
        // 与网页版一致：定时队列的队列项只有脚本与执行周期；循环队列另有参与循环、方式、时间 / 间隔、
        // 间隔起点、下次运行与「立即运行一次」。循环运行中不能换脚本、增删队列项（行内按钮置灰）。
        var irows = [], crows = []
        it.index.forEach(function (t) {
            var d = it.data[t.uid], s = { path: "/api/queue/item/update", base: { queueId: qid, queueItemId: t.uid } }
            var sc = d.Schedule
            var next = sc.NextRunAt && sc.NextRunAt.indexOf("2000-01-01") !== 0 ? sc.NextRunAt.slice(5, 16) : "未排期"
            var sid = d.Info.ScriptId, sname = sid && values.indexOf(sid) >= 0 ? names[values.indexOf(sid)] : "未选择脚本"
            var script = B(SD.sel(names, idx(values, sid)), "Info.ScriptId", values, s); script.lock = true
            var del = remover("/api/queue/item/delete", { queueId: qid, queueItemId: t.uid }, "队列项", true)
            if (!cycle) {
                var days = B(SD.chips(mask(sc.Days)), "Schedule.Days", null, s); days.lock = true
                irows.push([script, days, del])
                return
            }
            var on = B(SD.tog(sc.Enabled), "Schedule.Enabled", null, s)
            var mode = W(B(SD.seg(["定时", "间隔"], sc.Mode === "interval" ? 1 : 0), "Schedule.Mode", ["fixed_time", "interval"], s), on)
            function interval() { return valueOf(mode) === "interval" }
            function fixed() { return valueOf(mode) !== "interval" }
            var when = [Object.assign(W(B(SD.num(sc.IntervalMinutes, "分钟"), "Schedule.IntervalMinutes", null, s), on), { show: interval, min: 1, max: 10080 }),
                        Object.assign(W(B(SD.time(sc.Time), "Schedule.Time", null, s), on), { show: fixed })]
            var extra = [Object.assign(W(B(SD.seg(["从开始", "从结束"], idx(["start", "finish"], sc.IntervalAnchor)), "Schedule.IntervalAnchor", ["start", "finish"], s), on), { show: interval }),
                         Object.assign(W(B(SD.chips(mask(sc.Days)), "Schedule.Days", null, s), on), { show: fixed })]
            var once = W(SD.mini(["立即运行一次"]), on)
            once.ops = [{ path: "/api/queue/item/update", body: function () { return { queueId: qid, queueItemId: t.uid, data: { Schedule: { NextRunAt: nowText() } } } }, reload: true, done: "已安排立即运行" }]
            irows.push([script, on, mode, next, del])
            crows.push([sname, when, extra, once])
        })
        // 3D 阵列：列内各行 = 队列配置 + 各队列项（以所选脚本的启动程序图标作唱片）
        var rowNames = it.index.map(function (t) { var sid = it.data[t.uid].Info.ScriptId; return sid && values.indexOf(sid) >= 0 ? names[values.indexOf(sid)] : "未选择脚本" })
        var rowIcons = it.index.map(function (t) { return scriptPaths[it.data[t.uid].Info.ScriptId] || "" })
        var cycleOn = B(SD.tog(I.CycleEnabled, "cycle"), "Info.CycleEnabled"); cycleOn.lock = true
        var timeOn = W(B(SD.tog(I.TimeEnabled, "time"), "Info.TimeEnabled"), cycleOn, function (v) { return !v })
        var after = B(SD.sel(SD.POWER, idx(power, I.AfterAccomplish)), "Info.AfterAccomplish", power)
        var itemTable = cycle
            ? SD.table("队列项", ["脚本", "参与循环", "方式", "下次运行", "操作"], irows, [2.2, 1, 1.3, 1.1, 0.8])
            : SD.table("队列项", ["脚本", "执行周期", "操作"], irows, [2, 2.6, 0.8])
        itemTable.queueRows = true
        // 拖动行号到暂存区再拖回，调整队列项顺序；循环运行中不可调整
        itemTable.sort = { group: "item:" + qid, ids: it.index.map(function (t) { return t.uid }), labels: rowNames, lock: true,
                           path: "/api/queue/item/order", body: function (ids) { return { queueId: qid, indexList: ids } } }
        var tabs = [
            { name: "调度", api: save.path, save: save, blocks: [
                SD.kv("调度", [["队列名称", B(SD.inp(I.Name), "Info.Name"), "Info.Name"], ["定时启动", timeOn, "Info.TimeEnabled · 循环队列不使用定时"], ["循环队列", cycleOn, "Info.CycleEnabled · 循环运行中不能切换"], ["启动时运行", B(SD.seg(["从不", "每次", "每日首次"], idx(["Never", "Always", "DailyFirst"], I.StartUpMode)), "Info.StartUpMode", ["Never", "Always", "DailyFirst"]), "Info.StartUpMode"], ["完成后", after, "Info.AfterAccomplish"], ["延时执行", W(B(SD.num(I.AfterAccomplishDelay, "分钟"), "Info.AfterAccomplishDelay"), after, isNot("NoAction")), "Info.AfterAccomplishDelay · 完成后无动作时不可用"]]),
                SD.kv("前后脚本", [["运行前脚本", tp(B(SD.tog(I.IfScriptBeforeTask), "Info.IfScriptBeforeTask"), B(SD.path(I.ScriptBeforeTask), "Info.ScriptBeforeTask")), "Info.IfScriptBeforeTask / ScriptBeforeTask"], ["运行后脚本", tp(B(SD.tog(I.IfScriptAfterTask), "Info.IfScriptAfterTask"), B(SD.path(I.ScriptAfterTask), "Info.ScriptAfterTask")), "Info.IfScriptAfterTask / ScriptAfterTask"]])
            ], actions: ["保存", "立即运行", "新建队列", "删除队列"] }
        ]
        // 定时只属于定时队列：循环队列不显示「定时」页
        if (!cycle) tabs.push({ name: "定时", api: "POST /api/queue/time/update", blocks: [
            (function () { var tb = SD.table("定时", ["启用", "周期", "时间", "操作"], trows, [1, 2.6, 1, 0.8])
                // 拖动行号到暂存区再拖回，调整定时顺序
                tb.sort = { group: "time:" + qid, ids: ts.index.map(function (t) { return t.uid }), labels: ts.index.map(function (t, k) { return "定时 " + (k + 1) + " · " + (ts.data[t.uid].Info.Time || "") }),
                            path: "/api/queue/time/order", body: function (ids) { return { queueId: qid, indexList: ids } } }
                return tb })()
        ], actions: ["保存", "添加定时"] })
        tabs.push({ name: "队列项", api: "POST /api/queue/item/update", blocks: [itemTable
        ], actions: ["保存", "添加脚本"] })
        if (cycle) tabs.push({ name: "循环", api: "POST /api/queue/item/update", blocks: [
            SD.table("循环调度", ["脚本", "时间 / 间隔", "周期 / 间隔起点", "操作"], crows, [1.6, 1.3, 2.6, 1.2])
        ], actions: ["保存"] })
        return { name: I.Name, en: (I.CycleEnabled ? "QUEUE · CYCLE · " : "QUEUE · ") + String(i + 1).padStart(2, "0"), live: true, uid: qid,
            icon: "", accounts: rowNames, rowIcons: rowIcons, configRow: false,
            exclusive: I.CycleEnabled ? "cycle" : I.TimeEnabled ? "time" : "",
            // 切换队列类型后分页结构会变（定时 / 循环），保存后重新读取
            reloadOnSave: true,
            lockNote: "循环运行中，类型与队列项已锁定",
            ops: {
                "立即运行": { confirm: "将立即运行队列「" + I.Name + "」。", path: "/api/dispatch/start", body: { taskId: qid, mode: I.CycleEnabled ? "CycleRun" : "AutoProxy" }, done: "已开始运行", lock: true },
                "删除队列": { confirm: "将删除队列「" + I.Name + "」及其定时和队列项。", path: "/api/queue/delete", body: { queueId: qid }, reload: true, lock: true },
                "新建队列": { path: "/api/queue/add", body: {}, reload: true, done: "已新建队列" },
                "添加定时": { path: "/api/queue/time/add", body: { queueId: qid }, reload: true, done: "已添加定时" },
                "添加脚本": { path: "/api/queue/item/add", body: { queueId: qid }, reload: true, done: "已添加队列项", lock: true }
            },
            tabs: tabs }
    })
}
function nowText() {
    var d = new Date()
    function two(n) { return String(n).padStart(2, "0") }
    return d.getFullYear() + "-" + two(d.getMonth() + 1) + "-" + two(d.getDate()) + " " + two(d.getHours()) + ":" + two(d.getMinutes()) + ":" + two(d.getSeconds())
}

// ── 03 模拟器管理 ─────────────────────────────────────────────────────
function emulatorCaption(type) {
    return "EMULATOR · " + (type === "emulator2" ? "AUTO DETECT" : type.toUpperCase())
}
function emulatorRecord(uid, info) {
    const types = ["general", "mumu", "ldplayer", "emulator2"]
    const save = {path:"/api/emulator/update", base:{emulatorId:uid}}
    let shortcuts = []
    try { shortcuts = JSON.parse(info.BossKey || "[]") } catch (e) {}
    const boss = B(Object.assign(SD.inp(shortcuts[0] || ""),{bossKey:true}),"Info.BossKey")
    const bossRec = SD.mini(["录制"]); bossRec.ops = [{ captureHotkey: boss, boss: true }]
    const rows = [
        ["模拟器名称", B(SD.inp(info.Name), "Info.Name")],
        ["模拟器类型", B(SD.seg(["通用","MuMu","雷电","自动识别（推荐）"],idx(types,info.Type)), "Info.Type",types)],
        ["模拟器路径", B(SD.path(info.Path), "Info.Path")],
        ["最大等待时间", B(Object.assign(SD.num(info.MaxWaitTime ?? 300,"秒"),{min:10,max:9999}), "Info.MaxWaitTime")],
        ["老板键", [boss, bossRec], "Info.BossKey · 点「录制」后按下组合键", ["general","ldplayer"]],
        ["老板键", "MuMu 模拟器无需配置老板键", "", ["mumu"]],
        ["强力关闭", B(SD.tog(info.ForceKillOnClose), "Info.ForceKillOnClose"), "", ["mumu"]],
        ["启动前强力清理", B(SD.tog(info.ForceKillBeforeLaunch), "Info.ForceKillBeforeLaunch"), "", ["mumu"]],
        ["稳定模式", B(SD.tog(info.StableMode), "Info.StableMode"), "", ["emulator2"]],
        ["配置守卫", B(SD.tog(info.ConfigGuard), "Info.ConfigGuard"), "", ["emulator2"]],
        ["设备管理", Object.assign(SD.mini(["路径与实例"]), {ops:[{workspace:"自动识别管理"}]}), "", ["emulator2"]]
    ]
    const config = {name:"配置", api:save.path, save:save, blocks:[SD.kv("模拟器配置",rows)], actions:["搜索","添加","删除","保存"]}
    // 实例：状态每 3 秒刷新（与网页版相同）；在线时可显示，离线 / 异常时可启动，在线或启动中可关闭
    const STATUS = {0:["在线","ok"],1:["离线","idle"],2:["启动中","run"],3:["关闭中","idle"],4:["错误","err"],5:["未找到","err"],10:["未知","idle"]}
    function deviceRows(env) {
        const devs = env.devices && env.devices[uid] || {}
        return Object.keys(devs).map(function (i) {
            const d = devs[i], st = d.status
            const canStart = [1,4,5,10].indexOf(st) >= 0, canStop = st === 0 || st === 2
            const m = SD.mini(["显示", canStart ? "启动" : canStop ? "关闭" : "等待"])
            function op(kind, done) { return { path: "/api/emulator/operate", body: { emulatorId: uid, operate: kind, index: String(i) }, done: done, poll: true } }
            m.ops = [Object.assign(op("show", "已显示"), { off: st !== 0 }),
                     canStart ? op("open", "已发送启动指令") : canStop ? op("close", "已发送关闭指令") : { off: true }]
            const tg = STATUS[st] || ["未知","idle"]
            return [String(i), SD.tag(tg[0], tg[1]), d.title || "—", d.adb_address || "—", m]
        })
    }
    const devTable = SD.table("实例", ["编号", "状态", "名称", "ADB 地址", "操作"], [], [0.7, 0.9, 1.6, 1.6, 1.4])
    devTable.rowsFn = deviceRows
    devTable.deviceInstances = true
    devTable.pageRows = 3
    if (info.Type !== "emulator2") config.blocks.push(devTable)
    return {uid:uid, name:info.Name || "未命名模拟器", en:emulatorCaption(info.Type),
            live:true, deviceTable:devTable, deviceType:info.Type, tabs:[config]}
}

// ── 10 设置 / 06 本地控制（GlobalConfig） ─────────────────────────────
function settings(g, version, qq) {
    var save = { path: "/api/setting/update", base: {} }, api = "POST /api/setting/update"
    var F = g.Function, N = g.Notify, U = g.Update, R = g.Replay
    var keep = [7, 15, 30, 60, 90, 180, 365, 0]
    var push = ["不推送", "任何时刻", "仅失败时"]
    function secret(v, key) { return B(Object.assign(SD.inp(v), { secret: true }), key) }
    var testNotify = { "测试通知": { saveFirst: true, path: "/api/setting/test_notify", body: {}, done: "已发送测试通知" } }
    var voiceOn = B(SD.tog(g.Voice.Enabled), "Voice.Enabled")
    var source = B(SD.sel(["GitHub", "Mirror 酱", "自建下载站", "CNB 镜像源"], idx(["GitHub", "MirrorChyan", "AutoSite", "CNB"], U.Source)), "Update.Source", ["GitHub", "MirrorChyan", "AutoSite", "CNB"])
    var replayOn = B(SD.tog(R.Enabled), "Replay.Enabled")
    // QQ 官方机器人：未扫码绑定（未连接）时开关不可用；已开着的仍可关闭
    var qqOn = B(SD.tog(N.IfOpenClawQQ), "Notify.IfOpenClawQQ")
    if (!(qq && qq.connected) && !N.IfOpenClawQQ) qqOn.off = true
    return [
        { name: "启动与界面", en: "START · UI", live: true, api: api, save: save, blocks: [SD.kv("启动与界面", [["开机自启", B(SD.tog(g.Start.IfSelfStart), "Start.IfSelfStart"), "Start.IfSelfStart"], ["启动后最小化", B(SD.tog(g.Start.IfMinimizeDirectly), "Start.IfMinimizeDirectly"), "Start.IfMinimizeDirectly"], ["显示托盘图标", B(SD.tog(g.UI.IfShowTray), "UI.IfShowTray"), "UI.IfShowTray"], ["关闭到托盘", B(SD.tog(g.UI.IfToTray), "UI.IfToTray"), "UI.IfToTray"], ["隐藏关闭按钮", B(SD.tog(g.UI.IfHideCloseButton), "UI.IfHideCloseButton"), "UI.IfHideCloseButton"], ["主题", SD.segk(["跟随系统", "浅色", "深色"], 0, "theme"), "客户端设置"], ["动态效果", SD.segk(["减少", "标准", "增强"], 1, "motion"), "客户端设置"]])], actions: ["保存"] },
        { name: "功能", en: "FUNCTION", live: true, api: api, save: save, blocks: [
            SD.kv("运行", [["历史记录保留", B(SD.sel(["7 天", "15 天", "30 天", "60 天", "90 天", "180 天", "365 天", "永久"], idx(keep, F.HistoryRetentionTime)), "Function.HistoryRetentionTime", keep), "Function.HistoryRetentionTime"], ["运行时允许睡眠", B(SD.tog(F.IfAllowSleep), "Function.IfAllowSleep"), "Function.IfAllowSleep"], ["静默模式", B(SD.tog(F.IfSilence), "Function.IfSilence"), "Function.IfSilence"], ["屏蔽模拟器广告", B(SD.tog(F.IfBlockAd), "Function.IfBlockAd"), "Function.IfBlockAd"], ["哔哩哔哩协议弹窗", B(SD.tog(F.IfAgreeBilibili), "Function.IfAgreeBilibili"), "Function.IfAgreeBilibili"], ["匿名遥测", B(SD.tog(F.IfEnableTelemetry), "Function.IfEnableTelemetry"), "Function.IfEnableTelemetry"]]),
            SD.kv("语音", [["语音提示", voiceOn, "Voice.Enabled"], ["语音风格", W(B(SD.seg(["简洁", "聒噪"], idx(["simple", "noisy"], g.Voice.Type)), "Voice.Type", ["simple", "noisy"]), voiceOn), "Voice.Type · 开启语音提示后可选"]])
        ], actions: ["保存"] },
        // 通知按「内容 / 邮件 / 其它渠道」拆成三张卡，各渠道的地址与密钥都可直接填写
        { name: "通知内容", en: "NOTIFY", live: true, api: api, save: save, blocks: [SD.kv("通知内容", [["任务结果推送", B(SD.seg(push, idx(push, N.SendTaskResultTime)), "Notify.SendTaskResultTime", push), "Notify.SendTaskResultTime"], ["推送统计信息", B(SD.tog(N.IfSendStatistic), "Notify.IfSendStatistic"), "Notify.IfSendStatistic"], ["推送公招高资喜报", B(SD.tog(N.IfSendSixStar), "Notify.IfSendSixStar"), "Notify.IfSendSixStar"], ["系统通知", B(SD.tog(N.IfPushPlyer), "Notify.IfPushPlyer"), "Notify.IfPushPlyer"]])],
          ops: testNotify, actions: ["保存", "测试通知"] },
        { name: "邮件通知", en: "NOTIFY · MAIL", live: true, api: api, save: save, blocks: [SD.kv("邮件通知", [["启用邮件通知", B(SD.tog(N.IfSendMail), "Notify.IfSendMail"), "Notify.IfSendMail"], ["发信服务器", B(SD.inp(N.SMTPServerAddress, true), "Notify.SMTPServerAddress"), "Notify.SMTPServerAddress"], ["发信邮箱", B(SD.inp(N.FromAddress, true), "Notify.FromAddress"), "Notify.FromAddress"], ["发信授权码", secret(N.AuthorizationCode, "Notify.AuthorizationCode"), "Notify.AuthorizationCode"], ["收信邮箱", B(SD.inp(N.ToAddress, true), "Notify.ToAddress"), "Notify.ToAddress"]])],
          ops: testNotify, actions: ["保存", "测试通知"] },
        { name: "推送渠道", en: "NOTIFY · CHANNELS", live: true, api: api, save: save, blocks: [
            SD.kv("推送渠道", [["Server 酱", [B(SD.tog(N.IfServerChan), "Notify.IfServerChan"), secret(N.ServerChanKey, "Notify.ServerChanKey")], "Notify.IfServerChan / ServerChanKey"], ["移动 5G 短信", [B(SD.tog(N.IfCMCCNewMsg), "Notify.IfCMCCNewMsg"), secret(N.CMCCNewMsgApiKey, "Notify.CMCCNewMsgApiKey")], "Notify.IfCMCCNewMsg / CMCCNewMsgApiKey"], ["Koishi", B(SD.tog(N.IfKoishiSupport), "Notify.IfKoishiSupport"), "Notify.IfKoishiSupport"], ["Koishi 地址", B(SD.inp(N.KoishiServerAddress, true), "Notify.KoishiServerAddress"), "Notify.KoishiServerAddress"], ["Koishi 令牌", secret(N.KoishiToken, "Notify.KoishiToken"), "Notify.KoishiToken"], ["QQ 官方机器人", [qqOn, qq && qq.connected ? SD.tag("已连接", "ok") : SD.tag("未绑定", "idle")], "Notify.IfOpenClawQQ · 扫码绑定并连接后才能开启"]])
          ], ops:Object.assign({},testNotify,{"绑定 QQ":{workspace:"绑定 QQ"}}),
          actions:["保存","测试通知","全局 Webhook","绑定 QQ"] },
        { name: "更新", en: "UPDATE", live: true, api: api, save: save, blocks: [SD.kv("更新", [["当前版本", version || "—"], ["自动更新", B(SD.tog(U.IfAutoUpdate), "Update.IfAutoUpdate"), "Update.IfAutoUpdate"], ["暂停更新至", B(SD.inp(U.PauseUntil, true), "Update.PauseUntil"), "Update.PauseUntil · 年-月-日，留空为不暂停"], ["更新源", source, "Update.Source"], ["Mirror 酱 CDK", W(secret(U.MirrorChyanCDK, "Update.MirrorChyanCDK"), source, is("MirrorChyan")), "Update.MirrorChyanCDK · 更新源选 Mirror 酱时可填"], ["更新渠道", B(SD.seg(["稳定版", "公测版"], idx(["stable", "beta"], U.Channel)), "Update.Channel", ["stable", "beta"]), "Update.Channel"], ["GitHub 加速", B(SD.seg(["自动", "关闭"], idx(["Auto", "Off"], U.GitHubMirror)), "Update.GitHubMirror", ["Auto", "Off"]), "Update.GitHubMirror"], ["代理地址", B(SD.inp(U.ProxyAddress, true), "Update.ProxyAddress"), "Update.ProxyAddress"]])], actions: ["保存"] },
        { name: "失败回放", en: "REPLAY · OBS", live: true, api: api, save: save, blocks: [
            SD.kv("失败回放", [["启用失败回放", replayOn, "Replay.Enabled"], ["OBS 端口", W(B(SD.num(R.Port), "Replay.Port"), replayOn), "Replay.Port"], ["最多保留", W(B(SD.num(R.MaxReplayCount, "段"), "Replay.MaxReplayCount"), replayOn), "Replay.MaxReplayCount"],
                ["OBS 密码", W(B(Object.assign(SD.inp(""), { secret: true, skipEmpty: true }), "Replay.Password"), replayOn), "Replay.Password · " + (R.PasswordConfigured ? "已设置，留空不修改" : "未设置")]])
        ], ops: { "检查连接": { saveFirst: true, path: "/api/setting/obs/check", body: {}, show: true, done: "OBS 连接正常", when: function () { return !!valueOf(replayOn) } },
                  "试存回放": { path: "/api/setting/obs/save", body: {}, show: true, done: "回放已保存", when: function () { return !!valueOf(replayOn) } },
                  "清空密码": { confirm: "清空后将按无密码连接 OBS。", path: "/api/setting/update", body: { data: { Replay: { Password: "" } } }, reload: true, done: "OBS 密码已清空", off: !R.PasswordConfigured, when: function () { return !!valueOf(replayOn) } } },
          actions: ["保存", "检查连接", "试存回放", "清空密码"] },
        { name: "高级与关于", en: "ADVANCED", live: true, api: "GET /api/setting/backup", blocks: [
            SD.kv("数据与日志", [["数据备份", "导出配置、数据与历史记录的压缩包"], ["日志", "打包运行日志，反馈问题时附上"]]),
            SD.kv("关于", [["版本", version || "—"], ["字体", "MiSans（小米）· 许可见 NOTICE"], ["视觉参考", "LBEILC / RhineLabUI（MIT）"]])
          ], ops: { "导出数据备份": { exportBackup: true, when: function (e) { return !e.exporting } }, "打包日志": { exportLogs: true, when: function (e) { return !e.exporting } } },
          actions: ["导出数据备份", "打包日志"] }
    ]
}
function local(g, port, vd, nav, ports) {
    var save = { path: "/api/setting/update", base: {} }, api = "POST /api/setting/update"
    var C = g.ChildSession, D = g.Display, H = g.Hotkey
    var vdOn = B(SD.tog(D.IfEnableVirtualDisplay), "Display.IfEnableVirtualDisplay")
    if (vd && vd.ready === false && !D.IfEnableVirtualDisplay) vdOn.off = true
    var hkOn = B(SD.tog(H.Enabled), "Hotkey.Enabled")
    // 热键：可直接输入，也可点「录制」后按下组合键（启用全局热键后可用）
    function hotkey(v, key) {
        var field = W(B(SD.inp(v, true), key), hkOn)
        var rec = W(SD.mini(["录制"]), hkOn); rec.ops = [{ captureHotkey: field }]
        return [field, rec]
    }
    function dyn(f, tone) { return { c: "dyn", f: f, tone: tone } }
    function connected(e) { return !!(e.desk && e.desk.hostConnected) }
    // 远程桌面窗口操作：payload 可为函数（按当前状态取反）；needConn 为真时未连接不可用
    function deskOps(names, payloads, needConn) {
        var m = SD.mini(names)
        m.ops = payloads.map(function (pl) { return { path: "/api/child-session/window", body: pl, done: "已发送", poll: true, when: needConn ? connected : null } })
        return m
    }
    const modes = SD.mini(["观看模式", "画面自适应", "窗口置顶"])
    modes.ops = ["watchMode", "smartSizing", "topmost"].map(function (key) {
        const checked = e => !!e.desk?.hostStatus?.[key]
        return {path:"/api/child-session/window", checked:checked, when:connected,
            body:e => ({[key]:!checked(e)}), done:"已发送", poll:true}
    })
    var navData = nav || { queues: [], selectedQueueId: null, controls: [] }
    function navCurrent(e) { var n = e.nav || navData; var cs = n.controls || []; return cs.filter(function (c) { return c.queueId === n.selectedQueueId })[0] || cs[0] || null }
    var navQueues = navData.queues || []
    var navQueue = navQueues.length
        ? Object.assign(SD.sel(navQueues.map(function (q) { return q.name + (q.isCycle ? "（循环，上下切换不可用）" : "") }), Math.max(0, navQueues.map(function (q) { return q.id }).indexOf(navData.selectedQueueId))),
            { onPick: function (i) { return { path: "/api/dispatch/navigation/control", body: { action: "select", queueId: navQueues[i].id }, done: "已切换热键控制的队列", poll: true } } })
        : "暂无队列"
    var leaseCaller = Object.assign(SD.inp(""), { k: "caller" })
    var leaseDisconnect = SD.tog(true)
    var leaseTimeout = Object.assign(SD.num(3600, "秒"), { min: 1, max: 86400 })
    var leaseWait = SD.tog(false)
    var leaseWaitTimeout = W(Object.assign(SD.num(300, "秒"), { min: 1, max: 86400 }), leaseWait)
    const leases = SD.table("当前借用", ["调用方", "租约 ID", "状态", "操作"], [], [1.4,2.2,1,0.8])
    leases.pageRows = 3
    leases.rowsFn = function (env) {
        if (!env.desk) return [["读取中…", "", "", ""]]
        const list = env.desk.activeLeases || []
        if (!list.length) return [["暂无借用", "", "", ""]]
        return list.map(function (lease) {
            const action = SD.mini(["归还"])
            const caller = lease.caller || "未知调用方"
            action.ops = [{path:"/api/child-session/release", body:{leaseId:lease.leaseId},
                off:!lease.leaseId, confirm:"归还「" + caller + "」的租约 " + lease.leaseId + "？",
                done:"已归还该租约", poll:true}]
            const status = {pending:"等待中", granted:"借用中", released:"已归还"}
            return [caller, lease.leaseId || "—", status[lease.status] || lease.status || "—", action]
        })
    }
    var res = ["2560x1440", "1920x1080", "1600x900"]
    if (res.indexOf(C.Resolution) < 0) res.unshift(C.Resolution)
    return [
        { name: "远程桌面分身", en: "CHILD SESSION · RDP", live: true, api: api, save: save, blocks: [
            SD.kv("远程桌面分身", [["启用分身执行", B(SD.tog(C.Enabled), "ChildSession.Enabled"), "ChildSession.Enabled"], ["宿主端口", B(SD.num(C.HostPort), "ChildSession.HostPort"), "ChildSession.HostPort"], ["分辨率", B(SD.sel(res, res.indexOf(C.Resolution)), "ChildSession.Resolution", res), "ChildSession.Resolution"], ["启动时隐藏预览", B(SD.tog(C.StartHidden), "ChildSession.StartHidden"), "ChildSession.StartHidden"], ["观看模式", B(SD.tog(C.WatchMode), "ChildSession.WatchMode"), "ChildSession.WatchMode"]])
        ], actions: ["保存"] },
        // 远程桌面控制：状态每 3 秒刷新；未连接时观看模式、自适应、置顶与快捷键不可用（与网页版一致）
        { name: "远程桌面控制", en: "CHILD SESSION · CONTROL", live: true, api: "GET /api/child-session/status", blocks: [
            SD.kv("状态", [
                ["连接状态", dyn(function (e) { return !e.desk ? "读取中…" : e.desk.hostConnected ? "● 已连接" : "○ 未连接" }, function (e) { return e.desk && e.desk.hostConnected ? "#3f8f55" : "#9a958c" })],
                ["会话编号", dyn(function (e) { return e.desk && e.desk.childSessionId != null ? String(e.desk.childSessionId) : "—" })],
                ["子任务状态", dyn(function (e) { return !e.desk ? "—" : e.desk.inSubtaskExecution ? "执行中" : "空闲" })],
                ["窗口状态", dyn(function (e) { var h = e.desk && e.desk.hostStatus; return !h ? "宿主未就绪" : h.trayMode && !h.isVisible ? "系统托盘中" : "窗口显示中" })],
                ["当前模式", dyn(function (e) { var h = e.desk && e.desk.hostStatus || {}; return ["观看模式 " + (h.watchMode ? "开" : "关"), "自适应 " + (h.smartSizing ? "开" : "关"), "置顶 " + (h.topmost ? "开" : "关")].join("  ·  ") })],
                ["说明", dyn(function (e) { return e.desk && e.desk.hostStatus && e.desk.hostStatus.statusText || "—" })]
            ]),
            SD.kv("操作", [
                ["窗口", deskOps(["显示远程桌面", "隐藏到托盘"], [{ visible: true }, { visible: false }], false)],
                ["连接", (function () { var m = SD.mini(["建立 / 恢复连接", "注销会话"]); m.ops = [
                    { path: "/api/child-session/connect", body: {}, done: "已发送连接请求", poll: true },
                    { confirm: "将注销远程桌面会话，会话中的程序会被关闭。", path: "/api/child-session/logoff", body: {}, done: "已注销远程桌面会话", poll: true }]; return m })()],
                ["切换", modes],
                ["发送按键", deskOps(["Win+Tab", "Win+D"], [{ shortcut: "Win+Tab" }, { shortcut: "Win+D" }], true)]
            ])
        ], ops: { "刷新": { get: true, path: "/api/child-session/status", poll: true, done: "已刷新" } }, actions: ["刷新"] },
        // 任务快捷控制：启停 / 上下切换托管；选择全局热键控制的队列；任务等待确认时可暂停或跳过等待
        { name: "任务快捷控制", en: "TASK CONTROL", live: true, api: "POST /api/dispatch/navigation/control", blocks: [
            SD.kv("快捷控制", [
                ["任务", (function () { var m = SD.mini(["任务启停", "上一个任务", "下一个任务"]); m.ops = [
                    { confirm: "将切换当前任务的启停。", path: "/api/dispatch/navigation/toggle", body: {}, done: "已发送启停指令", poll: true },
                    { confirm: "将切换到上一个任务。", path: "/api/dispatch/navigation/previous", body: {}, done: "已切换到上一个任务", poll: true },
                    { confirm: "将切换到下一个任务。", path: "/api/dispatch/navigation/next", body: {}, done: "已切换到下一个任务", poll: true }]; return m })()],
                ["热键控制队列", navQueue, "循环队列不能用热键上下切换"],
                ["控制状态", dyn(function (e) { var c = navCurrent(e); return !c ? "没有运行中的队列" : c.error ? "异常：" + c.error : c.cleaning ? "正在清理" : c.paused ? "已暂停，按启停热键继续" : c.prompt ? c.prompt.message || "等待确认" : c.state || "运行中" })],
                ["等待确认", (function () { var m = SD.mini(["暂停", "跳过等待"]); m.ops = [
                    { path: "/api/dispatch/navigation/control", body: function (e) { var c = navCurrent(e); return { action: "pause", taskId: c.taskId, token: c.prompt.token } }, when: function (e) { var c = navCurrent(e); return !!(c && c.prompt && c.prompt.buttons) }, done: "已暂停", poll: true },
                    { path: "/api/dispatch/navigation/control", body: function (e) { var c = navCurrent(e); return { action: "continue", taskId: c.taskId, token: c.prompt.token } }, when: function (e) { var c = navCurrent(e); return !!(c && c.prompt && c.prompt.buttons && !c.cleaning && !c.error) }, done: "已跳过等待", poll: true }]; return m })(), "", function (e) { var c = navCurrent(e); return !!(c && c.prompt) }]
            ])
        ], actions: [] },
        // 外部程序借用：申请借用远程桌面（可断开本机画面、设超时与等待），或归还现有租约
        { name: "外部借用", en: "LEASE", live: true, api: "POST /api/child-session/acquire", blocks: [
            SD.kv("申请借用", [["调用方名称", leaseCaller], ["断开本机画面", leaseDisconnect], ["借用时长", leaseTimeout], ["排队等待", leaseWait], ["等待时长", leaseWaitTimeout]]),
            leases
        ], ops: {
            "申请借用": { path: "/api/child-session/acquire", body: function () { return { caller: String(leaseCaller.v).trim(), disconnectRdpView: !!leaseDisconnect.v, timeoutSeconds: Number(leaseTimeout.v), waitForGrant: !!leaseWait.v, waitTimeout: Number(leaseWaitTimeout.v) } },
                       when: function () { return String(leaseCaller.v).trim() !== "" }, done: "已申请借用", poll: true },
            "全部归还": { confirm: "将归还所有外部程序借用的远程桌面。", path: "/api/child-session/release", body: function (e) { return { caller: null, leaseId: null } }, when: function (e) { return !!(e.desk && (e.desk.activeLeases || []).length) }, done: "已归还", poll: true }
        }, actions: ["申请借用", "全部归还"] },
        {name:"外部程序接口", en:"EXTERNAL CONTROL", live:true, blocks:[
            SD.note("管理外部程序占用的托管脚本、调用方和邮箱指令。",true)],
            ops:{"占用管理":{workspace:"占用管理"},"邮箱指令":{workspace:"邮箱指令"},"请求示例":{workspace:"请求示例"}},
            actions:["占用管理","邮箱指令","请求示例"]},
        { name: "虚拟显示器", en: "VIRTUAL DISPLAY", live: true, api: api, save: save, blocks: [
            SD.kv("虚拟显示器", [["无人值守时挂载", vdOn, "Display.IfEnableVirtualDisplay · 驱动不可用时无法开启（已开启的仍可关闭）"], ["刷新率", W(B(SD.seg(["1920×1080 @60", "1920×1080 @30"], idx(["1920x1080@60", "1920x1080@30"], D.VirtualDisplayMode)), "Display.VirtualDisplayMode", ["1920x1080@60", "1920x1080@30"]), vdOn), "Display.VirtualDisplayMode"],
                ["驱动状态", vd && vd.ready === false ? [SD.tag("不可用", "err"), vd.message || ""] : vd && vd.ready ? SD.tag("可用", "ok") : "未检测"],
                ["当前挂载", vd && vd.holding ? String(vd.holding) : "未挂载"]])
        ], ops: { "检测": { path: "/api/setting/virtual-display/check", body: {}, show: true },
                  "立即拆除": { confirm: "将拆除当前挂载的虚拟显示器；正在运行电脑端游戏任务时，游戏窗口会被挪走，本轮任务可能出错。", path: "/api/setting/virtual-display/detach", body: {}, show: true, done: "已拆除虚拟显示器", reload: true, off: !D.IfEnableVirtualDisplay } },
          actions: ["保存", "检测", "立即拆除"] },
        { name: "全局热键", en: "HOTKEY", live: true, api: api, save: save, blocks: [
            SD.kv("全局热键", [["启用全局热键", hkOn, "Hotkey.Enabled"], ["任务启停", hotkey(H.ToggleStartStop, "Hotkey.ToggleStartStop"), "Hotkey.ToggleStartStop"], ["上一个任务", hotkey(H.PreviousTask, "Hotkey.PreviousTask"), "Hotkey.PreviousTask"], ["下一个任务", hotkey(H.NextTask, "Hotkey.NextTask"), "Hotkey.NextTask"]])
        ], ops: { "保存并重新加载": { saveFirst: true, path: "/api/dispatch/hotkey/reload", body: {}, done: "热键已重新加载" } }, actions: ["保存并重新加载"] },
        // 端口：页面端口（网页版）与后端端口，保存到 config/HostInstance.json，下次启动时生效
        { name: "连接端口", en: "HOST", live: true, api: "config/HostInstance.json", blocks: [SD.kv("连接", [
            ["页面端口", Object.assign(SD.num(ports && ports.frontendPort || 36262), { min: 1024, max: 65535, k: "frontendPort" })],
            ["后端端口", Object.assign(SD.num(ports && ports.backendPort || port), { min: 1024, max: 65535, k: "backendPort" })],
            ["当前连接", [SD.tag("已连接", "ok"), "127.0.0.1:" + port]]])],
          ops: { "保存端口": { savePorts: true } }, actions: ["保存端口"] }
    ]
}

// ── 07 签到 ───────────────────────────────────────────────────────────
function sign(tools, accounts) {
    var G = tools.GameSign, save = { path: "/api/tools/update", base: {} }
    var ids = accounts.instances || []
    function has(t) { return t && t.indexOf("损坏") < 0 }
    var rows = ids.map(function (a) {
        var d = accounts[a.uid].GameSignAccount, s = { path: "/api/tools/sign/account/update", base: { accountId: a.uid } }
        var del = SD.mini(["删除"]); del.ops = [{ confirm: "将删除账号组「" + d.Name + "」及其各平台凭据。", path: "/api/tools/sign/account/delete", body: { accountId: a.uid }, reload: true, done: "已删除账号组" }]
        return [B(SD.inp(d.Name), "Name", null, s), B(SD.tog(d.Enabled), "Enabled", null, s), has(d.MiyousheToken) ? OK : WAIT, has(d.SklandToken) ? OK : d.SklandToken ? ERR : WAIT, has(d.KuroToken) ? OK : WAIT, has(d.TaygedoToken) ? OK : WAIT, del]
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
    var signOn = B(SD.tog(G.Enabled), "GameSign.Enabled")
    // 每个账号组一张卡：名称、启用与各平台凭据（可直接粘贴凭据，扫码登录仍需在网页版完成）
    var groupCards = ids.map(function (a, n) {
        var d = accounts[a.uid].GameSignAccount, s = { path: "/api/tools/sign/account/update", base: { accountId: a.uid } }
        function token(v, key) { return B(Object.assign(SD.inp(v || "", true), { secret: true }), key) }
        return { name: d.Name || ("账号组 " + (n + 1)), en: "ACCOUNT GROUP · " + String(n + 1).padStart(2, "0"), live: true, api: s.path, save: s,
            sortId: a.uid, sortGroup: "signGroups", blocks: [
            SD.kv("账号组", [["名称", B(SD.inp(d.Name), "Name")], ["启用", B(SD.tog(d.Enabled), "Enabled")]]),
            SD.kv("平台凭据", [["米游社", [token(d.MiyousheToken, "MiyousheToken"), has(d.MiyousheToken) ? OK : WAIT]], ["森空岛", [token(d.SklandToken, "SklandToken"), has(d.SklandToken) ? OK : d.SklandToken ? ERR : WAIT]],
                ["库街区", [token(d.KuroToken, "KuroToken"), has(d.KuroToken) ? OK : WAIT]], ["塔吉多", [token(d.TaygedoToken, "TaygedoToken"), has(d.TaygedoToken) ? OK : WAIT]]])
        ], ops: { "获取凭据":{workspace:"获取凭据",accountId:a.uid}, "删除账号组": { confirm: "将删除账号组「" + d.Name + "」及其各平台凭据。", path: "/api/tools/sign/account/delete", body: { accountId: a.uid }, reload: true, done: "已删除账号组" } },
           actions: ["保存", "获取凭据", "删除账号组"] }
    })
    return [
        { name: "签到设置", en: "SIGN", live: true, api: "POST /api/tools/update", save: save, blocks: [SD.kv("签到", [["启用签到", signOn, "GameSign.Enabled"], ["启动时签到", B(SD.tog(G.RunOnStartup), "GameSign.RunOnStartup"), "GameSign.RunOnStartup"], ["每日自动签到", B(SD.tog(G.AutoStart), "GameSign.AutoStart"), "GameSign.AutoStart"], ["结果通知", B(SD.tog(G.NotifyEnabled), "GameSign.NotifyEnabled"), "GameSign.NotifyEnabled"], ["便笺查询（本版停用）", B(Object.assign(SD.tog(false),{off:true}), "GameSign.ActivityEnabled"), "GameSign.ActivityEnabled"], ["上次签到", (G.LastSignDate || "—") + (status ? " · " + status : "")]])],
          // 未启用签到时不能立即签到（与网页版一致）；有未保存的改动时先保存再签到
          ops: { "立即签到": { confirm: "将立即为所有启用的账号组执行签到。", path: "/api/tools/sign", body: {}, show: true, done: "签到已开始", reload: true, saveFirst: true, when: function () { return !!valueOf(signOn) } } }, actions: ["保存", "立即签到"] },
        { name: "账号组", en: "ACCOUNTS", live: true, api: "POST /api/tools/sign/account/update", blocks: [SD.table("账号组", ["名称", "启用", "米游社", "森空岛", "库街区", "塔吉多", "操作"], rows, [1.7, 1, 0.9, 0.9, 0.9, 0.9, 0.8]), SD.note("在账号组录像卡中获取或更新平台凭据。", true)],
          ops: { "添加账号组": { path: "/api/tools/sign/account/add", body: {}, reload: true, done: "已添加账号组" } }, actions: ["保存", "添加账号组"] },
        { name: "签到结果", en: "RESULT", live: true, api: "GET /api/tools/get", blocks: results.length ? [SD.table("上次结果", ["平台", "账号组", "结果", "内容"], results)] : [SD.note("暂无签到结果。", true)], actions: [] }
    ].concat(groupCards)
}

// ── 08 历史记录 ───────────────────────────────────────────────────────
function replayArchive(response) {
    const ready = response?.code === 200 && Array.isArray(response.replays)
    const rows = ready ? response.replays.map(record => {
        const play = SD.mini(["播放"])
        play.ops = [{replayPath:record.filePath, off:!record.filePath}]
        return [record.failedAt, record.scriptName || "—", record.userName || "—", record.reason || "—", play]
    }) : []
    const table = SD.table("失败回放", ["失败时间", "托管", "账号", "原因", "操作"], rows, [1.6,1.3,1,1.7,0.8])
    return {name:"失败回放", en:"REPLAY ARCHIVE", live:true, api:"GET /api/history/replays",
        blocks:rows.length ? [table] : [SD.note(ready ? "暂无失败回放。" : (response?.message || "读取失败，请刷新重试。"), true)],
        ops:{"刷新":{refreshReplays:true}}, actions:["刷新"]}
}

function history(resp, filter) {
    var data = resp && resp.data ? resp.data : {}
    var dates = Object.keys(data).sort().reverse()
    var total = 0, okN = 0, errN = 0
    var items = dates.map(function (date) {
        var users = data[date], rows = []
        Object.keys(users).forEach(function (u) {
            (users[u].index || []).forEach(function (h) {
                total++
                if (h.status === "DONE") okN++
                else if (h.status === "ERROR") errN++
                var view = SD.mini(["日志"]); view.ops = [{ historyLog: h.jsonFile, title: date + " " + (h.date.slice(11, 16) || "") + " · " + u }]
                rows.push([h.date.slice(11, 16) || h.date, u, h.status === "DONE" ? OK : h.status === "ERROR" ? ERR : h.status === "SKIP" ? SD.tag("跳过", "idle") : WAIT, h.result || "", view])
            })
        })
        return { name: date, en: "HISTORY", live: true, api: "POST /api/history/search", blocks: [
            SD.stats("当日概览", [["记录", String(rows.length)], ["成功", String(rows.filter(function (r) { return r[2] === OK }).length)], ["异常", String(rows.filter(function (r) { return r[2] === ERR }).length)]]),
            SD.table("记录", ["时间", "账号", "结果", "说明", "操作"], rows, [0.8, 1.8, 0.8, 1.8, 0.8])], ops:{"账号统计":{workspace:"账号统计",users:users}},actions:["账号统计"] }
    })
    const preset=SD.sel(["今天","昨天","最近一周","最近一个月","最近两个月","最近三个月","最近半年"],filter.preset ?? 2)
    const apply=Object.assign(SD.mini(["查询"]),{ops:[{period:preset}]})
    var q = { name: "查询", en: "SEARCH", live: true, api: "POST /api/history/search", blocks: [
        SD.kv("筛选", [["快捷日期",[preset,apply]],["开始日期", { c: "date", v: filter.start, k: "start" }, "start_date"], ["结束日期", { c: "date", v: filter.end, k: "end" }, "end_date"], ["合并方式", { c: "seg", opts: ["按日", "按周", "按月"], v: filter.mode, k: "mode", enum: ["DAILY", "WEEKLY", "MONTHLY"] }, "mode"]]),
        SD.stats("范围统计", [["记录", String(total)], ["成功", String(okN)], ["异常", String(errN)]]),
        SD.note(dates.length ? "" : "这个时间范围内没有历史记录。", !dates.length)
    ], ops: { "查询": { query: true }, "本机日志":{workspace:"本机日志"} }, actions: ["查询","本机日志"] }
    return [q].concat(items)
}

// ── 01 主页 / 05 调度中心 ─────────────────────────────────────────────
function quickStart(taskOpts, power) {
    var opts = taskOpts.filter(o => o.value)
    return { name: "快速启动", en: "QUICK START", live: true, api: "POST /api/dispatch/start", blocks: [
        { t: "taskPicker", title: "任务对象", options: opts },
        SD.kv("START", [["运行模式", { c: "seg", opts: ["自动代理", "设置脚本", "循环运行"], v: 0, k: "mode", enum: ["AutoProxy", "ScriptConfig", "CycleRun"] }, "mode"], ["完成后", { c: "sel", opts: SD.POWER, v: idx(POWER_EN, power), k: "power", enum: POWER_EN }, "POST /api/dispatch/set/power"]]),
        SD.stats("NOW", [["运行中任务", "—", "activeTasks"], ["可运行对象", String(opts.length)], ["完成后", SD.POWER[idx(POWER_EN, power)]]]),
        { t: "run", title: "RUN STATUS" }
    ], ops: { "开始执行": { start: true }, "停止": { stopAll: true } }, actions: ["开始执行", "停止"] }
}

function proxyOverview(proxy) {
    const rows = Object.entries(proxy).map(([name, entry]) => [
        name, entry.LastProxyDate, String(entry.ProxyTimes), String(entry.ErrorTimes)
    ])
    const table = SD.table("ACCOUNTS", ["账号", "最后运行时间", "运行次数", "错误次数"], rows, [1.4, 1.9, 0.85, 0.85])
    table.pageRows = 11
    return { name: "代理状态", en: "PROXY STATUS", live: true, api: "POST /api/info/get/overview",
             blocks: rows.length ? [table] : [SD.note("今天暂无代理记录。", true)],
             ops: { "刷新": { overview: true } }, actions: ["刷新"] }
}

function homePlaceholder(index, message, retry) {
    return { name: index ? "代理状态" : "快速启动", en: index ? "PROXY STATUS" : "QUICK START",
             live: true, placeholder: true, blocks: [SD.note(message, true)],
             ops: { "重试": { homeRetry: true } }, actions: retry ? ["重试"] : [] }
}
// ── 05 调度中心：每个运行中的任务（通常是一条队列）一张卡，第一张是总览 ──────────
var STATUS_TAG = { "完成": OK, "运行": RUN, "等待": WAIT, "异常": ERR, "跳过": SD.tag("跳过", "idle"), "已暂停": SD.tag("已暂停", "idle"), "外部占用，等待释放": SD.tag("外部占用", "idle"), "任务被用户手动中止": SD.tag("已中止", "err") }
var MODE_ZH = { AutoProxy: "自动代理", ScriptConfig: "设置脚本", CycleRun: "循环运行", Update: "更新" }
function statusTag(s) { return STATUS_TAG[s] || SD.tag(s || "—", "idle") }
function taskProgress(t) {
    var list = t.task_info || [], done = 0
    for (var i = 0; i < list.length; i++) if (["完成", "跳过", "异常"].indexOf(list[i].status) >= 0) done++
    var cur = null
    for (var j = 0; j < list.length; j++) if (list[j].status === "运行") { cur = list[j]; break }
    return { done: done, total: list.length, current: cur }
}
function logLines(text) {
    var lines = String(text || "").split(/\r?\n/).filter(function (x) { return x.trim() !== "" })
    return lines.map(function (x) {
        var m = x.match(/^(\S+\s+\S+|\S+)\s+(.*)$/)
        var kind = /异常|错误|失败|ERROR/i.test(x) ? "e" : /完成|成功|SUCCESS/i.test(x) ? "s" : ""
        return m && /\d{1,2}:\d{2}/.test(m[1]) ? [m[1].slice(-8), m[2], kind] : ["", x, kind]
    })
}
// 发起任务（与网页版调度中心的任务控制相同）：选任务与模式；队列任务以自动代理运行时可从某个脚本开始；
// 脚本任务可只运行部分账号（全选即不限制）；完成后的电源动作选择即生效
function launchCard(launch) {
    var tasks = launch.tasks || []
    var api = "POST /api/dispatch/start"
    if (!tasks.length) return { name: "发起任务", en: "LAUNCH", live: true, api: api, blocks: [SD.note("还没有可运行的任务。", true)], actions: [] }
    var task = SD.sel(tasks.map(function (o) { return o.label }), 0)
    function picked() { return tasks[task.v] || {} }
    function isQueue() { return !!launch.queueScripts[picked().value] }
    function mode() { return launch.cycles?.[picked().value]?.Info?.CycleEnabled ? "CycleRun" : "AutoProxy" }
    var rows = [["任务", task], ["运行模式", {c:"dyn", f:() => mode() === "CycleRun" ? "循环运行" : "自动代理"}]]
    // 从某脚本开始：每条队列一个下拉，只显示所选队列的那个
    var resumes = {}
    Object.keys(launch.queueScripts).forEach(function (qid) {
        var opts = launch.queueScripts[qid]
        var sel = SD.sel(["从头开始"].concat(opts.map(function (o) { return o.label })), 0)
        resumes[qid] = { spec: sel, opts: opts }
        rows.push(["从脚本开始", sel, "队列任务以自动代理运行时可选", function () { return picked().value === qid && mode() === "AutoProxy" }])
    })
    var power = { c: "sel", opts: SD.POWER, v: idx(POWER_EN, launch.power), onPick: function (i) { return { path: "/api/dispatch/set/power", body: { signal: POWER_EN[i] }, done: "完成后：" + SD.POWER[i] } } }
    rows.push(["完成后", power, "选择即生效"])
    var blocks = [SD.kv("发起任务", rows)]
    // 每个任务独立保存勾选草稿。同一脚本出现在不同队列中时，各队列互不影响。
    const scopes = {}
    tasks.forEach(option => {
        const id = option.value
        const scripts = launch.queueScripts[id] || [option]
        const groupPicker = SD.sel(scripts.map(s => s.label), 0)
        const groups = scripts.map(script => {
            const users = (launch.users[script.value] || []).map(user => ({
                id:user.value, name:user.label, reason:user.reason, toggle:user.reason ? null : SD.tog(true)
            }))
            return {id:script.value, users:users}
        })
        if (scripts.length > 1) rows.push(["账号所属托管", groupPicker, "", () => picked().value === id])
        scopes[id] = {groups:groups, picker:groupPicker}
    })
    function scope() { return scopes[picked().value] }
    function currentGroup() { return scope().groups[scope().picker.v] }
    function scopeError() { return launch.scopeErrors?.[picked().value] || "" }
    const table = SD.table("本次运行账号", ["账号", "本次运行"], [], [3, 1])
    table.pageRows = 4
    table.rowSet = () => picked().value + "/" + (currentGroup()?.id || "")
    table.rowsFn = () => {
        const group = currentGroup()
        if (scopeError()) return [[scopeError(), ""]]
        if (!group?.users.length) return [["暂无账号", ""]]
        return group.users.map(u => [u.name, u.toggle || u.reason])
    }
    blocks.push(table)
    function body() {
        const id = picked().value, b = {taskId:id, mode:mode()}
        const r = resumes[id]
        if (r && b.mode === "AutoProxy" && r.spec.v > 0) b.resumeFromScriptId = r.opts[r.spec.v - 1].value
        const queueUsers = {}
        scope().groups.forEach(group => {
            const available = group.users.filter(u => u.toggle)
            const ids = available.filter(u => u.toggle.v).map(u => u.id)
            if (ids.length === available.length) return
            if (isQueue()) queueUsers[group.id] = ids
            else b.userIds = ids
        })
        if (Object.keys(queueUsers).length) b.queueUserIds = queueUsers
        return b
    }
    function anyUser() {
        if (scopeError()) return false
        const groups = scope().groups
        return !groups.some(g => g.users.some(u => u.toggle)) || groups.some(g => g.users.some(u => u.toggle?.v))
    }
    return { name: "发起任务", en: "LAUNCH", live: true, api: api, blocks: blocks,
        ops: { "开始": { confirm: "将按所选任务与模式开始运行。", path: "/api/dispatch/start", body: body, queueMode:isQueue, reload: true, done: "已开始运行", when: anyUser },
               "刷新": {reload:true} },
        actions: Object.keys(launch.scopeErrors || {}).length ? ["开始", "刷新"] : ["开始"] }
}
function dispatchCenter(snapshot, queueNames, launch) {
    queueNames = queueNames || {}
    var tasks = snapshot && snapshot.tasks ? snapshot.tasks : []
    var api = "GET /api/dispatch/runtime-snapshot"
    var head = launch ? [launchCard(launch)] : []
    if (!tasks.length) return head.concat([{ name: "调度空闲", en: "IDLE", live: true, api: api, blocks: [SD.kv("任务", [["状态", [WAIT, "没有运行中的任务"]], ["定时关联脚本", String((snapshot.scheduledScripts || []).length) + " 个"]])], ops: { "刷新": { reload: true } }, actions: ["刷新"] }])
    function title(t, i) { return t.queueId && queueNames[t.queueId] ? queueNames[t.queueId] : (t.mode === "ScriptConfig" ? "脚本设置" : t.mode === "Update" ? "更新" : "任务 " + String(i + 1).padStart(2, "0")) }
    // 总览：所有同时运行的任务并排列出，一眼看到各自进行到哪
    var overview = { name: "总览", en: "OVERVIEW · " + tasks.length + " RUNNING", live: true, api: api, blocks: [
        SD.stats("运行概况", [["运行中", String(tasks.filter(function (t) { return !t.stopping }).length)], ["正在停止", String(tasks.filter(function (t) { return t.stopping }).length)],
            ["循环队列", String(tasks.filter(function (t) { return t.isCycle }).length)], ["定时关联脚本", String((snapshot.scheduledScripts || []).length)]]),
        SD.table("任务", ["队列 / 任务", "当前脚本", "进度", "状态"], tasks.map(function (t, i) {
            var p = taskProgress(t)
            return [title(t, i) + (t.isCycle ? " · 循环" : ""), p.current ? p.current.name : "—", p.done + " / " + p.total, t.stopping ? [WAIT, "正在停止"] : p.current ? RUN : WAIT]
        }), [2, 2, 0.9, 1.1])
    ], ops: { "刷新": { reload: true }, "全部停止": { confirm: "将停止全部 " + tasks.length + " 个运行中的任务。", path: "/api/dispatch/stop", body: { taskId: "ALL" }, reload: true } }, actions: ["刷新", "全部停止"] }
    return head.concat([overview]).concat(tasks.map(function (t, i) {
        var p = taskProgress(t)
        var scripts = (t.task_info || []).map(function (s) {
            var users = s.userList || [], ud = users.filter(function (u) { return u.status === "完成" }).length
            var cu = users.filter(function (u) { return u.status === "运行" })[0]
            return [s.name, statusTag(s.status), users.length ? ud + " / " + users.length : "—", cu ? cu.name : "—"]
        })
        var tabs = [
            { name: "执行", api: api, blocks: [
                SD.kv("任务", [["队列", title(t, i)], ["模式", (MODE_ZH[t.mode] || t.mode) + (t.isCycle ? " · 循环" : "")], ["状态", t.stopping ? [WAIT, "正在停止"] : [RUN, "运行中"]],
                    ["当前脚本", p.current ? p.current.name : "—"], ["进度", p.done + " / " + p.total + " 个脚本"]]),
                (function () { var tb = SD.table("脚本", ["脚本", "状态", "账号", "当前账号"], scripts, [2.4, 1, 0.8, 1.4]); tb.pageRows = 6; return tb })()
            ], actions: ["停止任务", "上一个托管", "下一个托管"] },
            { name: "日志", api: api, blocks: [SD.log("日志 · " + (p.current ? p.current.name : title(t, i)), logLines(t.log), true)], actions: ["停止任务"] }
        ]
        if (t.isCycle && (t.cycleNextList || []).length)
            tabs.push({ name: "循环", api: api, blocks: [SD.table("下次运行", ["脚本", "下次运行", "状态"], t.cycleNextList.map(function (c) {
                return [c.scriptName, c.nextRunAt.slice(5, 16), c.isRunning ? RUN : c.isDue ? SD.tag("到点", "run") : WAIT]
            }), [2.4, 1.4, 1])], actions: ["停止任务"] })
        return { runtimeKey: t.taskId, name: title(t, i), en: t.mode.toUpperCase() + (t.isCycle ? " · CYCLE" : "") + " · " + String(i + 1).padStart(2, "0"), live: true,
            ops: { "停止任务": { confirm: "将停止「" + title(t, i) + "」。", path: "/api/dispatch/stop", body: { taskId: t.taskId }, reload: true },
                   "上一个托管": { path: "/api/dispatch/navigation/previous", body: {} }, "下一个托管": { path: "/api/dispatch/navigation/next", body: {} } },
            tabs: tabs }
    }))
}
