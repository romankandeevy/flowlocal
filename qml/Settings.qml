// Окно настроек: боковое меню плюс страницы. Вёрстка целиком здесь, данные -
// в settings_qt.Backend (контекстное свойство `B`), токены - в `T`.
//
// Сохранение сразу по изменению, кнопки «Применить» нет намеренно: лишний шаг,
// о котором легко забыть.

import QtQuick

Rectangle {
    id: win
    color: T.bg
    focus: true

    // Фактура из системы: точечная сетка и мягкий прожектор акцентом.
    // Плоская заливка - не то, чем Korti предлагает заполнять поверхность.
    Backdrop { anchors.fill: parent }

    property string page: "Главная"
    readonly property var pages: ["Главная", "Основное", "Распознавание", "Модели",
                                  "Ввод", "Словарь", "Замены", "История",
                                  "Статистика", "О программе"]

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
        width: 214
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

            // Вордмарк: знак плюс имя. Знак - чернила на бумаге (--primary),
            // как «i» у korti; у нас микрофон - то, чем занят продукт.
            Row {
                spacing: 10
                leftPadding: 8
                bottomPadding: 18
                Rectangle {
                    width: 28; height: 28; radius: T.radiusSm
                    color: T.ink
                    Icon {
                        anchors.centerIn: parent
                        path: ic.mic
                        size: 16
                        color: T.bg
                        weight: 2.2
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "FlowLocal"
                    font.family: T.sans
                    font.pixelSize: T.tXl
                    font.weight: Font.ExtraBold
                    font.letterSpacing: -0.6
                    color: T.text
                }
            }

            Repeater {
                model: win.pages
                NavItem {
                    label: modelData
                    icon: ic.forPage(modelData)
                    active: win.page === modelData
                    onClicked: win.page = modelData
                }
            }
        }

        // Низ панели: состояние приложения. Korti кладёт сюда карточку
        // пользователя - у нас пользователя нет, а вот «чем диктовать» человек
        // ищет постоянно, и это единственное место, где оно всегда на виду.
        Column {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom
                      leftMargin: 22; rightMargin: 14; bottomMargin: 18 }
            spacing: 3
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
        contentHeight: content.implicitHeight + 48
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: content
            x: 26
            y: 24
            width: scroll.width - 52
            spacing: 16

            PageTitle { text: win.page === "Главная" ? home.greeting : win.page }

            // ===== Главная =====
            // Экрана не было вовсе: приложение открывалось сразу в настройки,
            // и человек первым делом видел «пре-буфер» и «квантизацию» вместо
            // того, ради чего всё затевалось.
            //
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

                function reload() {
                    st = B.stats();
                    recent = B.history().slice(0, 5);
                    var h = new Date().getHours();
                    greeting = h < 5 ? "Доброй ночи" : h < 12 ? "Доброе утро"
                             : h < 18 ? "Добрый день" : "Добрый вечер";
                }
                Component.onCompleted: reload()
                onVisibleChanged: if (visible) reload()

                // Первое, что человек должен узнать: как этим пользоваться.
                // Не «состояние системы», а одна фраза действием.
                Card {
                    width: parent.width
                    Item {
                        width: parent.width
                        implicitHeight: hero.implicitHeight + 36
                        Column {
                            id: hero
                            anchors { left: parent.left; right: parent.right; top: parent.top
                                      leftMargin: 18; rightMargin: 18; topMargin: 18 }
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
                                      : "Сочетание не назначено — задайте его в «Основном»."
                                font.family: T.sans
                                font.pixelSize: T.tXl
                                font.weight: Font.Bold
                                font.letterSpacing: -0.2
                                color: T.text
                                lineHeight: 1.3
                            }
                            Text {
                                width: hero.width
                                wrapMode: Text.WordWrap
                                text: "Работает в любом окне: письмо, чат, документ. "
                                      + "Голос никуда не отправляется — всё считается здесь."
                                font.family: T.sans
                                font.pixelSize: T.tSm
                                color: T.textMuted
                                lineHeight: 1.5
                            }
                        }
                    }
                }

                // Числа, а не прилагательные - так говорит система.
                Row {
                    width: parent.width
                    spacing: 12
                    property real cw: (width - 24) / 3
                    Metric {
                        width: parent.cw
                        label: "надиктовано"
                        value: home.st.words || "0"
                        hint: "слов всего"
                    }
                    Metric {
                        width: parent.cw
                        label: "сэкономлено"
                        value: home.st.saved_sec || "0 с"
                        hint: "против набора руками"
                    }
                    Metric {
                        width: parent.cw
                        label: "диктовок"
                        value: home.st.dictations || "0"
                        hint: "за всё время"
                    }
                }

                SectionHeader { text: "ПОСЛЕДНЕЕ" }

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
                                    anchors.fill: parent
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
                                        font.weight: Font.DemiBold
                                        color: T.text
                                    }
                                    Text {
                                        text: "нажмите, чтобы скопировать"
                                        font.family: T.sans
                                        font.pixelSize: T.t2xs
                                        color: T.textMuted
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

            // ===== Основное =====
            Column {
                visible: win.page === "Основное"
                width: parent.width
                spacing: 16

                SectionTitle { text: "Диктовка" }
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
                        subtitle: B.get("llm.enabled")
                            ? "Выделите текст, зажмите, скажите «сделай короче», «переведи на английский», «исправь ошибки» - выделенное заменится"
                            : "Нужна Ollama: правка по указанию - это понимание смысла. Включите полировку на вкладке «Распознавание»"
                        HotkeyField { field: "hotkey_command"; allowClear: true }
                    }
                    SettingRow {
                        title: "Микрофон"
                        subtitle: "Какой микрофон слушать"
                        Select {
                            options: B.micOptions
                            value: B.get("mic_device")
                            onPicked: (v) => B.set("mic_device", v)
                        }
                    }
                    SettingRow {
                        title: "Отменить последнюю диктовку"
                        subtitle: "Уберёт вставленный текст, если вы после этого ничего не печатали"
                        HotkeyField { field: "undo_hotkey"; allowClear: true }
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
                    ToggleRow {
                        title: "Вести историю"
                        subtitle: "Хранить, что вы надиктовали, — чтобы можно было найти и скопировать"
                        path: "history"
                    }
                }
            }

            // ===== Распознавание =====
            Column {
                visible: win.page === "Распознавание"
                width: parent.width
                spacing: 16

                SectionTitle { text: "Модель" }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: "Модель"
                        subtitle: "Кто именно распознаёт вашу речь. Выбрать другую — на странице «Модели»"
                        FlowButton {
                            label: (B.get("model") || "").split("/").pop()
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

                SectionTitle { text: "Обработка текста" }
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
                        id: llmToggle
                        title: "Понимать поправки на ходу"
                        subtitle: "Сказали «в пятницу, нет, в субботу» — останется суббота. Нужна Ollama"
                        path: "llm.enabled"
                    }
                    // Адрес и модель показываем только когда полировка включена:
                    // настройка выключенного - это шум.
                    SettingRow {
                        visible: llmToggle.value
                        title: "Адрес Ollama"
                        FlowInput {
                            width: 220
                            text: B.get("llm.url") || ""
                            onEdited: (t) => B.set("llm.url", t)
                        }
                    }
                    SettingRow {
                        visible: llmToggle.value
                        title: "Модель Ollama"
                        subtitle: "Оставьте пусто — найдём подходящую сами"
                        FlowInput {
                            width: 220
                            text: B.get("llm.model") || ""
                            onEdited: (t) => B.set("llm.model", t)
                        }
                    }
                }
            }

            // ===== Модели =====
            Column {
                id: modelsPage
                visible: win.page === "Модели"
                width: parent.width
                spacing: 12
                property var list: []
                function refresh() { list = B.modelsInfo() }
                onVisibleChanged: if (visible) refresh()
                Component.onCompleted: refresh()
                Connections {
                    target: B
                    function onModelsChanged() { modelsPage.refresh() }
                }

                Text {
                    width: parent.width
                    text: "Кто распознаёт вашу речь. Переключить можно на ходу — старая работает, пока грузится новая."
                    wrapMode: Text.WordWrap
                    font.family: T.sans; font.pixelSize: T.tBase
                    color: T.textSecondary
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

            // ===== Ввод =====
            Column {
                visible: win.page === "Ввод"
                width: parent.width
                spacing: 16

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

                SectionTitle { text: "Микрофон" }
                Card {
                    width: parent.width
                    ToggleRow {
                        first: true
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
            }

            // ===== Словарь =====
            Column {
                visible: win.page === "Словарь"
                width: parent.width
                spacing: 12

                Text {
                    width: parent.width
                    text: "Фамилии, названия, редкие слова — то, что программа слышит, но пишет неправильно. Напишите как надо, по одному на строку, и она исправится сама."
                    wrapMode: Text.WordWrap
                    font.family: T.sans; font.pixelSize: T.tBase
                    color: T.textSecondary
                }
                Card {
                    width: parent.width
                    height: 360
                    Item {
                        width: parent.width
                        height: 360
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
            }

            // ===== Замены =====
            Column {
                visible: win.page === "Замены"
                width: parent.width
                spacing: 16

                SectionHeader {
                    text: "Замены"; buttonLabel: "Добавить"; buttonKind: "primary"
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
                    text: "Чтобы не диктовать одно и то же по буквам. Скажете «моя почта» — вставится адрес. Слева что говорите, справа что появится."
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

                Row {
                    spacing: 6
                    layoutDirection: Qt.RightToLeft
                    width: parent.width
                    FlowButton { label: "Очистить"; kind: "danger"
                        onClicked: { B.clearHistory(); hist.reload() } }
                    FlowButton { label: "Обновить"; onClicked: hist.reload() }
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
                            property string note: ""
                            function reload() { model = B.history(); note = B.historyNote() }
                            Component.onCompleted: reload()
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
                onVisibleChanged: if (visible) s = B.stats()
                Component.onCompleted: s = B.stats()

                SectionTitle { text: "Итого" }
                Card {
                    width: parent.width
                    StatRow { first: true; title: "Диктовок"
                        subtitle: "Сколько раз вы говорили вместо того, чтобы печатать"
                        value: statsPage.s.dictations || "—" }
                    StatRow { title: "Слов надиктовано"; subtitle: "За всё время"
                        value: statsPage.s.words || "—" }
                    StatRow { title: "Средняя длина"; subtitle: "Слов за один раз"
                        value: statsPage.s.avg_words || "—" }
                    StatRow { title: "Под запись"; subtitle: "Столько вы говорили"
                        value: statsPage.s.seconds || "—" }
                    StatRow { title: "Сэкономлено против набора"
                        subtitle: "Оценка: речь ~" + (statsPage.s.speechWpm || 0)
                                  + " слов/мин против ~" + (statsPage.s.typingWpm || 0)
                                  + " слов/мин на клавиатуре"
                        value: statsPage.s.saved_sec || "—" }
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

                Text {
                    // Дисплейный кегль: тяжёлый вес, тесный трекинг - так задан бренд.
                    text: "FlowLocal"
                    font.family: T.sans; font.pixelSize: T.t3xl
                    font.weight: Font.ExtraBold; font.letterSpacing: -1
                    color: T.text
                }
                Text {
                    text: "Диктовка, которая работает без интернета.
Ваш голос никуда не отправляется."
                    font.family: T.sans; font.pixelSize: T.tMd
                    color: T.textSecondary
                }
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
        anchors { left: parent.left; leftMargin: 240; bottom: parent.bottom
                  bottomMargin: 10 }
        text: ""
        font.family: T.mono
        font.pixelSize: T.t2xs
        color: T.textMuted
    }
}
