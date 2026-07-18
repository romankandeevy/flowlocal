// Мастер первого запуска: шесть шагов (PLAN, раздел 4).
// Данные - в onboarding_qt (`B` - настроечный Backend, `OB` - живой звук,
// проба, финиш). Токены - `T`, один источник правды.

import QtQuick

Rectangle {
    id: wiz
    color: T.bg
    property int step: 0
    readonly property int last: 7

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
    // Семь точек честно говорят «это длинно», и это работает против нас. Разбор
    // онбординга Wispr Flow (Kristen Berman, «8 lessons») отмечает ровно это:
    // человек охотнее идёт дальше, когда знает, что осталось немного, чем когда
    // видит полную длину пути. Поэтому к точкам добавлена подпись, и появляется
    // она только под конец - там, где иначе хочется бросить.
    Column {
        id: dots
        anchors { top: parent.top; topMargin: 20; horizontalCenter: parent.horizontalCenter }
        spacing: 7

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 8
            Repeater {
                model: wiz.last + 1
                Rectangle {
                    width: 8; height: 8; radius: 4
                    color: index <= wiz.step ? T.ink : T.fill
                    Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
                }
            }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: wiz.step === wiz.last ? "последний шаг"
                : wiz.step === wiz.last - 1 ? "почти готово"
                : ""
            visible: text !== ""
            font.family: T.sans; font.pixelSize: T.t2xs
            color: T.textMuted
            opacity: visible ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: T.durBase * 1000 } }
        }
    }

    // ---------- содержимое шагов ----------
    Item {
        anchors { top: dots.bottom; left: parent.left; right: parent.right
                  bottom: footer.top; margins: 36 }

        // === 0. Привет ===
        Column {
            visible: wiz.step === 0
            anchors.centerIn: parent
            spacing: 14
            width: parent.width
            // Знак, а не голое имя: это первое, что человек видит от программы,
            // и стена текста на белом - плохое первое впечатление для приложения,
            // которое дальше показывает себя аккуратным. Тот же вордмарк, что в
            // панели настроек, только крупный.
            Wordmark {
                anchors.horizontalCenter: parent.horizontalCenter
                box: 44
                nameSize: T.t3xl
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.min(parent.width, 420)
                horizontalAlignment: Text.AlignHCenter
                text: "Зажали клавишу - говорите, отпустили - текст вставился туда, где курсор. Звук и текст не покидают этот компьютер."
                wrapMode: Text.WordWrap
                font.family: T.sans; font.pixelSize: T.tMd
                color: T.textSecondary
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
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width
            spacing: 14

            Text {
                text: "Как вам удобнее?"
                font.family: T.sans; font.pixelSize: T.tXl
                font.weight: Font.DemiBold; color: T.text
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: "Это можно поменять когда угодно — «Диктовка» → «Вид»."
                font.family: T.sans; font.pixelSize: T.tSm; color: T.textMuted
            }

            Item { width: 1; height: 4 }

            Text {
                text: "ЦВЕТА"
                font.family: T.sans; font.pixelSize: T.t2xs
                font.weight: Font.DemiBold; font.letterSpacing: 0.6
                color: T.textFaint
            }
            Segmented {
                options: [{label: "как в системе", value: "system"},
                          {label: "светлая", value: "light"},
                          {label: "тёмная", value: "dark"}]
                value: B.get("theme") || "system"
                onPicked: (v) => B.set("theme", v)
            }

            Item { width: 1; height: 8 }

            Text {
                text: "РАСПОЛОЖЕНИЕ"
                font.family: T.sans; font.pixelSize: T.t2xs
                font.weight: Font.DemiBold; font.letterSpacing: 0.6
                color: T.textFaint
            }
            Segmented {
                options: [{label: "карточками", value: "cards"},
                          {label: "строками", value: "lines"}]
                value: B.get("layout") || "cards"
                onPicked: (v) => B.set("layout", v)
            }

            // Показываем разницу тут же, а не описываем словами: «карточками»
            // и «строками» человеку ничего не говорят, пока он их не увидел.
            Item { width: 1; height: 6 }
            Card {
                width: parent.width
                Item {
                    width: parent.width
                    implicitHeight: demoCol.implicitHeight + 8
                    Column {
                        id: demoCol
                        width: parent.width
                        SettingRow {
                            first: true
                            title: "Так выглядит настройка"
                            subtitle: "А так — пояснение под ней"
                            Toggle { value: true }
                        }
                        SettingRow {
                            title: "И следующая за ней"
                            subtitle: "Разделены линией в обоих видах"
                            Toggle { value: false }
                        }
                    }
                }
            }
        }

        // === 2. Язык и модель ===
        Column {
            visible: wiz.step === 2
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width
            spacing: 12
            Text {
                text: "На каком языке вы говорите?"
                font.family: T.sans; font.pixelSize: T.tXl; font.weight: Font.DemiBold
                color: T.text
            }
            Text {
                width: parent.width
                text: "От этого зависит модель распознавания. Видеокарта не нужна."
                font.family: T.sans; font.pixelSize: T.tSm; color: T.textMuted
            }
            Repeater {
                model: [
                    {lang: "ru", title: "Русский",
                     sub: "GigaAM: обучена на 700 000 часов русской речи, сама ставит пунктуацию. 226 МБ"},
                    {lang: "en", title: "Русский и другие языки",
                     sub: "Parakeet: 25 европейских языков, язык определяет сама. 670 МБ"},
                ]
                Rectangle {
                    width: parent.width
                    height: 72
                    radius: T.radiusLg
                    color: T.paper
                    border.width: wiz.chosenModel === OB.pickModel(modelData.lang) ? 2 : 1
                    border.color: wiz.chosenModel === OB.pickModel(modelData.lang)
                                  ? T.accent : T.border
                    Column {
                        anchors { left: parent.left; leftMargin: 20
                                  verticalCenter: parent.verticalCenter }
                        width: parent.width - 40
                        spacing: 3
                        Text { text: modelData.title; color: T.text
                               font.family: T.sans; font.pixelSize: T.tMd
                               font.weight: Font.DemiBold }
                        Text { width: parent.width; text: modelData.sub
                               wrapMode: Text.WordWrap; color: T.textMuted
                               font.family: T.sans; font.pixelSize: T.tSm }
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: wiz.chosenModel = OB.pickModel(modelData.lang)
                    }
                }
            }
            // Прогресс скачивания выбранной модели
            Item {
                width: parent.width; height: 18
                visible: wiz.downloading
                Rectangle { anchors.verticalCenter: parent.verticalCenter
                            width: parent.width; height: 4; radius: 2; color: T.fillStrong }
                Rectangle { anchors.verticalCenter: parent.verticalCenter
                            width: parent.width * wiz.dlFrac; height: 4; radius: 2
                            color: T.accent
                            Behavior on width { NumberAnimation { duration: 300 } } }
            }
            Text {
                visible: wiz.modelReady
                text: "Модель уже на диске - можно дальше."
                font.family: T.sans; font.pixelSize: T.tSm; color: T.success
            }
        }

        // === 3. Микрофон ===
        Column {
            id: micStep
            visible: wiz.step === 3
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width
            spacing: 12
            property var bars: []
            Text {
                text: "Микрофон"
                font.family: T.sans; font.pixelSize: T.tXl; font.weight: Font.DemiBold
                color: T.text
            }
            Text {
                width: parent.width
                text: "Скажите что-нибудь - волна должна ожить. Если лежит ровно, выберите другой микрофон."
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
                width: parent.width; height: 88
                radius: T.radiusLg; color: T.paper
                border.width: 1; border.color: T.border
                Row {
                    anchors.centerIn: parent
                    spacing: 3
                    Repeater {
                        model: 40
                        Rectangle {
                            width: 5
                            radius: 2.5
                            anchors.verticalCenter: parent.verticalCenter
                            color: T.ink
                            opacity: 0.85
                            height: {
                                var b = micStep.bars;
                                var v = index < b.length ? b[b.length - 1 - (39 - index)] : 0;
                                return Math.max(3, (v === undefined ? 0 : v) * 64);
                            }
                            Behavior on height { NumberAnimation { duration: 60 } }
                        }
                    }
                }
            }
            Timer {
                interval: 33
                running: wiz.step === 3 && wiz.visible
                repeat: true
                onTriggered: {
                    var fresh = OB.levels();
                    if (fresh.length === 0) return;
                    var b = micStep.bars.slice();
                    for (var i = 0; i < fresh.length; i++)
                        b.push(Math.min(1, Math.pow(fresh[i] / 0.12, 0.65)));
                    micStep.bars = b.slice(-40);
                }
            }
        }

        // === 4. Сочетание ===
        Column {
            visible: wiz.step === 4
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width
            spacing: 12
            Text {
                text: "Каким жестом диктовать?"
                font.family: T.sans; font.pixelSize: T.tXl; font.weight: Font.DemiBold
                color: T.text
            }
            Text {
                width: parent.width
                text: "Зажали - говорите, отпустили - вставилось. Кликните по полю и нажмите своё сочетание; подойдёт и боковая кнопка мыши."
                wrapMode: Text.WordWrap
                font.family: T.sans; font.pixelSize: T.tSm; color: T.textMuted
            }
            HotkeyField { field: "hotkey_hold" }
            Text {
                width: parent.width
                text: "Второй жест - «нажал и говоришь со свободными руками» - настраивается позже, в Настройках."
                wrapMode: Text.WordWrap
                font.family: T.sans; font.pixelSize: T.t2xs; color: T.textFaint
            }
        }

        // === 5. Проверим вставку ===
        Column {
            visible: wiz.step === 5
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width
            spacing: 12
            property string result: ""
            id: insStep
            Text {
                text: "Проверим вставку"
                font.family: T.sans; font.pixelSize: T.tXl; font.weight: Font.DemiBold
                color: T.text
            }
            Text {
                width: parent.width
                text: "Разрешения Windows не нужны, но вставке может мешать антивирус. Нажмите кнопку - текст должен появиться в поле."
                wrapMode: Text.WordWrap
                font.family: T.sans; font.pixelSize: T.tSm; color: T.textMuted
            }
            FlowInput {
                id: insField
                width: parent.width
                placeholder: "сюда вставится проверочный текст"
            }
            FlowButton {
                label: "Проверить вставку"
                kind: "primary"
                onClicked: {
                    insField.text = "";
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
                    insStep.result = ok && insField.text.length > 0
                        ? "Работает."
                        : "не сработало - проверьте антивирус или включите режим «посимвольно» в настройках";
                }
            }
        }

        // === 6. Проба ===
        Column {
            id: trialStep
            visible: wiz.step === 6
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width
            spacing: 12
            property bool rec: false
            property string result: ""
            Text {
                text: "Скажите что-нибудь"
                font.family: T.sans; font.pixelSize: T.tXl; font.weight: Font.DemiBold
                color: T.text
            }
            Text {
                width: parent.width
                text: "Распознанный текст появится здесь и никуда не вставится."
                font.family: T.sans; font.pixelSize: T.tSm; color: T.textMuted
            }
            FlowButton {
                label: trialStep.rec ? "Стоп" : "Начать запись"
                kind: "primary"
                onClicked: {
                    if (trialStep.rec) { OB.trialStop(); trialStep.result = "распознаю…" }
                    else { trialStep.result = ""; OB.trialStart() }
                    trialStep.rec = !trialStep.rec;
                }
            }
            Rectangle {
                width: parent.width
                height: Math.max(96, resText.implicitHeight + 32)
                radius: T.radiusLg; color: T.paper
                border.width: 1; border.color: T.border
                Text {
                    id: resText
                    x: 16; y: 16
                    width: parent.width - 32
                    text: trialStep.result
                    wrapMode: Text.WordWrap
                    font.family: T.sans; font.pixelSize: T.tMd
                    color: T.text
                    lineHeight: 1.3
                }
            }
            Connections {
                target: OB
                function onTrialReady(text) { trialStep.result = text }
            }
        }

        // === 7. Править текст ===
        //
        // Экран последний намеренно: сначала человек увидел, что диктовка
        // работает, и только потом ему предлагают её улучшить. Предлагать
        // улучшение до того, как заработало основное, - значит просить
        // доверия авансом.
        Column {
            id: llmStep
            visible: wiz.step === 7
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width
            spacing: 12

            property bool busy: false
            property bool done: false
            property bool failed: false
            property bool declined: false
            property string stage: ""
            property real frac: 0
            property real total: 0

            Text {
                text: llmStep.done ? "Готово" : "Править текст на ходу?"
                font.family: T.sans; font.pixelSize: T.tXl; font.weight: Font.DemiBold
                color: T.text
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: llmStep.done
                      ? "Теперь программа понимает поправки на ходу. Выключить можно в «Диктовке»."
                      : "Скажете «встреча в пятницу, нет, в субботу» - в текст попадёт только суббота. "
                        + "И тон под приложение: в почте строже, в чате свободнее."
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
                    spacing: 6
                    Text {
                        text: "Нужно скачать 3.3 ГБ"
                        font.family: T.sans; font.pixelSize: T.tSm
                        font.weight: Font.DemiBold; color: T.text
                    }
                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: "Ollama - бесплатная программа, которая считает это на вашем "
                              + "компьютере, и модель к ней. Всё останется здесь: интернет "
                              + "нужен только чтобы скачать."
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
                    text: "Можно свернуть окно - диктовка уже работает."
                    font.family: T.sans; font.pixelSize: T.t2xs; color: T.textMuted
                }
            }

            Row {
                visible: !llmStep.busy && !llmStep.done
                spacing: 10
                FlowButton {
                    label: llmStep.failed ? "Попробовать снова" : "Да, установить"
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
                FlowButton {
                    label: "Не сейчас"
                    onClicked: { llmStep.declined = true; declineTimer.restart() }
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
                    text: "Хорошо. Включить можно потом: «Диктовка» → «Править текст», "
                          + "там та же кнопка и то же объяснение."
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
                text: "Не получилось - " + llmStep.stage + ". Диктовка работает и без этого, "
                      + "а попробовать снова можно в настройках."
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

    // ---------- низ: назад / дальше ----------
    Item {
        id: footer
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 72

        FlowButton {
            visible: wiz.step > 0
            anchors { left: parent.left; leftMargin: 36; verticalCenter: parent.verticalCenter }
            label: "Назад"
            onClicked: wiz.step -= 1
        }
        FlowButton {
            anchors { right: parent.right; rightMargin: 36; verticalCenter: parent.verticalCenter }
            kind: "primary"
            label: wiz.step === 0 ? "Начать"
                 : wiz.step === 2 ? (wiz.modelReady ? "Дальше"
                                     : wiz.downloading ? "Скачивается…" : "Скачать модель")
                 : wiz.step === wiz.last ? "Готово"
                 : "Дальше"
            onClicked: {
                if (wiz.step === 2 && !wiz.modelReady) {
                    if (!wiz.downloading) B.downloadModel(wiz.chosenModel);
                    return;
                }
                if (wiz.step === 2 && wiz.modelReady) B.setModel(wiz.chosenModel);
                if (wiz.step === wiz.last) { OB.finish(); return; }  // finish() сам закроет окно
                wiz.step += 1;
            }
        }
    }
}
