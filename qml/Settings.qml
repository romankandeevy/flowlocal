// Окно настроек: боковое меню плюс страницы. Вёрстка целиком здесь, данные -
// в settings_qt.Backend (контекстное свойство `B`), токены - в `T`.
//
// Сохранение сразу по изменению, кнопки «Применить» нет намеренно: лишний шаг,
// о котором легко забыть.
//
// Дверей шесть, а не десять (исследование конкурентов, IMPROVEMENTS §2.3):
// Основное+Распознавание+Ввод слились в «Диктовку», Словарь+Замены - в
// «Слова». Отдельной страницы «Модели» нет: в каталоге осталось две модели,
// и обе живут строкой в «Распознавании» - экран под два варианта был бы
// лишней дверью.
//
// Правило страниц: если возможность есть в коде, у неё есть место здесь.
// Настройка, которую видно только в config.json, для человека, которому
// программу отдали, не существует - сколько бы кода за ней ни стояло.

import QtQuick

Rectangle {
    id: win
    color: T.bg
    focus: true

    // Фактура из системы: точечная сетка и мягкий прожектор акцентом.
    // Плоская заливка - не то, чем Korti предлагает заполнять поверхность.
    Backdrop { anchors.fill: parent }

    property string page: "Главная"
    // Новая страница - с начала: прокрутка одной не должна доставаться другой.
    onPageChanged: scroll.contentY = 0
    // Программа и настройки разведены.
    //
    // Раньше всё лежало в одном списке: «Главная» рядом с «Диктовкой», история
    // рядом с микрофоном. Человек, открывший окно посмотреть надиктованное,
    // видел вперемешку своё и служебное - а это разные вещи, и заходят за ними
    // в разное время. Настройки трогают раз в месяц, историю - каждый день.
    //
    // Теперь два набора и переключение между ними. Шестерёнка внизу панели
    // уводит в настройки, «Назад» возвращает. Окно то же самое: заводить второе
    // значило бы решать заново и положение, и тему, и закрытие по Esc.
    property bool inSettings: false
    readonly property var mainPages: ["Главная", "История", "Статистика"]
    readonly property var settingsPages: ["Диктовка", "Слова", "О программе"]
    readonly property var pages: inSettings ? settingsPages : mainPages

    // Одна строка под заголовком отвечает на «что мне это даст» - правило
    // голоса бренда. У «Главной» вместо подписи говорит сама страница.
    // Страницы без записи (Главная говорит сама за себя, «О программе» - тоже)
    // просто отсутствуют: `subtitles[page] || ""` даёт пустую подпись, и
    // строка прячется. Заводить для них "" - два способа сказать одно.
    // Ключ - русское имя страницы (оно же идентификатор), значение переводится
    // при показе через L.t() там, где строка выводится.
    readonly property var subtitles: ({
        "Диктовка":    "Сочетания, микрофон и то, как появляется текст",
        "Слова":       "Научите программу писать так, как нужно вам",
        "История":     "Всё, что вы надиктовали. Можно найти и скопировать",
        "Статистика":  "Сколько вы наговорили и сколько времени это сберегло"
    })

    // Esc: во время захвата отменяет захват, иначе закрывает окно.
    Keys.onEscapePressed: B.cancelCapture()

    Connections {
        target: B
        function onFlashed(text, kind) {
            footer.text = text;
            footer.color = kind === "danger" ? T.danger
                         : kind === "accent" ? T.accent : T.textMuted;
            flashTimer.restart();
        }
    }
    Timer { id: flashTimer; interval: 2200; onTriggered: footer.text = "" }

    Icons { id: ic }

    // ---------- боковое меню ----------
    // Канон Korti (templates/app-shell): панель 240, отделена линией, вордмарк
    // со знаком, ниже - навигация с иконками.
    Item {
        id: side
        width: 240
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }

        // Линия-разделитель: в системе панель всегда отделена от содержимого.
        // Без неё окно разваливалось на два несвязанных поля.
        Rectangle {
            anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
            width: 1
            color: T.border
        }

        Column {
            anchors { left: parent.left; right: parent.right; top: parent.top
                      leftMargin: 14; rightMargin: 14; topMargin: 18 }
            spacing: 2

            Wordmark {
                leftPadding: 8
                bottomPadding: 18
            }

            // Возврат из настроек - первой строкой, там же, где обычно первый
            // пункт: глазу не надо искать выход в новом месте.
            NavItem {
                visible: win.inSettings
                label: L.t("Назад")
                icon: ic.forPage("Назад")
                active: false
                onClicked: {
                    win.inSettings = false;
                    win.page = win.mainPages[0];
                }
            }

            Repeater {
                model: win.pages
                NavItem {
                    // Имя страницы служит и идентификатором (win.page === ...),
                    // поэтому переводим только показ, а не сам массив.
                    label: L.t(modelData)
                    icon: ic.forPage(modelData)
                    active: win.page === modelData

                    onClicked: win.page = modelData
                }
            }

            // «Заметки» - отдельное ОКНО, а не страница, поэтому пункт не
            // подсвечивается и не меняет win.page. Но дверь ему нужна здесь:
            // пока её не было, скретчпад можно было найти только в трее, и
            // владелец его не нашёл. Функция, которую не видно, всё равно что
            // не сделана.
            NavItem {
                visible: !win.inSettings
                label: L.t("Заметки")
                icon: ic.forPage("Заметки")
                active: false
                onClicked: B.openNotes()
            }

            Item { width: 1; height: 10; visible: !win.inSettings }

            NavItem {
                visible: !win.inSettings
                label: L.t("Настройки")
                icon: ic.forPage("Настройки")
                active: false
                onClicked: {
                    win.inSettings = true;
                    win.page = win.settingsPages[0];
                }
            }
        }

        // Низ панели: чем диктовать. Korti кладёт сюда карточку пользователя -
        // у нас пользователя нет, а вот сочетание человек ищет постоянно, и
        // это единственное место, где оно всегда на виду.
        //
        // Сюда же, над сочетаниями, - предложение обновиться. Панель видна с
        // любой страницы, поэтому новость доходит независимо от того, где
        // человек находится. На Главной карточка этого не давала: туда ещё надо
        // зайти. Всплывающего окна нет намеренно - диктовка работает поверх
        // чужой работы, и выскакивать посреди неё с новостью о версии значит
        // мешать.
        Column {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom
                      leftMargin: 24; rightMargin: 14; bottomMargin: 18 }
            spacing: 3

            Item {
                id: upd
                property var info: B.pendingUpdate()
                readonly property bool has: info && info.version
                visible: has
                width: parent.width
                height: has ? updCol.implicitHeight + 20 : 0

                Column {
                    id: updCol
                    width: parent.width - 8
                    spacing: 2

                    Row {
                        spacing: 6
                        // Точка акцентом: в Korti синий - «особенное», и
                        // обновление ровно оно. Красный тут был бы враньём:
                        // ничего не сломалось.
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 6; height: 6; radius: 3
                            color: T.accent
                        }
                        Text {
                            text: L.t("Версия ") + (upd.info.version || "")
                            font.family: T.sans; font.pixelSize: T.t2xs
                            font.weight: Font.DemiBold
                            color: T.text
                        }
                    }
                    Text {
                        width: updCol.width
                        wrapMode: Text.WordWrap
                        text: upd.info.title || ""
                        visible: text !== ""
                        maximumLineCount: 2
                        elide: Text.ElideRight
                        font.family: T.sans; font.pixelSize: T.t2xs
                        color: T.textMuted
                        lineHeight: 1.35
                    }
                    Text {
                        id: updLink
                        text: L.t("Обновить · ") + (upd.info.size_mb || 0) + L.t(" МБ")
                        font.family: T.sans; font.pixelSize: T.t2xs
                        font.weight: Font.Medium
                        font.underline: updHit.containsMouse
                        color: T.accent
                        MouseArea {
                            id: updHit
                            anchors.fill: parent
                            anchors.margins: -4
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: B.applyUpdate()
                        }
                    }
                }
            }

            // Линия одна на двоих: блок обновления и сочетания разделяет та
            // же волосяная линия, что была тут всегда. Своя добавочная давала
            // на экране две подряд.
            Rectangle {
                width: parent.width - 8; height: 1; color: T.border
                anchors.horizontalCenter: parent.horizontalCenter
            }
            Item { width: 1; height: 9 }
            Text {
                text: L.t("ДИКТОВКА")
                font.family: T.sans; font.pixelSize: T.t2xs
                font.weight: Font.DemiBold; font.letterSpacing: 0.6
                color: T.textFaint
            }
            Text {
                width: parent.width
                text: {
                    var a = B.pretty(B.get("hotkey_hold") || "");
                    var b = B.pretty(B.get("hotkey_toggle") || "");
                    var parts = [];
                    if (B.get("hotkey_hold")) parts.push(a);
                    if (B.get("hotkey_toggle")) parts.push(b);
                    return parts.length ? parts.join("\n") : "не назначено";
                }
                font.family: T.mono; font.pixelSize: T.t2xs
                color: (B.get("hotkey_hold") || B.get("hotkey_toggle"))
                       ? T.textSecondary : T.danger
                lineHeight: 1.5
            }
        }
    }

    // ---------- содержимое ----------
    Flickable {
        id: scroll
        anchors { left: side.right; right: parent.right; top: parent.top
                  bottom: footer.top; rightMargin: 0 }
        clip: true
        contentHeight: content.implicitHeight + 52
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: content
            x: 28
            y: 26
            width: scroll.width - 56
            spacing: 16

            Column {
                width: parent.width
                spacing: 6
                // Сравниваем с РУССКИМ именем страницы, а показываем перевод:
                // имя служит идентификатором, и переводить его в сравнении
                // значит сломать условие на английском языке.
                PageTitle {
                    text: win.page === "Главная" ? home.greeting : L.t(win.page)
                }
                Text {
                    width: parent.width
                    visible: text !== ""
                    text: L.t(win.subtitles[win.page] || "")
                    wrapMode: Text.WordWrap
                    font.family: T.sans
                    font.pixelSize: T.tBase
                    color: T.textMuted
                }
            }

            // ===== Главная =====
            // Канон Korti (templates/app-shell, Overview): крупный заголовок,
            // ряд карточек-метрик, ниже список последних событий. Здесь то же
            // самое, только события - ваши диктовки.
            Column {
                id: home
                visible: win.page === "Главная"
                width: parent.width
                spacing: 16

                property var st: ({})
                property var recent: []
                property string greeting: L.t("Главная")
                // Находки считаются при открытии страницы и после каждого
                // решения: список обязан отвечать на нажатие сразу, иначе
                // человек нажмёт второй раз.
                property var tips: []
                function refreshTips() { home.tips = B.suggestions(); }
                // Есть ли что показывать в числах. Пустые метрики (три «0» и
                // прочерк) - худшее первое впечатление, поэтому до первой
                // диктовки ряда чисел нет вовсе, только зов попробовать.
                readonly property bool hasData: recent.length > 0

                function reload() {
                    // Одним заходом: числа и последние диктовки живут в одном
                    // файле, и читать его дважды незачем.
                    var d = B.homeData();
                    st = d.stats;
                    recent = d.recent;
                    // По имени, а не «Главная».
                    //
                    // Владелец сказал прямо: «Роман, с возвращением» - как в
                    // Wispr; сейчас из Wispr не взято ничего. Имя берём из
                    // учётной записи Windows, спрашивать его отдельным экраном
                    // ради одной строки не стоит. Не узнали - здороваемся без
                    // имени, как раньше: «Доброе утро, » с пустотой на конце
                    // хуже, чем просто «Доброе утро».
                    var h = new Date().getHours();
                    var hi = L.t(h < 5 ? "Доброй ночи" : h < 12 ? "Доброе утро"
                                 : h < 18 ? "Добрый день" : "Добрый вечер");
                    greeting = B.userName ? hi + ", " + B.userName : hi;
                }
                Component.onCompleted: { reload(); refreshTips(); }
                // Находки пересчитываем при каждом заходе на страницу: история
                // растёт, пока окно закрыто, и список должен это учитывать.
                onVisibleChanged: if (visible) { reload(); refreshTips(); }

                // Что программа заметила сама. Страница «Слова» была формой,
                // которую надо заполнять руками, - владелец назвал это функцией
                // для айтишника, и был прав. Заполнять её теперь предлагает
                // программа: она видит, что человек повторяет, и приносит
                // ЗНАЧЕНИЕ. Имя даёт человек - назвать по-человечески машина не
                // может, «roman@почта» это «моя почта» или «рабочая», знает
                // только он.
                Repeater {
                    model: home.tips

                    Card {
                        width: home.width
                        Item {
                            width: parent.width
                            implicitHeight: tipCol.implicitHeight + 36

                            Column {
                                id: tipCol
                                anchors { left: parent.left; right: parent.right; top: parent.top
                                          leftMargin: 20; rightMargin: 20; topMargin: 18 }
                                spacing: 10

                                Text {
                                    width: parent.width
                                    wrapMode: Text.WordWrap
                                    text: L.t("Вы диктовали это ") + modelData.times
                                          + (modelData.kind !== "фраза" ? " - " + modelData.kind : "")
                                          + L.t(". Дать короткую фразу?")
                                    font.family: T.sans; font.pixelSize: T.tSm
                                    font.weight: Font.DemiBold; color: T.text
                                }
                                Text {
                                    width: parent.width
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 3
                                    elide: Text.ElideRight
                                    text: "«" + modelData.value + "»"
                                    font.family: T.sans; font.pixelSize: T.tXs
                                    color: T.textMuted
                                    lineHeight: 1.4
                                }
                                Row {
                                    spacing: 8
                                    FlowInput {
                                        id: tipName
                                        width: 220
                                        placeholder: L.t("как это называть")
                                    }
                                    FlowButton {
                                        label: L.t("Запомнить")
                                        kind: "primary"
                                        onClicked: {
                                            B.acceptSuggestion(tipName.text, modelData.value);
                                            home.refreshTips();
                                        }
                                    }
                                    FlowButton {
                                        label: L.t("Не надо")
                                        onClicked: {
                                            B.declineSuggestion(modelData.value);
                                            home.refreshTips();
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Первое, что человек должен узнать: как этим пользоваться.
                // Не «состояние системы», а одна фраза действием.
                Card {
                    width: parent.width
                    Item {
                        width: parent.width
                        implicitHeight: hero.implicitHeight + 40
                        Column {
                            id: hero
                            anchors { left: parent.left; right: parent.right; top: parent.top
                                      leftMargin: 20; rightMargin: 20; topMargin: 20 }
                            spacing: 10

                            Row {
                                spacing: 9
                                Rectangle {
                                    width: 8; height: 8; radius: 4
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: B.ready ? T.success : T.textMuted
                                }
                                Text {
                                    text: B.ready ? L.t("Готов записывать") : L.t("Просыпаюсь…")
                                    font.family: T.sans
                                    font.pixelSize: T.tSm
                                    font.weight: Font.Medium
                                    color: T.textSecondary
                                }
                            }
                            Text {
                                width: hero.width
                                wrapMode: Text.WordWrap
                                text: B.pretty(B.get("hotkey_hold") || "")
                                      ? L.t("Зажмите ") + B.pretty(B.get("hotkey_hold"))
                                        + L.t(" и говорите. Отпустили - текст на месте.")
                                      : B.pretty(B.get("hotkey_toggle") || "")
                                      ? L.t("Нажмите ") + B.pretty(B.get("hotkey_toggle"))
                                        + L.t(" и говорите. Нажмите ещё раз - текст на месте.")
                                      : L.t("Сочетание не назначено - задайте его на странице «Диктовка».")
                                font.family: T.sans
                                // 17, а не 20: в шкале Korti 20 - это кегль
                                // заголовка, и целая фраза в нём спорила с
                                // «Добрый вечер» прямо над карточкой. Двух
                                // заголовков на экране не бывает.
                                font.pixelSize: T.tLg
                                font.weight: Font.DemiBold     // 600: крупная фраза, но не «кричит»
                                font.letterSpacing: -0.2
                                color: T.text
                                lineHeight: 1.3
                            }
                            Text {
                                width: hero.width
                                wrapMode: Text.WordWrap
                                text: L.t("Работает в любом окне: письмо, чат, документ. ")
                                      + L.t("Голос не покидает этот компьютер.")
                                font.family: T.sans
                                font.pixelSize: T.tSm
                                color: T.textMuted
                                lineHeight: 1.5
                            }
                        }
                    }
                }

                // Правка текста не установлена - говорим об этом первым делом
                // и не даём об этом забыть.
                //
                // Раньше она была необязательной, и без неё программа просто
                // работала чуть скромнее. Теперь без неё программа неполна:
                // модель по умолчанию не ставит знаков препинания, не работают
                // ни поправки на ходу, ни преобразования выделенного текста.
                // Молчать про это значит отдать человеку половину программы и
                // не сказать, что вторая половина существует.
                Card {
                    width: parent.width
                    visible: !llmBanner.ready
                    Item {
                        width: parent.width
                        implicitHeight: bcol.implicitHeight + 32
                        Column {
                            id: bcol
                            anchors { left: parent.left; right: parent.right; top: parent.top
                                      leftMargin: 20; rightMargin: 20; topMargin: 16 }
                            spacing: 8
                            Row {
                                spacing: 8
                                Rectangle {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 7; height: 7; radius: 4; color: T.danger
                                }
                                Text {
                                    text: L.t("Правка текста не установлена")
                                    font.family: T.sans; font.pixelSize: T.tMd
                                    font.weight: Font.DemiBold; color: T.text
                                }
                            }
                            Text {
                                width: parent.width
                                wrapMode: Text.WordWrap
                                text: L.t("Без неё нет знаков препинания, поправок на ходу и ")
                                      + L.t("преобразований текста. Ставится один раз, работает ")
                                      + L.t("дальше без интернета.")
                                font.family: T.sans; font.pixelSize: T.tSm
                                color: T.textMuted
                                lineHeight: 1.4
                            }
                            FlowButton {
                                label: llmBanner.busy ? L.t("Ставится…") : L.t("Установить")
                                kind: "primary"
                                enabled: !llmBanner.busy
                                onClicked: { llmBanner.busy = true; B.llmInstall() }
                            }
                        }
                    }
                    Item {
                        id: llmBanner
                        property bool ready: B.llmReady()
                        property bool busy: B.llmBusy()
                        Connections {
                            target: B
                            function onChanged() {
                                llmBanner.ready = B.llmReady();
                                llmBanner.busy = B.llmBusy();
                            }
                        }
                    }
                }

                // Числа, а не прилагательные - так говорит система. Первым -
                // сэкономленное время: единственное число, ради которого
                // человек вообще открыл бы эту страницу. До первой диктовки
                // ряда нет: пустые «0» и прочерк выглядят как сломанный экран.
                Row {
                    width: parent.width
                    spacing: 12
                    visible: home.hasData
                    property real cw: (width - 24) / 3
                    Metric {
                        width: parent.cw
                        order: 0
                        label: L.t("сэкономлено")
                        value: home.st.saved_sec || "0 с"
                        hint: L.t("по сравнению с печатью руками")
                    }
                    Metric {
                        width: parent.cw
                        order: 1
                        label: L.t("скорость")
                        pending: !home.st.speedOk
                        value: home.st.speedOk ? home.st.speed
                                               : L.t("Наговорите минуту - посчитаем")
                        hint: L.t("быстрее, чем печатать руками")
                    }
                    Metric {
                        width: parent.cw
                        order: 2
                        label: L.t("надиктовано")
                        // Чистый счётчик слов - его и оживляем: бежит от нуля.
                        countTo: parseInt(home.st.words || "0")
                        hint: L.t("слов за всё время")
                    }
                }

                SectionHeader { text: L.t("ПОСЛЕДНЕЕ"); visible: home.hasData }

                // Пусто - не прячем экран, а зовём попробовать. Пустой список
                // без объяснения выглядит как поломка.
                Card {
                    width: parent.width
                    visible: home.recent.length === 0
                    Item {
                        width: parent.width
                        implicitHeight: 92
                        Text {
                            anchors.centerIn: parent
                            width: parent.width - 36
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            text: L.t("Здесь появится то, что вы надиктуете.\nПопробуйте прямо сейчас - скажите что-нибудь.")
                            font.family: T.sans
                            font.pixelSize: T.tSm
                            color: T.textMuted
                            lineHeight: 1.5
                        }
                    }
                }

                Column {
                    width: parent.width
                    spacing: 8
                    Repeater {
                        model: home.recent
                        Card {
                            width: home.width
                            Item {
                                width: parent.width
                                implicitHeight: Math.max(52, line.implicitHeight + 26)
                                MouseArea {
                                    id: hit
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: B.copyText(modelData.text)
                                }
                                Rectangle {
                                    id: dot
                                    x: 16
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 7; height: 7; radius: 3.5
                                    color: T.success
                                }
                                Column {
                                    id: line
                                    anchors { left: dot.right; right: when_.left; top: parent.top
                                              leftMargin: 12; rightMargin: 12; topMargin: 13 }
                                    spacing: 3
                                    Text {
                                        width: parent.width
                                        elide: Text.ElideRight
                                        maximumLineCount: 2
                                        wrapMode: Text.WordWrap
                                        text: modelData.text
                                        font.family: T.sans
                                        font.pixelSize: T.tBase
                                        // Обычный вес, а не полужирный. Это
                                        // содержимое строки, а не её заголовок:
                                        // четыре полужирные фразы подряд
                                        // читались как четыре заголовка.
                                        color: T.text
                                    }
                                    Text {
                                        // Подсказка одна на список, а не по
                                        // штуке на строку: повторённая четыре
                                        // раза, она перестаёт быть подсказкой
                                        // и становится шумом. Показываем под
                                        // курсором - там, где она и нужна.
                                        text: L.t("нажмите, чтобы скопировать")
                                        font.family: T.sans
                                        font.pixelSize: T.t2xs
                                        color: T.textMuted
                                        opacity: hit.containsMouse ? 1 : 0
                                        Behavior on opacity {
                                            NumberAnimation { duration: T.durFast * 1000 }
                                        }
                                    }
                                }
                                Text {
                                    id: when_
                                    anchors { right: parent.right; rightMargin: 16
                                              verticalCenter: parent.verticalCenter }
                                    text: String(modelData.ts).slice(11, 16)
                                    font.family: T.mono
                                    font.pixelSize: T.t2xs
                                    color: T.textMuted
                                }
                            }
                        }
                    }
                }
            }

            // ===== Диктовка =====
            // Бывшие Основное + Распознавание + Ввод: одна дверь вместо трёх.
            // Порядок секций - от того, что трогают чаще, к тому, что один раз.
            Column {
                visible: win.page === "Диктовка"
                width: parent.width
                spacing: 16

                SectionTitle { text: L.t("Сочетания") }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: L.t("Удерживать и говорить")
                        subtitle: L.t("Самый простой способ. Можно назначить и боковую кнопку мыши")
                        HotkeyField { field: "hotkey_hold" }
                    }
                    SettingRow {
                        title: L.t("Нажать и говорить")
                        subtitle: L.t("Если диктуете долго и не хотите держать клавишу. Esc - отменить")
                        HotkeyField { field: "hotkey_toggle"; allowClear: true }
                    }
                    // Две строки, про которые владелец сказал «непонятно, что
                    // это и через что работает; если через Ollama - почему она
                    // тогда не требуется». Обе беды были в подписи:
                    //
                    //   1) она объясняла ЖЕСТ, но не результат. «Зажмите и
                    //      скажите» - это как, а человек спрашивал что;
                    //   2) про зависимость говорилось только когда правка
                    //      выключена. Включил - строчка исчезала, и связь между
                    //      «Правкой текста» и этими двумя пропадала совсем.
                    //
                    // Теперь обе подписи начинаются с результата и всегда
                    // называют, чем это работает.
                    SettingRow {
                        title: L.t("Править выделенное голосом")
                        // Привязка к самому тумблеру, а не к B.get: тумблер
                        // теперь на этой же странице, и подпись обязана
                        // меняться сразу, как его щёлкнули (B.get - слот без
                        // сигнала, он бы застыл на старом значении).
                        subtitle: L.t("Выделили чужой текст, зажали, сказали «сделай короче» - текст переписался. ")
                                  + (llmToggle.value
                                     ? L.t("Работает: «Правка текста на ходу» включена")
                                     : L.t("Сейчас не работает: включите «Правку текста на ходу» ниже"))
                        HotkeyField { field: "hotkey_command"; allowClear: true }
                    }
                    SettingRow {
                        title: L.t("Преобразовать текст")
                        subtitle: L.t("То же, но говорить не надо: список готовых правок, выбор цифрой. ")
                                  + (tfHint.value
                                     ? L.t("Что в списке - на странице «Слова»")
                                     : L.t("Сейчас не работает: включите «Правку текста на ходу» ниже"))
                        // Невидимая привязка к тому же тумблеру, что у правки
                        // голосом: подпись обязана меняться сразу, как его
                        // щёлкнули, а B.get - слот без сигнала и застыл бы.
                        Item { id: tfHint; property bool value: llmToggle.value; width: 0 }
                        HotkeyField { field: "hotkey_transform"; allowClear: true }
                    }
                    SettingRow {
                        title: L.t("Открыть заметки")
                        subtitle: L.t("Отдельное окно, куда удобно диктовать длинно, ")
                                  + L.t("не целясь в чужое поле. Есть и в панели слева")
                        HotkeyField { field: "hotkey_notes"; allowClear: true }
                    }
                    SettingRow {
                        title: L.t("Отменить последнюю диктовку")
                        subtitle: L.t("Уберёт вставленный текст, если вы после этого ничего не печатали")
                        HotkeyField { field: "undo_hotkey"; allowClear: true }
                    }
                }

                SectionTitle { text: L.t("Микрофон") }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: L.t("Микрофон")
                        subtitle: L.t("Какой микрофон слушать")
                        Select {
                            options: B.micOptions
                            value: B.get("mic_device")
                            onPicked: (v) => B.set("mic_device", v)
                        }
                    }
                    ToggleRow {
                        title: L.t("Не терять первое слово")
                        subtitle: L.t("Микрофон наготове, поэтому начало фразы не обрежется")
                        path: "keep_mic_open"
                    }
                    SettingRow {
                        title: L.t("Слышать начало заранее")
                        subtitle: L.t("На случай, если начали говорить чуть раньше, чем нажали")
                        Slider {
                            from: 0; to: 1.5; stepSize: 0.1
                            value: B.get("pre_buffer_sec")
                            onMoved: (v) => B.set("pre_buffer_sec", v)
                        }
                    }
                    // «Как это определяется?» - спросил владелец, и по подписи
                    // это было не узнать: она говорила, ЧТО будет, но не по
                    // какому признаку. Признак один и простой - длина нажатия,
                    // поэтому её и называем, вместе с текущим значением. У
                    // ползунка без числа вообще нет способа сказать, где он
                    // стоит.
                    SettingRow {
                        title: L.t("Не реагировать на случайные касания")
                        // Признак называем прямо: решает длина нажатия, и
                        // ничего больше. Число не повторяем - его показывает
                        // сам ползунок справа.
                        subtitle: L.t("Решает длина нажатия: короче этого - промах, а не диктовка. ")
                                  + L.t("Задели клавишу мимоходом - записи не будет")
                        Slider {
                            from: 0.1; to: 1.5; stepSize: 0.1
                            value: B.get("min_record_sec")
                            onMoved: (v) => B.set("min_record_sec", v)
                        }
                    }
                }

                SectionTitle { text: L.t("Чистка текста") }
                Card {
                    width: parent.width
                    // Выключателей здесь было пять, стало два.
                    //
                    // «Убирать слова-паразиты» и «Слышать вопрос» убраны
                    // намеренно: владелец спросил «зачем выключатель, это же
                    // должно работать всегда» - и он прав. Обе чистки нельзя
                    // заметить как вмешательство: они не переписывают сказанное,
                    // а убирают запинку и ставят знак, который вы и произнесли.
                    // Выключатель у такого - это вопрос «хотите ли вы, чтобы
                    // программа работала хорошо».
                    //
                    // Выключить их по-прежнему можно, и одним движением:
                    // «Насколько править» → «слегка» снимает чистку от бубнежа,
                    // «ничего» - всё сразу. Один понятный переключатель вместо
                    // трёх непонятных.
                    ToggleRow {
                        first: true
                        title: L.t("Голосовые команды")
                        subtitle: L.t("Скажите «с новой строки» - и будет новая строка. Скажите «нажми энтер» в конце - сообщение отправится")
                        path: "voice_commands"
                    }
                    // Была ДВА раза: здесь как «Понимать поправки на ходу» и
                    // ниже как «Правка текста на ходу» с кнопкой установки.
                    // Владелец сказал прямо: написано дважды про одно и то же.
                    // Осталась одна строка - с примером, состоянием и кнопкой.
                    ToggleRow {
                        id: llmToggle
                        title: L.t("Правка текста на ходу")
                        subtitle: llmSetup.ready
                            ? L.t("Сказали «в пятницу, нет, в субботу» - останется суббота. ")
                              + L.t("Она же нужна для «Править выделенное голосом» и «Преобразовать текст»")
                            : L.t("Сказали «в пятницу, нет, в субботу» - останется суббота. ")
                              + L.t("Ставится один раз кнопкой ниже, дальше работает без интернета")
                        path: "llm.enabled"
                    }

                    // Установка одной кнопкой - та же, что в мастере первого
                    // запуска, и с тем же объяснением. Раньше здесь стояло
                    // «Нужна Ollama» и всё: ни ссылки, ни того, какую модель
                    // качать, ни слова про сервер. Владелец сказал прямо, что
                    // даже он не знает, как это сделать, - значит функции не
                    // существовало, сколько бы кода за ней ни стояло.
                    //
                    // Строка не исчезает после установки: человеку нужно
                    // видеть, что всё на месте, а не догадываться по отсутствию
                    // кнопки. Состояние показывает цвет - зелёный «скачано»,
                    // синий «качается», красный «не скачано или не вышло».
                    SettingRow {
                        id: llmSetup

                        property bool ready: B.llmReady()
                        property bool busy: B.llmBusy()
                        property bool failed: false
                        property string stage: ""
                        property real frac: 0
                        property real total: 0

                        readonly property color tone: ready ? T.success
                                                    : busy  ? T.accent
                                                            : T.danger
                        readonly property string word: ready ? "скачано"
                                                     : busy  ? (stage || "качается")
                                                     : failed ? "не вышло"
                                                             : L.t("не скачано")

                        // Заголовок пустой намеренно: строкой выше уже стоит
                        // «Правка текста на ходу», и повторять его здесь -
                        // ровно та претензия, из-за которой две строки слились
                        // в одну. Здесь только состояние и кнопка к ней.
                        title: ""
                        subtitle: ready
                            ? L.t("Всё установлено. Поправки, тон и преобразования работают")
                            : busy
                            ? (total > 0
                               ? Math.round(frac * 100) + "% из " + (total / 1e9).toFixed(1) + " ГБ"
                               : L.t("идёт установка, диктовке это не мешает"))
                            : failed
                            ? L.t("Диктовка работает и без этого - попробуйте ещё раз")
                            : L.t("Скачаем Ollama и модель к ней - 3.3 ГБ. Всё останется на этом компьютере")

                        // Всё в один Row, и это не вкусовщина: holder в
                        // SettingRow кладёт детей друг на друга, без раскладки.
                        // Когда полоса и надпись были отдельными детьми, они
                        // налезали одна на другую - видно только на снимке.
                        Row {
                            spacing: 12
                            anchors.verticalCenter: parent.verticalCenter

                            // Полоса - только пока качается, и той же краской,
                            // что точка: одно состояние одним цветом.
                            Rectangle {
                                visible: llmSetup.busy
                                anchors.verticalCenter: parent.verticalCenter
                                width: 130; height: 6; radius: 3; color: T.fill
                                Rectangle {
                                    width: parent.width * Math.max(0, Math.min(1, llmSetup.frac))
                                    height: parent.height; radius: 3; color: T.accent
                                    Behavior on width {
                                        NumberAnimation { duration: T.durBase * 1000
                                                          easing.type: Easing.OutCubic }
                                    }
                                }
                            }

                            // Значок состояния: точка цветом плюс слово. Одной
                            // точки мало - цвет читают не все и не всегда, а
                            // «скачано» однозначно.
                            Row {
                                spacing: 7
                                anchors.verticalCenter: parent.verticalCenter
                                Rectangle {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 8; height: 8; radius: 4
                                    color: llmSetup.tone
                                    Behavior on color {
                                        ColorAnimation { duration: T.durBase * 1000 }
                                    }
                                    // Пока качается - пульс: неподвижная точка
                                    // не отличается от готовой, а ждать минуты.
                                    SequentialAnimation on opacity {
                                        running: llmSetup.busy; loops: Animation.Infinite
                                        NumberAnimation { from: 0.4; to: 1; duration: 900
                                                          easing.type: Easing.InOutSine }
                                        NumberAnimation { from: 1; to: 0.4; duration: 900
                                                          easing.type: Easing.InOutSine }
                                    }
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: llmSetup.word
                                    font.family: T.sans; font.pixelSize: T.tXs
                                    font.weight: Font.Medium
                                    color: llmSetup.tone
                                }
                            }

                            FlowButton {
                                anchors.verticalCenter: parent.verticalCenter
                                visible: !llmSetup.busy && !llmSetup.ready
                                label: llmSetup.failed ? L.t("Ещё раз") : L.t("Установить")
                                kind: "primary"
                                onClicked: {
                                    llmSetup.failed = false;
                                    llmSetup.busy = true;
                                    llmSetup.stage = "начинаю";
                                    llmSetup.frac = 0;
                                    llmSetup.total = 0;
                                    B.llmInstall();
                                }
                            }
                        }

                        Connections {
                            target: B
                            function onLlmStage(stage, frac, total) {
                                llmSetup.busy = true;
                                llmSetup.stage = stage;
                                llmSetup.frac = frac;
                                llmSetup.total = total;
                            }
                            function onLlmDone(ok) {
                                llmSetup.busy = false;
                                llmSetup.ready = ok;
                                llmSetup.failed = !ok;
                            }
                        }
                    }

                    // Адрес и модель - для тех, у кого Ollama своя и настроена
                    // не по умолчанию. Показываем только когда полировка
                    // включена и установка уже не нужна: настройка выключенного
                    // и недоустановленного - это шум.
                    SettingRow {
                        visible: llmToggle.value && llmSetup.ready
                        title: L.t("Адрес Ollama")
                        FlowInput {
                            width: 220
                            text: B.get("llm.url") || ""
                            onEdited: (t) => B.set("llm.url", t)
                        }
                    }
                    SettingRow {
                        visible: llmToggle.value && llmSetup.ready
                        title: L.t("Модель Ollama")
                        subtitle: L.t("Оставьте пусто - найдём подходящую сами")
                        FlowInput {
                            width: 220
                            text: B.get("llm.model") || ""
                            onEdited: (t) => B.set("llm.model", t)
                        }
                    }
                }

                SectionTitle { text: L.t("Вставка") }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: L.t("Как вставлять текст")
                        subtitle: L.t("«Сразу целиком» - мгновенно, подходит почти везде. ")
                                  + L.t("«По одной букве» медленнее, зато доходит туда, куда первое не доходит")
                        Segmented {
                            options: B.insertOptions
                            value: B.get("insert_mode")
                            onPicked: (v) => B.set("insert_mode", v)
                        }
                    }
                    // «Освобождать память» убрано: владелец сказал «не нужно», и
                    // это правда настройка ради настройки. Умолчание было
                    // «держать всегда», то есть строка ничего не делала у всех,
                    // кто её не трогал; тому, кто диктует, лишние 370 МБ дешевле
                    // двух секунд ожидания. Ключ `unload_after_min` остался в
                    // конфиге - у кого выставлено, у того и работает.
                    ToggleRow {
                        title: L.t("Продолжать мысль")
                        subtitle: L.t("Диктуете вторую фразу сразу за первой - программа поставит ")
                                  + L.t("пробел и не начнёт её с заглавной посреди предложения")
                        path: "smart_join"
                    }
                    // Знаки препинания. Модель по умолчанию их не ставит, и
                    // это выбор между «мгновенно правилами» и «умнее моделью».
                    SettingRow {
                        first: true
                        title: L.t("Насколько править")
                        subtitle: L.t("«Ничего» - как услышали. «Слегка» - знаки и словарь. ")
                                  + L.t("«Обычно» - плюс убрать бубнёж. «Сильно» - плюс ")
                                  + L.t("правка текста моделью, но это дольше")
                        Segmented {
                            options: [{label: L.t("ничего"), value: "none"},
                                      {label: L.t("слегка"), value: "light"},
                                      {label: L.t("обычно"), value: "medium"},
                                      {label: L.t("сильно"), value: "high"}]
                            value: B.get("cleanup") || "medium"
                            onPicked: (v) => B.set("cleanup", v)
                        }
                    }
                    // Ответ на «чем давить в вайб-кодинге». Не вставкой в
                    // редактор - вставлять мы и так умеем. Бедой было другое:
                    // модель обучена на обычной речи и пишет «джейсон» словами.
                    SettingRow {
                        title: L.t("Язык интерфейса")
                        subtitle: L.t("Распознавание остаётся русским - меняются только надписи")
                        Segmented {
                            options: [{label: "Русский", value: "ru"},
                                      {label: "English", value: "en"}]
                            value: B.get("ui_language") || "ru"
                            onPicked: (v) => B.set("ui_language", v)
                        }
                    }
                    SettingRow {
                        title: L.t("Технические термины")
                        subtitle: L.t("«джейсон» станет JSON, «гитхаб» - GitHub, ")
                                  + L.t("«пул реквест» - pull request. Сто терминов ")
                                  + L.t("разом; попадут в «Слова», можно править поштучно")
                        Segmented {
                            options: [{label: L.t("выключены"), value: false},
                                      {label: L.t("включены"), value: true}]
                            value: B.get("tech_terms") || false
                            onPicked: (v) => B.setTechTerms(v)
                        }
                    }
                    SettingRow {
                        title: L.t("Заметки открываются")
                        subtitle: L.t("Продолжить прошлую или каждый раз начинать с чистого листа")
                        Segmented {
                            options: [{label: L.t("прошлой"), value: "last"},
                                      {label: L.t("новой"), value: "new"}]
                            value: B.get("notes_open") || "last"
                            onPicked: (v) => B.set("notes_open", v)
                        }
                    }
                    // «Останавливать музыку» убрано из настроек: владелец
                    // сказал «переключателей слишком много», и этот - первый
                    // кандидат. Он выключает то, чего человек всё равно не
                    // замечает: музыка встаёт на паузу на время фразы и сама
                    // возвращается, а если не играла - ничего не происходит.
                    // Работает по-прежнему всегда; ключ `pause_music` остался.
                    SettingRow {
                        title: L.t("Знаки препинания")
                        subtitle: punctBox.ready
                            ? L.t("Модель скачана - ставит запятые по смыслу и слышит вопрос. ")
                              + L.t("Правила проще, но не ошибаются на редких словах")
                            : L.t("Правила ставят запятые перед «что», «если», «который». ")
                              + L.t("Модель умнее: понимает смысл фразы. ") + punctBox.note
                        Row {
                            spacing: 8
                            Segmented {
                                options: [{label: L.t("правила"), value: "rules"},
                                          {label: L.t("модель"), value: "model"}]
                                value: B.get("punctuation") || "rules"
                                enabled: punctBox.ready
                                opacity: enabled ? 1 : 0.45
                                onPicked: (v) => B.set("punctuation", v)
                            }
                            FlowButton {
                                visible: !punctBox.ready
                                label: punctBox.busy ? L.t("Качается…") : L.t("Скачать 30 МБ")
                                enabled: !punctBox.busy
                                onClicked: { punctBox.busy = true; B.punctModelInstall() }
                            }
                        }
                        Item {
                            id: punctBox
                            property bool ready: B.punctModelReady()
                            property bool busy: B.punctBusy()
                            property string note: B.punctModelNote()
                            Connections {
                                target: B
                                function onChanged() {
                                    punctBox.ready = B.punctModelReady();
                                    punctBox.busy = B.punctBusy();
                                    punctBox.note = B.punctModelNote();
                                }
                            }
                        }
                    }
                    // Было поле, куда вписывали «telegram.exe» через запятую.
                    // Владелец спросил, откуда человеку взять это имя, - и
                    // вопрос был единственно верный: ниоткуда. Теперь список
                    // собирается из запущенных программ, а имя exe остаётся
                    // внутри и наружу не показывается.
                    SettingRow {
                        title: L.t("Отправлять сообщение")
                        subtitle: L.t("После вставки нажимать Enter - для мессенджеров. ")
                                  + L.t("Выберите из запущенных программ. ")
                                  + L.t("Голосовое «нажми энтер» работает и без этого, везде")
                        Row {
                            spacing: 8
                            Select {
                                id: appPick
                                width: 230
                                options: apps.list
                                value: apps.list.length ? apps.list[0].value : ""
                            }
                            FlowButton {
                                label: L.t("Добавить")
                                enabled: apps.list.length > 0
                                onClicked: B.addAutoEnterApp(appPick.value)
                            }
                        }
                        Item {
                            id: apps
                            property var list: B.runningApps()
                            // Перечитываем по сигналу, а не по таймеру: список
                            // меняется, когда человек что-то запустил, и в этот
                            // момент он не смотрит в наше окно.
                            Connections {
                                target: B
                                function onChanged() { apps.list = B.runningApps() }
                            }
                        }
                    }
                    Repeater {
                        model: B.autoEnterApps
                        SettingRow {
                            title: modelData.label
                            subtitle: modelData.label !== modelData.exe ? modelData.exe : ""
                            FlowButton {
                                label: L.t("Убрать")
                                onClicked: B.removeAutoEnterApp(modelData.exe)
                            }
                        }
                    }
                    ToggleRow {
                        title: L.t("Пробел в конце")
                        subtitle: L.t("Чтобы следующая фраза не слиплась с этой")
                        path: "append_space"
                    }
                    ToggleRow {
                        title: L.t("Не трогать скопированное")
                        subtitle: L.t("Вернём на место то, что вы копировали до диктовки")
                        path: "restore_clipboard"
                    }
                }

                SectionTitle { text: L.t("Распознавание") }
                Card {
                    width: parent.width
                    // Переключатель, а не список с карточками и кнопками
                    // скачивания. Моделей осталось две, и обе - GigaAM: выбирать
                    // тут нечего, кроме «побыстрее» и «поаккуратнее». Отдельная
                    // страница под два варианта - это лишний экран и лишний
                    // повод задуматься там, где думать не о чем.
                    SettingRow {
                        first: true
                        title: L.t("Модель")
                        subtitle: L.t("Обычная подходит почти всем. Внимательная чуть медленнее, ")
                                  + L.t("но аккуратнее с окончаниями и редкими словами. ")
                                  + L.t("Переключается на ходу - старая работает, пока грузится новая")
                        Segmented {
                            options: B.modelOptions
                            value: B.get("model")
                            onPicked: (v) => B.setModel(v)
                        }
                    }
                    // Разбор на ходу. Раньше жил только в config.json, хотя
                    // это он делает длинную диктовку быстрой: выключить его
                    // человек не мог, а понять, почему пятнадцать минут речи
                    // готовы так же быстро, как полминуты, - тем более.
                    ToggleRow {
                        title: L.t("Разбирать речь на ходу")
                        subtitle: L.t("Программа начинает работать, пока вы ещё говорите. ")
                                  + L.t("Тогда ждать после клавиши почти не приходится, ")
                                  + L.t("даже если диктовали долго")
                        path: "stream_asr"
                    }
                    SettingRow {
                        title: L.t("Устройство")
                        subtitle: L.t("Оставьте «авто» - программа выберет сама")
                        Segmented {
                            options: B.deviceOptions
                            value: B.get("device")
                            onPicked: (v) => B.setRestart("device", v)
                        }
                    }

                    // Что лежит на диске. Строка отвечает на два вопроса
                    // сразу: сколько места занято и что будет, если
                    // переключиться на вторую модель (скачается 238 МБ, и
                    // лучше знать это заранее, чем в дороге).
                    Repeater {
                        model: modelDisk.rows
                        SettingRow {
                            title: modelData.title
                            subtitle: modelData.active
                                ? L.t("используется") + " · " + modelData.onDiskMb + " " + L.t("МБ на диске")
                                : modelData.downloading
                                  ? L.t("качается…")
                                  : modelData.installed
                                    ? L.t("скачана, лежит про запас") + " · " + modelData.onDiskMb + " " + L.t("МБ")
                                    : L.t("не скачана - скачается") + " " + modelData.sizeMb + " " + L.t("МБ при первом включении")
                            FlowButton {
                                visible: !modelData.active && !modelData.downloading
                                label: modelData.installed ? L.t("Удалить") : L.t("Скачать")
                                onClicked: modelData.installed
                                    ? B.deleteModel(modelData.id)
                                    : B.downloadModel(modelData.id)
                            }
                        }
                    }
                    Item {
                        id: modelDisk
                        property var rows: B.modelsInfo()
                        Connections {
                            target: B
                            function onModelsChanged() { modelDisk.rows = B.modelsInfo() }
                            function onChanged() { modelDisk.rows = B.modelsInfo() }
                        }
                    }
                }

                SectionTitle { text: L.t("Вид") }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: L.t("Оформление")
                        subtitle: L.t("«Система» - как в Windows")
                        Segmented {
                            options: B.themeOptions
                            value: B.get("theme")
                            onPicked: (v) => B.set("theme", v)
                        }
                    }
                    // Было «Расположение: карточками / строками». Владелец
                    // спросил «расположение ЧЕГО?» и сам же ответил точнее нас:
                    // разница только в фоне у элементов, ничего никуда не
                    // переставляется. Так и называем.
                    //
                    // Заодно ушла ошибка в подписи: там стояло «карточками - как
                    // сейчас», и при выбранных строках это была прямая ложь.
                    // Текст, который знает про выбор, обязан от него зависеть -
                    // либо не упоминать его вовсе, как здесь.
                    SettingRow {
                        title: L.t("Фон под настройками")
                        subtitle: L.t("С фоном настройки лежат карточками, без фона - ")
                                  + L.t("строками через линию. Второе плотнее и спокойнее")
                        Segmented {
                            options: [{label: L.t("есть"), value: "cards"},
                                      {label: L.t("нет"), value: "lines"}]
                            value: B.get("layout") || "cards"
                            onPicked: (v) => B.set("layout", v)
                        }
                    }
                    SettingRow {
                        title: L.t("Полоска во время записи")
                        subtitle: L.t("Полоска с волной: снизу экрана, сверху - или не показывать совсем. ")
                                  + L.t("Её можно перетащить мышью в любое место")
                        Segmented {
                            options: B.pillOptions
                            value: B.get("overlay_position")
                            onPicked: (v) => B.set("overlay_position", v)
                        }
                    }
                    // Звук переехал сюда из раздела «Система». Раздела больше
                    // нет: после того как «Запускать вместе с Windows» стало
                    // всегда включённым, в нём осталась одна эта строка, а
                    // заголовок над одной строкой - это заголовок ради
                    // заголовка. Владелец назвал раздел слишком пустым, и
                    // правильным ответом было расформировать его, а не
                    // дописывать туда что-нибудь.
                    ToggleRow {
                        title: L.t("Звуковые сигналы")
                        subtitle: L.t("Тихий сигнал, когда запись началась и закончилась")
                        path: "sounds"
                    }
                }
            }

            // ===== Слова =====
            // Бывшие Словарь + Замены. Словарь Dragon продаёт за 700 долларов -
            // наш виден и объяснён, а не спрятан за термином.
            Column {
                visible: win.page === "Слова"
                width: parent.width
                spacing: 16

                SectionTitle { text: L.t("Свои слова") }
                Text {
                    width: parent.width
                    text: L.t("Слова, которые программа слышит, но пишет неправильно: ")
                          + L.t("фамилии, названия, термины. По одному на строку.")
                    wrapMode: Text.WordWrap
                    font.family: T.sans; font.pixelSize: T.tSm
                    color: T.textSecondary
                    lineHeight: 1.4
                }
                Card {
                    width: parent.width
                    height: 300
                    Item {
                        width: parent.width
                        height: 300
                        Flickable {
                            anchors.fill: parent
                            anchors.margins: 14
                            clip: true
                            contentHeight: dict.implicitHeight
                            TextEdit {
                                id: dict
                                width: parent.width
                                text: B.dictionaryText
                                font.family: T.mono; font.pixelSize: T.tSm
                                color: T.text
                                selectByMouse: true
                                selectionColor: Qt.rgba(T.accent.r, T.accent.g, T.accent.b, 0.30)
                                selectedTextColor: T.text
                                wrapMode: TextEdit.NoWrap
                                onTextChanged: if (activeFocus) B.setDictionary(text)
                            }
                        }
                    }
                }

                SectionHeader {
                    text: L.t("Подстановки"); buttonLabel: L.t("Добавить"); buttonKind: "primary"
                    onAction: snips.add()
                }
                // Пояснение ПЕРЕД таблицей, а не после неё.
                //
                // Владелец сказал: «подстановки выглядят пусто и непонятно;
                // нужно два поля рядом со стрелкой - слева что говорю, справа
                // на что заменить». Поля со стрелкой были и раньше, но увидеть
                // их можно было, только нажав «Добавить»: пустая таблица
                // показывала одну серую строчку, а объяснение лежало ПОД ней,
                // то есть читалось после того, как непонятно уже стало.
                Note {
                    text: L.t("Слева - что вы говорите, справа - что вставится вместо этого. ")
                          + L.t("Скажете «моя почта» - появится адрес.")
                          + (snips.blanks > 0 ? "  " + L.t("Пустых строк:") + " " + snips.blanks
                                                + " - " + L.t("они не сохранятся.") : "")
                }
                PairTable {
                    id: snips
                    width: parent.width
                    storeKey: "snippets"
                    // Пустая таблица показывает не серую надпись, а живую
                    // строку: два поля и стрелку между ними. Так видно, что
                    // это форма, а не сообщение об ошибке.
                    showBlankRow: true
                    emptyText: "пока пусто - нажмите «Добавить»"
                    leftPlaceholder: "моя почта"
                    rightPlaceholder: "roman@example.com"
                }
                // «Не надо» на находке запоминается навсегда - иначе программа
                // спрашивала бы одно и то же каждую неделю. Но дверь назад
                // нужна: промах мыши не должен стоить находки, о которой потом
                // не узнаешь. Строки нет, пока отказываться было не от чего.
                Row {
                    visible: B.declinedCount > 0
                    spacing: 10
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: L.t("Отклонённых находок:") + " " + B.declinedCount
                        font.family: T.sans; font.pixelSize: T.tSm
                        color: T.textMuted
                    }
                    FlowButton {
                        label: L.t("Предложить снова")
                        onClicked: B.clearDeclined()
                    }
                }

                // «Тон под приложение» со страницы убран.
                //
                // Владелец сказал коротко: «никто не будет это заполнять». Он
                // прав, и правота эта устроена так: чтобы правило заработало,
                // надо знать имя exe чужой программы, придумать слово для тона
                // и держать в голове, что всё вместе требует установленной
                // правки текста. Три условия ради того, чтобы письмо вышло
                // построже, - это цена, которую платят единицы.
                //
                // Код `tone_rules` остаётся живым: у кого правила заведены -
                // работают, из резервной копии восстанавливаются. Мы убрали
                // форму, а не возможность.

                // ---- Преобразования ----
                // Список, который открывается по сочетанию «Преобразовать
                // текст». Готовые написали мы, свои пишет человек - и до сих
                // пор мог написать их только в config.json, то есть никак.
                SectionHeader {
                    text: L.t("Свои преобразования")
                    buttonLabel: tf.full ? "" : L.t("Добавить")
                    buttonKind: "primary"
                    onAction: tf.add()
                }
                TransformTable {
                    id: tf
                    width: parent.width
                }
                Note {
                    text: L.t("Выделите текст, нажмите сочетание «Преобразовать текст» - ")
                          + L.t("и выберите нужное. Слева название, справа что сделать: ")
                          + L.t("пишите словами, как объяснили бы человеку.")
                          + (tf.full ? "  " + L.t("Больше не поместится: список выбирают цифрами.") : "")
                          + (tf.blanks > 0 ? "  " + L.t("Незаполненных строк:") + " " + tf.blanks
                                             + " - " + L.t("они не сохранятся.") : "")
                }

                SectionTitle { text: L.t("Готовые преобразования") }
                Card {
                    width: parent.width
                    Repeater {
                        model: presets.rows
                        SettingRow {
                            first: index === 0
                            title: L.t(modelData.title)
                            subtitle: L.t(modelData.hint)
                            Toggle {
                                value: modelData.shown
                                onToggled: (v) => B.setTransformShown(modelData.id, v)
                            }
                        }
                    }
                    Item {
                        id: presets
                        property var rows: B.transformPresets()
                    }
                }
                Note {
                    text: L.t("Выключенное просто не показывается в списке - ")
                          + L.t("чтобы не искать своё среди того, чем не пользуетесь.")
                }
            }

            // ===== История =====
            Column {
                visible: win.page === "История"
                width: parent.width
                spacing: 12

                // Перечитываем при каждом входе: продиктовал при открытом окне,
                // зашёл сюда - запись уже на месте, без кнопки «Обновить».
                onVisibleChanged: if (visible) hist.reload()

                Card {
                    width: parent.width
                    // Главный выключатель первым, его подстройка - следом.
                    // Было наоборот, и получалось два огреха разом: «Забывать
                    // старое» стояло выше «Вести историю», от которого оно
                    // зависит, а разделительная линия рисовалась вплотную к
                    // верхнему краю карточки - flag first: true стоял у второй
                    // строки вместо первой.
                    ToggleRow {
                        first: true
                        title: L.t("Вести историю")
                        subtitle: L.t("Выключите - и программа не будет ничего запоминать")
                        path: "history"
                    }
                    // «Забывать старое» убрано.
                    //
                    // Владелец: «лишнее, если историю и так можно выключить
                    // целиком». Четыре срока хранения - это вопрос, на который
                    // человек не может ответить, потому что не знает, что
                    // выберет через полгода. А выключатель выше отвечает на
                    // тот же страх сразу и без вариантов.
                    //
                    // Чистка по сроку осталась в коде и работает у тех, кто
                    // уже выставил `history_days`: молча забыть чужую настройку
                    // хуже, чем убрать форму.
                }

                // Поиск слева, действия справа - как строка поиска в app-shell.
                Item {
                    width: parent.width
                    height: 30
                    FlowInput {
                        id: histSearch
                        anchors { left: parent.left; right: histBtns.left; rightMargin: 10 }
                        placeholder: L.t("Найти в надиктованном…")
                        onEdited: (t) => hist.apply(t)
                    }
                    Row {
                        id: histBtns
                        anchors.right: parent.right
                        spacing: 6
                        FlowButton { label: L.t("Обновить"); onClicked: hist.reload() }
                        FlowButton { label: L.t("Очистить"); kind: "danger"
                            onClicked: { B.clearHistory(); hist.reload() } }
                    }
                }
                Card {
                    width: parent.width
                    height: 380
                    Item {
                        width: parent.width
                        height: 380
                        ListView {
                            id: hist
                            anchors.fill: parent
                            anchors.margins: 14
                            clip: true
                            spacing: 10
                            property var all: []
                            property string note: ""
                            function reload() {
                                var d = B.historyData();
                                all = d.rows;
                                note = d.note;
                                apply(histSearch.text);
                            }
                            function apply(q) {
                                q = (q || "").toLowerCase().trim();
                                if (!q) { model = all; return }
                                var out = [];
                                for (var i = 0; i < all.length; i++)
                                    if (String(all[i].text).toLowerCase().indexOf(q) !== -1)
                                        out.push(all[i]);
                                model = out;
                            }
                            // Грузит onVisibleChanged страницы, не сборка окна.
                            delegate: Column {
                                width: hist.width
                                spacing: 3
                                Text {
                                    // Метаданные моноширинным - голос терминала.
                                    text: modelData.ts + "   ·   " + modelData.sec + L.t(" с")
                                    font.family: T.mono; font.pixelSize: T.t2xs
                                    color: T.textMuted
                                }
                                Text {
                                    width: parent.width
                                    text: modelData.text
                                    wrapMode: Text.WordWrap
                                    font.family: T.sans; font.pixelSize: T.tBase
                                    color: hma.containsMouse ? T.textSecondary : T.text
                                    // Клик - в буфер: переиспользовать вчерашнюю
                                    // диктовку без выделения мышью.
                                    MouseArea {
                                        id: hma
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: B.copyText(modelData.text)
                                    }
                                }
                            }
                            Text {
                                anchors.centerIn: parent
                                visible: hist.count === 0 && histSearch.text !== ""
                                text: L.t("Ничего не нашлось.")
                                font.family: T.sans; font.pixelSize: T.tSm
                                color: T.textFaint
                            }
                            // Пусто и без поиска - до сих пор здесь не было
                            // ничего: рамка в пол-экрана и внутри пустота. Это
                            // читается как поломка, а не как «вы ещё не
                            // начали». Заодно единственное место, где можно
                            // сказать про клик: список без записей объяснить
                            // самим списком нельзя.
                            Text {
                                anchors.centerIn: parent
                                width: parent.width - 48
                                horizontalAlignment: Text.AlignHCenter
                                wrapMode: Text.WordWrap
                                visible: hist.count === 0 && histSearch.text === ""
                                text: L.t("Здесь появится всё, что вы надиктуете.
Клик по строке скопирует её.")
                                font.family: T.sans; font.pixelSize: T.tSm
                                color: T.textMuted
                                lineHeight: 1.5
                            }
                        }
                    }
                }
                Note { text: hist.note }
            }

            // ===== Статистика =====
            Column {
                id: statsPage
                visible: win.page === "Статистика"
                width: parent.width
                spacing: 16
                property var s: ({})
                // Страница скрыта при старте (окно открывается на «Главной»):
                // считать статистику при сборке окна незачем, входа хватит.
                onVisibleChanged: if (visible) s = B.stats()

                // Пусто - зовём попробовать, а не показываем пять нулей.
                //
                // Так уже сделано на «Главной», и это было верно: шеренга нулей
                // читается как «программа сломана», а не как «вы ещё не
                // начали». Здесь до этого нулей было пять подряд, да ещё и
                // «пока пусто» дважды - в середине графика и подписью под ним.
                Card {
                    width: parent.width
                    visible: statsPage.s.hasData === false
                    Item {
                        width: parent.width
                        implicitHeight: 92
                        Text {
                            anchors.centerIn: parent
                            width: parent.width - 36
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            // Не повторяем подзаголовок страницы, он прямо над
                            // этой карточкой. Здесь - что сделать и что будет
                            // считаться. И сочетание под рукой, чтобы за ним не
                            // ходить на другую страницу.
                            text: (B.pretty(B.get("hotkey_hold") || "")
                                   ? L.t("Зажмите ") + B.pretty(B.get("hotkey_hold")) + L.t(" и скажите что-нибудь.")
                                   : L.t("Продиктуйте что-нибудь."))
                                  + "
Счёт слов, времени и дней подряд пойдёт с первой же диктовки."
                            font.family: T.sans
                            font.pixelSize: T.tSm
                            color: T.textMuted
                            lineHeight: 1.5
                        }
                    }
                }

                SectionTitle { text: L.t("Итого"); visible: statsPage.s.hasData === true }
                Card {
                    width: parent.width
                    visible: statsPage.s.hasData === true
                    StatRow { first: true; title: L.t("Диктовок")
                        subtitle: L.t("Сколько раз вы говорили вместо того, чтобы печатать")
                        value: statsPage.s.dictations || "-" }
                    StatRow { title: L.t("Слов надиктовано"); subtitle: L.t("За всё время")
                        value: statsPage.s.words || "-" }
                    StatRow { title: L.t("Наговорено"); subtitle: L.t("Столько вы говорили")
                        value: statsPage.s.seconds || "-" }
                    StatRow { title: L.t("Сэкономлено")
                        subtitle: L.t("Печатать это руками - примерно ")
                                  + (statsPage.s.typingWpm || 40)
                                  + L.t(" слов в минуту. Столько вы сберегли")
                        value: statsPage.s.saved_sec || "-" }
                    StatRow { visible: statsPage.s.speedOk === true
                        title: L.t("Ваша скорость")
                        subtitle: L.t("Слов в минуту под запись - замер по вашей истории")
                        value: (statsPage.s.userWpm || 0) + " сл/мин" }
                    StatRow { title: L.t("Дней подряд")
                        subtitle: L.t("Диктовали каждый день без пропуска")
                        value: statsPage.s.streak || "-" }
                }

                // ---- Как вы говорите ----
                //
                // Считается по накопленной истории, здесь же, на этой машине.
                // Пока данных мало - раздел не показывается вовсе: сказать
                // «ваше любимое слово - «который»» по трём диктовкам значит
                // соврать с умным видом.
                SectionTitle { text: L.t("Как вы говорите"); visible: ins.d.rows > 0 }
                Card {
                    width: parent.width
                    visible: ins.d.rows > 0
                    Item {
                        id: ins
                        property var d: ({rows: 0})
                        Component.onCompleted: d = B.insights()
                    }
                    Connections {
                        target: statsPage
                        function onVisibleChanged() {
                            if (statsPage.visible) ins.d = B.insights();
                        }
                    }

                    StatRow {
                        first: true
                        visible: ins.d.persona !== ""
                        title: L.t("Ваша манера")
                        subtitle: ins.d.persona || ""
                        value: ""
                    }
                    StatRow {
                        visible: ins.d.top_word !== ""
                        title: L.t("Любимое слово")
                        subtitle: L.t("Чаще всего повторяется в ваших диктовках")
                        value: ins.d.top_word + " · " + ins.d.top_word_n
                    }
                    StatRow {
                        visible: ins.d.phrase !== ""
                        title: L.t("Присказка")
                        subtitle: L.t("Три слова подряд, которые вы говорите чаще прочих")
                        value: ins.d.phrase
                    }
                    StatRow {
                        visible: ins.d.hourText !== ""
                        title: L.t("Часы пик")
                        subtitle: L.t("Когда вы диктуете больше всего")
                        value: ins.d.hourText
                    }
                    // Было «Программа исправила: 10». Владелец спросил, что ему
                    // с этим числом делать, - и вопрос справедлив: число само
                    // по себе не значит ничего. Десять исправлений это много
                    // или мало? Хорошо это или плохо? Ответа не было.
                    //
                    // Теперь строка отвечает на «что делать»: если ниже есть
                    // слова, которые путаются, - вот они, с кнопкой. Если нет,
                    // число значит «всё в порядке, чинить нечего».
                    StatRow {
                        visible: ins.d.fixed > 0
                        title: L.t("Программа исправила")
                        subtitle: (ins.d.pairs || []).length > 0
                            ? L.t("Столько слов она поправила за вас. Что путается чаще - ниже")
                            : L.t("Столько слов она поправила за вас. Ничего чинить не нужно")
                        value: ins.d.fixed + ""
                    }
                    // Слово, которое путается чаще прочих, - и кнопка, чтобы
                    // научить программу за одно нажатие. Открывать «Слова» и
                    // вспоминать написание не нужно: мы его уже знаем.
                    Repeater {
                        model: (ins.d.pairs || []).slice(0, 3)
                        SettingRow {
                            title: L.t("Путается «") + modelData.heard + "»"
                            subtitle: L.t("Вы диктуете «") + modelData.fixed + L.t("», а слышится ")
                                      + L.t("иначе. Уже ") + modelData.n + L.t(" раз")
                            FlowButton {
                                label: L.t("Научить")
                                onClicked: B.addToDictionary(modelData.heard,
                                                             modelData.fixed)
                            }
                        }
                    }
                    // Пока не набралось - говорим сколько ещё, а не молчим.
                    StatRow {
                        visible: !ins.d.enough
                        title: L.t("Пока считаем")
                        subtitle: L.t("Про любимое слово и присказку скажем, когда ")
                                  + L.t("наберётся побольше диктовок")
                        value: ins.d.words + " слов"
                    }
                }

                SectionTitle { text: L.t("Куда диктуете"); visible: (ins.d.where || []).length > 0 }
                Card {
                    width: parent.width
                    visible: (ins.d.where || []).length > 0
                    Repeater {
                        model: ins.d.where || []
                        StatRow {
                            first: index === 0
                            title: modelData.kind
                            subtitle: modelData.words + L.t(" слов за ")
                                      + modelData.count + " диктовок"
                            value: modelData.share + "%"
                        }
                    }
                }

                SectionTitle { text: L.t("По дням"); visible: statsPage.s.hasData === true }
                Card {
                    width: parent.width
                    visible: statsPage.s.hasData === true
                    Item {
                        width: parent.width
                        implicitHeight: 120 + 28 + 14
                        BarChart {
                            id: chart
                            x: 24; y: 14
                            width: parent.width - 48
                            height: 120
                            values: statsPage.s.values || []
                        }
                        Text {
                            anchors { left: chart.left; top: chart.bottom; topMargin: 8 }
                            text: statsPage.s.range || ""
                            font.family: T.mono; font.pixelSize: T.t2xs
                            color: T.textMuted
                        }
                    }
                }
            }

            // ===== О программе =====
            Column {
                visible: win.page === "О программе"
                width: parent.width
                spacing: 16

                Card {
                    width: parent.width
                    Item {
                        width: parent.width
                        implicitHeight: aboutHero.implicitHeight + 40
                        Column {
                            id: aboutHero
                            anchors { left: parent.left; right: parent.right; top: parent.top
                                      leftMargin: 20; rightMargin: 20; topMargin: 20 }
                            spacing: 10
                            // Тот же вордмарк, что на панели, только крупнее:
                            // это витрина продукта, а не строка меню.
                            Wordmark { box: 34; nameSize: T.t2xl }
                            Text {
                                width: aboutHero.width
                                text: L.t("Диктовка, которая работает без интернета.")
                                font.family: T.sans; font.pixelSize: T.tMd
                                font.weight: Font.DemiBold
                                color: T.text
                            }
                            Text {
                                width: aboutHero.width
                                wrapMode: Text.WordWrap
                                // Отрицательная гарантия сильнее обещания: не
                                // «мы защищаем данные», а «уходить им некуда».
                                text: L.t("Голос не покидает этот компьютер - не потому что мы обещаем, ")
                                      + L.t("а потому что некуда: интернет нужен один раз, чтобы скачать ")
                                      + L.t("модель, и ещё чтобы проверять обновления. Поэтому диктовка ")
                                      + L.t("работает в поезде, на даче и когда интернет упал.")
                                font.family: T.sans; font.pixelSize: T.tSm
                                color: T.textSecondary
                                lineHeight: 1.5
                            }
                        }
                    }
                }

                SectionTitle { text: L.t("Что важно знать") }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: L.t("Первые слова не теряются")
                        subtitle: L.t("Микрофон слушает чуть раньше, чем вы нажали клавишу")
                    }
                    SettingRow {
                        title: L.t("Ничего не переписывает")
                        subtitle: L.t("Чистка вычёркивает лишнее из сказанного и не добавляет ни слова от себя")
                    }
                    SettingRow {
                        title: L.t("Не мешает компьютеру")
                        subtitle: L.t("Пока вы не диктуете, программа ничего не делает и в интернет не ходит")
                    }
                }

                // Как обновлялось. Раньше человек видел номер версии и всё:
                // что в ней изменилось и чем она отличается от вчерашней -
                // узнать было неоткуда, а обновлятор предлагал обновиться,
                // не говоря ради чего.
                // Копия личного. Словарь и замены копятся годами, живут в одном
                // файле рядом с программой и не воспроизводятся ничем: снёс
                // Windows - и нет их. Раздел 0.8 плана уже ловил этот риск на
                // самом проекте («работа висит на одном диске»), на данных
                // владельца вывод тот же.
                SectionTitle { text: L.t("Свои слова и настройки") }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: L.t("Сохранить в файл")
                        subtitle: L.t("Словарь, замены, тон и сочетания. Пригодится при переустановке ")
                                  + L.t("и на втором компьютере")
                        Row {
                            spacing: 8
                            FlowButton {
                                label: L.t("Сохранить")
                                onClicked: B.exportData(false)
                            }
                            FlowButton {
                                label: L.t("Вместе с историей")
                                onClicked: B.exportData(true)
                            }
                        }
                    }
                    SettingRow {
                        title: L.t("Загрузить из файла")
                        subtitle: L.t("Добавит к тому, что есть. Ваши сочетания и слова не пропадут")
                        FlowButton {
                            label: L.t("Загрузить")
                            onClicked: B.importData()
                        }
                    }
                }

                // Записи, которые не удалось распознать. Раздел появляется
                // только когда такие есть: у человека, у которого всё хорошо,
                // он не должен даже мелькать.
                SectionTitle { text: L.t("Несохранённые записи"); visible: saved.count > 0 }
                Card {
                    width: parent.width
                    visible: saved.count > 0
                    Column {
                        id: saved
                        width: parent.width
                        property var rows: []
                        property int count: rows.length
                        Component.onCompleted: rows = B.savedRecordings()
                        Connections {
                            target: B
                            function onChanged() { saved.rows = B.savedRecordings() }
                        }

                        Item {
                            width: parent.width
                            implicitHeight: savedNote.implicitHeight + 28
                            Text {
                                id: savedNote
                                anchors { left: parent.left; right: parent.right
                                          top: parent.top
                                          leftMargin: 24; rightMargin: 24; topMargin: 14 }
                                wrapMode: Text.WordWrap
                                text: L.t("Распознать не вышло, но речь цела. Нажмите «Распознать» - ")
                                      + L.t("текст попадёт в буфер обмена, и его можно вставить куда нужно.")
                                font.family: T.sans; font.pixelSize: T.tXs
                                color: T.textMuted
                                lineHeight: 1.4
                            }
                        }

                        Repeater {
                            model: saved.rows
                            SettingRow {
                                title: modelData.name
                                subtitle: modelData.note
                                Row {
                                    spacing: 8
                                    FlowButton {
                                        label: L.t("Распознать")
                                        kind: "primary"
                                        onClicked: B.redoRecording(modelData.path)
                                    }
                                    FlowButton {
                                        label: L.t("Удалить")
                                        kind: "danger"
                                        onClicked: B.dropRecording(modelData.path)
                                    }
                                }
                            }
                        }
                    }
                }

                SectionTitle { text: L.t("Как обновлялось"); visible: history.count > 0 }
                Card {
                    width: parent.width
                    visible: history.count > 0
                    Column {
                        id: history
                        width: parent.width
                        property int count: rel.count
                        Repeater {
                            id: rel
                            model: B.changelog()
                            Item {
                                width: history.width
                                implicitHeight: relCol.implicitHeight + 32
                                // Волосяная линия между версиями, кроме первой:
                                // это список, а не набор карточек.
                                Rectangle {
                                    visible: index > 0
                                    width: parent.width - 48
                                    x: 24
                                    height: 1
                                    color: T.border
                                }
                                Column {
                                    id: relCol
                                    anchors { left: parent.left; right: parent.right
                                              top: parent.top
                                              leftMargin: 24; rightMargin: 24; topMargin: 16 }
                                    spacing: 6

                                    Row {
                                        spacing: 8
                                        Text {
                                            text: modelData.version
                                            font.family: T.sans; font.pixelSize: T.tSm
                                            font.weight: Font.DemiBold; color: T.text
                                        }
                                        // «Сейчас у вас» - единственное, ради
                                        // чего этот список открывают дважды.
                                        Rectangle {
                                            visible: modelData.current
                                            anchors.verticalCenter: parent.verticalCenter
                                            width: nowLbl.implicitWidth + 14
                                            height: 18
                                            radius: 9
                                            color: T.fill
                                            Text {
                                                id: nowLbl
                                                anchors.centerIn: parent
                                                text: L.t("сейчас у вас")
                                                font.family: T.sans; font.pixelSize: T.t2xs
                                                color: T.textSecondary
                                            }
                                        }
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: modelData.date
                                            font.family: T.mono; font.pixelSize: T.t2xs
                                            color: T.textMuted
                                        }
                                    }

                                    Text {
                                        width: relCol.width
                                        wrapMode: Text.WordWrap
                                        text: modelData.title
                                        visible: text !== ""
                                        font.family: T.sans; font.pixelSize: T.tXs
                                        color: T.textSecondary
                                        lineHeight: 1.4
                                    }

                                    Repeater {
                                        model: modelData.items
                                        Text {
                                            width: relCol.width
                                            wrapMode: Text.WordWrap
                                            text: "· " + modelData
                                            // Пункты в CHANGELOG.md пишутся с
                                            // полужирным зачином - «**Что
                                            // изменилось.** дальше подробности».
                                            // Без этой строки Qt рисовал
                                            // звёздочки буквально: список версий
                                            // был усыпан `**`. Зачин полужирным
                                            // не украшение - по нему список
                                            // просматривают глазами, не читая
                                            // целиком.
                                            textFormat: Text.MarkdownText
                                            font.family: T.sans; font.pixelSize: T.tXs
                                            color: T.textMuted
                                            lineHeight: 1.4
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                SectionTitle { text: L.t("Служебное") }
                Card {
                    width: parent.width
                    Item {
                        width: parent.width
                        implicitHeight: aboutText.implicitHeight + 48
                        Text {
                            id: aboutText
                            x: 24; y: 24
                            width: parent.width - 48
                            text: B.about()
                            font.family: T.mono; font.pixelSize: T.tXs
                            color: T.textSecondary
                            wrapMode: Text.WordWrap
                        }
                    }
                }
                Row {
                    spacing: 8
                    FlowButton { label: L.t("Папка приложения"); onClicked: B.openFolder() }
                    // Не имена файлов: рядом с «Папка приложения» они читались
                    // как список того, что лежит внутри, а не как кнопки. Куда
                    // они ведут, видно после нажатия - открывается тот же файл.
                    FlowButton { label: L.t("Файл настроек"); onClicked: B.openConfig() }
                    FlowButton { label: L.t("Журнал работы"); onClicked: B.openLog() }
                    FlowButton { label: L.t("Пройти знакомство заново")
                                 onClicked: B.restartOnboarding() }
                }
            }
        }
    }

    Text {
        id: footer
        anchors { left: side.right; leftMargin: 28; bottom: parent.bottom
                  bottomMargin: 10 }
        text: ""
        font.family: T.mono
        font.pixelSize: T.t2xs
        color: T.textMuted
    }
}
