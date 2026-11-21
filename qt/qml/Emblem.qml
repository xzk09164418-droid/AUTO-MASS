import QtQuick
import QtQuick.Shapes

Item {
    id: em

    enum Face { Plate, Hub, Tape, Archive }
    property int face: Emblem.Plate
    property color ink: "#ffffff"
    property color core: "#e8701f"
    property bool curve: true
    implicitWidth: 40
    implicitHeight: 40

    // 统一使用切角与橙色定位点，各场景按自身尺寸选择轮廓。
    Shape {
        anchors.centerIn: parent
        width: 40
        height: 40
        scale: Math.min(em.width, em.height) / 40
        preferredRendererType: em.curve ? Shape.CurveRenderer : Shape.GeometryRenderer
        antialiasing: true

        ShapePath {
            fillColor: em.ink
            strokeColor: "transparent"
            fillRule: ShapePath.OddEvenFill
            PathSvg {
                path: {
                    switch (em.face) {
                    case Emblem.Hub:     // 指向入口的双折角
                        return "M2 29 L15 5 H23 L10 29 Z M15 29 L25 11 L37 33 H28 L25 26 L23 29 Z"
                    case Emblem.Tape:    // 带双卷轴留白的磁带
                        return "M3 9 H31 L37 15 V32 H3 Z M8 14 V24 H32 V14 Z M11 19 a3 3 0 1 0 6 0 a3 3 0 1 0 -6 0 M23 19 a3 3 0 1 0 6 0 a3 3 0 1 0 -6 0"
                    case Emblem.Archive: // 错位叠放的卷宗
                        return "M3 12 L19 4 L37 12 L21 20 Z M3 18 L21 26 L37 18 V23 L21 31 L3 23 Z M3 27 L21 35 L29 31 V35 L21 39 L3 31 Z"
                    default:             // 铭牌上的翼形字母 M
                        return "M3 34 V10 L9 5 L20 20 L31 5 L37 10 V34 H30 V18 L20 31 L10 18 V34 Z"
                    }
                }
            }
        }

        ShapePath {
            fillColor: em.core
            strokeColor: "transparent"
            PathSvg {
                path: {
                    switch (em.face) {
                    case Emblem.Hub: return "M2 32 H12 L9 37 H0 Z"
                    case Emblem.Tape: return "M10 27 H26 L28 30 H8 Z"
                    case Emblem.Archive: return "M31 30 L37 27 V32 L31 35 Z"
                    default: return "M16 34 L20 29 L24 34 L20 39 Z"
                    }
                }
            }
        }
    }
}
