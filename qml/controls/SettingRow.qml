// Строка карточки: «иконка - название - контрол» сверху, пояснение снизу и
// необязательное раскрытие «подробнее» под ним.
//
// .ins-card__header: padding 14px --pad-card, то есть 24 по горизонтали и 14
// по вертикали. Разделитель - по краю содержимого, а не встык к рамке: у
// карточки скруглены углы, и линия во всю ширину упиралась бы в дугу.
//
// Иконка и «подробнее» необязательны. Тот же компонент стоит в главном окне и
// в мастере первого запуска, где нет ни того, ни другого: пусто - и ряд
// выглядит ровно как раньше.
//
// **Почему подпись идёт ПОД контролом, а не слева от него.** Раньше заголовок
// и подпись стояли одной колонкой слева, а контрол забирал правый край - как
// в PowerToys. При ширине колонки 640 (задача 4 плана) так больше не выходит:
// на подпись остаётся 220-300 px, а утверждённые тексты - до 60 знаков, это
// 400-440 px. Тринадцать подписей из сорока переносились на вторую строку, и
// критерий «ни одной видимой строки длиннее одной» ломался ровно там, где
// его и ставили. Выбор был между «резать утверждённые тексты» и «дать подписи
// всю ширину ряда» - взяли второе: план прямо запрещает резать объяснения.
// Контрол за это поднялся на строку заголовка и центрируется по ней.
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
    // Путь иконки из Icons.qml. Пусто - ряд без иконки, текст начинается от
    // края карточки.
    property string icon: ""
    // Длинное объяснение под шевроном. Пусто - шеврона нет вовсе.
    property string more: ""
    // Два послабления для содержимого, а не для настроек: моноширинный шрифт
    // нужен служебной сводке (это голос терминала), Markdown - списку версий
    // (в CHANGELOG.md пункты пишутся с полужирным зачином, и без разметки Qt
    // рисует звёздочки буквально).
    property string moreFont: ""
    property int moreFormat: Text.PlainText
    property bool first: false
    property bool expanded: false
    default property alias control: holder.data

    readonly property int pad: 24
    // Иконка 20 плюс 12 воздуха. Текст раскрытия выравниваем по той же линии,
    // что и подпись, - иначе объяснение выглядит принадлежащим не этому ряду.
    readonly property int textLeft: icon !== "" ? pad + 32 : pad

    width: parent ? parent.width : 0
    implicitHeight: head.height + moreBox.height

    Rectangle {
        visible: !row.first
        color: T.borderFlat
        height: 1
        anchors { left: parent.left; right: parent.right
                  leftMargin: row.pad; rightMargin: row.pad; top: parent.top }
    }

    // Иконки живут в Icons.qml, а не строкой по месту, - даже одна. Свой
    // инстанс здесь потому, что синглтоном Icons намеренно не сделан (см. его
    // шапку), а тянуть `ic` из окна-хозяина значит связать компонент с тремя
    // разными окнами сразу.
    Icons { id: ico }

    Item {
        id: head
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: texts.implicitHeight + 32

        Icon {
            visible: row.icon !== ""
            path: row.icon
            size: 20
            color: T.textSecondary
            // По центру строки заголовка, а не всего ряда: подпись бывает
            // длинной, и от неё иконка уезжала бы вниз.
            anchors { left: parent.left; leftMargin: row.pad; top: parent.top
                      topMargin: 16 + Math.max(0, (lineTop.height - 20) / 2) }
        }

        Column {
            id: texts
            anchors { left: parent.left; leftMargin: row.textLeft
                      right: parent.right; rightMargin: row.pad
                      top: parent.top; topMargin: 16 }
            spacing: 4

            Item {
                id: lineTop
                width: parent.width
                // Ряд без заголовка и без контрола (одна подпись) не должен
                // оставлять за собой пустую строку.
                visible: row.title !== "" || holder.width > 0
                height: Math.max(row.title !== "" ? titleText.implicitHeight : 0,
                                 holder.height)

                Text {
                    id: titleText
                    anchors { left: parent.left; right: holder.left; rightMargin: 16
                              verticalCenter: parent.verticalCenter }
                    visible: row.title !== ""
                    text: row.title
                    color: T.text
                    font.family: T.sans
                    font.pixelSize: T.tMd
                    elide: Text.ElideRight
                }

                Item {
                    id: holder
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    implicitWidth: childrenRect.width
                    implicitHeight: childrenRect.height
                    width: implicitWidth
                    height: implicitHeight
                }
            }

            Item {
                id: lineSub
                width: parent.width
                visible: row.subtitle !== "" || row.more !== ""
                height: Math.max(subText.implicitHeight, link.height)

                Text {
                    id: subText
                    anchors { left: parent.left
                              right: link.visible ? link.left : parent.right
                              rightMargin: link.visible ? 12 : 0
                              verticalCenter: parent.verticalCenter }
                    visible: row.subtitle !== ""
                    text: row.subtitle
                    color: T.textMuted
                    font.family: T.sans
                    font.pixelSize: T.tSm
                    wrapMode: Text.WordWrap
                    lineHeight: 1.25
                }

                // «подробнее» словом, а не голым шевроном. Программу ставят
                // людям, которые просто пишут письма: слово они прочитают, а
                // значок им ещё надо узнать.
                Item {
                    id: link
                    visible: row.more !== ""
                    width: visible ? linkRow.implicitWidth + 12 : 0
                    height: 20
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }

                    Rectangle {
                        id: linkFace
                        anchors.fill: parent
                        radius: T.radiusSm
                        color: linkHit.pressed ? T.fillStrong
                             : linkHit.containsMouse ? T.fill : "transparent"
                        Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
                    }
                    Row {
                        id: linkRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: L.t("подробнее")
                            font.family: T.sans
                            font.pixelSize: T.t2xs
                            font.weight: Font.Medium
                            color: linkHit.containsMouse ? T.text : T.textMuted
                        }
                        Icon {
                            anchors.verticalCenter: parent.verticalCenter
                            path: ico.chevron
                            size: 13
                            // Мелкая иконка требует штриха потолще: 1.9 на
                            // сетке 24 после сжатия до 13 даёт волосок.
                            weight: 2.4
                            color: linkHit.containsMouse ? T.text : T.textMuted
                            rotation: row.expanded ? 180 : 0
                            Behavior on rotation {
                                NumberAnimation { duration: T.durBase * 1000
                                                  easing.type: Easing.Bezier
                                                  easing.bezierCurve: T.easeOut }
                            }
                        }
                    }
                    // Таб доводит и до «подробнее»: это единственная дверь к
                    // длинному объяснению, и обходить её стороной нельзя.
                    activeFocusOnTab: visible
                    property bool mouseFocus: false
                    onActiveFocusChanged: if (!activeFocus) mouseFocus = false
                    Keys.onPressed: (e) => {
                        if (e.key === Qt.Key_Space || e.key === Qt.Key_Return
                                || e.key === Qt.Key_Enter) {
                            row.expanded = !row.expanded;
                            e.accepted = true;
                        }
                    }
                    FocusRing { target: linkFace; on: link.activeFocus && !link.mouseFocus }

                    MouseArea {
                        id: linkHit
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onPressed: { link.mouseFocus = true; link.forceActiveFocus() }
                        onClicked: row.expanded = !row.expanded
                    }
                }
            }
        }
    }

    // Раскрытие: высота от нуля до высоты текста, 180 мс той же кривой, что и
    // всё остальное движение в системе. Растим именно высоту, а не opacity:
    // соседние ряды должны разъезжаться, иначе текст ляжет поверх них.
    Item {
        id: moreBox
        anchors { left: parent.left; right: parent.right; top: head.bottom }
        clip: true
        height: row.expanded ? moreText.implicitHeight + 16 : 0
        Behavior on height {
            NumberAnimation { duration: T.durBase * 1000
                              easing.type: Easing.Bezier
                              easing.bezierCurve: T.easeOut }
        }

        Text {
            id: moreText
            anchors { left: parent.left; leftMargin: row.textLeft
                      right: parent.right; rightMargin: row.pad
                      top: parent.top }
            text: row.more
            textFormat: row.moreFormat
            wrapMode: Text.WordWrap
            font.family: row.moreFont !== "" ? row.moreFont : T.sans
            font.pixelSize: T.tSm
            color: T.textMuted
            lineHeight: 1.45
        }
    }
}
