// Заголовок секции с кнопкой действия справа.
// Кнопка живёт именно здесь, а не в карточке: внутри она налезала бы на
// содержимое строк.

import QtQuick

Item {
    id: h
    property string text: ""
    property string buttonLabel: ""
    property string buttonKind: "secondary"
    signal action()

    width: parent ? parent.width : 0
    height: Math.max(title.implicitHeight, btn.height)

    SectionTitle {
        id: title
        anchors { left: parent.left; verticalCenter: parent.verticalCenter }
        text: h.text
    }

    FlowButton {
        id: btn
        anchors { right: parent.right; verticalCenter: parent.verticalCenter }
        visible: h.buttonLabel !== ""
        label: h.buttonLabel
        kind: h.buttonKind
        onClicked: h.action()
    }
}
