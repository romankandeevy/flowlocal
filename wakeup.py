"""Заметить, что машина проснулась или экран разблокировали.

Зачем это вообще нужно. Симптом: ноутбук закрыли на ночь, утром открыли,
ввели PIN - и хоткей больше не работает. Ни звука, ни ошибки, ни намёка.
Программа сидит в трее живая, но глухая, и понять это можно только тем, что
диктовка не приходит. Для программы, которая по замыслу невидима, это худший
из возможных отказов: снаружи он выглядит как «ничего не произошло».

Причина, из-за которой это не чинится само. Чтобы Windows показала экран
ввода PIN, надо нажать любую клавишу. На это нажатие система шлёт key DOWN и
не шлёт key UP - похоже, защита от перехвата пароля: экран блокировки живёт на
отдельном защищённом рабочем столе, и туда наши хуки не пускают. Библиотека
keyboard после этого считает клавишу зажатой навсегда. Механизм сочетаний
сверяется с этим состоянием - и молчит. Само оно не рассосётся: снятие и
установка хуков состояние не чистят.

Что делаем: ловим момент пробуждения и разблокировки и пересобираем хоткеи
заново, попутно вычистив «зажатые» клавиши, которых никто не держит.

Как ловим. Скрытое окно и два сообщения:
  WM_POWERBROADCAST      - проснулись из сна (приходит всем окнам верхнего
                           уровня, регистрироваться не надо);
  WM_WTSSESSION_CHANGE   - разблокировали экран или вернулись в сеанс
                           (нужна подписка через WTSRegisterSessionNotification).

Окно создаётся в главном потоке Qt и своей очереди сообщений не заводит:
цикл событий Qt разбирает все сообщения потока подряд и раздаёт их по окнам,
включая наше. Отдельный поток с PumpMessages был бы лишним - и опасным, потому
что колбэк дёргает пересборку хоткеев, а её место в главном потоке.
"""

import ctypes

import platform_api

WM_POWERBROADCAST = 0x0218
WM_WTSSESSION_CHANGE = 0x02B1

# WM_POWERBROADCAST
PBT_APMRESUMESUSPEND = 0x0007      # проснулись после сна по команде человека
PBT_APMRESUMEAUTOMATIC = 0x0012    # проснулись сами (таймер, сеть)

# WM_WTSSESSION_CHANGE
WTS_SESSION_UNLOCK = 0x8
WTS_SESSION_LOGON = 0x5
WTS_CONSOLE_CONNECT = 0x1
WTS_REMOTE_CONNECT = 0x3

NOTIFY_FOR_THIS_SESSION = 0

_WAKE_POWER = {PBT_APMRESUMESUSPEND, PBT_APMRESUMEAUTOMATIC}
_WAKE_SESSION = {WTS_SESSION_UNLOCK, WTS_SESSION_LOGON,
                 WTS_CONSOLE_CONNECT, WTS_REMOTE_CONNECT}

# ctypes.WINFUNCTYPE - только Windows (AttributeError на маке), и вся ловля
# пробуждения на нём и на скрытом окне держится. Механизм целиком Windows: на
# macOS сон/пробуждение слушает NSWorkspace.notificationCenter, но главный повод
# этого модуля - залипание клавиш в библиотеке keyboard - на маке отпадает
# вместе с самой keyboard. Поэтому под darwin WakeWatcher - заглушка (start()
# возвращает False), а класс и тип поднимаем только под Windows.
#
# `ctypes.wintypes` (ниже как wt) - по той же причине под гардом: на macOS он
# не импортируется вовсе, VARIANT_BOOL в нём объявлен кодом типа "v".
if platform_api.IS_WINDOWS:
    import ctypes.wintypes as wt

    _WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wt.HWND, ctypes.c_uint,
                                  ctypes.c_ulonglong, ctypes.c_longlong)

    class _WNDCLASS(ctypes.Structure):
        _fields_ = [("style", ctypes.c_uint), ("lpfnWndProc", _WNDPROC),
                    ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                    ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH),
                    ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR)]


