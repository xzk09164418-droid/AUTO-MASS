import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "."

C.Popup {
    id: box
    required property var picker
    parent: C.Overlay.overlay; anchors.centerIn: parent
    width: Math.min(650,parent.width-24); height: Math.min(520,parent.height-24)
    modal: true; focus: true; padding: 20
    background: Rectangle { color: Theme.paper; border.color: Theme.ink; border.width: 2 }
    property var spec
    property var done
    property var rows: []
    property string error: ""
    readonly property bool restart: !!spec && spec.kind==="restart"
    function edit(field,callback) {
        spec=field; rows=JSON.parse(JSON.stringify(field.v)); done=callback; error=""; open()
    }
    function add() {
        rows=rows.concat(restart ? {Path:"",Arguments:"",WorkingDirectory:"",WaitSeconds:50,IsMain:!rows.length} : {Name:"",Path:""})
    }
    function move(index,delta) {
        const list=rows.slice()
        list.splice(index+delta,0,list.splice(index,1)[0]); rows=list
    }
    function apply() {
        for (const row of rows) {
            if (!row.Path.trim()) {error="请填写程序的完整路径";return}
            if (!restart && !row.Name.trim()) {error="请填写进程名称";return}
        }
        if (restart && rows.length && rows.filter(r=>r.IsMain).length!==1) {error="请指定一个主体程序";return}
        spec.v=rows; spec.dirty=true; done(); close()
    }
    contentItem: ColumnLayout {
        Text { text:"CSTD  /  RECOVERY";color:Theme.accent;font.bold:true }
        LabelText { text:box.restart?"重启清单":"清理清单";font.pixelSize:24 }
        C.ScrollView {
            Layout.fillWidth:true; Layout.fillHeight:true; contentWidth:availableWidth; clip:true
            Column {
                width:parent.width; spacing:8
                Repeater {
                    model:box.rows
                    ColumnLayout {
                        id:entry
                        required property int index
                        required property var modelData
                        width:parent.width
                        RowLayout {
                            LabelText { text:String(entry.index+1).padStart(2,"0") }
                            C.CheckBox { visible:box.restart; text:"主体"; checked:!!entry.modelData.IsMain
                                onClicked:{box.rows.forEach((r,i)=>r.IsMain=i===entry.index);box.rows=box.rows.slice()} }
                            Item {Layout.fillWidth:true}
                            C.Button { text:"↑"; enabled:entry.index>0; onClicked:box.move(entry.index,-1) }
                            C.Button { text:"↓"; enabled:entry.index+1<box.rows.length; onClicked:box.move(entry.index,1) }
                            C.Button { text:"移除"; onClicked:box.rows=box.rows.filter((_,i)=>i!==entry.index) }
                        }
                        Repeater {
                            model:box.restart?["Path","Arguments","WorkingDirectory","WaitSeconds"]:["Name","Path"]
                            RowLayout {
                                id:line
                                required property string modelData
                                Layout.fillWidth:true
                                LabelText { Layout.preferredWidth:78; text:({Name:"进程名称",Path:"程序路径",Arguments:"启动参数",WorkingDirectory:"工作目录",WaitSeconds:"等待秒数"})[line.modelData] }
                                C.TextField { id:value; Layout.fillWidth:true; text:String(entry.modelData[line.modelData]??"")
                                    onTextEdited:entry.modelData[line.modelData]=line.modelData==="WaitSeconds"?Number(text):text }
                                C.Button { visible:["Path","WorkingDirectory"].includes(line.modelData);text:"浏览";onClicked:box.picker.browse(value.text,"",line.modelData==="WorkingDirectory",p=>{
                                    entry.modelData[line.modelData]=p;value.text=p
                                    if (!box.restart && !entry.modelData.Name) {entry.modelData.Name=p.split(/[\\/]/).pop();box.rows=box.rows.slice()}
                                }) }
                            }
                        }
                    }
                }
            }
        }
        RowLayout {
            C.Button { text:"＋ 添加";onClicked:box.add() }
            LabelText { Layout.fillWidth:true;text:box.error;color:Theme.error }
            C.Button { text:"取消";onClicked:box.close() }
            C.Button { text:"应用";onClicked:box.apply() }
        }
    }
    component LabelText: Text {color:Theme.ink;font.family:Theme.font}
}
