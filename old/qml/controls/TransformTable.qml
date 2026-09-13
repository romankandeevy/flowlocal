// Свои преобразования: «название» и «что сделать с текстом».
//
// Похоже на PairTable, но не она. Там слева ключ, справа значение, и обе
// стороны короткие; здесь справа - фраза, которую человек пишет словами, и
// поле под неё нужно втрое шире. Разводить одну таблицу параметрами вышло бы
// дороже, чем написать вторую: сюда ещё придёт ограничение на количество и
// подсказка про указание, а туда - нет.
//
// Указание уходит в модель как есть. Это единственное место в программе, где
// человек говорит с моделью напрямую, и переписывать его формулировку под наш
// формат мы не будем: он лучше знает, чего хочет.

import QtQuick

Card {
    id: table
    // Сколько своих можно завести. Больше не влезет в список, который
    // выбирают цифрой с клавиатуры (transforms.MAX_CUSTOM).
    readonly property int limit: B.maxTransforms
    readonly property bool full: rows.count >= limit
    property int blanks: 0

    Component.onCompleted: reload()

    function reload() {
        rows.clear();
        var items = B.customTransforms();
        for (var i = 0; i < items.length; i++)
            rows.append({title: items[i].title, instruction: items[i].instruction});
        recount();
    }
    function add() { if (!full) { rows.append({title: "", instruction: ""}); recount() } }
    function recount() {
        var n = 0;
        for (var i = 0; i < rows.count; i++)
            if (rows.get(i).title.trim() === "" || rows.get(i).instruction.trim() === "")
                n++;
        blanks = n;
    }
    function commit() {
        var out = [];
        for (var i = 0; i < rows.count; i++)
            out.push({title: rows.get(i).title, instruction: rows.get(i).instruction});
        B.setCustomTransforms(out);
        recount();
    }

    ListModel { id: rows }

    // Иконка пустому состоянию берётся отсюда: Icons намеренно не синглтон,
    // а тянуть `ic` из окна-хозяина значит связать таблицу с конкретной
    // страницей настроек.
    Icons { id: ico }

    Item {
        width: parent.width
        // Пусто - высоту диктует само пустое состояние: серая строчка влезала
        // в 52 пикселя, знак с объяснением - нет.
        implicitHeight: rows.count === 0 ? blank.implicitHeight : list.height + 28

        // Серая строчка «своих пока нет» была честной, но неотличимой от
        // пустого поля: на свежей установке своих преобразований нет ни у
        // кого, и первое, что человек здесь видел, - пустая карточка.
        EmptyState {
            id: blank
            visible: rows.count === 0
            icon: ico.sparkles
            title: L.t("Своих преобразований пока нет")
            hint: L.t("Нажмите «Добавить»: слева название, справа - что ")
                  + L.t("сделать с выделенным текстом.")
        }

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
                        width: 170
                        text: model.title
                        placeholder: L.t("По-деловому")
                        onEdited: (t) => { rows.setProperty(index, "title", t); table.commit() }
                    }
                    FlowInput {
                        width: 380
                        text: model.instruction
                        placeholder: L.t("Перепиши вежливо и по делу, ничего не выбрасывая")
                        onEdited: (t) => { rows.setProperty(index, "instruction", t); table.commit() }
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
