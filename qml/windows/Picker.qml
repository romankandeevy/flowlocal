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

// Контролы лежат в соседней папке, поэтому импорт каталога: соседства,
// на котором QML находит типы сам, между windows/ и controls/ уже нет.
// Почему каталог, а не qmldir, - разобрано в windows/Settings.qml.
import QtQuick
import "../controls"

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

    // Появление: то же, что у карточек на «Главной», - фейд и рост из 98%.
    // Не подъём снизу: у списка, который открылся под курсором, направления
    // «откуда» нет. Пружин нет, Korti их не разрешает.
    opacity: 0
    scale: 0.98
    Component.onCompleted: appear.start()
    ParallelAnimation {
        id: appear
        NumberAnimation { target: root; property: "opacity"; to: 1
                          duration: T.durFast * 1000
                          easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut }
        NumberAnimation { target: root; property: "scale"; to: 1
                          duration: T.durFast * 1000
                          easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut }
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
                font.pixelSize: T.tSm
                color: T.textMuted
            }
        }
        Rectangle { width: parent.width; height: 1; color: T.border }

        Repeater {
            model: root.items
            Item {
                id: pick
                width: col.width
                height: 46

                readonly property bool active: index === root.current

                Rectangle {
                    anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                    // Карточка скруглена на 12, подсветка вложена на 8:
                    // остаётся 4. См. тот же расчёт в Select.
                    radius: T.radiusLg - 8
                    color: parent.active ? T.fill : "transparent"
                    Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
                }

                // Номер моноширинным: цифры в столбик не должны прыгать.
                Text {
                    anchors { left: parent.left; leftMargin: 16
                              verticalCenter: parent.verticalCenter }
                    text: index < 9 ? String(index + 1) : "·"
                    font.family: T.mono
                    font.pixelSize: T.t2xs
                    color: parent.active ? T.textSecondary : T.textFaint
                }

                Column {
                    anchors { left: parent.left; right: parent.right
                              // 16 + 24: край строки плюс колонка под номер. Оба слагаемых - ступени
                              // шкалы, поэтому сумма с неё не сходит.
                              leftMargin: 16 + 24; rightMargin: 16
                              verticalCenter: parent.verticalCenter }
                    spacing: 4
                    // Готовые названия переводятся, свои - нет: их писал
                    // человек, и переводить его слова нам нечем и незачем.
                    // L.t() отдаёт непереведённое как есть, поэтому одно
                    // правило работает для обоих случаев.
                    Text {
                        text: L.t(modelData.title)
                        font.family: T.sans
                        font.pixelSize: T.tSm
                        // По id строки, а не `parent.parent`. Второе указывало
                        // на Column внутри строки, у которой свойства `active`
                        // нет вовсе: выражение молча давало undefined, и
                        // выбранный пункт никогда не становился полужирным.
                        // Ошибка тихая - QML на неизвестное свойство не ругается,
                        // а начертание «не изменилось» глазом не ловится.
                        // Нашёл qmllint, которого в проекте до сегодня не было.
                        font.weight: pick.active ? Font.DemiBold : Font.Normal
                        color: T.text
                    }
                    Text {
                        width: parent.width
                        text: modelData.hint ? L.t(modelData.hint) : ""
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
                anchors { left: parent.left; leftMargin: 16
                          verticalCenter: parent.verticalCenter }
                text: L.t("цифра или Enter - применить · Esc - отменить")
                font.family: T.sans
                font.pixelSize: T.t2xs
                color: T.textFaint
            }
        }
    }
}
