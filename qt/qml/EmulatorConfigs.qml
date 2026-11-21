import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "."
import "Live.js" as Live
import "SectionData.js" as SD

Item {
    id: manager
    required property var host
    readonly property bool online: host.onlineHome
    property int nextId: 0
    property var preview: SD.emulatorExamples.map((info,i)=>previewRecord("demo-"+i,info))
    readonly property var records: online ? (host.live.emulators || []) : preview
    readonly property var empty: ({ name:"模拟器配置", en:"EMULATOR", live:false,
        blocks:[SD.note(host.liveState==="error" ? "读取失败："+host.liveMessage :
            host.liveState==="loading" ? "正在读取配置…" : "暂无模拟器配置，可搜索本机安装或手动添加。",true)],
        actions:["搜索","添加","删除","保存"] })
    property bool busy: false
    property int readId: 0
    property var results: []
    signal message(string text)
    signal confirmRemoval(string label,var callback)

    function previewRecord(id,info) {
        const entry=Live.emulatorRecord(id,info)
        entry.live=false
        return entry
    }
    function store(list) {
        if (!online) preview=list
        else if (host.emulatorPage) host.setLive("emulators",list)
        else host.live=Object.assign({},host.live,{emulators:list})
    }
    function load() {
        const id=++readId
        host.call("/api/emulator/get",{},r=>{
            if (id!==readId) return
            if (r.code===200) store(r.index.map(e=>Live.emulatorRecord(e.uid,r.data[e.uid].Info)))
            else if (host.emulatorPage) host.fail(r)
        })
    }
    function canAct(action,record) {
        if (busy || host.saving || (online && !host.api)) return false
        if (online && !host.live.emulators) return action==="搜索" && host.liveState!=="loading"
        return !!record?.uid || action==="搜索" || action==="添加"
    }
    function selectNew(entry) {
        store(records.filter(e=>e.uid!==entry.uid).concat(entry))
        if (host.opened && host.emulatorPage) host.select(records.length-1)
    }
    function add(candidate) {
        if (busy) return
        const info=candidate ? {Name:candidate.name,Type:candidate.type,Path:candidate.path,MaxWaitTime:300,BossKey:"[]"} : {Name:"新模拟器",Type:"general"}
        if (!online) {
            selectNew(previewRecord("manual-"+(++nextId),info))
            choices.close()
            return
        }
        busy=true
        host.call("/api/emulator/add",{},r=>{
            if (r.code!==200) {busy=false;message(r.message || "添加失败");return}
            const id=r.emulatorId
            if (!candidate) {
                selectNew(Live.emulatorRecord(id,r.data.Info)); busy=false; message("已添加模拟器配置");return
            }
            host.call("/api/emulator/update",{emulatorId:id,data:{Info:info}},saved=>{
                const entry=Live.emulatorRecord(id,Object.assign({},r.data.Info,info))
                if (saved.code!==200) Live.eachSpec(entry,s=>{
                    if (Object.keys(info).includes(s.key.slice(5))) s.dirty=true
                })
                selectNew(entry); busy=false; choices.close()
                message(saved.code===200?"已导入模拟器配置":"配置已创建，导入未保存。可在本卡重试保存："+(saved.message || ""))
            })
        })
    }
    function search() {
        if (!online) {
            results=SD.emulatorExamples.filter(e=>e.Type!=="emulator2").map(e=>({name:e.Name,type:e.Type,path:e.Path}))
            choices.open()
            return
        }
        busy=true
        host.call("/api/emulator/emulator/search",{},r=>{
            busy=false
            if (!host.opened || !host.emulatorPage) return
            if (r.code!==200) {message(r.message || "搜索失败");return}
            results=r.emulators || []
            if (results.length) choices.open()
            else message("未搜索到已安装的模拟器")
        })
    }
    function remove(entry) {
        confirmRemoval(entry.name,()=>{
            function finish(){store(records.filter(e=>e.uid!==entry.uid));message("已删除模拟器配置")}
            if (!online) {finish();return}
            busy=true
            host.call("/api/emulator/delete",{emulatorId:entry.uid},r=>{
                busy=false
                if (r.code===200) finish()
                else message(r.message || "删除失败")
            })
        })
    }
    function save(entry) {
        const wait=Live.fieldValue(entry,"Info.MaxWaitTime")
        if (!Number.isInteger(wait) || wait<10 || wait>9999) {message("最大等待时间应为 10 至 9999 秒");return}
        const name = Live.fieldValue(entry,"Info.Name") || "未命名模拟器"
        const type = Live.fieldValue(entry,"Info.Type")
        function refreshTitle() {
            store(records.map(e => {
                if (e.uid !== entry.uid) return e
                const config = e.tabs[0]
                const blocks = [config.blocks[0]]
                if (type !== "emulator2") blocks.push(e.deviceTable)
                return Object.assign({}, e, {name:name, en:Live.emulatorCaption(type),
                    deviceType:type, tabs:[Object.assign({}, config, {blocks:blocks, actions:type === "emulator2" ? ["路径与实例","搜索","添加","删除","保存"] : ["搜索","添加","删除","保存"]})]})
            }))
        }
        if (online) host.save(refreshTitle)
        else {Live.clearDirty(entry);refreshTitle();message("已保存预览配置")}
    }
    function act(action,entry) {
        if (!canAct(action,entry)) return
        if (action==="搜索") search()
        else if (action==="添加") add(null)
        else if (action==="删除") remove(entry)
        else if (action==="保存") save(entry)
        else if (entry && entry.live) host.liveAction(action)
    }

    // 搜索结果：莱茵生命风格的二级页面，按页显示（刻度翻页），不滚动
    RhineDialog {
        id: choices
        objectName: "emulatorSearchResults"
        code: "EMUL  /  SEARCH"
        title: manager.online ? "搜索到的模拟器" : "搜索结果（演示）"
        note: "共 " + manager.results.length + " 个"
        serial: "X-003  ·  SCAN"
        width: Math.min(820, parent.width - 40)
        height: Math.min(640, parent.height - 40)
        closePolicy: manager.busy ? C.Popup.NoAutoClose : C.Popup.CloseOnEscape | C.Popup.CloseOnPressOutside
        readonly property int perPage: 5
        onOpened: pager.pageIndex = 0
        ColumnLayout {
            anchors.fill: parent
            spacing: 12
            Item {
                Layout.fillWidth: true; Layout.fillHeight: true
                WheelHandler { onWheel: event => pager.turnWheel(event.pixelDelta.y, event.angleDelta.y) }
                Column {
                    width: parent.width
                    Repeater {
                        model: manager.results.slice(pager.pageIndex * choices.perPage, (pager.pageIndex + 1) * choices.perPage)
                        Item {
                            id: found
                            required property var modelData
                            required property int index
                            width: parent.width; height: 70
                            Rectangle { anchors.fill: parent; color: Theme.ink; opacity: foundHover.hovered ? 0.05 : 0 }
                            HoverHandler { id: foundHover }
                            Text { x: 4; y: 12; text: String(pager.pageIndex * choices.perPage + found.index + 1).padStart(2, "0"); color: Theme.accent; font.family: Theme.font; font.pixelSize: 13; font.weight: Font.Bold }
                            Column {
                                x: 44; y: 10; width: parent.width - 44 - importBtn.width - 16; spacing: 4
                                Text { width: parent.width; text: found.modelData.name; elide: Text.ElideRight; color: Theme.ink; font.family: Theme.font; font.pixelSize: 16; font.weight: Font.Bold }
                                Text { width: parent.width; text: found.modelData.path; elide: Text.ElideMiddle; color: Theme.muted; font.family: "Consolas"; font.pixelSize: 13 }
                            }
                            RhineButton { id: importBtn; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; small: true; text: "导入"; enabled: !manager.busy; onClicked: manager.add(found.modelData) }
                            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.hair; opacity: 0.7 }
                        }
                    }
                }
            }
            PageScale { id: pager; Layout.preferredWidth: parent.width / 3; Layout.preferredHeight: 40; pages: Math.max(1, Math.ceil(manager.results.length / choices.perPage)) }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                RhineButton { text: "关闭"; enabled: !manager.busy; onClicked: choices.close() }
            }
        }
    }
}
