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

    // Тени нет: число внутри добегает до значения, а сама карточка всплывает
    // лесенкой. И то и другое - движение источника, то есть пересчёт размытия
    // на каждом кадре. См. Card.shadow.
    shadow: false

    property string label: ""
    property string value: ""
    property string hint: ""
    // Путь иконки Lucide рядом с подписью. Пусто - подпись без значка, как было
    // (на «Главной» иконок нет). На «Статистике» она даёт метрике опознавалку с
    // одного взгляда: время, слова, серия - каждая со своим знаком.
    property string icon: ""

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
        // 280 мс - самый долгий срок системы, и потолок: счётчик здесь главное
        // движение экрана, но он всё равно переход, а не заставка. Раньше стояло
        // 520 - вдвое дольше всего остального в окне, и ряд метрик досчитывал
        // уже после того, как страница встала.
        duration: T.durSlow * 1000
        easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut
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

    // Появление: прозрачность плюс лёгкий рост, лесенкой по месту в ряду.
    //
    // Было - подъём на 8px снизу (Translate). Сменено на scale 0.98->1, и не
    // ради разнообразия. Подъём читается как «элемент приехал откуда-то», то
    // есть тянет за собой вопрос «откуда»; рост из 98% читается как «элемент
    // проявился здесь» - у него нет ни направления, ни источника, поэтому и
    // спрашивать не о чем. На карточке, которая просто есть на странице, верно
    // второе.
    //
    // Заодно ушёл Translate: и scale, и он рисуются поверх раскладки, но scale
    // - штатное свойство Item, а не отдельный узел трансформации. Прежняя
    // причина брать Translate (свойство `y` перебивало Flow, и три карточки
    // складывались друг на друга) для scale не возникает вовсе.
    opacity: 0
    scale: 0.98
    Component.onCompleted: appear.start()
    SequentialAnimation {
        id: appear
        // Вторая карточка ждёт первую, третья - вторую. Шаг - половина
        // быстрого токена (60 мс), а не своё число: задержка лесенки - часть
        // того же движения, и когда токен изменят, шаг обязан поехать с ним.
        PauseAnimation { duration: root.order * T.durFast * 1000 / 2 }
        // Число добегает от нуля, пока карточка встаёт на место.
        ScriptAction { script: root.runCount(0) }
        ParallelAnimation {
            NumberAnimation { target: root; property: "opacity"; to: 1
                              duration: T.durBase * 1000
                              easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut }
            NumberAnimation { target: root; property: "scale"; to: 1
                              duration: T.durBase * 1000
                              easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut }
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

            // Подпись со значком в строку. Значок того же приглушённого цвета,
            // что и подпись, и на ступень крупнее кегля метки - иначе штрих
            // Lucide рядом с 11px мокнет в фон.
            Row {
                spacing: 6
                Icon {
                    visible: root.icon !== ""
                    anchors.verticalCenter: label.verticalCenter
                    path: root.icon
                    size: 14
                    color: T.textMuted
                }
                Text {
                    id: label
                    text: root.label
                    font.family: T.mono
                    font.pixelSize: T.t2xs
                    color: T.textMuted
                }
            }
            Text {
                text: root._display
                visible: !root.pending
                font.family: T.sans
                // Ширина и HorizontalFit - страховка от длинного значения.
                // Число здесь набрано без ограничений по ширине, и «3 ч 20 мин»
                // в карточке шириной 132 (три метрики в ряд на «Статистике»)
                // вылезало за её край поверх соседней. Qt сам уменьшает кегль
                // до нижней границы, и только когда это нужно: «45» и «46 с»
                // как были 24-м, так им и остаются.
                width: col.width
                fontSizeMode: Text.HorizontalFit
                minimumPixelSize: T.tMd
                // 20, а не канонические 32. В Korti 32 - это --display, кегль
                // для ОДНОГО числа на экране. У нас их три в ряд, и рядом
                // заголовок страницы: числа перебивали его, и страница
                // читалась как три заголовка подряд.
                //
                // Было 24 - и это ровно тот случай, ради которого шкалу свели к
                // пяти ступеням: 24 против 26 у заголовка «отличались» на
                // восемь процентов, то есть не отличались ничем. Теперь 20
                // против 26 - разница видна, и иерархия наконец есть: метрика
                // главная В КАРТОЧКЕ, заголовок главный НА СТРАНИЦЕ.
                font.pixelSize: T.tXl
                // 700, не канонические 800: Onest в ExtraBold слишком чёрный,
                // на крупном числе это било по глазам. См. PageTitle.
                font.weight: Font.Bold
                // От кегля, а не готовым числом: -0.72 было -.03em от 24, и
                // после сведения шкалы к пяти ступеням молча перестало им быть.
                font.letterSpacing: -0.03 * T.tXl
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
