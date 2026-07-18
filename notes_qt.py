"""Окно заметок.

Отдельное окно, а не страница в главном: диктуют В него, а не рядом с ним, и
главное окно при этом остаётся открытым. Человек не должен выбирать между
«вижу свои настройки» и «пишу заметку».

Диктовка сюда работает сама, без единой строки специального кода: текст мы
вставляем в активное окно через Ctrl+V, а активным в этот момент будет это окно
с полем в фокусе. Приятная неожиданность, а не заслуга - но проверить это
обязательно, потому что вся затея на этом держится.

«Привести в порядок» переиспользует трансформы (transforms.py): там уже есть и
указание для модели, и предохранители от пустого ответа и абсурдной длины.
Заводить для заметок второй путь к Ollama незачем.
"""

import os
import sys

from PySide6.QtCore import QObject, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickView

import notes

# Указание для «привести в порядок». Отдельное от трансформов: там правки
# короткие и точечные, здесь - целая надиктованная страница, и главная беда у
# неё другая - поток без структуры.
TIDY = (
    "Приведи в порядок надиктованный текст. Расставь абзацы, убери повторы и "
    "оговорки, оформи перечисления списком. НЕ ВЫБРАСЫВАЙ смысл: все мысли, "
    "числа, имена и просьбы должны остаться. Ничего не придумывай от себя. "
    "Верни только итоговый текст."
)


def _qml_path() -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "qml", "Notes.qml")


class NotesWindow(QObject):
    """Окно заметок. Создаётся при первом открытии и дальше живёт в памяти."""

    # Результат «привести в порядок» возвращаем сигналом: считает его рабочий
    # поток, а трогать QML можно только из главного. Сигнал переносит сам.
    done = Signal(str, str)

    def __init__(self, tokens, cfg, log, tidy_fn=None) -> None:
        super().__init__()
        self.cfg = cfg
        self.log = log
        self._tidy_fn = tidy_fn
        self._query = ""
        self.view = QQuickView()
        self.view.setTitle("Заметки — FlowLocal")
        self.view.setColor(QColor(0, 0, 0, 0))
        self.view.setResizeMode(QQuickView.SizeRootObjectToView)
        self.view.resize(860, 600)
        self.view.rootContext().setContextProperty("T", tokens)
        self.view.setSource(QUrl.fromLocalFile(_qml_path()))
        if self.view.status() == QQuickView.Error:
            raise RuntimeError("; ".join(str(e) for e in self.view.errors()))
        self.root = self.view.rootObject()
        self.root.pick.connect(self.open_note)
        self.root.create.connect(self.create)
        self.root.remove.connect(self.remove)
        self.root.store.connect(self.store)
        self.root.improve.connect(self.improve)
        self.root.copy.connect(self.copy)
        self.root.search.connect(self.search)
        self.done.connect(self._on_done)

    # ---------- показ ----------

    def open(self) -> None:
        self.refresh()
        if not self.root.property("current"):
            items = notes.listing()
            if items:
                self.open_note(items[0]["id"])
            else:
                self.create()
        self.view.show()
        self.view.raise_()
        self.view.requestActivate()

    def refresh(self) -> None:
        self.root.setProperty("items", notes.listing(self._query))

    # ---------- ответы окна ----------

    @Slot(str)
    def search(self, query: str) -> None:
        self._query = query
        self.refresh()

    @Slot(str)
    def open_note(self, note_id: str) -> None:
        d = notes.load(note_id)
        if d is None:
            return
        self.root.setProperty("current", note_id)
        self.root.setText(d.get("text", ""))

    @Slot()
    def create(self) -> None:
        nid = notes.save(notes.new_id(), "")
        if not nid:
            return
        self.root.setProperty("current", nid)
        self.root.setText("")
        self.refresh()

    @Slot(str, str)
    def store(self, note_id: str, text: str) -> None:
        if not note_id:
            return
        notes.save(note_id, text)
        self.refresh()

    @Slot(str)
    def remove(self, note_id: str) -> None:
        notes.delete(note_id)
        self.root.setProperty("current", "")
        self.root.setText("")
        self.refresh()

    @Slot(str)
    def copy(self, text: str) -> None:
        from inserter import _set_clipboard_text

        _set_clipboard_text(text)

    @Slot(str, str)
    def improve(self, note_id: str, text: str) -> None:
        """Причесать заметку моделью. Работа уходит в поток - страница долгая."""
        import threading

        def work() -> None:
            got = ""
            try:
                if self._tidy_fn is not None:
                    got = self._tidy_fn(text, TIDY)
            except Exception as e:  # noqa: BLE001
                self.log(f"заметку не причесать: {e}")
            self.done.emit(note_id, got)

        threading.Thread(target=work, daemon=True).start()

    def _on_done(self, note_id: str, text: str) -> None:
        self.root.setProperty("busy", False)
        if not text:
            return
        notes.save(note_id, text)
        if self.root.property("current") == note_id:
            self.root.setText(text)
        self.refresh()
