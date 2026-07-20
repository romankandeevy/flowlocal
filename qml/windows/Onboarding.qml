// Мастер первого запуска: девять шагов (PLAN, задача 7).
// Данные - в onboarding_qt (`B` - настроечный Backend, `OB` - живой звук,
// проба, финиш). Токены - `T`, один источник правды.
//
// Правило этого файла: на каждом экране человеку есть что СДЕЛАТЬ, и на это
// что-то отвечает. Программа про «нажал - сказал - готово», и мастер, который
// про неё рассказывает неподвижным текстом, обещает не то, что дальше будет.

// Контролы лежат в соседней папке, поэтому импорт каталога: соседства,
// на котором QML находит типы сам, между windows/ и controls/ уже нет.
// Почему каталог, а не qmldir, - разобрано в windows/Settings.qml.
import QtQuick
import "../controls"

Rectangle {
    id: wiz
    color: T.bg
    property int step: 0
    readonly property int last: 8

    // Откуда пришли: вперёд содержимое въезжает справа, назад - слева. Само по
    // себе движение маленькое, но без него «Назад» и «Дальше» выглядят
    // одинаково, и человек теряет, в какую сторону он идёт.
    property int prevStep: 0
    onStepChanged: {
        stepSlide.from = step >= prevStep ? 8 : -8;
        prevStep = step;
        stepIn.restart();
        // Фокус обратно на мастер: поле проверки вставки забирает его себе и
        // после шага не отдаёт, а без фокуса Enter перестаёт вести вперёд.
        wiz.forceActiveFocus();
        // Слежку за живым нажатием переключаем здесь, из одного места - см.
        // syncHotkeyWatch, там же и почему не в onVisibleChanged экранов.
        wiz.syncHotkeyWatch();
    }

    // Enter ведёт вперёд. Мастер - это девять нажатий подряд, и рука уже лежит
    // на клавиатуре: в мастере, который учит нажимать клавиши, тянуться за
    // мышью ради «Дальше» странно.
    focus: true
    Keys.onReturnPressed: wiz.advance()
    Keys.onEnterPressed: wiz.advance()

    function advance() {
        if (!nextBtn.enabled)
            return;
        nextBtn.clicked();
    }

    // Умолчание для второго жеста (toggle). В конфиге он пуст по замыслу -
    // жест необязательный. Но экран B обязан что-то показать и проверить
    // живьём, поэтому одно сочетание мы предлагаем.
    //
    // Почему ctrl+shift+d, а не боковая кнопка мыши: экран заставляет жест
    // ВЫПОЛНИТЬ, пока не выполнил - «Дальше» заперта. Значит умолчание должно
    // нажиматься на ЛЮБОЙ машине. Боковой кнопки у отца и друзей - тех, для
    // кого программа, - может не быть вовсе (ноутбук, трекпад), и человек
    // застрял бы на пустом жесте. Клавиши есть у всех. С удержанием
    // (ctrl+shift+space) не конфликтует, буква d - от «диктовки». Кто хочет
    // мышь - назначит её тут же полем захвата.
    readonly property string toggleDefault: "ctrl+shift+d"

    // Слежка за живым нажатием - из одного места, по номеру шага.
    //
    // Раньше это жило в onVisibleChanged самого экрана, и с одним экраном
    // жестов работало. С двумя - ломается: при «Назад» visible-сигналы двух
    // экранов приходят в порядке их объявления, а не в порядке «сначала сними
    // старое, потом взведи новое». Экран, на который возвращаешься, успевал
    // взвести слежку, а уходящий тут же снимал её вместе с хоткеями -
    // программа оставалась немой. Здесь хозяин один и хук ровно один за раз.
    function syncHotkeyWatch() {
        if (wiz.step === 4) {
            hkStep.spec = B.get("hotkey_hold") || "";
            hkStep.down = [];
            hkStep.lit = false;
            OB.watchHotkey(hkStep.spec);
        } else if (wiz.step === 5) {
            // Умолчание предлагаем ЛОКАЛЬНО, в конфиг не пишем: пока человек не
            // доказал жест и не нажал «Дальше», навязывать ему сочетание
            // нечестно. В конфиг оно ляжет на «Дальше» (или пустота - на «Мне
            // хватит одного»).
            var cur = B.get("hotkey_toggle") || "";
            if (cur === "" && !toggleStep.skipped)
                cur = wiz.toggleDefault;
            toggleStep.spec = cur;
            toggleStep.down = [];
            toggleStep.lit = false;
            // Поле захвата читает конфиг лишь при создании и про наше умолчание
            // не знает - иначе плашки показывали бы сочетание, а поле «не
            // назначено». Держим их на одном значении руками.
            toggleField.value = cur;
            toggleField.pretty = B.pretty(cur);
            OB.watchHotkey(cur);
        } else {
            OB.unwatchHotkey();
        }
    }

    // Иконки на весь мастер одним объектом: QtObject, места не занимает.
    Icons { id: ic }

    // Модель, которую выбрал шаг 2. По умолчанию - рекомендация для русского.
    property string chosenModel: OB.recommended()
    property bool modelReady: false
    property real dlFrac: 0
    property bool downloading: false

    function refreshModelState() {
        var list = B.modelsInfo();
        for (var i = 0; i < list.length; i++)
            if (list[i].id === chosenModel) {
                modelReady = list[i].installed;
                downloading = list[i].downloading;
                return;
            }
        modelReady = false;
    }
    onChosenModelChanged: refreshModelState()
    Component.onCompleted: refreshModelState()
    Connections {
        target: B
        function onModelsChanged() { wiz.refreshModelState() }
        function onModelProgress(id, f) { if (id === wiz.chosenModel) wiz.dlFrac = f }
    }

    // ---------- шапка: точки прогресса ----------
    //
    // Девять точек честно говорят «это длинно», и это работает против нас. Разбор
    // онбординга Wispr Flow (Kristen Berman, «8 lessons») отмечает ровно это:
    // человек охотнее идёт дальше, когда знает, что осталось немного, чем когда
    // видит полную длину пути. Поэтому к точкам добавлена подпись, и появляется
    // она только под конец - там, где иначе хочется бросить.
    Column {
        id: dots
        anchors { top: parent.top; topMargin: 24; horizontalCenter: parent.horizontalCenter }
        spacing: 8

        // Точки одни на все девять экранов - один Repeater, никаких копий по
        // шагам. Крупнее прежних (8 -> 10) и с тремя состояниями вместо двух:
        // пройденное, текущее, будущее. Раньше пройденное и текущее красились
        // одинаково, и ряд отвечал только на «сколько всего», а на «где я» -
        // нет; ровно это владелец и назвал «не видно, на каком шаге».
        //
        // Текущий шаг - не точка, а короткая полоска: форма читается боковым
        // зрением, а оттенок в ряду одинаковых кружков - нет. Она же и есть
        // отклик на «Дальше»: полоска переезжает, точки перекрашиваются.
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 8
            Repeater {
                model: wiz.last + 1
                Rectangle {
                    width: index === wiz.step ? 24 : 10
                    height: 10
                    // --radius-full: и точка, и полоска - пилюли, поэтому
                    // радиус от высоты, а не числом. 5 читалось магией.
                    radius: height / 2
                    color: index === wiz.step ? T.ink
                         : index < wiz.step ? T.inkA(0.34)
                         : T.fillStrong
                    Behavior on width { NumberAnimation { duration: T.durBase * 1000
                                                          easing.type: Easing.Bezier
                                                          easing.bezierCurve: T.easeOut } }
                    Behavior on color { ColorAnimation { duration: T.durBase * 1000 } }
                }
            }
        }
        // Номер шага словами, а не только точками.
        //
        // Точки говорят «сколько всего» и «где-то тут», но не отвечают на
        // вопрос «на каком я». Владелец сказал прямо: не видно, где
        // находишься. Девять точек по 8 пикселей глазом не пересчитываются -
        // это работа, а не подсказка.
        //
        // К концу пути подпись меняется на «почти готово» и «последний шаг»:
        // там важнее не номер, а то, что осталось немного. Ровно то, ради
        // чего подпись и заводилась.
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: wiz.step === wiz.last ? L.t("последний шаг")
                : wiz.step === wiz.last - 1 ? L.t("почти готово")
                : L.t("шаг ") + (wiz.step + 1) + L.t(" из ") + (wiz.last + 1)
            font.family: T.sans; font.pixelSize: T.t2xs
            color: T.textMuted
        }
    }

    // ---------- содержимое шагов ----------
    //
    // Прокрутка нужна не «на всякий случай». Окно у мастера маленькое (640x560),
    // а шаги разной высоты: у одного заголовок и кнопка, у другого выбор темы,
    // образец настроек и объяснение. Пока содержимое лезло за край, оно
    // наезжало на «Назад» и «Дальше» - кнопки оказывались ПОД текстом, и это
    // ровно то, что владелец описал как «нажал переключатель, всё пропало».
    //
    // Высоту считаем по видимому шагу, а не по самому высокому: иначе на
    // коротких экранах прокручивалась бы пустота, а полоса намекала бы, что
    // внизу что-то есть.
    Flickable {
        id: scroll
        anchors { top: dots.bottom; left: parent.left; right: parent.right
                  bottom: footer.top; margins: 32 }
        clip: true
        contentHeight: {
            var h = 0;
            for (var i = 0; i < steps.children.length; i++) {
                var c = steps.children[i];
                if (c.visible) h = Math.max(h, c.implicitHeight);
            }
            return h + 8;
        }
        interactive: contentHeight > height
        // Новый шаг - с начала: прокрутка одного не должна доставаться другому.
        onContentHeightChanged: contentY = 0

    Item {
        id: steps
        width: scroll.width
        height: scroll.contentHeight

        // Вход шага: короткий фейд со сдвигом на 8 px в ту сторону, откуда
        // пришли. Всё из токенов - T.durBase и ease_out, ничего своего.
        transform: Translate { id: stepShift }

        ParallelAnimation {
            id: stepIn
            NumberAnimation {
                target: steps; property: "opacity"; from: 0; to: 1
                duration: T.durBase * 1000
                easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut
            }
            NumberAnimation {
                id: stepSlide
                target: stepShift; property: "x"; from: 8; to: 0
                duration: T.durBase * 1000
                easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut
            }
        }

        // Заголовок каждого шага стоит на ОДНОЙ высоте: шаги привязаны к верху,
        // а не центрируются по вертикали.
        //
        // Раньше центрировались, и выглядело это так: блоки у шагов разной
        // высоты, поэтому заголовок прыгал вверх-вниз на каждое «Дальше». Глазу
        // приходилось заново искать, где начинается текст, - и так восемь раз
        // подряд. Мелочь, которой не замечаешь, пока не положишь два экрана
        // рядом, и от которой мастер кажется дёрганым.
        //
        // Приветствие - осознанное исключение: там один знак и одна фраза,
        // прижимать их к верху не к чему, они и должны стоять посередине.

        // === 0. Привет ===
        Column {
            id: helloStep
            visible: wiz.step === 0
            anchors.centerIn: parent
            spacing: 24
            width: parent.width
            // Знак, а не голое имя: это первое, что человек видит от программы,
            // и стена текста на белом - плохое первое впечатление для приложения,
            // которое дальше показывает себя аккуратным. Тот же вордмарк, что в
            // панели настроек, только крупный.
            //
            // И он отзывается на касание: наводка приподнимает знак, нажатие -
            // кивок 0.96 -> 1.0, тот же, которым пилюля говорит «готово». На
            // этом экране человеку больше нечего трогать, кроме одной кнопки,
            // а первое, к чему тянется мышь, - самое крупное на экране. Пусть
            // оно отвечает: программа про отклик, и говорить об этом надо с
            // первого экрана.
            Item {
                anchors.horizontalCenter: parent.horizontalCenter
                width: hello.width; height: hello.height

                Wordmark {
                    id: hello
                    box: 44
                    nameSize: T.tDisplay
                    scale: helloMa.pressed ? 0.96 : helloMa.containsMouse ? 1.02 : 1
                    Behavior on scale { NumberAnimation { duration: T.durBase * 1000
                                                          easing.type: Easing.Bezier
                                                          easing.bezierCurve: T.easeOut } }
                }
                MouseArea {
                    id: helloMa
                    anchors.fill: parent
                    hoverEnabled: true
                }
            }
            // Обещание в три коротких такта - крупной строкой, ритмом из
            // README: коротко, действием, без восклицаний. Дисплейный кегль
            // (крупнее заголовков шагов), но вес DemiBold, а не Bold вордмарка
            // над ним: строка звучит спокойно, не спорит с именем за внимание.
            Column {
                width: parent.width
                spacing: 16
                PageTitle {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: L.t("Зажали. Сказали. Отпустили.")
                    font.pixelSize: T.tDisplay
                    font.weight: Font.DemiBold
                }
                // Под обещанием, тише: куда денется текст. Вторичный цвет и
                // основной кегль - это подсказка, а не второй заголовок.
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: L.t("Текст уже в том окне, где курсор")
                    font.family: T.sans; font.pixelSize: T.tMd
                    color: T.textSecondary
                }
            }
            // Приватность - тише всех: мелко и спокойно, отдельной строкой на
            // расстоянии. Обещание вполголоса, ему не нужен ни кегль, ни цвет
            // заголовка - только чтобы его прочли и пошли дальше.
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.min(parent.width, 420)
                horizontalAlignment: Text.AlignHCenter
                text: L.t("Звук и текст не покидают этот компьютер.")
                wrapMode: Text.WordWrap
                font.family: T.sans; font.pixelSize: T.tSm
                color: T.textMuted
                lineHeight: 1.35
            }
        }

        // === 1. Как это выглядит ===
        //
        // Вторым экраном намеренно: дальше человек проходит ещё пять шагов и
        // видит их уже в своём оформлении. Спросить об этом в конце значило бы
        // показать мастер дважды - один раз чужим, один раз своим.
        Column {
            visible: wiz.step === 1
            anchors.top: parent.top
            width: parent.width
            spacing: 16

            PageTitle {
                text: L.t("Как вам удобнее?")
                font.pixelSize: T.tXl
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: L.t("Это можно поменять когда угодно, в настройках.")
                font.family: T.sans; font.pixelSize: T.tSm; color: T.textMuted
            }

            Item { width: 1; height: 4 }

            Text {
                text: L.t("ЦВЕТА")
                font.family: T.sans; font.pixelSize: T.t2xs
                font.weight: Font.DemiBold; font.letterSpacing: 0.6
                color: T.textFaint
            }
            Segmented {
                options: [{label: L.t("как в системе"), value: "system"},
                          {label: L.t("светлая"), value: "light"},
                          {label: L.t("тёмная"), value: "dark"}]
                value: B.get("theme") || "system"
                onPicked: (v) => B.set("theme", v)
            }

            Item { width: 1; height: 8 }

            // Было «РАСПОЛОЖЕНИЕ: карточками / строками». Владелец спросил
            // «расположение чего?» - и правильно спросил: ничего никуда не
            // переставляется, меняется только фон под настройками. Так же
            // называется и в самих настройках, одними словами.
            Text {
                text: L.t("ФОН ПОД НАСТРОЙКАМИ")
                font.family: T.sans; font.pixelSize: T.t2xs
                font.weight: Font.DemiBold; font.letterSpacing: 0.6
                color: T.textFaint
            }
            Segmented {
                options: [{label: L.t("есть"), value: "cards"},
                          {label: L.t("нет"), value: "lines"}]
                value: B.get("layout") || "cards"
                onPicked: (v) => B.set("layout", v)
            }

            // Показываем разницу тут же, а не описываем словами: «с фоном» и
            // «без фона» человеку ничего не говорят, пока он их не увидел.
            //
            // И подписываем, что это образец. Раньше здесь просто стояли две
            // настройки без объяснения, и владелец спросил, зачем этот блок
            // вообще нужен: он выглядел как настоящие настройки, которые
            // почему-то ничего не делают.
            Item { width: 1; height: 6 }
            Text {
                text: L.t("Образец - чтобы увидеть разницу. Эти два переключателя ни на что не влияют:")
                width: parent.width
                wrapMode: Text.WordWrap
                font.family: T.sans; font.pixelSize: T.tSm
                color: T.textMuted
            }
            Card {
                width: parent.width
                Item {
                    width: parent.width
                    implicitHeight: demoCol.implicitHeight + 16
                    Column {
                        id: demoCol
                        width: parent.width
                        SettingRow {
                            first: true
                            title: L.t("Так выглядит настройка")
                            subtitle: L.t("А так - пояснение под ней")
                            Toggle {
                                id: demoOne
                                value: true
                                // Живой, а не мёртвый: неподвижный образец не
                                // показывает главного - что переключение
                                // ВИДНО. Ровно этого владелец и не увидел в
                                // тёмной теме.
                                onToggled: (v) => demoOne.value = v
                            }
                        }
                        SettingRow {
                            title: L.t("И следующая за ней")
                            subtitle: L.t("Разделены линией в обоих видах")
                            Toggle {
                                id: demoTwo
                                value: false
                                onToggled: (v) => demoTwo.value = v
                            }
                        }
                    }
                }
            }
        }

        // Выбора модели на этом шаге больше нет.
        //
        // Был выбор языка - «русский» против «русский и другие», - и за ним
        // стояли две разные модели. Многоязычных моделей в каталоге не
        // осталось: программа про русский, и выбирать не из чего. А выбор,
        // где вариант один, - это не выбор, а лишний экран.
        //
        // Шаг остался, потому что делает главное: качает модель. Без неё
        // диктовка не работает вовсе, и человек должен видеть, что качается и
        // сколько осталось.

        // === 2. Модель ===
        Column {
            id: modelStep
            visible: wiz.step === 2
            anchors.top: parent.top
            width: parent.width
            spacing: 12
            PageTitle {
                text: wiz.modelReady ? L.t("Модель на месте") : L.t("Скачаем модель")
                font.pixelSize: T.tXl
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: wiz.modelReady
                      ? L.t("Она уже на этом компьютере. Дальше интернет для распознавания не нужен.")
                      : L.t("Это то, что превращает вашу речь в текст. Она работает прямо ")
                        + L.t("здесь, поэтому её надо принести целиком - один раз.")
                font.family: T.sans; font.pixelSize: T.tSm; color: T.textMuted
                lineHeight: 1.4
            }

            // Экран был пустым: заголовок, одна строка про мегабайты - и всё.
            // Владелец назвал это абсурдом, и он прав: человека просят подождать
            // несколько минут и ничего не говорят о том, чего он ждёт.
            //
            // Три строки отвечают на три настоящих вопроса: сколько ждать, что
            // будет потом и не уедет ли что-нибудь наружу.
            Item { width: 1; height: 4; visible: !wiz.modelReady }
            Column {
                visible: !wiz.modelReady
                width: parent.width
                spacing: 8
                Repeater {
                    model: [
                        {t: L.t("236 МБ, две-три минуты"),
                         s: L.t("Скачивается один раз. Дальше не понадобится")},
                        {t: L.t("Дальше - без интернета"),
                         s: L.t("Распознавание идёт на этом компьютере, в самолёте и на даче тоже")},
                        {t: L.t("Видеокарта не нужна"),
                         s: L.t("Хватает обычного процессора: 8 секунд речи - меньше секунды работы")}
                    ]
                    Row {
                        spacing: 12
                        width: parent.width
                        Rectangle {
                            width: 5; height: 5; radius: 2.5; y: 7
                            color: T.textFaint
                        }
                        Column {
                            spacing: 4
                            width: parent.width - 15
                            Text {
                                text: modelData.t
                                font.family: T.sans; font.pixelSize: T.tSm
                                font.weight: Font.Medium; color: T.text
                            }
                            Text {
                                width: parent.width
                                wrapMode: Text.WordWrap
                                text: modelData.s
                                font.family: T.sans; font.pixelSize: T.tSm
                                color: T.textMuted
                            }
                        }
                    }
                }
            }

            // Прогресс скачивания: полоса плюс проценты словами. Без числа
            // полоса на 236 мегабайтах выглядит замершей - «зависло», сказал
            // владелец, и по одной полосе отличить это было невозможно.
            Item { width: 1; height: 4; visible: wiz.downloading }
            Column {
                visible: wiz.downloading
                width: parent.width
                spacing: 8
                Item {
                    width: parent.width; height: 8
                    Rectangle { anchors.verticalCenter: parent.verticalCenter
                                width: parent.width; height: 4; radius: 2; color: T.fillStrong }
                    Rectangle { anchors.verticalCenter: parent.verticalCenter
                                width: parent.width * wiz.dlFrac; height: 4; radius: 2
                                color: T.accent
                                // Полоса догоняет самым долгим сроком системы:
                                // проценты приходят редкими скачками, и рывок
                                // на них читается как подвисание.
                                Behavior on width {
                                    NumberAnimation { duration: T.durSlow * 1000
                                                      easing.type: Easing.Bezier
                                                      easing.bezierCurve: T.easeOut } } }
                }
                Text {
                    text: Math.round(wiz.dlFrac * 100) + L.t("% · качается, можно не смотреть")
                    font.family: T.sans; font.pixelSize: T.tSm; color: T.textMuted
                }
            }
            // Конец скачивания - единственный момент этого экрана, которого
            // человек действительно ждёт, и раньше он проходил молча: полоса
            // исчезала, строка появлялась. Теперь галка проявляется тем же
            // кивком, каким пилюля говорит «готово», - ответ на пять минут
            // ожидания должен быть виден.
            Row {
                id: modelDone
                visible: wiz.modelReady
                spacing: 8
                opacity: 0
                scale: 0.96
                onVisibleChanged: if (visible) modelPop.restart()
                Component.onCompleted: if (visible) modelPop.restart()

                ParallelAnimation {
                    id: modelPop
                    NumberAnimation { target: modelDone; property: "opacity"; from: 0; to: 1
                                      duration: T.durSlow * 1000
                                      easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut }
                    NumberAnimation { target: modelDone; property: "scale"; from: 0.96; to: 1
                                      duration: T.durSlow * 1000
                                      easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut }
                }

                Icon {
                    anchors.verticalCenter: parent.verticalCenter
                    path: ic.check; size: 16; color: T.success; weight: 2.2
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: L.t("Уже скачано - можно дальше.")
                    font.family: T.sans; font.pixelSize: T.tSm; color: T.success
                }
            }
        }

        // === 3. Микрофон ===
        //
        // Волна тут в полтора раза выше остальных (96 против прежних 64) и
        // занимает почти весь экран под выбором устройства. Это не украшение:
        // единственный экран мастера, который отвечает на голос, и главный
        // живой момент всего знакомства. Мелкая волна под абзацем текста
        // читалась как индикатор, а она - доказательство, что программа слышит.
        Column {
            id: micStep
            visible: wiz.step === 3
            anchors.top: parent.top
            width: parent.width
            spacing: 12
            PageTitle {
                text: L.t("Микрофон")
                font.pixelSize: T.tXl
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                text: L.t("Скажите что-нибудь - волна должна ожить. Если лежит ровно, выберите другой микрофон.")
                wrapMode: Text.WordWrap
                font.family: T.sans; font.pixelSize: T.tSm; color: T.textMuted
            }
            Select {
                options: B.micOptions
                value: B.get("mic_device")
                onPicked: (v) => B.set("mic_device", v)
            }
            // Живая волна - чернила, как в оверлее: данные, а не статус.
            Rectangle {
                width: parent.width; height: 132
                radius: T.radiusLg; color: T.paper
                border.width: 1; border.color: T.border
                WaveMeter {
                    id: micWave
                    anchors.centerIn: parent
                    running: wiz.step === 3 && wiz.visible
                    bars: 40; barW: 5; gap: 3; maxH: 96
                }
            }
            // Слово к волне. Форму волны человек видит, но вывод из неё делает
            // не сразу: «ровно» и «чуть шевелится» на глаз похожи, а решение
            // на этом экране принимается одно - тот микрофон или не тот.
            Row {
                spacing: 8
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 8; height: 8; radius: 4
                    color: micWave.peak > 0.45 ? T.success : T.textFaint
                    Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: micWave.peak > 0.45 ? L.t("слышу вас")
                                              : L.t("тихо - скажите что-нибудь")
                    font.family: T.sans; font.pixelSize: T.tSm
                    color: micWave.peak > 0.45 ? T.success : T.textMuted
                    Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
                }
            }
        }

        // === 4. Главный жест: зажать и говорить ===
        //
        // Здесь человеку называют клавиши, которыми он будет пользоваться
        // каждый день, - и до сих пор не давали их попробовать: поле захвата
        // отвечало на клик мышью, а на само нажатие не отвечало ничем.
        //
        // Теперь плашки живые. Зажал Ctrl - утонула одна, добавил Shift -
        // вторая, собрал сочетание целиком - загорелись все. Проверка идёт тем
        // же движением, каким потом диктуют, и до первой настоящей диктовки
        // человек уже знает: программа его слышит.
        Column {
            id: hkStep
            visible: wiz.step === 4
            anchors.top: parent.top
            width: parent.width
            spacing: 12

            property string spec: ""
            property var down: []
            property bool lit: false
            // Жест доказан живьём: lit был true хотя бы раз. Латч - не гаснет,
            // когда человек отпустил клавиши, и переживает уход на соседний
            // экран и обратно. Ровно он отпирает «Дальше». Сбрасывается только
            // сменой сочетания (captureDone): новое надо доказать заново.
            property bool verified: false

            // Слежку взводит и снимает wiz.syncHotkeyWatch по номеру шага -
            // здесь только приём состояния. Почему не в onVisibleChanged
            // экрана - разобрано в syncHotkeyWatch.
            Connections {
                target: OB
                function onComboState(down, lit) {
                    if (!hkStep.visible) return;
                    hkStep.down = down;
                    hkStep.lit = lit;
                    if (lit) hkStep.verified = true;
                }
            }
            Connections {
                target: B
                function onCaptureDone(f, spec) {
                    if (f !== "hotkey_hold" || !hkStep.visible) return;
                    // Сочетание сменили - доказательство обнуляем и перевзводим
                    // слежку под новый spec (заодно она заберёт назад снятые
                    // захватом хоткеи приложения, иначе нажатие ушло бы в
                    // настоящую диктовку).
                    hkStep.verified = false;
                    wiz.syncHotkeyWatch();
                }
            }

            PageTitle {
                text: L.t("Главный жест: зажать и говорить")
                font.pixelSize: T.tXl
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                text: L.t("Зажали - говорите, отпустили - вставилось. Нажмите сочетание прямо сейчас - плашки отзовутся.")
                wrapMode: Text.WordWrap
                font.family: T.sans; font.pixelSize: T.tSm; color: T.textMuted
            }

            Rectangle {
                width: parent.width
                height: 116
                radius: T.radiusLg
                color: T.paper
                border.width: 1
                // Зелёная и на живом нажатии (lit), и после того как жест уже
                // доказан (verified): рамка-подтверждение не должна гаснуть,
                // стоит отпустить клавиши.
                border.color: (hkStep.lit || hkStep.verified) ? T.success : T.border
                Behavior on border.color { ColorAnimation { duration: T.durFast * 1000 } }

                Column {
                    anchors { left: parent.left; right: parent.right
                              verticalCenter: parent.verticalCenter
                              leftMargin: 16; rightMargin: 16 }
                    spacing: 12

                    // Пустое сочетание - законное состояние: во время захвата
                    // Backspace его стирает. Плашки тогда не рисуем вовсе,
                    // иначе `pretty` отдал бы «не задано», и это встало бы
                    // отдельной клавишей.
                    KeyCaps {
                        width: parent.width
                        visible: hkStep.spec !== ""
                        combo: B.pretty(hkStep.spec)
                        // Крупнее, чем в главном окне: там сочетание вспоминают
                        // мельком, здесь по нему бьют пальцем.
                        keySize: T.tXl
                        down: hkStep.down
                        lit: hkStep.lit
                    }
                    // Подпись состояния. Доказанный жест - галка и зелёное
                    // «Работает»: это и есть условие, отпершее «Дальше», человек
                    // должен видеть, что именно он выполнил.
                    Row {
                        width: parent.width
                        spacing: 6
                        Icon {
                            id: hkOkMark
                            visible: hkStep.verified
                            y: 1
                            path: ic.check; size: 15; color: T.success; weight: 2.2
                        }
                        Text {
                            width: parent.width - (hkOkMark.visible ? hkOkMark.width + parent.spacing : 0)
                            text: hkStep.verified ? L.t("Работает - так и диктуйте")
                                : hkStep.spec === "" ? L.t("Сочетание не назначено - задайте его ниже")
                                : L.t("Зажмите и подержите - проверим, что срабатывает")
                            wrapMode: Text.WordWrap
                            font.family: T.sans; font.pixelSize: T.tSm
                            color: hkStep.verified ? T.success : T.textFaint
                            Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
                        }
                    }
                }
            }

            // Смена сочетания - вторым действием и с подписью. Само поле
            // осталось прежним: захват в нём уже устроен и проверен.
            Text {
                text: L.t("ПОМЕНЯТЬ")
                font.family: T.sans; font.pixelSize: T.t2xs
                font.weight: Font.DemiBold; font.letterSpacing: 0.6
                color: T.textFaint
            }
            HotkeyField { field: "hotkey_hold" }
            Text {
                width: parent.width
                text: L.t("Кликните по полю и нажмите своё - подойдёт и боковая кнопка мыши. Дальше настроим второй жест: нажал один раз и говоришь со свободными руками.")
                wrapMode: Text.WordWrap
                font.family: T.sans; font.pixelSize: T.t2xs; color: T.textFaint
            }
        }

        // === 5. Второй жест: нажать один раз ===
        //
        // Отдельным экраном, а не строкой в настройках: владелец просил не
        // просто назвать второй жест, а заставить его ВЫПОЛНИТЬ - иначе человек
        // заводит сочетание и не знает, срабатывает ли оно. Устройство - как у
        // главного жеста: живые плашки, поле захвата, зелёная галка на
        // доказанном. Разница одна и важная: жест необязателен, и на экране
        // есть явный выход «Мне хватит одного» - навязывать второе сочетание
        // тому, кому хватает первого, нечестно.
        Column {
            id: toggleStep
            visible: wiz.step === 5
            anchors.top: parent.top
            width: parent.width
            spacing: 12

            property string spec: ""
            property var down: []
            property bool lit: false
            property bool verified: false
            // Осознанный отказ от второго жеста. Латч: снимает требование
            // проверки и пускает дальше с пустым hotkey_toggle. Сбрасывается,
            // если человек всё же назначит сочетание полем захвата.
            property bool skipped: false

            // Слежку взводит wiz.syncHotkeyWatch - здесь только приём.
            Connections {
                target: OB
                function onComboState(down, lit) {
                    if (!toggleStep.visible) return;
                    toggleStep.down = down;
                    toggleStep.lit = lit;
                    if (lit) toggleStep.verified = true;
                }
            }
            Connections {
                target: B
                function onCaptureDone(f, spec) {
                    if (f !== "hotkey_toggle" || !toggleStep.visible) return;
                    // Назначил своё - значит жест ему нужен: отказ снимаем,
                    // доказательство обнуляем, слежку взводим под новый spec.
                    toggleStep.skipped = false;
                    toggleStep.verified = false;
                    wiz.syncHotkeyWatch();
                }
            }

            PageTitle {
                text: L.t("Второй жест: нажать один раз")
                font.pixelSize: T.tXl
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                text: L.t("Нажали один раз - пошла запись, нажали ещё раз - остановилась. Удобно, когда руки заняты, а сказать надо много.")
                wrapMode: Text.WordWrap
                font.family: T.sans; font.pixelSize: T.tSm; color: T.textMuted
            }

            Rectangle {
                width: parent.width
                height: 116
                radius: T.radiusLg
                color: T.paper
                border.width: 1
                border.color: (toggleStep.lit || toggleStep.verified) ? T.success : T.border
                Behavior on border.color { ColorAnimation { duration: T.durFast * 1000 } }

                Column {
                    anchors { left: parent.left; right: parent.right
                              verticalCenter: parent.verticalCenter
                              leftMargin: 16; rightMargin: 16 }
                    spacing: 12

                    KeyCaps {
                        width: parent.width
                        visible: toggleStep.spec !== ""
                        combo: B.pretty(toggleStep.spec)
                        keySize: T.tXl
                        down: toggleStep.down
                        lit: toggleStep.lit
                    }
                    Row {
                        width: parent.width
                        spacing: 6
                        Icon {
                            id: tgOkMark
                            visible: toggleStep.verified
                            y: 1
                            path: ic.check; size: 15; color: T.success; weight: 2.2
                        }
                        Text {
                            width: parent.width - (tgOkMark.visible ? tgOkMark.width + parent.spacing : 0)
                            text: toggleStep.verified ? L.t("Работает - этим и включайте")
                                : toggleStep.spec === "" ? L.t("Сочетание не назначено - задайте его ниже")
                                : L.t("Нажмите это сочетание - проверим, что срабатывает")
                            wrapMode: Text.WordWrap
                            font.family: T.sans; font.pixelSize: T.tSm
                            color: toggleStep.verified ? T.success : T.textFaint
                            Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
                        }
                    }
                }
            }

            Text {
                text: L.t("ПОМЕНЯТЬ")
                font.family: T.sans; font.pixelSize: T.t2xs
                font.weight: Font.DemiBold; font.letterSpacing: 0.6
                color: T.textFaint
            }
            HotkeyField { id: toggleField; field: "hotkey_toggle" }
            Text {
                width: parent.width
                text: L.t("Предложили сочетание, которое есть на любой клавиатуре. Можно оставить, поменять или назначить боковую кнопку мыши.")
                wrapMode: Text.WordWrap
                font.family: T.sans; font.pixelSize: T.t2xs; color: T.textFaint
            }

            // Явный выход. Второй жест необязателен: кому хватает главного - жмёт
            // сюда, и мастер пускает дальше с пустым hotkey_toggle. Это не то же,
            // что «Дальше»: «Дальше» ждёт доказанного жеста, а эта кнопка честно
            // снимает само требование.
            Item { width: 1; height: 4 }
            FlowButton {
                label: L.t("Мне хватит одного жеста")
                onClicked: {
                    toggleStep.skipped = true;
                    toggleStep.verified = false;
                    B.set("hotkey_toggle", "");   // отказ - значит пусто в конфиге
                    wiz.step += 1;
                }
            }
        }

        // === 6. Проверим вставку ===
        Column {
            visible: wiz.step === 6
            anchors.top: parent.top
            width: parent.width
            spacing: 12
            property string result: ""
            id: insStep
            PageTitle {
                text: L.t("Проверим вставку")
                font.pixelSize: T.tXl
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                text: L.t("Нажмите кнопку - текст должен появиться в поле. Если не появился, мешает антивирус.")
                wrapMode: Text.WordWrap
                font.family: T.sans; font.pixelSize: T.tSm; color: T.textMuted
            }
            // Поле в обёртке ради кольца вокруг него. Текст, появившийся сам,
            // легко принять за тот, что лежал там всегда: человек нажал кнопку,
            // моргнул - и в поле что-то есть. Кольцо на секунду показывает,
            // ЧТО именно сейчас произошло и где.
            Item {
                width: parent.width
                height: 30

                FlowInput {
                    id: insField
                    anchors.fill: parent
                    placeholder: L.t("сюда вставится проверочный текст")
                }
                Rectangle {
                    id: insRing
                    anchors.fill: parent
                    anchors.margins: -3
                    radius: T.radiusSm + 3
                    color: "transparent"
                    border.width: 2
                    border.color: T.success
                    opacity: 0

                    SequentialAnimation {
                        id: insFlash
                        NumberAnimation { target: insRing; property: "opacity"; to: 1
                                          duration: T.durFast * 1000 }
                        // 700 мс - ВНЕ трёх токенов, и намеренно. Это не
                        // движение, а стоянка: рамка горит неподвижно, пока
                        // человек переводит взгляд с кнопки на поле. Токены
                        // задают срок перехода (вспышка и угасание вокруг -
                        // как раз по ним), а сколько держать готовый кадр,
                        // диктует чтение. На 280 мс вспышку пропускали.
                        PauseAnimation { duration: 700 }
                        NumberAnimation { target: insRing; property: "opacity"; to: 0
                                          duration: T.durSlow * 1000 }
                    }
                }
            }
            FlowButton {
                label: L.t("Проверить вставку")
                kind: "primary"
                onClicked: {
                    insField.text = "";
                    insStep.result = "";
                    // Фокус в поле - настоящий inserter вставляет туда, где курсор.
                    insField.forceActiveFocus();
                    OB.testInsert();
                }
            }
            Text {
                visible: insStep.result !== ""
                text: insStep.result
                font.family: T.sans; font.pixelSize: T.tSm
                color: insStep.result.indexOf("не") === 0 ? T.danger : T.success
            }
            Connections {
                target: OB
                function onInsertDone(ok) {
                    var good = ok && insField.text.length > 0;
                    insStep.result = good
                        ? L.t("Работает.")
                        : L.t("не сработало - проверьте антивирус или включите режим «посимвольно» в настройках");
                    if (good) insFlash.restart();
                }
            }
        }

        // === 7. Проба ===
        //
        // Единственное место, где человек впервые слышит себя от программы.
        // Волна и текст стоят в ОДНОЙ рамке намеренно: пока говорят - в ней
        // волна, кончили - в ней же проявляется строка. Так видно, что текст
        // сделан из этого голоса, а не найден где-то ещё на экране.
        Column {
            id: trialStep
            visible: wiz.step === 7
            anchors.top: parent.top
            width: parent.width
            spacing: 12
            property bool rec: false
            property string result: ""

            // Проявление результата. Мгновенная подстановка читается как
            // подмена: распознавание идёт секунду с небольшим, и строка,
            // возникшая рывком, выглядит заранее заготовленной. 280 мс и
            // подъём на 6 px - те же, которыми всплывает пилюля.
            property real shown: 0
            property real lift: 0
            onResultChanged: if (result !== "") appear.restart()

            ParallelAnimation {
                id: appear
                NumberAnimation { target: trialStep; property: "shown"; from: 0; to: 1
                                  duration: T.durSlow * 1000
                                  easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut }
                NumberAnimation { target: trialStep; property: "lift"; from: 6; to: 0
                                  duration: T.durSlow * 1000
                                  easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut }
            }

            PageTitle {
                text: L.t("Скажите что-нибудь")
                font.pixelSize: T.tXl
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                text: L.t("Распознанный текст появится здесь и никуда не вставится.")
                font.family: T.sans; font.pixelSize: T.tSm; color: T.textMuted
            }
            FlowButton {
                label: trialStep.rec ? L.t("Стоп") : L.t("Начать запись")
                kind: "primary"
                onClicked: {
                    if (trialStep.rec) { OB.trialStop(); trialStep.result = L.t("распознаю…") }
                    else { trialStep.result = ""; OB.trialStart() }
                    trialStep.rec = !trialStep.rec;
                }
            }
            Rectangle {
                width: parent.width
                height: Math.max(112, resText.implicitHeight + 32)
                radius: T.radiusLg; color: T.paper
                border.width: 1
                // Красная точка записи была бы враньём - в системе красный это
                // ошибка. Зелёная рамка значит «в эфире», ровно как точка на
                // пилюле во время настоящей диктовки.
                border.color: trialStep.rec ? T.success : T.border
                Behavior on border.color { ColorAnimation { duration: T.durFast * 1000 } }

                WaveMeter {
                    anchors.centerIn: parent
                    running: trialStep.rec
                    bars: 32; barW: 4; gap: 4; maxH: 56
                    opacity: trialStep.rec ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: T.durBase * 1000 } }
                }
                Text {
                    id: resText
                    x: 16; y: 16 + trialStep.lift
                    width: parent.width - 32
                    text: trialStep.result
                    opacity: trialStep.shown
                    visible: !trialStep.rec
                    wrapMode: Text.WordWrap
                    font.family: T.sans; font.pixelSize: T.tMd
                    color: T.text
                    lineHeight: 1.3
                }
                Text {
                    anchors.centerIn: parent
                    visible: !trialStep.rec && trialStep.result === ""
                    text: L.t("здесь появится ваш текст")
                    font.family: T.sans; font.pixelSize: T.tSm; color: T.textFaint
                }
            }
            Connections {
                target: OB
                function onTrialReady(text) { trialStep.result = text }
            }
        }

        // === 8. Править текст ===
        //
        // Экран последний намеренно: сначала человек увидел, что диктовка
        // работает, и только потом ему предлагают её улучшить. Предлагать
        // улучшение до того, как заработало основное, - значит просить
        // доверия авансом.
        Column {
            id: llmStep
            visible: wiz.step === 8
            anchors.top: parent.top
            width: parent.width
            spacing: 12

            property bool busy: false
            property bool done: false
            property bool failed: false
            property bool declined: false
            property string stage: ""
            property real frac: 0
            property real total: 0

            PageTitle {
                text: llmStep.done ? L.t("Готово") : L.t("Осталось поставить правку текста")
                font.pixelSize: T.tXl
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                // Обещание переписано: раньше здесь стояло «без неё программа
                // работать не будет», и это перестало быть правдой. Знаки
                // препинания ставят правила, оговорки чинит corrections.py -
                // обязательной работы у Ollama не осталось. Пугать человека
                // тем, чего не случится, нельзя, тем более на последнем шаге,
                // где кнопка «Дальше» ждёт установки.
                text: llmStep.done
                      ? L.t("Всё готово. Программа умеет преобразовывать выделенный ")
                        + L.t("текст и править его голосом.")
                      : L.t("Диктовка работает и без неё: знаки препинания и оговорки ")
                        + L.t("программа чинит сама. Правка текста нужна для другого - ")
                        + L.t("преобразовать выделенное по одному нажатию: короче, строже, ")
                        + L.t("списком, заданием для ИИ.")
                font.family: T.sans; font.pixelSize: T.tSm; color: T.textMuted
                lineHeight: 1.4
            }

            // Цена названа ДО кнопки, а не после нажатия. 3.3 ГБ - это втрое
            // больше самой программы вместе с моделью распознавания, и узнать
            // об этом человек должен заранее.
            Rectangle {
                visible: !llmStep.busy && !llmStep.done
                width: parent.width
                height: priceCol.implicitHeight + 28
                radius: T.radiusLg; color: T.paper
                border.width: 1; border.color: T.border
                Column {
                    id: priceCol
                    x: 16; y: 14
                    width: parent.width - 32
                    spacing: 8
                    Text {
                        text: L.t("Нужно скачать 3.3 ГБ")
                        font.family: T.sans; font.pixelSize: T.tSm
                        font.weight: Font.DemiBold; color: T.text
                    }
                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: L.t("Ollama - бесплатная программа, которая считает это на вашем ")
                              + L.t("компьютере, и модель к ней. Всё останется здесь: интернет ")
                              + L.t("нужен только чтобы скачать.")
                        font.family: T.sans; font.pixelSize: T.t2xs; color: T.textMuted
                        lineHeight: 1.4
                    }
                }
            }

            // Ход установки: этап словами и полоса. Проценты без этапа врут -
            // «40%» ничего не значит, если непонятно, чего именно сорок.
            Column {
                visible: llmStep.busy
                width: parent.width
                spacing: 8
                Text {
                    text: llmStep.total > 0
                          ? llmStep.stage + " · " + Math.round(llmStep.frac * 100) + "% из "
                            + (llmStep.total / 1e9).toFixed(1) + " ГБ"
                          : llmStep.stage
                    font.family: T.sans; font.pixelSize: T.tSm; color: T.text
                }
                Rectangle {
                    width: parent.width; height: 6; radius: 3; color: T.fill
                    Rectangle {
                        width: parent.width * Math.max(0, Math.min(1, llmStep.frac))
                        height: parent.height; radius: 3; color: T.accent
                        Behavior on width { NumberAnimation { duration: T.durBase * 1000 } }
                    }
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: L.t("Можно свернуть окно - диктовка уже работает.")
                    font.family: T.sans; font.pixelSize: T.t2xs; color: T.textMuted
                }
            }

            // Конец установки. Три гигабайта ждут долго, и молчаливое
            // исчезновение полосы - плохая награда за ожидание: та же галка и
            // тот же кивок, что на экране модели, отвечают на «ну как?».
            Row {
                id: llmDoneRow
                visible: llmStep.done
                spacing: 8
                opacity: 0
                scale: 0.96
                onVisibleChanged: if (visible) llmPop.restart()

                ParallelAnimation {
                    id: llmPop
                    NumberAnimation { target: llmDoneRow; property: "opacity"; from: 0; to: 1
                                      duration: T.durSlow * 1000
                                      easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut }
                    NumberAnimation { target: llmDoneRow; property: "scale"; from: 0.96; to: 1
                                      duration: T.durSlow * 1000
                                      easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut }
                }

                Icon {
                    anchors.verticalCenter: parent.verticalCenter
                    path: ic.check; size: 16; color: T.success; weight: 2.2
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: L.t("Правка текста на месте - можно закрывать мастер.")
                    font.family: T.sans; font.pixelSize: T.tSm; color: T.success
                }
            }

            Row {
                visible: !llmStep.busy && !llmStep.done
                spacing: 12
                FlowButton {
                    label: llmStep.failed ? L.t("Попробовать снова") : L.t("Да, установить")
                    kind: "primary"
                    onClicked: {
                        llmStep.failed = false;
                        llmStep.declined = false;
                        llmStep.busy = true;
                        llmStep.stage = "начинаю";
                        llmStep.frac = 0;
                        llmStep.total = 0;
                        OB.llmInstall();
                    }
                }
                // «Позже» возвращена по решению владельца: правка текста снова
                // необязательна. Знаки препинания ставят правила, оговорки чинит
                // corrections.py - без Ollama диктовка работает целиком, и
                // запирать человека на этом шаге ради 3.3 ГБ нельзя. Путь тот же,
                // что у нижней «Готово», - OB.finish() закроет мастер без установки.
                FlowButton {
                    label: L.t("Позже")
                    onClicked: OB.finish()
                }
            }

            // Отказ не молчит: человек должен знать, что дверь осталась
            // открытой и где она. Уходит само через пять секунд - это заметка,
            // а не диалог, и закрывать её вручную незачем.
            Rectangle {
                id: declineNote
                width: parent.width
                height: noteText.implicitHeight + 24
                radius: T.radiusLg
                color: T.fillSubtle
                border.width: 1; border.color: T.border
                opacity: llmStep.declined ? 1 : 0
                visible: opacity > 0
                Behavior on opacity { NumberAnimation { duration: T.durBase * 1000 } }
                Text {
                    id: noteText
                    x: 16; y: 12
                    width: parent.width - 32
                    wrapMode: Text.WordWrap
                    text: L.t("Хорошо. Включить можно потом: «Диктовка» → «Правка текста на ходу», ")
                          + L.t("там та же кнопка и то же объяснение.")
                    font.family: T.sans; font.pixelSize: T.t2xs; color: T.textSecondary
                    lineHeight: 1.4
                }
                Timer {
                    id: declineTimer
                    interval: 5000
                    onTriggered: llmStep.declined = false
                }
            }

            Text {
                visible: llmStep.failed
                width: parent.width
                wrapMode: Text.WordWrap
                text: L.t("Не получилось - ") + llmStep.stage + L.t(". Диктовка работает и без этого, ")
                      + L.t("а попробовать снова можно в настройках.")
                font.family: T.sans; font.pixelSize: T.t2xs; color: T.danger
                lineHeight: 1.4
            }

            Connections {
                target: OB
                function onLlmStage(stage, frac, total) {
                    llmStep.stage = stage;
                    llmStep.frac = frac;
                    llmStep.total = total;
                }
                function onLlmDone(ok) {
                    llmStep.busy = false;
                    llmStep.done = ok;
                    llmStep.failed = !ok;
                }
            }
        }
    }
    }

    // ---------- низ: назад / дальше ----------
    Item {
        id: footer
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 72

        FlowButton {
            visible: wiz.step > 0
            anchors { left: parent.left; leftMargin: 32; verticalCenter: parent.verticalCenter }
            label: L.t("Назад")
            onClicked: wiz.step -= 1
        }
        FlowButton {
            id: nextBtn
            anchors { right: parent.right; rightMargin: 32; verticalCenter: parent.verticalCenter }
            kind: "primary"
            // Живая проверка жестов запирает «Дальше»: на экране удержания -
            // пока сочетание не зажали хоть раз (verified), на экране второго
            // жеста - пока не доказали ЛИБО не отказались явно (skipped).
            // Остальные шаги не трогаем: у модели блокировка своя, через
            // onClicked ниже (скачать, а не пройти дальше).
            enabled: wiz.step === 4 ? hkStep.verified
                   : wiz.step === 5 ? (toggleStep.verified || toggleStep.skipped)
                   : true
            // Последний шаг больше не запирает: владелец сделал правку текста
            // необязательной. Раньше кнопка ждала установки Ollama - без неё
            // модель отдавала текст без знаков препинания; теперь их ставят
            // правила, и «Готово» выпускает человека с рабочей диктовкой.
            // Ставить Ollama или нет, он решает сам кнопками на этом экране.
            label: wiz.step === 0 ? L.t("Начать")
                 : wiz.step === 2 ? (wiz.modelReady ? "Дальше"
                                     : wiz.downloading ? "Скачивается…" : "Скачать модель")
                 : wiz.step === wiz.last ? L.t("Готово")
                 : L.t("Дальше")
            onClicked: {
                if (wiz.step === 2 && !wiz.modelReady) {
                    if (!wiz.downloading) B.downloadModel(wiz.chosenModel);
                    return;
                }
                if (wiz.step === 2 && wiz.modelReady) B.setModel(wiz.chosenModel);
                // Второй жест доказан - только теперь пишем его в конфиг (до
                // «Дальше» умолчание жило локально, см. syncHotkeyWatch).
                if (wiz.step === 5) B.set("hotkey_toggle", toggleStep.spec);
                if (wiz.step === wiz.last) { OB.finish(); return; }  // finish() сам закроет окно
                wiz.step += 1;
            }
        }
    }
}
