import QtQuick
import QtQuick.Shapes

// 实验室导视图版，所有图形共用 96 × 60 的绘图坐标。
Item {
    id: art
    required property string department
    required property color ink
    required property color accent

    // 第一层为仪器轮廓，第二层标出该部门的观察点或操作位置。
    readonly property var drawings: ({
        home: [
            "M48 4 L80 21 V39 L48 56 L16 39 V21 Z M16 21 L48 38 L80 21 M48 38 V56 M28 15 L60 32 M36 10 L68 27",
            "M38 22 L48 17 L58 22 L48 28 Z"
        ],
        scripts: [
            "M20 6 H59 L70 17 V48 H20 Z M59 6 V17 H70 M26 54 H77 V22 M37 21 L30 27 L37 33 M52 21 L59 27 L52 33",
            "M46 18 H50 L43 36 H39 Z"
        ],
        emulators: [
            "M9 11 H64 V43 H9 Z M16 17 H57 V36 H16 Z M71 18 H85 V49 H62 M27 50 H47 M36 43 V50",
            "M66 40 H79 V45 H66 Z"
        ],
        queue: [
            "M8 12 H44 L55 23 H85 M8 30 H38 L49 41 H84 M8 48 H34 M72 15 L82 23 L72 31",
            "M8 7 H25 V16 H8 Z"
        ],
        scheduler: [
            "M48 6 A24 24 0 1 1 47.9 6 Z M48 10 V16 M28 30 H34 M62 30 H68 M48 44 V50 M48 30 L60 18",
            "M43 30 L48 25 L53 30 L48 35 Z"
        ],
        localControls: [
            "M20 12 H40 M54 12 H77 M20 30 H58 M72 30 H77 M20 48 H27 M41 48 H77 M41 7 H52 V17 H41 Z M28 43 H39 V53 H28 Z",
            "M58 24 H72 V36 H58 Z"
        ],
        gamesign: [
            "M27 34 L34 27 V20 A14 14 0 0 1 62 20 V27 L69 34 V40 H27 Z M20 48 H76 M26 54 H70",
            "M41 19 L46 24 L55 14 L58 17 L46 30 L38 22 Z"
        ],
        history: [
            "M13 16 A8 8 0 0 1 21 8 H75 A8 8 0 0 1 83 16 V43 H31 A9 9 0 0 1 13 43 Z M21 36 A7 7 0 1 0 21 50 A7 7 0 1 0 21 36 M31 22 H43 L48 15 L54 31 L60 22 H75",
            "M60 35 H74 V39 H60 Z"
        ],
        activity: [
            "M16 51 L48 8 L80 51 Z M28 51 L48 24 L68 51 M12 37 H31 M65 37 H84 M43 51 L48 44 L53 51",
            "M41 17 L48 7 L55 17 Z"
        ],
        settings: [
            "M48 4 L71 17 V43 L48 56 L25 43 V17 Z M48 15 L61 22 V38 L48 45 L35 38 V22 Z M25 17 L35 22 M61 38 L71 43",
            "M42 26 L48 22 L54 26 V34 L48 38 L42 34 Z"
        ]
    })
    readonly property var drawing: drawings[department] || []

    Shape {
        anchors.centerIn: parent
        width: 96
        height: 60
        scale: Math.min(art.width / width, art.height / height)
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: "transparent"
            strokeColor: art.ink
            strokeWidth: 2.8
            joinStyle: ShapePath.BevelJoin
            PathSvg { path: art.drawing[0] || "" }
        }
        ShapePath {
            fillColor: art.accent
            strokeColor: "transparent"
            PathSvg { path: art.drawing[1] || "" }
        }
    }
}
