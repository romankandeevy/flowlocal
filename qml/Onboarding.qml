// Мастер первого запуска: шесть шагов (PLAN, раздел 4).
// Данные - в onboarding_qt (`B` - настроечный Backend, `OB` - живой звук,
// проба, финиш). Токены - `T`, один источник правды.

import QtQuick

Rectangle {
    id: wiz
    color: T.bg
    property int step: 0
    readonly property int last: 5

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
    Row {
        id: dots
        anchors { top: parent.top; topMargin: 24; horizontalCenter: parent.horizontalCenter }
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
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "FlowLocal"
                font.family: T.sans; font.pixelSize: T.t3xl
                font.weight: Font.Bold; font.letterSpacing: -0.9   // 700, не 800: Onest чернит
                color: T.text
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

        // === 1. Язык и модель ===
        Column {
            visible: wiz.step === 1
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

        // === 2. Микрофон ===
        Column {
            id: micStep
            visible: wiz.step === 2
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
                running: wiz.step === 2 && wiz.visible
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

        // === 3. Сочетание ===
        Column {
            visible: wiz.step === 3
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

        // === 4. Проверка вставки ===
        Column {
            visible: wiz.step === 4
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

        // === 5. Проба ===
        Column {
            id: trialStep
            visible: wiz.step === 5
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
                 : wiz.step === 1 ? (wiz.modelReady ? "Дальше"
                                     : wiz.downloading ? "Скачивается…" : "Скачать модель")
                 : wiz.step === wiz.last ? "Готово"
                 : "Дальше"
            onClicked: {
                if (wiz.step === 1 && !wiz.modelReady) {
                    if (!wiz.downloading) B.downloadModel(wiz.chosenModel);
                    return;
                }
                if (wiz.step === 1 && wiz.modelReady) B.setModel(wiz.chosenModel);
                if (wiz.step === wiz.last) { OB.finish(); return; }  // finish() сам закроет окно
                wiz.step += 1;
            }
        }
    }
}
