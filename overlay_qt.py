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
from theme_qt import Tokens, effects_ok

# Windows: попадание мыши в окно. HTTRANSPARENT - «меня здесь нет, отдайте
# клик тому, кто ниже»; ровно этим окно пилюли и притворяется везде, кроме
# самой капсулы (см. Overlay._install_hit_filter).
_WM_NCHITTEST = 0x0084
_HTTRANSPARENT = -1
_HTCLIENT = 1


class _MSG(ctypes.Structure):
    """MSG из windows.h - ровно те поля, что нам нужны, в том же порядке."""

    _fields_ = [("hWnd", ctypes.c_void_p),
                ("message", ctypes.c_uint),
                ("wParam", ctypes.c_size_t),
                ("lParam", ctypes.c_ssize_t),
                ("time", ctypes.c_uint),
                ("pt_x", ctypes.c_long),
                ("pt_y", ctypes.c_long)]


# Подъём Qt6QuickEffects.dll переехал в theme_qt.effects_ok() - тень нужна уже
# двоим (пилюле и карточкам окна настроек), а грабли и лечение у них общие.
_EFFECTS_OK = effects_ok()

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

    _hit_filter = None                   # держим ссылку: Qt её не удерживает

    def __init__(self, level_fn=None) -> None:
        super().__init__()
        self.level_fn = level_fn
        self._state: str | None = None
        self._shown = False
        self._msg = ""
        self._peak = 0.02
        self._bars = [0.0] * T.WAVE_BARS
        self._last_level_at = 0.0
        self._last_voice_at = 0.0
        self._silence = False
        self._position = "bottom"        # bottom | top | off
        self._last_progress = -1.0       # чтобы не дёргать QML на каждый килобайт
        self._hwnd = 0                   # окно пилюли, кэш; см. _install_hit_filter

        self.tokens = Tokens(1.0)
        self.view = QQuickView()
        # Тот самый набор флагов. WindowDoesNotAcceptFocus обязателен: без него
        # пилюля заберёт фокус у окна, куда диктуют, и Ctrl+V уедет не туда.
        # WindowTransparentForInput (это WS_EX_TRANSPARENT) здесь БОЛЬШЕ НЕТ.
        # Он выключал мышь для всего окна, а окно у пилюли заметно больше
        # капсулы: вокруг лежит поле под тень, полтораста пикселей у края
        # экрана - внизу над строкой состояния, сверху ровно по вкладкам
        # браузера. Без флага это поле съедало чужие клики, с флагом нельзя
        # схватить и саму пилюлю, а владелец попросил её перетаскивать.
        # Вместо флага - точечная прозрачность по попаданию, _install_hit_filter.
        self.view.setFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                           | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.view.setColor(QColor(0, 0, 0, 0))
        self.view.setResizeMode(QQuickView.SizeViewToRootObject)
        ctx = self.view.rootContext()
        ctx.setContextProperty("T", self.tokens)
        from theme_qt import Lang

        self.lang = Lang()
        ctx.setContextProperty("L", self.lang)
        self.view.setSource(QUrl.fromLocalFile(_qml_path()))
        if self.view.status() == QQuickView.Error:
            raise RuntimeError("; ".join(str(e) for e in self.view.errors()))
        self.root = self.view.rootObject()
        self.root.setProperty("shadowOk", _EFFECTS_OK)
        # Перетаскивание: QML говорит, на сколько сдвинуть, двигаем мы. Границы
        # экрана знает Qt, а не QML, поэтому и прижимает к краю эта сторона.
        self.root.dragged.connect(self._drag_by)
        self.root.dragReset.connect(self._drag_reset)
        # Своё место, если пилюлю утащили. None - стоит там, где велит настройка.
        self._custom: tuple[int, int] | None = None
        self._save_pos = None            # чем сохранить положение в конфиг
        self._install_hit_filter()

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

    def _install_hit_filter(self) -> None:
        """Сделать окно прозрачным для мыши везде, кроме капсулы.

        У Windows для этого есть штатный ответ: на WM_NCHITTEST окно говорит
        HTTRANSPARENT - «меня в этой точке нет», и система отдаёт клик тому,
        кто под нами. Отвечаем так везде, кроме прямоугольника капсулы, который
        QML отдаёт свойством `capsule`.

        Не встал фильтр - возвращаем прежний флаг на всё окно: пилюля останется
        неперетаскиваемой, но чужие клики съедать не начнёт. Косметика не имеет
        права ронять диктовку.
        """
        try:
            from PySide6.QtCore import QAbstractNativeEventFilter
            from PySide6.QtGui import QGuiApplication as _App

            overlay = self

            class _HitFilter(QAbstractNativeEventFilter):
                def nativeEventFilter(self, kind, message):
                    try:
                        if bytes(kind) != b"windows_generic_MSG":
                            return False, 0
                        msg = ctypes.cast(int(message),
                                          ctypes.POINTER(_MSG)).contents
                        if msg.message != _WM_NCHITTEST:
                            return False, 0
                        # Своё окно узнаём по числу, спрошенному один раз.
                        # Кэш безопасен: HWND выдаётся окну при создании и
                        # держится до его закрытия - за жизнь окна он не
                        # меняется, и устареть тут нечему.
                        #
                        # А спрашивать заново дорого именно здесь. Фильтр
                        # висит на всём приложении, и WM_NCHITTEST прилетает
                        # на КАЖДОЕ движение мыши над любым нашим окном -
                        # то есть сотнями в секунду, пока человек просто
                        # ведёт курсор. Вызов winId() на каждое из них - это
                        # заход в Qt из-под фильтра ради числа, которое мы
                        # уже знаем.
                        if not overlay._hwnd:
                            overlay._hwnd = int(overlay.view.winId())
                        if msg.hWnd != overlay._hwnd:
                            return False, 0
                        return overlay._hit(msg.lParam)
                    except Exception:  # noqa: BLE001 - фильтр висит на всех
                        return False, 0   # сообщениях процесса, падать нельзя

            Overlay._hit_filter = _HitFilter()
            _App.instance().installNativeEventFilter(Overlay._hit_filter)
        except Exception as e:  # noqa: BLE001
            self.view.setFlags(self.view.flags() | Qt.WindowTransparentForInput)
            print(f"пилюля: фильтр попаданий не встал ({e}) - без перетаскивания")

    def _hit(self, lparam: int) -> tuple:
        """Ответ на WM_NCHITTEST: попала мышь в капсулу или мимо неё."""
        # lParam - две 16-битные координаты ЭКРАНА со знаком.
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        cap = self.root.property("capsule")
        if cap is None:
            return True, _HTTRANSPARENT
        pos = self.view.position()
        left = pos.x() + cap.x()
        top = pos.y() + cap.y()
        inside = (left <= x <= left + cap.width()
                  and top <= y <= top + cap.height())
        return True, (_HTCLIENT if inside else _HTTRANSPARENT)

    @staticmethod
    def _clamp(x: float, y: float, w: float, h: float, geo) -> tuple:
        """Не дать утащить пилюлю за край экрана.

        Оставляем видимой хотя бы четверть окна: пилюля маленькая, и уехавшую
        целиком за край нечем было бы вернуть, кроме правки конфига руками.
        """
        keep = w / 4
        x = max(geo.left() - w + keep, min(geo.right() - keep, x))
        y = max(geo.top(), min(geo.bottom() - h / 4, y))
        return int(x), int(y)

    def _drag_by(self, dx: float, dy: float) -> None:
        """Сдвинуть окно пилюли на столько, на сколько уехала мышь."""
        screen = QGuiApplication.screenAt(self.view.position()) or \
            QGuiApplication.primaryScreen()
        pos = self.view.position()
        x, y = self._clamp(pos.x() + dx, pos.y() + dy,
                           self.root.width(), self.root.height(),
                           screen.availableGeometry())
        self._custom = (x, y)
        self.view.setPosition(x, y)
        if self._save_pos is not None:
            self._save_pos(x, y)

    def _drag_reset(self) -> None:
        """Двойной клик - вернуть пилюлю на штатное место."""
        self._custom = None
        if self._save_pos is not None:
            self._save_pos(None, None)
        self._place()

    def set_custom_pos(self, x, y, save=None) -> None:
        """Место из конфига плюс чем его сохранять. Зовёт app при старте."""
        self._save_pos = save
        self._custom = ((int(x), int(y))
                        if x is not None and y is not None else None)

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
        self._peak = 0.02
        self._bars = [0.0] * T.WAVE_BARS
        now = time.perf_counter()
        self._last_level_at = now
        self._last_voice_at = now
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
        # Утащили мышью - слушаемся нового места, а не настройки: возвращать
        # пилюлю на «своё» при каждом показе значило бы отменять решение
        # человека по десять раз на дню.
        if self._custom is not None:
            x, y = self._clamp(self._custom[0], self._custom[1], w, h, geo)
            self.view.setGeometry(x, y, int(w), int(h))
            return
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
    return os.path.join(base, "qml", "windows", "Overlay.qml")
