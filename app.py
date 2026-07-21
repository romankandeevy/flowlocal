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
import platform_api  # noqa: E402

# keyboard - только Windows (см. requirements.txt и platform_api.CAN_HOTKEYS).
# На macOS библиотеки нет вовсе; держим имя пустым, а вся привязка хоткеев ниже
# уходит в заглушку. Так `import app` не падает на ModuleNotFoundError.
if platform_api.IS_WINDOWS:
    import keyboard  # noqa: E402
else:
    keyboard = None
from PySide6.QtCore import QObject, QTimer, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import config as C  # noqa: E402
import inputspec  # noqa: E402
import language  # noqa: E402
import models  # noqa: E402
import overlay_qt as OV  # noqa: E402
import theme as T  # noqa: E402
import updater  # noqa: E402
import i18n  # noqa: E402
import recordings  # noqa: E402
import streaming  # noqa: E402
import transforms  # noqa: E402
import wakeup  # noqa: E402
from version import __version__  # noqa: E402
import cleaner  # noqa: E402
from cleaner import _strip_fillers, clean, extract_commands, llm_command  # noqa: E402
from inserter import (_set_clipboard_text, backspace,  # noqa: E402
                      copy_selection, grab_text, insert, press_enter,
                      select_all, to_clipboard)
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

# С какой длины диктовка остаётся в буфере обмена после вставки.
#
# Триста знаков - это примерно абзац, полминуты речи. Короче - фраза в чат,
# её проще сказать заново, чем искать; длиннее - работа, потерять которую
# обидно по-настоящему. Порог грубый намеренно: точное число тут ничего не
# решает, решает сам факт, что у длинного текста есть второй след.
_KEEP_IN_CLIPBOARD_CHARS = 300


def _words_label(n: int) -> str:
    """«23 слова» - то, что пилюля показывает после диктовки.

    Согласование числительного считается здесь, а язык выбирает правило, а не
    перевод готовой строки: ключом в словаре была бы строка с числом, и вести
    его пришлось бы до бесконечности.
    """
    if i18n.language() == "en":
        return f"{n} word" if n == 1 else f"{n} words"
    return f"{n} {plural(n, 'слово', 'слова', 'слов')}"


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


# Заглушки платформы (beep, single_instance, фатальное окно) пишут в тот же
# журнал - отдаём им наш log сразу, как только он объявлен.
platform_api.set_logger(log)


def die(msg: str, detail: str = "") -> None:
    """Фатальная ошибка так, чтобы её увидели: под pythonw консоли нет и
    traceback уходит в никуда.

    Два текста, а не один, и это главное в этой функции. `msg` человеку -
    человеческой фразой; `detail` (текст исключения) уходит ТОЛЬКО в журнал.
    Раньше оба склеивались в одно окно, и последнее, что человек видел от
    программы, выглядело так:

        не удалось загрузить модель.

        [WinError 126] Не найден указанный модуль

    Вторая строка не говорит ему ничего и не подсказывает ни одного действия -
    она написана для нас. Ему нужен адрес журнала: окна, из которого журнал
    открывается кнопкой, в этот момент ещё нет и уже не будет.
    """
    log(f"FATAL: {msg}" + (f" | {detail}" if detail else ""))
    # Окно средствами платформы: MessageBoxW на Windows, osascript на macOS -
    # ctypes.windll там нет вовсе, и обращение к нему стало бы второй ошибкой
    # поверх первой (ровно то, что роняло старт на не-Windows).
    platform_api.fatal_message(msg, LOG_PATH)


