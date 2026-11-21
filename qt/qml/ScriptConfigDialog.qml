import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "."

RhineDialog {
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
    code: "CSTD  /  CONFIGURATION"
    title: action
    serial: "X-002  ·  CFG"
    width: Math.min(820,parent.width-40); height: Math.min(session ? 330 : 720,parent.height-40)
    closePolicy: C.Popup.NoAutoClose
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
    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        RhineCombo {card:dialog.contentItem;label:"配置文件";visible:dialog.editingFile && dialog.files.length>1;Layout.fillWidth:true;model:dialog.files;currentIndex:dialog.files.indexOf(dialog.file)
            enabled:!dialog.busy && editor.text===dialog.original;onActivated:dialog.loadFile(currentText)}
        // 原文件编辑区（文本编辑需要滚动）
        Rectangle {visible:dialog.editingFile;Layout.fillWidth:true;Layout.fillHeight:true;color:"transparent";border.width:1.5;border.color:editor.activeFocus?Theme.accent:Theme.ink
            C.ScrollView {id:editorScroll;anchors.fill:parent;anchors.margins:8
                C.ScrollBar.vertical: RhineScrollBar { parent: editorScroll; x: editorScroll.width - width; height: editorScroll.height }
                C.ScrollBar.horizontal: RhineScrollBar { parent: editorScroll; y: editorScroll.height - height; width: editorScroll.width }
                C.TextArea {id:editor; color:Theme.ink; selectByMouse:true;readOnly:dialog.busy || !dialog.file; font.family:"Consolas"; font.pixelSize:14; selectionColor:Theme.accent; selectedTextColor:"#ffffff"; background:null} } }
        ColumnLayout {visible:!dialog.editingFile && !dialog.session;Layout.fillWidth:true;Layout.fillHeight:true;enabled:!dialog.busy;spacing:10
            RowLayout { spacing:14
                RhineCombo {card:dialog.contentItem;label:"Webhook";model:dialog.hooks.map(h=>h.Info.Name);currentIndex:dialog.hooks.indexOf(dialog.hook);Layout.fillWidth:true;opacity:dialog.hooks.length?1:0;enabled:dialog.hooks.length>0;onActivated: index => dialog.chooseHook(dialog.hooks[index])}
                RhineButton{text:"＋ 添加";small:true;onClicked:dialog.hookAction("add")} }
            Text {visible:!dialog.hook && !dialog.busy;text:"暂无 Webhook";color:Theme.muted;font.family:Theme.font;font.pixelSize:14;font.letterSpacing:1.2}
            GridLayout { columns:2;visible:!!dialog.hook;Layout.fillWidth:true;columnSpacing:20;rowSpacing:8
                FieldLabel{text:"名称"} RhineField{id:hookName;Layout.fillWidth:true}
                FieldLabel{text:"启用"} RhineSwitch{id:enabledHook}
                FieldLabel{text:"地址"} RhineField{id:url;Layout.fillWidth:true;mono:true}
                FieldLabel{text:"请求方式"} RhineCombo{id:method;card:dialog.contentItem;label:"请求方式";model:["POST","GET"]}
                FieldLabel{text:"请求头"} RhineField{id:headers;Layout.fillWidth:true;mono:true;placeholderText:"JSON"}
                FieldLabel{text:"消息模板"} RhineField{id:template;Layout.fillWidth:true}
            }
            Item {Layout.fillHeight:true}
            RowLayout{visible:!!dialog.hook;spacing:10
                RhineButton{text:"保存";primary:true;onClicked:dialog.hookAction("update")}
                RhineButton{text:"测试";onClicked:dialog.hookAction("test")}
                RhineButton{text:dialog.confirmRemove?"确认删除":"删除";danger:true;onClicked:dialog.hookAction("delete")}
            }
        }
        Item {visible:dialog.session;Layout.fillHeight:true}
        RowLayout {Layout.fillWidth:true;spacing:10
            Text { text:dialog.message;Layout.fillWidth:true;wrapMode:Text.Wrap;color:Theme.muted;font.family:Theme.font;font.pixelSize:13 }
            RhineButton {text:dialog.editingFile && editor.text!==dialog.original?"放弃修改并关闭":"关闭";enabled:!dialog.busy && !dialog.sessionId;onClicked:dialog.close()}
            RhineButton {visible:dialog.editingFile;primary:true;text:"写回原文件";enabled:!dialog.busy && !!dialog.file && (!dialog.online || !!dialog.revision);onClicked:dialog.writeFile()}
            RhineButton {visible:dialog.session;primary:true;text:dialog.sessionId?"结束会话":"启动源程序设置";enabled:!dialog.busy;onClicked:dialog.sessionAction()}
        }
    }
    component FieldLabel: Text {color:Theme.muted;font.family:Theme.font;font.pixelSize:14;font.letterSpacing:0.8;Layout.preferredWidth:96}
}
