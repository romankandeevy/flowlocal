// Korti Slider: дорожка 5px, заливка акцентом, ручка бумажная с линией.
// Значение подписано справа: без него ползунок бесполезен - «где-то
// посередине» это не настройка, человеку нужно видеть, что он выставил.
//
// С клавиатуры - стрелки на один шаг, Home и End на края. Ползунок обычно и
// правят по одному шагу («сдвинуть чуть-чуть»), а мышью попасть в 14 пикселей
// ручки и отпустить ровно там, где надо, куда труднее, чем нажать стрелку.

import QtQuick

Item {
    id: sld
    property real from: 0
    property real to: 1
    property real stepSize: 0.1
    property real value: 0
    property string suffix: " с"
    property int trackW: 130
    signal moved(real value)

    height: 22
    implicitWidth: trackW + 54
    width: implicitWidth

    activeFocusOnTab: enabled

    // Мышиный ли фокус - разобрано в шапке FocusRing.qml.
    property bool mouseFocus: false
    readonly property bool visualFocus: activeFocus && !mouseFocus
    onActiveFocusChanged: if (!activeFocus) mouseFocus = false

    opacity: enabled ? 1 : 0.4
    Behavior on opacity { NumberAnimation { duration: T.durFast * 1000 } }

    function snap(v) {
        var s = Math.round((v - from) / stepSize) * stepSize + from;
        return Math.min(to, Math.max(from, Math.round(s * 100) / 100));
    }
    function set(v) {
        var n = snap(v);
        if (n !== value) { value = n; moved(n) }
    }
    readonly property real pos: (to > from) ? (value - from) / (to - from) : 0

    Keys.onPressed: (e) => {
        if (e.key === Qt.Key_Left || e.key === Qt.Key_Down) { set(value - stepSize); e.accepted = true; }
        else if (e.key === Qt.Key_Right || e.key === Qt.Key_Up) { set(value + stepSize); e.accepted = true; }
        else if (e.key === Qt.Key_Home) { set(from); e.accepted = true; }
        else if (e.key === Qt.Key_End) { set(to); e.accepted = true; }
    }

    Item {
        id: track
        width: sld.trackW
        height: parent.height
        anchors.verticalCenter: parent.verticalCenter

        Rectangle {                       // дорожка
            id: rail
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width; height: 5; radius: height / 2
            color: T.fillStrong
        }
        Rectangle {                       // пройденная часть - акцент
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width * sld.pos; height: 5; radius: height / 2
            color: T.accent
        }
        Rectangle {                       // ручка
            id: knob
            width: 14; height: 14; radius: width / 2
            anchors.verticalCenter: parent.verticalCenter
            x: sld.pos * (track.width - width)
            color: T.paper
            border.width: 1
            border.color: ma.containsMouse || ma.pressed ? T.borderStrong : T.border
            Behavior on border.color { ColorAnimation { duration: T.durFast * 1000 } }
            // Под пальцем ручка чуть подрастает - тот же жест, что у кнопки
            // «утонуть», но наоборот: кнопку нажимают, а ручку берут.
            scale: ma.pressed ? 1.15 : ma.containsMouse ? 1.08 : 1
            Behavior on scale { NumberAnimation { duration: T.durFast * 1000
                                                  easing.type: Easing.Bezier
                                                  easing.bezierCurve: T.easeOut } }
        }

        // Кольцо по дорожке, а не по ручке: ручка ездит, и кольцо ездило бы с
        // ней - фокус читался бы как ещё одно значение, а не как «этот контрол
        // сейчас слушает клавиатуру».
        FocusRing { target: rail; on: sld.visualFocus }

        MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            enabled: sld.enabled
            cursorShape: sld.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            function apply(mx) {
                var p = Math.min(1, Math.max(0, (mx - knob.width / 2) / (track.width - knob.width)));
                sld.set(sld.from + p * (sld.to - sld.from));
            }
            onPressed: { sld.mouseFocus = true; sld.forceActiveFocus(); apply(mouseX) }
            onPositionChanged: if (pressed) apply(mouseX)
        }
    }

    Text {
        anchors { left: track.right; leftMargin: 12; verticalCenter: parent.verticalCenter }
        // Моноширинный: это число-метаданные, и табличные цифры не дают
        // подписи дёргаться при перетаскивании.
        text: sld.value.toFixed(1).replace(".", ",") + sld.suffix
        font.family: T.mono
        font.pixelSize: T.t2xs
        // Пока ползунок ведут, подпись - главное, на что смотрят: она одна
        // говорит, что именно выставлено. На это время поднимаем её в полный
        // текст, в покое возвращаем в тихий.
        color: (ma.pressed || sld.activeFocus) ? T.text : T.textSecondary
        Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
    }
}
