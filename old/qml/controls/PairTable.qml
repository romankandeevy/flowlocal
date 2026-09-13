// Таблица «слева -> справа» со строками, которые можно добавлять и убирать.
//
// Одна и та же машинерия нужна и заменам («моя почта» -> адрес), и правилам
// тона («outlook.exe» -> формально): разница только в подписях и в том, куда
// сохранять.
//
// Значение собирается из полей ЗАНОВО на каждую правку, а не правится по
// ключу: ключ редактируют прямо на месте, и «переименование» иначе
// превращалось бы в удалить-плюс-добавить с потерей значения на полпути.
//
// Кнопка «Добавить» - снаружи, в SectionHeader: внутри карточки она налезала
// на «Убрать» первой строки.
//
// ---- Два списка вместо одного ----
//
// Владелец сказал дословно: «там подстановки, и ты туда забил около полусотни
// просто системных, для программирования. Сделай это отдельным выездным
// пунктом, закрывающимся». Беда была не в том, что термины есть, а в том, что
// свои три подстановки лежали среди сотни чужих и терялись в них насмерть.
//
// Поэтому строк теперь два списка. `rows` - свои, они на виду и ровно там же,
// где были. `ready` - те, что принесла программа (технические термины,
// B.pairs помечает их признаком `ready`), и они спрятаны под раскрытием со
// стрелкой. Не удалены и не заперты: раскрыл - и правишь их ровно как раньше.
//
// Модели именно две, а не одна с признаком на строке. С одной моделью пришлось
// бы держать два Repeater поверх неё и прятать делегаты через visible: сотня
// полей ввода создавалась бы дважды, чтобы половину из них не показать.

import QtQuick

