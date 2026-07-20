// Данные иконок Lucide (lucide.dev, ISC): панель, вордмарк и - с задачи 4
// плана - каждый ряд настроек.
//
// Раньше их было семь, и в шапке стояло «только те, что нужны меню». Теперь
// иконка есть у ряда: по ней страницу просматривают глазами, не читая
// заголовки подряд. Правило прежнее - мёртвых path-данных не держим: каждая
// строка ниже стоит в чьём-то ряду, и убрать ряд значит убрать иконку.
//
// Хранятся строками, а не файлами: одна строка на иконку дешевле, чем
// .svg рядом со сборкой, и не требует ни плагина SVG, ни правки
// flowlocal.spec. Рисует их Icon.qml.
//
// pragma Singleton не ставим намеренно: singleton требует qmldir, а вся папка
// и так резолвится по имени файла. Инстанс создают те, кому иконки нужны:
// Settings.qml, Onboarding.qml и сам SettingRow.qml (ему - ради шеврона
// «подробнее»).

import QtQuick

QtObject {
    // ---------- панель и окна ----------

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
    // wrench - «Дополнительно». Гаечный ключ, а не шестерёнка: страница не про
    // тонкую настройку, а про то, что чинят, когда что-то пошло не так.
    // Шестерёнка вдобавок уже занята входом в настройки.
    readonly property string extra:
        "M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77"
        + "a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91"
        + "a6 6 0 0 1 7.94-7.94l-3.76 3.76Z"
    // info
    readonly property string about:
        "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20ZM12 16v-4M12 8h.01"
    // notebook-pen - «Заметки». Отдельное окно, но дверь в шапке главного:
    // без неё человек его просто не находит - именно так и вышло на живой
    // проверке, пока скретчпад жил только в трее.
    readonly property string notes:
        "M13.4 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7.4"
        + "M2 6h4M2 10h4M2 14h4M2 18h4"
        + "M21.4 2.6a2 2 0 0 1 0 2.8l-6.8 6.8-3 .6.6-3 6.8-6.8a2 2 0 0 1 2.4 0Z"
    // trash-2 - удалить заметку карточкой на странице «Заметки»
    readonly property string trash:
        "M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
        + "M10 11v6M14 11v6"
    // settings - вход в настройки, внизу панели
    readonly property string settings:
        "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"
        + "M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06"
        + "a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09"
        + "A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83"
        + "l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09"
        + "A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83"
        + "l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09"
        + "a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83"
        + "l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09"
        + "a1.65 1.65 0 0 0-1.51 1Z"
    // arrow-left - выход из настроек
    readonly property string back:
        "M19 12H5M12 19l-7-7 7-7"
    // mic - вордмарк и ряд про микрофон
    readonly property string mic:
        "M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"
        + "M19 10v2a7 7 0 0 1-14 0v-2M12 19v3"

    // ---------- ряды настроек ----------
    // Порядок - как на страницах: сочетания, микрофон, чистка, вставка, вид,
    // «дополнительно», «о программе». Так проще проверить, что каждой строке
    // досталась своя иконка, а не соседняя по алфавиту.

    // chevron-down - раскрытие «подробнее». Рисуется мельче прочих и
    // переворачивается на 180°, когда ряд раскрыт.
    readonly property string chevron:
        "m6 9 6 6 6-6"
    // keyboard - «Удерживать и говорить»: жест про клавишу, которую держат.
    readonly property string keyboard:
        "M2 6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2Z"
        + "M6 8h.01M10 8h.01M14 8h.01M18 8h.01M8 12h.01M12 12h.01M16 12h.01M7 16h10"
    // circle-dot - «Нажать и говорить»: включил и говоришь, как кнопка записи.
    readonly property string record:
        "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20ZM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"
    // pen - «Править выделенное голосом»
    readonly property string edit:
        "M21.2 4.8a2.1 2.1 0 0 0-3-3L3 17v4h4Z"
    // list - «Преобразовать текст»: список готовых правок
    readonly property string list:
        "M3 6h.01M3 12h.01M3 18h.01M8 6h13M8 12h13M8 18h13"
    // rotate-ccw - «Отменить последнюю диктовку»
    readonly property string undo:
        "M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8M3 3v5h5"
    // zap - «Разбирать речь на ходу»: ждать после клавиши не приходится
    readonly property string zap:
        "M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02"
        + "A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46"
        + "l1.92-6.02A1 1 0 0 0 11 14Z"
    // corner-down-left - «Голосовые команды»: «с новой строки», «нажми энтер»
    readonly property string enter:
        "M20 4v7a4 4 0 0 1-4 4H4M9 10l-5 5 5 5"
    // sparkles - «Правка текста на ходу» и готовые преобразования
    readonly property string sparkles:
        "m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21"
        + "l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"
        + "M5 3v4M19 17v4M3 5h4M17 19h4"
    // download - установка и выгрузка личного в файл
    readonly property string download:
        "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"
    // upload - загрузка личного из файла
    readonly property string upload:
        "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"
    // link - адрес Ollama
    readonly property string link:
        "M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"
        + "M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"
    // box - модель Ollama
    readonly property string box:
        "M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8"
        + "a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"
        + "M3.3 7 12 12l8.7-5M12 22V12"
    // link-2 - «Продолжать мысль»: вторая фраза приклеивается к первой
    readonly property string join:
        "M9 17H7A5 5 0 0 1 7 7h2M15 7h2a5 5 0 1 1 0 10h-2M8 12h8"
    // sliders-horizontal - «Насколько править»
    readonly property string sliders:
        "M21 4h-7M10 4H3M21 12h-9M8 12H3M21 20h-5M12 20H3M14 2v4M8 10v4M16 18v4"
    // languages - язык интерфейса и преобразование «На английский»
    readonly property string languages:
        "m5 8 6 6M4 14l6-6 2-3M2 5h12M7 2h1M22 22l-5-10-5 10M14 18h6"
    // code - технические термины: «джейсон» -> JSON
    readonly property string code:
        "m16 18 6-6-6-6M8 6l-6 6 6 6"
    // type - знаки препинания
    readonly property string type:
        "M4 7V4h16v3M9 20h6M12 4v16"
    // send - «Отправлять сообщение»
    readonly property string send:
        "m22 2-7 20-4-9-9-4ZM22 2 11 13"
    // app-window - программа из списка запущенных
    readonly property string app:
        "M2 6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2Z"
        + "M2 10h20M6 7h.01M9 7h.01"
    // palette - оформление
    readonly property string palette:
        "M12 22a1 1 0 0 1 0-20 10 9 0 0 1 10 9 5 5 0 0 1-5 5h-2.25"
        + "a1.75 1.75 0 0 0-1.4 2.8l.3.4a1.75 1.75 0 0 1-1.4 2.8Z"
        + "M13.5 6.5h.01M17.5 10.5h.01M6.5 12.5h.01M8.5 7.5h.01"
    // panel-bottom - полоска с волной у нижнего края экрана
    readonly property string pill:
        "M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"
        + "M3 15h18"
    // clipboard - «Текст не появляется?»: вставка идёт через буфер
    readonly property string clipboard:
        "M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"
        + "M9 2h6a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1Z"
    // timer - «Записывает само?»: решает длина нажатия
    readonly property string timer:
        "M10 2h4M12 14l3-3M12 22a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z"
    // target - «Слова распознаются неточно?»
    readonly property string target:
        "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20ZM12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12Z"
        + "M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"
    // hard-drive - что лежит на диске
    readonly property string disk:
        "M22 12H2M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89"
        + "A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11ZM6 16h.01M10 16h.01"
    // gauge - «Распознавание медленное?»
    readonly property string gauge:
        "m12 14 4-4M3.34 19a10 10 0 1 1 17.32 0"
    // space - «Пробел в конце»
    readonly property string space:
        "M22 17v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-1"
    // copy - «Не трогать скопированное»
    readonly property string copy:
        "M20 8h-8a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2Z"
        + "M4 16a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2"
    // volume-1 - звуковые сигналы
    readonly property string sound:
        "M11 5 6 9H2v6h4l5 4ZM16 9a3 3 0 0 1 0 6"
    // square - фон под настройками: карточка это и есть квадрат с рамкой
    readonly property string surface:
        "M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z"
    // shield - «Ничего не переписывает»
    readonly property string shield:
        "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6"
        + "a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0"
        + "C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1Z"
    // moon - «Не мешает компьютеру»: в покое программа спит
    readonly property string moon:
        "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"
    // arrow-right-left - подстановки: слева говорю, справа вставится
    readonly property string swap:
        "m16 3 4 4-4 4M20 7H4M8 21l-4-4 4-4M4 17h16"
    // file-text - несохранённая запись и «Техзадание»
    readonly property string file:
        "M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7ZM14 2v6h6"
        + "M8 13h8M8 17h5"
    // scissors - «Короче»
    readonly property string scissors:
        "M6 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"
        + "M20 4 8.12 15.88M14.47 14.48 20 20M8.12 8.12 12 12"
    // check - «Только ошибки»
    readonly property string check:
        "M20 6 9 17l-5-5"
    // briefcase - «Строже»
    readonly property string briefcase:
        "M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"
        + "M4 6h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2Z"
    // smile - «Проще»
    readonly property string smile:
        "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20ZM8 14s1.5 2 4 2 4-2 4-2"
        + "M9 9h.01M15 9h.01"
    // mail - «Письмом»
    readonly property string mail:
        "M22 7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2ZM2 7l10 6 10-6"
    // list-ordered - «По шагам»
    readonly property string steps:
        "M10 6h11M10 12h11M10 18h11M4 6h1v4M4 10h2M6 18H4c0-1 2-2 2-3s-1-1.5-2-1"

    // Сопоставление «имя страницы -> иконка». Держим здесь, а не в Settings.qml:
    // список страниц и так один, а перебирать имена в вёрстке - шум.
    //
    // Дверей стало шесть вместо десяти: Основное+Распознавание+Ввод слились в
    // «Диктовку», Словарь+Замены - в «Слова», а «Модели» ушли с панели вглубь
    // (человеку, который пишет письма, зоопарк моделей видеть незачем).
    //
    // Дальше шесть разделились надвое: своё (Главная, История, Статистика) и
    // служебное (Диктовка, Слова, О программе). Отсюда ещё два имени -
    // «Настройки» и «Назад», это переход между наборами.
    function forPage(name) {
        switch (name) {
        case "Главная":       return home;
        case "Диктовка":      return asr;
        case "Слова":         return dictionary;
        case "Дополнительно": return extra;
        case "История":       return history;
        case "Статистика":    return stats;
        case "О программе":   return about;
        case "Заметки":       return notes;
        case "Настройки":     return settings;
        case "Назад":         return back;
        }
        return "";
    }

    // Готовые преобразования (transforms.PRESETS) - тот же приём, что и со
    // страницами: список задан кодом, а десять одинаковых иконок в столбце
    // читаются хуже, чем ни одной. Незнакомый id даёт пустую строку, и ряд
    // просто останется без иконки - это законное состояние.
    function forTransform(id) {
        switch (id) {
        case "prompt":  return sparkles;
        case "shorter": return scissors;
        case "fix":     return check;
        case "formal":  return briefcase;
        case "simpler": return smile;
        case "bullets": return list;
        case "email":   return mail;
        case "steps":   return steps;
        case "spec":    return file;
        case "en":      return languages;
        }
        return "";
    }
}
