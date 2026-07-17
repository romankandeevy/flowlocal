// Карточка-метрика: подпись моноширинным, число - крупно.
//
// Канон Korti (templates/app-shell, блок метрик): подпись 11px mono
// --text-muted, значение 32px / 800 / -.03em. Такое сочетание - голос системы:
// «числа и результат вместо прилагательных» (guidelines/brand-voice).
//
// Число намеренно крупнее всего на экране. Это единственное место, где человек
// видит не то, что программа умеет, а то, что она для него сделала.

import QtQuick

Card {
    id: root

    property string label: ""
    property string value: ""
    property string hint: ""

    implicitHeight: col.implicitHeight + 32

    Item {
        width: parent.width
        implicitHeight: col.implicitHeight + 32

        Column {
            id: col
            anchors { left: parent.left; right: parent.right; top: parent.top
                      leftMargin: 16; rightMargin: 16; topMargin: 16 }
            spacing: 8

            Text {
                text: root.label
                font.family: T.mono
                font.pixelSize: T.t2xs
                color: T.textMuted
            }
            Text {
                text: root.value
                font.family: T.sans
                font.pixelSize: 32
                font.weight: Font.ExtraBold
                font.letterSpacing: -0.96      // -.03em от 32px
                color: T.text
            }
            Text {
                text: root.hint
                visible: root.hint !== ""
                width: col.width
                wrapMode: Text.WordWrap
                font.family: T.sans
                font.pixelSize: T.t2xs
                color: T.textMuted
            }
        }
    }
}
