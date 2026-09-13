// «Быстрее печати в N раз» - полосой, а не только строкой. Две полосы: печать и
// голос, длина каждой - её скорость в словах в минуту. Голос длиннее ровно во
// столько раз, во сколько он быстрее, и это видно глазом, а не считается в уме.
//
// Числа - из истории, не из рекламы: печать это TYPING_WPM (оценка набора),
// голос - замер речи человека (stats.speech_wpm). ratio («в 3,0 раза») собран в
// Python, там же, где живёт склонение. Здесь только рисуем.
//
// Полосы вырастают от нуля за durSlow той же кривой, что и всё движение системы.
// Голос - акцентом (то самое «особенное»: ради этого числа диктовку и завели),
// печать - тихими чернилами. Тени нет: внутри едут полосы (см. Metric).

import QtQuick

Card {
    id: sb
    shadow: false

    property int typingWpm: 40
    property int voiceWpm: 0
    property string ratio: ""            // «в 3,0 раза» - готовая строка из Python

    readonly property int maxWpm: Math.max(1, typingWpm, voiceWpm)

    // Полосы растут при появлении данных. from:0 и перезапуск на смену скорости:
    // до захода на страницу voiceWpm нулевой, полосы пусты; пришло число -
    // поехали. Иначе к первому показу анимация давно бы отыграла в пустоту.
    property real progress: 0
    NumberAnimation on progress {
        id: grow
        from: 0; to: 1
        duration: T.durSlow * 1000
        easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut
    }
    onVoiceWpmChanged: grow.restart()

    // Модель двух полос. L.t уже здесь: подписи короткие и свои, готовыми
    // списками из Python их не собрать.
    readonly property var rows: [
        {name: L.t("печать"), wpm: sb.typingWpm, accent: false},
        {name: L.t("голос"),  wpm: sb.voiceWpm,  accent: true}
    ]

    Item {
        width: parent.width
        implicitHeight: col.implicitHeight + 32

        Column {
            id: col
            anchors { left: parent.left; right: parent.right; top: parent.top
                      leftMargin: 24; rightMargin: 24; topMargin: 16 }
            spacing: 12

            Repeater {
                model: sb.rows
                Item {
                    width: col.width
                    height: 22

                    // Подпись слева фиксированной ширины - чтобы обе полосы
                    // начинались от одной вертикали, иначе «печать» и «голос»
                    // разной длины сдвигали бы старт и полосы врали бы длиной.
                    Text {
                        id: name
                        anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                        width: 52
                        text: modelData.name
                        font.family: T.sans
                        font.pixelSize: T.tSm
                        color: modelData.accent ? T.text : T.textMuted
                    }

                    // Дорожка полосы. Значение - в самом конце дорожки, поэтому
                    // трек не тянется до правого края, а оставляет место числу.
                    Rectangle {
                        id: track
                        anchors { left: name.right; leftMargin: 8
                                  right: parent.right; rightMargin: 76
                                  verticalCenter: parent.verticalCenter }
                        height: 10
                        radius: 5
                        color: T.fill

                        Rectangle {
                            height: parent.height
                            radius: parent.radius
                            width: parent.width * Math.min(1, modelData.wpm / sb.maxWpm)
                                   * sb.progress
                            color: modelData.accent ? T.accent : T.ink
                            opacity: modelData.accent ? 1 : 0.72
                        }
                    }

                    Text {
                        anchors { left: track.right; leftMargin: 10
                                  verticalCenter: parent.verticalCenter }
                        text: (modelData.wpm || 0) + " сл/мин"
                        font.family: T.mono
                        font.pixelSize: T.t2xs
                        color: T.textMuted
                    }
                }
            }

            // Итог словами - под полосами. Число собрано в Python (ratio),
            // «быстрее, чем печатать руками» - готовый ключ, уже переведён.
            Text {
                visible: sb.ratio !== "" && sb.ratio !== "-"
                width: col.width
                wrapMode: Text.WordWrap
                text: sb.ratio + " " + L.t("быстрее, чем печатать руками")
                font.family: T.sans
                font.pixelSize: T.tSm
                color: T.textSecondary
                lineHeight: 1.3
            }
        }
    }
}
