// Korti Switch: 38x22, ручка 16, ход 16.
// Включённый - это ЧЕРНИЛА, а не акцент: акцент в системе выделяет особое, а
// не «включено». Размеры сверены по .jsx из системы, а не на глаз.

import QtQuick

Item {
    id: sw
    property bool value: false
    signal toggled(bool value)

    width: 38
    height: 22

    // Ход ручки - тот же, что у всех переходов: 180 мс, .2,.8,.2,1, без пружин.
    property real pos: value ? 1 : 0
    Behavior on pos { NumberAnimation { duration: T.durBase * 1000
                                        easing.type: Easing.Bezier
                                        easing.bezierCurve: T.easeOut } }

    Rectangle {
        id: track
        anchors.fill: parent
        radius: height / 2
        color: {
            var base = Qt.tint(T.fillStrong, Qt.rgba(T.ink.r, T.ink.g, T.ink.b, sw.pos));
            // ховер по правилу системы: заливка на ступень выше, без смены цвета
            return (ma.containsMouse && sw.pos < 0.5)
                   ? Qt.tint(base, Qt.rgba(T.ink.r, T.ink.g, T.ink.b, 0.06)) : base;
        }
        border.width: 1
        border.color: sw.pos < 0.5 ? T.border : T.ink
    }

    Rectangle {
        width: 16; height: 16; radius: 8
        color: T.bg
        y: 3
        x: 3 + sw.pos * 16
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: { sw.value = !sw.value; sw.toggled(sw.value) }
    }
}