class WakeWatcher:
    """Живёт всё время работы программы. Ссылку держать обязательно: умрёт
    объект - Python соберёт WNDPROC, и система вызовет освобождённую память."""

    def __init__(self, on_wake, log) -> None:
        self.on_wake = on_wake
        self.log = log
        self.hwnd = None
        self._registered = False
        self._wts = None
        if not platform_api.IS_WINDOWS:
            # На маке ни _WNDPROC, ни WinDLL нет - и не нужно (см. блок выше).
            self._proc = None
            self._u32 = None
            return
        self._proc = _WNDPROC(self._wndproc)   # ссылку держим полем, не локальной
        self._u32 = ctypes.WinDLL("user32", use_last_error=True)

    def start(self) -> bool:
        """True - слушаем. False - не вышло, но программа работает как прежде."""
        if not platform_api.IS_WINDOWS:
            platform_api.note_unsupported("слух за сном и разблокировкой экрана")
            return False
        try:
            self._create_window()
            self._subscribe_session()
            return True
        except Exception as e:  # noqa: BLE001 - слух о пробуждении не стоит запуска
            self.log(f"пробуждение: не слежу ({type(e).__name__}: {e})")
            return False

    def _create_window(self) -> None:
        u32 = self._u32
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)

        # Типы объявляем ЯВНО, все до одного. Без этого ctypes догадывается, а
        # на 64-битной Windows догадка неверна: у функции без `restype` он
        # считает ответ 32-битным `int`, и хэндл модуля - настоящий указатель -
        # приезжает обрезанным. Дальше он же уходит одиннадцатым аргументом в
        # CreateWindowExW, и вызов падает с «argument 11: OverflowError: int too
        # long to convert».
        #
        # Ловилось это только на живой машине и только в журнале одной строкой
        # «пробуждение: не слежу»: `start()` глушит исключение намеренно - слух
        # о пробуждении не стоит запуска программы. Тихо, но дорого: без этого
        # окна не приходит WM_POWERBROADCAST, то есть после сна и блокировки
        # никто не чистит залипшие клавиши, а ломалось там уже дважды.
        k32.GetModuleHandleW.restype = wt.HMODULE
        k32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
        u32.RegisterClassW.restype = wt.ATOM
        u32.RegisterClassW.argtypes = [ctypes.POINTER(_WNDCLASS)]
        u32.CreateWindowExW.restype = wt.HWND
        u32.CreateWindowExW.argtypes = [
            wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
        u32.DefWindowProcW.restype = ctypes.c_longlong

        wc = _WNDCLASS()
        wc.lpfnWndProc = self._proc
        wc.hInstance = k32.GetModuleHandleW(None)
        wc.lpszClassName = "FlowLocalWakeWatcher"
        if not u32.RegisterClassW(ctypes.byref(wc)):
            err = ctypes.get_last_error()
            if err != 1410:      # ERROR_CLASS_ALREADY_EXISTS - переживём
                raise OSError(f"RegisterClassW: {err}")
        self._wc = wc            # класс держит указатель на WNDPROC - не терять
        # HWND_MESSAGE (-3) дал бы окно-невидимку, но такому окну система НЕ
        # шлёт WM_POWERBROADCAST: широковещательные сообщения идут только окнам
        # верхнего уровня. Поэтому окно обычное, просто без WS_VISIBLE.
        self.hwnd = u32.CreateWindowExW(0, "FlowLocalWakeWatcher", "", 0,
                                        0, 0, 0, 0, None, None, wc.hInstance, None)
        if not self.hwnd:
            raise OSError(f"CreateWindowExW: {ctypes.get_last_error()}")

    def _subscribe_session(self) -> None:
        """Подписка на блокировку/разблокировку.

        Без неё осталось бы только пробуждение из сна, а самый частый случай -
        как раз «отошёл, экран заблокировался, вернулся»: машина не спала, и
        WM_POWERBROADCAST не придёт, а клавиша на снятие блокировки залипнет
        точно так же.
        """
        self._wts = ctypes.WinDLL("wtsapi32", use_last_error=True)
        ok = self._wts.WTSRegisterSessionNotification(self.hwnd,
                                                      NOTIFY_FOR_THIS_SESSION)
        if not ok:
            raise OSError(f"WTSRegisterSessionNotification: {ctypes.get_last_error()}")
        self._registered = True

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_POWERBROADCAST and wparam in _WAKE_POWER:
                self._wake("проснулись")
            elif msg == WM_WTSSESSION_CHANGE and wparam in _WAKE_SESSION:
                self._wake("сеанс разблокирован")
        except Exception:  # noqa: BLE001 - из оконной процедуры бросать нельзя
            pass
        return self._u32.DefWindowProcW(hwnd, msg, ctypes.c_ulonglong(wparam),
                                        ctypes.c_longlong(lparam))

    def _wake(self, why: str) -> None:
        self.log(f"пробуждение: {why} - пересобираю хоткеи")
        self.on_wake()

    def stop(self) -> None:
        try:
            if self._registered and self._wts is not None:
                self._wts.WTSUnRegisterSessionNotification(self.hwnd)
            if self.hwnd:
                self._u32.DestroyWindow(self.hwnd)
        except Exception:  # noqa: BLE001
            pass
        self.hwnd = None
        self._registered = False


def listener_dead(keyboard) -> str:
    """Проверить, слышит ли нас библиотека вообще. "" - слышит.

    Отдельный класс отказа, не связанный со сном: у `keyboard` два служебных
    потока - один сидит на низкоуровневом хуке, второй разбирает очередь. Оба
    демоны. Умри любой из них от необработанного исключения - программа
    остаётся жива, иконка в трее на месте, а хоткей не работает больше никогда.
    Ни ошибки, ни записи в журнале: поток-демон умирает молча.

    Снаружи это тот же симптом, что и залипание после сна, - «нажимаю, ничего
    не происходит», - поэтому проверка живёт здесь же.

    Чего эта проверка НЕ ловит, и это честно: если Windows сняла наш хук сама
    (так бывает, когда обработчик не уложился в LowLevelHooksTimeout), поток
    остаётся жив и висит в GetMessage. Изнутри библиотеки такое не отличить от
    исправной работы. Способа нет - и придумывать вид, что он есть, не надо.
    """
    listener = getattr(keyboard, "_listener", None)
    if listener is None or not getattr(listener, "listening", False):
        return "" if listener is None else "слушатель клавиатуры не запущен"
    for attr, what in (("listening_thread", "поток хука клавиатуры"),
                       ("processing_thread", "поток разбора нажатий")):
        t = getattr(listener, attr, None)
        if t is not None and not t.is_alive():
            return f"{what} умер"
    return ""


def can_revive(keyboard) -> bool:
    """Можно ли поднять слушателя заново, не рискуя вторым хуком.

    Условие намеренно узкое: оба служебных потока мертвы. Тогда поднимать
    некому и дублировать нечего.

    Почему не пробовать шире. `start_if_necessary()` смотрит на флаг
    `listening`, а флаг остаётся True и после смерти потоков. Сбросить его при
    живом потоке значит завести ВТОРОЙ хук поверх первого - и каждая диктовка
    станет вставляться дважды. Этот класс поломки в проекте уже был, на него
    даже написан `tools/repro_double_insert.py`. Половина живых потоков - это
    случай «сказать человеку», а не «чинить наугад».
    """
    listener = getattr(keyboard, "_listener", None)
    if listener is None:
        return False
    threads = [getattr(listener, a, None)
               for a in ("listening_thread", "processing_thread")]
    threads = [t for t in threads if t is not None]
    return bool(threads) and all(not t.is_alive() for t in threads)


def revive(keyboard, log) -> None:
    """Поднять слушателя заново. Звать только после can_revive()."""
    if keyboard is None:            # не-Windows: библиотеки keyboard нет вовсе
        return
    listener = keyboard._listener
    listener.listening = False      # иначе start_if_necessary() сочтёт, что всё уже идёт
    log("поднимаю слушателя клавиатуры заново")


def clear_stuck_keys(keyboard, log) -> int:
    """Забыть клавиши, которые библиотека считает зажатыми.

    Ровно то залипание, ради которого всё и написано: на нажатие, будящее экран
    входа, приходит DOWN без UP. Возвращаем, сколько вычистили, - в лог, чтобы
    в следующий раз не гадать, было залипание или нет.

    Лезем во внутренности библиотеки осознанно: своего способа сбросить
    состояние она не предлагает, а без сброса пересборка хоткеев бесполезна -
    сочетания сверяются именно с этим набором.
    """
    if keyboard is None:            # не-Windows: библиотеки keyboard нет вовсе
        return 0
    try:
        listener = keyboard._listener
        with listener.lock:
            pressed = getattr(keyboard, "_pressed_events", None)
            if pressed is None:
                return 0
            stuck = len(pressed)
            pressed.clear()
            physically = getattr(keyboard, "_physically_pressed_keys", None)
            if physically is not None and physically is not pressed:
                physically.clear()
            logically = getattr(keyboard, "_logically_pressed_keys", None)
            if logically is not None and logically is not pressed:
                logically.clear()
        if stuck:
            log(f"пробуждение: вычищено залипших клавиш: {stuck}")
        return stuck
    except Exception as e:  # noqa: BLE001
        log(f"пробуждение: не смог вычистить залипшие клавиши ({type(e).__name__}: {e})")
        return 0
