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
//
// ------- задача 1 плана, 19.07.2026 -------
// Пилюля подросла с 34 до 44 (PILL_H), волна с ней заодно - смотрят на неё
// краем глаза, и мелкой ей быть нельзя. И появился живой счётчик слов: разбор
// на ходу - главная работа последних версий, а снаружи он был невидим совсем.
// Человек не знал, что его речь уже разбирается, пока он говорит. Теперь
// знает, и по-прежнему НЕ ВИДИТ самого текста - показ распознанного по ходу
// речи в плане прямо запрещён.

// Контролы лежат в соседней папке, поэтому импорт каталога: соседства,
// на котором QML находит типы сам, между windows/ и controls/ уже нет.
// Почему каталог, а не qmldir, - разобрано в windows/Settings.qml.
import QtQuick
import "../controls"

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
    // Слов разобрано на ходу. 0 - счётчика на пилюле нет вовсе: до первого
    // разобранного куска показывать нечего, а «0 слов» под запись выглядит
    // как обвинение.
    property int    words: 0
    property string wordsLabel: ""        // «23 слова», согласовано в Python
    // Доля выполнения 0..1, или -1 если считать нечего. Пока её не было,
    // скачивание обновления показывало ту же лежащую ниточку, что и
    // распознавание фразы: «обновление 0.4.2» и всё. Человек не знал ни
    // сколько ждать, ни идёт ли вообще что-нибудь - за 70 МБ картинка не
    // менялась ни разу.
    property real   progress: -1

    // Перетаскивание: QML говорит, на сколько сдвинуть окно, двигает Python
    // (overlay_qt.PillOverlay). Здесь окна нет и быть не должно - QML про
    // экраны и границы не знает, а прижимать пилюлю к краю надо.
    signal dragged(real dx, real dy)
    signal dragReset()
    // Где сидит капсула внутри окна - для попадания мышью. Читает Python.
    property rect capsule: Qt.rect(0, 0, 0, 0)
    readonly property bool hasProgress: isProc && progress >= 0
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
    // Сообщение тоже через словарь. До сих пор переводилось только «загружаю
    // модель», а всё, что приходит из app.py готовой строкой, оставалось
    // русским - при том что переводы этих строк в i18n.py лежат с самого
    // начала (раздел «пилюля и сообщения»). Незнакомая строка вернётся из t()
    // как есть, так что хуже не станет ни одной из них.
    readonly property string label: isLoading ? L.t("загружаю модель") : L.t(message)

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
        // Отдаём свои координаты наружу: по ним Python решает, попала мышь в
        // капсулу или в пустое поле под тень. Капсула дышит по ширине, поэтому
        // прямоугольник живой, а не посчитанный один раз.
        onXChanged: root.capsule = Qt.rect(x, y, width, height)
        onWidthChanged: root.capsule = Qt.rect(x, y, width, height)
        // Высота меняется реже (только со сменой масштаба монитора), но молча
        // разъехавшийся прямоугольник ловил бы мышь не там, где капсула, -
        // а искать пилюлю, которая не хватается, человек не станет.
        onHeightChanged: root.capsule = Qt.rect(x, y, width, height)
        Component.onCompleted: root.capsule = Qt.rect(x, y, width, height)
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

        // ------- перетаскивание -------
        //
        // «Пилюля должна перетаскиваться мышью, посмотри как у Wispr», -
        // сказал владелец. Мешало одно: окно оверлея объявлено прозрачным для
        // мыши целиком (WS_EX_TRANSPARENT), иначе поле под тень - полтораста
        // пикселей у края экрана - съедало бы чужие клики. Теперь прозрачность
        // решается не флагом на всё окно, а попаданием в капсулу: окно
        // отвечает на WM_NCHITTEST «меня здесь нет» везде, кроме этого
        // прямоугольника (overlay_qt._HitFilter).
        //
        // Курсор - «рука», а не «перетащить»: капсула не разделяет мир на
        // «схватить» и «отпустить», она просто едет за мышью.
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            property real grabX: 0
            property real grabY: 0
            onPressed: (m) => { grabX = m.x; grabY = m.y }
            onPositionChanged: (m) => {
                if (!pressed) return;
                // Двигаем ОКНО, а не капсулу внутри него: капсула центрирована
                // и на следующем же кадре вернулась бы на место.
                root.dragged(m.x - grabX, m.y - grabY);
            }
            // Двойной клик возвращает пилюлю на место. Без этого утащенную за
            // край пилюлю пришлось бы искать мышью по всему экрану, а она
            // маленькая.
            onDoubleClicked: root.dragReset()
        }

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
                width: T.px(9); height: width; radius: width / 2
                color: T.success
                // Пульс только прозрачностью: масштаб - это уже пружинка.
                //
                // 920 мс и InOutSine - ВНЕ трёх токенов, и это единственно
                // возможный выбор. Токены отмеряют ПЕРЕХОД: было одно, стало
                // другое, чем быстрее, тем лучше. Здесь ничего не меняется -
                // точка дышит, пока идёт запись, и у дыхания свой темп, около
                // вдоха. На 280 мс это уже не дыхание, а тревожное мигание, и
                // ease_out (быстрый старт, долгий выкат) в петле даёт рывок на
                // стыке - синус на то и синус, что стыка не видно.
                SequentialAnimation on opacity {
                    running: root.isRec; loops: Animation.Infinite
                    NumberAnimation { from: 0.45; to: 1.0; duration: 920
                                      easing.type: Easing.InOutSine }
                    NumberAnimation { from: 1.0; to: 0.45; duration: 920
                                      easing.type: Easing.InOutSine }
                }
            }

            // Полоса выполнения на месте осциллограммы: та же ширина, чтобы
            // пилюля не прыгала. Заливка акцентом - обновление в Korti как раз
            // «особенное», и той же краской подписана ссылка в панели.
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                visible: root.hasProgress
                width: T.waveW
                height: T.px(4)
                radius: height / 2
                color: T.fill
                Rectangle {
                    width: parent.width * Math.max(0, Math.min(1, root.progress))
                    height: parent.height
                    radius: parent.radius
                    color: T.accent
                    // Полоса догоняет плавно: скачки на 5% рывками читаются
                    // как подвисание, хотя всё идёт.
                    Behavior on width { NumberAnimation { duration: T.durBase * 1000
                                                          easing.type: Easing.Bezier
                                                          easing.bezierCurve: T.easeOut } }
                }
            }

            // Осциллограмма - чернила: это данные, а не статус, тонировать нечем.
            Row {
                id: wave
                anchors.verticalCenter: parent.verticalCenter
                visible: !root.hasProgress
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
                            // Пока пишем - полоски идут за голосом: половина
                            // быстрого токена (60 мс). Целых 120 уже читаются
                            // как задержка между словом и откликом, а
                            // осциллограмма тем и полезна, что не отстаёт. В
                            // распознавании голоса нет, и волна укладывается в
                            // ниточку общим долгим сроком.
                            Behavior on height { NumberAnimation {
                                duration: root.isProc ? T.durSlow * 1000
                                                      : T.durFast * 1000 / 2 } }
                        }
                    }
                }
            }
            // Ниточка медленно дышит, пока модель думает, - видно, что жив.
            // 900 мс мимо токенов по той же причине, что и точка записи выше:
            // это не переход, а признак жизни в ожидании, и темп у него свой.
            SequentialAnimation {
                running: root.isProc && !root.hasProgress
                loops: Animation.Infinite
                onRunningChanged: if (!running) wave.opacity = 1
                NumberAnimation { target: wave; property: "opacity"
                                  from: 0.9; to: 0.35; duration: 900
                                  easing.type: Easing.InOutSine }
                NumberAnimation { target: wave; property: "opacity"
                                  from: 0.35; to: 0.9; duration: 900
                                  easing.type: Easing.InOutSine }
            }

            // Метаданные записи: таймер и счётчик слов. Обе цифры - голос
            // терминала, поэтому таймер моноширинный, а вместе они читаются
            // одной строкой «0:12 · 23 слова», а не двумя надписями.
            //
            // В распознавании здесь пусто: волна легла в ниточку и дышит - это
            // и есть ответ на «что сейчас происходит». Единственное исключение
            // - скачивание обновления: его надписью не заменишь.
            Item {
                anchors.verticalCenter: parent.verticalCenter
                width: root.isProc ? (root.hint !== "" ? procLbl.implicitWidth : 0)
                                   : metaRow.implicitWidth
                height: Math.max(metaRow.implicitHeight, procLbl.implicitHeight)
                Behavior on width { NumberAnimation { duration: T.durBase * 1000
                                                      easing.type: Easing.Bezier
                                                      easing.bezierCurve: T.easeOut } }
                Row {
                    id: metaRow
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: T.px(6)
                    opacity: root.isProc ? 0 : 1
                    Behavior on opacity { NumberAnimation { duration: T.durBase * 1000 } }

                    Text {
                        id: timerText
                        anchors.verticalCenter: parent.verticalCenter
                        text: Math.floor(root.seconds / 60) + ":"
                              + ("0" + Math.floor(root.seconds % 60)).slice(-2)
                        font.family: T.mono; font.pixelSize: T.px(T.t2xs)
                        font.weight: Font.Medium
                        // Табличные цифры. У JetBrains Mono они такие и без
                        // просьбы, но семейство берётся по имени из системы, и
                        // если оно не встало - подменыш будет пропорциональным,
                        // а «0:09 -> 0:10» задёргает всю строку.
                        font.features: ({ "tnum": 1 })
                        color: T.textSecondary
                    }

                    // Счётчик слов - ответ на «оно вообще что-нибудь делает?».
                    // Пока человек говорит, программа уже разбирает сказанное,
                    // и до этой строки узнать об этом было неоткуда.
                    //
                    // Под тишину прячем, и не только ради ширины: «не слышу
                    // микрофон» и «23 слова» рядом противоречат друг другу, а
                    // верна в этот момент жалоба.
                    // Разделитель - отдельная надпись, а не первые два символа
                    // счётчика. Пока точка жила внутри строки («· » + подпись),
                    // отступ ей задавал пробел в тексте: величина, которой нет
                    // ни в токенах, ни в раскладке, и которая менялась бы со
                    // сменой шрифта. Теперь её место держит spacing ряда, как
                    // и у всех соседей, а цвет тот же, что у таймера, - точка
                    // принадлежит ему, а не счётчику.
                    Text {
                        id: wordsDot
                        anchors.verticalCenter: parent.verticalCenter
                        visible: wordsText.visible
                        text: "·"
                        font.family: T.sans; font.pixelSize: T.px(T.t2xs)
                        font.weight: Font.Medium
                        color: timerText.color
                    }

                    Text {
                        id: wordsText
                        anchors.verticalCenter: parent.verticalCenter
                        visible: root.isRec && root.words > 0 && !root.silence
                        text: root.wordsLabel
                        font.family: T.sans; font.pixelSize: T.px(T.t2xs)
                        font.weight: Font.Medium
                        color: T.textSecondary
                    }
                }
                Text {
                    id: procLbl
                    anchors.verticalCenter: parent.verticalCenter
                    opacity: root.isProc && root.hint !== "" ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: T.durBase * 1000 } }
                    text: root.hasProgress
                          ? root.hint + " · " + Math.round(root.progress * 100) + "%"
                          : root.hint
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
                text: L.t("не слышу микрофон")
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

            // «Готово» - единственное место, где системе разрешён масштаб.
            // Итог диктовки (галка и честное число вставленных слов) приходит
            // на смену волне, и без подъёма он просто подменяет собой картинку:
            // человек, смотревший краем глаза, момента не замечает вовсе.
            // 0.96 и ни каплей меньше - это кивок, а не прыжок; пружин нет.
            transformOrigin: Item.Center
            NumberAnimation {
                id: donePop
                target: labelRow; property: "scale"
                from: 0.96; to: 1.0
                duration: T.durBase * 1000
                easing.type: Easing.Bezier
                easing.bezierCurve: T.easeOut
            }
            Connections {
                target: root
                function onState_Changed() {
                    if (root.state_ === "done")
                        donePop.restart();
                }
            }

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
                        // 600 мс мимо трёх токенов - но НЕ мимо системы: это
                        // отдельный токен Korti --spin (.6s linear), у бегунка
                        // он свой. Оборот - петля, а не переход: ease_out
                        // тормозил бы кольцо на каждом круге, поэтому linear.
                        from: 0; to: 360; duration: 600
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

    // Тень одним слоем: на капсуле такого размера два слоя не различить, а
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
        source: root.shadowOk ? "../controls/PillShadow.qml" : ""
        onLoaded: item.source = pill
    }
}
