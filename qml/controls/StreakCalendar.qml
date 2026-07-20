// Календарь серии: клетка на день, полгода столбцами по неделям.
//
// Раскрывается нажатием на серию дней («Статистика»). Дуга серии отвечает
// «сколько дней подряд», а этот вид - «как эти дни прожиты»: где густо, где
// пусто и где всё оборвалось. Одно число такого не покажет.
//
// ---- Про краски, и почему молчащий день не красный ----
//
// Владелец просил «как гитхаб: густо - тёмно-зелёный, ничего не говорил -
// красным, пассивным». Зелёная лестница здесь ровно такая, а вот молчащий день
// красным не заливается, и это не самоволие.
//
// В Korti красный - один и означает одно: ошибка, разрушительное действие. Им
// подсвечено «удалить историю» и им же горит строка, когда настройка не
// сохранилась. Залив им сто дней в календаре, мы сказали бы человеку, что сто
// раз что-то сломалось, - а он просто не диктовал в выходные. Слово «пассивным»
// в просьбе и есть настоящее требование: день молчания должен быть ТИХИМ, а не
// тревожным. Тихий здесь - чернила в семь процентов: клетка на месте, видно,
// что день был, и она не кричит.
//
// Данные - зелёные, потому что зелёный в системе значит «получилось». Акцент
// (синий) не берём: он занят фокусом и «сегодня», и на нём же стоит дуга серии
// рядом. Сегодняшняя клетка отмечена тонкой акцентной рамкой - её ищут глазом
// первой.
//
// Насыщенность считает Python (stats.calendar): уровень 0..4 - доля от лучшего
// дня в окне, а не от круглого числа слов. Здесь только краски.

import QtQuick

