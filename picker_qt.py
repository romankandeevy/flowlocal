"""Окно выбора преобразования.

Живёт отдельно от пилюли, потому что ведёт себя противоположно: пилюля не берёт
фокус НИКОГДА (иначе Ctrl+V уедет не в то окно), а список фокус берёт
обязательно - иначе цифры и стрелки печатались бы в чужой документ вместо того,
чтобы листать список.

Это безопасно ровно потому, что порядок такой:

    1. сняли выделение Ctrl+C    <- текст уже у нас, в переменной
    2. запомнили окно            <- layered.foreground_window()
    3. показали список           <- фокус ушёл к нам, чужому окну всё равно
    4. выбрали                   <- цифра, стрелки, Enter, мышь
    5. вернули фокус             <- layered.focus_window()
    6. вставили                  <- Ctrl+V уходит туда, откуда брали

Показывать и прятать - только из главного потока Qt (через app.ui), как и всё
остальное окно. Из рабочего потока Qt молча не покажет ничего.
"""

import os
import sys

from PySide6.QtCore import QObject, QUrl, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication
from PySide6.QtQuick import QQuickView

_PREVIEW_MAX = 90


def _qml_path() -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "qml", "Picker.qml")


def preview_of(text: str) -> str:
    """Одна строка текста для шапки списка.

    Переводы строк схлопываем: в поле высотой в строку многострочный текст
    показал бы только первую, и человек решил бы, что выделилось не всё.
    """
    one = " ".join(str(text or "").split())
    if len(one) <= _PREVIEW_MAX:
        return one
    return one[:_PREVIEW_MAX - 1].rstrip() + "…"


class Picker(QObject):
    chosen = Signal(str)
    cancelled = Signal()

    def __init__(self, tokens) -> None:
        super().__init__()
        self.view = QQuickView()
        # Tool, а не Window: без этого окно появляется на панели задач и в
        # Alt+Tab. Список живёт полсекунды, ему там не место.
        #
        # WindowDoesNotAcceptFocus здесь НЕТ намеренно - в этом вся разница с
        # пилюлей. Если поставить, окно откроется, но клавиши в него не придут,
        # и список будет мёртвой картинкой.
        self.view.setFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                           | Qt.Tool)
        self.view.setColor(QColor(0, 0, 0, 0))
        self.view.setResizeMode(QQuickView.SizeViewToRootObject)
        self.view.rootContext().setContextProperty("T", tokens)
        self.view.setSource(QUrl.fromLocalFile(_qml_path()))
        if self.view.status() == QQuickView.Error:
            raise RuntimeError("; ".join(str(e) for e in self.view.errors()))
        self.root = self.view.rootObject()
        self.root.chosen.connect(self._on_chosen)
        self.root.cancelled.connect(self._on_cancelled)
        self._open = False

    # ---------- показ ----------

    def show(self, items: list, preview: str) -> None:
        if not items:
            return
        self.root.setProperty("items", items)
        self.root.setProperty("preview", preview)
        self.root.setProperty("current", 0)
        self._place()
        self._open = True
        self.view.show()
        # requestActivate ПОСЛЕ show: до появления окна активировать нечего, и
        # вызов молча уходит в пустоту - список остаётся без клавиатуры.
        self.view.requestActivate()

    def _place(self) -> None:
        """По центру экрана, где сейчас мышь, чуть выше середины.

        Не по центру строго: список появляется в ответ на действие человека, и
        взгляд у него в этот момент на тексте, а не в геометрическом центре.
        Чуть выше - примерно туда, куда смотрят.

        Экран берём по курсору, а не главный: на двух мониторах список иначе
        выскакивал бы на соседнем.
        """
        screen = (QGuiApplication.screenAt(QCursor.pos())
                  or QGuiApplication.primaryScreen())
        area = screen.availableGeometry()
        w = self.view.width() or 420
        h = self.view.height() or 300
        self.view.setPosition(area.x() + (area.width() - w) // 2,
                              area.y() + max(0, int(area.height() * 0.32) - h // 2))

    def hide(self) -> None:
        self._open = False
        self.view.hide()

    @property
    def open(self) -> bool:
        return self._open

    # ---------- ответы QML ----------

    def _on_chosen(self, tid: str) -> None:
        self.hide()
        self.chosen.emit(tid)

    def _on_cancelled(self) -> None:
        self.hide()
        self.cancelled.emit()
