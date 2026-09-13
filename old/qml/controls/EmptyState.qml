// Пустая страница: иконка, одна строка «что это» и одно действие «как начать».
//
// Вид не придуман заново. Он уже был утверждён на «Статистике» (задача 6
// плана): заголовок кеглем tMd, под ним сочетание клавиш плашками, под ними
// строка про то, что сделать. Там это работало, поэтому здесь ровно то же,
// плюс иконка и необязательная кнопка. Переделывать было бы хуже, чем
// повторить: два разных пустых экрана в одной программе читаются как два
// разных приложения.
//
// Почему пустоту вообще надо закрывать. Список без записей и поле без слов
// выглядят одинаково с не загрузившимся списком и сломанным полем. Человек,
// который поставил программу пять минут назад, увидит именно поломку - у него
// ещё нет опыта, чтобы отличить «пусто» от «не работает».
//
// ---- Здесь нет ни одного обращения к `B`, и это условие, а не случайность ----
//
// EmptyState - переиспользуемый контрол: его ставят разные страницы и диалоги,
// и опираться на то, что у хозяина есть контекстное свойство `B`, он не вправе.
// Одно упоминание `B` в привязке - и хозяин без него падает в ReferenceError,
// причём молча: QML напишет про это в консоль, которой под pythonw не
// существует. Поэтому и сочетание, и действие приходят снаружи свойствами, а
// читает их тот, у кого `B` есть.

import QtQuick

Item {
    id: box

    // Путь иконки из Icons.qml. Пусто - без иконки: заголовок останется
    // первым, и это законный вид, а не полупустая плашка.
    property string icon: ""
    // «Что это»: одна строка, существительное или действие. Не пересказывать
    // название страницы - человек нажал её сам и уже знает, куда попал.
    property string title: ""
    // «Как начать»: одна мысль. Здесь же говорим, что случится дальше.
    property string hint: ""
    // Сочетание клавиш плашками (готовая строка от inputspec.pretty). Пусто -
    // плашек нет. Это второй способ показать действие: там, где начать можно
    // только голосом, кнопке взяться неоткуда.
    property string combo: ""
    // Кнопка под подсказкой. Пусто - кнопки нет.
    property string actionLabel: ""
    // Начать нечем (сочетание не задано, микрофона нет): подсказка краснеет.
    // Красный тут честный - человеку и правда нужно сначала сходить в другое
    // место, иначе страница не заработает никогда.
    property bool alarm: false

    signal action()

    readonly property int pad: 24

    width: parent ? parent.width : 0
    implicitHeight: col.implicitHeight + 2 * pad

    Column {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top
                  leftMargin: box.pad; rightMargin: box.pad; topMargin: box.pad }
        spacing: 12

        // Иконка в плашке, а не сама по себе. Голый штрих Lucide на пустой
        // странице теряется: вокруг ничего нет, и глазу не за что зацепиться.
        // Заливка и волосяная линия - те же, что у клавиш в KeyCaps, своих
        // красок здесь не заведено.
        Rectangle {
            visible: box.icon !== ""
            width: 44
            height: 44
            radius: T.radiusMd
            color: T.fillSubtle
            border.width: 1
            border.color: T.border

            Icon {
                anchors.centerIn: parent
                path: box.icon
                size: 22
                color: T.textMuted
            }
        }

        Text {
            visible: box.title !== ""
            width: parent.width
            wrapMode: Text.WordWrap
            text: box.title
            font.family: T.sans
            font.pixelSize: T.tMd
            font.weight: Font.DemiBold
            font.letterSpacing: -0.2
            color: T.text
        }

        KeyCaps {
            visible: box.combo !== ""
            width: col.width
            combo: box.combo
        }

        Text {
            visible: box.hint !== ""
            width: parent.width
            wrapMode: Text.WordWrap
            text: box.hint
            font.family: T.sans
            font.pixelSize: T.tSm
            color: box.alarm ? T.danger : T.textMuted
            lineHeight: 1.5
        }

        FlowButton {
            visible: box.actionLabel !== ""
            label: box.actionLabel
            kind: "primary"
            onClicked: box.action()
        }
    }
}
