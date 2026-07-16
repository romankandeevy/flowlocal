// Столбики «по дням». Данные - чернила, а не акцент: это данные, а не статус.
//
// Qt Graphs для этого не берём принципиально: он GPL-only и утянул бы весь
// проект в GPL (PLAN 3). Repeater из Rectangle - это Qt Quick, LGPLv3.

import QtQuick

Item {
    id: chart
    property var values: []
    property int barGap: 3

    implicitWidth: 560
    implicitHeight: 120
    width: implicitWidth
    height: implicitHeight

    readonly property real maxValue: {
        var m = 0;
        for (var i = 0; i < values.length; i++) m = Math.max(m, values[i]);
        return m || 1;
    }

    Row {
        anchors.fill: parent
        spacing: chart.barGap
        Repeater {
            model: chart.values.length
            Item {
                width: (chart.width - chart.barGap * (chart.values.length - 1))
                       / Math.max(1, chart.values.length)
                height: chart.height
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    radius: 2
                    // Пустой день - ниточка, а не пустота: иначе не видно, что
                    // день вообще был.
                    height: Math.max(2, chart.height * (chart.values[index] / chart.maxValue))
                    color: T.ink
                    opacity: chart.values[index] > 0 ? 0.72 : 0.16
                }
            }
        }
    }

    Text {
        anchors.centerIn: parent
        visible: chart.values.length === 0
        text: "пока пусто"
        font.family: T.sans
        font.pixelSize: T.tSm
        color: T.textFaint
    }
}
