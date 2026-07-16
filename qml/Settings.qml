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

    property string page: "Основное"
    readonly property var pages: ["Основное", "Распознавание", "Модели", "Ввод",
                                  "Словарь", "Замены", "История", "Статистика",
                                  "О программе"]

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

            PageTitle { text: win.page }

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
                        subtitle: "Зажали - говорите, отпустили - текст вставился. Можно назначить и боковую кнопку мыши"
                        HotkeyField { field: "hotkey_hold" }
                    }
                    SettingRow {
                        title: "Нажать и говорить"
                        subtitle: "Нажали - пишем, нажали ещё раз - стоп. Руки свободны, Esc отменяет запись"
                        HotkeyField { field: "hotkey_toggle"; allowClear: true }
                    }
                    SettingRow {
                        title: "Микрофон"
                        subtitle: "Применится при следующей записи"
                        Select {
                            options: B.micOptions
                            value: B.get("mic_device")
                            onPicked: (v) => B.set("mic_device", v)
                        }
                    }
                    SettingRow {
                        title: "Отменить последнюю диктовку"
                        subtitle: "Уберёт ровно то, что вставило приложение - и только если после вставки вы ничего не печатали"
                        HotkeyField { field: "undo_hotkey"; allowClear: true }
                    }
                }

                SectionTitle { text: "Вид" }
                Card {
                    width: parent.width
                    SettingRow {
                        first: true
                        title: "Оформление"
                        subtitle: "«система» - как настроено в Windows"
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
                        subtitle: "FlowLocal свернётся в трей при входе в систему"
                        // Автозапуск живёт в реестре, а не в config.json.
                        Toggle { value: B.autostart; onToggled: (v) => B.setAutostart(v) }
                    }
                    ToggleRow {
                        title: "Звуковые сигналы"
                        subtitle: "Короткий тон на старте и в конце записи"
                        path: "sounds"
                    }
                    ToggleRow {
                        title: "Вести историю"
                        subtitle: "Записывать распознанный текст в history.jsonl"
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
                        subtitle: "GigaAM - для русского, процессора хватает. Скачивание, размеры и удаление - на странице «Модели»"
                        FlowButton {
                            label: (B.get("model") || "").split("/").pop()
                            onClicked: win.page = "Модели"
                        }
                    }
                    SettingRow {
                        title: "Язык"
                        subtitle: "Только для Whisper и Parakeet. GigaAM знает один язык - русский"
                        Segmented {
                            options: B.langOptions
                            value: B.get("language")
                            onPicked: (v) => B.set("language", v)
                        }
                    }
                    SettingRow {
                        title: "Устройство"
                        subtitle: "«авто»: видеокарта, если onnxruntime собран с CUDA, иначе процессор. Для GigaAM разницы почти нет"
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
                        title: "Убирать «э-э» и «ммм»"
                        subtitle: "Консервативные правила: только однозначные междометия"
                        path: "remove_fillers"
                    }
                    ToggleRow {
                        title: "Голосовые команды"
                        subtitle: "«с новой строки», «с нового абзаца» - перевод строки; «нажми энтер» в конце фразы - отправка сообщения"
                        path: "voice_commands"
                    }
                    ToggleRow {
                        id: llmToggle
                        title: "Полировка локальной LLM"
                        subtitle: "Через Ollama: убирает слова-паразиты, учитывает самоисправления"
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
                        subtitle: "Например qwen2.5:3b - быстрая и достаточная"
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
                    text: "Модели живут в models/ рядом с приложением. Выбранная применяется без перезапуска: старая работает, пока грузится новая."
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
                                    text: modelData.sizeMb + " МБ · " + modelData.langs
                                          + " · " + modelData.device + " · " + modelData.license
                                    font.family: T.mono; font.pixelSize: T.t2xs
                                    color: T.textMuted
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
                        title: "Способ"
                        subtitle: "«вставка» - через буфер и Ctrl+V, мгновенно. «посимвольно» - для окон, где Ctrl+V не срабатывает"
                        Segmented {
                            options: B.insertOptions
                            value: B.get("insert_mode")
                            onPicked: (v) => B.set("insert_mode", v)
                        }
                    }
                    ToggleRow {
                        title: "Пробел в конце"
                        subtitle: "Чтобы следующая фраза не слиплась с предыдущей"
                        path: "append_space"
                    }
                    ToggleRow {
                        title: "Возвращать буфер обмена"
                        subtitle: "После вставки вернуть то, что лежало в буфере до неё"
                        path: "restore_clipboard"
                    }
                }

                SectionTitle { text: "Микрофон" }
                Card {
                    width: parent.width
                    ToggleRow {
                        first: true
                        title: "Держать микрофон открытым"
                        subtitle: "Не режет первое слово: поток пишет всегда, начало берётся из пре-буфера"
                        path: "keep_mic_open"
                    }
                    SettingRow {
                        title: "Пре-буфер"
                        subtitle: "Сколько секунд звука до нажатия попадёт в запись"
                        Slider {
                            from: 0; to: 1.5; stepSize: 0.1
                            value: B.get("pre_buffer_sec")
                            onMoved: (v) => B.set("pre_buffer_sec", v)
                        }
                    }
                    SettingRow {
                        title: "Игнорировать нажатия короче"
                        subtitle: "Защита от случайных касаний хоткея"
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
                    text: "Имена, термины и названия. Похожее слово в распознанном тексте починится по этому написанию. По одному на строку."
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
                    text: "Сказали «моя почта» - вставился адрес. Подстановка идёт после распознавания, целыми словами, без учёта регистра. Слева - что говорите, справа - что вставится."
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
                        subtitle: "Сколько раз вы нажимали хоткей"
                        value: statsPage.s.dictations || "—" }
                    StatRow { title: "Слов надиктовано"; subtitle: "По всей истории"
                        value: statsPage.s.words || "—" }
                    StatRow { title: "Средняя длина"; subtitle: "Слов за одну диктовку"
                        value: statsPage.s.avg_words || "—" }
                    StatRow { title: "Под запись"; subtitle: "Сколько всего звучал микрофон"
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
                    text: "Приватная диктовка. Звук и текст не покидают компьютер."
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
