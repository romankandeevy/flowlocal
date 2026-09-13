// Выпадающий список. Радиус меню 8, строки - на отступ меньше (считается ниже).
// Штатный ComboBox из QtQuick.Controls не берём: он тащит свой стиль, и
// перекрашивать его вышло бы дороже, чем нарисовать список из двух Rectangle.
//
// С клавиатуры: Space или Enter открывает и выбирает, стрелки водят по списку,
// Esc закрывает не выбрав. Пока этого не было, до половины настроек «Диктовки»
// с клавиатуры было просто не достать.

import QtQuick

Item {
    id: sel
    property var options: []              // [{label, value}]
    property var value
    signal picked(var value)

    height: 30
    implicitWidth: 290
    width: implicitWidth

    activeFocusOnTab: enabled

    // Мышиный ли фокус - разобрано в шапке FocusRing.qml.
    property bool mouseFocus: false
    readonly property bool visualFocus: activeFocus && !mouseFocus
    onActiveFocusChanged: if (!activeFocus) { mouseFocus = false; menu.visible = false }

    opacity: enabled ? 1 : 0.4
    Behavior on opacity { NumberAnimation { duration: T.durFast * 1000 } }

    // Куда встанет подсветка, когда список откроют с клавиатуры. Отдельно от
    // value: пока человек водит стрелками, настройка ещё не изменена - меняется
    // она на Enter. Иначе каждое нажатие стрелки писало бы в конфиг.
    property int hover: -1

    Keys.onPressed: (e) => {
        if (e.key === Qt.Key_Escape && menu.visible) {
            menu.visible = false; e.accepted = true;
        } else if (e.key === Qt.Key_Space
                   || e.key === Qt.Key_Return || e.key === Qt.Key_Enter) {
            if (menu.visible && sel.hover >= 0 && sel.hover < options.length) {
                sel.value = options[sel.hover].value;
                sel.picked(options[sel.hover].value);
                menu.visible = false;
            } else {
                sel.hover = indexOf(sel.value);
                menu.visible = true;
            }
            e.accepted = true;
        } else if (e.key === Qt.Key_Down || e.key === Qt.Key_Up) {
            var d = e.key === Qt.Key_Down ? 1 : -1;
            if (!menu.visible) { sel.hover = indexOf(sel.value); menu.visible = true; }
            else if (options.length)
                sel.hover = (sel.hover + d + options.length) % options.length;
            e.accepted = true;
        }
    }

    function indexOf(v) {
        for (var i = 0; i < options.length; i++)
            if (options[i].value === v) return i;
        return 0;
    }

    function labelOf(v) {
        for (var i = 0; i < options.length; i++)
            if (options[i].value === v) return options[i].label;
        return options.length ? options[0].label : "";
    }

    Rectangle {
        id: head
        anchors.fill: parent
        radius: T.radiusSm
        color: ma.pressed ? T.fillStrong : ma.containsMouse ? T.fill : T.fillSubtle
        Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
        border.width: 1
        border.color: menu.visible ? T.accent
                    : ma.containsMouse ? T.borderStrong : T.border
        Behavior on border.color { ColorAnimation { duration: T.durFast * 1000 } }

        Text {
            anchors { left: parent.left; leftMargin: 12; right: chev.left; rightMargin: 8
                      verticalCenter: parent.verticalCenter }
            text: L.t(sel.labelOf(sel.value))
            elide: Text.ElideRight
            font.family: T.sans
            font.pixelSize: T.tSm
            color: T.text
        }
        Text {
            id: chev
            anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
            text: "⌄"
            font.pixelSize: T.tSm
            color: ma.containsMouse ? T.text : T.textMuted
            // Шеврон переворачивается на открытом меню: указывает, куда
            // приведёт следующее нажатие, а не куда привело прошлое.
            rotation: menu.visible ? 180 : 0
            Behavior on rotation { NumberAnimation { duration: T.durBase * 1000
                                                     easing.type: Easing.Bezier
                                                     easing.bezierCurve: T.easeOut } }
        }
        MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            enabled: sel.enabled
            cursorShape: sel.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            onPressed: { sel.mouseFocus = true; sel.forceActiveFocus() }
            onClicked: { sel.hover = sel.indexOf(sel.value); menu.visible = !menu.visible }
        }
    }

    FocusRing { target: head; on: sel.visualFocus }

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
                // Меню скруглено на 8, список вложен с отступом 4 - значит
                // строке остаётся 4. Одинаковый радиус у вложенных углов
                // выглядит неправильно даже там, где глаз не объясняет чем.
                radius: T.radiusMd - 4
                // Подсветка одна на мышь и на клавиатуру: два разных признака
                // «вот эта строка» на одном списке читались бы как две строки.
                color: ima.pressed ? T.fillStrong
                     : (ima.containsMouse || sel.hover === index) ? T.fill : "transparent"
                Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
                Text {
                    anchors { left: parent.left; leftMargin: 8; right: parent.right
                              rightMargin: 8; verticalCenter: parent.verticalCenter }
                    text: L.t(modelData.label)
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
                    onEntered: sel.hover = index
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
