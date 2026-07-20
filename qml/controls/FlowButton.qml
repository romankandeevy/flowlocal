// Korti Button: высота 30 (--sm, в наших барах кнопки компактные), радиус 6,
// вес 600. Нажатие - сдвиг на 1px вниз, как задано в системе.
//
//   primary   = чернила на бумаге (главное действие)
//   secondary = --fill плюс линия
//   danger    = красный, только для разрушительного
//
// Имя не Button: так зовётся штатный тип QtQuick.Controls, и совпадение имён
// в одной папке - конфликт.
//
// Четыре состояния, а не одно. Отсутствие ховера читается как «недоделано»
// мгновенно, а выключенная кнопка без своего вида - как работающая, на которую
// нажали и ничего не случилось. Поэтому расписаны все: hover (заливка на
// ступень выше), pressed (пиксель вниз плюс ещё ступень), focus (кольцо, и
// только с клавиатуры) и disabled (гашение и обычный курсор).

import QtQuick

Item {
    id: btn
    property string label: ""
    property string kind: "secondary"    // primary | secondary | danger
    signal clicked()

    height: 30
    implicitWidth: Math.max(72, txt.implicitWidth + 24)
    width: implicitWidth

    // Таб доводит фокус до кнопки, Space и Enter её нажимают: пройти окно с
    // клавиатуры человек должен уметь, даже если сделает это раз в жизни.
    activeFocusOnTab: enabled

    // Мышиный ли фокус - разобрано в шапке FocusRing.qml.
    property bool mouseFocus: false
    readonly property bool visualFocus: activeFocus && !mouseFocus
    onActiveFocusChanged: if (!activeFocus) mouseFocus = false

    // Выключенная гасится целиком, а не перекрашивается по частям: одно
    // правило вместо ветвления в каждом из трёх видов.
    opacity: enabled ? 1 : 0.4
    Behavior on opacity { NumberAnimation { duration: T.durFast * 1000 } }

    Keys.onPressed: (e) => {
        if (e.key === Qt.Key_Space || e.key === Qt.Key_Return || e.key === Qt.Key_Enter) {
            btn.clicked();
            e.accepted = true;
        }
    }

    Rectangle {
        id: face
        anchors.fill: parent
        // Нажатие - на пиксель вниз. Не тень, не масштаб: система разрешает
        // ровно этот жест.
        y: ma.pressed ? 1 : 0
        radius: T.radiusSm
        color: {
            // Ступени одни и те же у всех видов: покой -> ховер -> нажатие.
            // Раньше нажатие цвета не меняло вовсе, и весь отклик держался на
            // сдвиге в один пиксель - на тёмной теме его было не разглядеть.
            if (btn.kind === "primary") {
                var a = ma.pressed ? 0.72 : ma.containsMouse ? 0.84 : 1.0;
                return Qt.rgba(T.ink.r, T.ink.g, T.ink.b, a);
            }
            if (btn.kind === "danger") {
                var d = ma.pressed ? 0.18 : ma.containsMouse ? 0.12 : 0.06;
                return Qt.rgba(T.danger.r, T.danger.g, T.danger.b, d);
            }
            return ma.pressed ? T.borderStrong : ma.containsMouse ? T.fillStrong : T.fill;
        }
        Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
        border.width: 1
        border.color: btn.kind === "primary" ? "transparent"
                    : btn.kind === "danger" ? Qt.rgba(T.danger.r, T.danger.g, T.danger.b, 0.30)
                    : ma.containsMouse ? T.borderStrong : T.border
        Behavior on border.color { ColorAnimation { duration: T.durFast * 1000 } }

        Text {
            id: txt
            anchors.centerIn: parent
            text: btn.label
            font.family: T.sans
            font.pixelSize: T.tSm
            font.weight: Font.DemiBold
            color: btn.kind === "primary" ? T.bg
                 : btn.kind === "danger" ? T.danger
                 : T.text
        }
    }

    FocusRing { target: face; on: btn.visualFocus }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        enabled: btn.enabled
        // Выключенной - обычная стрелка: палец обещает нажатие, которого не
        // будет.
        cursorShape: btn.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onPressed: { btn.mouseFocus = true; btn.forceActiveFocus() }
        onClicked: btn.clicked()
    }
}
