// Пилюля выбора преобразования: нажал сочетание - весь текст поля уже у нас,
// осталось выбрать, что с ним сделать.
//
// Переделана из вертикального списка в горизонтальную капсулу. Причина - в
// самой механике вызова: человек больше НЕ выделяет текст руками. Курсор просто
// стоит в поле, по сочетанию программа сама берёт весь текст (Ctrl+A, Ctrl+C),
// а здесь показывает по одному преобразованию - листаешь стрелками или колесом,
// цифрой прыгаешь, Enter применяешь, Esc отменяешь. Выбрал - весь текст поля
// заменяется результатом.
//
// Окно ЗАБИРАЕТ фокус, в отличие от пилюли-оверлея, и это осознанно: иначе
// стрелки и цифры уходили бы в чужое поле и печатались прямо в текст, который
// мы собираемся править. Текст к этому моменту уже лежит у нас в переменной
// (его сняли Ctrl+C до показа), поэтому терять нечего, а фокус в исходное окно
// возвращается перед вставкой - layered.focus_window() на стороне Python.
//
// Вид - «стиль пилюли-оверлея»: капсула на бумаге с волосяной рамкой и полным
// скруглением (radius = высота/2), как у Overlay.qml. Тени тут нет намеренно:
// PillShadow считает смещение через T.px(), а оверлей держит масштаб токенов
// равным DPI монитора ради попадания в физические пиксели, - в обычном окне это
// дало бы двойное увеличение. Поэтому здесь, как и в прежнем списке, значения
// сырые (T.tSm, T.radiusLg), без T.px(), и капсулу держит форма, а не тень.
//
// Контролы лежат в соседней папке, поэтому импорт каталога: соседства, на
// котором QML находит типы сам, между windows/ и controls/ уже нет.

import QtQuick
import "../controls"

Item {
    id: root
    // Ширина ОКНА постоянная - как у пилюли-оверлея: капсула дышит по ширине
    // внутри, а окно стоит на месте (его позицию Python ставит один раз при
    // показе). Превью и подсказка укладываются в эту же ширину, длинное - в
    // многоточие.
    width: 480
    height: col.implicitHeight + 2 * pad

    property var items: []
    property string preview: ""
    property int current: 0

    readonly property int pad: 20

    // Текущее преобразование одним объектом: и название, и подсказка, и id
    // берутся отсюда, чтобы не считать индекс в трёх местах. Пусто - null, и
    // вёрстка это переживает (показывает пустые строки).
    readonly property var cur:
        (items.length > 0 && current >= 0 && current < items.length)
        ? items[current] : null

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
        // Обе оси листают: горизонталь основная (капсула лежит вдоль неё), но
        // человек с привычкой к вертикальному списку нажмёт вверх/вниз - это не
        // должно быть тупиком.
        else if (e.key === Qt.Key_Left || e.key === Qt.Key_Up) {
            move(-1); e.accepted = true;
        } else if (e.key === Qt.Key_Right || e.key === Qt.Key_Down) {
            move(1); e.accepted = true;
        } else if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter) {
            take(current); e.accepted = true;
        } else if (e.key >= Qt.Key_1 && e.key <= Qt.Key_9) {
            take(e.key - Qt.Key_1); e.accepted = true;
        }
    }

    // Колесо листает наравне со стрелками. WheelHandler, а не MouseArea: он
    // pointer-handler и не спорит с MouseArea шевронов за клики - ему достаётся
    // только колесо.
    WheelHandler {
        onWheel: (e) => {
            if (e.angleDelta.y > 0) root.move(-1);
            else root.move(1);
        }
    }

    // Появление: фейд и рост из 98%, как у карточек и прежнего списка. Не
    // подъём снизу: у пилюли, открывшейся под курсором, направления «откуда»
    // нет. Пружин нет, Korti их не разрешает.
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

    Column {
        id: col
        y: root.pad
        width: parent.width
        spacing: 10

        // ----- что преобразуем: одна строка, приглушённо -----
        // Весь текст поля целиком заменится результатом, и человек должен
        // видеть, ЧТО именно он сейчас правит: замена большая, ошибиться дорого.
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.preview
            visible: text !== ""
            elide: Text.ElideRight
            maximumLineCount: 1
            font.family: T.sans
            font.pixelSize: T.tSm
            color: T.textMuted
        }

        // ----- капсула -----
        Item {
            id: capsuleBox
            anchors.horizontalCenter: parent.horizontalCenter
            width: pill.width
            height: pill.height

            Rectangle {
                id: pill
                anchors.horizontalCenter: parent.horizontalCenter
                height: contentRow.implicitHeight + 2 * 11
                radius: height / 2                 // --radius-full: пилюля есть пилюля
                color: T.paper
                border.width: 1
                border.color: T.border
                // Ширина по содержимому и плавно за ним: перелистнул на пункт
                // подлиннее - капсула доехала, а не прыгнула. Та же кривая, что
                // морфит ширину пилюли-оверлея.
                width: contentRow.implicitWidth + 2 * 16
                Behavior on width { NumberAnimation { duration: T.durBase * 1000
                                                      easing.type: Easing.Bezier
                                                      easing.bezierCurve: T.easeOut } }

                Row {
                    id: contentRow
                    anchors.centerIn: parent
                    spacing: 12

                    // Шеврон влево: и подсказка «листается», и клик - предыдущее.
                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        path: "m15 18-6-6 6-6"          // lucide chevron-left
                        size: 18
                        weight: 2
                        color: prevArea.containsMouse ? T.text : T.textFaint
                        MouseArea {
                            id: prevArea
                            anchors.fill: parent
                            anchors.margins: -6            // цель под палец крупнее самой галочки
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.move(-1)
                        }
                    }

                    // Счётчик «2 / 10»: и место в списке, и та самая цифра,
                    // которой сюда прыгают (для первых девяти). Моноширинным с
                    // табличными цифрами - чтобы не дёргался при смене числа.
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: (root.current + 1) + " / " + root.items.length
                        font.family: T.mono
                        font.pixelSize: T.t2xs
                        font.features: ({ "tnum": 1 })
                        color: T.textFaint
                    }

                    // Название и подсказка столбиком. Название переводится у
                    // готовых, у своих остаётся как есть: L.t() отдаёт
                    // непереведённое как есть, поэтому одно правило на оба.
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2
                        Text {
                            text: root.cur ? L.t(root.cur.title) : ""
                            font.family: T.sans
                            font.pixelSize: T.tMd
                            font.weight: Font.DemiBold
                            color: T.text
                        }
                        Text {
                            text: (root.cur && root.cur.hint) ? L.t(root.cur.hint) : ""
                            visible: text !== ""
                            font.family: T.sans
                            font.pixelSize: T.tSm
                            color: T.textMuted
                        }
                    }

                    // Шеврон вправо: клик - следующее.
                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        path: "m9 18 6-6-6-6"           // lucide chevron-right
                        size: 18
                        weight: 2
                        color: nextArea.containsMouse ? T.text : T.textFaint
                        MouseArea {
                            id: nextArea
                            anchors.fill: parent
                            anchors.margins: -6
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.move(1)
                        }
                    }
                }
            }
        }

        // ----- подсказка снизу -----
        // Что нажимать. Читают её один раз, поэтому под капсулой, а не на ней:
        // сама капсула остаётся чистой, как у пилюли-оверлея.
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: L.t("← → листать · Enter - применить · Esc - отмена")
            font.family: T.sans
            font.pixelSize: T.t2xs
            color: T.textFaint
        }
    }
}