def beep(freq: int, dur: int, enabled: bool) -> None:
    # winsound - только Windows; ветвление внутри platform_api.beep.
    platform_api.beep(freq, dur, enabled)


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
        T.set_layout(str(self.cfg.get("layout") or "cards"))
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
        # Куда пилюлю утащили в прошлый раз - и чем запомнить новое место.
        # Пишем сразу в конфиг: перетаскивание должно пережить перезапуск, а
        # случается оно раз в жизни, так что склеивать записи не за чем.
        self.overlay.set_custom_pos(self.cfg.get("overlay_x"),
                                    self.cfg.get("overlay_y"),
                                    save=self._save_overlay_pos)
        self.transcriber = Transcriber(self.cfg, log)
        self.settings = None         # окно программы: Главная, История, настройки
        self.onboarding = None
        self.tray = None
        self._recording = False
        self._rec_started_at = 0.0
        self._rec_mode = "hold"        # каким биндом начата текущая запись
        # Куда ушла последняя диктовка: окно, буфер или файл. Нужно «Повторить
        # последнюю» - повтор обязан отдать текст туда же, куда собирался.
        self._last_dest = "insert"
        self._held = {"hold": False, "toggle": False, "command": False,
                      "clipboard": False, "inbox": False}
        self._mouse_binds: list[tuple[str, tuple, str]] = []
        self._mouse_listener = None
        self._work_lock = threading.Lock()
        self._ready = False
        self._llm_note = ""          # модель Ollama, найденная автоопределением
        self._update_told = ""       # про какую версию уже сказали шариком
        # Сказали ли уже, что английская модель не приехала. Один раз за
        # запуск: шарик на каждую английскую фразу - это навязчивость, а
        # догрузка всё равно идёт своим ходом.
        self._english_told = False
        # Настройки страницей: мост, окно и Backend под них. Поднимаются по
        # требованию и только при включённом ui.web - вебвью стоит 123 МБ
        # памяти, а программа висит в трее сутками.
        self._web = None
        self._bridge = None
        self._web_backend = None
        self._ollama_busy = False    # идёт ли установка Ollama
        self._ollama_subs: list = []  # окна, которые хотят видеть ход
        self._last_insert = None     # (exe, когда, текст) - для склейки
        self._last_use = time.time()  # когда последний раз диктовали
        self._update: dict | None = None   # свежая версия с GitHub, если нашлась
        self._wake = None            # слух за сном и разблокировкой экрана
        self.transcript = None       # окно с расшифровкой файла
        # Идёт ли расшифровка файла. Отдельно от _recording: диктовать во время
        # расшифровки можно (она ждёт своей очереди на _work_lock), а вот
        # запускать вторую расшифровку поверх первой - нет: два часовых файла
        # разом просто поделят процессор и оба будут вдвое дольше.
        self._file_busy = False
        self._music = None           # пауза музыки на время диктовки
        self.picker = None           # список преобразований, создаётся при первом показе
        self._tf_text = ""           # что преобразуем
        self._tf_clip = None         # буфер человека, вернуть после вставки
        self._tf_hwnd = 0            # окно, куда возвращать фокус
        # Взяли ли мы поле ЦЕЛИКОМ (Ctrl+A наш) или это выделение человека. От
        # этого зависит вставка: своё выделение можно поставить заново, чужое -
        # нельзя, см. _transform_work.
        self._tf_all = False
        self._stream = None          # разбор речи на ходу, пока идёт запись
        self._stream_thread = None
        self._deaf_told = ""         # про какую глухоту уже сказали
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
        if not platform_api.CAN_HOTKEYS:
            # macOS: библиотеки keyboard нет, глобальные хоткеи пойдут через
            # pynput+Quartz - отдельная большая работа. Пока тихо не привязываем
            # ничего: окно, настройки и трей работают, диктовка по хоткею - нет.
            platform_api.note_unsupported("горячие клавиши")
            return
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
                    # Само сочетание из конфига на пилюле не показываем: сюда
                    # оно попадает как раз тогда, когда прочитать его не
                    # удалось, то есть это мусор из файла. Человеку важно
                    # другое - что диктовка работает и каким сочетанием.
                    self.ui(self.overlay.show_error,
                            "сочетание не распозналось - вернул стандартное")
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
        self._bind_transform()
        self._bind_notes()
        self._bind_elsewhere()

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

    def _bind_transform(self) -> None:
        """Хоткей преобразований текста. Пусто - выключено.

        Отдельным биндом, а не режимом диктовки: здесь нечего записывать.
        Нажал - взяли текст поля и показали пилюлю выбора. Выделять руками
        ничего не надо: выделил - возьмём выделение, не выделил - возьмём поле
        целиком. Всё остальное делает выбор.
        """
        spec = str(self.cfg.get("hotkey_transform") or "").strip()
        if not spec:
            return
        try:
            self._hk_handles.append(
                keyboard.add_hotkey(spec, self._transform_pressed, suppress=False))
        except (ValueError, KeyError) as e:
            log(f"bad hotkey_transform {spec!r}: {e}")

    def _bind_notes(self) -> None:
        """Сочетание для окна заметок. Пусто - только из трея."""
        spec = str(self.cfg.get("hotkey_notes") or "").strip()
        if not spec:
            return
        try:
            self._hk_handles.append(keyboard.add_hotkey(
                spec, lambda: self.ui(self.open_notes), suppress=False))
        except (ValueError, KeyError) as e:
            log(f"bad hotkey_notes {spec!r}: {e}")

    def _bind_elsewhere(self) -> None:
        """Два жеста диктовки, у которых текст едет не в активное окно:
        «в буфер» (hotkey_clipboard) и «в файл» (hotkey_inbox). Оба
        необязательные, оба по умолчанию пустые.

        Через тот же _bind_dictation, что hold и command: жест ровно тот же -
        зажал, сказал, отпустил, - и заводить ему второй способ ловли клавиш
        значило бы завести второе место, где ломается хоткей. Отличие целиком в
        одном: куда отдать распознанное (см. _process, параметр dest).

        Битое сочетание не откатываем на умолчание, как у hold: умолчание тут
        пустое, возвращать нечего, а немым приложение от этого не станет.
        """
        for mode, key in (("clipboard", "hotkey_clipboard"),
                          ("inbox", "hotkey_inbox")):
            spec = str(self.cfg.get(key) or "").strip()
            if not spec:
                continue
            # Инбокс без файла - это жест, который молча ничего не делает.
            # Лучше не вешать вовсе и сказать об этом в журнале.
            if mode == "inbox" and not str(self.cfg.get("inbox_path") or "").strip():
                log("hotkey_inbox задан, а файл не выбран - жест не включён")
                continue
            try:
                self._bind_dictation(mode, spec)
            except (ValueError, KeyError) as e:
                log(f"bad {key} {spec!r}: {e}")

    def open_notes(self) -> None:
        """Открыть заметки. ТОЛЬКО главный поток Qt.

        Заметки теперь страница главного окна, а не отдельное окно: диктуют в
        поле редактора на ней. Открываем то же единственное окно (что трей и
        «Пуск»), переводим его на страницу «Заметки» и по настройке «notes_open»
        решаем, показать список или сразу редактор под фокусом - чтобы
        надиктованному было куда лечь с первой секунды.

        Диктовка в поле работает сама: текст мы вставляем в активное окно через
        Ctrl+V, а активным будет это окно с полем в фокусе (страница берёт поле
        под фокус при переходе в редактор). Специального кода для этого нет.
        """
        try:
            self._open_settings()
            root = self.settings.view.rootObject() if self.settings.view else None
            if root is None:
                return
            root.openNotes(str(self.cfg.get("notes_open") or "list"))
        except Exception as e:  # noqa: BLE001 - заметки не должны ронять диктовку
            import traceback

            log("страница заметок не открылась:\n" + traceback.format_exc())
            self.ui(self.overlay.show_error, "заметки не открылись")

    # ---------- расшифровка готового файла (PLAN 11) ----------
    #
    # Второй источник речи, кроме микрофона. Дальше - ТОТ ЖЕ конвейер: резка на
    # куски по 60 секунд, ASR, знаки, чистка от бубнежа, словарь. Отличий ровно
    # три, и все три на краях: откуда берётся звук (audiofile), куда уходит
    # текст (окно с текстом вместо вставки в чужое поле) и пометка в истории.
    #
    # Дверей тоже две, и обе ведут сюда: пункт трея «Расшифровать файл…» и
    # перетаскивание файла на окно программы.

    def transcribe_file(self, path: str) -> None:
        """Расшифровать файл. ТОЛЬКО главный поток Qt.

        Здесь остаются только разговоры с человеком - проверка файла и вопрос
        про длинную запись. Сама работа уходит в поток: часовой подкаст считает
        минуты, и заморозить на них главный поток значит показать «программа
        зависла» вместо работы.
        """
        import audiofile

        path = str(path or "").strip('"')
        try:
            audiofile.check(path)
        except audiofile.AudioFileError as e:
            self._file_message("Не могу открыть", i18n.t(str(e)))
            return
        if self._recording:
            self._file_message("Идёт запись",
                               i18n.t("сначала закончите диктовку"))
            return
        if self._file_busy:
            self._file_message("Уже работаю",
                               i18n.t("подождите, идёт расшифровка"))
            return

        # Длину спрашиваем ДО старта, а не после. Человек, бросивший на окно
        # часовой подкаст, должен узнать про пятнадцать минут работы, пока он
        # ещё может передумать, - а не обнаружить это через десять минут по
        # молчащей программе.
        secs = audiofile.duration(path)
        if secs >= audiofile.LONG_MINUTES * 60 and not self._ask_long(path, secs):
            log(f"расшифровка отменена человеком: {secs / 60:.0f} мин")
            return
        self._file_busy = True
        self.ui(self.overlay.set_hint, "")
        self.ui(self.overlay.show_downloading, i18n.t("читаю файл"))
        self._set_tray_state("proc")
        threading.Thread(target=self._process_file, args=(path, secs),
                         daemon=True).start()

    def _file_message(self, title: str, body: str) -> None:
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox()
        box.setWindowTitle(i18n.t(title))
        box.setText(body)
        box.setIcon(QMessageBox.Information)
        box.exec()

    def _ask_long(self, path: str, secs: float) -> bool:
        """Спросить про длинную запись. True - человек согласен ждать."""
        import audiofile
        from PySide6.QtWidgets import QMessageBox

        mins = int(secs // 60)
        wait = int(audiofile.estimate(secs) // 60)
        box = QMessageBox()
        box.setWindowTitle(i18n.t("Это надолго"))
        box.setIcon(QMessageBox.Question)
        box.setText(
            f"{os.path.basename(path)}\n\n"
            + i18n.t("Запись идёт") + f" {mins} "
            + plural(mins, "минуту", "минуты", "минут") + ". "
            + i18n.t("Расшифровка займёт около") + f" {max(1, wait)} "
            + plural(max(1, wait), "минуты", "минут", "минут") + ".\n\n"
            + i18n.t("Программой можно пользоваться дальше - диктовка подождёт "
                     "своей очереди."))
        yes = box.addButton(i18n.t("Расшифровать"), QMessageBox.AcceptRole)
        box.addButton(i18n.t("Отмена"), QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() is yes

    def _process_file(self, path: str, secs: float) -> None:
        """Файл -> текст. Рабочий поток.

        Под тем же _work_lock, что и диктовка с микрофона, и это не
        перестраховка: модель одна, и два прогона разом в лучшем случае
        поделили бы процессор пополам, а в худшем - подрались бы за загрузку
        модели, если её успели выгрузить за простоем.
        """
        import audiofile

        name = os.path.basename(path)
        try:
            audio = audiofile.decode(
                path,
                on_progress=lambda d: self.ui(
                    self.overlay.show_downloading,
                    i18n.t("читаю файл") + f" {int(d * 100)}%"))
            dur = audio.size / 16000.0
            log(f"файл {name}: {dur:.1f} с звука")
            self.ui(self.overlay.show_processing)
            with self._work_lock:
                if not self.transcriber.loaded:
                    self.ui(self.overlay.show_downloading, i18n.t("просыпаюсь"))
                    self.transcriber.load()
                    self.ui(self.overlay.show_processing)
                self._last_use = time.time()
                t0 = time.time()
                # Прогресс «часть N из M» уже умеет transcriber - он и режет.
                raw = self.transcriber.transcribe(
                    audio, on_part=lambda i, n: self.ui(
                        self.overlay.show_downloading, f"часть {i} из {n}"))
                # process не передаём: чистка подбирает тон по тому, КУДА
                # вставляют, а мы никуда не вставляем. Правило тона для окна,
                # которое сейчас в фокусе, к чужому подкасту отношения не имеет.
                text = clean(raw, self.cfg, log)
            if not text:
                log(f"файл {name}: ничего не расслышали")
                self.ui(self.overlay.show_error, i18n.t("в файле не слышно речи"))
                return
            self._history(text, dur, raw=raw, source="file")
            n = len(text.split())
            log(f"файл {name}: {n} слов за {time.time() - t0:.1f} с")
            self.ui(self.overlay.show_done, _words_label(n))
            self.ui(self._show_transcript, name, text)
        except audiofile.AudioFileError as e:
            log(f"файл {name}: {e}")
            self.ui(self.overlay.show_error, i18n.t(str(e)))
        except Exception as e:  # noqa: BLE001 - чужой файл не должен ронять программу
            log(f"файл {name}: не вышло: {type(e).__name__}: {e}")
            self.ui(self.overlay.show_error, i18n.t("файл не расшифровался"))
        finally:
            self._file_busy = False
            self._set_tray_state("idle")

    def _show_transcript(self, name: str, text: str) -> None:
        """Окно с расшифровкой. Главный поток."""
        try:
            if self.transcript is None:
                from transcript_qt import TranscriptWindow

                self.transcript = TranscriptWindow(self.overlay.tokens, log)
            self.transcript.show(name, text)
        except Exception:  # noqa: BLE001 - текст важнее окна
            import traceback

            log("окно расшифровки не открылось:\n" + traceback.format_exc())
            # Текст не теряем ни при каком исходе: окна нет - значит в буфер, и
            # человеку об этом говорим. Час работы модели не должен пропасть
            # из-за того, что не нарисовалось окно.
            self._to_clipboard(text)
            self.ui(self.overlay.show_done, i18n.t("расшифровка в буфере"))

    def _pick_audio_file(self) -> None:
        """Пункт трея «Расшифровать файл…». Главный поток."""
        import audiofile
        from PySide6.QtWidgets import QFileDialog

        mask = " ".join("*" + e for e in audiofile.SUPPORTED)
        path, _ = QFileDialog.getOpenFileName(
            None, i18n.t("Какой файл расшифровать"),
            os.path.expanduser("~"),
            f"{i18n.t('Запись')} ({mask});;{i18n.t('Все файлы')} (*)")
        if path:
            self.transcribe_file(path)

    def _tidy_note(self, text: str, instruction: str) -> str:
        """Причесать заметку. Зовётся из потока окна заметок.

        Через llm_command - тот же путь, что у трансформов: там уже есть и
        предохранители от пустого ответа, и защита от абсурдной длины. Второй
        путь к Ollama заводить незачем.
        """
        llm = self.cfg.get("llm") or {}
        if not llm.get("enabled"):
            return ""
        with self._work_lock:
            return llm_command(text, instruction, llm, log)

    def _transform_pressed(self) -> None:
        """Колбэк хука: только передать в главный поток и уйти.

        У низкоуровневого хука 300 мс на ответ, иначе Windows вышибает его
        совсем. Ctrl+A и Ctrl+C с ожиданием буфера сюда не поместятся, поэтому
        вся работа - в потоке.
        """
        if self._recording or self._capturing:
            return
        threading.Thread(target=self._transform_grab, daemon=True).start()

    def _llm_missing(self) -> str:
        """Почему правки текста нет - фразой и с указанием, куда идти.

        Три разные беды выглядели на пилюле одинаково («правка текста не
        установлена»), а делать в них надо разное: включить переключатель,
        разбудить уснувшую Ollama, поставить её с нуля. Хуже всего был средний
        случай - программа стоит на диске и молчит, а человеку предлагали
        установить её заново.

        Спрашиваем состояние, а не гадаем по конфигу. serving() на закрытый
        порт отвечает отказом сразу, так что рабочий поток тут не залипнет.
        """
        import ollama_setup as O

        if (self.cfg.get("llm") or {}).get("enabled") is False:
            return "правка текста выключена в настройках"
        st = O.state()
        if st == O.STATE_SLEEPING:
            return "правка текста не отвечает - откройте настройки"
        if st == O.STATE_NO_MODEL:
            return "правке текста не хватает модели"
        return "правка текста не установлена - откройте настройки"

    def _nothing_to_transform(self) -> str:
        """Брать было нечего - сказать человеку, что делать. Фразой, не диагнозом.

        Прежняя надпись («нет текста») называла состояние программы, а владелец
        из неё вычитал поломку - и был по-своему прав: он ничего не выделял и
        ждал, что преобразуется всё. Теперь всё и берётся, так что пусто бывает
        по одной причине - фокус не в тексте.

        Чаще всего фокус ушёл в наше же окно: человек щёлкнул по FlowLocal,
        документ перестал быть активным. Это стоит назвать прямо, иначе совет
        «щёлкните в текст» звучит как «попробуйте ещё раз» - непонятно, что
        именно менять.

        Своё окно узнаём по имени exe. В сборке это FlowLocal.exe, совпадений
        быть не может; из исходников - python.exe, и соседнее приложение на
        питоне даст ложное срабатывание. Цена ошибки - одна подсказка вместо
        другой, поля мы в обоих случаях уже не трогаем.
        """
        try:
            exe = (layered.foreground_process() or "").lower()
            if exe and exe == os.path.basename(sys.executable).lower():
                return "это окно FlowLocal - щёлкните в свой текст"
        except Exception:  # noqa: BLE001 - подсказка не стоит падения
            pass
        return "щёлкните в свой текст и нажмите ещё раз"

    def _transform_grab(self) -> None:
        """Взять текст поля и показать пилюлю выбора. Рабочий поток.

        Порядок проверок не случаен - тот же, что у _process_command: мы
        собираемся вставить ПОВЕРХ чужого текста, а значит стереть его. Поэтому
        сперва спрашиваем, есть ли что показывать, и лишь потом трогаем чужое
        поле; на каждом сомнении - выходим, ничего не тронув.

        Текст берём сами. Выделил человек - берём выделение; не выделил -
        выделяем поле целиком (это и есть просьба владельца: «весь текст
        преобразовывается»). Разбор двух случаев - в inserter.grab_text, там же
        объяснено, почему Ctrl+A жмётся только вторым шагом.
        """
        if not self._work_lock.acquire(blocking=False):
            log("преобразование: занято")
            return
        try:
            llm = self.cfg.get("llm") or {}
            if not llm.get("enabled"):
                self.ui(self.overlay.show_error, self._llm_missing())
                return
            # Окно запоминаем ДО всего: пилюля выбора заберёт фокус себе, и
            # спрашивать «какое окно активно» будет уже поздно - активной
            # окажется она сама.
            self._tf_hwnd = layered.foreground_window()
            items = transforms.all_for(self.cfg)
            if not items:
                # Все готовые спрятаны и своих нет. Пилюлю всё равно
                # показываем - со словом «нету»: человек нажал сочетание и
                # обязан получить ответ, а тишина читается как поломка. Поля
                # при этом не касаемся вовсе.
                self._tf_text, self._tf_clip, self._tf_all = "", None, False
                self.ui(self._transform_show, [])
                return
            self._inserting = True
            try:
                text, old_clip, took_all = grab_text()
            finally:
                self._insert_window_closes()
            if not text or not text.strip():
                # Ни выделения, ни текста в поле. Буфер человека grab_text уже
                # вернул на место, поле не тронуто - остаётся объяснить.
                #
                # Спрашиваем ПОСЛЕ захвата, а не до: своё окно тоже бывает с
                # текстом (заметки), и отказывать ему заранее значило бы
                # отобрать работающую возможность ради подсказки.
                log("преобразование: в активном окне нет текста")
                self.ui(self.overlay.show_error, self._nothing_to_transform())
                return
            self._tf_text, self._tf_clip, self._tf_all = text, old_clip, took_all
            self.ui(self._transform_show, items)
        finally:
            self._work_lock.release()

    def _transform_show(self, items: list) -> None:
        """Показать пилюлю выбора. ТОЛЬКО главный поток Qt.

        Пустой список - тоже показ, а не тишина: пилюля скажет «нету». Фокус
        она заберёт и в этом случае, но терять нечего - поля мы не трогали, а
        Esc возвращает фокус обратно.
        """
        if self.picker is None:
            from picker_qt import Picker

            self.picker = Picker(self.overlay.tokens)
            self.picker.chosen.connect(self._transform_chosen)
            self.picker.cancelled.connect(self._transform_cancelled)
        from picker_qt import preview_of

        self.picker.show(items, preview_of(self._tf_text))

    def _transform_cancelled(self) -> None:
        # Буфер человека вернуть обязательно: Ctrl+C его затёр, а он ничего не
        # выбрал - для него не произошло вообще ничего, и буфер должен это
        # подтверждать.
        if self._tf_clip is not None:
            _set_clipboard_text(self._tf_clip)
        layered.focus_window(self._tf_hwnd)
        self._tf_text, self._tf_clip, self._tf_hwnd = "", None, 0
        self._tf_all = False

    def _transform_chosen(self, tid: str) -> None:
        t = transforms.find(self.cfg, tid)
        if not t or not self._tf_text:
            return
        # Фокус возвращаем СРАЗУ, а не после ответа модели: пока она думает,
        # человек уже смотрит в своё окно, и мигание в конце было бы лишним.
        layered.focus_window(self._tf_hwnd)
        threading.Thread(target=self._transform_work, args=(t,), daemon=True).start()

    def _transform_work(self, t: dict) -> None:
        """Прогнать текст через модель и положить результат ПОВЕРХ взятого.

        Здесь единственное место, где мы стираем чужой текст, поэтому обе
        опасные вещи обставлены проверками.

        Первая - Ctrl+A. Он снимает выделение человека и ставит своё на весь
        документ. Жмём его ТОЛЬКО если поле целиком забирали мы сами
        (`took_all`): тогда «выделить всё» и есть ровно то, что мы взяли, и
        замена совпадает с обещанием. Если текст выделял человек, Ctrl+A не
        жмём вовсе - его выделение пережило уход фокуса к пилюле, и вставка
        ляжет поверх него. А если не пережило, результат встанет рядом: это
        видно глазами и снимается Ctrl+Z, тогда как Ctrl+A переписал бы весь
        документ - непоправимо и молча.

        Вторая - окно. Пока модель думает (секунды), человек успевает уйти
        куда угодно, и Ctrl+A с вставкой уехали бы в чужой документ. Поэтому
        прямо перед заменой сверяем активное окно с тем, откуда брали. Не
        сошлось или окна мы не знаем - не трогаем ничего, результат кладём в
        буфер и говорим об этом.
        """
        text, old_clip = self._tf_text, self._tf_clip
        took_all, hwnd = self._tf_all, self._tf_hwnd
        self._tf_text, self._tf_clip = "", None
        with self._work_lock:
            try:
                self.ui(self.overlay.show_processing)
                t0 = time.time()
                result = llm_command(text, t["instruction"],
                                     self.cfg.get("llm") or {}, log)
                if not result:
                    # Модель промолчала или Ollama отвалилась. Поле не трогаем
                    # и возвращаем буфер человека: для него не случилось ничего.
                    self._restore_clip(old_clip)
                    self.ui(self.overlay.show_error, "не получилось - текст не тронут")
                    return
                if not hwnd or layered.foreground_window() != hwnd:
                    # Фокус не там, где мы брали текст. Замена уничтожила бы
                    # чужой документ, поэтому не вставляем: результат в буфере,
                    # человек ставит его сам куда хотел.
                    #
                    # Прежний буфер тут НЕ возвращаем намеренно: результат
                    # сейчас единственная копия работы, и затереть его своей
                    # уборкой значило бы выбросить её (та же логика, что у
                    # insert() при отказе UIPI).
                    log("преобразование: окно сменилось, вставку не делаем")
                    to_clipboard(result)
                    self.ui(self.overlay.show_error,
                            "окно сменилось - результат в буфере, Ctrl+V")
                    return
                self._inserting = True
                try:
                    if took_all:
                        select_all()
                    ok = insert(result, mode=self.cfg.get("insert_mode", "paste"),
                                restore=False)
                finally:
                    self._insert_window_closes()
                if self.cfg.get("restore_clipboard", True) and old_clip is not None:
                    time.sleep(0.3)
                    _set_clipboard_text(old_clip)
                # Отмену не взводим - по той же причине, что у правки голосом:
                # мы вставили ПОВЕРХ выделения, и стереть вставленное значит
                # оставить дыру вместо текста.
                self._undo_text, self._undo_armed = None, False
                if ok:
                    log(f"преобразование {t['id']}: {len(text)} -> {len(result)} "
                        f"символов за {time.time() - t0:.2f}с")
                    self.ui(self.overlay.show_done, "готово")
                else:
                    self.ui(self.overlay.show_error, "не удалось вставить")
            except Exception as e:  # noqa: BLE001
                log(f"преобразование не вышло: {e}")
                self._restore_clip(old_clip)
                self.ui(self.overlay.show_error, "не получилось - текст не тронут")

    def _restore_clip(self, old_clip) -> None:
        """Вернуть буфер человека, если он был и если он вообще нужен.

        Общий хвост неудачных путей преобразования: grab_text затёр буфер полем,
        а раз результат никуда не лёг - буфер должен подтверждать, что для
        человека не произошло ничего."""
        if self.cfg.get("restore_clipboard", True) and old_clip is not None:
            _set_clipboard_text(old_clip)

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
        self._held = {"hold": False, "toggle": False, "command": False,
                      "clipboard": False, "inbox": False}

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
        # Все жесты, кроме переключателя, кончаются отпусканием: и обычная
        # диктовка, и правка голосом, и «в буфер», и «в файл».
        if mode != "toggle" and self._recording and self._rec_mode == mode:
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
        self._stream_start()
        self._music_pause()

    def _music_pause(self) -> None:
        """Остановить музыку - в потоке.

        Замер уровня на выходе стоит около 150 мс (два опроса с паузой), и
        держать на них начало записи нельзя: человек уже говорит.
        """
        if not self.cfg.get("pause_music", True):
            return
        if self._music is None:
            import media

            self._music = media.Music(log)
        threading.Thread(target=self._music.pause, daemon=True).start()

    def _music_resume(self) -> None:
        if self._music is not None:
            self._music.resume()

    def _stream_start(self) -> None:
        """Разбирать речь, пока человек ещё говорит.

        Смысл в том, что сказанное минуту назад уже не изменится, и ждать конца
        фразы, чтобы начать работу, незачем. К отпусканию клавиши остаётся
        хвост в пару секунд - и ожидание перестаёт зависеть от длины речи.

        Командный режим не трогаем: там записывается короткое указание вроде
        «сделай короче», резать нечего.
        """
        self._stream = None
        if not self.cfg.get("stream_asr", True) or self._rec_mode == "command":
            return
        if not self._ready or not self.transcriber.loaded:
            return
        self._stream = streaming.Stream(
            self.transcriber.transcribe, log,
            min_tail=streaming.min_tail_sec(self.cfg))
        self._stream_thread = threading.Thread(target=self._stream_work, daemon=True)
        self._stream_thread.start()

    def _stream_work(self) -> None:
        """Рабочий поток разбора на ходу.

        Осторожность здесь дороже скорости. Пока крутится модель, микрофону
        нужен процессор, чтобы не потерять звук, а хуку клавиатуры - чтобы
        уложиться в свои 300 мс. Поэтому: просыпаемся раз в полсекунды, а не
        крутимся в цикле, и берёмся за работу, только когда накопилось
        достаточно и нашлась настоящая пауза.

        Ошибку глотаем и молча выключаем разбор на ходу: конец диктовки после
        этого просто распознает всё целиком, как раньше. Потерять текст из-за
        ускорения нельзя.
        """
        st = self._stream
        try:
            while self._recording and st is self._stream:
                # 0.2 с, а не 0.5: окно между «замолчал» и «отпустил»
                # бывает в треть секунды, и полусекундный сон его проспит.
                time.sleep(0.2)
                if not self._recording:
                    break
                audio, total = self.recorder.since(st.consumed)
                if not st.feed(audio, total):
                    # Резать нечего - может, человек уже договорил. Тогда
                    # разберём остаток заранее: пока он собирается отпустить
                    # клавишу, ответ будет готов.
                    st.speculate(audio, total)
        except Exception as e:  # noqa: BLE001
            log(f"разбор на ходу отключён: {type(e).__name__}: {e}")
            if st is self._stream:
                self._stream = None

    def _finish_recording(self) -> None:
        if not self._recording:
            return
        self._recording = False
        audio = self.recorder.stop()
        # Музыку возвращаем сразу, не дожидаясь распознавания: человек
        # договорил, и тишина ему больше не нужна.
        self._music_resume()
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
        # Куда отдавать текст, решает жест, которым начали. Дальше конвейер
        # общий: распознавание, чистка и история у всех троих одни и те же.
        dest = self._rec_mode if self._rec_mode in ("clipboard", "inbox") else "insert"
        # Запись держим до следующей: если распознавание или вставка упадут,
        # фраза не потеряна - «Повторить последнюю» в трее прогонит её заново.
        # Память дешёвая: минута речи в float32 - ~4 МБ.
        self._last_audio, self._last_dur, self._last_dest = audio, dur, dest
        threading.Thread(target=self._process, args=(audio, dur, dest),
                         daemon=True).start()

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
                    self.ui(self.overlay.show_error, self._llm_missing())
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
                    # «Не смог выполнить» звучало как отказ по существу
                    # («понял, но не буду»), а причина почти всегда другая:
                    # Ollama не ответила. Заодно говорим главное - выделенный
                    # текст на месте, ничего не испорчено.
                    self.ui(self.overlay.show_error,
                            "правка текста не ответила - текст не тронут")
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
            # «Ошибка команды» - это заголовок строки в журнале, а не фраза
            # человеку: она не говорит ни что случилось, ни что делать.
            self.ui(self.overlay.show_error, "не получилось - попробуйте ещё раз")
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
        # Повторяем и назначение тоже: диктовка в файл, прогнанная заново,
        # обязана лечь в файл, а не вставиться в то окно, где человек сейчас.
        threading.Thread(target=self._process,
                         args=(audio, getattr(self, "_last_dur", 0.0),
                               getattr(self, "_last_dest", "insert")),
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
        self._music_resume()
        # Разобранное на ходу выбрасываем вместе с записью: человек передумал,
        # и держать половину его фразы незачем.
        self._stream = None
        try:
            self.recorder.stop()
        except Exception as e:  # noqa: BLE001 - отмена не должна падать
            log(f"mic stop on cancel: {e}")
        beep(440, 80, self.cfg.get("sounds", True))
        self.ui(self.overlay.hide)
        self._set_tray_state("idle")
        log("recording cancelled")

    def _process(self, audio, dur: float, dest: str = "insert") -> None:
        """Распознать и отдать текст. dest решает, кому именно:

            insert    - в активное окно, как было всегда;
            clipboard - в буфер обмена, ничего никуда не вставляя;
            inbox     - в конец файла из inbox_path.

        Всё до доставки одинаково для всех троих - распознавание, чистка,
        команды, история. Новый жест не заводит второго конвейера: он выбирает
        только последний шаг.
        """
        try:
            # лок держим на весь конвейер, включая вставку: если распознать
            # вторую фразу, пока вставляется первая, текст уедет не в том порядке
            # Звук на диск ДО распознавания. Стоило это пятнадцати минут чужой
            # работы: распознавание упало, исключение ушло в лог, а запись жила
            # только в этой переменной - и исчезла вместе с ней. Ни текста, ни
            # звука, ни возможности повторить.
            #
            # Теперь при любом падении дальше по конвейеру wav остаётся на
            # диске, и его можно распознать заново. При успехе файл стирается
            # тут же и места не занимает.
            saved = recordings.save(audio)
            with self._work_lock:
                t0 = time.time()
                # Кто в фокусе - спрашиваем ДО распознавания, а не после: пока
                # модель думает, человек может успеть переключить окно, а тон
                # надо подобрать под то, куда он диктовал. Оверлей фокус не
                # забирает (WS_EX_NOACTIVATE), так что видим настоящее окно.
                process = layered.foreground_process()
                # Модель могли отпустить за простоем - поднимаем обратно. Под
                # тем же _work_lock, поэтому две фразы подряд не устроят двух
                # загрузок.
                if not self.transcriber.loaded:
                    self.ui(self.overlay.show_downloading, "просыпаюсь")
                    self.transcriber.load()
                    self.ui(self.overlay.show_processing)
                self._last_use = time.time()
                # Разбор на ходу: пока человек говорил, начало речи уже
                # разобрано. Остаётся хвост - те секунды, что он произнёс
                # последними. Отсюда и вся выгода: ожидание больше не зависит
                # от длины речи.
                st, self._stream = self._stream, None
                lat_spec = 0
                _t = time.perf_counter()
                if st is not None and st.runs:
                    tail = audio[st.consumed:]
                    text = st.finish(tail)
                    streamed, tail_sec = st.consumed / 16000, tail.size / 16000
                    if st.spec_hit:
                        lat_spec = 1
                else:
                    text = self.transcriber.transcribe(
                        audio, on_part=lambda i, n: self.ui(
                            self.overlay.show_downloading, f"часть {i} из {n}"))
                    streamed, tail_sec = 0.0, audio.size / 16000
                lat = {"asr": time.perf_counter() - _t}
                # Что услышала модель ДО чистки. Нужно, чтобы потом показать,
                # что программа за вас исправила, и какое слово она путает чаще
                # прочих, - без этого такой счёт не восстановить задним числом.
                raw = text
                # Говорили по-английски? Тогда у нас на руках не текст, а
                # английские звуки, записанные русскими буквами, - «дуис пик
                # инглиш». Переспрашиваем ту же запись моделью, которая пишет
                # латиницей, и отдаём её ответ. Русскую фразу это не стоит
                # ничего: одна проверка текста без звука и без модели.
                _t = time.perf_counter()
                english = self._english_retry(text, audio)
                lat["english"] = time.perf_counter() - _t
                _t = time.perf_counter()
                if english:
                    # Чистку английскому не отдаём, и это не экономия. Весь
                    # cleaner устроен под русский: словарь, паразиты, правила
                    # запятых, приведение к русской заглавной. Знаки и
                    # заглавные в английском уже расставила сама модель.
                    text = english
                    lat["punct"] = 0.0
                else:
                    text = clean(text, self.cfg, log, process=process)
                    lat["punct"] = cleaner.last_punct_sec
                lat["clean"] = time.perf_counter() - _t
                # Команды - ПОСЛЕ полировки: LLM не должна их видеть, иначе
                # перепишет или послушается, оба исхода хуже.
                before_commands = text
                text, want_enter = extract_commands(text, self.cfg)
                # Вопрос по голосу - но только если в конце не было команды.
                # Сказали «нажми энтер» - последние полсекунды записи это она,
                # и интонация там про команду, а не про фразу. Разбирать её
                # значило бы гадать по чужому хвосту.
                #
                # И не для английского: там знак уже поставила своя модель, а
                # правила подъёма тона в intonation.py писались под русскую
                # ИК-3 - в английском вопрос звучит иначе.
                if (self.cfg.get("question_by_voice", True)
                        and not english and text == before_commands):
                    import intonation

                    try:
                        text = intonation.maybe_question(text, audio)
                    except Exception as e:  # noqa: BLE001 - знак не стоит фразы
                        log(f"интонация: {e}")
                elapsed = time.time() - t0
                if not text:
                    # Молча спрятать пилюлю нельзя: человек говорил и ждёт
                    # текста. Скажем прямо, что вставлять нечего.
                    log(f"empty result ({dur:.1f}s audio)")
                    self.ui(self.overlay.show_error, "ничего не расслышали")
                    return
                if dest == "insert":
                    # Отправлять ли сообщение самим: список приложений в
                    # настройках. Голосовое «нажми энтер» при этом никуда не
                    # делось - оно работает везде и перебивает список.
                    want_enter = want_enter or self._auto_enter_here(process)
                    # Склейка с предыдущей вставкой: пробел спереди и строчная
                    # буква, если фраза продолжает мысль. Иначе две диктовки
                    # подряд слипаются в «первая фразаВторая фраза».
                    text = self._join_with_previous(text, process)
                    # После текста с Enter'ом хвостовой пробел - мусор в начале
                    # следующего сообщения.
                    out = text + (" " if self.cfg.get("append_space", True)
                                  and not want_enter else "")
                    ok, note, in_window = self._insert_here(out, want_enter, lat)
                else:
                    # Ни склейки, ни хвостового пробела, ни Enter: всё это про
                    # чужое поле, в которое мы сейчас и не целимся.
                    out = text
                    ok, note, in_window = self._put_aside(out, dest)
                if in_window:
                    # После Enter стирать нечего: текст уже улетел сообщением.
                    self._undo_text, self._undo_armed = \
                        (None, False) if want_enter else (out, True)
                    # Куда и когда вставили - чтобы следующая диктовка знала,
                    # продолжает она мысль или начинает новую.
                    self._last_insert = (process, time.time(), out) \
                        if not want_enter else None
            self._history(text, dur, process=process, raw=raw)
            n = len(text.split())
            # Одна строка на диктовку, по которой видно, куда ушло время.
            # Без неё любой спор о скорости решается на глазок, а этапов
            # пять и виноват каждый раз другой.
            log("задержка: "
                f"запись={dur:.1f}с на_ходу={streamed:.1f}с хвост={tail_sec:.1f}с | "
                + " ".join(f"{k}={v:.3f}" for k, v in lat.items())
                + f" | заготовка={lat_spec}"
                + f" | всего={sum(lat.values()):.3f}с")
            log(f"ok: {dur:.1f}s audio -> {len(text)} chars in {elapsed:.2f}s")
            if ok:
                # Текст доехал - запись больше не нужна. Стираем ТОЛЬКО здесь:
                # любой другой исход означает, что её ещё можно спасти.
                recordings.drop(saved)
                saved = ""
                # Пилюля называет место, а не только число. «Вставлено» и «в
                # буфере» - разные исходы, и человек должен знать, какой из них
                # у него сейчас: во втором случае ему остаётся нажать Ctrl+V.
                # Про буфер говорим только когда там правда лежит диктовка:
                # обещание на пустом месте было бы враньём.
                self.ui(self.overlay.show_done,
                        _words_label(n) + (f" · {i18n.t(note)}" if note else ""))
            else:
                self.ui(self.overlay.show_error, i18n.t(note))
        except Exception as e:  # noqa: BLE001
            log(f"process error: {e}")
            if saved:
                # Молчать здесь нельзя. Человек, наговоривший десять минут,
                # должен узнать, что его речь цела, - иначе он решит, что
                # работа пропала, и будет прав ровно наполовину.
                log(f"запись сохранена: {saved}")
                self.ui(self.overlay.show_error,
                        "не вышло - запись цела, см. «О программе»")
                self.ui(self._tell_saved, dur)
            else:
                self.ui(self.overlay.show_error, "не получилось - нажмите ещё раз")
        finally:
            # Сверх лимита не копим: спасение не должно стать свалкой.
            recordings.prune()
            self._set_tray_state("idle")

    # ---------- английская речь ----------

    def _english_retry(self, text: str, audio) -> str:
        """Английскую фразу переспросить моделью, которая пишет латиницей.

        Возвращает английский текст или пустую строку - тогда всё идёт как
        всегда, кириллицей и через обычную чистку.

        Порядок проверок от дешёвой к дорогой: выключатель, разбор текста,
        наличие модели, и только потом сам звук. На русской фразе дальше
        второго шага дело не заходит.

        Ошибку глотаем молча и отдаём кириллицу. Английский - улучшение, а не
        обязанность, и уронить из-за него обычную диктовку нельзя.
        """
        if not self.cfg.get("english_speech", True):
            return ""
        try:
            if not language.looks_english(text):
                return ""
        except Exception as e:  # noqa: BLE001 - разбор текста не стоит фразы
            log(f"определитель языка: {e}")
            return ""
        log(f"похоже на английский ({language.ru_score(text):.2f}): {text!r}")
        if not language.installed():
            self.ui(self._tell_english_missing)
            return ""
        try:
            en = language.shared(log)
            if not en.loaded:
                # Полсекунды на подъём, и человеку надо видеть, за что он
                # ждёт: слово на пилюле вместо молчаливой паузы.
                self.ui(self.overlay.show_downloading, i18n.t("английский"))
                en.load()
                self.ui(self.overlay.set_hint, "")
                self.ui(self.overlay.show_processing)
            out = en.transcribe(audio)
        except Exception as e:  # noqa: BLE001
            log(f"английский переспрос не вышел: {type(e).__name__}: {e}")
            return ""
        # Ответ без единой латинской буквы - это не английский, а что-то
        # пошедшее не так. Отдаём то, что было: хуже кириллицы только пустота.
        if not out or not any(c.isascii() and c.isalpha() for c in out):
            log(f"переспрос вернул не английский: {out!r} - оставляю как было")
            return ""
        log(f"английский: {out!r}")
        return out

    def _tell_english_missing(self) -> None:
        """Английский услышали, а писать его нечем. Главный поток.

        Так бывает у тех, кто обновился со старой версии: мастер первого
        запуска они проходили давно, а модель добавилась только сейчас.
        Молчать нельзя - человек увидит «дуис пик инглиш» и решит, что
        программа так и умеет. И заставлять его искать кнопку в настройках
        не за что: качаем сами, один раз, и говорим сколько.
        """
        if self._english_told:
            return
        self._english_told = True
        threading.Thread(target=self._fetch_english_bg, daemon=True).start()
        if self.tray is None:
            return
        self.tray.showMessage(
            "Похоже, вы говорили по-английски",
            f"Программа умеет писать английский как положено - буквами. "
            f"Догружаю недостающее, {language.SIZE_MB} МБ, один раз. "
            f"Следующая фраза уже будет английской.")

    def _fetch_english_bg(self) -> None:
        """Догрузить английскую модель. Отдельным ПРОЦЕССОМ, как и основную.

        Причина та же (см. download_model_cli): сборку сессии делает C-код,
        который держит GIL секундами, и всё это время окно не отвечает, а хук
        клавиатуры не укладывается в свои 300 мс.
        """
        import subprocess

        try:
            r = subprocess.run(
                _download_cmd(language.DOWNLOAD_ID),
                capture_output=True, text=True, encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as e:  # noqa: BLE001
            log(f"английская модель: загрузчик не запустился: {e}")
            return
        if r.returncode == 0 and language.installed():
            log(f"английская модель готова, {language.size_mb():.0f} МБ")
        else:
            # Не получилось - пусть попробует ещё раз на следующей английской
            # фразе. Одна неудачная сеть не должна выключать возможность.
            self._english_told = False
            log("английская модель не скачалась: "
                + (r.stderr or r.stdout or "").strip()[:300])

    # ---------- куда уходит распознанный текст ----------
    #
    # Три дороги и один общий выход. Общий выход - буфер обмена: он есть всегда
    # и работает везде, где не работает больше ничего, - в окне под
    # администратором, поверх полноэкранной игры, при занятом файле инбокса.
    # Поэтому фолбэк здесь ровно один (_to_clipboard), и каждая дорога
    # сворачивает на него, а не заводит свой.
    #
    # Обе доставки отвечают одинаковой тройкой:
    #   ok        - текст доехал хоть куда-то, и человек его не потерял;
    #   note      - чем дополнить пилюлю («в буфере», «в файле»); пусто - просто
    #               вставилось, дополнять нечем;
    #   in_window - текст лёг именно в активное окно. Только в этом случае можно
    #               взводить отмену: Backspace стирает символы ТАМ, где курсор,
    #               и после «в буфере» он съел бы чужой текст.

    def _to_clipboard(self, text: str) -> bool:
        """Общий фолбэк: положить текст в буфер обмена."""
        if to_clipboard(text):
            return True
        # Буфер занят намертво (обычно чужим менеджером буфера). Это последняя
        # дверь, и раз она закрыта - говорим об этом в журнал, а человеку
        # ответит пилюля.
        log("буфер обмена занят - текст отдать некуда")
        return False

    def _insert_here(self, out: str, want_enter: bool,
                     lat: dict) -> tuple[bool, str, bool]:
        """Вставить в активное окно. Не вышло - текст остаётся в буфере.

        Длинную диктовку оставляем в буфере обмена и при удачной вставке, даже
        если человек просил возвращать скопированное.

        Владелец спросил: надиктовал много, а не вставилось - что ему делать?
        Ответа не было. Мы шлём Ctrl+V и не всегда можем узнать, дошёл ли он:
        окно могло потерять фокус, поле могло не принимать вставку. Мы считали
        такую диктовку вставленной и возвращали в буфер то, что человек
        копировал раньше, - то есть своими руками стирали последний след его
        десяти минут.

        Теперь для длинного текста уборка отменяется: пропажа абзаца дороже,
        чем не возвращённая ссылка. А случай «система не пустила наши нажатия»
        (окно выше по правам) inserter теперь различает и честно отвечает False
        - тогда диктовка остаётся в буфере целиком, и пилюля про это говорит.
        """
        long_text = len(out) >= _KEEP_IN_CLIPBOARD_CHARS
        self._inserting = True
        _t = time.perf_counter()
        try:
            ok = insert(
                out,
                mode=self.cfg.get("insert_mode", "paste"),
                restore=(self.cfg.get("restore_clipboard", True)
                         and not long_text),
            )
            if ok and want_enter:
                time.sleep(0.05)   # дать окну дожевать вставку
                press_enter()
        finally:
            lat["insert"] = time.perf_counter() - _t
            self._insert_window_closes()
        if ok:
            return True, ("и в буфере" if long_text else ""), True
        log("вставить не вышло - оставляю текст в буфере")
        if self._to_clipboard(out):
            return True, "в буфере, нажмите Ctrl+V", False
        return False, "не вставилось и буфер занят", False

    def _put_aside(self, out: str, dest: str) -> tuple[bool, str, bool]:
        """Отдать текст мимо активного окна: в буфер или в файл инбокса."""
        if dest == "clipboard":
            if self._to_clipboard(out):
                log(f"в буфер: {len(out)} символов")
                return True, "в буфере", False
            return False, "буфер обмена занят", False

        import inbox

        path = str(self.cfg.get("inbox_path") or "").strip()
        if inbox.append(path, out):
            log(f"в файл {path}: {len(out)} символов")
            return True, "в файле", False
        # Файл занят или лежит не там - текст не пропадает, а уходит тем же
        # общим фолбэком. Второго способа спасти диктовку мы не заводим.
        log(f"инбокс недоступен ({path!r}) - отдаю в буфер")
        if self._to_clipboard(out):
            return True, "файл занят - текст в буфере", False
        return False, "файл занят и буфер тоже", False

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

    def _tell_saved(self, dur: float) -> None:
        """Сказать вслух, что запись цела. Главный поток."""
        if self.tray is None:
            return
        mins = int(dur // 60)
        how = f"{mins} мин {int(dur % 60)} с" if mins else f"{int(dur)} с"
        self.tray.showMessage(
            "Запись сохранена",
            f"Распознать не вышло, но {how} речи целы. "
            f"«О программе» → «Несохранённые записи»: можно распознать заново.")

    def _history(self, text: str, dur: float, process: str = "",
                 raw: str = "", source: str = "") -> None:
        """Строка в history.jsonl. Ничего не пишем, если история выключена.

        Кроме текста и длительности пишем ещё два поля, и оба - ради статистики
        о том, КАК человек диктует:

            app  - куда вставили ('outlook.exe'). По нему потом видно, где вы
                   диктуете больше всего и в какое время;
            raw  - что услышала модель до чистки. Только если отличается от
                   итога: совпадает - писать нечего, а история и так самое
                   тяжёлое, что мы храним;
            src  - откуда взялась речь. Пусто - микрофон, 'file' - расшифровка
                   готового файла. Нужно, чтобы «Историю» можно было читать:
                   часовой подкаст среди диктовок неотличим от диктовки на час,
                   а это разные вещи, и статистика «сколько вы наговорили» на
                   чужом подкасте врала бы в свою пользу.

        Заводим сейчас, хотя показывать пока негде, и это осознанно: такие
        числа считаются по накопленному. Добавь мы поля вместе с экраном - он
        открылся бы пустым, и первые осмысленные цифры человек увидел бы через
        месяц. Пусть копится заранее.

        Новой категории данных здесь не появляется: и то и другое - part той же
        диктовки, лежит в том же файле на той же машине и выключается тем же
        тумблером «Вести историю».
        """
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
                            **({"app": process} if process else {}),
                            **({"raw": raw} if raw and raw != text else {}),
                            **({"src": source} if source else {}),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except OSError:
            pass

    # ---------- окно ----------

    def _win_args(self) -> dict:
        """Чем кормить окно на QML: общий набор колбэков в приложение.

        Именно колбэков, а не состояния. Backend окно заводит себе само
        (SettingsWindow.__init__), и каждое открытие перечитывает конфиг с
        диска (open -> reload), так что правка снаружи доезжает сама. А вот
        «поставить Ollama» или «переслушать запись» умеет только приложение, и
        руки для этого даёт оно.

        Отдельным методом, а не семью строками в вызове: так видно списком, что
        именно окно просит у приложения, и добавить восьмое - правка в одном
        месте, а не поиск конструктора среди двух сотен строк.
        """
        return dict(
            on_onboarding=self._open_onboarding,
            update_fn=lambda: self._update,
            do_update=self._do_update,
            llm_install=self.install_ollama,
            llm_busy=self.ollama_busy,
            redo_fn=self._redo_recording,
            tidy_fn=self._tidy_note,
            transcribe_fn=self.transcribe_file)

    def _open_settings(self) -> None:
        """Окно программы. Одно на все двери.

        Сюда ведут все пути: клик по значку в трее, ярлык из «Пуска», пункт
        меню «Настройки…» и просьба от второго экземпляра (poke). Разными их
        делала пора двух окон - маленькое из трея и большое из меню; окно снова
        одно, и разводить входы больше некуда. Открывается оно на «Главной»,
        так что пришедший «посмотреть, что надиктовано» попадает именно туда, а
        настройки ждут второй группой в панели.
        """
        if self.cfg.get("ui.web", False) and self._open_settings_web():
            return

        from settings_qt import SettingsWindow

        if self.settings is None:
            self.settings = SettingsWindow(
                self._on_config_change, self._on_hotkey_capture,
                self._info, HISTORY_PATH, LOG_PATH, **self._win_args())
        self.settings.open()

    def _open_settings_web(self) -> bool:
        """Открыть настройки страницей. True - получилось.

        **Обе версии окна живут рядом, и это условие плана, а не осторожность
        сверх меры.** Страница проверена машиной целиком - типы, доступность,
        мост, - но ни разу не открывалась человеком: ни одна из восьми страниц,
        ни мастер. Выбросить работающее QML-окно раньше, чем новое посмотрели
        глазами, значит оставить владельца без настроек, если что-то не так.

        Выключатель в конфиге (`ui.web`), а не сборкой: переключиться туда и
        обратно должно быть можно на живой программе, ничего не пересобирая.

        Не вышло - возвращаем False, и открывается прежнее окно. Молча падать
        тут нельзя: человек нажал «Настройки», и окно обязано появиться хоть
        какое-то.
        """
        try:
            import bridge
            import webwindow

            if self._web is None:
                from settings_qt import Backend

                if self._web_backend is None:
                    self._web_backend = Backend(
                        self._on_config_change, self._on_hotkey_capture,
                        self._info, HISTORY_PATH, LOG_PATH, **self._win_args())
                extra = []
                try:
                    from onboarding_qt import _Extra

                    extra.append(_Extra(self))
                except Exception as e:  # noqa: BLE001 - мастер тут не главное
                    log(f"мост без объекта мастера: {e}")
                self._bridge = bridge.Bridge(self._web_backend, extra)
                self._web = webwindow.WebWindow(
                    self._bridge, self.overlay.tokens, self._web_lang(), log)
            self._web.show()
            return True
        except Exception as e:  # noqa: BLE001
            log(f"настройки страницей не открылись, беру прежнее окно: "
                f"{type(e).__name__}: {e}")
            return False

    def _web_lang(self):
        from theme_qt import Lang

        return Lang()

    def _redo_recording(self, path: str) -> None:
        """Распознать сохранённую запись заново - по кнопке из «О программе».

        В своём потоке: длинная запись режется на куски и считается минуты, а
        главный поток Qt держит окно. Заморозить его на минуту - значит
        показать человеку «программа зависла» ровно в тот момент, когда она
        спасает его работу.
        """
        threading.Thread(target=self._redo_work, args=(path,), daemon=True).start()

    def _redo_work(self, path: str) -> None:
        import recordings

        try:
            audio, _sr = recordings.load(path)
        except Exception as e:  # noqa: BLE001
            log(f"не прочитал сохранённую запись: {e}")
            self.ui(self._flash_settings, "не прочитать запись", "danger")
            return
        with self._work_lock:
            try:
                if not self.transcriber.loaded:
                    self.transcriber.load()
                text = self.transcriber.transcribe(audio)
                text = clean(text, self.cfg, log)
            except Exception as e:  # noqa: BLE001
                log(f"повторное распознавание не вышло: {e}")
                self.ui(self._flash_settings, "снова не вышло - запись цела",
                        "danger")
                return
        if not text:
            self.ui(self._flash_settings, "ничего не расслышали", "danger")
            return
        _set_clipboard_text(text)
        self._history(text, len(audio) / 16000.0)
        recordings.drop(path)
        n = len(text.split())
        log(f"повторно распознано: {n} слов из {os.path.basename(path)}")
        self.ui(self._flash_settings,
                f"{n} {plural(n, 'слово', 'слова', 'слов')} - в буфере обмена, "
                f"вставьте куда нужно", "accent")

    def _flash_settings(self, msg: str, kind: str) -> None:
        if self.settings is not None:
            self.settings.backend.flashed.emit(msg, kind)
            self.settings.backend.changed.emit()

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
        # Имя модели Ollama на диске не хранится - его находит автоопределение
        # при старте и кладёт только в память. А `new` прочитан с диска, где в
        # llm.model пусто, и update() затирал найденное.
        #
        # Стоило тронуть любую настройку - и правка текста умирала до
        # перезапуска: запросы уходили с пустым именем модели и получали 404.
        # Молча: в журнал строка есть, человеку - «отдаём сырой текст». Владелец
        # так прожил сутки и узнал об этом случайно.
        #
        # Возвращаем найденное имя на место. _llm_note хранит его с момента
        # автоопределения ровно для таких случаев.
        llm = self.cfg.get("llm")
        if isinstance(llm, dict) and not llm.get("model") and self._llm_note:
            llm["model"] = self._llm_note
            log(f"настройки затёрли имя модели - вернул {self._llm_note}")
        # Все сочетания разом, а не три главных. Назначение нового хоткея и так
        # перевешивает биндЫ (_on_hotkey_capture), а вот СНЯТИЕ идёт обычной
        # записью в конфиг - и снятое сочетание продолжало работать до
        # перезапуска. Здесь же и inbox_path: без файла жест «в файл» не
        # вешается вовсе, значит выбор файла обязан его включить.
        hk_keys = ("hotkey_hold", "hotkey_toggle", "hotkey_command",
                   "hotkey_transform", "hotkey_notes", "hotkey_clipboard",
                   "hotkey_inbox", "inbox_path", "undo_hotkey")
        if any(old.get(k) != new.get(k) for k in hk_keys):
            self._hotkey_bind()
            self._set_tray_state(self._tray_state)   # в подсказке трея - биндЫ
        mic_keys = ("mic_device", "keep_mic_open", "pre_buffer_sec")
        if any(old.get(k) != new.get(k) for k in mic_keys) and not self._recording:
            self._rebuild_recorder()
        model_keys = ("model", "quantization", "device")
        if any(old.get(k) != new.get(k) for k in model_keys):
            self._reload_model_bg()
        # Раскладка - такой же токен оформления, как краска: меняется тем же
        # путём и применяется на лету, без пересборки окна.
        if old.get("ui_language") != new.get("ui_language"):
            i18n.set_language(str(new.get("ui_language") or "ru"))
            # Строки в QML - это привязки к L.t(), и сигнал заставляет их
            # пересчитаться. Пересобирать окно, как когда-то с темой, не надо.
            for win in (self.settings, self.onboarding):
                lang = getattr(win, "lang", None)
                if lang is not None:
                    lang.retranslate()
            log(f"язык интерфейса: {new.get('ui_language')}")
        if (old.get("theme") != new.get("theme")
                or old.get("layout") != new.get("layout")):
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
        T.set_layout(str(self.cfg.get("layout") or "cards"))
        icons.retheme()
        self.overlay.retheme()
        self._set_tray_state(self._tray_state)
        if self.settings is not None:
            self.settings.retheme()
        # Мастер первого запуска - тоже окно, и тему в нём выбирают ВТОРЫМ
        # шагом. Про него забыли, и получилось так: человек нажимает «тёмная»,
        # краски приложения меняются, а окно мастера остаётся со старыми
        # токенами - перекрашивается наполовину, случайными кусками.
        #
        # Владелец описал это как «нажал переключатель - всё пропало, кнопка
        # «Дальше» исчезла», и до конца мастер не прошёл. Кнопка никуда не
        # девалась: она стала белой на белом.
        if getattr(self, "onboarding", None) is not None:
            self.onboarding.retheme()
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
                # Говорим и про беду, и про то, что диктовка цела: старая
                # модель осталась в работе, и «не удалось загрузить модель»
                # пугало человека молчанием о том, работает ли что-нибудь.
                self.ui(self.overlay.show_error,
                        "новая модель не загрузилась - работает прежняя")
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
        # Служебное для статус-строки «Главной» (settings_qt.statusInfo).
        # Подчёркивание - метка «не показывать»: about() такие ключи
        # пропускает, и на страницу «О программе» они не попадают. Здесь, а
        # не в конфиге окна, потому что оба ответа знает только приложение:
        # устройство выбирает onnxruntime при загрузке (провайдера может не
        # оказаться, и «cuda» тихо станет «cpu»), а модель могли сменить в
        # другом окне - его копия конфига об этом ещё не знает.
        info["_device"] = self.transcriber.device
        info["_model"] = str(self.cfg.get("model") or "")
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
                self.tray.setToolTip(f"FlowLocal - {self._status()}")
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
        # Клик по шарику - тот же путь, что и пункт меню. Человек, которому
        # сказали «нажмите, чтобы обновить», нажимает на сообщение, а не
        # идёт искать меню.
        self.tray.messageClicked.connect(self._on_balloon_clicked)
        self._act_update.triggered.connect(self._do_update)
        self._act_update.setVisible(False)
        menu.addAction("Заметки…").triggered.connect(self.open_notes)
        # Вторая дверь к расшифровке файла: первая - перетащить его на окно.
        # Обе нужны. Перетаскивание быстрее, но про него не догадываются, пока
        # не покажут; пункт меню видно списком, и он же работает, когда окно
        # закрыто и тащить не на что.
        menu.addAction("Расшифровать файл…").triggered.connect(self._pick_audio_file)
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
        # Двойной клик по значку - окно программы. Оно открывается на «Главной»,
        # то есть ровно там, зачем по значку и кликают: работает ли программа и
        # что она надиктовала.
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
            die("Не удалось загрузить распознавание речи. "
                "Помогает переустановка программы.", f"{type(e).__name__}: {e}")
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
        #
        # Но одного меню мало, и это выяснилось на владельце: приложение нашло
        # обновление, честно записало в лог - и не сказало ему ничего. Чтобы
        # узнать, надо было догадаться кликнуть правой кнопкой по значку в
        # трее, который Windows вдобавок прячет под шеврон. То есть функция
        # была, а дойти до неё человек не мог. Ровно то, за что мы ругали
        # «нужна Ollama».
        #
        # Шарик - не всплывающее окно: он не забирает фокус, не мешает печатать
        # и уходит сам. Тем же способом мы уже говорим «FlowLocal запущен».
        self.ui(self._notify_update, found)

    def _do_update(self) -> None:
        """Скачать и поставить. Зовётся из трея, работает своим потоком."""
        if not self._update:
            return
        info = self._update

        def work():
            try:
                self.ui(self.overlay.show_downloading, f"обновление {info['version']}")
                # Прогресс шёл в никуда: download() умеет о нём докладывать, а
                # мы вызывали его без колбэка. На экране 70 МБ выглядели как
                # неподвижная ниточка - владелец справедливо спросил, что это
                # за загрузка такая.
                path = updater.download(
                    info["url"],
                    lambda f: self.ui(self.overlay.set_progress, f))
                log(f"обновление скачано: {path}")
                self.ui(self.overlay.show_downloading, "устанавливаю")
                self.ui(self.overlay.set_progress, 1.0)
                updater.install(path)
                # Уходим сами: пока мы живы, установщик не заменит наш .exe.
                self.ui(self._shutdown)
            except Exception as e:  # noqa: BLE001
                log(f"обновление не удалось: {e}")
                self.ui(self.overlay.show_error, "не удалось обновить")

        threading.Thread(target=work, daemon=True).start()

    # ---------- установка Ollama: один хозяин на всё приложение ----------

    def install_ollama(self, on_stage=None) -> None:
        """Поставить Ollama и модель. Зовётся из настроек и из мастера.

        Хозяин один, и это главное в этой функции. Раньше установку запускали
        двое - Backend настроек и _Extra мастера, - каждый своим потоком и со
        своими сигналами. Отсюда две беды: нажать «Установить» можно было
        дважды и получить две качалки на одну машину, а закрыв окно, человек
        терял и полосу, и всякий признак того, что что-то идёт. Три гигабайта
        качаются минутами - окно за это время закроют обязательно.

        Поэтому ход показывает пилюля: она поверх всех окон и переживает
        закрытие любого из них. Подписчики (окна, пока открыты) получают то же
        самое своим колбэком и рисуют полосу у себя.
        """
        import ollama_setup as O

        if on_stage is not None and on_stage not in self._ollama_subs:
            self._ollama_subs.append(on_stage)
        if self._ollama_busy:
            return                      # уже качаем - второй раз не начинаем
        self._ollama_busy = True

        def tell(stage: str, frac: float, total: float, done=None) -> None:
            for cb in list(self._ollama_subs):
                try:
                    cb(stage, frac, total, done)
                except Exception:  # noqa: BLE001 - окно могли закрыть
                    self._ollama_subs.remove(cb)

        # Последний этап помним: ollama_setup заканчивает работу этапом-фразой
        # («не удалось скачать - проверьте интернет»), и это единственное
        # место, где известно, ЧТО именно не вышло. Без него пилюля говорила
        # «не удалось установить» одинаково на оборванную закачку, на
        # неудавшуюся установку и на молчащий сервер - то есть не говорила
        # ничего.
        last = {"stage": ""}

        def stage(name: str, frac: float, total: float) -> None:
            last["stage"] = name
            self.ui(self.overlay.show_downloading, name)
            self.ui(self.overlay.set_progress, frac)
            self.ui(tell, name, frac, total, None)

        def work() -> None:
            ok = False
            try:
                ok = O.ensure(on_stage=stage, log=log)
            except Exception as e:  # noqa: BLE001 - установка не роняет диктовку
                log(f"ollama install failed: {e}")
            if ok:
                llm = self.cfg.setdefault("llm", {})
                llm["enabled"] = True
                llm["model"] = O.DEFAULT_MODEL
                try:
                    C.save(self.cfg)
                except OSError:
                    pass
                self._llm_note = O.DEFAULT_MODEL
            self._ollama_busy = False
            # Итог виден и без окна: пилюля скажет «готово» или назовёт причину.
            # Про исключение (его текст ушёл в журнал строкой выше) на пилюле
            # не говорим ни слова - там ему не место.
            why = (last["stage"] if last["stage"] in O.FAILURES
                   else "не удалось установить")
            self.ui(self.overlay.show_done if ok else self.overlay.show_error,
                    "правка текста готова" if ok else why)
            self.ui(tell, "готово" if ok else "не удалось", 1.0 if ok else 0.0, 0, ok)

        threading.Thread(target=work, daemon=True).start()

    def ollama_busy(self) -> bool:
        return self._ollama_busy

    def _check_deaf(self) -> None:
        """Раз в минуту: не оглохли ли мы совсем.

        Отказ, ради которого это написано, стоит объяснить, потому что он
        неочевиден. Служебные потоки библиотеки `keyboard` - демоны. Умри
        любой из них, программа продолжит работать как ни в чём не бывало:
        окно открывается, иконка в трее на месте, настройки сохраняются. Не
        работает только главное. Демон умирает молча, в журнале пусто.

        Для программы, которую не видно, это худший вид поломки: снаружи он
        неотличим от «я неправильно нажал». Человек будет пробовать снова и
        снова, потом решит, что программа плохая, и удалит - так и не узнав,
        что достаточно было перезапустить.

        Поэтому: замечаем, говорим вслух и пробуем собраться заново. Молчать
        нельзя даже когда починить не вышло - сказать «оглох» полезнее, чем не
        сказать ничего.
        """
        if not platform_api.CAN_HOTKEYS:
            return          # хоткеев нет - и оглохнуть нечему (macOS)
        why = wakeup.listener_dead(keyboard)
        if not why or self._recording or self._capturing:
            return
        if self._deaf_told == why:
            return          # уже сказали и уже пробовали - не долбить каждую минуту
        self._deaf_told = why
        log(f"ОГЛОХ: {why}")
        if wakeup.can_revive(keyboard):
            try:
                wakeup.revive(keyboard, log)
                self._hotkey_unbind()
                self._hotkey_bind()
            except Exception as e:  # noqa: BLE001
                log(f"поднять не вышло: {type(e).__name__}: {e}")
            if not wakeup.listener_dead(keyboard):
                log("хоткеи снова живы")
                self._deaf_told = ""
                return
        else:
            # Половина потоков жива - поднимать нельзя, будет второй хук и
            # двойная вставка. Честно говорим человеку и не чиним наугад.
            log("поднять нельзя без риска задвоить вставку - прошу перезапуск")
        if self.tray is not None:
            self.tray.showMessage(
                "Диктовка не отвечает",
                "Горячие клавиши перестали работать. Перезапустите программу: "
                "правый клик по значку - «Выход», потом откройте заново.")

    def _maybe_unload_model(self) -> None:
        """Отпустить модель, если ей давно не пользовались.

        Проверяем раз в минуту, а не держим таймер на каждую диктовку: одно
        пробуждение в минуту на фоне «ноля в покое» - ничто, а лишний таймер,
        который заводится и снимается на каждую фразу, - лишний повод ошибиться.

        Во время записи и работы не трогаем: выдернуть модель из-под
        распознавания значит потерять фразу.
        """
        mins = int(self.cfg.get("unload_after_min") or 0)
        if mins <= 0 or not self._ready or self._recording:
            return
        if not self.transcriber.loaded:
            return
        if time.time() - self._last_use < mins * 60:
            return
        if not self._work_lock.acquire(blocking=False):
            return          # идёт распознавание - не мешаем
        try:
            self.transcriber.unload()
            # Английскую отпускаем той же рукой. Она поднимается за полсекунды,
            # а держать её в памяти между английскими фразами, которых у
            # большинства не будет вовсе, незачем.
            language.release()
        finally:
            self._work_lock.release()

    def _auto_enter_here(self, process: str) -> bool:
        """Отправлять ли сообщение самим в этом окне.

        Список ведёт человек: угадывать мессенджеры по имени exe - гиблое дело,
        их сотни, а цена ошибки высокая. Отправить недописанное сообщение в
        рабочий чат хуже, чем не отправить дописанное.
        """
        if not process:
            return False
        apps = self.cfg.get("auto_enter_apps") or []
        return any(str(a).lower() == process.lower() for a in apps)

    def _join_with_previous(self, text: str, process: str) -> str:
        """Склеить с предыдущей вставкой, если она была только что и там же.

        Две диктовки подряд слипались в «первая фразаВторая фраза»: хвостовой
        пробел ставится ПОСЛЕ текста, а курсор к моменту второй вставки стоит
        уже за ним - и всё равно выходило слитно, если пробел выключен.

        Три условия, и каждое нужно:
          - то же окно: в другом окне это другая мысль;
          - недавно: через час это уже не продолжение;
          - предыдущая фраза не кончилась точкой - иначе новая начинает
            предложение, и строчная буква была бы ошибкой.
        """
        if not self.cfg.get("smart_join", True) or not text:
            return text
        last = getattr(self, "_last_insert", None)
        if not last:
            return text
        where, when, prev = last
        if where != process:
            return text
        if time.time() - when > float(self.cfg.get("join_window_sec", 90)):
            return text
        prev = prev.rstrip()
        if not prev:
            return text
        # Предыдущая кончилась знаком конца предложения - новая фраза начинает
        # своё, трогать регистр нельзя.
        if prev[-1] in ".!?:;":
            return text
        # Иначе это продолжение: строчная буква и пробел спереди. Заглавную
        # оставляем именам собственным - у них вторая буква тоже заглавная
        # редко, но первое слово из одной буквы («Я») трогать нельзя.
        head = text[0]
        if head.isupper() and len(text) > 1 and text[1].islower() and text[:1] != "Я":
            text = head.lower() + text[1:]
        return (" " if not prev[-1].isspace() else "") + text

    def _forget_old_history(self) -> None:
        """Выбросить диктовки старше history_days. 0 - ничего не трогаем.

        Зовём на старте, а не по таймеру: приложение живёт в трее сутками, и
        просыпаться ради перечитывания файла незачем. День туда-сюда для срока
        хранения роли не играет.

        Переписываем целиком через временный файл: обрыв на середине оставил бы
        половину истории, а это не лог, это данные.
        """
        days = int(self.cfg.get("history_days") or 0)
        if days <= 0 or not os.path.exists(HISTORY_PATH):
            return
        import datetime

        edge = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        kept, dropped = [], 0
        try:
            with open(HISTORY_PATH, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    # Сравниваем строки: формат «ГГГГ-ММ-ДД ЧЧ:ММ:СС» сортируется
                    # как текст, разбирать дату ради этого незачем.
                    try:
                        ts = json.loads(line).get("ts") or ""
                    except ValueError:
                        continue        # битую строку не тащим дальше
                    if str(ts)[:10] >= edge:
                        kept.append(line)
                    else:
                        dropped += 1
            if not dropped:
                return
            tmp = HISTORY_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.writelines(kept)
            os.replace(tmp, HISTORY_PATH)
            log(f"история: забыто {dropped} "
                f"{plural(dropped, 'диктовка', 'диктовки', 'диктовок')} "
                f"старше {days} {plural(days, 'дня', 'дней', 'дней')}")
        except OSError as e:
            log(f"история: почистить не вышло - {e}")

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

    def _on_wake(self) -> None:
        """Машина проснулась или экран разблокировали - собрать себя заново.

        Вызывается из оконной процедуры, а она живёт в главном потоке Qt, так
        что делать всё можно прямо здесь - в отличие от рабочего потока.

        Порядок важен: сперва чистим залипшие клавиши, потом пересобираем
        хоткеи. Наоборот - бесполезно: свежий бинд сверится с тем же мусорным
        состоянием и промолчит ровно так же.
        """
        if self._recording or self._capturing or self._work_lock.locked():
            # Идёт диктовка или человек как раз ловит новое сочетание в
            # настройках - разбирать хоткеи посреди этого нельзя. Ждать нечего:
            # раз конвейер работает, значит и хук жив.
            log("пробуждение: занято, ничего не трогаю")
            return
        wakeup.clear_stuck_keys(keyboard, log)
        self._hotkey_unbind()
        self._hotkey_bind()
        # Микрофон после сна - вторая половина той же беды. Поток бывает жив по
        # флагу active, а колбэков с него уже не приходит: ссылка на устройство
        # протухла, пока машина спала. Диагностика тогда сбивает с толку - проба
        # в настройках работает (она открывает поток заново), а по хоткею
        # тишина. Закрываем сами, следующая запись откроет свежий.
        try:
            self.recorder._close()
        except Exception as e:  # noqa: BLE001
            log(f"пробуждение: микрофон не закрылся ({type(e).__name__}: {e})")

    def _shutdown(self) -> None:
        if self._wake is not None:
            self._wake.stop()
            self._wake = None
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

    def _save_overlay_pos(self, x, y) -> None:
        """Запомнить, куда утащили пилюлю. None - вернуть на штатное место."""
        self.cfg["overlay_x"] = x
        self.cfg["overlay_y"] = y
        try:
            C.save(self.cfg)
        except OSError as e:
            log(f"положение пилюли не сохранилось: {e}")

    def _heal_autostart(self) -> None:
        """Автозапуск: поставить, если его нет, и обновить, если устарел.

        Галочки в настройках больше нет - владелец сказал «должно быть всегда»,
        и это верно для программы, которая всё время ждёт в трее: диктовка,
        которую надо сначала запустить, не выручает в тот момент, когда она
        нужна. Поэтому собранная сборка прописывает себя сама, молча и при
        каждом старте.

        Запись живёт своей жизнью: папку перенесли, Python обновили, у нас
        появился флаг `--silent`. Пока она старая, вход в систему будет
        открывать окно настроек - ровно то, чего мы избегаем.

        Выключить по-прежнему можно, и это не спрятанная лазейка, а честный
        выход: `FlowLocal.exe --autostart off`. Ключ реестра там же, руками
        снимается так же.
        """
        # Но НЕ из исходников поверх установленной сборки. Иначе запуск рабочей
        # копии молча уводит автозапуск на себя, и после перезагрузки стартует
        # не то, чем человек пользуется, а дерево разработки. Поймано на живой
        # машине владельца: проба из исходников переписала запись, указывавшую
        # на установленный .exe.
        #
        # Признак: мы не собранная сборка, а в реестре стоит .exe. Разработчик,
        # которому это правда нужно, ставит запись руками через --autostart on.
        frozen = bool(getattr(sys, "frozen", False))
        try:
            if not frozen and ".exe" in str(app_paths.autostart_command_current()).lower():
                log("автозапуск: в реестре стоит собранная сборка - "
                    "из исходников не трогаю")
                return
            # Из исходников себя в автозапуск НЕ прописываем. Рабочее дерево
            # запускают десятки раз на дню и не для того, чтобы оно поселилось
            # в реестре; у владельца там должна стоять установленная сборка.
            if not frozen:
                return
            if app_paths.autostart_enabled() and not app_paths.autostart_command_stale():
                return
            set_autostart(True)
            log("автозапуск: запись в реестре поставлена или обновлена")
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
            log("не смог открыть окно по ярлыку:\n" + traceback.format_exc())

    def run(self, silent: bool = False) -> None:
        # Язык интерфейса ставим ДО первого окна: иначе мастер первого
        # запуска успеет отрисоваться по-русски и переведётся только
        # после первой перерисовки.
        i18n.set_language(str(self.cfg.get("ui_language") or "ru"))
        self._hotkey_bind()
        self._wake = wakeup.WakeWatcher(self._on_wake, log)
        self._wake.start()
        self._start_tray()
        self._start_ipc()
        self._heal_autostart()
        # Модель НЕ греем, пока идёт мастер первого запуска.
        #
        # Загрузка модели - это сборка сессии onnxruntime, и делает её C-код,
        # который держит GIL пачками по несколько секунд. Поток тут не спасает:
        # GIL один на процесс, и всё это время окно Qt не получает управления.
        # Владелец на первом запуске сказал «сильно лагает» - это оно и было:
        # мастер открывался через 600 мс, ровно в разгар загрузки.
        #
        # Мастеру модель не нужна до предпоследнего шага («Скажите
        # что-нибудь»), а там она поднимется сама - тем же ленивым путём, что
        # и на первой диктовке. Скачивание на шаге 2 идёт отдельным процессом
        # (download_model_cli), окна оно не касается вовсе.
        if self.cfg.get("onboarded"):
            threading.Thread(target=self._load_model_bg, daemon=True).start()
        threading.Thread(target=self._autoconfig_llm_bg, daemon=True).start()
        self._forget_old_history()
        threading.Thread(target=self._check_update_bg, daemon=True).start()
        # И дальше - по таймеру, пока приложение живёт в трее.
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(
            lambda: threading.Thread(target=self._check_update_bg, daemon=True).start())
        self._update_timer.start(_UPDATE_EVERY)
        # Простой модели - раз в минуту. Дешевле, чем заводить и снимать таймер
        # на каждую диктовку.
        self._idle_timer = QTimer()
        self._idle_timer.timeout.connect(self._maybe_unload_model)
        self._idle_timer.timeout.connect(self._check_deaf)
        self._idle_timer.start(60 * 1000)
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
            if keyboard is not None:
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

    def _notify_update(self, found: dict) -> None:
        """Шарик «есть новая версия». Клик по нему ставит обновление.

        Показываем один раз на находку, а не на каждую перепроверку: проверка
        идёт каждые шесть часов, и напоминать об одном и том же четыре раза в
        сутки - это уже навязчивость.
        """
        from PySide6.QtWidgets import QSystemTrayIcon

        if self.tray is None or self._update_told == found.get("version"):
            return
        self._update_told = str(found.get("version") or "")
        title = str(found.get("notes") or "").splitlines()
        self.tray.showMessage(
            f"Есть версия {found.get('version')}",
            (title[0] if title else "") + f"\nНажмите, чтобы обновить · {found.get('size_mb')} МБ",
            QSystemTrayIcon.Information, 12000)

    def _on_balloon_clicked(self) -> None:
        """Клик по шарику. Обновление - если оно есть; иначе просто окно.

        Windows не говорит, по какому именно шарику кликнули, поэтому решаем
        по состоянию: висит найденное обновление - ставим его, нет - открываем
        настройки. Оба исхода человек и ожидает от клика по сообщению.
        """
        if self._update:
            self._do_update()
        else:
            self._open_settings()

    def _greet_after_onboarding(self) -> None:
        """Мастер пройден - сказать, чем пользоваться, прямо сейчас.

        Раньше мастер просто закрывался, и человек оставался с пустым экраном:
        иконку в трее Windows прячет под шеврон, а сочетание он видел один раз,
        три экрана назад. Подсказка нужна не в начале списка правил, а в момент,
        когда ей можно воспользоваться.
        """
        from PySide6.QtWidgets import QSystemTrayIcon

        if self.tray is None:
            return
        binds = self._binds_pretty()
        QTimer.singleShot(400, lambda: self.tray.showMessage(
            "Всё готово",
            f"Зажмите {binds} в любом окне и говорите" if binds
            else "Назначьте сочетание в настройках - и можно диктовать",
            QSystemTrayIcon.Information, 8000))

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
            else "Сочетание не назначено - откройте настройки",
            QSystemTrayIcon.Information, 4000)


IPC_NAME = "FlowLocal_ipc"


def single_instance() -> bool:
    # Мьютекс (Windows) или заглушка (macOS: пока без блокировки) - ветвление в
    # platform_api, чтобы голого CreateMutexW в общем коде не было.
    return platform_api.single_instance()


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


def _download_cmd(model_id: str) -> list:
    """Чем звать загрузчик модели: собранный .exe или свой же исходник.

    Двойник этой функции есть в settings_qt - там она нужна окну настроек.
    Держим отдельно намеренно: тащить сюда весь settings_qt (а с ним QtWidgets)
    ради шести строк, да ещё из рабочего потока, дороже, чем повторить их.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--download-model", model_id]
    return [sys.executable, os.path.join(APP_DIR, "app.py"),
            "--download-model", model_id]


def download_model_cli() -> int:
    """Скачать модель и выйти. Служебный режим, человеку не показывается.

        FlowLocal.exe --download-model gigaam-v2-ctc
        FlowLocal.exe --download-model english

    Зачем отдельный процесс. Раньше модель качалась потоком внутри окна
    настроек, и владелец, проходя мастер первого запуска, написал: «после
    появления полоски скачивания всё зависло - никуда не перейти, ничего не
    нажать». Так и было. Скачивание - это половина работы; вторая половина -
    сборка сессии onnxruntime, а она идёт в C и держит GIL секундами. Пока она
    держит, поток Qt не получает управления вовсе: окно не перерисовывается и
    не отвечает на нажатия. Для Windows это «программа не отвечает».

    Потоком эту беду не вылечить - GIL один на процесс. Отдельный процесс
    лечит её целиком и заодно бесплатно: упасть он может только сам по себе,
    окно от этого не пострадает.

    Прогресс наружу не отдаём: его и так видно по тому, как растёт папка
    модели, и настройки считают именно так (settings_qt.downloadModel). Один
    способ мерить вместо двух, которые однажды разойдутся.
    """
    model_id = sys.argv[2] if len(sys.argv) >= 3 else ""
    if not model_id:
        print("использование: --download-model <идентификатор>")
        return 2
    import shutil

    import models
    from transcriber import model_dir

    # Английская модель идёт особняком: в каталоге моделей распознавания её
    # нет и быть не должно. Каталог - это выбор человека («Обычная» или
    # «Внимательная»), а английская не выбирается: она приезжает вместе с
    # основной и работает сама.
    if model_id in (language.DOWNLOAD_ID, language.MODEL):
        err = language.download()
        if err:
            log(f"скачивание английской модели не вышло: {err}")
            print(f"не скачалось: {err}")
            return 1
        log(f"скачано: английская модель, {language.size_mb():.0f} МБ")
        print("готово")
        return 0

    m = models.get(model_id)
    if m is None:
        print(f"нет такой модели: {model_id}")
        return 2
    d = model_dir(m.id, m.quant)
    # Папку НЕ создаём заранее, и это не мелочь: для onnx-asr существующая
    # папка означает «работаем офлайн», качать в неё он не пойдёт и упадёт на
    # ненайденном файле. Здесь раньше стоял makedirs - то есть первое же
    # скачивание в мастере отвечало «не удалось скачать, проверьте интернет»
    # при живом интернете.
    #
    # Неполную папку от оборванной скачки сносим по той же причине: докачать в
    # неё нельзя. А полную не трогаем - иначе повторное нажатие «Скачать»
    # стирало бы готовую модель и качало её заново.
    if os.path.isdir(d):
        try:
            on_disk = sum(os.path.getsize(os.path.join(d, f))
                          for f in os.listdir(d)) / 1e6
        except OSError:
            on_disk = 0.0
        if on_disk >= m.size_mb * 0.9:
            log(f"{model_id} уже на месте, {on_disk:.0f} МБ")
            print("готово")
            return 0
        shutil.rmtree(d, ignore_errors=True)
    try:
        import onnx_asr

        # load_model и качает, и собирает сессию. Собранную тут же выбрасываем:
        # нам нужны файлы на диске, а не рабочая модель. Зато так мы уверены,
        # что скачано ровно то и в том виде, что попросит настоящая загрузка.
        onnx_asr.load_model(m.id, path=d, quantization=m.quant,
                            providers=["CPUExecutionProvider"])
    except Exception as e:  # noqa: BLE001 - сюда приходит что угодно из сети
        log(f"скачивание {model_id} не вышло: {e}")
        print(f"не скачалось: {e}")
        return 1
    log(f"скачано: {model_id}")
    print("готово")
    return 0


def transcribe_cli() -> int:
    """`--transcribe <файл>`: расшифровать запись и положить текст рядом.

    Окон не открывает и в трей не лезет - это одноразовая работа, а не запуск
    программы. Тем же приёмом сделан `--download-model` выше.

    Зачем этот флаг существует, кроме удобства. СОБРАННОЕ приложение иначе
    нечем проверить: у него нет консоли (console=False в flowlocal.spec), в
    трее оно ждёт мыши, а декодер - единственная часть задачи 11, которая
    ломается именно в сборке, а не в исходниках. Обе библиотеки приезжают
    скомпилированными расширениями плюс своя DLL рядом, и PyInstaller такое
    теряет регулярно и молча: из исходников работает, у человека с
    установщиком - нет, и узнаёт он об этом, перетащив первое голосовое.
    Флаг превращает эту проверку в одну команду и делает её обязательной
    частью выпуска, а не доброй волей проверяющего.

    Текст пишем ФАЙЛОМ рядом с записью, а не в вывод: печатать некуда - у
    собранного приложения консоли нет.
    """
    path = sys.argv[2] if len(sys.argv) >= 3 else ""
    if not path:
        print("использование: --transcribe <файл>")
        return 2

    import audiofile

    try:
        audio = audiofile.decode(path)
    except audiofile.AudioFileError as e:
        log(f"--transcribe: {e}")
        print(f"не вышло: {e}")
        return 1
    except Exception as e:  # noqa: BLE001 - чужой файл, прилететь может что угодно
        log(f"--transcribe: {type(e).__name__}: {e}")
        print(f"не вышло: {type(e).__name__}: {e}")
        return 1

    cfg = C.load()
    t = Transcriber(cfg, log)
    try:
        t.load()
        text = clean(t.transcribe(audio), cfg, log)
    except Exception as e:  # noqa: BLE001
        log(f"--transcribe: распознать не вышло: {type(e).__name__}: {e}")
        print(f"не вышло: {type(e).__name__}: {e}")
        return 1

    out = os.path.splitext(path)[0] + ".txt"
    try:
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
    except OSError as e:
        log(f"--transcribe: не записать {out}: {e}")
        print(f"не записать {out}: {e}")
        return 1
    log(f"--transcribe: {len(text.split())} слов из {os.path.basename(path)} "
        f"({audio.size / 16000:.1f} с) -> {out}")
    print(f"готово: {out}")
    return 0


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "--download-model":
        sys.exit(download_model_cli())
    if len(sys.argv) >= 2 and sys.argv[1] == "--transcribe":
        sys.exit(transcribe_cli())
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
    # Аргументы в улике обязательны. Без них по логу не отличить автозапуск от
    # клика по ярлыку: строка была одинаковой, и расследование «почему не
    # стартует при входе в систему» упиралось в то, что записи о таком старте
    # просто нет - ни успешной, ни неуспешной. Теперь видно и флаг, и то, что
    # Windows вообще нас позвала.
    _auto = "--silent" in sys.argv
    log(f"launch: pid={os.getpid()} {'АВТОЗАПУСК' if _auto else 'вручную'} "
        f"argv={sys.argv[1:]} exe={sys.executable} cwd={os.getcwd()}")
    if _auto:
        # Отдельной строкой и до всякой тяжёлой работы: если приложение умрёт
        # на загрузке модели, эта строка всё равно останется в логе и скажет,
        # что автозапуск сработал, а упало уже наше.
        log("автозапуск: Windows нас позвала, поднимаюсь")
    if not single_instance():
        log("already running")
        # Достучаться до живого экземпляра нужен цикл событий Qt - создаём
        # приложение, но окон не открываем: этот процесс сейчас же умрёт.
        from PySide6.QtWidgets import QApplication

        _q = QApplication(sys.argv)
        if not poke_running_instance():
            # Пайпа нет: экземпляр от старой версии или умирает. Сказать вслух
            # - лучше, чем молча выйти. Окно средствами платформы (на macOS эта
            # ветка недостижима: single_instance там всегда True).
            platform_api.already_running_notice()
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
        die("FlowLocal не запустился. Помогает перезагрузка компьютера, "
            "а если не помогла - переустановка программы.",
            f"{type(e).__name__}: {e}")
        raise SystemExit(1) from e
