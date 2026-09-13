// Иконка Lucide: рисуем path-данные на Canvas.
//
// У Qt Canvas есть своё расширение - ctx.path принимает строку SVG-пути как
// есть. Поэтому иконку не надо ни собирать из примитивов, ни тащить модуль
// QtQuick.Shapes или плагин SVG: одна строка данных из Lucide - и готово.
//
// Lucide рисуется штрихом по сетке 24 с круглыми торцами и обводкой 2 - это
// заложено в самих данных, поэтому здесь только масштаб и цвет.

import QtQuick

Canvas {
    id: ico
    property string path: ""
    property color color: T.text
    property real weight: 1.9        // как в app-shell Korti: stroke-width 1.9
    property int size: 17

    width: size
    height: size
    // Canvas рисует один раз и на смену привязок не смотрит: без явных
    // requestPaint иконка осталась бы того цвета и той формы, что были в
    // момент создания (на этом уже обжигались с галкой «готово»).
    onPathChanged: requestPaint()
    onColorChanged: requestPaint()
    onWidthChanged: requestPaint()

    onPaint: {
        var ctx = getContext("2d");
        ctx.reset();
        if (!path) return;
        var k = width / 24;
        ctx.scale(k, k);
        ctx.strokeStyle = color;
        ctx.lineWidth = weight;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.path = path;          // расширение Qt: SVG-данные как есть
        ctx.stroke();
    }
}
