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
import ctypes.wintypes as wt

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
        self._proc = _WNDPROC(self._wndproc)   # ссылку держим полем, не локальной
        self._u32 = ctypes.WinDLL("user32", use_last_error=True)
        self._wts = None

    def start(self) -> bool:
        """True - слушаем. False - не вышло, но программа работает как прежде."""
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
        u32.CreateWindowExW.restype = wt.HWND
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


def clear_stuck_keys(keyboard, log) -> int:
    """Забыть клавиши, которые библиотека считает зажатыми.

    Ровно то залипание, ради которого всё и написано: на нажатие, будящее экран
    входа, приходит DOWN без UP. Возвращаем, сколько вычистили, - в лог, чтобы
    в следующий раз не гадать, было залипание или нет.

    Лезем во внутренности библиотеки осознанно: своего способа сбросить
    состояние она не предлагает, а без сброса пересборка хоткеев бесполезна -
    сочетания сверяются именно с этим набором.
    """
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
