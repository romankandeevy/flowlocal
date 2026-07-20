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
    // Начинать ли захват с клавиатуры (Space). По умолчанию да - так поле
    // доступно и без мыши в настройках. На экранах жеста мастера выключается
    // (keyStart: false): там человек НАЖИМАЕТ сочетание ради живой проверки, а
    // пробел входит в стандартное ctrl+shift+space - и «Space начинает захват»
    // превращал каждую проверку в переназначение. Захват дрался с проверкой и
    // шёл по кругу, «Дальше» не открывалась. Клик по полю - действие
    // осознанное, им захват и оставляем.
    property bool keyStart: true
    signal startCapture()
    signal cancelCapture()
    signal cleared()

    width: 200 + (allowClear ? 26 : 0)
    height: 34

    activeFocusOnTab: enabled

    // Мышиный ли фокус - разобрано в шапке FocusRing.qml.
    property bool mouseFocus: false
    readonly property bool visualFocus: activeFocus && !mouseFocus
    onActiveFocusChanged: if (!activeFocus) mouseFocus = false

    opacity: enabled ? 1 : 0.4
    Behavior on opacity { NumberAnimation { duration: T.durFast * 1000 } }

    // Space начинает захват (когда keyStart), Esc отменяет идущий. Space, а не
    // Enter: Enter сам бывает частью сочетания, и «начать захват» на нём значило
    // бы, что назначить Enter нельзя вовсе. keyStart=false выключает старт с
    // клавиатуры целиком - зачем, см. свойство keyStart выше.
    Keys.onPressed: (e) => {
        if (box.keyStart && e.key === Qt.Key_Space && !box.capturing) { box.startCapture(); e.accepted = true; }
        else if (e.key === Qt.Key_Escape && box.capturing) { box.cancelCapture(); e.accepted = true; }
    }

    Rectangle {
        id: field
        width: 200
        height: parent.height
        radius: T.radiusSm
        color: box.capturing ? Qt.rgba(T.accent.r, T.accent.g, T.accent.b, 0.08)
             : ma.pressed ? T.fill
             : ma.containsMouse ? T.fill : T.fillSubtle
        Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
        border.width: 1
        // Синий - только особенное: захват это фокус, ровно его случай.
        border.color: box.capturing ? T.accent
                    : ma.containsMouse ? T.borderStrong : T.border
        Behavior on border.color { ColorAnimation { duration: T.durFast * 1000 } }

        Text {
            anchors.centerIn: parent
            width: parent.width - 20
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            text: box.capturing ? L.t("нажмите сочетание…")
                 : box.pretty !== "" ? box.pretty : "не назначено"
            // Моноширинный: сочетание клавиш - это голос терминала.
            font.family: T.mono
            font.pixelSize: T.t2xs
            color: box.capturing ? T.accent
                 : box.pretty !== "" ? T.text : T.textFaint
        }

        MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            enabled: box.enabled
            cursorShape: box.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            onPressed: { box.mouseFocus = true; box.forceActiveFocus() }
            onClicked: box.capturing ? box.cancelCapture() : box.startCapture()
        }

        FocusRing { on: box.visualFocus }
    }

    // Крестик: «выключено» - законное состояние для необязательного бинда.
    Item {
        visible: box.allowClear && box.pretty !== ""
        anchors { left: field.right; leftMargin: 8; verticalCenter: parent.verticalCenter }
        width: 20; height: 20
        // Подложка под крестиком: без неё цель клика в 20 пикселей ничем не
        // обозначена, и наведение читается как случайное покраснение значка.
        Rectangle {
            anchors.fill: parent
            radius: T.radiusSm
            color: cma.pressed ? Qt.rgba(T.danger.r, T.danger.g, T.danger.b, 0.18)
                 : cma.containsMouse ? Qt.rgba(T.danger.r, T.danger.g, T.danger.b, 0.10)
                 : "transparent"
            Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
        }
        Text {
            anchors.centerIn: parent
            text: "✕"
            font.pixelSize: T.t2xs
            color: cma.containsMouse ? T.danger : T.textFaint
            Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
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
