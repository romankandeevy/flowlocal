// Сцена для демо-гифки: окно, в которое диктуют, и клавиши-бейджи.
//
// Пилюли здесь НЕТ намеренно. Она снимается из настоящего окна оверлея
// (overlay_qt.Overlay, те же флаги, тот же QML) и подклеивается кадром сверху
// в tools/demo_gif.py. Нарисовать её тут второй раз значило бы показать в
// README не то, что видит человек, а её похожую копию.
//
// Окно-приёмник поддельное, и это честно: настоящее чужое окно снять нельзя,
// не сняв заодно чужую почту. Ровно на этом уже обжигались - в репозиторий
// уехал скриншот с личными данными (HANDOFF, раздел 6). Здесь показывать
// нечего: адрес и тема выдуманы, а текст в теле - настоящий вывод модели.
//
// Клавиши-бейджи - подпись к жесту, а не элемент интерфейса. Без них гифка без
// звука не объясняет, что человек всё это время держал сочетание.

import QtQuick

Item {
    id: root
    width: 860
    height: 500

    property bool held: false        // сочетание зажато
    property string body: ""         // то, что вставилось

    Loader { anchors.fill: parent; source: "../qml/Backdrop.qml" }

    // ------- окно, в которое диктуют -------
    Rectangle {
        id: card
        x: 60
        y: 28
        width: parent.width - 2 * x
        height: 236
        radius: T.radiusLg
        color: T.paper
        border.width: 1
        border.color: T.border

        Text {
            id: title
            x: 20
            y: 16
            text: "Новое письмо"
            font.family: T.sans
            font.pixelSize: T.tSm
            font.weight: Font.DemiBold
            color: T.text
        }

        Rectangle { y: 48; width: parent.width; height: 1; color: T.border }

        // Поля адреса: приглушённые, они здесь только чтобы окно читалось
        // как почта, а не как абстрактный прямоугольник.
        Column {
            y: 62
            width: parent.width
            spacing: 10
            Repeater {
                model: [["Кому", "team@example.com"], ["Тема", "Планы на неделю"]]
                Row {
                    x: 20
                    spacing: 12
                    Text {
                        width: 52
                        text: modelData[0]
                        font.family: T.sans
                        font.pixelSize: T.tXs
                        color: T.textMuted
                    }
                    Text {
                        text: modelData[1]
                        font.family: T.sans
                        font.pixelSize: T.tXs
                        color: T.textSecondary
                    }
                }
            }
        }

        Rectangle { y: 118; width: parent.width; height: 1; color: T.border }

        // Тело письма. TextEdit, а не Text, ради курсора: он должен стоять
        // там, где кончился текст, и мигать - иначе непонятно, что окно живое
        // и текст пришёл в него, а не нарисован поверх.
        TextEdit {
            id: bodyText
            x: 20
            y: 138
            width: parent.width - 40
            readOnly: true
            activeFocusOnPress: false
            text: root.body
            wrapMode: Text.WordWrap
            font.family: T.sans
            font.pixelSize: T.tMd
            color: T.text
            cursorVisible: true
            cursorDelegate: Rectangle {
                width: 2
                color: T.text
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    PropertyAnimation { to: 1; duration: 0 }
                    PauseAnimation { duration: 520 }
                    PropertyAnimation { to: 0; duration: 0 }
                    PauseAnimation { duration: 520 }
                }
            }
            onTextChanged: cursorPosition = text.length
            Component.onCompleted: cursorPosition = text.length
        }
    }

    // ------- клавиши -------
    Row {
        id: keys
        anchors.horizontalCenter: parent.horizontalCenter
        y: 300
        spacing: 6

        Repeater {
            model: ["Ctrl", "Shift", "Space"]

            Rectangle {
                width: cap.implicitWidth + 26
                height: 30
                radius: T.radiusSm
                // Зажатая клавиша - заливка и линия построже, плюс сдвиг на
                // 1px вниз: нажатие в Korti выглядит именно так.
                y: root.held ? 1 : 0
                color: root.held ? T.fill : "transparent"
                border.width: 1
                border.color: root.held ? T.borderStrong : T.border

                Behavior on y { NumberAnimation { duration: T.durFast * 1000 } }
                Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
                Behavior on border.color { ColorAnimation { duration: T.durFast * 1000 } }

                Text {
                    id: cap
                    anchors.centerIn: parent
                    text: modelData
                    font.family: T.mono
                    font.pixelSize: T.t2xs
                    font.weight: Font.Medium
                    color: root.held ? T.text : T.textMuted
                    Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
                }
            }
        }
    }
}
