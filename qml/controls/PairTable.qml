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

    Component.onCompleted: reload()

    function reload() {
        rows.clear();
        var items = B.pairs(storeKey);
        for (var i = 0; i < items.length; i++)
            rows.append({k: items[i].k, v: items[i].v});
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
        var out = [];
        for (var i = 0; i < rows.count; i++)
            out.push({k: rows.get(i).k, v: rows.get(i).v});
        B.setPairs(storeKey, out);
        recount();
    }

    ListModel { id: rows }

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
                Row {
                    spacing: 8
                    FlowInput {
                        width: 190
                        text: model.k
                        placeholder: table.leftPlaceholder
                        onEdited: (t) => { rows.setProperty(index, "k", t); table.commit() }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "→"
                        font.family: T.sans; font.pixelSize: T.tMd
                        color: T.textFaint
                    }
                    FlowInput {
                        width: 250
                        text: model.v
                        placeholder: table.rightPlaceholder
                        onEdited: (t) => { rows.setProperty(index, "v", t); table.commit() }
                    }
                    FlowButton {
                        label: L.t("Убрать")
                        onClicked: { rows.remove(index); table.commit() }
                    }
                }
            }
        }
    }
}
