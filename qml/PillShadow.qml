// Тень под капсулой оверлея. Отдельным файлом ровно по одной причине:
// `import QtQuick.Effects` тянет Qt6QuickEffects.dll, который грузится не
// всегда (HANDOFF, грабли PySide6: QML-плагины грузит штатный загрузчик
// Windows, а он не смотрит в папку PySide6). Пока импорт стоял в Overlay.qml,
// его падение уносило бы всю пилюлю - ради украшения. Здесь падает только
// тень, а Loader в Overlay.qml это переживает молча.
//
// `source` ставит Overlay.qml после загрузки (`onLoaded`), а не привязкой:
// обращаться из компонента к id снаружи нельзя без pragma ComponentBehavior.
//
// Значения - --shadow-lg из Korti, ужатая под капсулу в 34 пикселя: было два
// слоя (4/8 и 16/40), стал один. На такой высоте разницы не видно, а копий
// пилюли в графе отрисовки вдвое меньше.

import QtQuick
import QtQuick.Effects

MultiEffect {
    anchors.fill: parent
    shadowEnabled: true
    shadowColor: T.shadowFar
    shadowVerticalOffset: T.px(10)
    shadowBlur: 1.0
    shadowScale: 1.0
    blurMax: T.px(28)
}
