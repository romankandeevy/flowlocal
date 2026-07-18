// Пилюля-индикатор: загрузка / запись / распознавание / готово / ошибка.
//
// Это Qt-версия того, что overlay.py рисовал в PIL (этап 6 плана). Смысл
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
//
// ------- переделка 18.07.2026 -------
// Владелец: «слишком большая, слишком много текста, и не по центру». Всё три
// верно, и третье было настоящим багом - см. `pillWMax` в theme.py.
//
// Ориентир - Flow Bar у Wispr: капсула, внутри волна, подписей нет. Что ушло
// и почему:
//   подсказка «ещё раз - стоп · Esc - отмена»  - её читают один раз, а висит
//       она каждую диктовку. Про Esc написано на странице «Диктовка»
//   «микрофон: системный»                      - запись при этом идёт, то есть
//       это не отказ, а мелочь для лога
//   слово «распознаю»                          - о том, что идёт распознавание,
//       говорит само движение: волна оседает в ниточку и медленно дышит.
//       Читать при этом нечего
// Осталось то, что несёт смысл: точка «в эфире», волна, таймер, число слов в
// конце и текст ошибки. `hint` остался как канал для скачивания обновления -
// это единственная надпись, которую движением не выразить.

import QtQuick

Item {
    id: root
    // Ширина постоянная: капсула центрируется внутри окна, а окно не ездит.
    // Пока окно подгонялось под капсулу, смена состояния уводила пилюлю из
    // центра экрана - x ставился один раз при показе, а ширина потом росла.
    width: T.pillWMax + 2 * T.pillPad
    // Холст выше пилюли: тень уходит за её край, а места ей надо больше снизу,
    // чем сверху. Симметричное поле обрезало бы хвост, и на светлом фоне
    // появлялся горизонтальный шов - на этом уже обжигались, см. HANDOFF.
    height: T.pillH + T.pillPad + T.pillPadBottom

    // ------- вход из Python -------
    property string state_: "loading"     // loading|recording|processing|done|error
    property string message: ""
    property string hint: ""              // только скачивание обновления
    property real   seconds: 0
    property var    bars: []              // WAVE_BARS чисел 0..1
    property bool   shown: false
    property bool   silence: false        // запись идёт, а микрофон молчит
    // Есть ли Qt6QuickEffects.dll. Без него MultiEffect не просто не даёт
    // тени - он способен закрасить пилюлю чёрным прямоугольником. Тень это
    // украшение, пилюля - нет: рисуем её только когда эффект точно жив.
    property bool   shadowOk: true

    readonly property bool isRec: state_ === "recording"
    readonly property bool isProc: state_ === "processing"
    readonly property bool isLoading: state_ === "loading"
    // «Распознаю» - не отдельная картинка, а продолжение записи: волна тает
    // в ниточку на месте, вместо подмены на спиннер. Микро-тревога «оно
    // зависло?» после конца фразы - самая частая жалоба на такие приложения,
    // и отвечать на неё должно само движение, без чтения подписи. Оба
    // состояния поэтому показывает один и тот же ряд - recRow.
    readonly property bool isBusy: isRec || isProc
    // Только для labelRow: запись и распознавание сюда не заходят.
    readonly property color iconColor: state_ === "done"  ? T.success
                                     : state_ === "error" ? T.danger
                                                          : T.accent
    readonly property string label: isLoading ? "загружаю модель" : message

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
        // Центр окна, а не левый край: окно постоянной ширины, капсула дышит
        // внутри него симметрично в обе стороны.
        x: (root.width - width) / 2
        height: T.pillH
        radius: height / 2                    // --radius-full: пилюля есть пилюля
        color: T.paper
        // Волосяная линия вместо заливки - основной приём системы.
        border.width: 1
        border.color: T.border

        // Ширина зависит от состояния и от текста. Анимируем её той же кривой:
        // раньше это был кросс-фейд трёх нарезанных картинок.
        width: isBusy ? recRow.implicitWidth + 2 * T.px(12)
                      : labelRow.implicitWidth + 2 * T.px(12)
        Behavior on width { NumberAnimation { duration: T.durBase * 1000
                                              easing.type: Easing.Bezier
                                              easing.bezierCurve: T.easeOut } }

        // ------- содержимое: запись и распознавание -------
        Row {
            id: recRow
            anchors.centerIn: parent
            spacing: T.px(10)
            visible: isBusy
            opacity: isBusy ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: T.durFast * 1000 } }

            // Точка «в эфире». Зелёная, а не красная: в Korti зелёный - это
            // «успех/в эфире», а красный - ошибка. Мигать красным во время
            // нормальной диктовки значило бы врать. В «распознаю» точки нет
            // вовсе (visible, а не opacity): эфир кончился, а прозрачный элемент
            // Row всё равно держит spacing - и пилюля была бы шире.
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                visible: root.isRec
                width: T.px(7); height: width; radius: width / 2
                color: T.success
                // Пульс только прозрачностью: масштаб - это уже пружинка.
                SequentialAnimation on opacity {
                    running: root.isRec; loops: Animation.Infinite
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
                            // В «распознаю» волна оседает в ниточку - тот же
                            // элемент, только затихший, а не другая картинка.
                            height: root.isProc ? T.px(1.5)
                                    : Math.max(T.px(1.5),
                                       (index < root.bars.length ? root.bars[index] : 0)
                                       * wave.height)
                            color: T.ink
                            // Хвост слева гаснет - полоски будто уплывают за край.
                            opacity: 0.90 * Math.min(1.0, (index + 1) / (T.waveBars * 0.16))
                            Behavior on height { NumberAnimation {
                                duration: root.isProc ? T.durSlow * 1000 : 70 } }
                        }
                    }
                }
            }
            // Ниточка медленно дышит, пока модель думает, - видно, что жив.
            SequentialAnimation {
                running: root.isProc
                loops: Animation.Infinite
                onRunningChanged: if (!running) wave.opacity = 1
                NumberAnimation { target: wave; property: "opacity"
                                  from: 0.9; to: 0.35; duration: 900
                                  easing.type: Easing.InOutSine }
                NumberAnimation { target: wave; property: "opacity"
                                  from: 0.35; to: 0.9; duration: 900
                                  easing.type: Easing.InOutSine }
            }

            // Таймер моноширинный: это метаданные, голос терминала. Цифры
            // табличные, поэтому 0:09 -> 0:10 не дёргает вёрстку.
            //
            // В распознавании здесь пусто: волна легла в ниточку и дышит - это
            // и есть ответ на «что сейчас происходит». Единственное исключение
            // - скачивание обновления: его надписью не заменишь.
            Item {
                anchors.verticalCenter: parent.verticalCenter
                width: root.isProc ? (root.hint !== "" ? procLbl.implicitWidth : 0)
                                   : timerText.implicitWidth
                height: Math.max(timerText.implicitHeight, procLbl.implicitHeight)
                Behavior on width { NumberAnimation { duration: T.durBase * 1000
                                                      easing.type: Easing.Bezier
                                                      easing.bezierCurve: T.easeOut } }
                Text {
                    id: timerText
                    anchors.verticalCenter: parent.verticalCenter
                    opacity: root.isProc ? 0 : 1
                    Behavior on opacity { NumberAnimation { duration: T.durBase * 1000 } }
                    text: Math.floor(root.seconds / 60) + ":"
                          + ("0" + Math.floor(root.seconds % 60)).slice(-2)
                    font.family: T.mono; font.pixelSize: T.px(T.t2xs); font.weight: Font.Medium
                    color: T.textSecondary
                }
                Text {
                    id: procLbl
                    anchors.verticalCenter: parent.verticalCenter
                    opacity: root.isProc && root.hint !== "" ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: T.durBase * 1000 } }
                    text: root.hint
                    font.family: T.sans; font.pixelSize: T.px(T.t2xs); font.weight: Font.DemiBold
                    color: T.text
                }
            }

            // Молчащий микрофон - единственная надпись, которая на пилюле
            // осталась из подсказок, и она заслужила: пустая вставка после
            // диктовки в заглушенную гарнитуру запутывает сильнее всего, а
            // движением «микрофон не слышит» не покажешь - лежащая волна
            // выглядит ровно как тишина в комнате.
            Text {
                anchors.verticalCenter: parent.verticalCenter
                visible: root.isRec && root.silence
                text: "не слышу микрофон"
                font.family: T.sans; font.pixelSize: T.px(T.t2xs); font.weight: Font.Medium
                color: T.textMuted
            }
        }

        // ------- содержимое: остальные состояния -------
        Row {
            id: labelRow
            anchors.centerIn: parent
            spacing: T.px(8)
            visible: !isBusy
            opacity: isBusy ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: T.durFast * 1000 } }

            Item {
                width: T.px(14); height: T.px(14)     // иконка «в строку с текстом»
                anchors.verticalCenter: parent.verticalCenter

                // Спиннер Korti: кольцо с вырезанной четвертью, линейно, 0.6 с.
                // Только для загрузки модели: «распознаю» показывает recRow,
                // где волна тает в ниточку, - спиннер там был бы подменой.
                Canvas {
                    id: ring
                    anchors.fill: parent
                    visible: root.isLoading
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
                font.family: T.sans; font.pixelSize: T.px(T.t2xs); font.weight: Font.DemiBold
                // Текст статуса чернилами, цвет несёт иконка - как в Toast.
                // Исключение - ошибка: там красный и текст.
                color: state_ === "error" ? T.danger : T.text
            }
        }
    }

    // Тень одним слоем: на капсуле в 34 пикселя два слоя не различить, а
    // каждый MultiEffect - это ещё одна копия пилюли в графе отрисовки.
    //
    // Отдельным файлом через Loader, и это не украшательство архитектуры.
    // `import QtQuick.Effects` тянет Qt6QuickEffects.dll, а он грузится не
    // всегда (HANDOFF, грабли PySide6). Пока импорт стоял здесь, его падение
    // унесло бы весь Overlay.qml - то есть пилюлю целиком, ради тени. В
    // отдельном файле падает только тень, и Loader это переживает.
    Loader {
        anchors.fill: pill
        z: -1
        source: root.shadowOk ? "PillShadow.qml" : ""
        onLoaded: item.source = pill
    }
}
