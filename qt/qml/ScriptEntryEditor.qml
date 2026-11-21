import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "."

RhineDialog {
    id: box
    required property var picker
    code: "CSTD  /  RECOVERY"
    title: restart ? "重启清单" : "清理清单"
    note: "共 " + rows.length + " 项"
    serial: "X-002  ·  LIST"
    width: Math.min(860,parent.width-40); height: Math.min(760,parent.height-40)
    // 条目按页显示（刻度翻页），不滚动
    readonly property int perPage: restart ? 2 : 4
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
        pager.pageIndex=Math.floor((rows.length-1)/perPage)
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
    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        Item {
            Layout.fillWidth: true; Layout.fillHeight: true
            WheelHandler { onWheel: event => pager.turnWheel(event.pixelDelta.y, event.angleDelta.y) }
            Text { visible: !box.rows.length; text: "清单为空"; color: Theme.muted; font.family: Theme.font; font.pixelSize: 14 }
            Column {
                width: parent.width; spacing: 14
                Repeater {
                    model: box.rows.slice(pager.pageIndex*box.perPage, (pager.pageIndex+1)*box.perPage)
                    ColumnLayout {
                        id:entry
                        required property int index
                        required property var modelData
                        readonly property int at: pager.pageIndex*box.perPage+index
                        width:parent.width; spacing:4
                        RowLayout {
                            spacing: 10
                            Rectangle { width: 4; height: 18; color: Theme.accent }
                            Text { text:String(entry.at+1).padStart(2,"0"); color:Theme.accent; font.family:Theme.font; font.pixelSize:14; font.weight:Font.Bold }
                            RhineSwitch { visible:box.restart; text:"主体"; checked:!!entry.modelData.IsMain
                                onToggled:{box.rows.forEach((r,i)=>r.IsMain=i===entry.at);box.rows=box.rows.slice()} }
                            Item {Layout.fillWidth:true}
                            RhineButton { small:true; text:"上移"; enabled:entry.at>0; onClicked:box.move(entry.at,-1) }
                            RhineButton { small:true; text:"下移"; enabled:entry.at+1<box.rows.length; onClicked:box.move(entry.at,1) }
                            RhineButton { small:true; danger:true; text:"移除"; onClicked:box.rows=box.rows.filter((_,i)=>i!==entry.at) }
                        }
                        Repeater {
                            model:box.restart?["Path","Arguments","WorkingDirectory","WaitSeconds"]:["Name","Path"]
                            RowLayout {
                                id:line
                                required property string modelData
                                Layout.fillWidth:true; spacing:12
                                LabelText { Layout.preferredWidth:84; color:Theme.muted; text:({Name:"进程名称",Path:"程序路径",Arguments:"启动参数",WorkingDirectory:"工作目录",WaitSeconds:"等待秒数"})[line.modelData] }
                                RhineField { id:value; Layout.fillWidth:true; mono:line.modelData!=="Name"; text:String(entry.modelData[line.modelData]??"")
                                    onTextEdited:entry.modelData[line.modelData]=line.modelData==="WaitSeconds"?Number(text):text }
                                RhineButton { small:true; visible:["Path","WorkingDirectory"].includes(line.modelData);text:"浏览";onClicked:box.picker.browse(value.text,"",line.modelData==="WorkingDirectory",p=>{
                                    entry.modelData[line.modelData]=p;value.text=p
                                    if (!box.restart && !entry.modelData.Name) {entry.modelData.Name=p.split(/[\\/]/).pop();box.rows=box.rows.slice()}
                                }) }
                            }
                        }
                        Rectangle { Layout.fillWidth:true; height:1; color:Theme.hair; Layout.topMargin:4 }
                    }
                }
            }
        }
        PageScale { id: pager; Layout.preferredWidth: parent.width/3; Layout.preferredHeight: 40; pages: Math.max(1, Math.ceil(box.rows.length/box.perPage)) }
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            RhineButton { text:"＋ 添加"; onClicked:box.add() }
            LabelText { Layout.fillWidth:true;text:box.error;color:Theme.error }
            RhineButton { text:"取消";onClicked:box.close() }
            RhineButton { text:"应用";primary:true;onClicked:box.apply() }
        }
    }
    component LabelText: Text {color:Theme.ink;font.family:Theme.font;font.pixelSize:14}
}
