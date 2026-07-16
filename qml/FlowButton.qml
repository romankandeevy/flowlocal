// Korti Button: высота 30 (--sm, в наших барах кнопки компактные), радиус 6,
// вес 600. Нажатие - сдвиг на 1px вниз, как задано в системе.
//
//   primary   = чернила на бумаге (главное действие)
//   secondary = --fill плюс линия
//   danger    = красный, только для разрушительного
//
// Имя не Button: так зовётся штатный тип QtQuick.Controls, и совпадение имён
// в одной папке - конфликт.

import QtQuick

Item {
    id: btn
    property string label: ""
    property string kind: "secondary"    // primary | secondary | danger
    signal clicked()

    height: 30
    implicitWidth: Math.max(72, txt.implicitWidth + 24)
    width: implicitWidth

    Rectangle {
        anchors.fill: parent
        // Нажатие - на пиксель вниз. Не тень, не масштаб: система разрешает
        // ровно этот жест.
        y: ma.pressed ? 1 : 0
        radius: T.radiusSm
        color: {
            if (btn.kind === "primary")
                return ma.containsMouse ? Qt.rgba(T.ink.r, T.ink.g, T.ink.b, 0.84) : T.ink;
            if (btn.kind === "danger")
                return ma.containsMouse ? Qt.rgba(T.danger.r, T.danger.g, T.danger.b, 0.12)
                                        : Qt.rgba(T.danger.r, T.danger.g, T.danger.b, 0.06);
            return ma.containsMouse ? T.fillStrong : T.fill;
        }
        border.width: 1
        border.color: btn.kind === "primary" ? "transparent"
                    : btn.kind === "danger" ? Qt.rgba(T.danger.r, T.danger.g, T.danger.b, 0.30)
                    : T.border

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

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: btn.clicked()
    }
}
