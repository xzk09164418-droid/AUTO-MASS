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
        function refreshTitle(){
            const name=Live.fieldValue(entry,"Info.Name") || "未命名模拟器"
            const type=Live.fieldValue(entry,"Info.Type")
            store(records.map(e=>e.uid===entry.uid ? Object.assign({},e,{name:name,en:"EMULATOR · "+type.toUpperCase()}) : e))
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

    C.Popup {
        id: choices
        objectName: "emulatorSearchResults"
        parent: C.Overlay.overlay; anchors.centerIn: parent
        width: Math.min(660,parent.width-32)
        height: Math.min(parent.height-40,150+Math.min(manager.results.length,6)*74)
        modal:true; focus:true; padding:18
        closePolicy: manager.busy ? C.Popup.NoAutoClose : C.Popup.CloseOnEscape | C.Popup.CloseOnPressOutside
        background: Rectangle {color:Theme.paper;border.color:Theme.ink;border.width:2}
        contentItem: ColumnLayout {
            Text {text:manager.online?"搜索到的模拟器":"搜索结果（演示）";color:Theme.ink;font.family:Theme.font;font.pixelSize:22;font.bold:true}
            ListView {
                Layout.fillWidth:true;Layout.fillHeight:true
                clip:true;model:manager.results
                C.ScrollBar.vertical: C.ScrollBar {}
                delegate: RowLayout {
                    required property var modelData
                    width:ListView.view.width-12;height:72
                    ColumnLayout {
                        Layout.fillWidth:true
                        Text {Layout.fillWidth:true;text:modelData.name;elide:Text.ElideRight;color:Theme.ink;font.bold:true}
                        Text {Layout.fillWidth:true;text:modelData.path;wrapMode:Text.WrapAnywhere;maximumLineCount:2;elide:Text.ElideMiddle;color:Theme.muted}
                    }
                    C.Button {text:"导入";enabled:!manager.busy;onClicked:manager.add(modelData)}
                }
            }
            C.Button {Layout.alignment:Qt.AlignRight;text:"关闭";enabled:!manager.busy;onClicked:choices.close()}
        }
    }
}
