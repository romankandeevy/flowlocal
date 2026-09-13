// Одна строка таблицы «слева -> справа»: два поля, стрелка между ними, «Убрать».
//
// Отдельным файлом, а не разметкой внутри PairTable, потому что таких строк там
// теперь два списка - свои подстановки и готовые, спрятанные под раскрытием, - и
// каждый со своей моделью. Держать одну и ту же разметку в двух Repeater значит
// однажды поправить одну и забыть вторую; здесь она одна на оба.
//
// Про модель строка не знает ничего: наружу уходят только «поправили левое»,
// «поправили правое» и «убрать», а какой ListModel это записывает, решает
// таблица. Иначе делегату пришлось бы тащить с собой ссылку на свой список.

import QtQuick

Row {
    id: pair

    property string keyText: ""
    property string valueText: ""
    property string leftPlaceholder: ""
    property string rightPlaceholder: ""

    signal keyEdited(string text)
    signal valueEdited(string text)
    signal removed()

    spacing: 8

    FlowInput {
        width: 190
        text: pair.keyText
        placeholder: pair.leftPlaceholder
        onEdited: (t) => pair.keyEdited(t)
    }
    Text {
        anchors.verticalCenter: parent.verticalCenter
        text: "→"
        font.family: T.sans; font.pixelSize: T.tMd
        color: T.textFaint
    }
    FlowInput {
        width: 250
        text: pair.valueText
        placeholder: pair.rightPlaceholder
        onEdited: (t) => pair.valueEdited(t)
    }
    FlowButton {
        label: L.t("Убрать")
        onClicked: pair.removed()
    }
}
