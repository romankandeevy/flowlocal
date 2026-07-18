"""Мастер первого запуска - этап 5 плана (PLAN, раздел 4).

Шесть экранов: привет → язык и модель → микрофон → сочетание → проверка
вставки → проба. Канон подсмотрен у Handy и Wispr: момент «вау» должен
случиться ДО выхода из мастера, поэтому последний экран распознаёт настоящую
речь и показывает текст прямо в окне, никуда не вставляя.

Открывается сам, когда cfg.onboarded ещё false, и повторно - из настроек
(«О программе» → «Пройти знакомство заново»).

Работает на живых частях приложения, а не на муляжах: волна - с настоящего
микрофона (recorder), проба - через настоящий transcriber, проверка вставки -
настоящим inserter в поле самого мастера. Иначе мастер проверял бы сам себя.
"""

import threading

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickView

import models
import theme as T
from cleaner import clean
from settings_qt import Backend, _CloseFilter
from theme_qt import Tokens


class _Extra(QObject):
    """То, чего нет в настроечном Backend: живой звук, проба, финиш.

    Держит ссылку на App, а не копии его частей: recorder пересоздаётся при
    смене микрофона, и копия смотрела бы на мёртвый поток.
    """

    trialReady = Signal(str)
    insertDone = Signal(bool)
    # Установка Ollama: этап человеческими словами, доля и общий размер.
    # Размер отдаём отдельно, потому что 1.4 ГБ - это не та цифра, которую
    # прячут за процентами: человек должен видеть, во что ввязался.
    llmStage = Signal(str, float, float)
    llmDone = Signal(bool)

    def __init__(self, app) -> None:
        super().__init__()
        self._app = app
        self._trial = False
        self._llm_busy = False

    def _log(self, msg: str) -> None:
        """Логгер приложения. Импортировать app отсюда нельзя - он импортирует
        нас, вышел бы цикл; берём через уже имеющуюся ссылку."""
        try:
            import app as _app

            _app.log(msg)
        except Exception:  # noqa: BLE001 - лог не должен ронять установку
            pass

    @Slot(result="QVariantList")
    def levels(self) -> list:
        """Свежие уровни микрофона - волна рисуется в самом мастере.

        Прямо из recorder: он пишет всегда (keep_open), запись не нужна.
        """
        try:
            return [float(v) for v in self._app.recorder.drain_levels()]
        except Exception:  # noqa: BLE001 - без звука мастер не должен падать
            return []

    @Slot(result=str)
    def recommended(self) -> str:
        return models.pick(None)

    @Slot(str, result=str)
    def pickModel(self, lang: str) -> str:
        """Автовыбор по языку (PLAN 2.4): вопрос не про железо, а про язык."""
        return models.pick(lang or None)

    # ---------- проверка вставки ----------

    @Slot()
    def testInsert(self) -> None:
        """Вставить проверочный текст в поле мастера настоящим inserter'ом.

        В потоке: insert() ждёт отпускания модификаторов, и держать на этом
        главный поток нельзя. Фокус на поле ставит QML до вызова.
        """
        from inserter import insert

        def work() -> None:
            try:
                ok = insert("Проверка вставки FlowLocal ✓",
                            mode=self._app.cfg.get("insert_mode", "paste"),
                            restore=True)
            except Exception:  # noqa: BLE001
                ok = False
            self.insertDone.emit(bool(ok))

        threading.Thread(target=work, daemon=True).start()

    # ---------- проба ----------

    @Slot()
    def trialStart(self) -> None:
        if self._trial:
            return
        try:
            self._app.recorder.start()
            self._trial = True
        except Exception:  # noqa: BLE001
            self.trialReady.emit("микрофон недоступен")

    @Slot()
    def trialStop(self) -> None:
        if not self._trial:
            return
        self._trial = False
        audio = self._app.recorder.stop()

        def work() -> None:
            try:
                text = self._app.transcriber.transcribe(audio)
                text = clean(text, self._app.cfg, lambda *_a: None)
                self.trialReady.emit(text or "тишина - попробуйте ещё раз")
            except Exception as e:  # noqa: BLE001
                self.trialReady.emit(f"не получилось: {e}")

        threading.Thread(target=work, daemon=True).start()

    # ---------- правка текста: ставим Ollama за человека ----------

    @Slot(result=bool)
    def llmReady(self) -> bool:
        """Всё ли уже есть. Если да - экран предложения показывать незачем."""
        import ollama_setup as O

        return O.serving() and O.has_model(O.DEFAULT_MODEL)

    @Slot()
    def llmInstall(self) -> None:
        """Установку ведёт приложение, а не мастер.

        Мастер закроют раньше, чем докачаются три гигабайта, - и вместе с ним
        исчезли бы и полоса, и всякий признак работы. У App хозяин один, ход
        видно на пилюле поверх всех окон, а мы подписываемся, пока открыты.
        """
        self._app.install_ollama(self._llm_stage)

    def _llm_stage(self, stage: str, frac: float, total: float, done) -> None:
        if done is None:
            self.llmStage.emit(stage, frac, float(total))
        else:
            self.llmDone.emit(bool(done))

    @Slot()
    def finish(self) -> None:
        """Мастер пройден. Пишется через конфиг приложения, а не свой: у
        мастера и настроек не должно быть двух правд об одном файле."""
        self._app.cfg["onboarded"] = True
        import config as C

        try:
            C.save(self._app.cfg)
        except OSError:
            pass          # не записалось - покажем мастер ещё раз, не страшно
        if self._app.onboarding is not None:
            self._app.onboarding.close()
        # И сразу сказать, чем пользоваться. Мастер закрылся - человек остался
        # один на один с пустым экраном и иконкой в трее, которую Windows ещё и
        # прячет под шеврон. Тот же приём, что у Wispr: подсказку показывают в
        # момент, когда она нужна, а не заранее в списке правил.
        greet = getattr(self._app, "_greet_after_onboarding", None)
        if greet is not None:
            greet()


