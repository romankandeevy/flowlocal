"""Две вещи, которые Qt не умеет, а Windows делает только через Win32.

Файл — остаток. В нём было 425 строк: класс `LayeredWindow` с попиксельной
альфой, DIB-битмап, свой оконный класс с WNDPROC, опрос монитора и DPI — всё
ради пилюли, которую тогда рисовал PIL, а показывал `UpdateLayeredWindow`.
Этап 6 плана заменил её на Qt: `WindowDoesNotAcceptFocus` разворачивается в
`WS_EX_NOACTIVATE` сам, скругления и тень делает QML, монитор и его масштаб
знает `QScreen`. Проверено `tools/probe_qt_overlay.py` — фокус чужого окна цел
даже при попытке активировать пилюлю.

Мёртвое вырезано 18.07.2026. Достать при нужде: `git show <коммит>~1:layered.py`.

Осталось ровно то, чему замены в Qt нет:

    style_titlebar()      заголовок окна красит DWM, а не Qt. Без этого над
                          тёмным интерфейсом висит белая системная полоса
    foreground_process()  имя exe окна, в которое сейчас пишут, — для правил
                          тона («в outlook.exe формально, в чате свободно»)
    foreground_window()   / focus_window() — запомнить окно и вернуть в него
                          фокус: список преобразований забирает фокус себе,
                          а вставлять надо обратно, туда же, откуда взяли

Обе уедут в `platform/`, когда дойдёт черёд macOS: там это `NSWindow` и
bundle id вместо exe. Пока — здесь, и это единственный Win32 в проекте помимо
`inserter.py` и хука.

**`argtypes` обязательны.** Без них ctypes считает хэндлы 32-битными и на x64
рвёт старшие биты — молча работая не с тем объектом.
"""

import ctypes
import os
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                            ctypes.POINTER(wintypes.DWORD)]

kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def style_titlebar(hwnd: int, caption=None, dark: bool = True) -> None:
    """Заголовок окна под нашу тему средствами DWM: рамка становится
    продолжением интерфейса, а не чужой полосой сверху.

    Звать после `view.create()` — до него HWND не существует. И заново при
    смене темы: Windows сама не узнает.

    dark управляет цветом кнопок и текста заголовка - их рисует Windows, и
    подобрать их через caption нельзя: на светлой теме белые крестик и
    подпись просто исчезли бы. На старых сборках атрибуты игнорируются.
    """
    try:
        dwm = ctypes.WinDLL("dwmapi")
    except OSError:
        return

    def attr(code: int, value: int) -> None:
        try:
            dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), wintypes.DWORD(code),
                                      ctypes.byref(ctypes.c_int(value)),
                                      ctypes.sizeof(ctypes.c_int))
        except OSError:
            pass

    attr(20, int(dark))   # DWMWA_USE_IMMERSIVE_DARK_MODE
    attr(19, int(dark))   # то же на сборках 1809 (старый код атрибута)
    attr(33, 2)           # DWMWA_WINDOW_CORNER_PREFERENCE = ROUND
    if caption is not None:
        # COLORREF - это 0x00BBGGRR, а не привычный RGB
        attr(35, (caption[2] << 16) | (caption[1] << 8) | caption[0])
        attr(34, (caption[2] << 16) | (caption[1] << 8) | caption[0])


user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


def foreground_window() -> int:
    """HWND окна, в которое сейчас пишут. 0 - не спросить."""
    return int(user32.GetForegroundWindow() or 0)


def focus_window(hwnd: int) -> bool:
    """Вернуть фокус окну, которое мы у него забрали.

    Голый SetForegroundWindow тут не работает: Windows защищает активное окно
    от кражи фокуса, и вызов молча возвращает ложь. Обход - на время
    подцепиться к очереди ввода того окна: тогда система считает нас с ним
    одним целым и передачу разрешает.

    Классический совет «нажать Alt перед SetForegroundWindow» здесь ЯДОВИТ и
    проверен на своей шкуре в test_insert.py: отпускание Alt вводит окно в
    режим меню, и следующее нажатие съедается - ровно наш Ctrl+V. В режиме
    вставки не вставлялось ничего, в посимвольном пропадала первая буква.
    AttachThreadInput клавиатуру не трогает вовсе.
    """
    if not hwnd:
        return False
    try:
        mine = kernel32.GetCurrentThreadId()
        theirs = user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), None)
        attached = bool(theirs and theirs != mine
                        and user32.AttachThreadInput(mine, theirs, True))
        try:
            return bool(user32.SetForegroundWindow(wintypes.HWND(hwnd)))
        finally:
            if attached:
                user32.AttachThreadInput(mine, theirs, False)
    except OSError:
        return False


def foreground_process() -> str:
    """Имя exe окна, в которое сейчас пишут: 'outlook.exe', 'telegram.exe'.

    Нужно правилам тона: в почте формально, в чате свободно. Спрашиваем у окна,
    а не у списка процессов - важно именно то, куда уедет текст.

    Пустая строка, если спросить не удалось (окна нет, процесс чужого сеанса,
    доступ закрыт). Правила тона тогда просто не сработают - молча, потому что
    диктовка важнее тона.
    """
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    # PROCESS_QUERY_LIMITED_INFORMATION: минимум прав, которого хватает на имя.
    # PROCESS_QUERY_INFORMATION потребовал бы больше и ломался бы на чужих
    # процессах с более высокой целостностью.
    h = kernel32.OpenProcess(0x1000, False, pid.value)
    if not h:
        return ""
    try:
        size = wintypes.DWORD(260)
        buf = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return ""
        return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(h)
