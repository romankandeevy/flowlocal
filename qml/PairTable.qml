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
    property string emptyText: ""
    property string leftPlaceholder: ""
    property string rightPlaceholder: ""
    // Строки без ключа не сохранятся - об этом надо сказать вслух, иначе
    // человек напишет значение, закроет окно и потеряет его.
    property int blanks: 0

    Component.onCompleted: reload()

    function reload() {
        rows.clear();
        var items = B.pairs(storeKey);
        for (var i = 0; i < items.length; i++)
            rows.append({k: items[i].k, v: items[i].v});
        recount();
    }
    function add() { rows.append({k: "", v: ""}); recount() }
    function recount() {
        var n = 0;
        for (var i = 0; i < rows.count; i++)
            if (rows.get(i).k.trim() === "") n++;
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

    Item {
        width: parent.width
        implicitHeight: rows.count === 0 ? 52 : list.height + 28

        Text {
            x: 24
            anchors.verticalCenter: parent.verticalCenter
            visible: rows.count === 0
            text: table.emptyText
            font.family: T.sans; font.pixelSize: T.tSm
            color: T.textFaint
        }

        Column {
            id: list
            x: 24
            y: 14
            width: parent.width - 48
            spacing: 6

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
                        label: "Убрать"
                        onClicked: { rows.remove(index); table.commit() }
                    }
                }
            }
        }
    }
}
