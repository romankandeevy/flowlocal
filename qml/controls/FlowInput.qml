// Korti Input: высота 30, радиус 6, линия вместо заливки.
// Фокус - синий акцент: это ровно тот случай, для которого он в системе и
// заведён (фокус, ссылки, выделение), а не «включено».
//
// Кольца фокуса тут нет намеренно, и это единственный контрол-исключение. У
// поля ввода о фокусе говорят мигающий курсор внутри и акцентная рамка -
// третий признак того же события лишний. Кольцо к тому же зажигается только на
// клавиатурный фокус, а в поле приходят и мышью, и табом одинаково часто.

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

    opacity: enabled ? 1 : 0.4
    Behavior on opacity { NumberAnimation { duration: T.durFast * 1000 } }

    Rectangle {
        anchors.fill: parent
        radius: T.radiusSm
        // Ховер поднимает заливку на ступень: без него поле неотличимо от
        // подписи рядом, пока в него не ткнёшь.
        color: (ma.containsMouse && !input.activeFocus) ? T.fill : T.fillSubtle
        Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
        border.width: 1
        border.color: input.activeFocus ? T.accent
                    : ma.containsMouse ? T.borderStrong : T.border
        Behavior on border.color { ColorAnimation { duration: T.durFast * 1000 } }

        // Ховер ловим отдельной областью поверх всего поля: TextInput сам
        // hoverEnabled не умеет. acceptedButtons: NoButton обязательно - иначе
        // область съест клики, и вместе с ними установку курсора и выделение
        // мышью, то есть поле перестанет быть полем.
        MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.NoButton
            cursorShape: field.enabled ? Qt.IBeamCursor : Qt.ArrowCursor
        }

        TextInput {
            id: input
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            enabled: field.enabled
            verticalAlignment: TextInput.AlignVCenter
            font.family: field.mono ? T.mono : T.sans
            font.pixelSize: field.mono ? T.t2xs : T.tSm
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
