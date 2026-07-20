"""Окно настроек на вебвью: создать по требованию, при закрытии отпустить.

Почему не «поднять один раз и держать». Замер фазы 0: вебвью стоит 77 МБ
приватной памяти плюс 46 МБ своих, и живёт это в шести отдельных процессах
msedgewebview2.exe. Программа висит в трее сутками, а окно настроек открывают
раз в неделю - держать под него сто двадцать мегабайт всё это время нельзя.

Тем же замером проверено, что отпускать их работает: после `setSource(QUrl())`
от вебвью не остаётся ни одного процесса и ни одного мегабайта. Оговорка из
плана не просто записана, а измерена.

**Прогрев обязателен, а не желателен.** Пятый замер фазы 0 - единственный, что
не уложился в порог: от `show()` до загруженной страницы 443-475 мс при пороге
400. План это предвидел («не уложились - прогревать вебвью в фоне через 30 с
после старта»), и здесь прогрев из оговорки становится кодом. Через 30 секунд
после запуска поднимаем вебвью скрытым, даём ему загрузить страницу и гасим:
дорогая часть - инициализация движка, и она остаётся сделанной.

Тридцать секунд - не круглое число ради красоты. На старте программа и так
занята: грузится модель распознавания (медиана 2.1 с, худшие 10% - 4.0 с),
ставится хук клавиатуры, поднимается трей. Совать туда же запуск Chromium
значит соревноваться с тем, ради чего программу открыли.
"""

import os
import sys

# Каталог PySide6 - в поиск библиотек, иначе QML-плагин вебвью не грузится с
# «не найден указанный модуль», хотя все DLL на месте. Python 3.8+ зовёт
# SetDefaultDllDirectories, и PATH из поиска выпадает; Qt грузит плагин обычным
# LoadLibrary и не находит соседний Qt6WebViewQuick.dll.
#
# В собранной программе не понадобится - там DLL лежат рядом с exe, а каталог
# exe в поиске есть всегда. Грабля чисто для запуска из исходников, но ловится
# первой и выглядит как «вебвью не работает вовсе». Разобрано в PLAN, фаза 0.
import PySide6

if hasattr(os, "add_dll_directory"):
    # Проверка не для красоты: `os.add_dll_directory` существует ТОЛЬКО на
    # Windows. Без неё импорт этого модуля падал бы на macOS с AttributeError -
    # то есть ровно тем классом отказа, который на ветке port/macos уже
    # вычищали из layered, media и wakeup. Новый код принёс его обратно.
    #
    # На macOS вебвью тоже работает, но другим бэкендом - WKWebView вместо
    # WebView2, - и никакой возни с путями к библиотекам ему не нужно.
    os.add_dll_directory(os.path.dirname(PySide6.__file__))

from PySide6.QtCore import QMetaObject, QSize, QTimer, QUrl, Qt  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtQuick import QQuickView  # noqa: E402
from PySide6.QtWebView import QtWebView  # noqa: E402

import theme as T  # noqa: E402

W, H = 980, 720
MIN_W, MIN_H = 720, 560

# Через сколько после старта греть вебвью. Обоснование - в шапке модуля.
WARMUP_AFTER_MS = 30_000

_initialized = False


def initialize() -> None:
    """QtWebView.initialize(). Зовётся ДО создания QApplication - так требует Qt.

    Отдельной функцией, а не при импорте: импорт модуля может случиться в любой
    момент, а этот вызов - строго один и строго раньше приложения.
    """
    global _initialized

    if not _initialized:
        QtWebView.initialize()
        _initialized = True


