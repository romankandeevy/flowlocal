// Фон окна: точечная сетка плюс «прожектор» акцентом сверху.
//
// Не украшательство и не самодеятельность - это tokens/patterns.css из Korti
// (.ins-bg-dots и .ins-bg-spot), там же и объяснено зачем: «subtle, technical
// background textures so surfaces aren't flat/boring». Обе краски выведены из
// ink/accent на низкой прозрачности, поэтому инвертируются вместе с темой.
//
// Точки - шаг 20, чернила 10%, как в системе. Сетка гасится к низу маской:
// в оригинале это .ins-bg-fade.

// QtQuick.Effects тут не импортируем: он тянет Qt6QuickEffects.dll, который
// без ручного ctypes-подъёма не грузится (HANDOFF, грабли PySide6). Градиент и
// точки рисуются штатным QtQuick.

import QtQuick

Item {
    id: bd
    property color base: T.bg

    Rectangle { anchors.fill: parent; color: bd.base }

    // Прожектор: мягкое пятно акцента, привязанное к верхнему краю.
    // В CSS это radial-gradient(60% 55% at 50% -5%, var(--accent-bg), transparent).
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0
                           color: Qt.rgba(T.accent.r, T.accent.g, T.accent.b,
                                          T.dark ? 0.055 : 0.035) }
            GradientStop { position: 0.42; color: "transparent" }
        }
    }

    // Точечная сетка. Рисуем один раз в Canvas: это статичный фон, и
    // перерисовывать его на каждый кадр незачем.
    Canvas {
        id: dots
        anchors.fill: parent
        opacity: 0.55           // маска-«fade»: сетка не спорит с содержимым
        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            ctx.fillStyle = Qt.rgba(T.ink.r, T.ink.g, T.ink.b, 0.10);
            for (var y = 10; y < height; y += 20)
                for (var x = 10; x < width; x += 20) {
                    ctx.beginPath();
                    ctx.arc(x, y, 1, 0, 2 * Math.PI);
                    ctx.fill();
                }
        }
        // Canvas не следит за привязками - перерисовываем руками при смене
        // темы и размера, иначе точки останутся в старых чернилах.
        Connections {
            target: T
            function onChanged() { dots.requestPaint() }
        }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }
}
