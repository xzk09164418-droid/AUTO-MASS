.pragma library
.import "SectionData.js" as SD
.import "Live.js" as Live

function button(label, perform) {
    return Object.assign(SD.mini([label]), { ops: [{ perform: perform }] })
}
function multiline(title, value, readOnly) {
    return { t: "multiline", title: title, v: value || "", readOnly: !!readOnly }
}
function open(w, kind, op) {
    if (kind === "选择实例") {
        const id = Live.valueOf(op.emulator)
        w.request("/api/info/combox/emulator/devices", { emulatorId: id }, r => {
            const rows = r.data
                .filter(o => o.value !== "-")
                .map(o => [
                    o.label,
                    button("选择", () => {
                        if (w.affected()) {
                            w.message("运行中，配置已锁定")
                            return
                        }
                        op.index.v = o.value
                        op.index.dirty = true
                        w.leave()
                        w.changed()
                    })
                ])
            w.page(
                kind,
                [
                    rows.length
                        ? SD.table("可用实例", ["实例", ""], rows, [3, 1])
                        : SD.note("没有可枚举的实例，可返回手动填写。", true)
                ],
                {}
            )
        })
    } else if (kind === "预处理规则" || kind === "推送规则") editRules(w, kind)
    else if (kind === "获取凭据" || kind === "绑定 QQ") credentials(w, kind, op.accountId)
    else if (kind === "Webhook" || kind === "全局 Webhook") webhooks(w, kind, op.userId)
    else if (kind === "账号统计") accountStats(w, op.users)
    else if (kind === "本机日志") localLogs(w)
    else externalControl(w, kind)
}