class WebWindow:
    """Окно с вебвью. Создаётся при первом показе, гасится при закрытии."""

    def __init__(self, bridge, tokens, lang, log=print) -> None:
        self.bridge = bridge
        self.tokens = tokens
        self.lang = lang
        self.log = log
        self.view: QQuickView | None = None
        self.on_file = None          # кому отдать перетащенный файл
        self._warmed = False

    # ---------- показ и уборка ----------

    def show(self) -> None:
        if self.view is None:
            self._build()
        v = self.view
        assert v is not None
        v.show()
        v.raise_()
        v.requestActivate()

    def hide(self) -> None:
        """Спрятать и отпустить память.

        Не просто hide(): спрятанное вебвью держит все шесть процессов и все сто
        двадцать мегабайт. Гасим источник целиком - тем же способом, каким это
        проверено в пробнике фазы 0.
        """
        v, self.view = self.view, None
        if v is None:
            return
        v.hide()
        v.setSource(QUrl())
        v.deleteLater()

    def toggle(self) -> None:
        if self.view is not None and self.view.isVisible():
            self.hide()
        else:
            self.show()

    # ---------- прогрев ----------

    def schedule_warmup(self) -> None:
        """Через WARMUP_AFTER_MS поднять вебвью скрытым и погасить.

        Дорогая часть - инициализация движка, и она переживает закрытие окна:
        второе открытие укладывается в порог, первое - нет.
        """
        QTimer.singleShot(WARMUP_AFTER_MS, self._warmup)

    def _warmup(self) -> None:
        if self._warmed or self.view is not None:
            return          # окно уже открыли руками - греть нечего
        self._warmed = True
        try:
            self._build()
            v = self.view
            assert v is not None
            # Не show(): окно не должно мелькнуть на экране. Достаточно того,
            # что вебвью создано и загрузило страницу.
            v.create()
            QTimer.singleShot(4000, self._warmup_done)
        except Exception as e:  # noqa: BLE001 - прогрев не обязан удаваться
            self.log(f"прогрев вебвью не вышел: {type(e).__name__}: {e}")
            self.view = None

    def _warmup_done(self) -> None:
        # Окно могли открыть за эти четыре секунды - тогда его не трогаем.
        if self.view is not None and not self.view.isVisible():
            self.hide()
            self.log("вебвью прогрето")

    # ---------- сборка ----------

    def _build(self) -> None:
        initialize()
        v = QQuickView()
        v.setTitle("FlowLocal")
        v.setColor(QColor(*T.BG))
        v.setResizeMode(QQuickView.SizeRootObjectToView)
        v.resize(W, H)
        v.setMinimumSize(QSize(MIN_W, MIN_H))

        ctx = v.rootContext()
        # Токены и язык нужны самой рамке: она рисует фон до того, как страница
        # успела загрузиться. Backend рамке не нужен - страница ходит к нему
        # мостом, а не контекстным свойством.
        ctx.setContextProperty("T", self.tokens)
        ctx.setContextProperty("L", self.lang)

        base = getattr(sys, "_MEIPASS", None) or os.path.dirname(
            os.path.abspath(__file__))
        v.setSource(QUrl.fromLocalFile(
            os.path.join(base, "qml", "windows", "WebShell.qml")))
        if v.status() == QQuickView.Error:
            raise RuntimeError("; ".join(e.toString() for e in v.errors()))

        root = v.rootObject()
        root.setProperty("startUrl", self.bridge.page_url())
        root.fileDropped.connect(self._dropped)
        root.loaded.connect(self._loaded)
        self.view = v

    # ---------- события ----------

    def _dropped(self, path: str) -> None:
        # Путь пришёл с уровня Qt, а не из страницы, и это единственный способ
        # его получить: HTML5 drag-drop в WebView2 отдаёт File без пути.
        if self.on_file:
            self.on_file(path)

    def _loaded(self, ok: bool, detail: str) -> None:
        if not ok:
            self.log(f"страница настроек не загрузилась: {detail}")

    # ---------- тема ----------

    def retheme(self) -> None:
        """Перекрасить страницу вслед за темой программы.

        Атрибутом на <html>, а не через prefers-color-scheme: тему выбирают в
        настройках программы, а системная там лишь один вариант из трёх.
        """
        if self.view is None:
            return
        root = self.view.rootObject()
        if root is None:
            return
        # T.mode() отдаёт уже разрешённую тему: «системная» к этому моменту
        # превращена в light или dark, и гадать заново не надо.
        mode = T.mode()
        QMetaObject.invokeMethod(
            root, "run", Qt.DirectConnection,
            _arg(f'document.documentElement.dataset.theme = "{mode}"'))


def _arg(value: str):
    """Q_ARG(QString, value) - у PySide он собирается так."""
    from PySide6.QtCore import Q_ARG

    return Q_ARG("QVariant", value)
