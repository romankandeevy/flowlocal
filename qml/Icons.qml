// Данные иконок Lucide (lucide.dev, ISC) - только те, что нужны меню и
// вордмарку: шесть страниц плюс микрофон. Раньше их было десять - лишние ушли
// вместе со слиянием страниц, мёртвых path-данных не держим.
//
// Хранятся строками, а не файлами: одна строка на иконку дешевле, чем
// .svg рядом со сборкой, и не требует ни плагина SVG, ни правки
// flowlocal.spec. Рисует их Icon.qml.
//
// pragma Singleton не ставим намеренно: singleton требует qmldir, а вся папка
// и так резолвится по имени файла. Инстанс создаётся один раз в Settings.qml.

import QtQuick

QtObject {
    // layout-dashboard - ею же помечен Overview в каркасе системы
    // (templates/app-shell), а наша «Главная» - это он и есть.
    readonly property string home:
        "M3 5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"
        + "M13 5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2Z"
        + "M13 13a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2Z"
        + "M3 17a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"
    // audio-lines - «Диктовка»
    readonly property string asr:
        "M2 10v3M6 6v11M10 3v18M14 8v7M18 5v13M22 10v3"
    // book-a - «Слова»
    readonly property string dictionary:
        "M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20"
        + "M10 13.5 12.5 8l2.5 5.5M11 12h3"
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
    //
    // Дверей стало шесть вместо десяти: Основное+Распознавание+Ввод слились в
    // «Диктовку», Словарь+Замены - в «Слова», а «Модели» ушли с панели вглубь
    // (человеку, который пишет письма, зоопарк моделей видеть незачем).
    function forPage(name) {
        switch (name) {
        case "Главная":       return home;
        case "Диктовка":      return asr;
        case "Слова":         return dictionary;
        case "История":       return history;
        case "Статистика":    return stats;
        case "О программе":   return about;
        }
        return "";
    }
}
