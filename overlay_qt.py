"""Пилюля-индикатор на Qt/QML - этап 6 плана.

Замена overlay.py (PIL) и layered.py (426 строк ctypes). Что уходит вместе с
ними, доказано замером `tools/probe_qt_overlay.py` на живой машине:

    вариант                          NOACTIVATE  цел:show  цел:activate
    full (с WindowDoesNotAcceptFocus)      True      True          True
    trap (рецепт из интернета)            False      True         False

То есть Qt ставит WS_EX_NOACTIVATE сам, из флага WindowDoesNotAcceptFocus, и
фокус чужого окна цел даже при попытке активировать пилюлю. Ходовой рецепт
`Frameless | WindowStaysOnTop | Tool` (он стоит в мёртвом whisper-writer)
флага не даёт и фокус отдаёт - проверено, тест краснеет.

Осциллограмма живёт в QML на render-потоке: из Python сюда прилетают только
числа, никакой отрисовки на GIL. Именно на этом сломался Handy - у него кадры
летят через IPC в вебвью, и ему пришлось душить волну до 30 fps из-за утечки
памяти в WebKit (wry#1489, открыт с февраля 2025).

Токены - из theme.py через контекстное свойство `T`: один источник правды.

ВНИМАНИЕ: в app.py пока НЕ подключён. Qt требует своего exec() в главном
потоке, где сейчас крутится tkinter, - переворот главного цикла делается
вместе с этапом 7, одним куском. Проверять этот файл: tools/preview_overlay_qt.py
"""

import ctypes
import os
import sys
import time

from PySide6.QtCore import QObject, QTimer, QUrl, Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtQuick import QQuickView

import theme as T
from theme_qt import Tokens


