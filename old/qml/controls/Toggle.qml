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

    // Таб доводит, Space переключает. Переключатель - самый частый контрол
    // окна, и пройти настройки с клавиатуры без него нельзя вовсе.
    activeFocusOnTab: enabled

    // Мышиный ли фокус - разобрано в шапке FocusRing.qml.
    property bool mouseFocus: false
    readonly property bool visualFocus: activeFocus && !mouseFocus
    onActiveFocusChanged: if (!activeFocus) mouseFocus = false

    opacity: enabled ? 1 : 0.4
    Behavior on opacity { NumberAnimation { duration: T.durFast * 1000 } }

    function flip() { sw.value = !sw.value; sw.toggled(sw.value) }

    Keys.onPressed: (e) => {
        if (e.key === Qt.Key_Space || e.key === Qt.Key_Return || e.key === Qt.Key_Enter) {
            flip();
            e.accepted = true;
        }
    }

    // Ход ручки - 120 мс, самый быстрый токен, а не общие 180. Тумблер не
    // показывает переход, он отвечает на палец: на 180 щелчок успевал
    // прочитаться как задержка. Кривая та же, .2,.8,.2,1, без пружин.
    //
    // pos - доля перехода для ЦВЕТА дорожки; положение ручки считается отдельно
    // (см. ниже). Сроком и кривой они совпадают, иначе ручка приезжает раньше,
    // чем дорожка договорит, и одно нажатие читается двумя движениями.
    property real pos: value ? 1 : 0
    Behavior on pos { NumberAnimation { duration: T.durFast * 1000
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

    FocusRing { target: track; on: sw.visualFocus }

    Rectangle {
        width: 16; height: 16; radius: 8
        color: T.bg
        y: 3
        // Ход 16: от 3 слева до 19 справа (38 - 16 - 3). Едет своим
        // `Behavior on x`, а не через pos: положение ручки - это геометрия, а
        // pos - доля перехода цвета. Пока x считался из pos, любая правка
        // кривой у дорожки молча двигала и ручку.
        x: sw.value ? 19 : 3
        Behavior on x { NumberAnimation { duration: T.durFast * 1000
                                          easing.type: Easing.Bezier
                                          easing.bezierCurve: T.easeOut } }
        // Нажатие: ручка чуть тонет. Масштаб, а не сдвиг, - сдвиг тут
        // неотличим от хода, ради которого переключатель и существует.
        scale: ma.pressed ? 0.88 : 1
        Behavior on scale { NumberAnimation { duration: T.durFast * 1000
                                              easing.type: Easing.Bezier
                                              easing.bezierCurve: T.easeOut } }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        enabled: sw.enabled
        cursorShape: sw.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onPressed: { sw.mouseFocus = true; sw.forceActiveFocus() }
        onClicked: sw.flip()
    }
}
