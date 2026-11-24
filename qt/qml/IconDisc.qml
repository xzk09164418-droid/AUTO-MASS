import QtQuick
import "."

// 录像带上的程序图标唱片（参考 Rhine Music Database 把封面放进录像带）：
// 浅色圆盘 + 外圈 + 放大的图标底纹 + 中央清晰图标。支持程序图标和已重绘的活动肖像。
Item {
    id: disc
    property string path: ""
    property string artwork: ""
    readonly property string source: artwork || (path ? "image://exeicon/" + encodeURIComponent(path) : "")

    Rectangle {
        id: face
        anchors.fill: parent
        radius: width / 2
        color: Theme.dark ? "#3b474b" : "#dcd8d1"
        border.width: Math.max(2, width * 0.035)
        border.color: Theme.dark ? "#56656a" : "#cdcac4"
        clip: true
        // 放大的图标作底纹
        Image {
            anchors.centerIn: parent
            width: parent.width * 0.9
            height: width
            asynchronous: true
            source: disc.source
            sourceSize: Qt.size(256, 256)
            opacity: 0.16
            smooth: true
            mipmap: true
        }
    }
    Rectangle {
        anchors.centerIn: parent
        width: parent.width * 0.86
        height: width
        radius: width / 2
        color: "transparent"
        border.width: 1
        border.color: Qt.rgba(0.16, 0.16, 0.14, 0.25)
    }
    Image {
        objectName: disc.artwork ? "activityPortrait" : ""
        anchors.centerIn: parent
        width: parent.width * 0.48
        height: width
        asynchronous: true
        source: disc.source
        sourceSize: Qt.size(256, 256)
        smooth: true
        mipmap: true
    }
}
