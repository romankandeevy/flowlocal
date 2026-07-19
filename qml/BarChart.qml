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
                    id: bar
                    anchors.bottom: parent.bottom
                    width: parent.width
                    radius: 2
                    // Пустой день - ниточка, а не пустота: иначе не видно, что
                    // день вообще был.
                    readonly property real full:
                        Math.max(2, chart.height * (chart.values[index] / chart.maxValue))
                    color: T.ink
                    opacity: chart.values[index] > 0 ? 0.72 : 0.16

                    // Высота - ПРИВЯЗКА, умноженная на коэффициент появления.
                    // Анимировать саму height нельзя: императивная запись рвёт
                    // привязку намертво, и график навсегда остаётся с высотами
                    // первого захода. У Repeater model - это длина массива, то
                    // есть всегда 30: делегаты не пересоздаются, и второй раз
                    // Component.onCompleted уже не играет. Симптом был
                    // издевательский: прозрачность живая, высота мёртвая - день
                    // без единого слова стоял высоким столбцом, а день с пиком
                    // лежал ниточкой. Проверено пробой, см. ревью 18.07.2026.
                    property real k: 0
                    height: bar.full * bar.k

                    // Столбцы вырастают снизу волной слева направо: 11 мс на
                    // шаг - к тридцатому дню ~330 мс. Движение читается как
                    // «вот ваши дни», а не мельтешение. Korti разрешает: рост
                    // высоты - не пружина.
                    Component.onCompleted: grow.start()
                    SequentialAnimation {
                        id: grow
                        PauseAnimation { duration: index * 11 }
                        NumberAnimation {
                            target: bar; property: "k"; from: 0; to: 1
                            duration: 300; easing.type: Easing.OutCubic
                        }
                    }
                    Component.onDestruction: grow.stop()
                }
            }
        }
    }

    Text {
        anchors.centerIn: parent
        visible: chart.values.length === 0
        text: L.t("пока пусто")
        font.family: T.sans
        font.pixelSize: T.tSm
        color: T.textFaint
    }
}