function editRules(w, kind) {
    const hook = kind === "预处理规则"
    const key = hook ? "Script.LogHookRules" : "Script.PushLogPatterns"
    let spec
    Live.eachSpec(w.source, s => {
        if (s.key === key) spec = s
    })
    let list
    try {
        list = JSON.parse(spec.v || "[]")
        if (!Array.isArray(list)) throw Error()
    } catch (e) {
        w.page(kind, [SD.note("规则原文无法解析，请返回修正。", true)], {})
        return
    }
    const types = hook ? ["drop", "replace"] : ["regex", "split", "multiline"]
    const labels = hook ? ["丢弃", "改写"] : ["正则", "分隔符", "多行"]
    function overview() {
        const rows = list.map((r, i) => [
            r.name || "规则 " + (i + 1),
            labels[types.indexOf(r.type)] || r.type,
            button("编辑", () => edit(i, r.type)),
            button("上移", () => {
                if (i) {
                    list.splice(i - 1, 0, list.splice(i, 1)[0])
                    overview()
                }
            })
        ])
        w.page(
            kind,
            [
                rows.length
                    ? SD.table("规则顺序", ["名称", "类型", "", ""], rows, [2, 1, 1, 1])
                    : SD.note("暂无规则", true)
            ],
            {
                新增: () => chooseType(),
                应用: () => {
                    if (w.affected()) {
                        w.message("运行中，配置已锁定")
                        return
                    }
                    spec.v = JSON.stringify(list)
                    spec.dirty = true
                    w.leave()
                    w.changed()
                    w.message("已应用，请保存脚本")
                }
            }
        )
    }
    function chooseType() {
        w.page(
            "新增规则",
            [
                SD.table(
                    "类型",
                    ["类型", ""],
                    types.map((t, i) => [labels[i], button("新建", () => edit(list.length, t))]),
                    [3, 1]
                )
            ],
            {},
            overview
        )
    }
    function edit(i, type) {
        const original = list[i] || {}
        const keys =
            type === "multiline"
                ? ["start", "end", "extract", "maxLines"]
                : type === "split"
                  ? ["match", "head", "headInclude", "tail", "tailInclude"]
                  : type === "replace"
                    ? ["match", "replace"]
                    : type === "drop"
                      ? ["match"]
                      : ["match", "extract"]
        const names = {
            name: "名称",
            enabled: "启用",
            match: "匹配表达式",
            replace: "替换为",
            extract: "提取表达式",
            start: "开始标记",
            end: "结束标记",
            maxLines: "最多行数",
            head: "头分隔符",
            tail: "尾分隔符",
            headInclude: "包含头",
            tailInclude: "包含尾"
        }
        const fields = {}
        const rows = ["name", "enabled"].concat(keys).map(k => {
            const field =
                k === "enabled"
                    ? SD.tog(original.enabled !== false)
                    : k.endsWith("Include")
                      ? SD.tog(original[k])
                      : k === "maxLines"
                        ? SD.num(original[k] || 50)
                        : SD.inp(original[k] || "")
            fields[k] = field
            return [names[k], field]
        })
        const logType = SD.sel(["普通", "失败"], original.logType === "失败" ? 1 : 0)
        if (!hook) rows.push(["日志类型", logType])
        const sample = multiline("测试日志", "", false)
        function rule() {
            const result = Object.assign({}, original, { type: type })
            for (const k of Object.keys(fields)) result[k] = fields[k].v
            if (!hook) result.logType = logType.opts[logType.v]
            return result
        }
        const blocks = [SD.kv(labels[types.indexOf(type)], rows), sample]
        function render(output) {
            const actions = {
                切换类型: () =>
                    w.page(
                        "选择规则类型",
                        [
                            SD.table(
                                "类型",
                                ["类型", ""],
                                types.map((t, n) => [labels[n], button("选用", () => edit(i, t))]),
                                [3, 1]
                            )
                        ],
                        {},
                        () => edit(i, type)
                    ),
                保留修改: () => {
                    list[i] = rule()
                    overview()
                },
                调试: () => {
                    if (hook) render(w.sampleHook(rule(), sample.v))
                    else
                        w.request("/api/setting/debug_pattern", { pattern: rule(), logText: sample.v }, r =>
                            render(
                                r.configError ||
                                    r.results
                                        .map(
                                            x =>
                                                x.idx +
                                                1 +
                                                "　" +
                                                (x.hit ? "命中" : "未命中") +
                                                "　" +
                                                (x.error || x.extracted || x.line || "")
                                        )
                                        .join("\n") ||
                                    "无匹配"
                            )
                        )
                }
            }
            if (i < list.length)
                actions["删除"] = () =>
                    w.ask("删除规则", original.name || "当前规则", () => {
                        list.splice(i, 1)
                        overview()
                    })
            w.page(
                kind,
                output ? blocks.concat(multiline("调试结果", output, true)) : blocks,
                actions,
                overview
            )
        }
        render("")
    }
    overview()
}