class OnboardingWindow:
    def __init__(self, app) -> None:
        # Свой Backend, как у настроек: капчер хоткея должен снимать хоткеи
        # приложения на время захвата - это уже устроено в нём.
        self.backend = Backend(app._on_config_change, app._on_hotkey_capture,
                               lambda: {}, "", "")
        self.extra = _Extra(app)
        self.tokens = Tokens()
        self.view: QQuickView | None = None

    def _build(self) -> None:
        import os
        import sys

        v = QQuickView()
        v.setTitle("Добро пожаловать в FlowLocal")
        v.setColor(QColor(*T.BG))
        v.setResizeMode(QQuickView.SizeRootObjectToView)
        v.resize(640, 560)
        v.setMinimumSize(v.size())
        ctx = v.rootContext()
        ctx.setContextProperty("T", self.tokens)
        ctx.setContextProperty("B", self.backend)
        ctx.setContextProperty("OB", self.extra)
        base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
        v.setSource(QUrl.fromLocalFile(os.path.join(base, "qml", "Onboarding.qml")))
        if v.status() == QQuickView.Error:
            raise RuntimeError("; ".join(e.toString() for e in v.errors()))
        v.installEventFilter(self._filter)
        self.view = v
        # Заголовок под тему - как у настроек: белая полоса над тёмным окном
        # выглядит чужеродно.
        import layered

        v.create()
        try:
            layered.style_titlebar(int(v.winId()), T.BG, dark=T.mode() == "dark")
        except Exception:  # noqa: BLE001 - косметика не роняет мастер
            pass

    def open(self) -> None:
        if self.view is None:
            self._filter = _CloseFilter(self.backend.cancelCapture)
            self._build()
        self.backend.reload()
        self.view.rootObject().setProperty("step", 0)
        self.view.show()
        self.view.raise_()
        self.view.requestActivate()

    def close(self) -> None:
        self.backend.cancelCapture()
        if self.view is not None:
            self.view.hide()
