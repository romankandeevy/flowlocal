// Фон окна: точечная сетка плюс «прожектор» акцентом сверху.
//
// Не украшательство и не самодеятельность - это tokens/patterns.css из Korti
// (.ins-bg-dots и .ins-bg-spot), там же и объяснено зачем: «subtle, technical
// background textures so surfaces aren't flat/boring». Обе краски выведены из
// ink/accent на низкой прозрачности, поэтому инвертируются вместе с темой.
//
// Значения - из первоисточника, не на глаз (сверено через DesignSync):
//   точки   - radial ink/0.10, шаг 20 (.ins-bg-dots)
//   прожектор- radial(60% 55% at 50% -5%, --accent-bg, transparent 70%)
//   --accent-bg = accent/0.10 светлая, accent/0.16 тёмная
//   к краям всё гаснет маской .ins-bg-fade (radial 120% 90% at 50% 0%)
//
// Раньше и точки, и прожектор были приглушены «на глаз» (точки под общим
// opacity 0.55, прожектор линейным градиентом до 42%) - фактуры на экране не
// было вовсе. Теперь ровно как в системе: сдержанно, но видно.

// QtQuick.Effects тут не импортируем: он тянет Qt6QuickEffects.dll, который
// без ручного ctypes-подъёма не грузится (HANDOFF, грабли PySide6). Радиальные
// градиенты рисуем на Canvas - штатный QtQuick, без GPL-модулей.

import QtQuick

Item {
    id: bd
    property color base: T.bg

    Rectangle { anchors.fill: parent; color: bd.base }

    // Прожектор: мягкое пятно акцента у верхнего края. В CSS это
    // radial-gradient(60% 55% at 50% -5%, var(--accent-bg), transparent 70%).
    // Canvas умеет только круговой градиент - берём круг радиусом 60% ширины,
    // центр чуть выше верхней кромки (at 50% -5%), эллипс на глаз не отличить.
    Canvas {
        id: spot
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            var cx = width / 2;
            var cy = -0.05 * height;
            var r = Math.max(width, height) * 0.6;
            var a = T.dark ? 0.16 : 0.10;      // --accent-bg по теме
            var g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
            g.addColorStop(0.0, Qt.rgba(T.accent.r, T.accent.g, T.accent.b, a));
            g.addColorStop(0.7, Qt.rgba(T.accent.r, T.accent.g, T.accent.b, 0));
            ctx.fillStyle = g;
            ctx.fillRect(0, 0, width, height);
        }
        Connections {
            target: T
            function onChanged() { spot.requestPaint() }
        }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }

    // Точечная сетка. Рисуем один раз в Canvas: это статичный фон, и
    // перерисовывать его на каждый кадр незачем. Чернила 0.10 - полные, как в
    // системе; к нижнему краю гасим (приближение маски .ins-bg-fade), чтобы
    // сетка не спорила с содержимым внизу длинных страниц.
    Canvas {
        id: dots
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            for (var y = 10; y < height; y += 20) {
                // fade вниз: у верхней кромки полные 0.10, к низу - в ноль.
                var fade = Math.max(0, 1 - (y / height) * 1.15);
                ctx.fillStyle = Qt.rgba(T.ink.r, T.ink.g, T.ink.b, 0.10 * fade);
                for (var x = 10; x < width; x += 20) {
                    ctx.beginPath();
                    ctx.arc(x, y, 1, 0, 2 * Math.PI);
                    ctx.fill();
                }
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
