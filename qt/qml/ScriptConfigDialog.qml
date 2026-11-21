import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "."

C.Popup {
    id: dialog
    property var host
    property string action: ""
    property var item
    property var page
    property bool online: false
    property bool busy: false
    property string message: ""
    property string sessionId: ""
    property var files: []
    property string revision: ""
    property string file: ""
    property string original: ""
    property var hooks: []
    property var hook: null
    property bool confirmRemove: false
    readonly property bool editingFile: action === "编辑并写回原文件"
    readonly property bool session: action === "打开源程序设置"
    parent: C.Overlay.overlay; anchors.centerIn: parent
    width: Math.min(640,parent.width-24); height: Math.min(session ? 225 : 550,parent.height-24)
    modal: true; focus:true; padding:20; closePolicy:C.Popup.NoAutoClose
    background: Rectangle { color:Theme.paper; border.color:Theme.ink; border.width:2 }
    function request(url,body,done) {
        busy=true; message=""
        host.call(url,body,r=>{
            busy=false
            if (r.code!==200) {message=r.message || "操作失败";return}
            done(r)
        })
    }
    function begin(kind,record,p,live) {
        action=kind; item=record; page=p; online=live; message=""; files=[]; file=""; revision=""; original=""; editor.text=""; sessionId=""; hook=null; hooks=[]; confirmRemove=false
        open()
        if (editingFile) loadFile("")
        else if (!session) loadHooks("")
    }
    function loadFile(name) {
        if (!online) { files=["config.json"]; file=files[0]; original=item.previewText || "{}"; editor.text=original;return }
        request("/api/scripts/general/native/read",{scriptId:item.uid,file:name || ""},r=>{
            files=r.files || [];file=r.file || ""; revision=r.revision || "";original=r.content || "";editor.text=original
        })
    }
    function writeFile() {
        if (!online) {item.previewText=editor.text;close();return}
        request("/api/scripts/general/native/write",{scriptId:item.uid,file:file,revision:revision,content:editor.text},r=>{
            original=editor.text;revision=r.revision;close()
        })
    }
    function sessionAction(){
        if (!online) {sessionId=sessionId?"":"preview"; return}
        if (sessionId) request("/api/dispatch/stop",{taskId:sessionId},r=>{sessionId="";close()})
        else request("/api/dispatch/start",{taskId:item.uid,mode:"ScriptConfig",viewOnly:false},r=>{sessionId=r.taskId;message="请在源程序内保存设置后结束会话"})
    }
    function hookBody(extra){return Object.assign({scriptId:item.uid,userId:page.userId},extra)}
    function loadHooks(preferred) {
        function display(entries){hooks=entries;chooseHook(entries.find(h=>h.id===preferred)||entries[0]||null)}
        if (!online){display(page.previewHooks||[]);return}
        request("/api/scripts/webhook/get",hookBody({}),r=>display(r.index.map(i=>Object.assign({id:i.uid},r.data[i.uid]))))
    }
    function chooseHook(h) {
        hook=h;confirmRemove=false
        hookName.text=h?.Info?.Name || "";enabledHook.checked=!!h?.Info?.Enabled
        url.text=h?.Data?.Url || "";method.currentIndex=h?.Data?.Method==="GET"?1:0
        headers.text=h?.Data?.Headers || "";template.text=h?.Data?.Template || ""
    }
    function hookAction(op) {
        if (op==="delete" && !confirmRemove) {confirmRemove=true;return}
        const data={Info:{Name:hookName.text,Enabled:enabledHook.checked},Data:{Url:url.text,Method:method.currentText,Headers:headers.text,Template:template.text}}
        if (!online) {
            if (op==="test"){message="预览模式仅编辑配置";return}
            let list=hooks.slice(), id=hook?.id
            if (op==="add"){id=String(Date.now());list.push({id:id,Info:{Name:"新 Webhook"},Data:{}})}
            if (op==="update")list=list.map(h=>h.id===id?Object.assign({id:id},data):h)
            if (op==="delete")list=list.filter(h=>h.id!==id)
            page.previewHooks=list;loadHooks(id);return
        }
        const body=op==="add"?{}:op==="test"?{data:data}:op==="delete"?{webhookId:hook.id}:{webhookId:hook.id,data:data}
        request(op==="test"?"/api/setting/webhook/test":"/api/scripts/webhook/"+op,hookBody(body),r=>{
            if(op==="test")message="测试请求成功"
            else loadHooks(op==="add"?r.webhookId:hook?.id)
        })
    }
    Timer {
        interval: 1500; repeat: true; running: dialog.opened && dialog.online && !!dialog.sessionId
        property bool reading: false
        onTriggered: {
            if (reading || !dialog.host.api || dialog.busy) return
            const id=dialog.sessionId
            reading=true
            dialog.host.api.get("/api/dispatch/task/"+encodeURIComponent(id),text=>{
                reading=false
                if (dialog.sessionId!==id) return
                let r
                try { r=JSON.parse(text) } catch(e) { return }
                if (r.code===404 || ["success","error","cancelled"].includes(r.status)) {
                    dialog.sessionId=""; dialog.message=r.message || "设置会话已结束"
                }
            })
        }
    }
    contentItem: ColumnLayout {
        Text {text:"CSTD  /  CONFIGURATION";color:Theme.accent;font.bold:true}
        Text {text:dialog.action;color:Theme.ink;font.pixelSize:24;font.bold:true}
        C.ComboBox {visible:dialog.editingFile && dialog.files.length>1;Layout.fillWidth:true;model:dialog.files;currentIndex:dialog.files.indexOf(dialog.file)
            enabled:!dialog.busy && editor.text===dialog.original;onActivated:dialog.loadFile(currentText)}
        C.ScrollView {visible:dialog.editingFile;Layout.fillWidth:true;Layout.fillHeight:true
            C.TextArea {id:editor; color:Theme.ink; selectByMouse:true;readOnly:dialog.busy || !dialog.file; font.family:"Consolas"} }
        ColumnLayout {visible:!dialog.editingFile && !dialog.session;Layout.fillWidth:true;Layout.fillHeight:true;enabled:!dialog.busy
            RowLayout { C.ComboBox {model:dialog.hooks.map(h=>h.Info.Name);currentIndex:dialog.hooks.indexOf(dialog.hook);Layout.fillWidth:true;onActivated: index => dialog.chooseHook(dialog.hooks[index])}
                C.Button{text:"＋ 添加";onClicked:dialog.hookAction("add")} }
            GridLayout { columns:2;visible:!!dialog.hook;Layout.fillWidth:true
                Text{text:"名称";color:Theme.ink} C.TextField{id:hookName;Layout.fillWidth:true}
                Text{text:"启用";color:Theme.ink} C.CheckBox{id:enabledHook}
                Text{text:"URL";color:Theme.ink} C.TextField{id:url;Layout.fillWidth:true}
                Text{text:"请求方式";color:Theme.ink} C.ComboBox{id:method;model:["POST","GET"]}
                Text{text:"请求头 JSON";color:Theme.ink} C.TextField{id:headers;Layout.fillWidth:true}
                Text{text:"消息模板";color:Theme.ink} C.TextField{id:template;Layout.fillWidth:true}
            }
            RowLayout{visible:!!dialog.hook
                C.Button{text:"保存";onClicked:dialog.hookAction("update")}
                C.Button{text:"测试";onClicked:dialog.hookAction("test")}
                C.Button{text:dialog.confirmRemove?"确认删除":"删除";onClicked:dialog.hookAction("delete")}
            }
        }
        Text { text:dialog.message || (dialog.session?"在源程序内编辑并保存设置。":"");Layout.fillWidth:true;wrapMode:Text.Wrap;color:Theme.muted }
        RowLayout {Layout.alignment:Qt.AlignRight
            C.Button {text:dialog.editingFile && editor.text!==dialog.original?"放弃修改并关闭":"关闭";enabled:!dialog.busy && !dialog.sessionId;onClicked:dialog.close()}
            C.Button {visible:dialog.editingFile;text:"写回原文件";enabled:!dialog.busy && !!dialog.file && (!dialog.online || !!dialog.revision);onClicked:dialog.writeFile()}
            C.Button {visible:dialog.session;text:dialog.sessionId?"结束会话":"启动源程序设置";enabled:!dialog.busy;onClicked:dialog.sessionAction()}
        }
    }
}


