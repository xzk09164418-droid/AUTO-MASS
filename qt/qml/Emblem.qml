import QtQuick
import QtQuick.Shapes

// 铭牌与卡带面上的小标志（与方块里的圆环标志区分开）：
// 切角方框 + 「A」形折线 + 横档 + 右下琥珀方块，像一枚档案编号章。设计坐标 40×40。
Item {
    id: em
    property color ink: "#ffffff"
    property color core: "#e8701f"
    property real lineWidth: 2.6
    // 放在透视变换下的卡带面上时，曲线渲染器不出图，改用几何渲染
    property bool curve: true
    readonly property real k: width / 40

    implicitWidth: 40
    implicitHeight: 40

    Shape {
        anchors.fill: parent
        preferredRendererType: em.curve ? Shape.CurveRenderer : Shape.GeometryRenderer
        antialiasing: true
        // 切角方框：左上与右下各切一角
        ShapePath {
            fillColor: "transparent"
            strokeColor: em.ink
            strokeWidth: em.lineWidth * em.k
            joinStyle: ShapePath.MiterJoin
            startX: 9 * em.k; startY: 2 * em.k
            PathLine { x: 38 * em.k; y: 2 * em.k }
            PathLine { x: 38 * em.k; y: 26 * em.k }
            PathMove { x: 26 * em.k; y: 38 * em.k }
            PathLine { x: 2 * em.k; y: 38 * em.k }
            PathLine { x: 2 * em.k; y: 9 * em.k }
            PathLine { x: 9 * em.k; y: 2 * em.k }
        }
        // 「A」：折线 + 横档
        ShapePath {
            fillColor: "transparent"
            strokeColor: em.ink
            strokeWidth: em.lineWidth * 1.25 * em.k
            joinStyle: ShapePath.MiterJoin
            capStyle: ShapePath.FlatCap
            startX: 10 * em.k; startY: 31 * em.k
            PathLine { x: 20 * em.k; y: 9 * em.k }
            PathLine { x: 30 * em.k; y: 31 * em.k }
            PathMove { x: 14.5 * em.k; y: 23 * em.k }
            PathLine { x: 25.5 * em.k; y: 23 * em.k }
        }
    }
    Rectangle {
        x: 31 * em.k
        y: 31 * em.k
        width: 7 * em.k
        height: width
        color: em.core
    }
}
