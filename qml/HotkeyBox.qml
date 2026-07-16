// Поле «нажмите сочетание». Клик -> захват, Esc -> отмена.
//
// Сам захват живёт в Python (backend.startCapture): ловить надо и клавиши, и
// боковые кнопки мыши, а Qt отдаёт только свои события и только когда окно в
// фокусе. Имена клавиш обязаны совпадать с теми, которыми приложение вешает
// хоткей, - иначе поле и хук поймут «ctrl» по-разному, а такой баг уже был.
// Разбор и показ - через inputspec, таблицы общие с приложением.

import QtQuick

Item {
    id: box
    property string value: ""
    property string pretty: ""            // человекочитаемое из inputspec.pretty
    property bool capturing: false
    property bool allowClear: false
    signal startCapture()
    signal cancelCapture()
    signal cleared()

    width: 200 + (allowClear ? 26 : 0)
    height: 34

    Rectangle {
        id: field
        width: 200
        height: parent.height
        radius: T.radiusSm
        color: box.capturing ? Qt.rgba(T.accent.r, T.accent.g, T.accent.b, 0.08)
                             : T.fillSubtle
        border.width: 1
        // Синий - только особенное: захват это фокус, ровно его случай.
        border.color: box.capturing ? T.accent
                    : ma.containsMouse ? T.borderStrong : T.border

        Text {
            anchors.centerIn: parent
            width: parent.width - 20
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            text: box.capturing ? "нажмите сочетание…"
                 : box.pretty !== "" ? box.pretty : "не назначено"
            // Моноширинный: сочетание клавиш - это голос терминала.
            font.family: T.mono
            font.pixelSize: T.tXs
            color: box.capturing ? T.accent
                 : box.pretty !== "" ? T.text : T.textFaint
        }

        MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: box.capturing ? box.cancelCapture() : box.startCapture()
        }
    }

    // Крестик: «выключено» - законное состояние для необязательного бинда.
    Item {
        visible: box.allowClear && box.pretty !== ""
        anchors { left: field.right; leftMargin: 6; verticalCenter: parent.verticalCenter }
        width: 20; height: 20
        Text {
            anchors.centerIn: parent
            text: "✕"
            font.pixelSize: T.t2xs
            color: cma.containsMouse ? T.danger : T.textFaint
        }
        MouseArea {
            id: cma
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: box.cleared()
        }
    }
}
