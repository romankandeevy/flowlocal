// Korti Input: высота 30, радиус 6, линия вместо заливки.
// Фокус - синий акцент: это ровно тот случай, для которого он в системе и
// заведён (фокус, ссылки, выделение), а не «включено».

import QtQuick

Item {
    id: field
    property alias text: input.text
    property string placeholder: ""
    property bool mono: false
    signal edited(string text)

    height: 30
    implicitWidth: 200
    width: implicitWidth

    Rectangle {
        anchors.fill: parent
        radius: T.radiusSm
        color: T.fillSubtle
        border.width: 1
        border.color: input.activeFocus ? T.accent : T.border

        TextInput {
            id: input
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            verticalAlignment: TextInput.AlignVCenter
            font.family: field.mono ? T.mono : T.sans
            font.pixelSize: field.mono ? T.tXs : T.tSm
            color: T.text
            selectByMouse: true
            selectionColor: Qt.rgba(T.accent.r, T.accent.g, T.accent.b, 0.30)
            selectedTextColor: T.text
            clip: true
            onTextEdited: field.edited(text)

            Text {
                anchors.verticalCenter: parent.verticalCenter
                visible: input.text === "" && !input.activeFocus
                text: field.placeholder
                font: input.font
                color: T.textFaint
            }
        }
    }
}
