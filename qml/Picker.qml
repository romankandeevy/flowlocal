// Список преобразований: выделил текст, нажал сочетание, выбрал что сделать.
//
// Окно ЗАБИРАЕТ фокус, в отличие от пилюли, и это осознанно. Иначе список
// нечем было бы листать: клавиши уходили бы в чужое окно и печатались прямо в
// текст, который мы собираемся править. Выделение к этому моменту уже лежит у
// нас в переменной (его сняли Ctrl+C до показа), поэтому терять нечего, а
// фокус в исходное окно возвращается перед вставкой - layered.focus_window().
//
// Цифры слева не украшение: первые три пункта нажимаются не глядя, и ради
// этого список отсортирован по частоте, а не по алфавиту.

import QtQuick

Item {
    id: root
    width: 420
    height: col.implicitHeight + 2 * pad

    property var items: []
    property string preview: ""
    property int current: 0

    readonly property int pad: 8

    signal chosen(string id)
    signal cancelled()

    function move(delta) {
        if (items.length === 0)
            return;
        current = (current + delta + items.length) % items.length;
    }

    function take(i) {
        if (i >= 0 && i < items.length)
            chosen(items[i].id);
    }

    focus: true
    Keys.onPressed: (e) => {
        if (e.key === Qt.Key_Escape) { cancelled(); e.accepted = true; }
        else if (e.key === Qt.Key_Down) { move(1); e.accepted = true; }
        else if (e.key === Qt.Key_Up) { move(-1); e.accepted = true; }
        else if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter) {
            take(current); e.accepted = true;
        } else if (e.key >= Qt.Key_1 && e.key <= Qt.Key_9) {
            take(e.key - Qt.Key_1); e.accepted = true;
        }
    }

    // Появление: то же, что у карточек на «Главной» - фейд и подъём на 8px.
    // Пружин нет, Korti их не разрешает.
    opacity: 0
    y: 8
    Component.onCompleted: appear.start()
    ParallelAnimation {
        id: appear
        NumberAnimation { target: root; property: "opacity"; to: 1
                          duration: T.durFast * 1000; easing.type: Easing.OutCubic }
        NumberAnimation { target: root; property: "y"; to: 0
                          duration: T.durFast * 1000; easing.type: Easing.OutCubic }
    }

    Rectangle {
        anchors { fill: parent; margins: root.pad }
        radius: T.radiusLg
        color: T.surface
        border.width: 1
        border.color: T.border
    }

    Column {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top
                  margins: root.pad }
        spacing: 0

        // Что именно правим. Без этого человек не уверен, что выделил то, что
        // хотел, - а мы собираемся ЗАМЕНИТЬ этот текст, и ошибиться дорого.
        Item {
            width: parent.width
            height: 44
            Text {
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter
                          leftMargin: 16; rightMargin: 16 }
                text: root.preview
                elide: Text.ElideRight
                maximumLineCount: 1
                font.family: T.sans
                font.pixelSize: T.tXs
                color: T.textMuted
            }
        }
        Rectangle { width: parent.width; height: 1; color: T.border }

        Repeater {
            model: root.items
            Item {
                width: col.width
                height: 46

                readonly property bool active: index === root.current

                Rectangle {
                    anchors { fill: parent; leftMargin: 6; rightMargin: 6 }
                    radius: T.radiusMd
                    color: parent.active ? T.fill : "transparent"
                    Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
                }

                // Номер моноширинным: цифры в столбик не должны прыгать.
                Text {
                    anchors { left: parent.left; leftMargin: 18
                              verticalCenter: parent.verticalCenter }
                    text: index < 9 ? String(index + 1) : "·"
                    font.family: T.mono
                    font.pixelSize: T.t2xs
                    color: parent.active ? T.textSecondary : T.textFaint
                }

                Column {
                    anchors { left: parent.left; right: parent.right
                              leftMargin: 40; rightMargin: 16
                              verticalCenter: parent.verticalCenter }
                    spacing: 1
                    Text {
                        text: modelData.title
                        font.family: T.sans
                        font.pixelSize: T.tSm
                        font.weight: parent.parent.active ? Font.DemiBold : Font.Normal
                        color: T.text
                    }
                    Text {
                        width: parent.width
                        text: modelData.hint || ""
                        visible: text !== ""
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        font.family: T.sans
                        font.pixelSize: T.t2xs
                        color: T.textMuted
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onEntered: root.current = index
                    onClicked: root.chosen(modelData.id)
                }
            }
        }

        Rectangle { width: parent.width; height: 1; color: T.border }
        Item {
            width: parent.width
            height: 30
            Text {
                anchors { left: parent.left; leftMargin: 18
                          verticalCenter: parent.verticalCenter }
                text: "цифра или Enter - применить · Esc - отменить"
                font.family: T.sans
                font.pixelSize: T.t2xs
                color: T.textFaint
            }
        }
    }
}
