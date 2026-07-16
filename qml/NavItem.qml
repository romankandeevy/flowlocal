// Строка бокового меню - по канону Korti (templates/app-shell): иконка плюс
// текст, gap 11, padding 8/10, радиус 6, кегль 14, вес 500. Активная - заливка
// --fill и чернила, остальные - --text-secondary.
//
// Синим не красим: акцент в системе для особенного (фокус, ссылки), а не для
// «тут я сейчас».

import QtQuick

Item {
    id: nav
    property string label: ""
    property string icon: ""
    property bool active: false
    signal clicked()

    width: 186
    height: 34

    Rectangle {
        anchors.fill: parent
        radius: T.radiusSm
        color: nav.active ? T.fill : (ma.containsMouse ? T.fillSubtle : "transparent")
        Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }

        Row {
            anchors { left: parent.left; leftMargin: 10
                      verticalCenter: parent.verticalCenter }
            spacing: 11

            Icon {
                anchors.verticalCenter: parent.verticalCenter
                path: nav.icon
                size: 17
                color: nav.active ? T.text : T.textMuted
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: nav.label
                font.family: T.sans
                font.pixelSize: T.tBase
                font.weight: Font.Medium
                color: nav.active ? T.text : T.textSecondary
            }
        }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: nav.clicked()
    }
}
