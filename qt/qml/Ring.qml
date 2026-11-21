import QtQuick
import QtQuick.Shapes

// 以自身中心为圆心的圆弧，供授权圆环、加载指示等复用。
Item {
    id: ring
    property real radius: 50
    property real stroke: 4
    property color color: "#0b0c0b"
    property real startAngle: -90
    property real sweep: 360
    property bool roundCap: false

    width: 2 * (radius + stroke)
    height: width

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: "transparent"
            strokeColor: ring.color
            strokeWidth: ring.stroke
            capStyle: ring.roundCap ? ShapePath.RoundCap : ShapePath.FlatCap
            PathAngleArc {
                centerX: ring.width / 2
                centerY: ring.height / 2
                radiusX: ring.radius
                radiusY: ring.radius
                startAngle: ring.startAngle
                sweepAngle: ring.sweep
            }
        }
    }
}
