// Дуга серии: «дней подряд» кольцом, а не голым числом. Заполнение дуги - доля
// текущей серии от рекордной (best): полное кольцо значит «вы на своём рекорде».
// Рекорд - честное число из истории (stats._best_streak), а не выдуманная цель
// вроде «до семи»: дуга не должна врать, к чему человек идёт.
//
// Рисуем на Canvas, как Icon.qml: у Qt Canvas есть ctx.arc, и ни QtQuick.Shapes,
// ни плагин SVG ради одной дуги тащить незачем. Число - обычный Text поверх
// холста: так оно чёткое и красится токеном, а не пикселями canvas.
//
// Движение по токенам: дуга растёт от нуля за durSlow той же кривой easeOut, что
// и всё в системе, число добегает снизу - как в Metric. Пружин нет.
//
// Стоит в ряду метрик «Статистики» и подогнан к ним по высоте (implicitHeight
// 82), чтобы сетка из трёх оставалась ровной. Тени нет: внутри движется дуга, и
// тень пересчитывалась бы на каждом кадре (та же причина, что у Metric).

import QtQuick

Card {
    id: ring
    shadow: false

    property int value: 0        // текущая серия, дней
    property int best: 0         // рекорд серии - потолок дуги
    property string label: ""    // подпись рядом с числом
    property string record: ""   // строка рекорда под подписью, напр. «рекорд 7»

    // Дуга умеет раскрываться в календарь по дням - об этом просил владелец
    // словами «если нажать на стрик, сделай календарь». Сам календарь рисует не
    // она: метрика в ряду из трёх не может развернуться на всю ширину страницы,
    // не сломав сетку. Поэтому здесь только нажатие и шеврон, а показывает
    // календарь страница (Settings.qml, «Статистика»).
    //
    // Выключено по умолчанию: без обработчика нажатия курсор-рука и шеврон
    // обещали бы то, чего не будет.
    property bool expandable: false
    property bool open: false
    signal activated()

    // Доля кольца. best может быть нулём только при пустой истории, а там
    // страница показывает пустое состояние, не эту дугу, - но делим осторожно.
    readonly property real target: best > 0 ? Math.min(1, value / best) : 0

    implicitHeight: 82

    // Обе величины добегают до цели: дуга - заполнением, число - счётом снизу.
    // Отдельными свойствами, потому что цель у них разная (доля и штуки).
    property real progress: 0
    property real shown: 0

    // Анимации отдельными объектами с императивным from/to, а не «NumberAnimation
    // on progress» источником значения: то же, что в Metric, и по той же причине.
    // Данные приходят не при сборке окна, а на заходе на «Статистику» (окно живёт
    // в трее сутками), и цель - привязка (value/best). Источник значения читает
    // такую привязку один раз при подключении и на перезапуск новую цель не
    // берёт: дуга так и осталась бы пустой. Здесь from/to выставляются в момент
    // старта, поэтому догоняют любое новое значение.
    NumberAnimation {
        id: arc
        target: ring; property: "progress"
        duration: T.durSlow * 1000
        easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut
    }
    NumberAnimation {
        id: num
        target: ring; property: "shown"
        duration: T.durSlow * 1000
        easing.type: Easing.Bezier; easing.bezierCurve: T.easeOut
    }
    function runArc() { arc.stop(); arc.from = ring.progress; arc.to = ring.target; arc.start() }
    function runNum() { num.stop(); num.from = ring.shown; num.to = ring.value; num.start() }
    onTargetChanged: runArc()
    onValueChanged: runNum()
    Component.onCompleted: { runArc(); runNum() }
    onProgressChanged: canvas.requestPaint()

    // Иконки своим инстансом, а не через `ic` окна-хозяина: тот же довод, что в
    // SettingRow - компонент не должен знать, в каком окне он стоит.
    Icons { id: ico }

    Item {
        id: box
        width: parent.width
        implicitHeight: 82

        // Подсветка нажатия - под содержимым, поэтому объявлена первой. Радиус
        // берём у карточки; в раскладке «линии» коробки нет, и скругления тоже.
        Rectangle {
            anchors.fill: parent
            visible: ring.expandable
            radius: ring.lines ? 0 : T.radiusLg
            color: hit.pressed ? T.fillStrong
                 : hit.containsMouse ? T.fill : "transparent"
            Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
        }

        Row {
            anchors { left: parent.left; leftMargin: 16
                      verticalCenter: parent.verticalCenter }
            spacing: 12

            Item {
                width: 56; height: 56
                anchors.verticalCenter: parent.verticalCenter

                Canvas {
                    id: canvas
                    anchors.fill: parent
                    // Canvas не следит за привязками (см. Icon.qml): на смену
                    // темы краски дорожки и дуги поменялись бы только после
                    // перерисовки, поэтому просим её на сигнал токенов.
                    Connections { target: T; function onChanged() { canvas.requestPaint() } }
                    onPaint: {
                        var ctx = getContext("2d");
                        ctx.reset();
                        var lw = 5;
                        var c = width / 2;
                        var r = (width - lw) / 2;
                        // Дорожка - полное кольцо тихой заливкой чернил.
                        ctx.beginPath();
                        ctx.arc(c, c, r, 0, 2 * Math.PI);
                        ctx.lineWidth = lw;
                        ctx.strokeStyle = Qt.rgba(T.ink.r, T.ink.g, T.ink.b, 0.10);
                        ctx.stroke();
                        // Заполнение - от 12 часов по часовой на долю progress.
                        // Акцентом: серия - то самое «особенное», для чего синий
                        // в системе и заведён (сегодняшний столбик графика тоже
                        // акцентный, и это не спор - там один день, тут итог).
                        if (ring.progress > 0) {
                            var a0 = -Math.PI / 2;
                            ctx.beginPath();
                            ctx.arc(c, c, r, a0, a0 + 2 * Math.PI * ring.progress);
                            ctx.lineWidth = lw;
                            ctx.lineCap = "round";
                            ctx.strokeStyle = T.accent;
                            ctx.stroke();
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    text: Math.round(ring.shown)
                    font.family: T.sans
                    font.pixelSize: T.tXl
                    font.weight: Font.Bold
                    font.letterSpacing: -0.03 * T.tXl
                    color: T.text
                }
            }

            Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Text {
                    text: ring.label
                    font.family: T.mono
                    font.pixelSize: T.t2xs
                    color: T.textMuted
                }
                Text {
                    visible: ring.record !== ""
                    text: ring.record
                    font.family: T.sans
                    font.pixelSize: T.t2xs
                    color: T.textFaint
                }
                // Что случится по нажатию - словом, а не одним шевроном.
                // Программу ставят людям, которые просто пишут письма: значок
                // им ещё надо узнать, а слово они прочитают (тот же довод, что
                // у «подробнее» в SettingRow).
                Text {
                    visible: ring.expandable
                    text: ring.open ? L.t("свернуть") : L.t("по дням")
                    font.family: T.sans
                    font.pixelSize: T.t2xs
                    font.weight: Font.Medium
                    color: hit.containsMouse ? T.text : T.textMuted
                }
            }
        }

        Icon {
            visible: ring.expandable
            anchors { right: parent.right; rightMargin: 16
                      verticalCenter: parent.verticalCenter }
            path: ico.chevron
            size: 14
            // Мелкая иконка требует штриха потолще - как в SettingRow.
            weight: 2.4
            color: hit.containsMouse ? T.text : T.textMuted
            rotation: ring.open ? 180 : 0
            Behavior on rotation {
                NumberAnimation { duration: T.durBase * 1000
                                  easing.type: Easing.Bezier
                                  easing.bezierCurve: T.easeOut }
            }
        }

        // Клавиатура доходит и сюда: календарь за дугой - единственная дверь к
        // виду по дням, и обходить её табом стороной нельзя.
        activeFocusOnTab: ring.expandable
        property bool mouseFocus: false
        onActiveFocusChanged: if (!activeFocus) mouseFocus = false
        Keys.onPressed: (e) => {
            if (e.key === Qt.Key_Space || e.key === Qt.Key_Return
                    || e.key === Qt.Key_Enter) {
                ring.activated();
                e.accepted = true;
            }
        }
        // Радиус задаём явно: цель - Item, у него скругления нет вовсе, и
        // кольцо вышло бы прямоугольным вокруг круглой карточки.
        FocusRing {
            target: box
            targetRadius: ring.lines ? 0 : T.radiusLg
            on: box.activeFocus && !box.mouseFocus
        }

        MouseArea {
            id: hit
            anchors.fill: parent
            enabled: ring.expandable
            hoverEnabled: ring.expandable
            cursorShape: Qt.PointingHandCursor
            onPressed: { box.mouseFocus = true; box.forceActiveFocus() }
            onClicked: ring.activated()
        }
    }
}