function credentials(w, kind, accountId) {
    const qq = kind === "绑定 QQ"
    function start(provider) {
        const base = qq ? "/api/setting/openclaw-qq/login/" : "/api/tools/sign/" + provider + "/qr/"
        w.request(base + (qq ? "start" : "create"), {}, r => {
            const url = qq ? r.qrUrl : r.qr_url
            const image = w.qr(url)
            if (!image) {
                w.page(
                    kind,
                    [SD.note("二维码生成失败，可重新获取。", true)],
                    { 重试: () => start(provider) },
                    home
                )
                return
            }
            let status = "请使用对应平台的手机应用扫码"
            const blocks = [
                { t: "qr", url: image },
                SD.kv("登录状态", [["状态", { c: "dyn", f: () => status }]])
            ]
            w.page(kind, blocks, { 重新获取: () => start(provider) }, home)
            function stop(text) {
                w.tick = null
                status = text
                w.changed()
            }
            function finished() {
                w.leave()
                w.host.fetchLive(qq ? "settings" : "gamesign")
                w.message("绑定已更新")
            }
            w.tick = () =>
                w.request(
                    base + "check",
                    qq ? { sessionId: r.sessionId } : { ticket: r.ticket, device: r.device },
                    v => {
                        if (qq) {
                            if (v.state === "connected") {
                                finished()
                                return
                            }
                            if (["expired", "error"].includes(v.state)) {
                                stop(v.message || "二维码失效")
                                return
                            }
                            status =
                                {
                                    waiting: "等待扫码",
                                    scanned: "已扫码",
                                    connecting: "绑定成功，等待网关连接"
                                }[v.state] || v.state
                        } else if (v.status === "Confirmed") {
                            w.tick = null
                            const body =
                                provider === "skland"
                                    ? { account_uid: accountId, scan_code: v.scan_code }
                                    : { account_uid: accountId, cookie: v.cookies_str }
                            w.request(base + "save", body, finished, stop)
                        } else if (["Init", "Scanned"].includes(v.status))
                            status = v.status === "Scanned" ? "已扫码，请在手机上确认" : "等待扫码"
                        else {
                            stop(v.message || "二维码失效")
                            return
                        }
                        w.changed()
                    },
                    stop
                )
        })
    }
    function home() {
        if (qq) {
            w.request("/api/setting/openclaw-qq/status", {}, s =>
                w.page(
                    kind,
                    [
                        SD.kv("QQ 官方机器人", [
                            ["绑定状态", s.connected ? "已绑定" : "未绑定"],
                            ["连接状态", s.state || "未连接"]
                        ])
                    ],
                    {
                        扫码绑定: () => start("qq"),
                        解除绑定: () =>
                            w.ask("解除绑定", "解除当前 QQ 官方机器人绑定？", () =>
                                w.request("/api/setting/openclaw-qq/unbind", {}, () => {
                                    w.leave()
                                    w.host.fetchLive("settings")
                                })
                            )
                    }
                )
            )
        } else {
            const phone = SD.inp(""),
                password = Object.assign(SD.inp(""), { secret: true })
            w.page(
                kind,
                [
                    SD.kv("扫码登录", [
                        ["米游社", button("生成二维码", () => start("miyoushe"))],
                        ["森空岛", button("生成二维码", () => start("skland"))],
                        [
                            "库街区",
                            button("打开 Better MAS Tools", () =>
                                Qt.openUrlExternally("https://github.com/Lance0174/Better-MAS-Tools")
                            )
                        ]
                    ]),
                    SD.kv("塔吉多", [
                        ["手机号", phone],
                        ["密码", password]
                    ])
                ],
                {
                    塔吉多登录: () => {
                        w.request(
                            "/api/tools/sign/account/taygedo/login",
                            { accountId: accountId, phone: phone.v, password: password.v },
                            () => {
                                password.v = ""
                                w.leave()
                                w.host.fetchLive("gamesign")
                                w.message("凭据已保存")
                            }
                        )
                    }
                }
            )
        }
    }
    home()
}

function localLogs(w) {
    function list() {
        const rows = w.logs().map(f => [f.label, button("查看", () => read(f))])
        w.page(
            "本机日志",
            [
                rows.length
                    ? SD.table("本次与归档", ["日志", ""], rows, [4, 1])
                    : SD.note("暂无本机日志。", true)
            ],
            { 刷新: list }
        )
    }
    function read(f) {
        let previous,
            before = -1,
            paused = false
        const newer = []
        function refresh(force) {
            const result = w.logWindow(f.path, before, !!f.previous)
            if (!force && result.text === previous) return
            previous = result.text
            const lines = result.text.split("\n").map(s => ["", s, ""])
            const actions = {}
            if (result.start > result.floor)
                actions["较早"] = () => {
                    newer.push(before)
                    before = result.start
                    refresh(true)
                }
            if (newer.length)
                actions["较新"] = () => {
                    before = newer.pop()
                    refresh(true)
                }
            if (f.current && before < 0)
                actions[paused ? "继续更新" : "暂停更新"] = () => {
                    paused = !paused
                    refresh(true)
                }
            actions["最新"] = () => {
                before = -1
                newer.length = 0
                paused = false
                refresh(true)
            }
            w.page(f.label, [SD.log("日志", lines, true)], actions, list)
            if (f.current && before < 0 && !paused) w.tick = () => refresh(false)
        }
        refresh()
    }
    list()
}

