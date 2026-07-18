"""FlowLocal - приватный локальный аналог Wispr Flow для Windows.

Зажал хоткей - говоришь, отпустил - текст вставился в активное окно.
Всё локально: GigaAM v3 через onnx-asr, на процессоре, никакого облака.

Запуск:            pythonw app.py        (без консоли)
Отладка:           python app.py
Автозапуск:        python app.py --autostart on | off

Архитектура потоков:
  main            - Qt: оверлей, окно настроек, трей, очередь UI-команд
  keyboard hook   - press/release хоткея (поток библиотеки keyboard)
  worker          - распознавание + вставка, по одному на фразу
                    (сериализованы _work_lock: иначе две быстрые фразы
                    вставились бы в обратном порядке)

Из чужих потоков к Qt обращаться нельзя, поэтому всё, что трогает оверлей и
окно настроек, идёт через app.ui(fn) - сигналом в главный поток.

Интерфейс переехал с tkinter на Qt/QML (PLAN, этапы 6-7). Вместе с ним ушли:
layered-окно с попиксельной альфой (Qt даёт WS_EX_NOACTIVATE флагом
WindowDoesNotAcceptFocus - проверено tools/probe_qt_overlay.py), контролы,
рисованные в PIL, и pystray со своим потоком.
"""

import ctypes
import json
import os
import sys
import threading
import time


class _NullStream:
    """Заглушка для sys.stdout/sys.stderr, когда их нет.

    У приложения без консоли (собранный .exe с windowed=True, а также pythonw)
    sys.stdout и sys.stderr равны None. Наш print это переживает - он молча
    ничего не делает. А чужая библиотека - нет.

    Дорого добытое, найдено на собранной сборке при первом запуске: модель
    качает huggingface_hub, он рисует прогресс-бар через tqdm, tqdm делает
    sys.stderr.write() - и приложение умирает с «'NoneType' object has no
    attribute 'write'». В разработке этого не увидеть: модель уже лежит на
    диске, скачивать нечего. То есть падало ровно у того, у кого запуск первый,
    - у нового человека, и только у него.

    Затыкаем в самом начале, до любых импортов, которые могут писать в вывод.
    """

    def write(self, _s):
        return 0

    def flush(self):
        pass

    def isatty(self):
        return False

    def fileno(self):
        raise OSError("нет файлового дескриптора")


if sys.stdout is None:
    sys.stdout = _NullStream()
if sys.stderr is None:
    sys.stderr = _NullStream()

# Рабочая папка - та, где живут конфиг, лог, история и модель. Своим
# os.path.dirname(__file__) тут не обойтись: в собранном .exe он указывает во
# временную распаковку, которая исчезает при выходе. app_paths это уже знает.
import app_paths  # noqa: E402
from app_paths import (APP_DIR, CONFIG_PATH, HISTORY_PATH,  # noqa: E402
                       LOG_PATH, set_autostart)

os.chdir(APP_DIR)

# DPI: раньше здесь стоял layered.set_dpi_awareness() - вручную, до первого
# окна, иначе Windows отдавала растянутый мыльный интерфейс. Qt объявляет
# per-monitor v2 сам при создании QApplication, и делать это руками теперь
# нельзя: два объявления конфликтуют.
#
# layered.py целиком пока не уходит: в нём остался foreground_process() - имя
# exe активного окна для правил тона. Окно с попиксельной альфой оттуда больше
# не нужно (его заменил Qt), но win32-хвост живёт до этапа 11 (platform/).
import layered  # noqa: E402
import keyboard  # noqa: E402
from PySide6.QtCore import QObject, QTimer, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import config as C  # noqa: E402
import inputspec  # noqa: E402
import models  # noqa: E402
import overlay_qt as OV  # noqa: E402
import theme as T  # noqa: E402
import updater  # noqa: E402
from version import __version__  # noqa: E402
import cleaner  # noqa: E402
from cleaner import _strip_fillers, clean, extract_commands, llm_command  # noqa: E402
from inserter import (_set_clipboard_text, backspace,  # noqa: E402
                      copy_selection, insert, press_enter)
from overlay_qt import Overlay  # noqa: E402
from recorder import Recorder  # noqa: E402
from transcriber import Transcriber  # noqa: E402
from util import plural  # noqa: E402

LOG_MAX = 512 * 1024
# История - это уже не отладка, а данные: из неё считается статистика, и
# терять её обиднее, чем лог. Поэтому порог выше, но он всё равно нужен: окно
# настроек и статистика читают файл целиком, а за год плотной диктовки он
# вырастет в десятки мегабайт.
HISTORY_MAX = 4 * 1024 * 1024


# Как часто перепроверять обновления, пока приложение висит в трее.
# Шесть часов: релиз выходит не чаще, а узнать о нём в тот же день - достаточно.
_UPDATE_EVERY = 6 * 60 * 60 * 1000


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
    try:
        # лог крутится вечно в фоне - без ротации он растёт до бесконечности
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > LOG_MAX:
            os.replace(LOG_PATH, LOG_PATH + ".1")
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass
    print(line, end="")   # под pythonw sys.stdout = None, print молча ничего не делает


def die(msg: str) -> None:
    """Фатальная ошибка так, чтобы её увидели: под pythonw консоли нет и
    traceback уходит в никуда."""
    log(f"FATAL: {msg}")
    try:
        ctypes.windll.user32.MessageBoxW(None, str(msg), "FlowLocal", 0x10)
    except Exception:  # noqa: BLE001
        pass


def beep(freq: int, dur: int, enabled: bool) -> None:
    if not enabled:
        return
    import winsound

    threading.Thread(target=winsound.Beep, args=(freq, dur), daemon=True).start()


class _UiBridge(QObject):
    """Переброс вызова в главный поток. Живёт отдельным QObject, потому что
    сигналы бывают только у QObject, а App им быть незачем."""

    invoke = Signal(object, tuple)