Item {
    id: cal

    // Клетки по датам, они же порядок обхода сетки сверху вниз, столбец за
    // столбцом: {level: 0..4, today: bool, future: bool, hint: "17 июля · 12 слов"}.
    // Подсказка собрана в Python - русское склонение числительных живёт там.
    property var days: []
    // Подписи месяцев над столбцами: {label: "июл", col: 3}.
    property var months: []
    // «пн»…«вс» - подписи строк. Приходят из stats, а не пишутся здесь: порядок
    // обязан совпадать с сеткой, и держать его в двух местах нельзя.
    property var weekdays: []
    property int weeks: 26

    readonly property int gap: 3
    readonly property int labelW: 26
    // Скругление клетки - как у столбиков недельного графика (BarChart, radius
    // 3), а не радиус из токенов: RADIUS_SM это шесть, то есть половина клетки,
    // и квадратики превратились бы в кружки. Мелкая графика в системе живёт по
    // этому же числу, второго мнения о нём в проекте нет.
    readonly property int cellRadius: 3
    readonly property int monthsH: 16
    readonly property int legendH: 20
    // Полоса под подсказку держится всегда, даже когда её не показывают, -
    // иначе сетка подпрыгивала бы на каждое наведение мыши (как в BarChart).
    readonly property int tipH: 24

    // Клетка тянется за шириной колонки, но в разумных пределах: на узком окне
    // мельче восьми пикселей в неё не попасть мышью, на широком крупнее
    // шестнадцати она перестаёт читаться как сетка и становится плиткой.
    readonly property int cell: Math.max(8, Math.min(16,
        Math.floor((width - labelW - gap * (weeks - 1)) / weeks)))
    readonly property int step: cell + gap
    readonly property int gridW: weeks * step - gap
    readonly property int gridH: 7 * step - gap

    implicitHeight: tipH + monthsH + gridH + legendH + 8

    // Какая клетка под курсором. -1 - мышь ушла или наведена на пустое место.
    property int hovered: -1
    // Данные сменились - подсказка от прошлого наведения не должна их пережить.
    onDaysChanged: hovered = -1

    // Краски читаются через T.ink и T.success, а не через T.inkA(): привязка
    // следит за СВОЙСТВАМИ, прочитанными во время счёта, а вызов слота таким
    // свойством не является. С inkA() календарь остался бы в старых красках до
    // перерисовки, когда человек переключит тему на живом окне.
    function cellColor(level) {
        if (level <= 0)
            return Qt.rgba(T.ink.r, T.ink.g, T.ink.b, 0.07);
        // Четыре ступени зелёного. Верхняя - чистый success, ниже - он же
        // прозрачностью: своих красок не заводим, лестница считается от токена.
        var a = [0, 0.28, 0.48, 0.72, 1.0][Math.min(4, level)];
        return Qt.rgba(T.success.r, T.success.g, T.success.b, a);
    }

    // ---- подсказка ----
    Rectangle {
        id: tip
        readonly property var day: (cal.hovered >= 0 && cal.hovered < cal.days.length)
                                   ? cal.days[cal.hovered] : null
        visible: !!day && (day.hint || "") !== ""
        height: cal.tipH - 4
        width: tipText.implicitWidth + 16
        radius: T.radiusSm
        color: T.ink
        y: 0
        // По центру своего столбца, но не за краем сетки: у крайних недель
        // плашка шире клетки и иначе уезжала бы за карточку.
        x: Math.max(0, Math.min(cal.width - width,
                                cal.labelW + Math.floor(cal.hovered / 7) * cal.step
                                + cal.cell / 2 - width / 2))

        Text {
            id: tipText
            anchors.centerIn: parent
            text: tip.day ? (tip.day.hint || "") : ""
            font.family: T.sans
            font.pixelSize: T.t2xs
            font.weight: Font.Medium
            color: T.bg
        }
    }

    // ---- месяцы ----
    Item {
        id: monthRow
        anchors { left: parent.left; leftMargin: cal.labelW
                  top: parent.top; topMargin: cal.tipH }
        width: cal.gridW
        height: cal.monthsH

        Repeater {
            model: cal.months
            Text {
                x: (modelData.col || 0) * cal.step
                text: modelData.label || ""
                font.family: T.sans
                font.pixelSize: T.t2xs
                color: T.textFaint
            }
        }
    }

    // ---- сетка ----
    Item {
        id: gridBox
        anchors { left: parent.left; top: monthRow.bottom }
        width: cal.labelW + cal.gridW
        height: cal.gridH

        // Подписи строк - через одну: семь надписей подряд при клетке в десять
        // пикселей сливаются в серую полосу. «пн», «ср», «пт» хватает, чтобы
        // понять, где верх недели и где выходные.
        Repeater {
            model: cal.weekdays
            Text {
                visible: index % 2 === 0
                y: index * cal.step + (cal.cell - height) / 2
                text: modelData
                font.family: T.sans
                font.pixelSize: T.t2xs
                color: T.textFaint
            }
        }

        Grid {
            id: grid
            x: cal.labelW
            rows: 7
            columns: cal.weeks
            // Столбец - это неделя, поэтому заполняем сверху вниз: порядок
            // клеток совпадает с порядком дат в days, и считать индексы на
            // JavaScript не нужно.
            flow: Grid.TopToBottom
            rowSpacing: cal.gap
            columnSpacing: cal.gap

            Repeater {
                model: cal.days.length

                Rectangle {
                    readonly property var day: cal.days[index] || ({})
                    width: cal.cell
                    height: cal.cell
                    radius: cal.cellRadius
                    // Дни после сегодняшнего не рисуем вовсе. Даже пустая
                    // клетка в завтра утверждала бы, что мы что-то знаем про
                    // завтра; место при этом занято, и сетка не съезжает.
                    visible: !day.future
                    color: cal.cellColor(day.level || 0)
                    border.width: day.today ? 1 : 0
                    border.color: T.accent
                    // Под курсором клетка проявляется - отклик на наведение,
                    // подсказка сверху его продолжение, а не единственный знак.
                    opacity: cal.hovered === index ? 0.75 : 1
                    Behavior on opacity {
                        NumberAnimation { duration: T.durFast * 1000 }
                    }
                }
            }
        }

        // Одна мышь на всю сетку, а не сто восемьдесят областей по клеткам:
        // индекс считается из координат, и промежутки между клетками при этом
        // тоже ведут к ближайшему дню - попадать в девять пикселей точно не
        // нужно.
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onExited: cal.hovered = -1
            onPositionChanged: (m) => {
                var col = Math.floor((m.x - cal.labelW) / cal.step);
                var r = Math.floor(m.y / cal.step);
                if (m.x < cal.labelW || col < 0 || col >= cal.weeks || r < 0 || r > 6)
                    cal.hovered = -1;
                else
                    cal.hovered = col * 7 + r;
            }
        }
    }

    // ---- лестница ----
    Row {
        anchors { right: parent.right; top: gridBox.bottom; topMargin: 6 }
        spacing: cal.gap
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: L.t("тише")
            font.family: T.sans; font.pixelSize: T.t2xs
            color: T.textFaint
            rightPadding: 4
        }
        Repeater {
            model: 5
            Rectangle {
                width: cal.cell; height: cal.cell
                radius: cal.cellRadius
                color: cal.cellColor(index)
            }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: L.t("гуще")
            font.family: T.sans; font.pixelSize: T.t2xs
            color: T.textFaint
            leftPadding: 4
        }
    }
}