Card {
    id: table
    property string storeKey: ""
    property string leftPlaceholder: ""
    property string rightPlaceholder: ""
    // Строки без ключа не сохранятся - об этом надо сказать вслух, иначе
    // человек напишет значение, закроет окно и потеряет его.
    property int blanks: 0
    // Была ли таблица пустой, когда страницу открыли. Спрашивает страница:
    // пустое состояние живёт НАД таблицей, а не внутри неё - объяснять надо
    // до формы, а не под ней (ровно эту претензию владелец высказал про
    // подстановки).
    //
    // Не `rows.count === 0`: при showBlankRow в модели всегда лежит наше
    // приглашение, и по счётчику таблица не пуста никогда.
    //
    // И не живой пересчёт на каждую правку, хотя так было бы «точнее».
    // Пустое состояние выше таблицы занимает вчетверо больше места, чем
    // сменяющая его строка, - и схлопывалось бы оно на первой же букве,
    // которую человек печатает в поле. Поле уехало бы вверх из-под курсора
    // прямо во время ввода. Состояние меняется по перезаходу на страницу,
    // когда человек на неё не смотрит.
    property bool empty: true
    // Показывать пустую строку, когда записей нет. Пустая таблица с одной
    // серой надписью не объясняет, что это вообще такое: человек видит
    // сообщение, а не форму. Живая строка с двумя полями и стрелкой между
    // ними объясняет устройство сама, без единого слова.
    property bool showBlankRow: false

    // Подписи свёрнутого пункта. Задаёт страница, а не таблица: все тексты окна
    // живут в Settings.qml, и заводить им второе место незачем. Пусто -
    // раскрытие останется без объяснения, но не сломается.
    property string readyTitle: ""
    property string readyHint: ""
    // Сколько готовых строк спрятано - страница показывает это числом рядом с
    // заголовком, чтобы «пусто» и «свёрнуто» не путались.
    readonly property int readyCount: ready.count
    property bool readyOpen: false

    Component.onCompleted: reload()

    function reload() {
        rows.clear();
        ready.clear();
        var items = B.pairs(storeKey);
        for (var i = 0; i < items.length; i++) {
            var r = {k: items[i].k, v: items[i].v};
            if (items[i].ready) ready.append(r); else rows.append(r);
        }
        empty = rows.count === 0;      // до приглашения, а не после него
        if (rows.count === 0 && showBlankRow)
            rows.append({k: "", v: ""});
        recount();
    }
    function add() { rows.append({k: "", v: ""}); recount() }
    function recount() {
        var n = 0;
        for (var i = 0; i < rows.count; i++)
            if (rows.get(i).k.trim() === "") n++;
        // Единственная пустая строка - это наше приглашение (showBlankRow), а
        // не забытая человеком запись. Предупреждать «она не сохранится» про
        // строку, которую он не заводил, значит ругать его за нашу же затею.
        if (n === 1 && rows.count === 1 && rows.get(0).v.trim() === "")
            n = 0;
        blanks = n;
    }
    function commit() {
        // Готовые уходят на сохранение вместе со своими, даже когда пункт
        // свёрнут. B.setPairs собирает словарь ЗАНОВО из присланного, и отправь
        // мы только видимые - сотня терминов стёрлась бы от правки одной буквы
        // в чужой строке.
        var out = [];
        var i;
        for (i = 0; i < rows.count; i++)
            out.push({k: rows.get(i).k, v: rows.get(i).v});
        for (i = 0; i < ready.count; i++)
            out.push({k: ready.get(i).k, v: ready.get(i).v});
        B.setPairs(storeKey, out);
        recount();
    }

    ListModel { id: rows }
    ListModel { id: ready }

    // Серой строчки «пока пусто - нажмите «Добавить»» здесь больше нет, и это
    // не потеря: показать её было нельзя. showBlankRow всегда кладёт в модель
    // приглашение, то есть `rows.count === 0` не наступало никогда, и надпись
    // лежала мёртвой с того дня, как приглашение завели. Пустое состояние
    // теперь показывает страница - целиком, со знаком и объяснением.
    Item {
        width: parent.width
        implicitHeight: rows.count === 0 ? 52 : list.height + 28

        Column {
            id: list
            x: 24
            y: 14
            width: parent.width - 48
            spacing: 8

            Repeater {
                model: rows
                PairRow {
                    keyText: model.k
                    valueText: model.v
                    leftPlaceholder: table.leftPlaceholder
                    rightPlaceholder: table.rightPlaceholder
                    onKeyEdited: (t) => { rows.setProperty(index, "k", t); table.commit() }
                    onValueEdited: (t) => { rows.setProperty(index, "v", t); table.commit() }
                    onRemoved: { rows.remove(index); table.commit() }
                }
            }
        }
    }

    // ---- Готовые: свёрнутый пункт со стрелкой ----
    //
    // Появляется, только когда готовые строки есть. Технические термины
    // выключены - и таблица выглядит ровно как до этой правки.
    Item {
        id: readyBox
        width: parent.width
        visible: ready.count > 0
        implicitHeight: visible ? head.height + body.height : 0

        // Волосяная линия сверху - та же, что делит ряды карточки: пункт это
        // вторая часть таблицы, а не приклеенный к ней ящик.
        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top
                      leftMargin: 24; rightMargin: 24 }
            height: 1
            color: T.borderFlat
        }

        Icons { id: ico }

        Item {
            id: head
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 52

            Rectangle {
                anchors.fill: parent
                anchors.margins: 8
                radius: T.radiusSm
                color: hit.pressed ? T.fillStrong
                     : hit.containsMouse ? T.fill : "transparent"
                Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
            }

            Icon {
                id: chevron
                anchors { left: parent.left; leftMargin: 24
                          verticalCenter: parent.verticalCenter }
                path: ico.chevron
                size: 16
                weight: 2.2
                color: hit.containsMouse ? T.text : T.textMuted
                // Свёрнут - стрелка вправо, раскрыт - вниз. Шеврон в наборе
                // смотрит вниз, поэтому свёрнутое состояние - это поворот.
                rotation: table.readyOpen ? 0 : -90
                Behavior on rotation {
                    NumberAnimation { duration: T.durBase * 1000
                                      easing.type: Easing.Bezier
                                      easing.bezierCurve: T.easeOut }
                }
            }

            Column {
                anchors { left: chevron.right; leftMargin: 12
                          right: countText.left; rightMargin: 12
                          verticalCenter: parent.verticalCenter }
                spacing: 2
                Text {
                    width: parent.width
                    text: table.readyTitle
                    font.family: T.sans; font.pixelSize: T.tMd
                    color: T.text
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    visible: table.readyHint !== ""
                    text: table.readyHint
                    font.family: T.sans; font.pixelSize: T.tSm
                    color: T.textMuted
                    elide: Text.ElideRight
                }
            }

            Text {
                id: countText
                anchors { right: parent.right; rightMargin: 24
                          verticalCenter: parent.verticalCenter }
                text: ready.count
                font.family: T.mono; font.pixelSize: T.tSm
                color: T.textFaint
            }

            activeFocusOnTab: true
            property bool mouseFocus: false
            onActiveFocusChanged: if (!activeFocus) mouseFocus = false
            Keys.onPressed: (e) => {
                if (e.key === Qt.Key_Space || e.key === Qt.Key_Return
                        || e.key === Qt.Key_Enter) {
                    table.readyOpen = !table.readyOpen;
                    e.accepted = true;
                }
            }
            FocusRing {
                target: head
                targetRadius: T.radiusSm
                on: head.activeFocus && !head.mouseFocus
            }

            MouseArea {
                id: hit
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onPressed: { head.mouseFocus = true; head.forceActiveFocus() }
                onClicked: table.readyOpen = !table.readyOpen
            }
        }

        // Раскрытие - ростом высоты, как «подробнее» в SettingRow: соседи
        // обязаны разъезжаться, иначе сотня строк ляжет поверх страницы.
        //
        // Анимации у высоты нет намеренно. Под пунктом сотня полей ввода, и
        // прогонять их перекладку 180 мс подряд значит уронить кадры на любом
        // ноутбуке; у «подробнее» там один абзац текста. Раскрытие мгновенное,
        // движется только стрелка.
        Item {
            id: body
            anchors { left: parent.left; right: parent.right; top: head.bottom }
            clip: true
            height: table.readyOpen ? readyList.height + 22 : 0

            Column {
                id: readyList
                x: 24
                y: 6
                width: parent.width - 48
                spacing: 8

                Repeater {
                    // Делегаты не создаются, пока пункт свёрнут: сотня полей
                    // ввода в скрытой карточке - это её цена при каждом заходе
                    // на страницу, заплаченная ни за что.
                    model: table.readyOpen ? ready : null
                    PairRow {
                        keyText: model.k
                        valueText: model.v
                        leftPlaceholder: table.leftPlaceholder
                        rightPlaceholder: table.rightPlaceholder
                        onKeyEdited: (t) => { ready.setProperty(index, "k", t); table.commit() }
                        onValueEdited: (t) => { ready.setProperty(index, "v", t); table.commit() }
                        onRemoved: { ready.remove(index); table.commit() }
                    }
                }
            }
        }
    }
}