class App:
    def __init__(self) -> None:
        self.cfg = C.load()
        # Тему ставим до первого окна и до первой картинки: краски читаются в
        # момент отрисовки, но иконка трея кэшируется, а окно настроек
        # запоминает фон канвы при создании.
        T.set_theme(str(self.cfg.get("theme") or "system"))
        # QApplication, а не QGuiApplication: QSystemTrayIcon и QMenu живут в
        # QtWidgets. Окна при этом остаются на QML.
        self.qapp = QApplication(sys.argv)
        # Иначе закрытие окна настроек убило бы всё приложение: у нас нет
        # «главного окна», мы живём в трее.
        self.qapp.setQuitOnLastWindowClosed(False)
        T.register_fonts()
        self._bridge = _UiBridge()
        self._bridge.invoke.connect(self._run_ui)
        self.recorder = self._make_recorder()
        # level_fn читает self.recorder лениво: микрофон пересоздаётся при
        # смене устройства в настройках, а оверлей должен видеть новый
        self.overlay = Overlay(level_fn=lambda: self.recorder.drain_levels())
        self.overlay.set_position(str(self.cfg.get("overlay_position") or "bottom"))
        self.transcriber = Transcriber(self.cfg, log)
        self.settings = None
        self.onboarding = None
        self.tray = None
        self._recording = False
        self._rec_started_at = 0.0
        self._rec_mode = "hold"        # каким биндом начата текущая запись
        self._held = {"hold": False, "toggle": False, "command": False}
        self._mouse_binds: list[tuple[str, tuple, str]] = []
        self._mouse_listener = None
        self._work_lock = threading.Lock()
        self._ready = False
        self._llm_note = ""          # модель Ollama, найденная автоопределением
        self._update: dict | None = None   # свежая версия с GitHub, если нашлась
        self._hk_handles: list = []
        self._hook_handles: list = []
        self._capturing = False
        self._tray_state = "load"
        # Отмена последней вставки: помним текст и «мы всё ещё последние, кто
        # писал в это поле». См. _undo_last и _watch_typing.
        self._undo_text: str | None = None
        self._undo_armed = False
        self._undo_mods: set[str] = set()
        self._undo_trigger = ""
        self._inserting = False

    def _make_recorder(self) -> Recorder:
        dev = self.cfg.get("mic_device")
        try:
            return Recorder(
                pre_buffer_sec=float(self.cfg.get("pre_buffer_sec", 0.5)),
                keep_open=bool(self.cfg.get("keep_mic_open", True)),
                device=dev,
            )
        except Exception as e:  # noqa: BLE001 - без микрофона стартуем, откроем при нажатии
            log(f"mic not available at start: {e}")
            return Recorder(
                pre_buffer_sec=float(self.cfg.get("pre_buffer_sec", 0.5)),
                keep_open=False,
                device=dev,
            )

    # ---------- UI-очередь: все обращения к Qt только отсюда ----------

    def ui(self, fn, *args) -> None:
        """Выполнить fn в главном потоке. Звать откуда угодно.

        Сигналом, а не опросом очереди по таймеру: у сигнала с авто-соединением
        вызов из чужого потока кладётся в очередь событий получателя и будит
        главный поток ровно тогда, когда есть работа. Раньше здесь тикал
        root.after(30) - 33 холостых пробуждения в секунду круглые сутки на
        приложении, которое почти всё время просто висит в трее.
        """
        self._bridge.invoke.emit(fn, args)

    def _run_ui(self, fn, args) -> None:
        try:
            fn(*args)
        except Exception as e:  # noqa: BLE001 - кривой колбэк не должен ронять приложение
            log(f"ui error: {e}")

    # ---------- хоткеи ----------
    # Два НЕЗАВИСИМЫХ бинда, каждый со своим сочетанием (config hotkey_hold и
    # hotkey_toggle). Не переключатель режима у одного хоткея: человек может
    # держать оба сразу и выбирать жест по ситуации.
    #   hold   - нажал = старт, отпустил = стоп.
    #   toggle - нажал = старт, нажал ещё раз = стоп, Esc = отмена.
    # Любой из них может быть и кнопкой мыши («ctrl+mouse4») - разбор в
    # inputspec.py, ловля в _on_mouse.
    #
    # Клавиатура. Одна клавиша: press/release ловятся напрямую. Комбинация:
    # add_hotkey на нажатие, отпускание ЛЮБОЙ её клавиши - на release-хуки.
    #
    # _held[mode] взводится на нажатии и снимается на отпускании, и делает
    # сразу два дела:
    #   1) гасит автоповтор: зажатое сочетание дёргает add_hotkey десятки раз
    #      в секунду, и toggle мигал бы старт-стоп-старт;
    #   2) помнит, что старт был именно от этого бинда - иначе отпускание
    #      постороннего хоткея (или кнопки мыши, нажатой без модификаторов)
    #      останавливало бы чужую запись.

    _GENERIC_KEYS = {
        "ctrl": ("left ctrl", "right ctrl"),
        "shift": ("left shift", "right shift"),
        "alt": ("left alt", "right alt"),
        "win": ("left windows", "right windows"),
        "windows": ("left windows", "right windows"),
    }
    # Все физические имена модификаторов - по ним _watch_typing понимает, что
    # нажатие само по себе не «печатал человек».
    _MOD_NAMES = frozenset(
        {"ctrl", "shift", "alt", "win", "windows", "alt gr", "right alt"}
        | {n for names in _GENERIC_KEYS.values() for n in names})

    def _hotkey_bind(self) -> None:
        self._hotkey_unbind()
        for mode in ("hold", "toggle", "command"):
            spec = str(self.cfg.get(f"hotkey_{mode}") or "").strip()
            if not spec:
                continue
            try:
                self._bind_dictation(mode, spec)
            except (ValueError, KeyError) as e:
                # Битое имя не должно оставить приложение немым. Откатываем
                # ТОЛЬКО этот бинд и только hold: он основной, а у toggle
                # умолчание пустое - возвращать нечего.
                log(f"bad hotkey_{mode} {spec!r}: {e}")
                fallback = C.DEFAULTS.get(f"hotkey_{mode}") or ""
                if not fallback:
                    continue
                try:
                    self._bind_dictation(mode, fallback)
                    self.cfg[f"hotkey_{mode}"] = fallback
                    self.ui(self.overlay.show_error, f"сочетание {spec} не распознано")
                except (ValueError, KeyError) as e2:
                    log(f"fallback hotkey_{mode} failed too: {e2}")
        if str(self.cfg.get("hotkey_toggle") or "").strip():
            # Esc отменяет начатую запись. Хук висит, пока есть бинд-переключатель,
            # а не вешается на старте записи: добавлять хук из колбэка самой
            # keyboard - напрашиваться на неприятности.
            self._hook_handles.append(
                keyboard.on_press_key("esc", self._esc, suppress=False))
        log(f"hotkeys: hold={self.cfg.get('hotkey_hold')!r} "
            f"toggle={self.cfg.get('hotkey_toggle')!r}")
        self._bind_undo()

    def _bind_dictation(self, mode: str, spec: str) -> None:
        mods, key, mouse_btn = inputspec.parse(spec)
        if mouse_btn:
            self._bind_mouse(mode, mods, mouse_btn)
            return
        if not key:
            # одни модификаторы: «right ctrl» как хоткей - клавиша тут сама и
            # есть модификатор, вешаемся на её физическое имя
            key = spec.strip().lower()
            mods = []
        if mods:
            hk = inputspec.build(mods, key)
            self._hk_handles.append(keyboard.add_hotkey(
                hk, lambda m=mode: self._dictation_press(m), suppress=False))
            release_keys: set[str] = set()
            for part in mods:
                release_keys.update(self._GENERIC_KEYS.get(part, (part,)))
            release_keys.add(key)
            for name in release_keys:
                self._hook_handles.append(keyboard.on_release_key(
                    name, lambda _e, m=mode: self._dictation_release(m),
                    suppress=False))
        else:
            self._hook_handles.append(keyboard.on_press_key(
                key, lambda _e, m=mode: self._dictation_press(m), suppress=False))
            self._hook_handles.append(keyboard.on_release_key(
                key, lambda _e, m=mode: self._dictation_release(m), suppress=False))

    # Сообщения WH_MOUSE_LL, которые нас касаются. Левую и правую кнопки не
    # ловим вовсе: ими человек кликает по интерфейсу, и биндить их - значит
    # сделать мышь неуправляемой.
    _WM_XDOWN, _WM_XUP = 0x020B, 0x020C
    _WM_MDOWN, _WM_MUP = 0x0207, 0x0208

    def _bind_mouse(self, mode: str, mods: list, button: str) -> None:
        """Бинд на кнопку мыши. Модификаторы проверяем в момент нажатия:
        слушатель мыши про клавиатуру не знает, а keyboard - про мышь.

        Ловим и ГЛОТАЕМ через pynput, а не библиотекой mouse: та подавлять не
        умеет вовсе, и кнопка долетала до чужого окна. Для X1 это не мелочь -
        в Chromium и Electron X1 значит «Назад». Симптом был такой: диктуешь,
        жмёшь ctrl+mouse4 ради второй диктовки, приложение уходит назад, поле
        очищается, и вторая фраза ложится в пустое. Снаружи - «прошлое
        стирается полностью».
        """
        from pynput import mouse as pmouse

        if mods:
            self._wake_keyboard_listener()
        self._mouse_binds.append((mode, tuple(mods), button))
        if self._mouse_listener is None:
            # Колбэки on_click не используем намеренно: suppress_event() глушит
            # событие целиком, вместе с ними (проверено
            # tools/probe_mouse_suppress.py). Вся работа - в фильтре.
            self._mouse_listener = pmouse.Listener(win32_event_filter=self._mouse_filter)
            self._mouse_listener.start()

    def _mouse_filter(self, msg, data) -> None:
        """Фильтр WH_MOUSE_LL. Исполняется ВНУТРИ хука, где у нас 300 мс на всё:
        поэтому здесь только решение, а сама работа уходит в главный поток
        через self.ui().

        Ловушка: suppress_event() ПОДАВЛЯЕТ СОБЫТИЕ ИСКЛЮЧЕНИЕМ - так устроен
        pynput. Ловить его нельзя: свой `except Exception` здесь молча съест
        подавление, и кнопка снова полетит в чужое окно. Поэтому решение
        принимаем в защищённом блоке, а глотаем - за его пределами.
        """
        act = None
        try:
            if msg in (self._WM_XDOWN, self._WM_XUP):
                # старшее слово mouseData: 1 = X1, 2 = X2
                btn = "x" if (data.mouseData >> 16) == 1 else "x2"
                down = msg == self._WM_XDOWN
            elif msg in (self._WM_MDOWN, self._WM_MUP):
                btn, down = "middle", msg == self._WM_MDOWN
            else:
                return
            for mode, mods, button in self._mouse_binds:
                if button != btn:
                    continue
                if down:
                    # Нажатие без нужных модификаторов - не наш жест: пропускаем
                    # дальше и _held не взводим, поэтому отпускание тоже пройдёт
                    # мимо.
                    if self._mods_held(mods):
                        act = (self._dictation_press, mode, True)
                else:
                    # Отпускание глотаем только если нажатие было наше: иначе
                    # чужой клик остался бы без своего UP.
                    act = (self._dictation_release, mode, self._held.get(mode, False))
                break
        except Exception as e:  # noqa: BLE001 - падение в хуке роняет весь ввод
            log(f"mouse filter error: {e}")
            return
        if act is None:
            return
        fn, mode, swallow = act
        self.ui(fn, mode)
        if swallow:
            self._mouse_listener.suppress_event()   # бросает - и это норма

    @staticmethod
    def _wake_keyboard_listener() -> None:
        """Поднять слушателя keyboard заранее, в своём потоке.

        Дорого добытое (симптом: «ctrl+mouse4 не срабатывает, и Ctrl лагает»).
        keyboard.is_pressed() читает состояние клавиш из _pressed_events, а
        наполняет их слушатель, который поднимается ЛЕНИВО - первым же вызовом
        is_pressed. Пока в конфиге есть хоть один клавиатурный бинд, слушатель
        встаёт на старте, и никто не замечает. Но если бинд только мышиный
        (hold пуст, undo пуст), первым вызовом оказывается наш - из колбэка
        библиотеки mouse. И тогда:

        1. _pressed_events в этот момент ПУСТ. Модификатор человек зажал ДО
           старта слушателя, события его нажатия слушатель не видел, и
           is_pressed('ctrl') честно отвечает False. Бинд не срабатывает - и
           не сработает, пока Ctrl не отпустят и не нажмут заново.
        2. WH_KEYBOARD_LL ставится изнутри колбэка WH_MOUSE_LL, а у него 300 мс
           на ответ (LowLevelHooksTimeout). Windows такого не прощает: весь
           ввод в системе начинает лагать.

        Приватный _listener - не от хорошей жизни: публичного способа поднять
        слушателя, не повесив хук, у keyboard нет, а лишний хук на каждое
        нажатие - это Python-колбэк на каждую клавишу в системе, то есть та же
        задержка, только всегда.
        """
        try:
            keyboard._listener.start_if_necessary()  # noqa: SLF001
        except Exception as e:  # noqa: BLE001 - без этого бинд просто сработает со второго раза
            log(f"keyboard listener warmup failed: {e}")

    @staticmethod
    def _mods_held(mods) -> bool:
        try:
            return all(keyboard.is_pressed(m) for m in mods)
        except Exception:  # noqa: BLE001 - is_pressed изредка кидает на экзотике
            return False

    def _bind_undo(self) -> None:
        """Хоткей отмены - отдельно от диктовки.

        Его может не быть вовсе (пустая строка = выключено), и битое имя в
        конфиге не должно откатывать на умолчание хоткей диктовки: это разные
        настройки, и падать вместе им незачем.
        """
        self._undo_mods = set()
        self._undo_trigger = ""
        undo = str(self.cfg.get("undo_hotkey") or "").strip()
        if not undo:
            return
        try:
            self._hk_handles.append(
                keyboard.add_hotkey(undo, self._undo_last, suppress=False))
        except (ValueError, KeyError) as e:
            log(f"bad undo hotkey {undo!r}: {e}")
            return
        # Разбираем сочетание на модификаторы и триггер-клавишу. Триггер держим
        # отдельно от _MOD_NAMES: он-то и есть та клавиша, нажатие которой без
        # модификаторов означает «человек печатает», а с модификаторами - «это
        # сам жест отмены». Раньше триггер попадал в общий список исключений, и
        # набор слова с этой буквой (напр. латинской z) не снимал отмену -
        # следующая отмена стирала уже не диктовку, а то, что человек напечатал.
        for part in (p.strip() for p in undo.split("+") if p.strip()):
            if part in self._GENERIC_KEYS:
                self._undo_mods.add(part)
            else:
                self._undo_trigger = part
        self._hook_handles.append(keyboard.hook(self._watch_typing))
        log(f"undo hotkey: {undo}")

    def _hotkey_unbind(self) -> None:
        # снимаем поимённо, а не unhook_all: unhook_all снёс бы и временный
        # хук захвата хоткея в окне настроек
        for h in self._hk_handles:
            try:
                keyboard.remove_hotkey(h)
            except (KeyError, ValueError):
                pass
        for h in self._hook_handles:
            try:
                keyboard.unhook(h)
            except (KeyError, ValueError):
                pass
        self._hk_handles.clear()
        self._hook_handles.clear()
        if self._mouse_listener is not None:
            try:
                self._mouse_listener.stop()
            except Exception:  # noqa: BLE001 - слушатель мог уже умереть
                pass
            self._mouse_listener = None
        self._mouse_binds.clear()
        self._held = {"hold": False, "toggle": False, "command": False}

    def _dictation_press(self, mode: str) -> None:
        if self._held.get(mode):      # автоповтор зажатого сочетания
            return
        self._held[mode] = True
        if mode == "toggle":
            if self._recording and self._rec_mode == "toggle":
                self._finish_recording()
            elif not self._recording:
                self._start_recording("toggle")
            # идёт запись от удержания - не перехватываем её переключателем
        else:
            # command держится и отпускается так же, как hold: разница не в
            # жесте, а в том, что делать с распознанным (см. _finish_recording).
            self._start_recording(mode)

    def _dictation_release(self, mode: str) -> None:
        # не взводились - значит и старта от нас не было: чужую запись не трогаем
        if not self._held.get(mode):
            return
        self._held[mode] = False
        if mode in ("hold", "command") and self._recording and self._rec_mode == mode:
            self._finish_recording()

    def _esc(self, _e) -> None:
        if self._recording and self._rec_mode == "toggle":
            self._cancel_recording()

    # ---------- запись ----------

    def _start_recording(self, mode: str = "hold") -> None:
        if self._capturing or self._recording:
            return
        self._rec_mode = mode
        if not self._ready:
            # раньше нажатие до загрузки модели молча игнорировалось, и
            # человек говорил в пустоту - теперь честно показываем, что грузимся
            self.ui(self.overlay.show_loading)
            return
        self._recording = True
        self._rec_started_at = time.time()
        try:
            self.recorder.start()
        except Exception as e:  # noqa: BLE001
            log(f"mic error: {e}")
            self._recording = False
            self.ui(self.overlay.show_error, "микрофон недоступен")
            return
        beep(880, 60, self.cfg.get("sounds", True))
        if self.recorder.fell_back:
            # Выбранный микрофон умер, пишем с системного. Запись при этом
            # идёт, то есть это не отказ, а мелочь - и на пилюле ей больше не
            # место (переделка 18.07.2026: подписи оттуда ушли). Лог остаётся.
            log("mic fell back to default device")
        # Пилюля показывает состояние, а не инструкцию: подсказка «ещё раз -
        # стоп · Esc - отмена» висела каждую диктовку, а прочитать её нужно
        # один раз. Она есть на странице «Диктовка», рядом с самим сочетанием.
        self.ui(self.overlay.set_hint, "")
        self.ui(self.overlay.show_recording)
        self._set_tray_state("rec")

    def _finish_recording(self) -> None:
        if not self._recording:
            return
        self._recording = False
        audio = self.recorder.stop()
        dur = time.time() - self._rec_started_at
        beep(660, 60, self.cfg.get("sounds", True))
        if dur < float(self.cfg.get("min_record_sec", 0.3)) or audio.size == 0:
            self.ui(self.overlay.hide)
            self._set_tray_state("idle")
            return
        # hint - канал только для скачивания обновления, но чистим на всякий:
        # прошлый заход мог его выставить, а показывать «обновление 0.3.1» под
        # распознавание фразы нельзя.
        self.ui(self.overlay.set_hint, "")
        self.ui(self.overlay.show_processing)
        self._set_tray_state("proc")
        if self._rec_mode == "command":
            # Команду в «Повторить последнюю» не кладём: повтор вслепую прогнал
            # бы правку ещё раз - по другому выделению или вовсе без него.
            threading.Thread(target=self._process_command, args=(audio,),
                             daemon=True).start()
            return
        # Запись держим до следующей: если распознавание или вставка упадут,
        # фраза не потеряна - «Повторить последнюю» в трее прогонит её заново.
        # Память дешёвая: минута речи в float32 - ~4 МБ.
        self._last_audio, self._last_dur = audio, dur
        threading.Thread(target=self._process, args=(audio, dur), daemon=True).start()

    def _process_command(self, audio) -> None:
        """Command mode: выделил текст, сказал что сделать - выделенное заменилось.

        Порядок шагов не случаен. Выделение забираем ПЕРВЫМ, до распознавания:
        человек только отпустил хоткей и ещё стоит в своём документе, а на
        распознавание уходит секунда - за неё он успеет кликнуть куда угодно, и
        Ctrl+C уедет в чужое окно.

        Отдельный риск, которого нет у диктовки: мы вставляем ПОВЕРХ выделения,
        то есть стираем его. Поэтому на каждом сомнении - выходим, ничего не
        тронув. Вставить сюда мусор - значит уничтожить кусок чужого документа,
        а Ctrl+Z у каждого приложения свой, и вернуть мы не поможем.
        """
        try:
            with self._work_lock:
                llm = self.cfg.get("llm") or {}
                if not llm.get("enabled"):
                    log("command: полировка выключена, править нечем")
                    self.ui(self.overlay.show_error, "нужна Ollama")
                    return

                self._inserting = True
                try:
                    sel, old_clip = copy_selection()
                finally:
                    self._insert_window_closes()
                if not sel or not sel.strip():
                    log("command: ничего не выделено")
                    self.ui(self.overlay.show_error, "ничего не выделено")
                    return

                instruction = self.transcriber.transcribe(audio)
                # Паразитов из указания убираем, а полировку LLM не зовём: это
                # был бы второй проход модели ради фразы в три слова, и лишняя
                # секунда к задержке.
                instruction = _strip_fillers(instruction)
                if not instruction.strip():
                    log("command: указание пустое")
                    self.ui(self.overlay.show_error, "не расслышал команду")
                    return
                log(f"command: {instruction!r} над {len(sel)} символами")

                t0 = time.time()
                result = llm_command(sel, instruction, llm, log)
                if not result:
                    self.ui(self.overlay.show_error, "не смог выполнить")
                    return

                self._inserting = True
                try:
                    # restore=False: insert вернул бы в буфер выделение, которое
                    # сам же туда и положил Ctrl+C. Прежний буфер человека
                    # возвращаем ниже, сами.
                    ok = insert(result, mode=self.cfg.get("insert_mode", "paste"),
                                restore=False)
                finally:
                    self._insert_window_closes()
                if self.cfg.get("restore_clipboard", True) and old_clip is not None:
                    time.sleep(0.3)      # дать окну забрать вставленное
                    _set_clipboard_text(old_clip)

                # Отмену НЕ взводим намеренно. Она стирает вставленное
                # Backspace'ом, а вернуть выделение, поверх которого мы
                # вставили, ей нечем: получилась бы дыра вместо текста.
                self._undo_text, self._undo_armed = None, False

            if ok:
                log(f"command ok: {len(sel)} -> {len(result)} символов "
                    f"за {time.time() - t0:.2f}с")
                self.ui(self.overlay.show_done, "готово")
            else:
                self.ui(self.overlay.show_error, "не удалось вставить")
        except Exception as e:  # noqa: BLE001
            log(f"command error: {e}")
            self.ui(self.overlay.show_error, "ошибка команды")
        finally:
            self._set_tray_state("idle")

    def _retry_last(self) -> None:
        """Прогнать последнюю запись заново - аналог retry у Wispr Flow.

        Спасает в двух случаях: вставка ушла не в то окно (человек успел
        кликнуть) и «не удалось вставить»/«ошибка распознавания». Звук уже
        записан - переговаривать не надо, достаточно встать в нужное поле.
        """
        audio = getattr(self, "_last_audio", None)
        if audio is None or not self._ready or self._recording:
            return
        # hint переживает отмену записи, а на пилюле он занимает место надписи
        # про обновление - и повтор после Esc показывал бы её вместо ничего.
        self.ui(self.overlay.set_hint, "")
        self.ui(self.overlay.show_processing)
        self._set_tray_state("proc")
        threading.Thread(target=self._process,
                         args=(audio, getattr(self, "_last_dur", 0.0)),
                         daemon=True).start()

    def _cancel_recording(self) -> None:
        """Передумал: запись выбрасывается, ничего не распознаётся и не вставляется.

        Нужна только переключателю. В режиме удержания «передумал» - это просто
        отпустить клавишу, не начав говорить: короткое нажатие и так отсекается
        по min_record_sec.
        """
        if not self._recording:
            return
        self._recording = False
        try:
            self.recorder.stop()
        except Exception as e:  # noqa: BLE001 - отмена не должна падать
            log(f"mic stop on cancel: {e}")
        beep(440, 80, self.cfg.get("sounds", True))
        self.ui(self.overlay.hide)
        self._set_tray_state("idle")
        log("recording cancelled")

    def _process(self, audio, dur: float) -> None:
        try:
            # лок держим на весь конвейер, включая вставку: если распознать
            # вторую фразу, пока вставляется первая, текст уедет не в том порядке
            with self._work_lock:
                t0 = time.time()
                # Кто в фокусе - спрашиваем ДО распознавания, а не после: пока
                # модель думает, человек может успеть переключить окно, а тон
                # надо подобрать под то, куда он диктовал. Оверлей фокус не
                # забирает (WS_EX_NOACTIVATE), так что видим настоящее окно.
                process = layered.foreground_process()
                text = self.transcriber.transcribe(audio)
                text = clean(text, self.cfg, log, process=process)
                # Команды - ПОСЛЕ полировки: LLM не должна их видеть, иначе
                # перепишет или послушается, оба исхода хуже.
                text, want_enter = extract_commands(text, self.cfg)
                elapsed = time.time() - t0
                if not text:
                    # Молча спрятать пилюлю нельзя: человек говорил и ждёт
                    # текста. Скажем прямо, что вставлять нечего.
                    log(f"empty result ({dur:.1f}s audio)")
                    self.ui(self.overlay.show_error, "ничего не расслышали")
                    return
                # После текста с Enter'ом хвостовой пробел - мусор в начале
                # следующего сообщения.
                out = text + (" " if self.cfg.get("append_space", True)
                              and not want_enter else "")
                self._inserting = True
                try:
                    ok = insert(
                        out,
                        mode=self.cfg.get("insert_mode", "paste"),
                        restore=self.cfg.get("restore_clipboard", True),
                    )
                    if ok and want_enter:
                        time.sleep(0.05)   # дать окну дожевать вставку
                        press_enter()
                finally:
                    self._insert_window_closes()
                if ok:
                    # После Enter стирать нечего: текст уже улетел сообщением.
                    self._undo_text, self._undo_armed = \
                        (None, False) if want_enter else (out, True)
            self._history(text, dur)
            n = len(text.split())
            log(f"ok: {dur:.1f}s audio -> {len(text)} chars in {elapsed:.2f}s")
            if ok:
                self.ui(self.overlay.show_done,
                        f"{n} {plural(n, 'слово', 'слова', 'слов')}")
            else:
                self.ui(self.overlay.show_error, "не удалось вставить")
        except Exception as e:  # noqa: BLE001
            log(f"process error: {e}")
            self.ui(self.overlay.show_error, "ошибка распознавания")
        finally:
            self._set_tray_state("idle")

    # ---------- отмена последней вставки ----------

    def _insert_window_closes(self) -> None:
        """Закрыть «это печатаем мы» - но не сразу.

        Мы шлём вставку через SendInput/keybd_event, а не через keyboard: её
        собственные посылки она бы пометила как replay и пропустила, а наши
        видит как обычный ввод. Значит, _watch_typing увидит нашу же вставку и
        решит, что печатал человек. Хук работает в своём потоке и отстаёт,
        поэтому окно закрываем с запасом, а не по возврату из insert().
        """
        threading.Timer(0.4, lambda: setattr(self, "_inserting", False)).start()

    def _watch_typing(self, e) -> None:
        """Любое чужое нажатие после вставки снимает отмену.

        Иначе Backspace'ы съедят не наш текст, а то, что человек напечатал сам
        поверх - и это будет уже не «отмена», а порча.

        Модификатор сам по себе - не печать (человек тянется к сочетанию).
        Триггер-клавиша отмены снимает отмену, ЕСЛИ нажата без своих
        модификаторов: значит это просто буква в слове, а не жест отмены. С
        зажатыми модификаторами это сам хоткей отмены - его пропускаем, чтобы
        не разоружиться прямо перед тем, как отработает _undo_last.
        """
        if not self._undo_armed or self._inserting or e.event_type != "down":
            return
        name = (e.name or "").lower()
        if name in self._MOD_NAMES:
            return
        if name == self._undo_trigger and self._undo_mods_held():
            return
        self._undo_armed = False

    def _undo_mods_held(self) -> bool:
        try:
            return all(keyboard.is_pressed(m) for m in self._undo_mods)
        except Exception:  # noqa: BLE001 - is_pressed изредка кидает на экзотике
            return False

    def _undo_last(self) -> None:
        if not self._undo_armed or not self._undo_text:
            self.ui(self.overlay.show_error, "нечего отменять")
            return
        text, self._undo_text = self._undo_text, None
        self._undo_armed = False
        threading.Thread(target=self._undo_send, args=(text,), daemon=True).start()

    def _undo_send(self, text: str) -> None:
        # лок тот же, что у диктовки: отмена посреди вставки следующей фразы
        # стёрла бы её, а не предыдущую
        with self._work_lock:
            self._inserting = True
            try:
                # Считаем UTF-16-единицы, а не символы Python: эмодзи и прочее
                # вне BMP уходит суррогатной парой, и поле правки на Windows
                # хранит его двумя единицами - один Backspace на символ оставил
                # бы половинку. Для обычного текста (BMP) это то же число.
                ok = backspace(len(text.encode("utf-16-le")) // 2)
            finally:
                self._insert_window_closes()
        if ok:
            n = len(text.split())
            log(f"undo: {len(text)} chars")
            self.ui(self.overlay.show_done,
                    f"убрано {n} {plural(n, 'слово', 'слова', 'слов')}")
        else:
            self.ui(self.overlay.show_error, "не удалось отменить")

    def _history(self, text: str, dur: float) -> None:
        if not self.cfg.get("history", True):
            return
        try:
            # ротация: у лога она есть, а история росла без предела - её читают
            # целиком и окно истории, и статистика
            if (os.path.exists(HISTORY_PATH)
                    and os.path.getsize(HISTORY_PATH) > HISTORY_MAX):
                os.replace(HISTORY_PATH, HISTORY_PATH + ".1")
            with open(HISTORY_PATH, "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "sec": round(dur, 1),
                            "text": text,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except OSError:
            pass

    # ---------- настройки ----------

    def _open_settings(self) -> None:
        from settings_qt import SettingsWindow

        if self.settings is None:
            self.settings = SettingsWindow(
                self._on_config_change, self._on_hotkey_capture,
                self._info, HISTORY_PATH, LOG_PATH,
                on_onboarding=self._open_onboarding,
                update_fn=lambda: self._update,
                do_update=self._do_update)
        self.settings.open()

    def _open_onboarding(self) -> None:
        from onboarding_qt import OnboardingWindow

        if self.onboarding is None:
            self.onboarding = OnboardingWindow(self)
        self.onboarding.open()

    def _on_config_change(self, new: dict) -> None:
        """Настройки сохранились - применяем на лету, что можно."""
        old = dict(self.cfg)
        # Мутируем тот же словарь - Transcriber держит его по ссылке. Без
        # clear(): рабочий поток может читать cfg прямо сейчас, и пустой
        # словарь между clear() и update() отдал бы ему умолчания. Настройки
        # всегда пишут конфиг целиком, так что update() ничего не пропустит.
        self.cfg.update(new)
        hk_keys = ("hotkey_hold", "hotkey_toggle", "undo_hotkey")
        if any(old.get(k) != new.get(k) for k in hk_keys):
            self._hotkey_bind()
            self._set_tray_state(self._tray_state)   # в подсказке трея - биндЫ
        mic_keys = ("mic_device", "keep_mic_open", "pre_buffer_sec")
        if any(old.get(k) != new.get(k) for k in mic_keys) and not self._recording:
            self._rebuild_recorder()
        model_keys = ("model", "quantization", "device")
        if any(old.get(k) != new.get(k) for k in model_keys):
            self._reload_model_bg()
        if old.get("theme") != new.get("theme"):
            self._apply_theme()
        if old.get("overlay_position") != new.get("overlay_position"):
            self.overlay.set_position(str(new.get("overlay_position") or "bottom"))

    def _apply_theme(self) -> None:
        """Тема сменилась на живом приложении.

        В QML краски - это привязки к токенам, поэтому окна перекрашиваются
        сами, стоит токенам дёрнуть свой сигнал. Раньше окно настроек
        приходилось пересобирать целиком: половина красок впечатывалась в
        виджеты при создании.

        Иконка трея - по-прежнему картинка, и про смену палитры она не знает:
        её сбрасываем руками.
        """
        import icons

        mode = T.set_theme(str(self.cfg.get("theme") or "system"))
        icons.retheme()
        self.overlay.retheme()
        self._set_tray_state(self._tray_state)
        if self.settings is not None:
            self.settings.retheme()
        log(f"theme: {self.cfg.get('theme')} -> {mode}")

    def _reload_model_bg(self) -> None:
        """Смена модели без перезапуска (PLAN 2.4).

        Старая модель работает, пока грузится новая: долгая загрузка (или
        скачивание) не оставляет диктовку немой. Подмена - под _work_lock,
        чтобы не выдернуть модель из-под идущего распознавания.
        """
        if getattr(self, "_model_reloading", False):
            return
        self._model_reloading = True
        self._set_tray_state("load")

        def work() -> None:
            try:
                tr = Transcriber(self.cfg, log)
                tr.load()
                with self._work_lock:
                    self.transcriber = tr
                beep(1040, 90, self.cfg.get("sounds", True))
                self.ui(self.overlay.show_done, "модель готова")
            except Exception as e:  # noqa: BLE001 - старая модель продолжает работать
                log(f"model reload failed: {e}")
                self.ui(self.overlay.show_error, "не удалось загрузить модель")
            finally:
                self._model_reloading = False
                self._set_tray_state("idle")

        threading.Thread(target=work, daemon=True).start()

    def _rebuild_recorder(self) -> None:
        old = self.recorder
        try:
            self.recorder = self._make_recorder()
        except Exception as e:  # noqa: BLE001
            log(f"recorder rebuild failed: {e}")
            return
        try:
            old.close()
        except Exception:  # noqa: BLE001
            pass
        log(f"mic reopened: device={self.cfg.get('mic_device')}")

    def _on_hotkey_capture(self, active: bool) -> None:
        """Пока в настройках ловят новое сочетание, наш хоткей мешает:
        Ctrl+Shift+Space запустил бы запись вместо того, чтобы записаться."""
        self._capturing = active
        if active:
            self._hotkey_unbind()
        else:
            self._hotkey_bind()

    def _info(self) -> dict:
        from recorder import default_input_name, list_input_devices

        dev = self.cfg.get("mic_device")
        if dev is None:
            mic = default_input_name()
        else:
            mic = next((f"{n} · {a}" for i, n, a in list_input_devices() if i == dev),
                       f"устройство {dev}")
        # Страница «О программе», а не дамп для отладки. Раньше здесь стояли
        # «устройство: cpu / int8», «модель: gigaam-v3-e2e-rnnt» и версия
        # Python - человеку, который просто пишет письма, это не говорит
        # ничего, а на вопрос «всё ли хорошо?» не отвечает вовсе.
        #
        # Оставлено ровно то, что он может проверить глазами и о чём может
        # спросить: слышу ли я вас, чем диктовать, всё ли готово. Служебное
        # (имя модели, версия Python, точный путь) никуда не делось - оно в
        # flow.log, и кнопка рядом.
        m = models.get(str(self.cfg.get("model") or ""))
        info = {
            "состояние": self._status(),
            "версия": __version__ + ("" if not self._update else
                                     f"  ·  есть новая: {self._update['version']}"),
            "распознаёт": (f"{m.title} · {m.langs}" if m
                           else str(self.cfg.get("model"))),
            "слушает": mic,
            "диктовать": " · ".join(
                p for p in (inputspec.pretty(str(self.cfg.get("hotkey_hold") or "")),
                            inputspec.pretty(str(self.cfg.get("hotkey_toggle") or "")))
                if p) or "сочетание не назначено",
        }
        # Полировку мы включаем сами, молча - значит обязаны сказать, что она
        # включена. Иначе человек не поймёт, почему текст стал другим, а это
        # худший сорт сюрприза.
        if self._llm_note:
            info["понимает поправки"] = "да"
        return info

    def _status(self) -> str:
        if not self._ready:
            return "просыпаюсь…"
        # Без единого бинда приложение немое, и снаружи это неотличимо от
        # «оно не запустилось»: человек жмёт хоткей, ничего не происходит, и он
        # идёт запускать приложение снова. Так и было - четыре раза подряд.
        if not self._binds_pretty():
            return "не назначено сочетание · откройте настройки"
        return f"готов · {self._binds_pretty()}"

    def _binds_pretty(self) -> str:
        parts = [inputspec.pretty(str(self.cfg.get(k) or ""))
                 for k in ("hotkey_hold", "hotkey_toggle")
                 if str(self.cfg.get(k) or "").strip()]
        return " · ".join(parts)

    # ---------- трей ----------

    def _tray_icon(self, state: str):
        """PIL-картинка из icons.py -> QIcon.

        .copy() обязателен: QImage не владеет буфером, а tobytes() отдаёт
        временный - без копии икона показала бы мусор, как только сборщик
        доберётся до строки.
        """
        from PySide6.QtGui import QIcon, QImage, QPixmap

        import icons

        img = icons.mic(state, 64).convert("RGBA")
        qim = QImage(img.tobytes("raw", "RGBA"), img.width, img.height,
                     QImage.Format_RGBA8888).copy()
        return QIcon(QPixmap.fromImage(qim))

    def _set_tray_state(self, state: str) -> None:
        self._tray_state = state
        if self.tray is not None:
            try:
                self.tray.setIcon(self._tray_icon(state))
                # Подсказка трея - единственное, что видно, не открывая ничего.
                # Пусть в ней будет то, что человек ищет: чем диктовать.
                # Обновляем по событию, а не таймером: приложение висит в трее
                # сутками, и опрос ради строчки - те же холостые пробуждения.
                self.tray.setToolTip(f"FlowLocal — {self._status()}")
            except Exception:  # noqa: BLE001
                pass

    def _start_tray(self) -> None:
        """Трей на QSystemTrayIcon: своего потока, в отличие от pystray, ему не
        надо - живёт в цикле Qt. Заодно уходит вкомпиленный LGPLv3-пакет,
        из-за которого нельзя было раздавать onefile (PLAN 8.4)."""
        from PySide6.QtWidgets import QMenu, QSystemTrayIcon

        self.tray = QSystemTrayIcon(self._tray_icon("load"))
        menu = QMenu()
        self._tray_status = menu.addAction("FlowLocal")
        self._tray_status.setEnabled(False)
        menu.addSeparator()
        # Первым и заметным: если обновление есть, человек пришёл в меню скорее
        # всего за ним. Прячется, пока обновлять нечего.
        self._act_update = menu.addAction("Обновить")
        self._act_update.triggered.connect(self._do_update)
        self._act_update.setVisible(False)
        act_settings = menu.addAction("Настройки…")
        act_settings.triggered.connect(self._open_settings)
        self._act_retry = menu.addAction("Повторить последнюю диктовку")
        self._act_retry.triggered.connect(self._retry_last)
        menu.addAction("Открыть config.json").triggered.connect(
            lambda: os.startfile(CONFIG_PATH))  # noqa: S606 - свой же файл
        menu.addSeparator()
        menu.addAction("Выход").triggered.connect(self._shutdown)
        # Строку состояния и доступность «Повторить» пересобираем при каждом
        # открытии: модель грузится в фоне, а повторять до первой диктовки нечего.
        def _refresh_menu():
            self._tray_status.setText(f"FlowLocal - {self._status()}")
            self._act_retry.setEnabled(
                getattr(self, "_last_audio", None) is not None
                and self._ready and not self._recording)
            upd = self._update
            self._act_update.setVisible(bool(upd))
            if upd:
                self._act_update.setText(
                    f"Обновить до {upd['version']}  ({upd['size_mb']} МБ)")
        menu.aboutToShow.connect(_refresh_menu)
        self.tray.setContextMenu(menu)
        # Двойной клик - настройки: у pystray это был default=True.
        self.tray.activated.connect(
            lambda r: self._open_settings()
            if r == QSystemTrayIcon.DoubleClick else None)
        self._tray_menu = menu          # держим ссылку: иначе меню соберёт GC
        self.tray.show()
        self._set_tray_state(self._tray_state)   # иконка и подсказка на старте

    # ---------- запуск ----------

    def _load_model_bg(self) -> None:
        try:
            self.transcriber.load()
            self._ready = True
            self._set_tray_state("idle")
            log(f"ready, hold={self.cfg.get('hotkey_hold')!r} "
                f"toggle={self.cfg.get('hotkey_toggle')!r}")
            beep(1040, 90, self.cfg.get("sounds", True))
            # если человек уже жал хоткей и видит «загружаю модель…» - убрать
            self.ui(self._loading_done)
        except Exception as e:  # noqa: BLE001
            die(f"не удалось загрузить модель.\n\n{e}")
            self.ui(self._shutdown)

    def _check_update_bg(self) -> None:
        """Есть ли версия свежее. Своим потоком, молча, раз в несколько часов.

        Молча - это принцип, а не лень. Приложение висит в трее сутками; всплыть
        поверх чужой работы с новостью «вышла версия 0.2.1» - это ровно то, за
        что ненавидят программы. Нашли - пишем в трей и в «О программе», человек
        увидит, когда сам туда посмотрит.

        Из исходников не проверяем вовсе: там обновляются git pull, а не
        установщиком поверх рабочей копии.

        **Раз за запуск было мало, и это поймал владелец.** Приложение живёт в
        трее сутками: он поставил версию, запустил, проверка прошла и ничего
        не нашла - а релиз вышел через час. Узнать о нём было неоткуда, пока не
        перезапустишь. Теперь проверка повторяется по таймеру (_UPDATE_EVERY).
        Четыре пробуждения в сутки - это не «ноль в покое», это ноль и есть:
        принцип был про тик 60 раз в секунду, а не про запрос раз в шесть часов.
        """
        if not updater.can_update():
            return
        try:
            found = updater.check()
        except Exception as e:  # noqa: BLE001 - обновление не должно мешать диктовке
            log(f"проверка обновлений не удалась: {e}")
            return
        if not found:
            return
        self._update = found
        log(f"есть обновление: {found['version']} ({found['size_mb']} МБ)")
        # Меню трея само перечитает self._update при открытии (_refresh_menu),
        # трогать его отсюда, из чужого потока, не надо и нельзя.

    def _do_update(self) -> None:
        """Скачать и поставить. Зовётся из трея, работает своим потоком."""
        if not self._update:
            return
        info = self._update

        def work():
            try:
                self.ui(self.overlay.show_processing)
                self.ui(self.overlay.set_hint, f"обновление {info['version']}")
                path = updater.download(info["url"])
                log(f"обновление скачано: {path}")
                updater.install(path)
                # Уходим сами: пока мы живы, установщик не заменит наш .exe.
                self.ui(self._shutdown)
            except Exception as e:  # noqa: BLE001
                log(f"обновление не удалось: {e}")
                self.ui(self.overlay.show_error, "не удалось обновить")

        threading.Thread(target=work, daemon=True).start()

    def _autoconfig_llm_bg(self) -> None:
        """Есть ли у человека Ollama - выясняем сами, а не спрашиваем.

        Полировка (самоисправления, тон) - это то, чем мы отличаемся от простого
        распознавателя. Но она требует Ollama, и раньше умолчанием было
        «выключено»: у постороннего человека наша главная функция не работала ни
        разу, и он о ней даже не узнавал. Кто поставил Ollama - тот согласен на
        локальную модель по определению.

        Своим потоком: probe_ollama ждёт ответа до полутора секунд, а в главном
        потоке это полторы секунды без хоткея. Конфиг на диск не пишем -
        автоопределение делается на каждом старте заново, иначе выбранная
        сегодня модель осталась бы в файле навсегда и человек, удалив её,
        получил бы вечные ошибки в логе.
        """
        try:
            model = cleaner.autoconfig_llm(self.cfg, log)
        except Exception as e:  # noqa: BLE001 - полировка опциональна, диктовка нет
            log(f"autoconfig llm failed: {e}")
            return
        if model:
            self._llm_note = model

    def _loading_done(self) -> None:
        if self.overlay.state == OV.LOADING:
            self.overlay.hide()

    def _shutdown(self) -> None:
        self._hotkey_unbind()
        if self.tray is not None:
            try:
                self.tray.hide()
            except Exception:  # noqa: BLE001
                pass
            self.tray = None
        self.qapp.quit()

    def _start_ipc(self) -> None:
        """Слушаем ярлык: повторный запуск просит нас показаться.

        removeServer перед listen обязателен: если процесс когда-то умер не
        по-человечески, имя остаётся занятым, listen падает - и ярлык навсегда
        перестаёт открывать окно.
        """
        from PySide6.QtNetwork import QLocalServer

        self._ipc = QLocalServer()
        QLocalServer.removeServer(IPC_NAME)
        if not self._ipc.listen(IPC_NAME):
            log(f"ipc listen failed: {self._ipc.errorString()}")
            return
        self._ipc.newConnection.connect(self._on_ipc)

    def _heal_autostart(self) -> None:
        """Команда автозапуска в реестре устарела - перезаписать.

        Записывается она один раз, галочкой в настройках, и после этого живёт
        своей жизнью: папку перенесли, Python обновили, у нас появился флаг
        `--silent`. Пока запись старая, вход в систему будет открывать окно
        настроек - ровно то, чего мы избегаем.
        """
        try:
            if app_paths.autostart_command_stale():
                set_autostart(True)
                log("автозапуск: команда в реестре обновлена")
        except Exception as e:  # noqa: BLE001 - реестр не должен ронять запуск
            log(f"autostart heal failed: {e}")

    def _on_ipc(self) -> None:
        conn = self._ipc.nextPendingConnection()
        if conn is not None:
            conn.disconnectFromServer()
        # Под pythonw stderr мёртв, и исключение внутри Qt-слота уходит в
        # никуда: снаружи это выглядит как «кликнул по ярлыку - ничего не
        # произошло», и отладить нечем. Это единственный путь, которым человек
        # добирается до окна, - он обязан оставлять улику.
        try:
            self._open_settings()
        except Exception:  # noqa: BLE001
            import traceback
            log("не смог открыть настройки по ярлыку:\n" + traceback.format_exc())

    def run(self, silent: bool = False) -> None:
        self._hotkey_bind()
        self._start_tray()
        self._start_ipc()
        self._heal_autostart()
        threading.Thread(target=self._load_model_bg, daemon=True).start()
        threading.Thread(target=self._autoconfig_llm_bg, daemon=True).start()
        threading.Thread(target=self._check_update_bg, daemon=True).start()
        # И дальше - по таймеру, пока приложение живёт в трее.
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(
            lambda: threading.Thread(target=self._check_update_bg, daemon=True).start())
        self._update_timer.start(_UPDATE_EVERY)
        if not self.cfg.get("onboarded"):
            # Первый запуск: без мастера человек видит только иконку в трее и
            # не понимает ничего. Небольшая задержка - дать трею показаться.
            QTimer.singleShot(600, self._open_onboarding)
        elif silent:
            # Вход в систему: молча в трей. Окно, всплывающее при каждой
            # загрузке Windows, - это не забота, а навязчивость.
            #
            # Шарик всё же показываем: иконку в трее может быть не видно вовсе -
            # Windows прячет новые значки под шеврон, а панель задач бывает с
            # автоскрытием, и тогда запуск выглядит как «ничего не произошло».
            QTimer.singleShot(900, self._greet)
        else:
            # Человек кликнул по ярлыку - значит хочет увидеть программу, а не
            # догадываться, запустилась ли она. Раньше здесь был только шарик, и
            # клик по ярлыку выглядел как «ничего не открывается»: живого
            # экземпляра ещё нет, будить некого, а новый молча садился в трей.
            QTimer.singleShot(400, self._open_settings)
        log("started")
        try:
            self.qapp.exec()
        finally:
            self._hotkey_unbind()
            try:
                keyboard.unhook_all()
            except Exception:  # noqa: BLE001
                pass
            if self.settings is not None:
                self.settings.close()
            self.overlay.destroy()
            self.recorder.close()
            if self.tray is not None:
                try:
                    self.tray.hide()
                except Exception:  # noqa: BLE001
                    pass

    def _greet(self) -> None:
        """Сказать, что мы здесь и чем нас звать.

        Иконку в трее может быть не видно вовсе: Windows прячет новые значки
        под шеврон, а панель задач бывает с автоскрытием. Тогда запуск выглядит
        как «ничего не произошло» - ровно на это и жаловались.
        """
        from PySide6.QtWidgets import QSystemTrayIcon

        if self.tray is None:
            return
        binds = self._binds_pretty()
        self.tray.showMessage(
            "FlowLocal запущен",
            f"Диктовка: {binds}" if binds
            else "Хоткей не назначен - откройте настройки",
            QSystemTrayIcon.Information, 4000)


IPC_NAME = "FlowLocal_ipc"


def single_instance() -> bool:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    # хэндл намеренно не закрываем: мьютекс должен жить, пока живёт процесс
    k32.CreateMutexW(None, False, "FlowLocal_single_instance")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def poke_running_instance() -> bool:
    """Попросить уже запущенный экземпляр показаться. True - достучались.

    Зачем вообще: человек кликает ярлык, приложение уже в трее - и второй
    экземпляр молча выходил. Снаружи это неотличимо от «не запускается»:
    иконку в трее не видно, если панель задач скрывается автоматически, а
    MessageBox «уже запущен, иконка в трее» отправлял искать невидимое.
    Теперь клик по ярлыку всегда что-то показывает - как у любой программы,
    живущей в трее.
    """
    from PySide6.QtNetwork import QLocalSocket

    s = QLocalSocket()
    s.connectToServer(IPC_NAME)
    if not s.waitForConnected(600):
        return False
    s.write(b"show")
    s.waitForBytesWritten(600)
    s.disconnectFromServer()
    return True


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "--autostart":
        mode = sys.argv[2] if len(sys.argv) >= 3 else ""
        if mode not in ("on", "off"):
            print("использование: python app.py --autostart on|off")
            return
        set_autostart(mode == "on")
        print(f"автозапуск {'включён' if mode == 'on' else 'выключен'}")
        return
    # Первая строка лога - до всего остального. Она отвечает на вопрос, который
    # иначе не отличить: приложение не запустилось вовсе или запустилось и
    # умерло? По автозапуску это единственная улика, которая у нас будет.
    log(f"launch: pid={os.getpid()} exe={sys.executable} cwd={os.getcwd()}")
    if not single_instance():
        log("already running")
        # Достучаться до живого экземпляра нужен цикл событий Qt - создаём
        # приложение, но окон не открываем: этот процесс сейчас же умрёт.
        from PySide6.QtWidgets import QApplication

        _q = QApplication(sys.argv)
        if not poke_running_instance():
            # Пайпа нет: экземпляр от старой версии или умирает. Сказать вслух
            # - лучше, чем молча выйти.
            ctypes.windll.user32.MessageBoxW(
                None, "FlowLocal уже запущен - иконка в трее.", "FlowLocal", 0x40)
        return
    C.bootstrap()      # свежий клон: config.json ещё нет, делаем из примера
    # --silent ставит себе автозапуск (app_paths.autostart_command): вход в
    # систему молчит, клик по ярлыку показывает окно.
    App().run(silent="--silent" in sys.argv)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        # Под pythonw консоли нет, и до сих пор ЛЮБАЯ ошибка на старте уходила
        # в никуда: процесс молча умирал, не оставив в логе даже следа. Ровно
        # поэтому «после перезагрузки автозапуск не сработал» оказалось нечем
        # отлаживать - а автозапуск как раз и стартует в самый неудачный момент,
        # когда система ещё раскачивается.
        import traceback

        log("FATAL on startup:\n" + traceback.format_exc())
        die(f"не удалось запуститься.\n\n{e}")
        raise SystemExit(1) from e
