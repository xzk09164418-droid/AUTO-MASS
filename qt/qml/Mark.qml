import QtQuick
import QtQuick.Shapes

// AUTO-MAS 自有标志：细圆环 + 琥珀核心 + 四向刻度 + 斜线。设计坐标 40×40。
// progress 控制圆环与斜线的描绘进度，tickOpacity / coreScale 供启动动画分段显现。
Item {
    id: mark
    property color ink: "#0b0c0b"
    property color core: "#e8701f"
    property real progress: 1
    property real tickOpacity: 1
    property real coreScale: 1
    property real lineWidth: 3
    readonly property real k: width / 40

    implicitWidth: 40
    implicitHeight: 40

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            fillColor: "transparent"
            strokeColor: mark.ink
            strokeWidth: mark.lineWidth * mark.k
            capStyle: ShapePath.FlatCap
            PathAngleArc {
                centerX: 20 * mark.k
                centerY: 20 * mark.k
                radiusX: 15 * mark.k
                radiusY: 15 * mark.k
                startAngle: -45
                sweepAngle: 360 * mark.progress
            }
        }
        ShapePath {
            fillColor: "transparent"
            strokeColor: mark.ink
            strokeWidth: mark.lineWidth * 0.7 * mark.k
            capStyle: ShapePath.FlatCap
            startX: 9 * mark.k
            startY: 31 * mark.k
            PathLine {
                x: (9 + 22 * mark.progress) * mark.k
                y: (31 - 22 * mark.progress) * mark.k
            }
        }
    }

    Shape {
        anchors.fill: parent
        opacity: mark.tickOpacity
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: "transparent"
            strokeColor: mark.ink
            strokeWidth: mark.lineWidth * mark.k
            capStyle: ShapePath.FlatCap
            PathMove { x: 20 * mark.k; y: 0 }
            PathLine { x: 20 * mark.k; y: 6 * mark.k }
            PathMove { x: 20 * mark.k; y: 34 * mark.k }
            PathLine { x: 20 * mark.k; y: 40 * mark.k }
            PathMove { x: 0; y: 20 * mark.k }
            PathLine { x: 6 * mark.k; y: 20 * mark.k }
            PathMove { x: 34 * mark.k; y: 20 * mark.k }
            PathLine { x: 40 * mark.k; y: 20 * mark.k }
        }
    }

    Rectangle {
        width: 10 * mark.k
        height: width
        radius: width / 2
        anchors.centerIn: parent
        color: mark.core
        scale: mark.coreScale
    }
}