function externalControl(w, kind) {
    const base = "/api/dispatch/external-holds/"
    function load() {
        w.request(base + "management", null, r => {
            const cfg = r.settings
            if (kind === "占用管理") {
                const rows = r.holds.map(h => [
                    h.scriptId,
                    h.callerId,
                    h.state,
                    button("解除", () =>
                        w.ask("解除占用", h.callerId + " · " + h.holdId, () =>
                            w.request(base + "force-release", { callerId: h.callerId, holdId: h.holdId }, load)
                        )
                    )
                ])
                w.page(
                    kind,
                    [
                        rows.length
                            ? SD.table("脚本占用", ["脚本", "调用方", "状态", ""], rows, [2, 1.2, 1, 1])
                            : SD.note("暂无外部程序占用脚本。", true)
                    ],
                    { 刷新: load }
                )
            } else if (kind === "邮箱指令") {
                const enabled = SD.tog(cfg.enabled),
                    email = SD.inp(cfg.email),
                    auth = Object.assign(SD.inp(""), { secret: true })
                const caller = SD.inp(""),
                    secret = Object.assign(SD.inp(""), { secret: true })
                const settings = () => ({
                    enabled: enabled.v,
                    email: email.v.trim(),
                    authorizationCode: auth.v || null
                })
                const save = extra => w.request(base + "settings", Object.assign(settings(), extra), load)
                const rows = cfg.callers.map(id => [
                    id,
                    button("移除", () =>
                        w.ask("移除调用方", id, () => save({ callerId: id, removeCaller: true }))
                    )
                ])
                w.page(
                    kind,
                    [
                        SD.kv("邮箱", [
                            ["启用", enabled],
                            ["QQ 邮箱", email],
                            ["授权码（留空保留）", auth]
                        ]),
                        SD.kv("调用方", [
                            ["标识", caller],
                            ["新密钥", secret]
                        ]),
                        SD.table("已授权", ["调用方", ""], rows, [3, 1])
                    ],
                    {
                        保存邮箱: () => save({}),
                        保存调用方: () => {
                            if (!caller.v.trim() || secret.v.length < 32) {
                                w.message("请输入调用方标识及至少 32 字符的新密钥")
                                return
                            }
                            save({ callerId: caller.v.trim(), callerSecret: secret.v })
                        },
                        测试邮箱: () => w.request(base + "mail-test", {}, v => w.message(v.message))
                    }
                )
            } else
                w.request(base + "contract", null, c => {
                    w.request("/api/info/combox/script", {}, response => {
                        const scripts = response.data.filter(row => row.value && row.value !== "-")
                        const script = SD.sel(
                            scripts.map(row => row.label),
                            0
                        )
                        const caller = SD.inp(cfg.callers[0] || "调用方标识"),
                            hold = SD.inp("外部任务")
                        const operation = SD.sel(["申请", "查询", "释放"], 0)
                        const example = () =>
                            w.host.signatureExample(
                                c.backendUrl,
                                scripts[script.v]?.value || "托管脚本 ID",
                                caller.v,
                                hold.v,
                                ["acquire", "status", "release"][operation.v]
                            )
                        function render() {
                            w.page(
                                kind,
                                [
                                    SD.kv("签名参数", [
                                        ["托管", script],
                                        ["调用方", caller],
                                        ["占用标识", hold],
                                        ["操作", operation]
                                    ]),
                                    multiline("Python · 本机请求", example(), true),
                                    SD.note(
                                        "使用邮箱发送同一条签名指令时，邮件标题为 [AUTO-MAS COMMAND v1]，正文为示例中的 body.decode()。",
                                        true
                                    )
                                ],
                                { 生成示例: render, 复制示例: () => w.host.copyText(example()) }
                            )
                        }
                        render()
                    })
                })
        })
    }
    load()
}

