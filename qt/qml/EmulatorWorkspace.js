.pragma library
.import "SectionData.js" as SD
.import "ArchiveFlows.js" as UI

function open(w, emulatorId) {
    if (w.source.deviceType !== "emulator2") {
        w.page("自动识别管理", [SD.note("请先保存模拟器类型。", true)], {})
        return
    }
    const api = "/api/emulator2/"
    const names = {
        width: "宽度",
        height: "高度",
        dpi: "DPI",
        cpu: "CPU 核数",
        memoryMb: "内存（MB）",
        fps: "帧率"
    }
    function request(path, data, done) {
        w.request(api + path, Object.assign({ emulatorId: emulatorId }, data), done)
    }
    const status = { 0: "在线", 1: "离线", 2: "启动中", 3: "关闭中", 4: "异常", 5: "未找到", 10: "未知" }
    function fingerprint(devices) {
        return JSON.stringify(devices.map(d => [d.slot, d.status, d.title, d.adbAddress, d.availability]))
    }
    function refresh() {
        request("devices", { withSettings: true }, r => {
            const paths = r.paths.map(p => [p.alias, p.installPath, UI.button("管理", () => pathPage(p))])
            const devices = r.devices.map(d => [
                d.slot,
                d.title || d.alias,
                status[d.status] || "未知",
                d.adbAddress || "—",
                UI.button("管理", () => device(d))
            ])
            w.page(
                "自动识别管理",
                [
                    SD.table("安装路径", ["名称", "目录", ""], paths, [1, 2.5, 0.7]),
                    SD.table("实例", ["设备号", "实例", "状态", "ADB", ""], devices, [0.7, 1.4, 0.8, 1.6, 0.7])
                ],
                {
                    添加路径: add,
                    批量设置: () => settings(null),
                    守卫基线: () =>
                        w.ask("采集守卫基线", "使用当前设备配置建立新的守卫基线？", () =>
                            request("guard/capture", {}, r => w.message("已采集 " + r.count + " 台设备"))
                        ),
                    刷新: refresh
                }
            )
            const version = w.generation,
                snapshot = fingerprint(r.devices)
            let polling = false
            w.tick = () => {
                if (polling) return
                polling = true
                w.host.call(api + "devices", { emulatorId: emulatorId, withSettings: false }, update => {
                    polling = false
                    if (
                        w.generation === version &&
                        update.code === 200 &&
                        snapshot !== fingerprint(update.devices)
                    )
                        refresh()
                })
            }
        })
    }
    function add() {
        const folder = Object.assign(SD.path(""), { folder: true }),
            alias = SD.inp("")
        function form(extra) {
            const actions = {
                搜索本机: () =>
                    request("search", {}, r => {
                        const rows = r.emulators.map(p => [
                            p.alias || p.type,
                            p.installPath,
                            p.supported
                                ? UI.button("选用", () => {
                                      folder.v = p.installPath
                                      alias.v = p.alias
                                      form([])
                                  })
                                : p.reason
                        ])
                        form([SD.table("搜索结果", ["名称", "目录", ""], rows, [1, 2.4, 1])])
                    }),
                "检查 AVD": () =>
                    w.request(api + "avd/status", { root: folder.v, refresh: true }, r =>
                        form([
                            SD.table(
                                "组件",
                                ["组件", "状态"],
                                r.components.map(c => [c.name, c.installed ? "已就绪" : "缺失"])
                            ),
                            SD.note(r.accelerationDetail || (r.ready ? "就绪" : "组件未就绪"), true)
                        ])
                    ),
                添加: () => request("paths/add", { installPath: folder.v, alias: alias.v || null }, refresh)
            }
            w.page(
                "添加路径",
                [
                    SD.kv("安装目录", [
                        ["目录", folder],
                        ["别名", alias]
                    ])
                ].concat(extra),
                actions,
                refresh
            )
        }
        form([])
    }
    function remove(kind, payload, label) {
        request(kind + "/preview", payload, r => {
            const affected = r.affectedScripts || []
            const note = affected.map(s => s.name + (s.running ? "（运行中）" : "")).join("、")
            w.ask(
                label,
                "影响的设备号：" +
                    (r.slots || [payload.slot]).join("、") +
                    "；关联托管：" +
                    (note || "无") +
                    "。",
                () => request(kind, payload, refresh)
            )
        })
    }
    function pathPage(p) {
        const name = SD.inp(""),
            rows = [
                ["路径", p.installPath],
                ["实例名称", name]
            ]
        const body = { pathId: p.pathId }
        const fields = {}
        if (p.type === "avd") {
            for (const [key, label, values] of [
                ["cpu", "CPU", [2, 4, 6]],
                ["memoryMb", "内存（MB）", [3072, 4096, 5120, 6144]],
                ["fps", "帧率", [30, 60]]
            ]) {
                const f = SD.sel(values.map(String), values.length - 1)
                fields[key] = () => values[f.v]
                rows.push([label, f])
            }
            const size = Object.assign(SD.num(64, "GB"), { min: 16, max: 512 })
            fields.dataPartitionGb = () => size.v
            rows.push(["数据盘上限", size])
        }
        w.page(
            p.alias,
            [SD.kv("新建实例", rows)],
            {
                创建实例: () => {
                    const data = Object.assign({ name: name.v || null }, body)
                    for (const key of Object.keys(fields)) data[key] = fields[key]()
                    request("instances/create", data, refresh)
                },
                移除路径: () => remove("paths/remove", body, "移除 " + p.alias)
            },
            refresh
        )
    }
    function device(d) {
        const actions = { 设置: () => settings(d) }
        const op = kind =>
            w.request(
                "/api/emulator/operate",
                { emulatorId: emulatorId, index: d.slot, operate: kind },
                refresh
            )
        if (d.status === 0) actions["显示"] = () => op("show")
        if ([0, 2].includes(d.status)) actions["关闭"] = () => op("close")
        else if ([1, 4, 5, 10].includes(d.status)) actions["启动"] = () => op("open")
        if (d.realType === "ldplayer" && d.status === 0)
            actions["游戏中心"] = () =>
                request("instances/store/open", { slot: d.slot }, r => w.message(r.message))
        actions["删除实例"] = () => remove("instances/delete", { slot: d.slot }, "删除实例 " + d.slot)
        const page = [
            SD.kv("设备", [
                ["名称", d.title],
                ["编号", d.slot],
                ["ADB", d.adbAddress || "—"],
                ["稳定模式", d.stableMode ? "已生效" : "未生效"]
            ])
        ]
        if (d.realType === "avd") {
            const apk = SD.path("")
            page.push(
                SD.kv("安装应用", [
                    ["APK", apk],
                    [
                        "",
                        UI.button("安装 APK", () =>
                            request("avd/instance/apk/install", { slot: d.slot, apkPath: apk.v }, r =>
                                w.message(r.message)
                            )
                        )
                    ]
                ])
            )
        }
        w.page(d.title || d.slot, page, actions, refresh)
    }
    function batchResult(r) {
        const rows = r.results.map(x => [x.slot, x.ok ? "已应用" : x.message])
        w.page("批量结果", [SD.table("逐台结果", ["设备", "结果"], rows)], {}, refresh)
    }
    function settings(d) {
        const fields = {},
            rows = []
        for (const key of Object.keys(names)) {
            if (d && !d.settings[key]) continue
            const value = d?.settings[key]?.value
            const field = SD.inp(value == null ? "" : String(value))
            fields[key] = field
            rows.push([names[key], field])
        }
        function apply() {
            const changes = {},
                expected = {}
            for (const key of Object.keys(fields)) {
                const raw = String(fields[key].v).trim(),
                    prior = d?.settings[key]?.value ?? null
                if (!raw) continue
                const n = Number(raw)
                if (!Number.isInteger(n) || n <= 0) {
                    w.message(names[key] + "须为正整数")
                    return
                }
                if (n !== prior) {
                    changes[key] = n
                    expected[key] = prior
                }
            }
            if (!Object.keys(changes).length) {
                w.message("没有需要写入的设置")
                return
            }
            if (d) request("settings/apply", { slot: d.slot, changes: changes, expected: expected }, refresh)
            else
                w.ask("批量应用", "将填写的设置应用到全部支持的实例？", () =>
                    request("settings/apply-all", { changes: changes }, batchResult)
                )
        }
        w.page(
            d ? "实例设置" : "批量设置",
            [SD.kv("下次启动使用", rows), SD.note("留空的字段保持原值。", true)],
            {
                应用: apply,
                应用稳定模式: () =>
                    w.ask("应用稳定模式", d ? "应用到当前设备？" : "应用到全部设备？", () =>
                        request("stable-mode/apply", { slots: d ? [d.slot] : [] }, batchResult)
                    )
            },
            refresh
        )
    }
    refresh()
}
