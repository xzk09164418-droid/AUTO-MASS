import QtQuick
import "."

// 二级页面用下拉：与主页「完成后」同一实现（CardPowerSelect），菜单在所在页面内展开
CardPowerSelect {
    id: combo
    property var model: []
    property int currentIndex: 0
    readonly property string currentText: options[currentIndex] || ""
    signal activated(int index)
    options: model.map(x => String(x))
    selectedIndex: Math.max(0, currentIndex)
    minWidth: 120
    onPicked: index => { currentIndex = index; activated(index) }
}