function accountStats(w, users) {
    function overview() {
        w.page(
            "账号统计",
            [
                SD.table(
                    "查询范围内的账号",
                    ["账号", "记录", ""],
                    Object.entries(users).map(([name, u]) => [
                        name,
                        String((u.index || []).length),
                        button("详情", () => detail(name, u))
                    ]),
                    [2, 1, 1]
                )
            ],
            {}
        )
    }
    function detail(name, u) {
        const blocks = []
        const labels = {
            resource_pulls: "资源折算抽数",
            carry_over_pulls: "可结转凭证",
            next_pool_shop_pulls: "下期商店",
            next_pool_signin_pulls: "下期签到",
            current_pool_total: "本期可用抽数",
            next_pool_total: "下期预计抽数"
        }
        const sections = {
            recruit_statistics: "公招统计",
            drop_statistics: "关卡掉落",
            matrix_statistics: "矩阵统计",
            pull_count_statistics: "抽数统计",
            error_info: "错误记录"
        }
        for (const key of Object.keys(sections)) {
            const rows = []
            for (const [label, value] of Object.entries(u[key] || {})) {
                if (value && typeof value === "object") {
                    for (const [sub, n] of Object.entries(value)) rows.push([label + " · " + sub, String(n)])
                } else rows.push([labels[label] || label, String(value)])
            }
            if (rows.length) blocks.push(SD.table(sections[key], ["项目", "数量 / 结果"], rows, [3, 1]))
        }
        if (!blocks.length) blocks.push(SD.note("当前账号在此时间段没有专项统计。", true))
        const records = (u.index || [])
            .slice()
            .reverse()
            .map(r => [
                r.date,
                r.result || r.status,
                Object.assign(SD.mini(["日志"]), {
                    ops: [{ historyLog: r.jsonFile, title: name + " · " + r.date }]
                })
            ])
        if (records.length) blocks.push(SD.table("运行记录", ["时间", "结果", ""], records, [2, 2, 0.7]))
        w.page(name, blocks, {}, overview)
    }
    overview()
}

function webhooks(w, title, userId) {
    const account = title === "Webhook"
    const base = account ? "/api/scripts/webhook/" : "/api/setting/webhook/"
    const scope = account ? { scriptId: w.source.uid, userId: userId } : {}
    function write(path, body, done) {
        if (account && w.affected()) {
            w.message("运行中，配置已锁定")
            return
        }
        w.request(path, Object.assign({}, scope, body), done)
    }
    function load(preferred) {
        w.request(base + "get", scope, r => {
            if (preferred && r.data[preferred]) {
                edit(preferred, r.data[preferred])
                return
            }
            const rows = r.index.map(i => [
                r.data[i.uid].Info.Name,
                r.data[i.uid].Info.Enabled ? "启用" : "停用",
                button("编辑", () => edit(i.uid, r.data[i.uid]))
            ])
            w.page(
                title,
                [
                    rows.length
                        ? SD.table("通知目标", ["名称", "状态", ""], rows, [3, 1, 1])
                        : SD.note("暂无 Webhook。", true)
                ],
                {
                    添加: () => write(base + "add", {}, result => load(result.webhookId)),
                    刷新: () => load()
                }
            )
        })
    }
    function edit(id, entry) {
        const info = entry.Info,
            data = entry.Data
        const name = SD.inp(info.Name),
            enabled = SD.tog(info.Enabled),
            url = SD.inp(data.Url || "", true)
        const method = SD.sel(["POST", "GET"], data.Method === "GET" ? 1 : 0)
        const headers = multiline("请求头", data.Headers || "{}", false),
            template = multiline("消息模板", data.Template, false)
        const payload = () => ({
            Info: { Name: name.v, Enabled: enabled.v },
            Data: { Url: url.v, Method: method.opts[method.v], Headers: headers.v, Template: template.v }
        })
        w.page(
            title,
            [
                SD.kv("通知目标", [
                    ["名称", name],
                    ["启用", enabled],
                    ["地址", url],
                    ["请求方法", method]
                ]),
                headers,
                template
            ],
            {
                保存: () => write(base + "update", { webhookId: id, data: payload() }, () => load()),
                测试: () => write("/api/setting/webhook/test", { data: payload() }, r => w.message(r.message)),
                删除: () =>
                    w.ask("删除 Webhook", name.v, () => write(base + "delete", { webhookId: id }, () => load()))
            },
            () => load()
        )
    }
    load()
}
