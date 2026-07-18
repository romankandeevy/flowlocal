// Korti Slider: дорожка 5px, заливка акцентом, ручка бумажная с линией.
// Значение подписано справа: без него ползунок бесполезен - «где-то
// посередине» это не настройка, человеку нужно видеть, что он выставил.

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

    function snap(v) {
        var s = Math.round((v - from) / stepSize) * stepSize + from;
        return Math.min(to, Math.max(from, Math.round(s * 100) / 100));
    }
    readonly property real pos: (to > from) ? (value - from) / (to - from) : 0

    Item {
        id: track
        width: sld.trackW
        height: parent.height
        anchors.verticalCenter: parent.verticalCenter

        Rectangle {                       // дорожка
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width; height: 5; radius: 2.5
            color: T.fillStrong
        }
        Rectangle {                       // пройденная часть - акцент
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width * sld.pos; height: 5; radius: 2.5
            color: T.accent
        }
        Rectangle {                       // ручка
            id: knob
            width: 14; height: 14; radius: 7
            anchors.verticalCenter: parent.verticalCenter
            x: sld.pos * (track.width - width)
            color: T.paper
            border.width: 1
            border.color: ma.containsMouse || ma.pressed ? T.borderStrong : T.border
        }
        MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            function apply(mx) {
                var p = Math.min(1, Math.max(0, (mx - knob.width / 2) / (track.width - knob.width)));
                var v = sld.snap(sld.from + p * (sld.to - sld.from));
                if (v !== sld.value) { sld.value = v; sld.moved(v) }
            }
            onPressed: apply(mouseX)
            onPositionChanged: if (pressed) apply(mouseX)
        }
    }

    Text {
        anchors { left: track.right; leftMargin: 10; verticalCenter: parent.verticalCenter }
        // Моноширинный: это число-метаданные, и табличные цифры не дают
        // подписи дёргаться при перетаскивании.
        text: sld.value.toFixed(1).replace(".", ",") + sld.suffix
        font.family: T.mono
        font.pixelSize: T.tXs
        color: T.textSecondary
    }
}
