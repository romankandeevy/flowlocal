// Карточка-метрика: подпись моноширинным, число - крупно.
//
// Канон Korti (templates/app-shell, блок метрик): подпись 11px mono
// --text-muted, значение 32px / 800 / -.03em. Такое сочетание - голос системы:
// «числа и результат вместо прилагательных» (guidelines/brand-voice).
//
// Число намеренно крупнее всего на экране. Это единственное место, где человек
// видит не то, что программа умеет, а то, что она для него сделала. Поэтому оно
// и появляется живо: карточки всплывают лесенкой, а «живые» числа добегают до
// значения снизу вверх - не украшение, а «вот это про вас, смотрите».

import QtQuick

Card {
    id: root

    property string label: ""
    property string value: ""
    property string hint: ""

    // Если задан countTo - показываем не value, а число, добегающее от 0.
    // Форматированные строки («46 с») так не оживить, а чистый счётчик слов -
    // можно, и это самый убедительный из троих.
    property real countTo: -1
    property string suffix: ""
    property int order: 0            // место в ряду - для лесенки появления

    // Числа ещё нет, но будет. Не то же самое, что ноль.
    //
    // Скорость печати нельзя посчитать, пока человек не наговорил хотя бы
    // минуту, и раньше на её месте стоял прочерк - тем же кеглем 24 и тем же
    // жирным начертанием, что и настоящие числа рядом. Читалось это как
    // сломанное значение: два числа и одно битое. Прочерк вообще плохо годится
    // на роль «пока нечего показать» - в таблицах он значит «ноль» или
    // «неприменимо», а здесь не то и не другое.
    //
    // Поэтому ожидающая метрика говорит словами и вполголоса: обычный кегль,
    // приглушённый цвет. Строй ряда из трёх сохраняется, но карточка честно
    // выглядит приглашением, а не поломкой.
    property bool pending: false

    property real _shown: 0
    readonly property string _display: countTo >= 0
        ? Math.round(_shown) + suffix : value

    implicitHeight: col.implicitHeight + 32

    // Счётчик отдельной анимацией, а не внутри появления, и это не стиль.
    // Пока он жил внутри, число писалось один раз при сборке окна и застревало
    // навсегда: окно строится один раз за запуск, а приложение живёт в трее
    // сутками. У нового человека первое открытие давало «надиктовано 0», он
    // диктовал, возвращался - и видел рядом честное «сэкономлено 46 с» и ноль.
    // Теперь на каждую смену countTo счётчик добегает от текущего значения.
    NumberAnimation {
        id: count
        target: root; property: "_shown"
        duration: 520; easing.type: Easing.OutCubic
    }

    function runCount(from) {
        if (root.countTo < 0)
            return;
        count.stop();
        count.from = from;
        count.to = Math.max(0, root.countTo);
        count.start();
    }

    onCountToChanged: runCount(root._shown)

    // Появление: прозрачность и подъём на 8px, лесенкой по месту в ряду.
    // Korti разрешает фейды и небольшие сдвиги - пружин здесь нет.
    opacity: 0
    y: 8
    Component.onCompleted: appear.start()
    SequentialAnimation {
        id: appear
        // Вторая карточка ждёт первую, третья - вторую: 70 мс на шаг.
        PauseAnimation { duration: root.order * 70 }
        // Число добегает от нуля, пока карточка встаёт на место.
        ScriptAction { script: root.runCount(0) }
        ParallelAnimation {
            NumberAnimation { target: root; property: "opacity"; to: 1
                              duration: T.durBase * 1000; easing.type: Easing.OutCubic }
            NumberAnimation { target: root; property: "y"; to: 0
                              duration: T.durBase * 1000; easing.type: Easing.OutCubic }
        }
    }

    Item {
        width: parent.width
        implicitHeight: col.implicitHeight + 32

        Column {
            id: col
            anchors { left: parent.left; right: parent.right; top: parent.top
                      leftMargin: 16; rightMargin: 16; topMargin: 16 }
            spacing: 8

            Text {
                text: root.label
                font.family: T.mono
                font.pixelSize: T.t2xs
                color: T.textMuted
            }
            Text {
                text: root._display
                visible: !root.pending
                font.family: T.sans
                // 24, а не канонические 32. В Korti 32 - это --display, кегль
                // для ОДНОГО числа на экране. У нас их три в ряд, и рядом
                // заголовок страницы в 26: числа перебивали его, и страница
                // читалась как три заголовка подряд. 24 оставляет метрику
                // самым крупным в карточке, не споря с «Добрый вечер».
                font.pixelSize: T.t2xl
                // 700, не канонические 800: Onest в ExtraBold слишком чёрный,
                // на крупном числе это било по глазам. См. PageTitle.
                font.weight: Font.Bold
                font.letterSpacing: -0.72      // -.03em от 24px
                color: T.text
            }
            // Вместо числа - что надо сделать, чтобы оно появилось.
            Text {
                text: root.value
                visible: root.pending
                width: col.width
                wrapMode: Text.WordWrap
                font.family: T.sans
                font.pixelSize: T.tMd
                color: T.textSecondary
                lineHeight: 1.3
            }
            Text {
                text: root.hint
                visible: root.hint !== "" && !root.pending
                width: col.width
                wrapMode: Text.WordWrap
                font.family: T.sans
                font.pixelSize: T.t2xs
                color: T.textMuted
            }
        }
    }
}
