"""Мастер первого запуска (PLAN, задача 7).

Девять экранов: привет → оформление → модель → микрофон → удержание →
нажатие → проверка вставки → проба → правка текста. Канон подсмотрен у Handy
и Wispr:
момент «вау» должен случиться ДО выхода из мастера, поэтому предпоследний
экран распознаёт настоящую речь и показывает текст прямо в окне, никуда не
вставляя.

Открывается сам, когда cfg.onboarded ещё false, и повторно - из настроек
(«О программе» → «Пройти знакомство заново»).

Работает на живых частях приложения, а не на муляжах: волна - с настоящего
микрофона (recorder), проба - через настоящий transcriber, проверка вставки -
настоящим inserter в поле самого мастера, отклик плашек - с настоящего хука
клавиатуры. Иначе мастер проверял бы сам себя.
"""

import threading

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickView

import inputspec
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
    # Экран сочетания: какие плашки зажаты прямо сейчас и собралось ли
    # сочетание целиком. Список булевых идёт ровно в том порядке, в каком
    # inputspec.pretty клеит подписи, - иначе загорались бы не те плашки.
    comboState = Signal("QVariantList", bool)
    # Приватный: им колбэк из потока keyboard/mouse перебрасывает состояние в
    # главный поток. Прямо из чужого потока трогать QML нельзя - тот же приём
    # и по той же причине, что `_captured` у настроечного Backend.
    _comboRaw = Signal("QVariantList", bool)

    # Имена кнопок у pynput и у нас разные: pynput зовёт боковые «x1»/«x2»,
    # inputspec - «x»/«x2» (так их называет низкоуровневый хук Windows).
    _PYNPUT_BUTTONS = {"middle": "middle", "x1": "x", "x2": "x2"}

    def __init__(self, app) -> None:
        super().__init__()
        self._app = app
        self._trial = False
        self._llm_busy = False
        # Слежка за живым нажатием сочетания (экран «Сочетание»).
        self._watching = False
        self._watch_mods: list[str] = []
        self._watch_key: str | None = None
        self._watch_mouse: str | None = None
        self._watch_held: set[str] = set()
        self._watch_tail = False
        self._watch_hook = None
        self._watch_mouse_hook = None
        # Последнее отданное состояние плашек. Зажатую клавишу Windows шлёт
        # авто-повтором - десятки одинаковых "down" в секунду, - а на живой
        # проверке жеста человек именно ДЕРЖИТ сочетание. Без этой памяти каждый
        # повтор гнал бы сигнал через поток в QML; поток одинаковых состояний
        # голодал GIL, и хук клавиатуры переставал укладываться в отведённые
        # Windows 300 мс - весь ввод начинал лагать (HANDOFF, «тик оверлея»).
        self._last_combo: tuple | None = None
        self._comboRaw.connect(self._relay_combo)

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

    @Slot(str, result="QVariantMap")
    def themeSwatch(self, name: str) -> dict:
        """Краски КОНКРЕТНОЙ темы для мини-превью на шаге выбора оформления.

        Не через глобальную T: там живёт ТЕКУЩАЯ тема, и все три карточки
        показали бы одно и то же. Считаем пары бумага/чернила прямо из палитры
        (theme._PALETTE) и сплавляем производные - глобальное состояние темы не
        трогаем. «system» разворачиваем в реальную тему Windows: карточка
        «Система» должна показывать то, что человек и увидит.

        Отдаём готовыми «#rrggbb» - строку QML кладёт в color как есть.
        """
        t = T.resolve(name)                       # system -> light|dark
        pal = T._PALETTE[t]
        ink, paper = pal["ink"], pal["paper"]
        a = dict(T._ALPHA)
        a.update(pal.get("alpha") or {})

        def flat(alpha: float) -> str:
            # «серый» - это чернила поверх бумаги; сплавляем в непрозрачный цвет,
            # ровно как theme._apply делает для текущей темы.
            return T.hx(T.mix(paper, ink, alpha))

        return {
            "paper": T.hx(paper),
            "ink": T.hx(ink),
            "text": T.hx(ink),
            "textMuted": flat(a["text_muted"]),
            "textFaint": flat(a["text_faint"]),
            "border": flat(a["border"]),
            "fillStrong": flat(a["fill_strong"]),
            "accent": T.hx(pal["accent"]),
            "accentFg": T.hx(pal["accent_fg"]),
            "success": T.hx(pal["success"]),
        }

    # ---------- живое нажатие сочетания ----------
    #
    # Экран сочетания был единственным местом мастера, где человеку называли
    # клавиши и не давали их попробовать: поле захвата отвечает на клик, а на
    # само нажатие - ничем. Теперь плашки тонут под пальцами по одной, а
    # собранное сочетание загорается целиком, и «работает ли оно вообще»
    # проверяется тем же движением, каким потом диктуют.

    @Slot(str)
    def watchHotkey(self, spec: str) -> None:
        """Начать следить за настоящим нажатием `spec`.

        Слушаем, но НЕ глотаем: отклик не должен стоить человеку клавиш.
        А вот хоткеи приложения на это время сняты - иначе нажатие прямо в
        мастере запустило бы настоящую диктовку, и вставлять её было бы
        некуда: текстового поля на этом экране нет. Пробуют голос на шаге
        «Проба», и там для этого есть кнопка.
        """
        self.unwatchHotkey()
        mods, key, mouse = inputspec.parse(spec or "")
        if not (mods or key or mouse):
            return
        self._watch_mods, self._watch_key, self._watch_mouse = mods, key, mouse
        self._watch_held = set()
        self._watch_tail = False
        self._last_combo = None      # новый экран - первый emit должен пройти
        try:
            import keyboard

            self._watch_hook = keyboard.hook(self._watch_key_event)
            if mouse:
                from pynput import mouse as pmouse

                self._watch_mouse_hook = pmouse.Listener(on_click=self._watch_mouse_click)
                self._watch_mouse_hook.start()
        except Exception as e:  # noqa: BLE001 - без отклика мастер проходится
            self._log(f"слежка за сочетанием не завелась: {e}")
            self._watch_hook = self._watch_mouse_hook = None
            return
        self._watching = True
        try:
            self._app._on_hotkey_capture(True)
        except Exception as e:  # noqa: BLE001
            self._log(f"хоткеи на время экрана сочетания не снялись: {e}")
        self._emit_combo()

    @Slot()
    def unwatchHotkey(self) -> None:
        """Снять слежку. Звать безопасно всегда - в том числе при закрытии
        окна: иначе хук остался бы висеть, а приложение - без хоткеев."""
        if not self._watching:
            return
        self._watching = False
        try:
            import keyboard

            if self._watch_hook is not None:
                keyboard.unhook(self._watch_hook)   # поимённо, не unhook_all
        except (KeyError, ValueError, ImportError):
            pass
        try:
            if self._watch_mouse_hook is not None:
                self._watch_mouse_hook.stop()
        except Exception:  # noqa: BLE001 - слушатель мог уже умереть
            pass
        self._watch_hook = self._watch_mouse_hook = None
        self._watch_held = set()
        self._watch_tail = False
        self._last_combo = None
        try:
            self._app._on_hotkey_capture(False)     # хоткеи приложению обратно
        except Exception as e:  # noqa: BLE001
            self._log(f"хоткеи после экрана сочетания не вернулись: {e}")

    def _relay_combo(self, down: list, lit: bool) -> None:
        """Уже в главном потоке: сюда попадают только через `_comboRaw`."""
        self.comboState.emit(down, lit)

    def _emit_combo(self) -> None:
        down = [m in self._watch_held for m in self._watch_mods]
        if self._watch_key or self._watch_mouse:
            down.append(self._watch_tail)
        lit = bool(down) and all(down)
        # Шлём, только когда состояние реально изменилось: авто-повтор зажатой
        # клавиши приносит то же самое десятки раз в секунду - см. _last_combo.
        state = (tuple(down), lit)
        if state == self._last_combo:
            return
        self._last_combo = state
        self._comboRaw.emit(down, lit)

    # Колбэки ниже исполняются в потоке keyboard/mouse: только своё состояние
    # и сигнал, больше ничего.

    def _watch_key_event(self, e) -> None:
        name = (e.name or "").lower()
        canon = inputspec.canon_modifier(name)
        if e.event_type == "down":
            if canon:
                self._watch_held.add(canon)
            elif self._watch_key and name == self._watch_key:
                self._watch_tail = True
            else:
                return
        elif e.event_type == "up":
            if canon:
                self._watch_held.discard(canon)
            elif self._watch_key and name == self._watch_key:
                self._watch_tail = False
            else:
                return
        else:
            return
        self._emit_combo()

    def _watch_mouse_click(self, _x, _y, button, pressed) -> None:
        btn = self._PYNPUT_BUTTONS.get(getattr(button, "name", ""))
        if btn is None or btn != self._watch_mouse:
            return
        self._watch_tail = bool(pressed)
        self._emit_combo()

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
                # Первая проба голоса в жизни человека. Питоновское исключение
                # здесь - худшее из возможных первых впечатлений; подробность
                # уходит в журнал, человеку остаётся понятная строка.
                try:
                    from app import log
                    log(f"пробная диктовка не вышла: {e}")
                except Exception:  # noqa: BLE001
                    pass
                self.trialReady.emit("не получилось - попробуйте ещё раз")

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
        # Перевод на границе с окном, как в settings_qt._llm_stage: этапы
        # приходят из ollama_setup русскими фразами.
        import i18n

        if done is None:
            self.llmStage.emit(i18n.t(stage), frac, float(total))
        else:
            self.llmDone.emit(bool(done))

    @Slot()
    def finish(self) -> None:
        """Мастер пройден. Пишется через конфиг приложения, а не свой: у
        мастера и настроек не должно быть двух правд об одном файле."""
        # Первым делом - вернуть приложению хоткеи. Экран сочетания снимает их
        # на время слежки, и уйти отсюда с немой программой нельзя: диктовать
        # человек пойдёт сразу же, ему только что показали чем.
        self.unwatchHotkey()
        self._app.cfg["onboarded"] = True
        import config as C

        try:
            C.save(self._app.cfg)
        except OSError:
            pass          # не записалось - покажем мастер ещё раз, не страшно
        if self._app.onboarding is not None:
            self._app.onboarding.close()
        # Теперь можно и модель поднять. На старте её намеренно не греют, пока
        # мастер на экране: сборка сессии держит GIL и мастер от этого лагает
        # (app.run, там же и объяснение). Мастер закрылся - греем, чтобы первая
        # диктовка не ждала лишние две секунды.
        try:
            threading.Thread(target=self._app._load_model_bg, daemon=True).start()
        except Exception as e:  # noqa: BLE001 - прогрев не стоит финиша мастера
            self._log(f"прогрев после мастера не запустился: {e}")
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
        # 660, а не 560. Прокрутка внутри шага теперь есть (Onboarding.qml), но
        # прокручиваемый мастер - плохой мастер: человек видит обрезанную
        # карточку и не догадывается, что под ней что-то есть. Высоты хватает
        # самому длинному шагу целиком, прокрутка остаётся страховкой на случай
        # мелкого экрана.
        v.resize(640, 660)
        v.setMinimumSize(v.size())
        ctx = v.rootContext()
        ctx.setContextProperty("T", self.tokens)
        ctx.setContextProperty("B", self.backend)
        ctx.setContextProperty("OB", self.extra)
        from theme_qt import Lang

        self.lang = Lang()
        ctx.setContextProperty("L", self.lang)
        base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
        v.setSource(QUrl.fromLocalFile(os.path.join(base, "qml", "windows", "Onboarding.qml")))
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

    def _on_window_close(self) -> None:
        """Окно закрыли крестиком, а не кнопкой «Готово».

        Наш close() при этом не зовётся - Qt просто прячет окно, - поэтому
        уборка нужна здесь. Прежде хватало снять захват хоткея; теперь экран
        сочетания на время слежки снимает ВСЕ хоткеи приложения, и без этой
        строки программа осталась бы немой до перезапуска. Ровно тот сорт
        поломки, который человек не свяжет с мастером: он просто нажмёт своё
        сочетание, и ничего не произойдёт.
        """
        self.backend.cancelCapture()
        self.extra.unwatchHotkey()

    def open(self) -> None:
        if self.view is None:
            self._filter = _CloseFilter(self._on_window_close)
            self._build()
        self.backend.reload()
        self.view.rootObject().setProperty("step", 0)
        self.view.show()
        self.view.raise_()
        self.view.requestActivate()

    def retheme(self) -> None:
        """Перекрасить окно под новую тему. Зовёт app._apply_theme().

        Метода тут не было, и это стоило владельцу непройденного мастера: тему
        выбирают ВТОРЫМ шагом, приложение её применяло, а окно мастера
        оставалось со старыми токенами. Перекрашивалось оно наполовину -
        случайными кусками, - и «Дальше» становилась белой на белом.

        Ровно тот же метод есть у окна настроек. Разница была не в устройстве,
        а в том, что про мастер забыли: там тему меняют раз в полгода, здесь -
        на втором экране из девяти, у человека, который видит программу
        впервые.
        """
        self.tokens.retheme()
        if self.view is None:
            return
        self.view.setColor(QColor(*T.BG))
        try:
            import layered

            layered.style_titlebar(int(self.view.winId()), T.BG,
                                   dark=T.mode() == "dark")
        except Exception:  # noqa: BLE001 - косметика не роняет мастер
            pass

    def close(self) -> None:
        self.backend.cancelCapture()
        self.extra.unwatchHotkey()
        if self.view is not None:
            self.view.hide()
