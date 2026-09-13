"""Окно с расшифровкой файла.

Отдельным окном, а не вставкой в активное поле, - почему именно так, разобрано
в шапке qml/windows/Transcript.qml.

Окно ОДНО и переиспользуется: вторая расшифровка показывается в нём же, а не
разводит по экрану стопку одинаковых окон. Прошлый текст при этом теряется - и
это законно, потому что он уже лежит в истории, а история открывается из
главного окна.

Устройство то же, что у settings_qt: QQuickView, токены и переводчик контекстными
свойствами, ответы окна - сигналами. Второй способ делать окна в этом проекте
заводить незачем.
"""

import os
import sys
import time

from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickView


def _qml_path() -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "qml", "windows", "Transcript.qml")


class TranscriptWindow(QObject):
    def __init__(self, tokens, log) -> None:
        super().__init__()
        self.log = log
        self._source = ""
        self.view = QQuickView()
        self.view.setTitle("Расшифровка — FlowLocal")
        self.view.setColor(QColor(0, 0, 0, 0))
        self.view.setResizeMode(QQuickView.SizeRootObjectToView)
        self.view.resize(760, 560)
        self.view.rootContext().setContextProperty("T", tokens)
        from theme_qt import Lang

        self.lang = Lang()
        self.view.rootContext().setContextProperty("L", self.lang)
        self.view.setSource(QUrl.fromLocalFile(_qml_path()))
        if self.view.status() == QQuickView.Error:
            raise RuntimeError("; ".join(str(e) for e in self.view.errors()))
        self.root = self.view.rootObject()
        self.root.copy.connect(self.copy)
        self.root.save.connect(self.save)

    def show(self, source: str, text: str) -> None:
        self._source = source
        self.root.setProperty("source", source)
        self.root.setProperty("note", "")
        self.root.setText(text)
        self.view.show()
        self.view.raise_()
        self.view.requestActivate()

    @Slot(str)
    def copy(self, text: str) -> None:
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setText(text)
        import i18n

        self.root.setProperty("note", i18n.t("скопировано"))

    @Slot(str)
    def save(self, text: str) -> None:
        """Сохранить в .txt рядом с исходным файлом.

        Имя предлагаем от исходного - «запись.ogg» превращается в «запись.txt».
        Человек, расшифровавший десять голосовых, иначе получил бы десять
        файлов с именами вида «Новый текстовый документ (3)».
        """
        import i18n
        from PySide6.QtWidgets import QFileDialog

        stem = os.path.splitext(self._source)[0] or time.strftime("Расшифровка-%Y-%m-%d")
        path, _ = QFileDialog.getSaveFileName(
            None, i18n.t("Куда сохранить"),
            os.path.join(os.path.expanduser("~"), stem + ".txt"),
            f"{i18n.t('Текст')} (*.txt)")
        if not path:
            return
        try:
            # newline="" плюс свои \n: в текстовом режиме Windows превратила бы
            # их в CRLF, и файл стал бы смесью двух переносов, если его потом
            # правят чем-то ещё. Ровно то же правило, что в inbox.append.
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text.replace("\r\n", "\n"))
        except OSError as e:
            self.log(f"расшифровка не сохранилась: {e}")
            self.root.setProperty("note", i18n.t("файл не сохранился"))
            return
        self.log(f"расшифровка сохранена: {path}")
        self.root.setProperty("note", i18n.t("сохранено"))
