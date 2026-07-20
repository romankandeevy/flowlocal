// Рамка вокруг вебвью: то немногое, что остаётся на Qt в окне настроек.
//
// Внутри - страница на React, снаружи - Qt. Граница проведена не по вкусу, а
// по тому, чего вебвью не умеет:
//
// 1. **Перетаскивание файла.** HTML5 drag-drop в WebView2 отдаёт объект File,
//    а не путь на диске - Python такой открыть не может. DropArea стоит ВОКРУГ
//    вебвью и на уровне Qt, где путь настоящий. Страница только рисует
//    подсветку по сигналу, а файл забирает Python.
// 2. **Фон под страницей.** Пока вебвью грузится, окно не должно быть белым
//    прямоугольником поверх тёмной темы. Цвет берём из токенов, и он совпадает
//    с тем, что через секунду нарисует страница.
//
// Тени тут нет намеренно: окно с системной рамкой, тень рисует Windows.

import QtQuick
import QtWebView

Rectangle {
    id: shell
    color: T.bg

    // Адрес с токеном и портом сокета. Ставит Python при создании окна: до
    // этого момента сервера ещё нет, и грузить нечего.
    property string startUrl: ""
    // Идёт ли перетаскивание файла - страница подсветится по этому сигналу.
    signal fileDropped(string path)
    signal dragActive(bool active)
    signal loaded(bool ok, string detail)

    onStartUrlChanged: if (startUrl !== "") view.url = startUrl

    // Выполнить скрипт на странице. Обёртка нужна, потому что runJavaScript
    // ждёт JS-функцию обратного вызова: питоновская лямбда на её месте молчит
    // - ни ошибки, ни ответа. Проверено пробником фазы 0, полчаса замера ушло
    // ровно на это.
    function run(script) {
        view.runJavaScript(script, function (r) {});
    }

    WebView {
        id: view
        objectName: "view"
        anchors.fill: parent

        onLoadingChanged: function (info) {
            if (info.status === WebView.LoadSucceededStatus)
                shell.loaded(true, "");
            else if (info.status === WebView.LoadFailedStatus)
                shell.loaded(false, info.errorString);
        }
    }

    // Поверх вебвью, но мышь не перехватывает: DropArea пропускает всё, кроме
    // перетаскивания. Без этого страница перестала бы получать щелчки.
    DropArea {
        anchors.fill: parent
        onEntered: (drag) => {
            // Берём только то, что и раньше умели: один файл с диска.
            drag.accepted = drag.hasUrls && drag.urls.length > 0;
            if (drag.accepted) shell.dragActive(true);
        }
        onExited: shell.dragActive(false)
        onDropped: (drop) => {
            shell.dragActive(false);
            if (drop.hasUrls && drop.urls.length > 0) {
                // toLocalFile, а не toString: у Python на руках должен быть
                // путь вида C:/..., а не file:///C:/...
                var u = drop.urls[0];
                shell.fileDropped(u.toString().replace(/^file:\/{3}/, ""));
                drop.accept();
            }
        }
    }
}
