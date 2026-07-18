// Окно настроек: боковое меню плюс страницы. Вёрстка целиком здесь, данные -
// в settings_qt.Backend (контекстное свойство `B`), токены - в `T`.
//
// Сохранение сразу по изменению, кнопки «Применить» нет намеренно: лишний шаг,
// о котором легко забыть.
//
// Дверей шесть, а не десять (исследование конкурентов, IMPROVEMENTS §2.3):
// Основное+Распознавание+Ввод слились в «Диктовку», Словарь+Замены - в
// «Слова». «Модели» с панели убраны - туда ведёт кнопка «Другие языки и
// модели»: человеку, который просто пишет письма, зоопарк моделей не нужен.

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
    readonly property var pages: ["Главная", "Диктовка", "Слова", "История",
                                  "Статистика", "О программе"]

    // Одна строка под заголовком отвечает на «что мне это даст» - правило
    // голоса бренда. У «Главной» вместо подписи говорит сама страница.
    // Страницы без записи (Главная говорит сама за себя, «О программе» - тоже)
    // просто отсутствуют: `subtitles[page] || ""` даёт пустую подпись, и
    // строка прячется. Заводить для них "" - два способа сказать одно.
    readonly property var subtitles: ({
        "Диктовка":    "Сочетания, микрофон и то, как появляется текст",
        "Модели":      "Кто именно превращает голос в текст",
        "Слова":       "Научите программу писать так, как нужно вам",
        "История":     "Всё, что вы надиктовали, - можно найти и вернуть",
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

            Repeater {
                model: win.pages
                NavItem {
                    label: modelData
                    icon: ic.forPage(modelData)
                    // «Модели» открываются из «Диктовки» - пока человек там,
                    // подсвечиваем дверь, через которую он вошёл.
                    active: win.page === modelData
                            || (modelData === "Диктовка" && win.page === "Модели")
                    onClicked: win.page = modelData
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
                            text: "Версия " + (upd.info.version || "")
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
                        text: "Обновить · " + (upd.info.size_mb || 0) + " МБ"
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
                text: "ДИКТОВКА"
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
                PageTitle { text: win.page === "Главная" ? home.greeting : win.page }
                Text {
                    width: parent.width
                    visible: text !== ""
                    text: win.subtitles[win.page] || ""
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
                property string greeting: "Главная"
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
                    var h = new Date().getHours();
                    greeting = h < 5 ? "Доброй ночи" : h < 12 ? "Доброе утро"
                             : h < 18 ? "Добрый день" : "Добрый вечер";
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
                                    text: "Вы диктовали это " + modelData.times
                                          + (modelData.kind !== "фраза" ? " — " + modelData.kind : "")
                                          + ". Дать короткую фразу?"
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
                                        placeholder: "как это называть"
                                    }
                                    FlowButton {
                                        label: "Запомнить"
                                        kind: "primary"
                                        onClicked: {
                                            B.acceptSuggestion(tipName.text, modelData.value);
                                            home.refreshTips();
                                        }
                                    }
                                    FlowButton {
                                        label: "Не надо"
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
                                    text: B.ready ? "Готов записывать" : "Просыпаюсь…"
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
                                      ? "Зажмите " + B.pretty(B.get("hotkey_hold"))
                                        + " и говорите. Отпустили — текст на месте."
                                      : B.pretty(B.get("hotkey_toggle") || "")
                                      ? "Нажмите " + B.pretty(B.get("hotkey_toggle"))
                                        + " и говорите. Нажмите ещё раз — текст на месте."
                                      : "Сочетание не назначено — задайте его на странице «Диктовка»."
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
                                text: "Работает в любом окне: письмо, чат, документ. "
                                      + "Голос не покидает этот компьютер."
                                font.family: T.sans
                                font.pixelSize: T.tSm
                                color: T.textMuted
                                lineHeight: 1.5
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
                        label: "сэкономлено"
                        value: home.st.saved_sec || "0 с"
                        hint: "печати руками — по вашим диктовкам"
                    }
                    Metric {
                        width: parent.cw
                        order: 1
                        label: "скорость"
                        value: home.st.speedOk ? home.st.speed : "—"
                        hint: home.st.speedOk
                              ? "быстрее, чем печатать руками"
                              : "наговорите минуту — посчитаем"
                    }
                    Metric {
                        width: parent.cw
                        order: 2
                        label: "надиктовано"
                        // Чистый счётчик слов - его и оживляем: бежит от нуля.
                        countTo: parseInt(home.st.words || "0")
                        hint: "слов за всё время"
                    }
                }

                SectionHeader { text: "ПОСЛЕДНЕЕ"; visible: home.hasData }

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
                            text: "Здесь появится то, что вы надиктуете.\nПопробуйте прямо сейчас — скажите что-нибудь."
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
                                        text: "нажмите, чтобы скопировать"
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

                SectionTitle { text: "Сочетания" }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: "Удерживать и говорить"
                        subtitle: "Самый простой способ. Можно назначить и боковую кнопку мыши"
                        HotkeyField { field: "hotkey_hold" }
                    }
                    SettingRow {
                        title: "Нажать и говорить"
                        subtitle: "Если диктуете долго и не хотите держать клавишу. Esc — отменить"
                        HotkeyField { field: "hotkey_toggle"; allowClear: true }
                    }
                    SettingRow {
                        title: "Править выделенное голосом"
                        // Привязка к самому тумблеру, а не к B.get: тумблер
                        // теперь на этой же странице, и подпись обязана
                        // меняться сразу, как его щёлкнули (B.get - слот без
                        // сигнала, он бы застыл на старом значении).
                        subtitle: llmToggle.value
                            ? "Выделите текст, зажмите, скажите «сделай короче», «переведи на английский», «исправь ошибки» - выделенное заменится"
                            : "Правка по указанию - это понимание смысла. Установите её ниже, одной кнопкой"
                        HotkeyField { field: "hotkey_command"; allowClear: true }
                    }
                    SettingRow {
                        title: "Отменить последнюю диктовку"
                        subtitle: "Уберёт вставленный текст, если вы после этого ничего не печатали"
                        HotkeyField { field: "undo_hotkey"; allowClear: true }
                    }
                }

                SectionTitle { text: "Микрофон" }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: "Микрофон"
                        subtitle: "Какой микрофон слушать"
                        Select {
                            options: B.micOptions
                            value: B.get("mic_device")
                            onPicked: (v) => B.set("mic_device", v)
                        }
                    }
                    ToggleRow {
                        title: "Не терять первое слово"
                        subtitle: "Микрофон наготове, поэтому начало фразы не обрежется"
                        path: "keep_mic_open"
                    }
                    SettingRow {
                        title: "Слышать начало заранее"
                        subtitle: "На случай, если начали говорить чуть раньше, чем нажали"
                        Slider {
                            from: 0; to: 1.5; stepSize: 0.1
                            value: B.get("pre_buffer_sec")
                            onMoved: (v) => B.set("pre_buffer_sec", v)
                        }
                    }
                    SettingRow {
                        title: "Не реагировать на случайные касания"
                        subtitle: "Задели клавишу мимоходом — записи не будет"
                        Slider {
                            from: 0.1; to: 1.5; stepSize: 0.1
                            value: B.get("min_record_sec")
                            onMoved: (v) => B.set("min_record_sec", v)
                        }
                    }
                }

                SectionTitle { text: "Чистка текста" }
                Card {
                    width: parent.width
                    ToggleRow {
                        first: true
                        title: "Убирать слова-паразиты"
                        subtitle: "«Ну вот, короче, я думаю, надо сделать» → «Я думаю, надо сделать»"
                        path: "remove_fillers"
                    }
                    ToggleRow {
                        title: "Голосовые команды"
                        subtitle: "Скажите «с новой строки» — и будет новая строка. Скажите «нажми энтер» в конце — сообщение отправится"
                        path: "voice_commands"
                    }
                    ToggleRow {
                        title: "Слышать вопрос"
                        subtitle: "«Ты придёшь» и «Ты придёшь?» — одни и те же слова, "
                                  + "разница только в голосе. Услышим — поставим знак"
                        path: "question_by_voice"
                    }
                    ToggleRow {
                        id: llmToggle
                        title: "Понимать поправки на ходу"
                        subtitle: llmSetup.ready
                            ? "Сказали «в пятницу, нет, в субботу» — останется суббота"
                            : "Сказали «в пятницу, нет, в субботу» — останется суббота. Нужно доустановить, кнопка ниже"
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
                                                             : "не скачано"

                        title: "Правка текста на ходу"
                        subtitle: ready
                            ? "Ollama и модель на месте. Самоисправления и тон работают"
                            : busy
                            ? (total > 0
                               ? Math.round(frac * 100) + "% из " + (total / 1e9).toFixed(1) + " ГБ"
                               : "идёт установка, диктовке это не мешает")
                            : failed
                            ? "Диктовка работает и без этого — попробуйте ещё раз"
                            : "Скачаем Ollama и модель к ней — 3.3 ГБ. Всё останется на этом компьютере"

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
                                label: llmSetup.failed ? "Ещё раз" : "Установить"
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
                        title: "Адрес Ollama"
                        FlowInput {
                            width: 220
                            text: B.get("llm.url") || ""
                            onEdited: (t) => B.set("llm.url", t)
                        }
                    }
                    SettingRow {
                        visible: llmToggle.value && llmSetup.ready
                        title: "Модель Ollama"
                        subtitle: "Оставьте пусто — найдём подходящую сами"
                        FlowInput {
                            width: 220
                            text: B.get("llm.model") || ""
                            onEdited: (t) => B.set("llm.model", t)
                        }
                    }
                }

                SectionTitle { text: "Вставка" }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: "Как вставлять текст"
                        subtitle: "Обычно «вставка» — это мгновенно. Если текст не появляется — попробуйте «посимвольно»"
                        Segmented {
                            options: B.insertOptions
                            value: B.get("insert_mode")
                            onPicked: (v) => B.set("insert_mode", v)
                        }
                    }
                    SettingRow {
                        title: "Освобождать память"
                        subtitle: "Модель занимает около 370 МБ. Если долго не диктуете, "
                                  + "её можно отпустить — обратно поднимется за пару секунд"
                        Segmented {
                            options: [{label: "держать", value: 0},
                                      {label: "через час", value: 60},
                                      {label: "через 4 часа", value: 240}]
                            value: B.get("unload_after_min") || 0
                            onPicked: (v) => B.set("unload_after_min", v)
                        }
                    }
                    ToggleRow {
                        title: "Продолжать мысль"
                        subtitle: "Диктуете вторую фразу сразу за первой — программа поставит "
                                  + "пробел и не начнёт её с заглавной посреди предложения"
                        path: "smart_join"
                    }
                    SettingRow {
                        title: "Отправлять сообщение"
                        subtitle: "Список программ, где после вставки нажимать Enter. Имена "
                                  + "через запятую: telegram.exe, whatsapp.exe. Голосовое "
                                  + "«нажми энтер» работает и без списка"
                        FlowInput {
                            width: 260
                            mono: true
                            placeholder: "пусто — никуда"
                            text: (B.get("auto_enter_apps") || []).join(", ")
                            onEdited: (t) => {
                                var list = [];
                                var parts = t.split(",");
                                for (var i = 0; i < parts.length; i++) {
                                    var one = parts[i].trim();
                                    if (one !== "") list.push(one);
                                }
                                B.set("auto_enter_apps", list);
                            }
                        }
                    }
                    ToggleRow {
                        title: "Пробел в конце"
                        subtitle: "Чтобы следующая фраза не слиплась с этой"
                        path: "append_space"
                    }
                    ToggleRow {
                        title: "Не трогать скопированное"
                        subtitle: "Вернём в буфер то, что вы копировали до диктовки"
                        path: "restore_clipboard"
                    }
                }

                SectionTitle { text: "Распознавание" }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: "Модель"
                        subtitle: "Кто превращает голос в текст. Для других языков есть другие модели"
                        FlowButton {
                            label: "Другие языки и модели"
                            onClicked: win.page = "Модели"
                        }
                    }
                    SettingRow {
                        title: "Язык"
                        subtitle: "GigaAM понимает только русский. Для других языков нужна другая модель"
                        Segmented {
                            options: B.langOptions
                            value: B.get("language")
                            onPicked: (v) => B.set("language", v)
                        }
                    }
                    SettingRow {
                        title: "Устройство"
                        subtitle: "Оставьте «авто» — программа выберет сама"
                        Segmented {
                            options: B.deviceOptions
                            value: B.get("device")
                            onPicked: (v) => B.setRestart("device", v)
                        }
                    }
                }

                SectionTitle { text: "Вид" }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: "Оформление"
                        subtitle: "«Система» — как в Windows"
                        Segmented {
                            options: B.themeOptions
                            value: B.get("theme")
                            onPicked: (v) => B.set("theme", v)
                        }
                    }
                    SettingRow {
                        title: "Расположение"
                        subtitle: "Карточками — как сейчас. Строками — то же самое без рамок, "
                                  + "плотнее и спокойнее"
                        Segmented {
                            options: [{label: "карточками", value: "cards"},
                                      {label: "строками", value: "lines"}]
                            value: B.get("layout") || "cards"
                            onPicked: (v) => B.set("layout", v)
                        }
                    }
                    SettingRow {
                        title: "Пилюля во время записи"
                        subtitle: "Полоска с волной: снизу экрана, сверху — или не показывать совсем"
                        Segmented {
                            options: B.pillOptions
                            value: B.get("overlay_position")
                            onPicked: (v) => B.set("overlay_position", v)
                        }
                    }
                }

                SectionTitle { text: "Система" }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: "Запускать вместе с Windows"
                        subtitle: "Будет ждать в углу экрана, готовый к работе"
                        // Автозапуск живёт в реестре, а не в config.json.
                        Toggle { value: B.autostart; onToggled: (v) => B.setAutostart(v) }
                    }
                    ToggleRow {
                        title: "Звуковые сигналы"
                        subtitle: "Тихий сигнал, когда запись началась и закончилась"
                        path: "sounds"
                    }
                }
            }

            // ===== Модели =====
            // Скрытая страница: с панели убрана, вход - кнопкой из «Диктовки».
            Column {
                id: modelsPage
                visible: win.page === "Модели"
                width: parent.width
                spacing: 12
                property var list: []
                function refresh() { list = B.modelsInfo() }
                // Только при входе: страница скрыта при старте, грузить каталог
                // при сборке окна незачем - откроется кнопкой из «Диктовки».
                onVisibleChanged: if (visible) refresh()
                Connections {
                    target: B
                    function onModelsChanged() { modelsPage.refresh() }
                }

                Row {
                    spacing: 10
                    FlowButton { label: "← Назад"; onClicked: win.page = "Диктовка" }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Переключить можно на ходу — старая работает, пока грузится новая."
                        font.family: T.sans; font.pixelSize: T.tSm
                        color: T.textMuted
                    }
                }

                Repeater {
                    model: modelsPage.list
                    Card {
                        width: modelsPage.width
                        Item {
                            width: parent.width
                            implicitHeight: mcol.implicitHeight + 28

                            Column {
                                id: mcol
                                x: 24; y: 14
                                width: parent.width - 48 - 130
                                spacing: 3
                                Row {
                                    spacing: 8
                                    Text {
                                        text: modelData.title
                                        font.family: T.sans; font.pixelSize: T.tMd
                                        font.weight: Font.DemiBold
                                        color: T.text
                                    }
                                    // Статус - пилюлей: активная чернилами,
                                    // остальное тише. Не синим: акцент - не статус.
                                    Rectangle {
                                        visible: modelData.active || modelData.installed
                                        anchors.verticalCenter: parent.verticalCenter
                                        radius: height / 2
                                        height: 18
                                        width: st.implicitWidth + 16
                                        color: modelData.active ? T.ink : T.fill
                                        Text {
                                            id: st
                                            anchors.centerIn: parent
                                            text: modelData.active ? "используется" : "скачана"
                                            font.family: T.sans; font.pixelSize: T.t2xs
                                            font.weight: Font.DemiBold
                                            color: modelData.active ? T.bg : T.textSecondary
                                        }
                                    }
                                }
                                Text {
                                    width: parent.width
                                    text: modelData.why
                                    wrapMode: Text.WordWrap
                                    font.family: T.sans; font.pixelSize: T.tSm
                                    color: T.textSecondary
                                }
                                Text {
                                    // Метаданные моноширинным - голос терминала.
                                    //
                                    // Раньше здесь стояло «226 МБ · русский · CPU ·
                                    // MIT». Человеку, который просто пишет письма,
                                    // «CPU» и «MIT» не говорят ничего: первое он
                                    // прочтёт как ошибку, второе примет за опечатку.
                                    // Размер и языки - это выбор («поместится?
                                    // поймёт меня?»), железо - ответ на «а у меня
                                    // пойдёт?». Лицензия - обязательство перед
                                    // авторами модели, и её место ниже, в сноске,
                                    // а не в строке выбора.
                                    text: modelData.sizeMb + " МБ · " + modelData.langs
                                          + " · " + (modelData.device === "GPU"
                                                     ? "нужна видеокарта"
                                                     : "видеокарта не нужна")
                                    font.family: T.mono; font.pixelSize: T.t2xs
                                    color: T.textMuted
                                }
                                Text {
                                    // Parakeet под CC-BY-4.0 - она требует указать
                                    // авторство, и молчать об этом нельзя. Но и
                                    // кричать незачем: это про нас и авторов модели,
                                    // а не про выбор человека.
                                    text: "лицензия " + modelData.license
                                    visible: modelData.license !== "MIT"
                                    font.family: T.mono; font.pixelSize: T.t2xs
                                    color: T.textFaint
                                }
                                // Прогресс скачивания: линия, не спиннер -
                                // видно, сколько осталось от сотен мегабайт.
                                Item {
                                    width: parent.width; height: 12
                                    visible: modelData.downloading
                                    property real frac: 0
                                    Connections {
                                        target: B
                                        function onModelProgress(id, f) {
                                            if (id === modelData.id) parent.frac = f;
                                        }
                                    }
                                    Rectangle {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width; height: 4; radius: 2
                                        color: T.fillStrong
                                    }
                                    Rectangle {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width * parent.frac
                                        height: 4; radius: 2
                                        color: T.accent
                                        Behavior on width { NumberAnimation { duration: 300 } }
                                    }
                                }
                            }

                            Column {
                                anchors { right: parent.right; rightMargin: 24
                                          verticalCenter: parent.verticalCenter }
                                spacing: 6
                                FlowButton {
                                    visible: !modelData.active
                                    label: modelData.installed ? "Использовать"
                                         : modelData.downloading ? "Скачивается…" : "Скачать"
                                    kind: modelData.installed ? "primary" : "secondary"
                                    onClicked: {
                                        if (modelData.downloading) return;
                                        if (modelData.installed) B.setModel(modelData.id);
                                        else B.downloadModel(modelData.id);
                                    }
                                }
                                FlowButton {
                                    visible: modelData.installed && !modelData.active
                                    label: "Удалить (" + modelData.onDiskMb + " МБ)"
                                    kind: "danger"
                                    onClicked: B.deleteModel(modelData.id)
                                }
                            }
                        }
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

                SectionTitle { text: "Свои слова" }
                Text {
                    width: parent.width
                    text: "Слова, которые программа слышит, но пишет неправильно: "
                          + "фамилии, названия, термины. По одному на строку."
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
                    text: "Подстановки"; buttonLabel: "Добавить"; buttonKind: "primary"
                    onAction: snips.add()
                }
                PairTable {
                    id: snips
                    width: parent.width
                    storeKey: "snippets"
                    emptyText: "пока пусто - нажмите «Добавить»"
                    leftPlaceholder: "моя почта"
                    rightPlaceholder: "roman@example.com"
                }
                Note {
                    text: "Скажете «моя почта» — вставится адрес. Слева что говорите, "
                          + "справа что появится."
                          + (snips.blanks > 0 ? "  Строк без фразы: " + snips.blanks + " - они не сохранятся." : "")
                }

                SectionHeader {
                    text: "Тон под приложение"; buttonLabel: "Добавить"
                    onAction: tones.add()
                }
                PairTable {
                    id: tones
                    width: parent.width
                    storeKey: "tone_rules"
                    emptyText: "правил нет - тон не меняется"
                    leftPlaceholder: "outlook.exe"
                    rightPlaceholder: "формально"
                }
                Note {
                    text: B.toneNote
                          + (tones.blanks > 0 ? "  Строк без программы: " + tones.blanks + " - не сохранятся." : "")
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
                    SettingRow {
                        title: "Забывать старое"
                        subtitle: "История - самое личное, что тут есть: дословно всё, что вы "
                                  + "наговорили. Можно хранить не вечно"
                        Segmented {
                            // options - пары «подпись/значение», а не голые
                            // строки: value здесь число дней, и сравнивать
                            // подписи было бы враньём про то, что хранится.
                            options: [{label: "всегда", value: 0},
                                      {label: "месяц", value: 30},
                                      {label: "полгода", value: 180},
                                      {label: "год", value: 365}]
                            value: B.get("history_days") || 0
                            onPicked: (v) => B.set("history_days", v)
                        }
                    }
                    ToggleRow {
                        first: true
                        title: "Вести историю"
                        subtitle: "Выключите — и программа не будет ничего запоминать"
                        path: "history"
                    }
                }

                // Поиск слева, действия справа - как строка поиска в app-shell.
                Item {
                    width: parent.width
                    height: 30
                    FlowInput {
                        id: histSearch
                        anchors { left: parent.left; right: histBtns.left; rightMargin: 10 }
                        placeholder: "Найти в надиктованном…"
                        onEdited: (t) => hist.apply(t)
                    }
                    Row {
                        id: histBtns
                        anchors.right: parent.right
                        spacing: 6
                        FlowButton { label: "Обновить"; onClicked: hist.reload() }
                        FlowButton { label: "Очистить"; kind: "danger"
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
                                    text: modelData.ts + "   ·   " + modelData.sec + " с"
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
                                text: "Ничего не нашлось."
                                font.family: T.sans; font.pixelSize: T.tSm
                                color: T.textFaint
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

                SectionTitle { text: "Итого" }
                Card {
                    width: parent.width
                    StatRow { first: true; title: "Диктовок"
                        subtitle: "Сколько раз вы говорили вместо того, чтобы печатать"
                        value: statsPage.s.dictations || "—" }
                    StatRow { title: "Слов надиктовано"; subtitle: "За всё время"
                        value: statsPage.s.words || "—" }
                    StatRow { title: "Под запись"; subtitle: "Столько вы говорили"
                        value: statsPage.s.seconds || "—" }
                    StatRow { title: "Сэкономлено"
                        subtitle: "Печатать эти слова руками — примерно "
                                  + (statsPage.s.typingWpm || 40)
                                  + " слов в минуту. Разница со временем ваших записей"
                        value: statsPage.s.saved_sec || "—" }
                    StatRow { visible: statsPage.s.speedOk === true
                        title: "Ваша скорость"
                        subtitle: "Слов в минуту под запись — замер по вашей истории"
                        value: (statsPage.s.userWpm || 0) + " сл/мин" }
                    StatRow { title: "Дней подряд"
                        subtitle: "Серия: диктовали каждый день без пропуска"
                        value: statsPage.s.streak || "—" }
                }

                SectionTitle { text: "По дням" }
                Card {
                    width: parent.width
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
                                text: "Диктовка, которая работает без интернета."
                                font.family: T.sans; font.pixelSize: T.tMd
                                font.weight: Font.DemiBold
                                color: T.text
                            }
                            Text {
                                width: aboutHero.width
                                wrapMode: Text.WordWrap
                                // Отрицательная гарантия сильнее обещания: не
                                // «мы защищаем данные», а «уходить им некуда».
                                text: "Голос не покидает этот компьютер — не потому что мы обещаем, "
                                      + "а потому что некуда: интернет нужен один раз, чтобы скачать "
                                      + "модель, и ещё чтобы проверять обновления. Поэтому диктовка "
                                      + "работает в поезде, на даче и когда интернет упал."
                                font.family: T.sans; font.pixelSize: T.tSm
                                color: T.textSecondary
                                lineHeight: 1.5
                            }
                        }
                    }
                }

                SectionTitle { text: "Что важно знать" }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: "Первые слова не теряются"
                        subtitle: "Микрофон слушает чуть раньше, чем вы нажали клавишу"
                    }
                    SettingRow {
                        title: "Ничего не переписывает"
                        subtitle: "Чистка вычёркивает лишнее из сказанного и не добавляет ни слова от себя"
                    }
                    SettingRow {
                        title: "В покое — ноль"
                        subtitle: "Пока вы не диктуете, программа не тратит ни процессор, ни интернет"
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
                SectionTitle { text: "Свои слова и настройки" }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: "Сохранить в файл"
                        subtitle: "Словарь, замены, тон и сочетания. Пригодится при переустановке "
                                  + "и на втором компьютере"
                        Row {
                            spacing: 8
                            FlowButton {
                                label: "Сохранить"
                                onClicked: B.exportData(false)
                            }
                            FlowButton {
                                label: "Вместе с историей"
                                onClicked: B.exportData(true)
                            }
                        }
                    }
                    SettingRow {
                        title: "Загрузить из файла"
                        subtitle: "Добавит к тому, что есть. Ваши сочетания и слова не пропадут"
                        FlowButton {
                            label: "Загрузить"
                            onClicked: B.importData()
                        }
                    }
                }

                SectionTitle { text: "Как обновлялось"; visible: history.count > 0 }
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
                                                text: "сейчас у вас"
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

                SectionTitle { text: "Служебное" }
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
                    FlowButton { label: "Папка приложения"; onClicked: B.openFolder() }
                    FlowButton { label: "config.json"; onClicked: B.openConfig() }
                    FlowButton { label: "flow.log"; onClicked: B.openLog() }
                    FlowButton { label: "Пройти знакомство заново"
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
