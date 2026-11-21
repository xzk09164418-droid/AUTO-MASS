import QtQuick
import QtQuick.Layouts
import "." 
import "ActivityPresentation.js" as Presentation

Column {
    id: calendar
    required property var block
    property real now: Date.now()
    readonly property var model: Presentation.build(block.game, block.name, block.data, now)
    spacing: 18

    Timer { interval: 30000; repeat:true; running:calendar.visible; onTriggered:calendar.now=Date.now() }

    Rectangle {
        width: parent.width
        height: Math.max(190, bannerText.implicitHeight + 48)
        color: Theme.block
        clip: true
        Image {
            anchors.fill: parent
            source: /^https?:/.test(calendar.model.banner.cover) ? calendar.model.banner.cover : ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            sourceSize.width: 1000
        }
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position:0; color:"#de101713" }
                GradientStop { position:1; color:"#85101713" }
            }
        }
        Column {
            id: bannerText
            x:22; y:22; width:parent.width-44; spacing:10
            Text {
                textFormat: Text.PlainText
                text:calendar.model.name+(calendar.model.banner.version?" · "+calendar.model.banner.version:"")
                color:"#e5e6dd"; font.family:Theme.font; font.pixelSize:13; font.bold:true
            }
            Text {
                textFormat: Text.PlainText
                width:parent.width; text:calendar.model.banner.title; wrapMode:Text.Wrap
                color:"#ffffff"; font.family:Theme.font; font.pixelSize:26; font.bold:true
            }
            Text {
                textFormat: Text.PlainText
                text:Presentation.duration(calendar.model.banner,calendar.now)
                color:"#ffffff"; font.family:Theme.font; font.pixelSize:17
            }
            Text {
                textFormat: Text.PlainText
                width:parent.width; text:Presentation.boundary(calendar.model.banner,calendar.now)
                color:"#d7d8d0"; font.family:Theme.font; font.pixelSize:12; wrapMode:Text.Wrap
            }
        }
    }
    Text {
        textFormat: Text.PlainText
        width:parent.width; visible:text.length>0
        text:calendar.block.error || calendar.model.error
        color:Theme.warning; wrapMode:Text.Wrap; font.family:Theme.font; font.pixelSize:13
    }
    Repeater {
        model:calendar.model.sections
        Column {
            id: section
            required property var modelData
            width:calendar.width; spacing:10
            RowLayout {
                width:parent.width
                Rectangle { width:14; height:2; color:Theme.accent }
                Text { text:section.modelData.title; color:Theme.muted; font.family:Theme.font; font.pixelSize:13; font.bold:true }
                Rectangle { Layout.fillWidth:true; height:1; color:Theme.hair }
            }
            Text {
                textFormat: Text.PlainText
                visible:!!section.modelData.error || !section.modelData.rows.length
                width:parent.width; wrapMode:Text.Wrap
                text:section.modelData.error || (section.modelData.loading?"正在读取卡池…":"暂无"+section.modelData.title)
                color:section.modelData.error?Theme.warning:Theme.muted
                font.family:Theme.font; font.pixelSize:13
            }
            Grid {
                width:parent.width; columns:section.modelData.kind==="pools"?Math.min(2,section.modelData.rows.length):1; spacing:10
                Repeater {
                    model:section.modelData.rows
                    Rectangle {
                        id: entry
                        required property var modelData
                        readonly property bool pool:section.modelData.kind==="pools"
                        readonly property bool stacked:pool && section.modelData.rows.length>1
                        readonly property bool resource:section.modelData.kind==="resources"
                        readonly property bool upcoming:Presentation.time(modelData.startTime)>calendar.now
                        readonly property bool completed:!pool && (calendar.block.completed || []).includes(Presentation.key(modelData))
                        readonly property bool waiting:calendar.block.pendingKey===Presentation.key(modelData)
                        readonly property string picture:modelData.cover || (calendar.block.game==="endfield" || calendar.block.game==="arknights" ? "" : calendar.model.banner.cover)
                        width:entry.stacked?(calendar.width-10)/2:calendar.width
                        height:Math.max(entry.stacked?210:120, content.implicitHeight+(entry.stacked?118:26))
                        color:entry.completed?Qt.rgba(Theme.accent.r,Theme.accent.g,Theme.accent.b,0.08):Theme.paper
                        Rectangle { anchors.left:parent.left; width:2; height:parent.height; color:entry.completed?Theme.accent:Theme.hair }
                        Image {
                            id: art
                            x:entry.stacked?14:12; y:12
                            width:entry.stacked?parent.width-28:104; height:entry.stacked?92:parent.height-24
                            source:/^https?:/.test(entry.picture)?entry.picture:""
                            visible:source.toString().length>0 && status!==Image.Error
                            fillMode:entry.pool || entry.resource?Image.PreserveAspectFit:Image.PreserveAspectCrop
                            asynchronous:true; sourceSize.width:entry.stacked?360:240
                        }
                        Column {
                            id: content
                            x:!entry.stacked && art.visible?128:14
                            y:entry.stacked?112:13
                            width:parent.width-x-14; spacing:6
                            Text {
                                textFormat: Text.PlainText
                                width:parent.width; text:entry.modelData.name; wrapMode:Text.Wrap
                                color:Theme.ink; font.family:Theme.font; font.pixelSize:16; font.bold:true
                            }
                            Text {
                                textFormat: Text.PlainText
                                width:parent.width; visible:text.length>0
                                text:entry.modelData.tags?.join(" · ") || entry.modelData.kind || ""
                                wrapMode:Text.Wrap; color:Theme.muted; font.family:Theme.font; font.pixelSize:12
                            }
                            Text {
                                textFormat: Text.PlainText
                                width:parent.width; visible:text.length>0
                                text:entry.modelData.description || ""; wrapMode:Text.Wrap
                                color:Theme.muted; font.family:Theme.font; font.pixelSize:12
                            }
                            Text {
                                textFormat: Text.PlainText
                                text:Presentation.duration(entry.modelData,calendar.now)
                                color:entry.upcoming?Theme.muted:Theme.accent; font.family:Theme.font; font.pixelSize:14
                            }
                            Text {
                                textFormat: Text.PlainText
                                width:parent.width; text:Presentation.boundary(entry.modelData,calendar.now); wrapMode:Text.Wrap
                                color:Theme.muted; font.family:Theme.font; font.pixelSize:11
                            }
                            RhineButton {
                                visible:!entry.pool && !entry.resource
                                enabled:calendar.block.completed!==null && !calendar.block.pendingKey
                                small:true; text:entry.waiting?"保存中…":entry.completed?"已完成 · 撤销":"标记完成"
                                onClicked:calendar.block.toggle(entry.modelData,!entry.completed)
                            }
                        }
                    }
                }
            }
        }
    }
    Text {
        textFormat: Text.PlainText
        width:parent.width; wrapMode:Text.Wrap
        text:"数据来源 · "+calendar.model.source+(calendar.block.markError?"　"+calendar.block.markError:"")
        color:Theme.muted; font.family:Theme.font; font.pixelSize:11
    }
}
