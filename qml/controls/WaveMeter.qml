// Живая волна мастера первого запуска: столбики по громкости микрофона.
//
// Отдельным файлом, потому что мест два - экран микрофона и экран пробы, - а
// нарисованные по отдельности они разъедутся на первой же правке размеров.
//
// Уровни берёт у `OB.levels()`, то есть у настоящего recorder приложения, а не
// у муляжа: мастер, который показывает нарисованную волну, проверяет сам себя,
// и «микрофон не тот» человек узнал бы уже после мастера.
//
// Живёт только внутри мастера - оверлей рисует свою волну сам (Overlay.qml),
// у него другой источник данных и другой размер.

import QtQuick

Item {
    id: wave

    // Пока false - таймер стоит и уровни не копятся. Иначе два экрана мастера
    // тянули бы из recorder по очереди и обкрадывали друг друга: drain_levels
    // отдаёт замеры один раз.
    property bool running: false

    property int bars: 40
    property real barW: 5
    property real gap: 3
    property real maxH: 96
    property color barColor: T.ink

    // Громкость наружу: 0 - тишина, 1 - говорят в полный голос. Держится и
    // спадает, как пик-метр на пульте, а не повторяет каждый замер. Строка
    // «слышу вас», честно повторяющая кадры, моргала бы тридцать раз в
    // секунду - речь идёт волнами, между словами всегда тихо.
    property real peak: 0

    property var _levels: []

    implicitWidth: bars * barW + (bars - 1) * gap
    implicitHeight: maxH

    onRunningChanged: if (!running) { _levels = []; peak = 0 }

    Row {
        anchors.centerIn: parent
        spacing: wave.gap

        Repeater {
            model: wave.bars

            Rectangle {
                width: wave.barW
                radius: wave.barW / 2
                anchors.verticalCenter: parent.verticalCenter
                color: wave.barColor
                opacity: 0.85
                // Свежий замер - справа: волна едет влево, как осциллограф.
                // Пока замеров меньше, чем столбиков, слева честно лежит
                // ровная линия, а не пустое место.
                height: {
                    var b = wave._levels;
                    var v = b[b.length - 1 - (wave.bars - 1 - index)];
                    return Math.max(3, (v === undefined ? 0 : v) * wave.maxH);
                }
                // Столбик идёт за голосом, а не проигрывает переход: половина
                // быстрого токена (60 мс). На целых 120 полоска отстаёт от
                // слова настолько, что проверка микрофона перестаёт отвечать
                // на свой единственный вопрос - «меня слышно прямо сейчас?».
                Behavior on height { NumberAnimation { duration: T.durFast * 1000 / 2 } }
            }
        }
    }

    Timer {
        interval: 33
        running: wave.running && wave.visible
        repeat: true
        onTriggered: {
            var fresh = OB.levels();
            if (fresh.length === 0)
                return;
            var b = wave._levels.slice();
            var last = 0;
            for (var i = 0; i < fresh.length; i++) {
                // Корень от отношения к порогу: линейная громкость почти всё
                // время лежит у нуля, и волна на ней выглядела бы мёртвой.
                last = Math.min(1, Math.pow(fresh[i] / 0.12, 0.65));
                b.push(last);
            }
            wave._levels = b.slice(-wave.bars);
            wave.peak = Math.max(wave.peak * 0.92, last);
        }
    }
}
