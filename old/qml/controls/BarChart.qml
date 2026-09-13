// Неделя столбиками: «пн»…«вс», сегодня - акцентом, число - под курсором.
//
// Qt Graphs для этого не берём принципиально: он GPL-only и утянул бы весь
// проект в GPL (PLAN 3). Repeater из Rectangle - это Qt Quick, LGPLv3.
//
// ---- Почему неделя, а не тридцать дней ----
//
// Тридцать столбиков раньше и стояли. В окне 460 содержимому достаётся 420, за
// вычетом полей карточки графику остаётся 372 пикселя - это 12 пикселей на
// день. Подпись «пн» туда не влезает никакая, попасть мышью в такой столбик
// тоже нельзя. Получалась красивая полоска, по которой нельзя сказать даже,
// где вчера: график был, чтения не было. Семь дней дают 47 пикселей на
// столбик - хватает и на подпись, и на курсор.
//
// Данные - чернила, а не акцент: это данные, а не статус. Исключение одно -
// сегодняшний столбик: он отвечает на «а сегодня-то я сколько?», и глаз должен
// находить его без счёта слева направо.

import QtQuick

Item {
    id: chart

    // День: {label: "пн", value: 12, today: bool, hint: "16 июля · 12 слов"}.
    // Подпись подсказки собрана в Python: русское склонение числительных живёт
    // там (util.plural), и второй раз на JavaScript его заводить нельзя.
    property var days: []
    // Средние слова за день недели - линия-ориентир поверх столбцов. Число
    // считает Python (settings_qt._stats), здесь только рисуем. 0 - линии нет.
    property real avg: 0
    property int barGap: 6
    // Потолок ширины столбика. Колонка тянется за окном, а столбик - нет:
    // на колонке содержимого в 760 графику достаётся 712, это по 96 пикселей
    // на день, и семь дней превращались в семь плит. Столбик шириной с ладонь
    // перестаёт читаться как величина - глаз сравнивает высоты, а ширина
    // только мешает. Цель мыши при этом остаётся во всю колонку, поэтому
    // попадать по узкому столбику не нужно.
    property int maxBarW: 56

    // Полоса под подсказку держится всегда, даже когда её не показывают.
    // Иначе столбики подпрыгивали бы на каждое наведение мыши.
    readonly property int tipH: 26
    readonly property int labelH: 18

    property int hovered: -1
    // Данные сменились - подсказка от прошлого наведения не должна пережить
    // их: под курсором окажется другое число, а надпись останется старой.
    onDaysChanged: hovered = -1

    implicitWidth: 372
    implicitHeight: 150
    width: implicitWidth
    height: implicitHeight

    readonly property real maxValue: {
        var m = 0;
        for (var i = 0; i < days.length; i++) m = Math.max(m, days[i].value || 0);
        return m || 1;
    }
    readonly property real barsH: Math.max(0, height - tipH - 6 - labelH)
    readonly property real colW: days.length > 0
        ? (width - barGap * (days.length - 1)) / days.length : 0

    Row {
        anchors.fill: parent
        spacing: chart.barGap

        Repeater {
            model: chart.days.length

            Item {
                id: col
                width: chart.colW
                height: chart.height
                readonly property var day: chart.days[index] || ({})
                readonly property bool lit: chart.hovered === index
                // Рекордный день недели: самый высокий столбик. Ничья возможна -
                // подсветим оба, врать про «единственный» рекорд не станем.
                readonly property bool isRecord:
                    (col.day.value || 0) > 0 && (col.day.value || 0) === chart.maxValue

                Rectangle {
                    id: bar
                    anchors { bottom: dayLabel.top; bottomMargin: 8
                              horizontalCenter: parent.horizontalCenter }
                    width: Math.min(parent.width, chart.maxBarW)
                    radius: 3
                    // Пустой день - ниточка, а не пустота: иначе не видно, что
                    // день вообще был.
                    readonly property real full:
                        Math.max(2, chart.barsH * ((col.day.value || 0) / chart.maxValue))
                    color: col.day.today ? T.accent : T.ink
                    // Сегодня во всю силу, прочие дни - вполголоса. Под
                    // курсором столбик дотягивается до полной непрозрачности:
                    // это и есть отклик на наведение, подсказка сверху - его
                    // продолжение, а не единственный признак. Рекорд недели тоже
                    // во всю силу - так он выделен и без акцента, который занят
                    // «сегодня»: сегодня синим, рекорд плотными чернилами.
                    opacity: (col.day.value || 0) > 0
                             ? (col.day.today || col.lit || col.isRecord ? 1 : 0.72)
                             : (col.lit ? 0.3 : 0.16)
                    Behavior on opacity {
                        NumberAnimation { duration: T.durFast * 1000 }
                    }

                    // Высота - ПРИВЯЗКА, умноженная на коэффициент появления.
                    // Анимировать саму height нельзя: императивная запись рвёт
                    // привязку намертво, и график навсегда остаётся с высотами
                    // первого захода. У Repeater model - это длина массива, то
                    // есть всегда семь: делегаты не пересоздаются, и второй раз
                    // Component.onCompleted уже не играет. Симптом был
                    // издевательский: прозрачность живая, высота мёртвая - день
                    // без единого слова стоял высоким столбцом, а день с пиком
                    // лежал ниточкой. Проверено пробой, см. ревью 18.07.2026.
                    property real k: 0
                    height: bar.full * bar.k

                    // Столбцы вырастают снизу волной слева направо. Шаг волны -
                    // треть быстрого токена (40 мс), а не своё число: задержка
                    // тут часть того же движения и обязана ехать за токеном.
                    // К седьмому дню набегает 240 мс - под потолком системы.
                    // Korti разрешает: рост высоты - не пружина.
                    Component.onCompleted: grow.start()
                    SequentialAnimation {
                        id: grow
                        PauseAnimation { duration: index * T.durFast * 1000 / 3 }
                        NumberAnimation {
                            target: bar; property: "k"; from: 0; to: 1
                            duration: T.durSlow * 1000
                            easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut
                        }
                    }
                    Component.onDestruction: grow.stop()
                }

                // Число над столбиком - чтобы читать график, не наводя мышь.
                // Едет вместе с вершиной столбика (привязано к bar.top), поэтому
                // всплывает снизу вверх заодно с ростом. Сегодня - акцентом,
                // рекорд - плотным текстом, прочие тихо: числа не должны спорить
                // с самими столбцами. Нулевой день числа не показывает - ниточка
                // и так говорит «здесь ноль».
                Text {
                    visible: (col.day.value || 0) > 0
                    anchors { bottom: bar.top; bottomMargin: 3
                              horizontalCenter: bar.horizontalCenter }
                    text: col.day.value || 0
                    font.family: T.sans
                    font.pixelSize: T.t2xs
                    font.weight: (col.day.today || col.isRecord) ? Font.DemiBold
                                                                 : Font.Normal
                    color: col.day.today ? T.accent
                         : col.isRecord ? T.text : T.textMuted
                }

                Text {
                    id: dayLabel
                    anchors { bottom: parent.bottom
                              horizontalCenter: parent.horizontalCenter }
                    // Высота задана и текст прижат вниз: так низ подписи стоит
                    // ровно на дне колонки, а её верх - предсказуемо на
                    // chart.labelH выше. От этого верха и пляшет базовая линия
                    // столбцов (bar снизу к dayLabel.top), а значит и средняя
                    // линия ниже совпадает со столбцами до пикселя.
                    height: chart.labelH
                    verticalAlignment: Text.AlignBottom
                    text: col.day.label || ""
                    font.family: T.sans
                    font.pixelSize: T.t2xs
                    font.weight: col.day.today ? Font.DemiBold : Font.Normal
                    color: col.day.today ? T.text
                         : col.lit ? T.textSecondary : T.textMuted
                }

                // Цель мыши - вся колонка, а не столбик. Попасть в двухпиксельную
                // ниточку пустого дня нельзя, а узнать, что в тот день было
                // ровно ноль, человек имеет право.
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    onEntered: chart.hovered = index
                    onExited: if (chart.hovered === index) chart.hovered = -1
                }
            }
        }
    }

    // Средняя линия недели - тонкий пунктир поверх столбцов. Пунктиром, а не
    // сплошной: сплошная читается как ось графика, пунктир - как ориентир «вот
    // ваш обычный день». База линии - та же, что у столбцов (dayLabel держит её
    // ровной), поэтому линия и столбцы совпадают до пикселя. Число - из Python.
    Item {
        id: avgLine
        visible: chart.avg > 0 && chart.maxValue > 0
        x: 0
        width: chart.width
        height: 1
        y: (chart.height - chart.labelH - 8)
           - chart.barsH * Math.min(1, chart.avg / chart.maxValue)

        Row {
            height: 1
            spacing: 4
            Repeater {
                model: Math.max(1, Math.floor(chart.width / 10))
                Rectangle { width: 6; height: 1; color: T.borderStrong }
            }
        }
        Text {
            anchors { left: parent.left; top: parent.bottom; topMargin: 2 }
            text: L.t("среднее")
            font.family: T.sans
            font.pixelSize: T.t2xs
            color: T.textFaint
        }
    }

    // Подсказка: чернильная плашка в полосе над столбиками. Не всплывающее
    // окно и не поверх графика - у окна 420 пикселей ширины, и всплывашка
    // накрыла бы половину недели.
    Rectangle {
        id: tip
        readonly property var day: chart.hovered >= 0 ? chart.days[chart.hovered]
                                                      : null
        visible: !!day
        height: chart.tipH - 4
        width: tipText.implicitWidth + 16
        radius: T.radiusSm
        color: T.ink
        y: 0
        // По центру своего столбика, но не за краем графика: у «пн» и «вс»
        // плашка шире колонки и иначе уезжала бы за карточку.
        x: Math.max(0, Math.min(chart.width - width,
                                chart.hovered * (chart.colW + chart.barGap)
                                + chart.colW / 2 - width / 2))

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

    Text {
        anchors.centerIn: parent
        visible: chart.days.length === 0
        text: L.t("пока пусто")
        font.family: T.sans
        font.pixelSize: T.tSm
        color: T.textFaint
    }
}
