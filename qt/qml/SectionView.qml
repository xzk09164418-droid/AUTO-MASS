import QtQuick
import "."
import "SectionData.js" as SD
import "Live.js" as Live

// 二级界面（参考 PV 1:19 构图）：左上品牌与竖线、黑色部门卡、左下录像带串、上方标志剪影、
// 右侧分页点 + 档案卡 + 铭牌、底部字幕。
// 进入：被点击的方块随机选一种方式（弧线 / 拉伸 / 折叠 / 残影）飞成部门卡，
// 位置、尺寸、底色在整个过程中同时插值；返回时按同一方式飞回。
FocusScope {
    id: view

    property var departments: []
    property int index: -1
    property bool opened: false
    readonly property bool busy: index >= 0
    readonly property var d: index >= 0 ? departments[index] : null
    readonly property var conf: d ? SD.sections[d.n] : null
    // 仅离线预览使用示例；联网模式在首次读取完成前显示连接状态。
    property var api: null                  // BackendSupervisor（后端就绪时）
    property var enhanced: null             // EnhancedComponent
    // 增强挡位复用同一场景，按部门组织行列。
    readonly property bool arrayMode: Theme.motion === "enhanced" && Theme.enhancedAvailable && !!d
    property var arrayHostItem: null        // Main.qml 里常驻的 ArchiveArray3D（未加载完时为 null）
    readonly property var arrayItem: arrayMode ? arrayHostItem : null
    readonly property bool arrayDetail: !!arrayItem && arrayItem.detailOpen
    readonly property var arrayColumns: {
        if (!arrayMode || !d) return []
        if (!items.length) return emulatorPage ? [{name:d.zh, rows:[emulatorConfigs.empty.name]}] : []
        if (d.key === "queue")
            return items.map(it => ({name:it.name, en:it.en, accounts:it.accounts || [],
                rowIcons:it.rowIcons || null, configRow:it.configRow !== false, icon:it.icon || ""}))
        if (d.key === "scripts")
            return items.map(it => ({uid:it.uid,name:it.name, icon:it.icon || "", rows:SD.pages(it).map(p => p.name)}))
        return [{name:d.zh, rows:items.map(it => it.name), rowIcons:items.map(it => it.artwork || it.icon || "")}]
    }
    property bool arrayPanelUsed: false
    property bool syncingArray: false
    function syncArray() {
        if (syncingArray || !opened || !arrayItem || arrayItem.mode !== d.key || d.key === "queue" || workspace.record) return
        const a = arrayItem
        if (!items.length) {
            if (d.key === "scripts" && a.detailOpen) a.close()
            return
        }
        const lane = a.singleColumn ? 0 : target
        const row = a.singleColumn ? target : Math.max(0, Math.min(panel.tab, SD.pages(item).length - 1))
        syncingArray = true
        if (!a.singleColumn && panel.tab !== row) panel.tab = row
        if (lane !== a.lane || row !== a.row) a.moveTo(a.cellLane + lane - a.lane, 12 + row)
        syncingArray = false
    }
    property bool onlineHome: false
    readonly property bool isHome: !!d && d.key === "home"
    readonly property bool showingOnlineHome: onlineHome && isHome
    property var homeCards: [Live.homePlaceholder(0, "等待后端连接…", false), Live.homePlaceholder(1, "等待后端连接…", false)]
    property var homeHotkeys: null
    readonly property var controlGuide: SD.controlGuide(api?.port, homeHotkeys)
    property int quickRequest: 0
    property int overviewRequest: 0
    signal uiSettings(var patch)
    onApiChanged: {
        homeHotkeys = null
        const source = api
        if (source) call("/api/setting/get", {}, r => {
            if (api !== source || r.code !== 200) return
            homeHotkeys = r.data.Hotkey || null
            uiSettings(r.data.UI || {})
        })
        quickRequest++
        overviewRequest++
        if (!api) homeCards = [Live.homePlaceholder(0, "等待后端连接…", false), Live.homePlaceholder(1, "等待后端连接…", false)]
        if (!api && onlineHome) { const cached=Object.assign({},live); delete cached.activity; live=cached }
        if (opened && d) fetchLive(d.key)
    }
    property var live: ({})                 // 部门 key → 条目
    property string liveState: ""           // loading / ok / error
    property string liveMessage: ""
    readonly property bool isLive: showingOnlineHome ? !!api && !item?.placeholder : !!(d && live[d.key])
    readonly property bool emulatorPage: !!d && d.key === "emulators"
    readonly property var connectionCard: ({
        name:d?.zh || "", en:"CONNECTION", live:true,
        blocks:[SD.note(!api ? "等待后端连接…" : liveState === "error" ? liveMessage : "正在读取配置…", true)],
        ops:{"重试":{reload:true}}, actions:api && liveState === "error" ? ["重试"] : []
    })
    readonly property var items: emulatorPage ? emulatorConfigs.records : showingOnlineHome ? homeCards.concat(controlGuide)
        : d?.key === "scripts" ? scriptShelf.filtered : d && live[d.key] ? live[d.key]
        : onlineHome ? [connectionCard] : conf ? conf.items : []
    onItemsChanged: {
        if (!opened) return
        target = Math.min(target, Math.max(0, items.length - 1))
        if (arrayMode) { Qt.callLater(syncArray); return }
        if (chain.introTarget === 1) { chain.items = items; chain.goTo(target, 1) }
    }
    // ── 后端接入 ──────────────────────────────────────────────────────────
    function call(path, body, cb) {
        if (!api) { cb({code:0,message:"后端未连接"}); return }
        api.request(path, JSON.stringify(body || {}), text => {
            let r = null
            try { r = JSON.parse(text) } catch (e) { r = { code: 0, message: "响应无法解析" } }
            cb(r)
        })
    }
    // 依次请求多个接口：steps = [[name, path, body], ...]，全部返回后 done(map)
    function callAll(steps, done) {
        const generation = sectionGeneration
        const out = {}
        let i = 0
        const next = () => {
            if (generation !== sectionGeneration) return
            if (i >= steps.length) { done(out); return }
            const st = steps[i++]
            if (!api) { out[st[0]]={code:0,message:"后端未连接"}; next(); return }
            // body 为 null 表示 GET 接口
            if (st[2] === null) api.get(st[1], text => { let r = { code: 0 }; try { r = JSON.parse(text) } catch (e) {} out[st[0]] = r; next() })
            else call(st[1], st[2], r => { out[st[0]] = r; next() })
        }
        next()
    }
    // 会随运行状态变化的数据（远程桌面连接、热键控制队列等）：控件的可用条件与状态文字按它即时刷新
    property var env: ({})
    property int deskStatusRequest: 0
    function pollDesk() {
        if (!api || !d) return
        if (d.key === "emulators") {
            // 当前模拟器的实例状态（2.0 模拟器另有面板，不在这里轮询）
            const it = item
            if (!it || !it.uid || !it.live || it.deviceType === "emulator2") return
            call("/api/emulator/status", { emulatorId: it.uid }, r => {
                const all = Object.assign({}, env.devices || {})
                all[it.uid] = r.code === 200 && r.data ? (r.data[it.uid] || {}) : {}
                env = Object.assign({}, env, { devices: all, deviceError: r.code === 200 ? "" : (r.message || "") })
            })
            return
        }
        const request = ++deskStatusRequest
        api.get("/api/child-session/status", text => {
            if (request !== deskStatusRequest) return
            let r = null; try { r = JSON.parse(text) } catch (e) {}
            if (r && r.code === 200) env = Object.assign({}, env, { desk: r.data })
        })
        api.get("/api/dispatch/navigation/state", text => {
            let r = null; try { r = JSON.parse(text) } catch (e) {}
            if (r && r.code === 200) env = Object.assign({}, env, { nav: r.data })
        })
    }
    Timer {
        interval: 3000; repeat: true
        running: view.opened && !!view.api && !!view.d && (view.d.key === "localControls" || view.d.key === "emulators")
        triggeredOnStart: true
        onTriggered: view.pollDesk()
    }
    HotkeyRecorder { id: recorder; host: view }
    LogViewer { id: logViewer; objectName: "logViewer"; host: view }
    function copyText(value) { fileLocations.copyText(value); toast.show("已复制") }
    function signatureExample(base, scriptId, callerId, holdId, operation) {
        return ['import os, json, uuid, base64, hmac, hashlib, urllib.request',
            'from datetime import datetime, timezone',
            'command = dict(version=1, requestId=str(uuid.uuid4()), callerId='+JSON.stringify(callerId)+',',
            '    action='+JSON.stringify(operation)+', scriptId='+JSON.stringify(scriptId)+', holdId='+JSON.stringify(holdId)+', ttlSeconds=1800,',
            '    issuedAt=datetime.now(timezone.utc).isoformat())',
            'payload = base64.urlsafe_b64encode(json.dumps(command).encode()).decode().rstrip("=")',
            'signature = hmac.new(os.environ["AUTO_MAS_CONTROL_SECRET"].encode(), payload.encode(), hashlib.sha256).hexdigest()',
            'body = json.dumps(dict(payload=payload, signature=signature)).encode()',
            'url = '+JSON.stringify(base+'/api/dispatch/external-holds/')+' + command["action"]',
            'request = urllib.request.Request(url, data=body, headers={"Content-Type":"application/json"})',
            'with urllib.request.urlopen(request, timeout=10) as response: print(response.read().decode())'].join("\n")
    }
    function askWorkspace(title, detail, action) { modal.ask(title,detail,"","确认",true,action) }
    function toastText(text) { toast.show(text) }
    property int replayRequest: 0
    function loadReplayArchive() {
        const request = ++replayRequest
        api.get("/api/history/replays", text => {
            if (request !== replayRequest || !opened || d?.key !== "history") return
            let response
            try { response = JSON.parse(text) } catch (e) {}
            const list = live.history
            if (list) setLive("history", list.map(entry => entry.en === "REPLAY ARCHIVE" ? Live.replayArchive(response) : entry))
        })
    }
    property var historyFilter: ({ start: "", end: "", mode: 0 })
    // 运行快照：托管脚本 / 循环队列运行时锁定对应配置，结束后解锁（与网页版一致）
    property var runtimeTasks: []
    readonly property bool runLocked: !!d && Live.itemLocked(d.key, item, runtimeTasks)
    property int runtimeRequestGeneration: -1
    function pollRuntime() {
        const generation = sectionGeneration
        if (!api || runtimeRequestGeneration === generation) return
        runtimeRequestGeneration = generation
        api.get("/api/dispatch/runtime-snapshot?includeLogs=false", text => {
            if (runtimeRequestGeneration === generation) runtimeRequestGeneration = -1
            if (sectionGeneration !== generation || !opened) return
            let snap = null
            try { snap = JSON.parse(text) } catch (e) {}
            if (snap && Array.isArray(snap.tasks)) runtimeTasks = demoSnapshot ? demoSnapshot.tasks : snap.tasks
        })
    }
    Timer {
        interval: 3000; repeat: true; triggeredOnStart: true
        running: view.opened && !!view.api && !!view.d && ["scripts", "queue"].indexOf(view.d.key) >= 0
        onTriggered: view.pollRuntime()
    }
    property var lastSnapshot: null
    property var schedulerNames: null
    property var schedulerPaths: ({})       // 脚本 ID → 启动程序路径（阵列图标唱片）
    property int sectionGeneration: 0
    property bool snapshotPending: false
    function currentScheduler(generation) {
        return generation === sectionGeneration && opened && api && d?.key === "scheduler"
    }
    function refreshScheduler() {
        const generation = sectionGeneration
        if (!currentScheduler(generation) || !schedulerNames || snapshotPending) return
        snapshotPending = true
        api.get("/api/dispatch/runtime-snapshot", text => {
            if (!currentScheduler(generation)) return
            snapshotPending = false
            let snap
            try { snap = demoSnapshot || JSON.parse(text) } catch (e) { return }
            if (!Array.isArray(snap?.tasks) || JSON.stringify(snap) === JSON.stringify(lastSnapshot)) return
            lastSnapshot = snap
            const previous = item?.runtimeKey
            const previousTab = panel.tab
            const list = [live.scheduler[0]].concat(Live.dispatchCenter(snap, schedulerNames, null, schedulerPaths))
            const position = previous ? list.findIndex(row => row.runtimeKey === previous) : target
            setLive("scheduler", list)
            if (previous) {
                select(position < 0 ? 1 : position)
                // 总览与任务共用稳定刷新，但总览没有页签。
                panel.tab = position < 0 ? 0 : Math.min(previousTab, (list[position].tabs?.length || 1) - 1)
            }
        })
    }
    Timer {
        interval: 1500; repeat: true
        running: view.opened && !!view.api && view.d?.key === "scheduler" && !!view.schedulerNames
        onTriggered: view.refreshScheduler()
    }
    property var demoSnapshot: null         // 演示 / 自检：用模拟的运行快照代替后端返回（不启动任何真实任务）
    function today(offset) {
        const d = new Date(Date.now() + (offset || 0) * 86400000)
        return Qt.formatDate(d, "yyyy-MM-dd")
    }
    function setLive(key, list) {
        const next = Object.assign({}, live)
        next[key] = list
        live = next
        liveState = "ok"
        liveMessage = ""
    }
    function fail(r) { liveState = "error"; liveMessage = r && r.message ? r.message : "读取失败" }
    HomeRuns {
        id: liveHomeRuns
        api: view.api
        watching: view.opened && !!view.d && view.d.key === "home" && view.target === 0
        onMessage: text => toast.show(text)
    }
    HomeRuns { id: previewRuns; api: null; watching: false }
    function setHomeCard(index, card) {
        const next = homeCards.slice()
        next[index] = card
        homeCards = next
    }
    function loadOverview() {
        if (!api) return
        const request = ++overviewRequest
        call("/api/info/get/overview", {}, result => {
            if (request !== overviewRequest) return
            const proxy = result.data && result.data.Proxy
            setHomeCard(1, result.code === 200 && proxy && typeof proxy === "object" && !Array.isArray(proxy)
                ? Live.proxyOverview(proxy)
                : Live.homePlaceholder(1, result.message || "账号统计读取失败", true))
        })
    }
    function loadQuickStart() {
        if (!api) return
        const request = ++quickRequest
        call("/api/info/combox/task", {}, tasks => {
            if (request !== quickRequest) return
            if (tasks.code !== 200 || !Array.isArray(tasks.data)) {
                setHomeCard(0, Live.homePlaceholder(0, tasks.message || "任务列表读取失败", true))
                return
            }
            call("/api/dispatch/get/power", {}, power => {
                if (request !== quickRequest) return
                if (power.code !== 200 || !Live.POWER_EN.includes(power.signal)) {
                    setHomeCard(0, Live.homePlaceholder(0, power.message || "电源动作读取失败", true))
                    return
                }
                liveHomeRuns.options = tasks.data
                setHomeCard(0, Live.quickStart(tasks.data, power.signal))
                liveHomeRuns.poll()
            })
        })
    }
    function fetchLive(key) {
        const generation = ++sectionGeneration
        schedulerNames = null
        snapshotPending = false
        if (!api) { liveState = ""; return }
        if (key === "activity") {
            liveState = "loading"
            activityShelf.refresh(generation)
            return
        }
        if (key === "home") { loadQuickStart(); loadOverview(); return }
        const supported = ["home", "scripts", "emulators", "queue", "scheduler", "localControls", "gamesign", "history", "settings"]
        if (supported.indexOf(key) < 0) { liveState = ""; return }
        liveState = "loading"
        if (key === "scripts") {
            callAll([["s", "/api/scripts/get", { includeUsers: true }], ["e", "/api/info/combox/emulator", {}]],
                    m => Qt.callLater(() => {
                        // 在网络回调返回后再构建托管卡片，切页时丢弃旧请求。
                        if (generation !== sectionGeneration || !opened || d?.key !== key) return
                        if (m.s.code === 200) setLive(key, Live.scripts(m.s, m.e.code === 200 ? m.e.data : []))
                        else fail(m.s)
                    }))
        } else if (key === "queue") {
            callAll([["q", "/api/queue/get", {}], ["s", "/api/info/combox/script", {}], ["sc", "/api/scripts/get", {}]], m => {
                if (m.q.code !== 200) { fail(m.q); return }
                const steps = []
                m.q.index.forEach(q => { steps.push(["t" + q.uid, "/api/queue/time/get", { queueId: q.uid }]); steps.push(["i" + q.uid, "/api/queue/item/get", { queueId: q.uid }]) })
                callAll(steps, n => {
                    const times = {}, items = {}
                    m.q.index.forEach(q => { times[q.uid] = n["t" + q.uid]; items[q.uid] = n["i" + q.uid] })
                    // 队列项所选脚本的启动程序：阵列里作图标唱片
                    const paths = {}
                    if (m.sc.code === 200) m.sc.index.forEach(x => { const c = m.sc.data[x.uid]; if (c && c.Script && c.Script.ScriptPath) paths[x.uid] = c.Script.ScriptPath })
                    setLive(key, Live.queues(m.q, times, items, m.s.code === 200 ? m.s.data : [], paths))
                })
            })
        } else if (key === "emulators") {
            emulatorConfigs.load()
        } else if (key === "settings" || key === "localControls") {
            // 设置：QQ 机器人绑定状态决定开关能否打开；本地控制：虚拟显示驱动状态、远程桌面状态与热键控制队列
            const extra = key === "settings" ? [["q", "/api/setting/openclaw-qq/status", {}]]
                : [["d", "/api/setting/virtual-display/status", {}], ["n", "/api/dispatch/navigation/state", null]]
            callAll([["g", "/api/setting/get", {}], ["v", "/api/info/version", {}]].concat(extra), m => {
                if (m.g.code !== 200) { fail(m.g); return }
                const ver = m.v.current_hash ? "本地 " + m.v.current_hash.slice(0, 8) : ""
                if (key === "settings") { setLive(key, Live.settings(m.g.data, ver, m.q && m.q.code === 200 ? m.q : null)); return }
                const vd = m.d && m.d.code === 200 ? { ready: (m.d.results || []).every(x => x.passed), message: m.d.message, holding: m.d.holding } : null
                if (m.n && m.n.code === 200) env = Object.assign({}, env, { nav: m.n.data })
                setLive(key, Live.local(m.g.data, api.port, vd, env.nav, api.ports()))
                pollDesk()
            })
        } else if (key === "gamesign") {
            callAll([["t", "/api/tools/get", {}], ["a", "/api/tools/sign/account/list", {}]], m => m.t.code === 200 ? setLive(key, Live.sign(m.t.data, m.a.code === 200 ? m.a.data : {})) : fail(m.t))
        } else if (key === "history") {
            if (!historyFilter.start) historyFilter = { start: today(-6), end: today(0), mode: 0 }
            const f = historyFilter
            const query = {mode:["DAILY","WEEKLY","MONTHLY"][f.mode], start_date:f.start, end_date:f.end}
            call("/api/history/search", query, r => {
                if (generation !== sectionGeneration || d?.key !== key) return
                const list = Live.history(r, f)
                if (r.code !== 200) list[0].blocks = [list[0].blocks[0],
                    SD.note(r.message || "历史记录读取失败，请重新查询。", true)]
                list.splice(1, 0, Live.replayArchive({message:"正在读取失败回放…"}))
                setLive(key, list)
                loadReplayArchive()
            })
        } else if (key === "scheduler") {
            // 发起任务需要：任务列表、脚本名、各队列的队列项（从某脚本开始）、各脚本账号（账号范围）、当前电源动作
            callAll([["q", "/api/queue/get", {}], ["t", "/api/info/combox/task", {}], ["cs", "/api/info/combox/script", {}],
                     ["s", "/api/scripts/get", { includeUsers: true }], ["p", "/api/dispatch/get/power", {}]], m => {
                if (!currentScheduler(generation)) return
                const queues = m.q
                const steps = queues.code === 200 ? queues.index.map(q => ["i" + q.uid, "/api/queue/item/get", { queueId: q.uid }]) : []
                callAll(steps, items => {
                    if (!currentScheduler(generation)) return
                    api.get("/api/dispatch/runtime-snapshot", text => {
                        if (!currentScheduler(generation)) return
                        let snap
                        try { snap = demoSnapshot || JSON.parse(text) } catch (e) {}
                        if (!Array.isArray(snap?.tasks)) { fail({message:"无法读取运行状态"}); return }
                        lastSnapshot = snap
                        const names = {}
                        if (queues.code === 200) queues.index.forEach(q => { const d = queues.data[q.uid]; if (d && d.Info) names[q.uid] = d.Info.Name })
                        if (demoSnapshot && demoSnapshot.queueNames) Object.assign(names, demoSnapshot.queueNames)
                        const scriptNames = {}
                        if (m.cs.code === 200) m.cs.data.forEach(o => scriptNames[o.value] = o.label.replace(/^通用 - /, ""))
                        const queueScripts = {}, scopeErrors = {}
                        if (queues.code === 200) queues.index.forEach(q => {
                            const r = items["i" + q.uid], seen = []
                            if (r?.code === 200) r.index.forEach(x => {
                                const sid = r.data[x.uid]?.Info?.ScriptId
                                if (sid && sid !== "-" && !seen.includes(sid)) seen.push(sid)
                            })
                            else scopeErrors[q.uid] = "队列项读取失败，请刷新重试"
                            queueScripts[q.uid] = seen.map(sid => ({value:sid, label:scriptNames[sid] || sid}))
                        })
                        const users = {}
                        if (m.s.code === 200) m.s.index.forEach(x => {
                            const ur = m.s.users && m.s.users[x.uid]
                            if (ur?.code !== 200) return
                            users[x.uid] = ur.index.filter(u => ur.data[u.uid]?.Info).map(u => {
                                const info = ur.data[u.uid].Info
                                const reason = !info.Status ? "未启用" : info.RemainedDay === 0 ? "天数已耗尽" : ""
                                return {value:u.uid, label:info.Name || u.uid, reason:reason}
                            })
                        })
                        const tasks = m.t.code === 200 ? m.t.data.filter(o => o.value) : []
                        tasks.forEach(task => {
                            const scripts = queueScripts[task.value] || [task]
                            if (queues.code !== 200 || scripts.some(script => !users[script.value]))
                                scopeErrors[task.value] = "账号范围读取失败，请刷新重试"
                        })
                        const launch = { cycles:queues.data || {}, tasks:tasks, queueScripts:queueScripts, users:users, scopeErrors:scopeErrors,
                                         power: m.p.code === 200 ? m.p.signal : "NoAction" }
                        const paths = {}
                        if (m.s.code === 200) m.s.index.forEach(x => { const c = m.s.data[x.uid]; if (c?.Script?.ScriptPath) paths[x.uid] = c.Script.ScriptPath })
                        schedulerPaths = paths
                        setLive(key, Live.dispatchCenter(snap, names, launch, paths))
                        schedulerNames = names
                    })
                })
            })
        }
    }
    // 保存：只提交改过的字段，同一接口的字段合并成一个请求
    property bool saving: false
    function save(then) {
        if (saving) return
        const it = item
        if (!it || !it.live) return
        if (runLocked && it.lockAll) { toast.show("任务运行中，配置已锁定；任务结束后可编辑"); return }
        const reqs = Live.collect(it)
        if (!reqs.length) { toast.show("没有需要保存的改动"); if (then) then(); return }
        const snapshot = []
        Live.eachSpec(it, spec => {
            if (spec.dirty && spec.key) snapshot.push({ spec: spec, value: JSON.stringify(Live.valueOf(spec)) })
        })
        saving = true
        let i = 0
        const next = () => {
            if (i >= reqs.length) {
                snapshot.forEach(saved => {
                    if (JSON.stringify(Live.valueOf(saved.spec)) === saved.value) saved.spec.dirty = false
                })
                saving = false
                panel.edits++
                toast.show("已保存到后端 · " + reqs.length + " 个请求")
                if (it.reloadOnSave) fetchLive(d.key)
                if (then) then()
                return
            }
            const q = reqs[i++]
            call(q.path, q.body, r => {
                if (r.code === 200) {
                    if (q.path === "/api/setting/update" && q.body.data?.UI) uiSettings(q.body.data.UI)
                    if (q.path === "/api/setting/update" && q.body.data?.Hotkey)
                        homeHotkeys = Object.assign({}, homeHotkeys || {}, q.body.data.Hotkey)
                    if (q.path === "/api/scripts/update" || q.path === "/api/scripts/user/update")
                        scriptShelf.acknowledge(q)
                    next()
                }
                else { saving = false; toast.show("保存失败：" + (r.message || q.path)) }
            })
        }
        next()
    }
    ActivityShelf { id: activityShelf; host:view }
    ArchiveWorkspace { id: workspace; host: view; archive: panel }
    onIndexChanged: workspace.leave()
    onItemChanged: if (workspace.record && workspace.source !== item) workspace.leave()
    onTargetChanged: {
        workspace.leave()
        if(opened && api && d?.key==="activity" && liveState==="ok") activityShelf.load(activityShelf.games[target]?.[0],false)
    }

    function exec(op) {
        const done = r => {
            if (r.code === 200 || r.code === undefined) {
                toast.show(op.show && r.message ? r.message : (op.done || "已完成"))
                if (op.reload) fetchLive(d.key)
                if (op.path === "/api/child-session/window" && r.data?.hostStatus) {
                    deskStatusRequest++
                    env = Object.assign({}, env, {desk:r.data})
                } else if (op.poll) pollDesk()
            } else toast.show("操作失败：" + (r.message || op.path))
        }
        const body = typeof op.body === "function" ? op.body(env) : op.body
        if (op.get) api.get(op.path, text => { let r = { code: 0 }; try { r = JSON.parse(text) } catch (e) {} done(r) })
        else if (op.queueMode && op.queueMode()) {
            call("/api/queue/get", {queueId:body.taskId}, result => {
                const info = result.data?.[body.taskId]?.Info
                if (result.code !== 200 || !info) { toast.show("读取队列类型失败，请重试"); return }
                body.mode = info.CycleEnabled ? "CycleRun" : "AutoProxy"
                if (info.CycleEnabled) delete body.resumeFromScriptId
                call(op.path, body, done)
            })
        } else call(op.path, body, done)
    }
    function runOp(op) {
        if (!op) return
        if (op.workspace) { workspace.begin(op.workspace, op); return }
        if (op.perform) { op.perform(); return }
        if (op.overview || op.homeRetry) {
            if (op.overview || target === 1) loadOverview()
            else loadQuickStart()
            return
        }
        if (op.period !== undefined) {
            const preset=op.period.v
            let start=today(preset===1?-1:preset===2?-7:0),end=today(preset===1?-1:0)
            if(preset>=3){
                const now=new Date(),day=now.getDate()
                now.setDate(1);now.setMonth(now.getMonth()-(preset===6?6:preset-2))
                now.setDate(Math.min(day,new Date(now.getFullYear(),now.getMonth()+1,0).getDate()))
                start=Qt.formatDate(now,"yyyy-MM-dd")
            }
            historyFilter={start:start,end:end,preset:preset,mode:preset>=5?2:preset>=3?1:0}
            fetchLive("history")
            return
        }
        if (op.query) {
            const f = Object.assign({}, historyFilter)
            const s = Live.pick(item, "start"), e = Live.pick(item, "end"), m = Live.pick(item, "mode")
            if (s) f.start = s
            if (e) f.end = e
            if (m) f.mode = ["DAILY", "WEEKLY", "MONTHLY"].indexOf(m)
            historyFilter = f
            fetchLive("history")
            return
        }
        if (op.start) {
            const tasks = panel.selectedTasks.slice()
            if (!tasks.length || liveHomeRuns.submitting) return
            const mode = tasks.length > 1 ? "AutoProxy" : Live.pick(item, "mode")
            const power = Live.pick(item, "power")
            const modeName = {AutoProxy:"自动代理", ScriptConfig:"设置脚本", CycleRun:"循环运行"}[mode]
            modal.ask("开始执行", "将以「" + modeName + "」启动 " + tasks.length + " 个任务，完成后执行「" + SD.POWER[Live.POWER_EN.indexOf(power)] + "」。",
                "POST /api/dispatch/start", "开始执行", false, () => liveHomeRuns.launch(tasks, mode, power))
            return
        }
        if (op.resume) { liveHomeRuns.resume(panel.selectedTasks); return }
        if (op.stopAll) {
            const tasks = liveHomeRuns.activeTasks
            if (!liveHomeRuns.snapshotReady || liveHomeRuns.snapshotError) { liveHomeRuns.poll(); toast.show("正在同步运行状态，请稍后重试"); return }
            if (!tasks.length) { toast.show("当前没有运行中的任务"); return }
            modal.ask("停止任务", "将停止 " + tasks.length + " 个运行中的任务。", "POST /api/dispatch/stop", "停止", true, () => {
                let replies = 0, failures = []
                tasks.forEach(t => call("/api/dispatch/stop", { taskId: t.taskId }, r => {
                    if (r.code !== 200) failures.push(r.message || "请求失败")
                    if (++replies === tasks.length) {
                        toast.show(failures.length ? "停止失败：" + failures.join("；") : "已发送停止指令")
                        liveHomeRuns.poll()
                    }
                }))
            })
            return
        }
        if (op.exportBackup) {
            env = Object.assign({}, env, { exporting: true })
            toast.show("正在导出数据备份…")
            api.exportBackup(text => {
                env = Object.assign({}, env, { exporting: false })
                let r = {}; try { r = JSON.parse(text) } catch (e) {}
                if (r.ok) { toast.show("已导出：" + r.path); fileLocations.openFolder(r.path) }
                else toast.show("导出失败：" + (r.message || ""))
            })
            return
        }
        if (op.exportLogs) {
            const path = fileLocations.exportLogs()
            if (path) { toast.show("已打包日志：" + path); fileLocations.openFolder(path) }
            else toast.show("打包日志失败")
            return
        }
        if (op.savePorts) {
            const err = api.savePorts(Number(Live.pick(item, "backendPort")))
            toast.show(err ? "保存失败：" + err : "端口已保存，下次启动时生效")
            return
        }
        if (op.refreshReplays) { loadReplayArchive(); return }
        if (op.replayPath) {
            if (!fileLocations.openFile(op.replayPath)) toast.show("无法打开回放文件，请检查文件是否存在")
            return
        }
        if (op.historyLog) { logViewer.open(op.historyLog, op.title || ""); return }
        if (op.captureHotkey) {
            const field = op.captureHotkey
            recorder.bossMode = !!op.boss
            recorder.begin(value => { field.v = value; field.dirty = true; panel.edits++; panel.rebuild(); toast.show("热键已录入，请保存配置后生效") })
            return
        }
        if (!op.path) { if (op.reload) fetchLive(d.key); return }
        // saveFirst：先保存未保存的改动再执行；有确认语时先确认
        const go = () => op.saveFirst ? save(() => exec(op)) : exec(op)
        if (op.confirm) { modal.ask("确认操作", op.confirm, "POST " + op.path, "确认", true, go); return }
        go()
    }
    function liveAction(name) {
        const page = SD.pages(item)[Math.min(panel.tab, SD.pages(item).length - 1)]
        const ops = Object.assign({}, item.ops || {}, page.ops || {})
        if (name === "保存") { save(); return }
        if (ops[name]) { runOp(ops[name]); return }
        toast.show("「" + name + "」尚未接入后端")
    }
    EmulatorConfigs {
        id: emulatorConfigs
        objectName: "emulatorConfigs"
        host: view
        onMessage: text => toast.show(text)
        onConfirmRemoval: (label, callback) => modal.ask("删除模拟器配置","删除「"+label+"」的配置？","POST /api/emulator/delete","删除",true,callback)
    }
    property int target: 0
    readonly property var item: items.length ? items[Math.min(target, items.length - 1)] : emulatorPage ? emulatorConfigs.empty : null

    property var hub: null          // 一级索引：取方块实时位置、在飞行期间隐藏对应方块
    property bool returning: false  // 正在飞回：索引提前淡入，与飞回并行
    property real reveal: 0         // 外围元素整体显现
    property bool landed: false     // 部门卡已由真身接替
    property real tiltX: 0
    property real tiltY: 0

    signal closed()

    visible: busy
    // 部门说明不在画面上显示（不加底部白字），只提供给读屏
    Accessible.name: d ? d.zh : ""
    Accessible.description: conf ? conf.caption + " 共 " + items.length + " 项。" : ""

    // ── 打开 / 关闭 ──────────────────────────────────────────────────────
    function open(i, r, tileItem) {
        if (hub) { r = hub.liveTileRect(i); hub.hiddenIndex = i }
        returning = false
        arrayPanelUsed = false
        index = i
        fetchLive(departments[i].key)
        // 记忆：回到上次停留的条目与功能分页
        target = Math.min(memory[departments[i].key] || 0, Math.max(0, items.length - 1))
        panel.tab = items[target] && items[target]._tab ? items[target]._tab : 0
        landed = false
        opened = true
        // 增强阵列：方块直接消失不再重建，阵列飞入
        if (arrayMode) { landed = true; setupArray() }
        else morph.start(r, tileItem, false)
        revealAnim.stop(); hideAnim.stop()
        revealAnim.start()
        if (!arrayMode) chainDelay.restart()
        forceActiveFocus()
    }
    function close() {
        ++sectionGeneration
        if (!opened) return
        opened = false
        landed = false
        revealAnim.stop()
        hideAnim.start()
        chain.close()
        // 索引在飞回途中就开始淡入；目标方块保持隐藏，落地同一帧再换成真身，避免闪一下
        returning = true
        if (arrayMode) {
            // 增强阵列：阵列飞出，索引同时淡入，方块随索引一起出现
            if (hub) hub.hiddenIndex = -1
            if (arrayItem) arrayItem.blurOut()
            else finishClose()
            return
        }
        const r = hub ? hub.liveTileRect(index) : morph.tileRect
        morph.start(r, null, true)
    }
    // 首尾循环：越过末张（或首张）直接接到另一端，录像带串按同一方向继续滑过去（不提示、不需要二次滚动）
    function select(k, d) {
        const n = items.length
        if (!n) return
        if (k < 0 || k > n - 1) {
            if (n < 2) return
            d = k < 0 ? -1 : 1
            k = ((k % n) + n) % n
        }
        if (k === target) return
        go(k, d || (k > target ? 1 : -1))
    }
    function go(next, d) {
        dir = d
        target = next
        if (showingOnlineHome && next === 1) loadOverview()
        memory[view.d.key] = next
        // 记忆：每个条目保留自己的功能分页
        panel.tab = items[next] && items[next]._tab ? items[next]._tab : 0
        if (!arrayMode) chain.goTo(next, d)
        else syncArray()
    }
    property int dir: 1
    property var memory: ({})               // 部门 key → 上次停留的条目

    Timer { id: chainDelay; interval: 260; onTriggered: chain.open(view.items, view.d.n, view.target) }
    NumberAnimation { id: revealAnim; target: view; property: "reveal"; to: 1; duration: 700; easing.type: Easing.OutCubic }
    NumberAnimation { id: hideAnim; target: view; property: "reveal"; to: 0; duration: 260 }

    Keys.onPressed: event => {
        if (!opened) return
        // Ctrl+F：聚焦本页搜索框
        if (event.key === Qt.Key_F && (event.modifiers & Qt.ControlModifier)) {
            const f = scriptShelf.visible ? scriptShelf.searchField : sectionSearch.visible ? sectionSearch : null
            if (f) { f.forceActiveFocus(); f.selectAll() }
            event.accepted = true
            return
        }
        if (scriptShelf.typing) return
        let k = event.key
        if (modal.shown) { if (k === Qt.Key_Escape) modal.close(); event.accepted = true; return }
        const editor = view.Window.window?.activeFocusItem
        if (editor && typeof editor.cursorPosition === "number" && !editor.readOnly && k !== Qt.Key_Escape) return
        if (arrayMode && !arrayItem && k !== Qt.Key_Escape) return
        // WASD 与方向键等价
        if (k === Qt.Key_W) k = Qt.Key_Up
        else if (k === Qt.Key_S) k = Qt.Key_Down
        else if (k === Qt.Key_A) k = Qt.Key_Left
        else if (k === Qt.Key_D) k = Qt.Key_Right
        if (k === Qt.Key_Escape && workspace.record) { workspace.leave(); event.accepted = true; return }
        if (arrayItem) {
            // 阵列：方向键切列 / 翻档，回车读取，ESC 先退出读取再返回索引
            if (k === Qt.Key_Escape) { if (arrayItem.detailOpen) arrayItem.close(); else close(); event.accepted = true; return }
            if (!workspace.record && (!arrayItem.detailOpen || !arrayItem.isQueue)) {
                if (k === Qt.Key_Down) arrayItem.nav("row", 1)
                else if (k === Qt.Key_Up) arrayItem.nav("row", -1)
                else if (k === Qt.Key_Right || k === Qt.Key_Left) {
                    const delta = k === Qt.Key_Right ? 1 : -1
                    if (arrayItem.singleColumn && arrayDetail)
                        panel.tab = Math.max(0, Math.min(panel.pages.length - 1, panel.tab + delta))
                    else arrayItem.nav("lane", delta)
                }
                else if (k === Qt.Key_Return || k === Qt.Key_Enter) arrayItem.open()
                else if (arrayDetail && k >= Qt.Key_1 && k < Qt.Key_1 + Math.min(9, panel.pages.length)) panel.tab = k - Qt.Key_1
                else return
                event.accepted = true
                return
            }
        }
        if (k === Qt.Key_Escape) { close(); event.accepted = true }
        else if (k === Qt.Key_Down || k === Qt.Key_Right) { select(target + 1); event.accepted = true }
        else if (k === Qt.Key_Up || k === Qt.Key_Left) { select(target - 1); event.accepted = true }
        else if (k >= Qt.Key_1 && k <= Qt.Key_9) {
            const t = k - Qt.Key_1
            if (t < panel.pages.length) panel.tab = t
            event.accepted = true
        }
    }
    WheelHandler {
        enabled: view.opened
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: event => {
            if (scriptShelf.visible && scriptShelf.sortableMode && scriptShelf.overDock(Qt.point(event.x,event.y))) {
                scriptShelf.scrollDock(event.pixelDelta.y ? -event.pixelDelta.y : -event.angleDelta.y / 2)
                event.accepted = true
                return
            }
            // 卡片顶部：滚轮切换分页
            if (panel.visible && panel.wheelTabs(view, event.x, event.y, event.pixelDelta.y, event.angleDelta.y)) { event.accepted = true; return }
            const log = panel.logViewport
            if (log && log.visible && log.contains(log.mapFromItem(view,event.x,event.y))) {
                const maxY=Math.max(0,log.contentHeight-log.height)
                log.contentY=Math.max(0,Math.min(maxY,log.contentY-(event.pixelDelta.y || event.angleDelta.y/2)))
                log.follow=log.contentY>=maxY-1
                event.accepted=true
                return
            }
            if (panel.scrollForm) {
                const dy=event.pixelDelta.y ? -event.pixelDelta.y : -event.angleDelta.y/2
                for (const surface of [panel.formViewport]) {
                    const at = surface.mapFromItem(view,event.x,event.y)
                    if (!surface.contains(at)) continue
                    if (surface === panel.tabViewport && surface.contentWidth>surface.width)
                        surface.contentX=Math.max(0,Math.min(surface.contentWidth-surface.width,surface.contentX+dy))
                    else if (surface === panel.formViewport && surface.contentHeight>surface.height)
                        surface.contentY=Math.max(0,Math.min(surface.contentHeight-surface.height,surface.contentY+dy))
                    else continue
                    event.accepted=true
                    return
                }
            }
            const picker = panel.taskPickerArea
            if (picker && picker.visible) {
                const point = picker.mapFromItem(view, event.x, event.y)
                // 包括同一数据块上方 24 像素的标题和 8 像素的间距。
                if (point.x >= 0 && point.x < picker.width && point.y >= -32 && point.y < picker.height) {
                    picker.turnWheel(event.pixelDelta.y, event.angleDelta.y)
                    event.accepted = true
                    return
                }
            }
            const area = panel.runArea
            if (area && area.visible) {
                const p = area.mapFromItem(view, event.x, event.y)
                if (p.x >= 0 && p.y >= -32 && p.x < area.width && p.y < area.height) {
                    area.scrollBy(event.pixelDelta.y ? -event.pixelDelta.y : -event.angleDelta.y * 0.5)
                    event.accepted = true
                    return
                }
            }
            // 鼠标在档案卡上、且当前页有分页的表格：滚轮翻页，不切换条目
            if (panel.hovered && panel.scrollTable && panel.scrollTable.turnWheel(event.pixelDelta.y, event.angleDelta.y)) { event.accepted = true; return }
            const delta = event.pixelDelta.y || event.angleDelta.y
            if (view.arrayItem) {
                if (delta && !workspace.record && (!view.arrayItem.detailOpen || !view.arrayItem.isQueue)) {
                    view.arrayItem.nav("row", delta < 0 ? 1 : -1)
                    event.accepted = true
                }
                return
            }
            // 在改变选中档案前丢弃溢出的输入，让录像盒与右侧档案始终指向同一项。
            if (delta && chain.queue.length + Number(chain.stepping) < 3)
                view.select(view.target + (delta < 0 ? 1 : -1))
            event.accepted = true
        }
    }
    HoverHandler {
        enabled: view.opened
        onPointChanged: {
            view.tiltY = (point.position.x / view.width - 0.5) * 3
            view.tiltX = -(point.position.y / view.height - 0.5) * 2
        }
    }
    function finishClose() {
        returning = false
        index = -1
        closed()
    }
    // 吞掉点击，避免穿透到背后的索引（增强阵列在本界面之下，需要接收点击）
    MouseArea { anchors.fill: parent; enabled: view.opened && !view.arrayMode }

    // ── 左上：品牌、竖线、数据库标签 ─────────────────────────────────────
    Rectangle {
        visible: !view.arrayMode
        x: 430
        width: 2
        height: 640
        color: Theme.ink
        transformOrigin: Item.Top
        scale: 1
        opacity: view.reveal > 0 ? 1 : 0
        transform: Scale { yScale: Math.min(1, view.reveal * 1.3) }
    }
    Column {
        x: (view.arrayMode ? 59 : 64) - 20 * (1 - view.reveal)
        y: view.arrayMode ? 109 : 122
        opacity: view.reveal
        Text {
            text: "AUTO-MAS"; color: Theme.ink; font.family: Theme.font
            font.pixelSize: view.arrayMode ? 44 : 35; font.letterSpacing: view.arrayMode ? 2.3 : 4
            font.weight: view.arrayMode ? Font.Bold : Font.Normal
        }
        Text {
            visible: view.arrayMode; text: "LOCAL DATABASE"; color: Theme.ink
            font.family: Theme.font; font.pixelSize: 19; font.weight: Font.DemiBold
        }
        Row {
            Text { text: "ANALYSIS "; color: Theme.ink; font.family: Theme.font; font.pixelSize: 35; font.letterSpacing: 4 }
            Text { text: "OS"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 35; font.weight: Font.Bold; font.letterSpacing: 4 }
        }
    }
    Column {
        x: 50
        y: 370
        visible: !view.arrayMode
        spacing: 22
        opacity: view.reveal
        Rectangle { width: 14; height: 3; color: Theme.ink }
        Rectangle {
            width: dbText.implicitWidth + 12
            height: 14
            color: Theme.ink
            Text { id: dbText; anchors.centerIn: parent; text: "AUTO-MAS LOCAL DATABASE"; color: Theme.paper; font.family: Theme.font; font.pixelSize: 8; font.weight: Font.Bold; font.letterSpacing: 1 }
        }
    }

    // ── 上方：标志剪影（半调网点），切换条目时转动 ─────────────────────────
    Item {
        id: hero
        visible: !view.arrayMode
        x: 690
        y: -60 + 30 * (1 - view.reveal)
        width: 380
        height: 540
        opacity: view.reveal
        Canvas {
            id: heroCanvas
            anchors.fill: parent
            renderStrategy: Canvas.Cooperative
            transform: Rotation {
                origin.x: 190
                origin.y: 300
                angle: view.target * 24
                Behavior on angle { NumberAnimation { duration: 900; easing.type: Easing.OutCubic } }
            }
            onPaint: {
                const g = getContext("2d")
                g.reset()
                g.fillStyle = Theme.dark ? "#2c383d" : "#101110"
                g.strokeStyle = g.fillStyle
                // 半尺寸版的 AUTO-MAS 圆环标志
                g.lineWidth = 48
                g.beginPath(); g.arc(190, 300, 116, 0, Math.PI * 2); g.stroke()
                g.lineWidth = 42
                g.beginPath()
                g.moveTo(190, 114); g.lineTo(190, 189)
                g.moveTo(190, 411); g.lineTo(190, 486)
                g.moveTo(4, 300); g.lineTo(79, 300)
                g.moveTo(301, 300); g.lineTo(376, 300)
                g.stroke()
                g.lineWidth = 27
                g.beginPath(); g.moveTo(118, 372); g.lineTo(262, 228); g.stroke()
                g.beginPath(); g.arc(190, 300, 32, 0, Math.PI * 2); g.fill()
                // 网点只落在标志上
                g.globalCompositeOperation = "source-atop"
                g.fillStyle = Theme.dark ? "#43525a" : "#2a2b2a"
                for (let y = 2; y < height; y += 7)
                    for (let x = 2; x < width; x += 7) g.fillRect(x, y, 2, 2)
                g.globalCompositeOperation = "source-over"
                g.fillStyle = Theme.accent
                g.beginPath(); g.arc(190, 300, 11, 0, Math.PI * 2); g.fill()
            }
            Connections { target: Theme; function onDarkChanged() { heroCanvas.requestPaint() } }
        }
        RollDigits {
            id: heroNum
            x: 250
            y: 330
            text: String(view.target + 1).padStart(2, "0")
            dir: view.dir
            live: view.landed
            color: "transparent"
            style: Text.Outline
            styleColor: Qt.rgba(Theme.ink.r, Theme.ink.g, Theme.ink.b, 0.16)
            font.family: Theme.font
            font.pixelSize: 150
            font.weight: Font.Bold
        }
    }

    // ── 左侧黑色部门卡 ───────────────────────────────────────────────────
    Item {
        id: sec
        visible: !view.arrayMode
        x: 248
        y: 300
        width: 410
        height: 329
        z: 3
        Rectangle {
            x: 50
            y: view.reveal > 0.3 ? 0 : 8
            width: tabText.implicitWidth + 48
            height: 39
            color: Theme.dark ? "#2a363b" : "#e3e1dc"
            opacity: view.reveal
            Behavior on y { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
            Text { id: tabText; anchors.centerIn: parent; text: "SECTION"; color: Theme.dark ? Theme.ink : "#333333"; font.family: Theme.font; font.pixelSize: 20; font.letterSpacing: 1.2 }
        }
        Rectangle {
            id: box
            y: 39
            width: 410
            height: 290
            visible: view.landed
            gradient: Gradient {
                orientation: Gradient.Vertical
                GradientStop { position: 0; color: Theme.block }
                GradientStop { position: 0.55; color: Qt.lighter(Theme.block, 2.2) }
                GradientStop { position: 1; color: Theme.block }
            }
            Rectangle { anchors.right: parent.right; anchors.rightMargin: 18; y: 16; width: 14; height: 14; radius: 7; color: "#9a9893" }
            Column {
                id: boxText
                anchors.centerIn: parent
                opacity: view.landed ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 300 } }
                Repeater {
                    model: view.d ? view.d.code.split("\n") : []
                    Text {
                        required property string modelData
                        anchors.horizontalCenter: parent.horizontalCenter
                        height: font.pixelSize * 0.92
                        text: modelData
                        color: Theme.blockText
                        font.family: Theme.font
                        font.pixelSize: view.d && view.d.code.indexOf("\n") >= 0 ? 96 : 120
                        font.weight: Font.Black
                        verticalAlignment: Text.AlignVCenter
                    }
                }
                Item { width: 1; height: 10 }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: view.d ? view.d.sub : ""; color: Theme.blockText; font.family: Theme.font; font.pixelSize: 13; font.letterSpacing: 1.3 }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: view.d ? view.d.zh : ""; color: Theme.blockText; font.family: Theme.font; font.pixelSize: 13; topPadding: 4 }
            }
        }
    }

    // ── 增强挡位：多列档案阵列（实例在 Main.qml 里常驻、启动空闲后预加载，这里只驱动它） ──
    Connections {
        target: view.arrayItem
        // 读取：右侧档案卡切到对应条目；选的是账号 / 队列项行时直接停在对应分页
        function onOpened(lane, row) {
            view.arrayPanelUsed = true
            if (view.d.key !== "queue") { view.applyArraySelection(lane,row); return }
            view.select(lane)
            const it = view.items[lane] || {}
            view.focusQueueRow(it,row)
            const k = SD.pages(it).findIndex(p => p.name === "队列项")
            panel.tab = k >= 0 ? k : 0
            panel.rebuild()
        }
        function onMoved(lane, row) {
            if (view.d.key === "queue") { if (lane !== view.target) view.select(lane); return }
            view.applyArraySelection(lane,row)
        }
        function onFlownOut() { if (!view.opened) view.finishClose() }
    }
    function applyArraySelection(lane,row) {
        if (syncingArray || !arrayItem || !items.length) return
        syncingArray = true
        select(arrayItem.singleColumn ? row : lane)
        if (!arrayItem.singleColumn) panel.tab = row
        syncingArray = false
    }
    Connections {
        target: panel
        function onTabChanged() { if (view.arrayDetail && view.d?.key === "scripts") view.syncArray() }
    }
    // 队列项表格：翻到选中的那一项所在的页并标出它
    function focusQueueRow(it, row) {
        for (const tab of it.tabs || []) for (const b of tab.blocks || []) {
            if (b.t !== "table" || !b.queueRows) continue
            b.page = Math.floor(row / (b.pageRows || 9))
            b.focus = row
        }
    }
    function setupArray() {
        if (!arrayItem || !d) return
        arrayItem.mode = d.key
        arrayItem.columns = Qt.binding(() => view.arrayColumns)
        arrayItem.sectionCode = d.code
        arrayItem.emptyText = Qt.binding(() => d?.key === "scripts" ? (scriptShelf.query ? "没有匹配的脚本" : "暂无脚本") : "暂无档案")
        arrayItem.sortShelf = sortDock
        arrayItem.sortRecord = Qt.binding(() => signSorting && item?.sortId ? item : null)
        arrayItem.reset(target,panel.tab)
        arrayItem.flyIn()
    }
    onArrayItemChanged: {
        if (opened && arrayItem) setupArray()
        else if (opened && !arrayMode && d) chain.open(items,d.n,target)
    }

    // ── 左下：录像带串 + 访问等级 ───────────────────────────────────────────
    CassetteChain {
        id: chain
        shelf: scriptShelf.visible ? scriptShelf : sortDock
        objectName: "chain"
        visible: !view.arrayMode
        x: 0
        y: 440
        width: 900
        height: 640
        z: 2
        onPicked: k => view.select(k)
    }
    Row {
        visible: !view.arrayMode
        x: 0
        y: 956
        z: 4
        spacing: 26
        opacity: view.reveal
        Rectangle { y: 4; width: 46; height: 14; color: Theme.ink }
        Column {
            Text { text: view.d ? view.d.code.replace("\n", " ") + " SECTION" : ""; color: Theme.ink; font.family: Theme.font; font.pixelSize: 15; font.letterSpacing: 0.6 }
            Text { text: "[LIMITED ACCESS]"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 15; font.weight: Font.Bold; font.letterSpacing: 0.6 }
        }
    }

    // ── 读取失败提示（正常时不显示数据来源说明）─────────────────────────────
    Row {
        visible: !view.isHome && view.liveState === "error"
        x: 1150
        y: 26
        z: 5
        spacing: 8
        opacity: view.reveal
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 8; height: 8; radius: 4
            color: view.isLive ? Theme.success : view.liveState === "error" ? Theme.error : view.liveState === "loading" ? Theme.warning : Theme.muted
        }
        Text {
            text: "后端读取失败：" + view.liveMessage
            color: Theme.muted
            font.family: Theme.font
            font.pixelSize: 12
            font.letterSpacing: 1.2
        }
    }

    // ── 右侧：分页点、档案卡、铭牌 ───────────────────────────────────────
    // 条目少时用圆点；条目多时换成「序号 / 总数」+ 刻度条（宽度固定，不会挤到搜索框）
    Item {
        id: pager
        visible: !view.arrayMode
        x: 1150
        y: 58
        z: 5
        height: 22
        width: Math.max(0, back.x - 14 - 198 - 28 - x)
        opacity: view.reveal
        readonly property int n: view.items.length
        readonly property bool dense: n > 7
        Row {
            visible: !pager.dense
            spacing: 4
            Repeater {
                model: pager.dense ? 0 : pager.n
                Item {
                    id: dot
                    required property int index
                    readonly property bool on: view.target === index
                    width: on ? 42 : 22
                    height: 22
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Button
                    Accessible.name: String(index + 1).padStart(2, "0") + " " + (view.items[index] ? view.items[index].name : "")
                    Keys.onSpacePressed: view.select(index)
                    Rectangle { visible: dot.on; y: 10; width: 12; height: 2; color: Theme.accent }
                    Rectangle { visible: dot.on; x: 30; y: 10; width: 12; height: 2; color: Theme.accent }
                    Rectangle {
                        anchors.centerIn: parent
                        width: dot.on ? 12 : 6
                        height: width
                        radius: width / 2
                        color: dot.on ? "transparent" : Theme.accent
                        border.width: dot.on ? 2 : 0
                        border.color: Theme.accent
                        scale: dotMouse.containsMouse && !dot.on ? 1.6 : 1
                        Behavior on scale { NumberAnimation { duration: 150 } }
                    }
                    Rectangle { anchors.fill: parent; color: "transparent"; border.width: 2; border.color: Theme.accent; visible: dot.activeFocus }
                    MouseArea { id: dotMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: view.select(dot.index) }
                }
            }
        }
        Text {
            id: pagerCount
            visible: pager.dense
            anchors.verticalCenter: parent.verticalCenter
            text: String(view.target + 1).padStart(2, "0") + " / " + String(pager.n).padStart(2, "0")
            color: Theme.accent
            font.family: Theme.font
            font.pixelSize: 13
            font.weight: Font.Bold
            font.letterSpacing: 1
        }
        // 刻度条：刻度均匀铺满固定宽度（条目再多也只画到每 5px 一根），当前条目是一根高的橙色刻度；
        // 点击 / 拖动按位置换条目，滚轮逐个切换，悬停显示条目名
        Item {
            id: strip
            visible: pager.dense
            x: pagerCount.implicitWidth + 16
            width: Math.max(40, pager.width - x)
            height: 22
            readonly property int ticks: Math.max(2, Math.min(pager.n, Math.floor(width / 5)))
            function at(px) { return Math.max(0, Math.min(pager.n - 1, Math.round(px / width * (pager.n - 1)))) }
            function px(i) { return pager.n > 1 ? i / (pager.n - 1) * (width - 2) : 0 }
            Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 1; color: Theme.hair; opacity: 0.6 }
            Repeater {
                model: strip.ticks
                Rectangle {
                    required property int index
                    x: index / (strip.ticks - 1) * (strip.width - 2)
                    width: 2; height: 8
                    anchors.verticalCenter: parent.verticalCenter
                    color: Theme.accent
                    opacity: 0.55
                }
            }
            Rectangle {
                visible: stripMouse.containsMouse
                x: strip.px(strip.at(stripMouse.mouseX)) - 1
                width: 4; height: 16
                anchors.verticalCenter: parent.verticalCenter
                color: Theme.ink; opacity: 0.35
            }
            Rectangle {
                x: strip.px(view.target) - 2
                width: 6; height: 22
                color: Theme.accent
                Behavior on x { enabled: Theme.richMotion; NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
            }
            MouseArea {
                id: stripMouse
                anchors.fill: parent; anchors.topMargin: -8; anchors.bottomMargin: -8
                hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onPressed: mouse => view.select(strip.at(mouse.x))
                onPositionChanged: mouse => { if (pressed) view.select(strip.at(mouse.x)) }
                onWheel: wheel => view.select(view.target + (wheel.angleDelta.y > 0 || wheel.pixelDelta.y > 0 ? -1 : 1))
            }
            Rectangle {
                visible: stripMouse.containsMouse && !stripMouse.pressed
                readonly property int hit: strip.at(stripMouse.mouseX)
                x: Math.max(0, Math.min(strip.width - width, strip.px(hit) - width / 2))
                y: 30
                width: tipText.implicitWidth + 20; height: 26
                color: Theme.ink
                Text { id: tipText; anchors.centerIn: parent; text: String(parent.hit + 1).padStart(2, "0") + "  " + (view.items[parent.hit] ? view.items[parent.hit].name : ""); color: Theme.paper; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Bold; font.letterSpacing: 1 }
            }
        }
    }

    Item {
        id: glass
        visible: !view.arrayMode || view.arrayDetail
        x: 1150
        y: 92
        z: 5
        width: 730
        height: 800
        opacity: Math.max(0, Math.min(1, (view.reveal - 0.3) / 0.5))
        transform: [
            Rotation { origin.x: 730; origin.y: 400; axis { x: 0; y: 1; z: 0 } angle: 2 + 16 * (1 - view.reveal) + view.tiltY },
            Rotation { origin.x: 365; origin.y: 400; axis { x: 1; y: 0; z: 0 } angle: view.tiltX },
            Translate { x: 40 * (1 - view.reveal) }
        ]
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Theme.dark ? Qt.rgba(0.11, 0.15, 0.17, 0.86) : Qt.rgba(1, 1, 1, 0.78) }
                GradientStop { position: 0.6; color: Theme.dark ? Qt.rgba(0.11, 0.15, 0.17, 0.72) : Qt.rgba(0.965, 0.957, 0.945, 0.62) }
                GradientStop { position: 1; color: Theme.dark ? Qt.rgba(0.11, 0.15, 0.17, 0.82) : Qt.rgba(1, 1, 1, 0.72) }
            }
            border.width: 1
            border.color: Qt.rgba(Theme.ink.r, Theme.ink.g, Theme.ink.b, 0.14)
        }
        ArchivePanel {
            id: panel
            visible: !!view.item
            host: view
            sortDock: sortDock
            homeRuns: view.isLive ? liveHomeRuns : previewRuns
            objectName: "archivePanel"
            x: 30
            y: 20
            width: parent.width - 60
            height: parent.height - 40
            dept: view.d
            item: workspace.record || (!view.arrayMode || view.arrayDetail || view.arrayPanelUsed ? view.item : null)
            itemIndex: view.target
            // 后端还在读取本部门数据时，档案卡停在合拢状态；读取完成（或失败）立即揭开
            saving: view.saving
            runLocked: view.runLocked
            env: view.env
            loading: view.liveState === "loading"
            onToast: text => toast.show(text)
            onConfirmDelete: (name, api) => modal.open(name, api)
            emulatorManager: view.emulatorPage && !workspace.record ? emulatorConfigs : null
            onLiveAction: name => {
                if (workspace.record) view.runOp(workspace.record.ops[name])
                else view.liveAction(name)
            }
            onLiveOp: op => view.runOp(op)
            onRequestEnhanced: {
                if (!view.enhanced) return
                modal.ask("下载 3D 增强组件",
                    "增强挡位用 Qt Quick 3D 绘制实体档案卡带，需要另外下载 " + view.enhanced.packageText + "（" + view.enhanced.sizeText + "，来自 PyPI）。安装完成后自动切换到增强挡位；以后切回减少或标准挡位时，会在退出程序、下次启动空闲后删除这些文件。",
                    "OPTIONAL COMPONENT", "下载并安装", false, () => view.enhanced.install())
            }
            onMotionChosen: motion => { if (view.enhanced) view.enhanced.choose(motion) }
        }
    }

    Item {
        id: plate
        visible: !view.arrayMode
        x: 1150
        y: 910
        z: 5
        width: 730
        height: 100
        opacity: view.reveal
        transform: Translate { x: 30 * (1 - view.reveal) }
        Rectangle {
            width: 116
            height: 64
            color: Theme.block
            Column {
                anchors.centerIn: parent
                spacing: 3
                Emblem { anchors.horizontalCenter: parent.horizontalCenter; width: 34; height: 34; ink: Theme.blockText; core: Theme.accent }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "AUTO-MAS"; color: Theme.blockText; font.family: Theme.font; font.pixelSize: 6; font.weight: Font.Bold; font.letterSpacing: 1.8 }
            }
        }
        // 铭牌文字滚动更新（借鉴 RhineLabUI）；刚进入时直接显示
        Column {
            x: 132
            y: -4
            width: parent.width - 132
            RollText { text: view.d ? view.d.code.replace("\n", " ") + " / " + view.d.zh : ""; dir: view.dir; live: view.landed; color: Theme.ink; font.family: Theme.font; font.pixelSize: 14; font.letterSpacing: 0.6 }
            RollText { text: view.item ? view.item.name : ""; dir: view.dir; live: view.landed; color: Theme.ink; font.family: Theme.font; font.pixelSize: 34; font.weight: Font.Bold; font.letterSpacing: 0.7 }
        }
        Rectangle {
            x: 116
            y: 62
            width: (parent.width - 116) * Math.min(1, view.reveal * 1.2)
            height: 2
            color: Theme.ink
        }
        Row {
            x: 132
            y: 72
            RollDigits { text: view.d ? view.d.n + "-" + String(view.target + 1).padStart(2, "0") : ""; dir: view.dir; live: view.landed; color: Theme.ink; font.family: Theme.font; font.pixelSize: 13; font.weight: Font.Bold; font.letterSpacing: 0.8 }
            Text { text: "  ·  "; color: Theme.ink; font.family: Theme.font; font.pixelSize: 13 }
            RollText { text: view.item ? view.item.en : ""; dir: view.dir; live: view.landed; color: Theme.ink; font.family: Theme.font; font.pixelSize: 13; font.letterSpacing: 0.8 }
        }
    }

    // ── 底部：字幕、POWERED BY、提示 ─────────────────────────────────────
    Row {
        anchors.right: parent.right
        anchors.rightMargin: 56
        y: 1044
        spacing: 40
        opacity: view.reveal
        Row {
            Text { text: "POWERED BY "; color: Theme.ink; font.family: Theme.font; font.pixelSize: 14; font.letterSpacing: 0.6 }
            Text { text: "AUTO-MAS"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 14; font.weight: Font.Bold; font.letterSpacing: 0.6 }
        }
    }

    // 通用暂存区：签到账号组录像带、队列定时 / 队列项行、托管账号页签的拖动排序
    SortDock {
        id: sortDock
        objectName: "sortDock"
        anchors.fill: parent
        z: 6
        visible: view.opened && (!view.arrayMode || !!view.arrayItem?.singleColumn)
    }
    // 签到账号组（录像带）的排序组：放到当前选中的账号组之前 / 之后
    property var signSortGroup: ({
        ids: () => (live.gamesign || []).filter(x => x.sortId).map(x => x.sortId),
        label: id => ((live.gamesign || []).find(x => x.sortId === id) || {}).name || "",
        target: pt => {
            const it = view.item
            if (!it || !it.sortId) return null
            const side = arrayMode && arrayItem ? arrayItem.sortSide(sortDock, pt) : chain.insertSide(sortDock, pt)
            return side ? { id: it.sortId, side: side } : null
        },
        commit: (ids, done) => call("/api/tools/sign/account/reorder", { order: ids }, r => {
            done(r.code === 200)
            if (r.code === 200) { toast.show("已调整账号组顺序"); fetchLive("gamesign") }
            else toast.show("排序保存失败：" + (r.message || ""))
        })
    })
    readonly property bool signSorting: opened && !!d && d.key === "gamesign"
    onSignSortingChanged: signSorting ? sortDock.register("signGroups", signSortGroup) : sortDock.unregister("signGroups", signSortGroup)
    onOpenedChanged: if (!opened) { sortDock.reset(); workspace.leave() }
    // ── 搜索：匹配条目名、英文名、编号、账号与功能分页名，跳到对应的卡片（与分页）；回车下一个，Shift+回车上一个 ──
    property var searchHits: []
    property int searchHit: 0
    function searchItems(q) {
        q = q.trim().toLowerCase()
        if (!q || !d) return []
        const hits = []
        const has = v => String(v || "").toLowerCase().includes(q)
        items.forEach((it, i) => {
            if (!it) return
            if ([it.name, it.en, d.n + "-" + String(i + 1).padStart(2, "0")].concat(it.accounts || []).some(has)) { hits.push({ i: i, tab: -1 }); return }
            // 分页名，其次分页里的分区标题、字段名与表格首列
            const inPage = p => has(p.name) || (p.blocks || []).some(b => has(b.title)
                || (Array.isArray(b.rows) ? b.rows : []).some(r => Array.isArray(r) && typeof r[0] === "string" && has(r[0])))
            SD.pages(it).forEach((p, t) => { if (inPage(p)) hits.push({ i: i, tab: t }) })
        })
        return hits
    }
    function showHit(k) {
        if (!searchHits.length) return
        searchHit = (k + searchHits.length) % searchHits.length
        const h = searchHits[searchHit]
        if (h.i !== target) select(h.i)
        if (h.tab >= 0) Qt.callLater(() => { panel.tab = h.tab; if (arrayMode) syncArray() })
    }
    SearchField {
        id: sectionSearch
        objectName: "sectionSearch"
        z: 7
        visible: view.opened && !!view.d && view.d.key !== "scripts" && view.items.length > 1
        x: back.x - 14 - width
        y: back.y; width: 198; height: back.height
        opacity: view.reveal
        Accessible.name: "搜索本页条目"
        badge: view.searchHits.length ? (view.searchHit + 1) + " / " + view.searchHits.length : "无匹配"
        miss: !view.searchHits.length
        onTextEdited: { view.searchHits = view.searchItems(text); view.showHit(0) }
        Keys.onReturnPressed: event => view.showHit(view.searchHit + (event.modifiers & Qt.ShiftModifier ? -1 : 1))
        Keys.onEnterPressed: event => view.showHit(view.searchHit + (event.modifiers & Qt.ShiftModifier ? -1 : 1))
        onLeave: view.forceActiveFocus()
        onVisibleChanged: if (!visible) { clear(); view.searchHits = [] }
    }
    ScriptShelf {
        id: scriptShelf
        objectName: "scriptShelf"
        view: view; chain: chain; backButton: back
        anchors.fill: parent; z: 7
        visible: view.opened && !!view.d && view.d.key === "scripts"
        onMessage: text => toast.show(text)
    }
    Rectangle {
        id: back
        anchors.right: parent.right
        anchors.rightMargin: 56
        y: 40
        z: 7
        width: backText.implicitWidth + 36
        height: 38
        opacity: view.reveal
        color: backMouse.containsMouse || back.activeFocus ? Theme.ink : "transparent"
        border.width: 1.5
        border.color: Theme.ink
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: qsTr("返回一级界面")
        Keys.onReturnPressed: view.close()
        Keys.onSpacePressed: view.close()
        Text {
            id: backText
            anchors.centerIn: parent
            text: "← RETURN TO INDEX"
            color: backMouse.containsMouse || back.activeFocus ? Theme.paper : Theme.ink
            font.family: Theme.font
            font.pixelSize: 13
            font.weight: Font.Bold
            font.letterSpacing: 3.6
        }
        MouseArea { id: backMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: view.close() }
    }

    // ── 确认弹窗：300ms 入场（位移 12px）、200ms 退出（位移 8px）；Esc 只关弹窗 ──
    Item {
        id: modal
        objectName: "confirmModal"
        anchors.fill: parent
        z: 60
        property bool shown: false
        property real p: 0
        property string api: ""
        visible: p > 0
        function open(name, a) {
            title = "确认删除"; okText = "删除"; danger = true; onOk = null
            api = a
            mText.text = "将删除「" + name + "」，删除后无法撤销。"
            shown = true
            outAnim.stop()
            inAnim.restart()
            cancelBtn.forceActiveFocus()
        }
        property string title: "确认删除"
        property string okText: "删除"
        property bool danger: true
        property var onOk: null
        function ask(t, body, meta, ok, isDanger, fn) {
            title = t; okText = ok; danger = isDanger; onOk = fn
            api = meta
            mText.text = body
            shown = true
            outAnim.stop()
            inAnim.restart()
            cancelBtn.forceActiveFocus()
        }
        function close(done) {
            if (!shown) return
            shown = false
            inAnim.stop()
            outAnim.done = done || null
            outAnim.restart()
            view.forceActiveFocus()
        }
        NumberAnimation { id: inAnim; target: modal; property: "p"; to: 1; duration: Theme.richMotion ? 300 : 0; easing.type: Easing.OutCubic }
        NumberAnimation {
            id: outAnim
            property var done: null
            target: modal; property: "p"; to: 0; duration: Theme.richMotion ? 200 : 0; easing.type: Easing.InCubic
            onFinished: if (done) { const f = done; done = null; f() }
        }
        Rectangle {
            anchors.fill: parent
            color: Theme.dark ? Qt.rgba(0.04, 0.07, 0.08, 0.55) : Qt.rgba(0.9, 0.89, 0.87, 0.6)
            opacity: modal.p
            MouseArea { anchors.fill: parent; enabled: modal.shown; onClicked: modal.close() }
        }
        Rectangle {
            id: mBox
            width: 560
            height: mCol.implicitHeight + 98
            anchors.centerIn: parent
            anchors.verticalCenterOffset: modal.shown ? 12 * (1 - modal.p) : 8 * (1 - modal.p)
            opacity: modal.p
            // 与 RhineDialog 同一外框：顶部色条、右上斜纹、四角折角、底部编号栏
            color: Theme.paper
            border.width: 1.5
            border.color: Theme.ink
            MouseArea { anchors.fill: parent }
            Rectangle { width: parent.width; height: 4; color: modal.danger ? Theme.error : Theme.accent }
            Item {
                anchors.right: parent.right; anchors.rightMargin: 28; y: 24
                width: 96; height: 12; clip: true
                Repeater {
                    model: 14
                    Rectangle { required property int index; x: index * 9 - 10; y: -6; width: 3; height: 26; rotation: 35; color: Theme.ink; opacity: 0.85 }
                }
            }
            Repeater {
                model: 4
                Item {
                    required property int index
                    readonly property bool isRight: index % 2 === 1
                    readonly property bool isBottom: index > 1
                    x: isRight ? mBox.width - 22 : 8; y: isBottom ? mBox.height - 22 : 12
                    width: 14; height: 14
                    Rectangle { x: parent.isRight ? 12 : 0; width: 2; height: 14; color: Theme.ink }
                    Rectangle { y: parent.isBottom ? 12 : 0; width: 14; height: 2; color: Theme.ink }
                }
            }
            Rectangle { x: 28; width: parent.width - 56; y: parent.height - 34; height: 1; color: Theme.hair }
            Text { x: 28; y: parent.height - 26; text: "X-0" + (view.d ? view.d.n : "00") + "  ·  CONFIRM"; color: Theme.accent; font.family: Theme.font; font.pixelSize: 10; font.weight: Font.Bold; font.letterSpacing: 2.4 }
            Text { anchors.right: parent.right; anchors.rightMargin: 28; y: parent.height - 26; text: "AUTO-MAS  //  ANALYSIS OS"; color: Theme.muted; font.family: Theme.font; font.pixelSize: 10; font.weight: Font.Bold; font.letterSpacing: 2.4 }
            Column {
                id: mCol
                x: 36; y: 26
                width: parent.width - 72
                spacing: 0
                Text { text: (view.d ? view.d.code.replace("\n", " ") + "  /  " : "") + "CONFIRM"; color: modal.danger ? Theme.error : Theme.accent; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Bold; font.letterSpacing: 2.8 }
                Item { width: 1; height: 6 }
                Text { text: modal.title; color: Theme.ink; font.family: Theme.font; font.pixelSize: 28; font.weight: Font.Bold; font.letterSpacing: 1.4 }
                Item { width: 1; height: 12 }
                Rectangle { width: 36; height: 2; color: Theme.ink }
                Item { width: 1; height: 20 }
                Text { id: mText; width: parent.width; wrapMode: Text.Wrap; color: Theme.ink; font.family: Theme.font; font.pixelSize: 15; lineHeight: 1.4 }
                Item { width: 1; height: 28 }
                Row {
                    anchors.right: parent.right
                    spacing: 12
                    Repeater {
                        model: ["取消", modal.okText]
                        Rectangle {
                            id: mb
                            required property string modelData
                            required property int index
                            readonly property bool danger: index === 1
                            readonly property bool hotRed: danger && modal.danger
                            width: mbText.implicitWidth + 44
                            height: 40
                            color: danger ? (mbMouse.containsMouse || activeFocus ? (hotRed ? Theme.error : Theme.accent) : Theme.ink) : "transparent"
                            border.width: 1.5
                            border.color: danger ? color : mbMouse.containsMouse || activeFocus ? Theme.accent : Theme.ink
                            activeFocusOnTab: true
                            Accessible.role: Accessible.Button
                            Accessible.name: modelData
                            Component.onCompleted: if (index === 0) modal.cancelRef = mb
                            function trigger() {
                                if (danger && modal.onOk) { const f = modal.onOk; modal.close(() => f()) }
                                else if (danger) modal.close(() => toast.show("已删除"))
                                else modal.close()
                            }
                            Keys.onReturnPressed: trigger()
                            Keys.onSpacePressed: trigger()
                            Text { id: mbText; anchors.centerIn: parent; text: mb.modelData; color: mb.danger ? (mbMouse.containsMouse || mb.activeFocus ? "#ffffff" : Theme.paper) : mbMouse.containsMouse || mb.activeFocus ? Theme.accent : Theme.ink; font.family: Theme.font; font.pixelSize: 14; font.weight: Font.Bold; font.letterSpacing: 2 }
                            MouseArea { id: mbMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: mb.trigger() }
                        }
                    }
                }
            }
        }
        property Item cancelRef: null
        readonly property Item cancelBtn: cancelRef
    }

    // 组件下载 / 删除进度
    Connections {
        target: view.enhanced
        function onChanged() {
            const e = view.enhanced
            if (e.state === "installing") toast.show("3D 增强组件：" + (e.detail || "准备下载") + "…", true)
            else if (e.state === "removing") toast.show("正在删除 3D 增强组件…", true)
            else if (e.state === "installed" && e.detail === "kept") toast.show("已取消删除 3D 增强组件")
            else if (e.state === "installed") { Theme.requestMotion("enhanced"); e.choose("enhanced"); toast.show("3D 增强组件已安装，已切换到增强挡位") }
            else if (e.state === "missing") toast.show("已删除 3D 增强组件")
            else if (e.state === "pending-remove") toast.show("3D 增强组件将在退出程序、下次启动空闲后删除")
            else if (e.state === "error") toast.show("3D 增强组件失败：" + e.detail)
        }
    }

    // ── 提示条 ─────────────────────────────────────────────────────────
    Rectangle {
        id: toast
        anchors.right: parent.right
        anchors.rightMargin: 72
        y: 980 + 10 * (1 - shownP)
        z: 40
        width: toastRow.implicitWidth + 40
        height: 44
        color: Theme.ink
        property real shownP: 0
        opacity: shownP
        function show(t, sticky) {
            toastText.text = t
            toastIn.restart()
            if (sticky) toastTimer.stop()
            else toastTimer.restart()
        }
        NumberAnimation { id: toastIn; target: toast; property: "shownP"; to: 1; duration: 220; easing.type: Easing.OutCubic }
        NumberAnimation { id: toastOut; target: toast; property: "shownP"; to: 0; duration: 200 }
        Timer { id: toastTimer; interval: 1800; onTriggered: toastOut.restart() }
        Row {
            id: toastRow
            anchors.centerIn: parent
            spacing: 12
            Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 10; height: 10; color: Theme.accent }
            Text { id: toastText; objectName: "toastText"; color: Theme.paper; font.family: Theme.font; font.pixelSize: 14; font.letterSpacing: 1.6 }
        }
    }

    // ── 过渡体：方块 ↔ 部门卡 ────────────────────────────────────────────
    Item {
        id: morph
        z: 50
        visible: false

        property string kind: "arc"
        property real sign: 1
        property bool reverse: false
        property rect tileRect: Qt.rect(0, 0, 0, 0)
        property color fromColor: "transparent"
        property real p: 0
        readonly property rect cardRect: Qt.rect(sec.x, sec.y + box.y, box.width, box.height)

        readonly property var durations: ({ arc: 720, stretch: 640, fold: 820, echo: 760 })
        readonly property var kinds: ["arc", "stretch", "fold", "echo"]

        function start(r, tileItem, rev) {
            tileRect = r
            reverse = rev
            if (!rev) {
                kind = kinds[Math.floor(Math.random() * kinds.length)]
                sign = Math.random() < 0.5 ? -1 : 1
                const st = view.d.style
                fromColor = st === "block" ? Theme.block : st === "card" ? Theme.paper : Qt.rgba(Theme.block.r, Theme.block.g, Theme.block.b, 0)
                snap.sourceItem = tileItem
                snap.scheduleUpdate()
            }
            anim.stop()
            anim.from = rev ? 1 : 0
            anim.to = rev ? 0 : 1
            anim.duration = durations[kind]
            p = anim.from
            visible = true
            anim.start()
        }

        // 三次贝塞尔缓动（与 CSS cubic-bezier 相同）
        function bezier(x1, y1, x2, y2, x) {
            if (x <= 0) return 0
            if (x >= 1) return 1
            const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx
            const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by
            let t = x
            for (let i = 0; i < 8; i++) {
                const X = ((ax * t + bx) * t + cx) * t - x
                const dX = (3 * ax * t + 2 * bx) * t + cx
                if (Math.abs(dX) < 1e-6) break
                t = Math.max(0, Math.min(1, t - X / dX))
            }
            return ((ay * t + by) * t + cy) * t
        }
        function eMove(x) { return bezier(0.7, 0, 0.2, 1, x) }
        function eSize(x) { return bezier(0.5, 0, 0.1, 1, x) }
        function eSoft(x) { return bezier(0.2, 0.8, 0.2, 1, x) }
        function clamp01(v) { return Math.max(0, Math.min(1, v)) }
        function mix(a, b, t) { return a + (b - a) * t }

        // 给定 p 的矩形：中心 cx, cy 与宽高 w, h
        function at(q) {
            q = clamp01(q)
            const a = { cx: tileRect.x + tileRect.width / 2, cy: tileRect.y + tileRect.height / 2, w: tileRect.width, h: tileRect.height }
            const b = { cx: cardRect.x + cardRect.width / 2, cy: cardRect.y + cardRect.height / 2, w: cardRect.width, h: cardRect.height }
            if (kind === "fold") {
                const p1 = eSoft(clamp01(q / 0.34)), p2 = eMove(clamp01((q - 0.14) / 0.6)), p3 = eSoft(clamp01((q - 0.6) / 0.4))
                const bar = 6
                return { cx: mix(a.cx, b.cx, p2), cy: mix(a.cy, b.cy - b.h / 2 + bar / 2, p2) + (b.h / 2 - bar / 2) * p3,
                         w: mix(a.w, b.w, p2), h: p3 > 0 ? mix(bar, b.h, p3) : mix(a.h, bar, p1) }
            }
            const m = eMove(q), s = eSize(q)
            if (kind === "stretch") {
                const k = Math.sin(Math.PI * m) * 0.45
                const dx = b.cx - a.cx, dy = b.cy - a.cy, L = Math.hypot(dx, dy) || 1, hx = Math.abs(dx) / L, hy = Math.abs(dy) / L
                const w = mix(a.w, b.w, s), h = mix(a.h, b.h, s)
                return { cx: mix(a.cx, b.cx, m), cy: mix(a.cy, b.cy, m), w: w * (1 + k * hx - k * 0.5 * hy), h: h * (1 + k * hy - k * 0.5 * hx) }
            }
            // arc / echo：沿二次贝塞尔曲线移动
            const mx = (a.cx + b.cx) / 2, my = (a.cy + b.cy) / 2, dx = b.cx - a.cx, dy = b.cy - a.cy
            const L = Math.hypot(dx, dy) || 1, off = Math.min(220, L * 0.32) * sign
            const kx = mx - dy / L * off, ky = my + dx / L * off, u = 1 - m
            return { cx: u * u * a.cx + 2 * u * m * kx + m * m * b.cx, cy: u * u * a.cy + 2 * u * m * ky + m * m * b.cy, w: mix(a.w, b.w, s), h: mix(a.h, b.h, s) }
        }
        function colorAt(q, alpha) {
            const c = eSoft(clamp01(q / 0.7))
            const f = fromColor, t = Theme.block
            return Qt.rgba(mix(f.r, t.r, c), mix(f.g, t.g, c), mix(f.b, t.b, c), mix(f.a, 1, c) * alpha)
        }

        NumberAnimation {
            id: anim
            target: morph
            property: "p"
            easing.type: Easing.Linear
            onFinished: {
                if (morph.reverse) {
                    if (view.hub) view.hub.hiddenIndex = -1
                    morph.visible = false
                    view.returning = false
                    view.index = -1
                    view.closed()
                } else {
                    view.landed = true
                    morph.visible = false
                }
            }
        }

        // 残影：落后主体 0.09 / 0.18 的两道淡影
        Repeater {
            model: morph.kind === "echo" ? [0.09, 0.18] : []
            Rectangle {
                required property real modelData
                readonly property real lin: morph.reverse ? 1 - morph.p : morph.p
                readonly property real gp: morph.reverse ? 1 - (lin - modelData) : lin - modelData
                readonly property var r: morph.at(gp)
                visible: lin > modelData && lin < 1
                x: r.cx - r.w / 2
                y: r.cy - r.h / 2
                width: r.w
                height: r.h
                color: morph.colorAt(gp, modelData < 0.1 ? 0.35 : 0.16)
            }
        }
        Rectangle {
            id: body
            readonly property var r: morph.at(morph.p)
            x: r.cx - r.w / 2
            y: r.cy - r.h / 2
            width: r.w
            height: r.h
            color: morph.colorAt(morph.p, 1)
            clip: true
            // 方块原有内容：等比缩放跟随并在前段淡出，文字不做非等比拉伸
            ShaderEffectSource {
                id: snap
                live: false
                hideSource: false
                width: morph.tileRect.width
                height: morph.tileRect.height
                anchors.centerIn: parent
                scale: Math.min(body.width / Math.max(1, morph.tileRect.width), body.height / Math.max(1, morph.tileRect.height))
                opacity: 1 - morph.clamp01(morph.p / 0.4)
            }
        }
    }
}
