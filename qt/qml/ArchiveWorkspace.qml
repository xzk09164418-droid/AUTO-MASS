import QtQuick
import "SectionData.js" as SD
import "ArchiveFlows.js" as Flows
import "EmulatorWorkspace.js" as Emulators

QtObject {
    id: desk
    required property var host
    required property var archive
    property var record: null
    property var source: null
    property int originalTab: 0
    property int generation: 0
    property bool busy: false
    property bool loadingPage: false
    property var tick: null
    property Timer timer: Timer {
        interval: 2000
        repeat: true
        running: !!desk.record && !!desk.tick && desk.host.opened
        onTriggered: if (!desk.busy)
                         desk.tick()
    }
    function leave() {
        generation++;
        tick = null;
        loadingPage = false;
        busy = false;
        if (record) {
            record = null;
            archive.tab = originalTab;
        }
        source = null;
    }
    function begin(kind, op) {
        if (!host.api || !host.item?.live) {
            host.toastText("后端尚未连接");
            return;
        }
        if (op.lock && host.runLocked) {
            host.toastText("运行中，配置已锁定");
            return;
        }
        leave();
        originalTab = archive.tab;
        source = host.item;
        page(kind, [SD.note("正在读取…", true)], {});
        loadingPage = true;
        if (kind === "自动识别管理")
            Emulators.open(desk, source.uid);
        else
            Flows.open(desk, kind, op);
    }
    function page(title, blocks, actions, back) {
        generation++;
        tick = null;
        loadingPage = false;
        busy = false;
        const ops = {};
        for (const label of Object.keys(actions))
            ops[label] = {
                perform: actions[label]
            };
        ops["返回"] = {
            perform: back || (() => leave())
        };
        record = {
            workspace: true,
            live: true,
            uid: source?.uid,
            name: title,
            en: "DETAIL",
            blocks: blocks,
            actions: Object.keys(ops),
            ops: ops
        };
        archive.tab = 0;
    }
    function request(path, body, accept, failed) {
        if (busy || !host.api)
            return;
        const version = generation;
        busy = true;
        function finish(result) {
            if (version !== generation)
                return;
            busy = false;
            if (result?.code === 200 && result.ok !== false)
                accept(result);
            else {
                const why = result?.reason || result?.message || "请求失败";
                if (failed)
                    failed(why);
                else if (loadingPage) {
                    const title = record.name;
                    page(title, [SD.note(why, true)], {
                             "重试": () => request(path, body, accept, failed)
                         });
                    loadingPage = true;
                } else
                    host.toastText(why);
            }
        }
        if (body === null)
            host.api.get(path, text => {
                             let result;
                             try {
                                 result = JSON.parse(text);
                             } catch (e) {}
                             finish(result);
                         });
        else
            host.call(path, body, finish);
    }
    function ask(label, detail, action) {
        const version = generation;
        host.askWorkspace(label, detail, () => {
                              if (version === generation && !busy)
                              action();
                          });
    }
    function message(text) {
        host.toastText(text);
    }
    function qr(url) {
        return fileLocations.qrImage(url);
    }
    function sampleHook(rule, sample) {
        return fileLocations.previewRule(JSON.stringify(rule), sample);
    }
    function logs() {
        return fileLocations.logFiles();
    }
    function logWindow(path, before, previous) {
        return fileLocations.logWindow(path, before, previous);
    }
    function affected() {
        return host.runLocked;
    }
    function changed() {
        archive.edits++;
    }
}
