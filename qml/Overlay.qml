// Пилюля-индикатор: загрузка / запись / распознавание / готово / ошибка.
//
// Это Qt-версия того, что overlay.py рисует в PIL (этап 6 плана). Смысл
// переезда виден прямо здесь: там скругление считалось суперсэмплом x3, тень
// размывалась гауссом и кэшировалась нарезкой по три куска, а кривая
// cubic-bezier(.2,.8,.2,1) была посчитана честной формулой. Тут это
// `radius`, `MultiEffect` и `easing.bezierCurve` - и всё крутится на
// render-потоке, мимо GIL.
//
// Все токены приходят из theme.py через контекстное свойство `T`: один
// источник правды, как требует CLAUDE.md. Своих чисел здесь нет.
//
// Qt Graphs (то есть графики) и Qt Quick Timeline - GPL-only, они утянули бы
// весь проект в GPL. Поэтому осциллограмма - Repeater из Rectangle, анимации -
// штатные NumberAnimation. Qt Quick и Qt GUI под LGPLv3, это нам подходит.

import QtQuick
import QtQuick.Effects

Item {
    id: root
    // Холст больше пилюли: тень уходит за её край, а места ей надо больше
    // снизу, чем сверху (--shadow-lg смещена вниз на 16px при сигме 20).
    // Симметричное поле обрезало бы хвост, и на светлом фоне появлялся
    // горизонтальный шов - на этом уже обжигались, см. HANDOFF.
    width: pill.width + 2 * T.pillPad
    height: T.pillH + T.pillPad + T.pillPadBottom

    // ------- вход из Python -------
    property string state_: "loading"     // loading|recording|processing|done|error
    property string message: ""
    property string hint: ""
    property real   seconds: 0
    property var    bars: []              // WAVE_BARS чисел 0..1
    property bool   shown: false

    readonly property bool isRec: state_ === "recording"
    readonly property color iconColor: state_ === "done"  ? T.success
                                     : state_ === "error" ? T.danger
                                                          : T.accent
    readonly property string label: state_ === "loading"    ? "загружаю модель"
                                  : state_ === "processing" ? "распознаю"
                                                            : message

    // Появление: прозрачность 0->1 и сдвиг на 8px вверх за 180 мс.
    // Без масштаба и без пружин - Korti разрешает фейды и небольшие сдвиги.
    opacity: shown ? 1 : 0
    transform: Translate { y: root.shown ? 0 : T.px(8)
        Behavior on y { NumberAnimation { duration: T.durBase * 1000
                                          easing.type: Easing.Bezier
                                          easing.bezierCurve: T.easeOut } } }
    Behavior on opacity { NumberAnimation { duration: T.durBase * 1000
                                            easing.type: Easing.Bezier
                                            easing.bezierCurve: T.easeOut } }

    // ------- капсула -------
    Rectangle {
        id: pill
        y: T.pillPad
        x: T.pillPad
        height: T.pillH
        radius: height / 2                    // --radius-full: пилюля есть пилюля
        color: T.paper
        // Волосяная линия вместо заливки - основной приём системы.
        border.width: 1
        border.color: T.border

        // Ширина зависит от состояния и от текста. Анимируем её той же кривой:
        // раньше это был кросс-фейд трёх нарезанных картинок.
        width: isRec ? recRow.implicitWidth + 2 * T.px(14)
                     : labelRow.implicitWidth + 2 * T.px(14)
        Behavior on width { NumberAnimation { duration: T.durBase * 1000
                                              easing.type: Easing.Bezier
                                              easing.bezierCurve: T.easeOut } }

        // ------- содержимое: запись -------
        Row {
            id: recRow
            anchors.centerIn: parent
            spacing: T.px(12)
            visible: isRec
            opacity: isRec ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: T.durFast * 1000 } }

            // Точка «в эфире». Зелёная, а не красная: в Korti зелёный - это
            // «успех/в эфире», а красный - ошибка. Мигать красным во время
            // нормальной диктовки значило бы врать.
            Rectangle {
                width: T.px(8); height: width; radius: width / 2
                anchors.verticalCenter: parent.verticalCenter
                color: T.success
                // Пульс только прозрачностью: масштаб - это уже пружинка.
                SequentialAnimation on opacity {
                    running: isRec; loops: Animation.Infinite
                    NumberAnimation { from: 0.45; to: 1.0; duration: 920
                                      easing.type: Easing.InOutSine }
                    NumberAnimation { from: 1.0; to: 0.45; duration: 920
                                      easing.type: Easing.InOutSine }
                }
            }

            // Осциллограмма - чернила: это данные, а не статус, тонировать нечем.
            Row {
                id: wave
                anchors.verticalCenter: parent.verticalCenter
                width: T.waveW
                height: T.waveH
                spacing: 0
                Repeater {
                    model: T.waveBars
                    Item {
                        width: T.waveW / T.waveBars
                        height: wave.height
                        Rectangle {
                            anchors.centerIn: parent
                            width: parent.width * 0.55
                            radius: width / 2
                            height: Math.max(T.px(1.5),
                                     (index < root.bars.length ? root.bars[index] : 0)
                                     * wave.height)
                            color: T.ink
                            // Хвост слева гаснет - полоски будто уплывают за край.
                            opacity: 0.90 * Math.min(1.0, (index + 1) / (T.waveBars * 0.16))
                            Behavior on height { NumberAnimation { duration: 70 } }
                        }
                    }
                }
            }

            // Таймер моноширинный: это метаданные, голос терминала. Цифры
            // табличные, поэтому 0:09 -> 0:10 не дёргает вёрстку.
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: Math.floor(root.seconds / 60) + ":"
                      + ("0" + Math.floor(root.seconds % 60)).slice(-2)
                font.family: T.mono; font.pixelSize: T.px(T.tXs); font.weight: Font.Medium
                color: T.textSecondary
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                visible: root.hint !== ""
                text: root.hint
                // Подсказка тише таймера: её читают один раз.
                font.family: T.mono; font.pixelSize: T.px(T.t2xs); font.weight: Font.Medium
                color: T.textMuted
            }
        }

        // ------- содержимое: остальные состояния -------
        Row {
            id: labelRow
            anchors.centerIn: parent
            spacing: T.px(10)
            visible: !isRec
            opacity: isRec ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: T.durFast * 1000 } }

            Item {
                width: T.px(16); height: T.px(16)     // иконка «в строку с текстом»
                anchors.verticalCenter: parent.verticalCenter

                // Спиннер Korti: кольцо с вырезанной четвертью, линейно, 0.6 с.
                Canvas {
                    id: ring
                    anchors.fill: parent
                    visible: state_ === "loading" || state_ === "processing"
                    property real deg: 0
                    onDegChanged: requestPaint()
                    onPaint: {
                        var ctx = getContext("2d");
                        ctx.reset();
                        var r = width * 0.43;
                        ctx.beginPath();
                        ctx.arc(width / 2, height / 2, r,
                                deg * Math.PI / 180, (deg + 270) * Math.PI / 180);
                        ctx.lineWidth = T.px(1.75);      // обводка Lucide
                        ctx.strokeStyle = root.iconColor;
                        ctx.stroke();
                    }
                    NumberAnimation on deg {
                        running: ring.visible; loops: Animation.Infinite
                        from: 0; to: 360; duration: 600      // --spin: .6s linear
                    }
                }

                // Lucide check: M20 6 L9 17 L4 12 на сетке 24.
                Canvas {
                    anchors.fill: parent
                    visible: state_ === "done"
                    // Canvas рисуется один раз и на смену цвета не смотрит:
                    // привязок внутри onPaint для него не существует. Без этих
                    // двух строк галка оставалась того цвета, который был на
                    // момент создания, - то есть синего вместо зелёного.
                    property color c: root.iconColor
                    onCChanged: requestPaint()
                    onVisibleChanged: requestPaint()
                    onPaint: {
                        var ctx = getContext("2d");
                        ctx.reset();
                        var k = width / 24;
                        ctx.beginPath();
                        ctx.moveTo(20 * k, 6 * k);
                        ctx.lineTo(9 * k, 17 * k);
                        ctx.lineTo(4 * k, 12 * k);
                        ctx.lineWidth = T.px(1.75);
                        ctx.lineCap = "round";
                        ctx.lineJoin = "round";
                        ctx.strokeStyle = root.iconColor;
                        ctx.stroke();
                    }
                }

                // Lucide alert-circle: кольцо, палка, точка.
                Canvas {
                    anchors.fill: parent
                    visible: state_ === "error"
                    property color c: root.iconColor
                    onCChanged: requestPaint()
                    onVisibleChanged: requestPaint()
                    onPaint: {
                        var ctx = getContext("2d");
                        ctx.reset();
                        var k = width / 24, c = width / 2;
                        ctx.lineWidth = T.px(1.75);
                        ctx.lineCap = "round";
                        ctx.strokeStyle = root.iconColor;
                        ctx.beginPath(); ctx.arc(c, c, 10 * k, 0, 2 * Math.PI); ctx.stroke();
                        ctx.beginPath(); ctx.moveTo(c, 8 * k); ctx.lineTo(c, 12.5 * k); ctx.stroke();
                        ctx.beginPath(); ctx.arc(c, 16 * k, T.px(0.9), 0, 2 * Math.PI);
                        ctx.fillStyle = root.iconColor; ctx.fill();
                    }
                }
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: root.label
                font.family: T.sans; font.pixelSize: T.px(T.tSm); font.weight: Font.DemiBold
                // Текст статуса чернилами, цвет несёт иконка - как в Toast.
                // Исключение - ошибка: там красный и текст.
                color: state_ === "error" ? T.danger : T.text
            }
        }
    }

    // --shadow-lg в два слоя: 0 4px 8px rgb(0 0 0/.06) и 0 16px 40px rgb(0 0 0/.12).
    // MultiEffect умеет одну тень, поэтому их две, вложенные. CSS-радиус
    // размытия r - это примерно гаусс с сигмой r/2, а blurMax у Qt задаётся
    // в тех же пикселях, что и радиус CSS.
    MultiEffect {
        source: pill
        anchors.fill: pill
        shadowEnabled: true
        shadowColor: T.shadowFar
        shadowVerticalOffset: T.px(16)
        shadowBlur: 1.0
        shadowScale: 1.0
        blurMax: T.px(40)
        z: -2
    }
    MultiEffect {
        source: pill
        anchors.fill: pill
        shadowEnabled: true
        shadowColor: T.shadowNear
        shadowVerticalOffset: T.px(4)
        shadowBlur: 1.0
        blurMax: T.px(8)
        z: -1
    }
}
