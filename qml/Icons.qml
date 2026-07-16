// Данные иконок Lucide (lucide.dev, ISC) - только те, что нужны меню.
//
// Хранятся строками, а не файлами: одна строка на иконку дешевле, чем
// девять .svg рядом со сборкой, и не требует ни плагина SVG, ни правки
// flowlocal.spec. Рисует их Icon.qml.
//
// pragma Singleton не ставим намеренно: singleton требует qmldir, а вся папка
// и так резолвится по имени файла. Инстанс создаётся один раз в Settings.qml.

import QtQuick

QtObject {
    // sliders-horizontal
    readonly property string general:
        "M21 4h-7M10 4H3M21 12h-9M8 12H3M21 20h-5M12 20H3M14 2v4M8 10v4M16 18v4"
    // audio-lines
    readonly property string asr:
        "M2 10v3M6 6v11M10 3v18M14 8v7M18 5v13M22 10v3"
    // box
    readonly property string models:
        "M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"
        + "M3.3 7 12 12l8.7-5M12 22V12"
    // keyboard
    readonly property string input:
        "M10 8h.01M12 12h.01M14 8h.01M16 12h.01M18 8h.01M6 8h.01M7 16h10"
        + "M8 12h.01M2 6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2Z"
    // book-a
    readonly property string dictionary:
        "M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20"
        + "M10 13.5 12.5 8l2.5 5.5M11 12h3"
    // replace
    readonly property string snippets:
        "M14 4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2Z"
        + "M2 16a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2Z"
        + "M3 7a2 2 0 0 1 2-2M7 3a2 2 0 0 1 2 2M5 11a2 2 0 0 1-2-2M9 9a2 2 0 0 1-2 2"
    // history
    readonly property string history:
        "M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8M3 3v5h5M12 7v5l4 2"
    // bar-chart-3
    readonly property string stats:
        "M3 3v18h18M18 17V9M13 17V5M8 17v-3"
    // info
    readonly property string about:
        "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20ZM12 16v-4M12 8h.01"
    // mic - для вордмарка
    readonly property string mic:
        "M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"
        + "M19 10v2a7 7 0 0 1-14 0v-2M12 19v3"

    // Сопоставление «имя страницы -> иконка». Держим здесь, а не в Settings.qml:
    // список страниц и так один, а перебирать имена в вёрстке - шум.
    function forPage(name) {
        switch (name) {
        case "Основное":      return general;
        case "Распознавание": return asr;
        case "Модели":        return models;
        case "Ввод":          return input;
        case "Словарь":       return dictionary;
        case "Замены":        return snippets;
        case "История":       return history;
        case "Статистика":    return stats;
        case "О программе":   return about;
        }
        return "";
    }
}