def _preload_qml_deps() -> bool:
    """Втянуть в процесс Qt6QuickEffects.dll до загрузки QML.

    Грабли PySide6, стоившие часа. QML-плагин (qml/QtQuick/Effects/
    effectsplugin.dll) грузится штатным загрузчиком Windows, а тот ищет
    зависимости по обычным путям - и не видит папку PySide6, которую Python
    прописал себе через os.add_dll_directory. Работает поэтому только то, чей
    Qt6*.dll УЖЕ загружен в процесс импортом Python-модуля.

    Отсюда странная картина: `import QtQuick` живёт (его Qt6Quick.dll притащил
    `from PySide6.QtQuick import QQuickView`), а `import QtQuick.Effects` падает
    с «Не найден указанный модуль» - у MultiEffect Python-модуля нет, тянуть
    его нечем. Правка PATH не помогает и делает хуже: она ломает и базовый
    QtQuick.

    Лечится тем же способом, каким Python тянет остальные: загрузить DLL руками.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        import PySide6
        base = os.path.dirname(PySide6.__file__)
    dll = os.path.join(base, "Qt6QuickEffects.dll")
    try:
        ctypes.WinDLL(dll)
        return True
    except OSError:
        # Без него не будет тени, но пилюля покажется. Оверлей не должен
        # ронять приложение - тем более из-за украшения.
        return False


_EFFECTS_OK = _preload_qml_deps()

LOADING = "loading"
RECORDING = "recording"
PROCESSING = "processing"
DONE = "done"
ERROR = "error"

# Пол осциллограммы: RMS ниже него нормируется в тишину, чтобы полоски не
# плясали на шуме. Замеры на этой машине: тихая комната ~0.0004, еле слышный
# источник ~0.005, речь ~0.05-0.2. Выше ставить нельзя - придавит речь с тихого
# микрофона (при 0.015 запись с rms 0.001 модель читала, а волна лежала ровно).
_FLOOR = 0.006

# Отдельный, куда более низкий порог - для надписи «не слышно микрофона». Это
# НЕ порог отрисовки: под `_FLOOR` (0.006) попадает и еле слышный источник
# (0.005), который модель отлично читает, - обвинять микрофон в молчании, пока
# он пишет речь, нельзя. «Не слышно» - это про заглушенную гарнитуру и мёртвый
# вход, а там сигнал у самого цифрового нуля (тихая комната ~0.0004). Порог
# между ними: всё, что тише 0.0015, - действительно тишина.
_SILENCE_FLOOR = 0.0015

# Сколько секунд тишины под запись терпим молча, прежде чем написать на пилюле
# «не слышно микрофона». Ловит заглушенные гарнитуры: без этого диктовка в
# выключенный микрофон кончается пустой вставкой и недоумением.
_SILENCE_SEC = 3.0


class Overlay(QObject):
    """Тот же публичный API, что у overlay.Overlay, - чтобы app.py не заметил
    подмены, когда дойдёт черёд его переворачивать."""

    def __init__(self, level_fn=None) -> None:
        super().__init__()
        self.level_fn = level_fn
        self._state: str | None = None
        self._shown = False
        self._msg = ""
        self._rec_at = 0.0
        self._peak = 0.02
        self._bars = [0.0] * T.WAVE_BARS
        self._last_level_at = 0.0
        self._last_voice_at = 0.0
        self._silence = False
        self._position = "bottom"        # bottom | top | off
        self._last_progress = -1.0       # чтобы не дёргать QML на каждый килобайт

        self.tokens = Tokens(1.0)
        self.view = QQuickView()
        # Тот самый набор флагов. WindowDoesNotAcceptFocus обязателен: без него
        # пилюля заберёт фокус у окна, куда диктуют, и Ctrl+V уедет не туда.
        # WindowTransparentForInput - это WS_EX_TRANSPARENT: клики проходят
        # насквозь. Пилюля ничего не ловит (в Overlay.qml нет ни одной
        # MouseArea), а окно у неё с полем под тень - без этого флага оно
        # съедало клики полосой в полтораста пикселей у края экрана. Внизу это
        # над строкой состояния, сверху - ровно вкладки браузера.
        self.view.setFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                           | Qt.Tool | Qt.WindowDoesNotAcceptFocus
                           | Qt.WindowTransparentForInput)
        self.view.setColor(QColor(0, 0, 0, 0))
        self.view.setResizeMode(QQuickView.SizeViewToRootObject)
        ctx = self.view.rootContext()
        ctx.setContextProperty("T", self.tokens)
        self.view.setSource(QUrl.fromLocalFile(_qml_path()))
        if self.view.status() == QQuickView.Error:
            raise RuntimeError("; ".join(str(e) for e in self.view.errors()))
        self.root = self.view.rootObject()
        self.root.setProperty("shadowOk", _EFFECTS_OK)

        self._done_timer = QTimer()
        self._done_timer.setSingleShot(True)
        self._done_timer.timeout.connect(self.hide)

        # Тик нужен ТОЛЬКО во время записи: из Python сюда идут лишь волна и
        # таймер. Спиннер, пульс точки, фейды и морфинг ширины - это QML, они
        # крутятся на render-потоке сами и Python не будят.
        #
        # 60 fps, хотя уровни приходят ~31/с: на половине кадров новых данных
        # нет, и это норма (см. _pump_bars). Реже нельзя - секунды в таймере
        # начнут дёргаться.
        #
        # Раньше тик молотил всегда, включая скрытую пилюлю: 60 захватов GIL в
        # секунду круглые сутки. Приложение живёт в трее и 99% времени именно
        # что скрыто, а от этих захватов голодает поток слушателя keyboard - у
        # его хука 300 мс на ответ, иначе Windows роняет ввод в лаги.
        self._tick = QTimer()
        self._tick.timeout.connect(self._frame)

    # ---------- публичный API ----------

    @property
    def state(self) -> str | None:
        return self._state if self._shown else None

    def set_hint(self, text: str) -> None:
        self.root.setProperty("hint", text or "")

    def set_position(self, pos: str) -> None:
        """Где жить пилюле: bottom | top | off. «off» - совсем без неё, для
        тех, кому на экране не нужно ничего (запись и сигналы остаются)."""
        pos = pos if pos in ("bottom", "top", "off") else "bottom"
        if pos == self._position:
            return
        self._position = pos
        if pos == "off":
            self.hide()
        elif self._shown:
            self._place()

    def retheme(self) -> None:
        self.tokens.retheme()

    def show_loading(self) -> None:
        self._to(LOADING)

    def show_recording(self) -> None:
        self._rec_at = time.perf_counter()
        self._peak = 0.02
        self._bars = [0.0] * T.WAVE_BARS
        self._last_level_at = self._rec_at
        self._last_voice_at = self._rec_at
        self._set_silence(False)
        self._to(RECORDING)

    def show_processing(self) -> None:
        self._progress(-1)
        self._to(PROCESSING)

    def show_downloading(self, msg: str) -> None:
        """«Распознаю», но с полосой: у скачивания есть измеримый конец.

        Отдельным методом, а не флагом в show_processing: у распознавания
        прогресса нет и быть не может (модель не докладывает, сколько ей
        осталось), и делать вид, что есть, - враньё.
        """
        self.set_hint(msg)
        self._progress(0.0)
        self._to(PROCESSING)

    def set_progress(self, frac: float) -> None:
        """Доля 0..1. Зовётся часто - из потока скачивания, - поэтому в QML
        уходит только заметное изменение: перерисовывать пилюлю на каждый
        килобайт незачем, а GIL нужен слушателю хоткея."""
        self._progress(frac)

    def _progress(self, frac: float) -> None:
        if frac < 0:
            self._last_progress = -1.0
            self.root.setProperty("progress", -1)
            return
        frac = max(0.0, min(1.0, float(frac)))
        if abs(frac - self._last_progress) < 0.01 and frac < 1.0:
            return
        self._last_progress = frac
        self.root.setProperty("progress", frac)

    def show_done(self, msg: str = "готово") -> None:
        self._msg = msg
        self._to(DONE)
        self._done_timer.start(int(T.T_DONE_HOLD * 1000))

    def show_error(self, msg: str) -> None:
        self._msg = msg
        self._to(ERROR)
        self._done_timer.start(2200)

    def hide(self) -> None:
        self._done_timer.stop()
        self._tick.stop()
        if not self._shown:
            return
        self._shown = False
        self.root.setProperty("shown", False)
        # Прячем окно не сразу: сначала должен доиграть уход.
        QTimer.singleShot(int(T.T_DUR * 1000) + 40, self.view.hide)

    def destroy(self) -> None:
        self._tick.stop()
        self._done_timer.stop()
        self.view.hide()
        self.view.deleteLater()

    # ---------- внутреннее ----------

    def _to(self, state: str) -> None:
        self._done_timer.stop()
        self._state = state
        self.root.setProperty("state_", state)
        self.root.setProperty("message", self._msg)
        # «Скрыть» гасит индикацию записи, но НЕ ошибки: настройка называется
        # «Пилюля во время записи», а не «немой режим». Иначе у человека с
        # мёртвым микрофоном и скрытой пилюлей нажатие клавиши даёт ноль
        # обратной связи - он не узнает, что диктовка не идёт. Ошибка проходит
        # всегда и сама уходит по таймеру.
        if self._position == "off" and state != ERROR:
            self._tick.stop()
            # Прячем, а не просто выходим: показанная ошибка иначе оставалась
            # висеть, и человек, выбравший «не показывать ничего», получал
            # полноценную пилюлю на всю следующую диктовку. hide() сам
            # проверит, показано ли что-нибудь.
            self.hide()
            return
        # Тик - только под запись, остальное QML анимирует само.
        if state == RECORDING:
            self._tick.start(16)
        else:
            self._tick.stop()
        if not self._shown:
            self._shown = True
            self._place()
            self.view.show()
            self.root.setProperty("shown", True)

    def _place(self) -> None:
        """Пилюля у края активного монитора - снизу или сверху, по настройке.
        Масштаб берём у экрана - Qt знает про DPI сам, вручную его считать
        больше не надо."""
        screen = QGuiApplication.screenAt(self.view.position()) or \
            QGuiApplication.primaryScreen()
        self.tokens.set_scale(screen.devicePixelRatio())
        geo = screen.availableGeometry()
        w = self.root.width()
        h = self.root.height()
        if self._position == "top":
            # Зеркально низу: видимая капсула на том же отступе от края.
            y = geo.top() + T.PILL_BOTTOM * self.tokens.scale - T.PILL_PAD
        else:
            y = geo.bottom() - T.PILL_BOTTOM * self.tokens.scale - h + T.PILL_PAD_BOTTOM
        self.view.setGeometry(int(geo.center().x() - w / 2), int(y), int(w), int(h))

    def _frame(self) -> None:
        """Кадр. Исключения глушим: оверлей не должен ронять приложение."""
        try:
            if not self._shown:
                return
            now = time.perf_counter()
            if self._state == RECORDING:
                self._pump_bars(now)
                self.root.setProperty("bars", self._bars)
                self.root.setProperty("seconds", max(0.0, now - self._rec_at))
        except Exception:  # noqa: BLE001 - кадр пропустить не страшно, упасть - страшно
            pass

    def _pump_bars(self, now: float) -> None:
        """Свежие уровни микрофона и плавающий масштаб под голос.

        Уровни идут ~31/с, кадров 60/с: на большинстве кадров новых данных нет,
        и это норма - картинка стоит. Гасить полоски на таком кадре нельзя,
        осциллограмма схлопнётся в ниточку на живом микрофоне (в синтетическом
        превью не всплывало: там уровни генерятся на каждый вызов).

        Затухание пика привязано к числу уровней, а не к кадрам: иначе
        чувствительность зависела бы от частоты отрисовки.
        """
        levels = self.level_fn() if self.level_fn else []
        if levels:
            self._last_level_at = now
            loudest = max(levels)
            if loudest >= _SILENCE_FLOOR:
                self._last_voice_at = now
            self._peak = max(self._peak * (0.992 ** len(levels)), loudest, _FLOOR)
            for lv in levels[-T.WAVE_BARS:]:
                self._bars.append(min(1.0, (lv / self._peak) ** 0.65))
            del self._bars[:-T.WAVE_BARS]
        elif now - self._last_level_at > 0.3:
            # звука нет совсем (устройство отвалилось) - гасим, чтобы застывшая
            # картинка не выдавала себя за живую
            self._bars = [v * 0.90 for v in self._bars]
        # Голоса давно не слышно - пишем об этом на пилюле. Сходит само, как
        # только звук вернётся: заглушенную гарнитуру включают, не перезапуская
        # диктовку.
        self._set_silence(now - self._last_voice_at > _SILENCE_SEC)

    def _set_silence(self, value: bool) -> None:
        if value != self._silence:
            self._silence = value
            self.root.setProperty("silence", value)


def _qml_path() -> str:
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "qml", "Overlay.qml")
