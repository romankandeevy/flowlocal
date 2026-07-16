// Строка карточки: «название - пояснение - контрол».
//
// .ins-card__header: padding 14px --pad-card, то есть 24 по горизонтали и 14
// по вертикали. Разделитель - по краю содержимого, а не встык к рамке: у
// карточки скруглены углы, и линия во всю ширину упиралась бы в дугу.
//
// В tkinter здесь была ловушка: pack раздаёт место в порядке вызовов, и
// контрол приходилось паковать ДО растягивающегося текста, иначе текст съедал
// ширину и контрол уезжал за край. У anchors такой беды нет - ширина текста
// считается от того, что осталось.

import QtQuick

Item {
    id: row
    property string title: ""
    property string subtitle: ""
    property bool first: false
    default property alias control: holder.data

    width: parent ? parent.width : 0
    implicitHeight: Math.max(texts.implicitHeight, holder.childrenRect.height) + 28

    Rectangle {
        visible: !row.first
        color: T.borderFlat
        height: 1
        anchors { left: parent.left; right: parent.right
                  leftMargin: 24; rightMargin: 24; top: parent.top }
    }

    Item {
        id: holder
        anchors { right: parent.right; rightMargin: 24
                  verticalCenter: parent.verticalCenter }
        implicitWidth: childrenRect.width
        implicitHeight: childrenRect.height
        width: implicitWidth
        height: implicitHeight
    }

    Column {
        id: texts
        anchors { left: parent.left; leftMargin: 24
                  right: holder.left; rightMargin: 14
                  verticalCenter: parent.verticalCenter }
        spacing: 2

        Text {
            width: parent.width
            text: row.title
            color: T.text
            font.family: T.sans
            font.pixelSize: T.tBase
            wrapMode: Text.WordWrap
        }
        Text {
            width: parent.width
            visible: row.subtitle !== ""
            text: row.subtitle
            color: T.textMuted
            font.family: T.sans
            font.pixelSize: T.tSm
            wrapMode: Text.WordWrap
            lineHeight: 1.25
        }
    }
}
