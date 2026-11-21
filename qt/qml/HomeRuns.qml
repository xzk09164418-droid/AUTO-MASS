import QtQuick
import "."
import "SectionData.js" as SD

// 行按运行实例标识保留，快照更新只改动对应行，手动查看其它行时不会跳回顶部。
Item {
    id: runs
    required property var api
    required property bool watching
    property alias rows: entries
    property bool submitting: false
    property bool reading: false
    property bool snapshotReady: false
    property string snapshotError: ""
    property var options: []
    property var activeTasks: []
    signal advanced(int row, int child)
    signal message(string text)
    ListModel { id: entries }

    function find(id) {
        for (let i = 0; i < entries.count; i++) if (entries.get(i).uid === id) return i
        return -1
    }
    function put(id, label, status, fraction, phase, children) {
        let index = find(id)
        const row = {uid:id, label:label, status:status, fraction:fraction, phase:phase}
        if (index < 0) {
            entries.append(Object.assign({steps: []}, row))
            index = entries.count - 1
        } else {
            const old = entries.get(index)
            if (old.fraction === fraction && old.status === status && old.phase === phase
                    && old.label === label && !children) return
            entries.set(index, row)
        }
        const steps = entries.get(index).steps
        let changed = -1
        if (children) {
            for (let i = 0; i < children.length; i++) {
                const step = children[i]
                const previous = i < steps.count ? steps.get(i) : null
                if (!previous) steps.append(step)
                else if (step.name === previous.name && step.state === previous.state
                         && step.progressValue === previous.progressValue && step.account === previous.account) continue
                else steps.set(i, step)
                if (changed === -1 || step.state === "运行") changed = i
            }
            if (steps.count > children.length) steps.remove(children.length, steps.count - children.length)
            if (changed < 0) return
        } else if (steps.count > 1) {
            // 队列整体结束时保留当前子项的位置。
            return
        }
        advanced(index, Math.max(0, changed))
    }
    function scriptSteps(scripts) {
        const finished = ["完成", "异常", "跳过"]
        return scripts.map(sc => {
            const users = sc.userList || []
            const current = users.find(u => u.status === "运行")
            const count = users.filter(u => finished.includes(u.status)).length
            return {name:sc.name, state:sc.status, account:current ? current.name : "",
                    progressValue:finished.includes(sc.status) ? 1 : users.length ? count / users.length : 0}
        })
    }
    function waitingSteps(names) {
        return names.map(name => ({name:name, state:"等待", account:"", progressValue:0}))
    }
    function trimFinished() {
        for (let i = entries.count - 1; i >= 0; i--)
            if (entries.get(i).phase === "ended") entries.remove(i)
    }
    function sync(tasks) {
        snapshotReady = true
        snapshotError = ""
        activeTasks = tasks
        const seen = new Set()
        for (const t of tasks) {
            seen.add(t.taskId)
            const option = options.find(o => o.value === (t.queueId || t.scriptId))
            const old = find(t.taskId)
            const scripts = t.task_info || []
            const done = ["完成", "异常", "跳过"]
            let total = 0, completed = 0, current = ""
            for (const sc of scripts) {
                const users = sc.userList || []
                const units = Math.max(1, users.length)
                total += units
                completed += done.includes(sc.status) ? units : users.filter(u => done.includes(u.status)).length
                if (sc.status === "运行") current = [sc.name, (users.find(u => u.status === "运行") || {}).name].filter(Boolean).join(" · ")
            }
            let children
            if (t.queueId && scripts.length) {
                children = scripts.length > 1 ? scriptSteps(scripts) : []
            } else if (t.queueId && t.scripts && t.scripts.length > 1 && (old < 0 || !entries.get(old).steps.count)) {
                children = waitingSteps(t.scripts.map((sc, i) => {
                    const match = options.find(o => o.value === sc.scriptId)
                    return match ? match.label : "子项 " + (i + 1)
                }))
            }
            put(t.taskId, option ? option.label : old >= 0 ? entries.get(old).label : (scripts[0] || {}).name || t.taskId.slice(0,8),
                t.stopping ? "正在停止" : current || "运行中", total ? completed / total : 0, "running", children)
        }
        for (let i = 0; i < entries.count; i++) {
            const row = entries.get(i)
            if (row.phase !== "running" || seen.has(row.uid) || !api) continue
            const id = row.uid
            entries.setProperty(i, "phase", "checking")
            api.get("/api/dispatch/task/" + encodeURIComponent(id), text => {
                const pos = find(id)
                if (pos < 0 || entries.get(pos).phase !== "checking") return
                let r = {}
                try { r = JSON.parse(text) } catch (e) {}
                const labels = {success:"完成", error:"异常", cancelled:"已停止"}
                const terminal = r.code === 200 && labels[r.status]
                const previous = entries.get(pos)
                put(id, previous.label, terminal || (r.code === 404 ? "已结束" : "等待同步"),
                    terminal && r.status === "success" ? 1 : previous.fraction, terminal || r.code === 404 ? "ended" : "running")
            })
        }
    }
    function poll() {
        if (!api || reading || submitting) return
        reading = true
        api.get("/api/dispatch/runtime-snapshot", text => {
            reading = false
            try {
                const snapshot = JSON.parse(text)
                if (!Array.isArray(snapshot.tasks)) throw new Error(snapshot.message || "运行状态读取失败")
                if (!submitting) sync(snapshot.tasks)
            } catch (e) { snapshotError = "运行状态同步失败，将自动重试" }
        })
    }
    Timer { interval: 1500; running: runs.watching && !!runs.api; repeat: true; onTriggered: runs.poll() }

    function launch(tasks, mode, power) {
        if (submitting || !api || !tasks.length) return
        submitting = true
        const backend = api
        function post(path, body, callback) {
            backend.request(path, JSON.stringify(body), text => {
                let r
                try { r = JSON.parse(text) } catch (e) { r = {message:"响应无法解析"} }
                callback(r)
            })
        }
        post("/api/dispatch/set/power", {signal:power}, r => {
            if (r.code !== 200) { submitting = false; message("设置电源动作失败：" + (r.message || "")); return }
            trimFinished()
            let index = 0, started = 0
            function next() {
                if (index === tasks.length) {
                    submitting = false
                    message("已启动 " + started + " / " + tasks.length + " 个任务")
                    poll()
                    return
                }
                const task = tasks[index++]
                post("/api/dispatch/start", {taskId:task.value, mode:mode}, result => {
                    if (result.code === 200 && result.taskId) {
                        started++
                        put(result.taskId, task.label, "已启动", 0, "running")
                        loadQueueSteps(task, result.taskId)
                    } else put("failed-" + task.value, task.label, result.message || "启动失败", 0, "ended")
                    next()
                })
            }
            next()
        })
    }
    // 很短的队列可能在首次轮询前就已退出，先补上配置顺序，实时快照到达后接管。
    function loadQueueSteps(task, runId) {
        if (!task.label.startsWith("队列 - ")) return
        api.request("/api/queue/item/get", JSON.stringify({queueId:task.value}), text => {
            const i = find(runId)
            if (i < 0 || entries.get(i).steps.count) return
            let r
            try { r = JSON.parse(text) } catch (e) { return }
            if (r.code !== 200 || !Array.isArray(r.index) || !r.data) return
            const names = r.index.map((entry, n) => {
                const data = r.data[entry.uid]
                const match = data && options.find(o => o.value === data.Info.ScriptId)
                return match ? match.label.replace(/^脚本 - [^-]+ - /, "") : "子项 " + (n + 1)
            })
            if (names.length > 1) {
                const row = entries.get(i)
                put(runId, row.label, row.status, row.fraction, row.phase, waitingSteps(names))
            }
        })
    }
    function preview(tasks) {
        entries.clear()
        for (const t of tasks) {
            const queue = SD.sections["04"].items.find(q => t.value === q.name + " · 队列" || t.value === q.name + " · 循环队列")
            put(t.value, t.label, "待运行", 0, "demo", queue && queue.accounts.length > 1 ? waitingSteps(queue.accounts) : [])
        }
        demo.restart()
    }
    function stopPreview() {
        demo.stop()
        for (let i=0; i<entries.count; i++)
            if (entries.get(i).phase === "demo") entries.set(i,{status:"已停止",phase:"ended"})
    }
    Timer {
        id: demo
        interval: 450
        repeat: true
        onTriggered: {
            for (let i=0; i<entries.count; i++) {
                const r=entries.get(i)
                if (r.phase !== "demo") continue
                if (r.steps.count) {
                    const children = []
                    let advancedStep = false, total = 0
                    for (let j = 0; j < r.steps.count; j++) {
                        const step = r.steps.get(j)
                        let progress = step.progressValue
                        if (!advancedStep && progress < 1) {
                            progress = Math.min(1, progress + 0.25)
                            advancedStep = true
                        }
                        total += progress
                        children.push({name:step.name, progressValue:progress, account:"",
                                       state:progress === 1 ? "完成" : progress ? "运行" : "等待"})
                    }
                    const fraction = total / children.length
                    runs.put(r.uid, r.label, fraction === 1 ? "完成" : "演示运行", fraction, fraction === 1 ? "ended" : "demo", children)
                    return
                }
                const progress=Math.min(1,r.fraction+0.25)
                runs.put(r.uid,r.label,progress===1?"完成":"演示运行",progress,progress===1?"ended":"demo")
                return
            }
            stop()
        }
    }
}
