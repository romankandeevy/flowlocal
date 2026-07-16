// Выпадающий список. Радиус меню 8, строки 6 - как задано в Korti.
// Штатный ComboBox из QtQuick.Controls не берём: он тащит свой стиль, и
// перекрашивать его вышло бы дороже, чем нарисовать список из двух Rectangle.

import QtQuick

Item {
    id: sel
    property var options: []              // [{label, value}]
    property var value
    signal picked(var value)

    height: 30
    implicitWidth: 290
    width: implicitWidth

    function labelOf(v) {
        for (var i = 0; i < options.length; i++)
            if (options[i].value === v) return options[i].label;
        return options.length ? options[0].label : "";
    }

    Rectangle {
        id: head
        anchors.fill: parent
        radius: T.radiusSm
        color: ma.containsMouse ? T.fill : T.fillSubtle
        border.width: 1
        border.color: menu.visible ? T.accent : T.border

        Text {
            anchors { left: parent.left; leftMargin: 10; right: chev.left; rightMargin: 6
                      verticalCenter: parent.verticalCenter }
            text: sel.labelOf(sel.value)
            elide: Text.ElideRight
            font.family: T.sans
            font.pixelSize: T.tSm
            color: T.text
        }
        Text {
            id: chev
            anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
            text: "⌄"
            font.pixelSize: T.tSm
            color: T.textMuted
        }
        MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: menu.visible = !menu.visible
        }
    }

    Rectangle {
        id: menu
        visible: false
        z: 100
        anchors { top: head.bottom; topMargin: 4; left: head.left }
        width: head.width
        height: Math.min(240, list.contentHeight + 8)
        radius: T.radiusMd
        color: T.paper
        border.width: 1
        border.color: T.border

        ListView {
            id: list
            anchors.fill: parent
            anchors.margins: 4
            clip: true
            model: sel.options
            delegate: Rectangle {
                width: list.width
                height: 28
                radius: T.radiusSm
                color: ima.containsMouse ? T.fill : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 8; right: parent.right
                              rightMargin: 8; verticalCenter: parent.verticalCenter }
                    text: modelData.label
                    elide: Text.ElideRight
                    font.family: T.sans
                    font.pixelSize: T.tSm
                    color: modelData.value === sel.value ? T.text : T.textSecondary
                }
                MouseArea {
                    id: ima
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        sel.value = modelData.value;
                        sel.picked(modelData.value);
                        menu.visible = false;
                    }
                }
            }
        }
    }
}
