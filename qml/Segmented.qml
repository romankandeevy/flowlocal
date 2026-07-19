// Korti SegmentedControl: контейнер --fill, выбранный сегмент - бумага.
// Радиус контейнера 8, сегмента 6 - так задано в системе, не «на глаз».

import QtQuick

Item {
    id: seg
    // [{label: "тёмная", value: "dark"}, ...] - value любого типа, в том числе null
    property var options: []
    property var value
    signal picked(var value)

    height: 30
    implicitWidth: box.implicitWidth
    width: implicitWidth

    function indexOf(v) {
        for (var i = 0; i < options.length; i++)
            if (options[i].value === v) return i;
        return 0;
    }

    Rectangle {
        id: box
        anchors.fill: parent
        radius: T.radiusMd
        color: T.fill
        implicitWidth: rowItems.implicitWidth + 6

        // Бегунок выбранного сегмента - бумага. Едет той же кривой, что и всё
        // остальное: система разрешает фейды и сдвиги, пружин нет.
        Rectangle {
            id: thumb
            visible: rowItems.children.length > 0
            y: 3
            height: parent.height - 6
            radius: T.radiusSm
            color: T.paper
            border.width: 1
            border.color: T.border
            x: {
                var acc = 3;
                for (var i = 0; i < seg.indexOf(seg.value) && i < rowItems.children.length; i++)
                    acc += rowItems.children[i].width;
                return acc;
            }
            width: {
                var i = seg.indexOf(seg.value);
                return i < rowItems.children.length ? rowItems.children[i].width : 0;
            }
            Behavior on x { NumberAnimation { duration: T.durBase * 1000
                                              easing.type: Easing.Bezier
                                              easing.bezierCurve: T.easeOut } }
            Behavior on width { NumberAnimation { duration: T.durBase * 1000
                                                  easing.type: Easing.Bezier
                                                  easing.bezierCurve: T.easeOut } }
        }

        Row {
            id: rowItems
            x: 3
            y: 3
            height: parent.height - 6
            Repeater {
                model: seg.options
                Item {
                    height: rowItems.height
                    width: Math.max(36, lbl.implicitWidth + 24)
                    Text {
                        id: lbl
                        anchors.centerIn: parent
                        // Подписи приходят из двух мест: собранные тут же (уже
                        // через L.t) и готовые списки из Python (B.themeOptions
                        // и прочие) - вот эти до сих пор оставались русскими
                        // при английском интерфейсе. L.t идемпотентен: то, что
                        // уже переведено, ключом не является и проходит как
                        // есть, - поэтому одно место, а не два.
                        text: L.t(modelData.label)
                        font.family: T.sans
                        font.pixelSize: T.tSm
                        font.weight: Font.Medium
                        color: seg.indexOf(seg.value) === index ? T.text
                             : ma.containsMouse ? T.textSecondary : T.textMuted
                    }
                    MouseArea {
                        id: ma
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { seg.value = modelData.value; seg.picked(modelData.value) }
                    }
                }
            }
        }
    }
}
