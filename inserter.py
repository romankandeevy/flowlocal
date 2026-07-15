"""Вставка текста в активное окно.

Режим paste (по умолчанию): текст кладётся в буфер обмена, шлётся
Ctrl+V, затем прежний текстовый буфер восстанавливается - как делает
Wispr Flow. Мгновенно при любой длине текста.

Ctrl+V шлётся через keybd_event с виртуальными кодами (VK_CONTROL, 'V'):
библиотека keyboard маппит буквы через текущую раскладку, и на русской
раскладке "ctrl+v" у неё не срабатывает. VK-коды от раскладки не зависят.

Режим type: посимвольный ввод юникод-событиями SendInput - медленнее,
но работает там, где Ctrl+V не вставляет (старая cmd.exe и т.п.).
"""

import ctypes
import time

import win32api
import win32clipboard
import win32con

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_V = 0x56


def _wait_modifiers_released(timeout: float = 2.0) -> None:
    """Ждём, пока физически отпущены Ctrl/Shift/Alt/Win: иначе наш Ctrl+V
    превратится в Ctrl+Shift+V и т.п."""
    deadline = time.time() + timeout
    mods = (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN)
    while time.time() < deadline:
        if not any(win32api.GetAsyncKeyState(vk) & 0x8000 for vk in mods):
            return
        time.sleep(0.02)


def _send_ctrl_v() -> None:
    win32api.keybd_event(VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.02)
    win32api.keybd_event(VK_V, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("padding", ctypes.c_ubyte * 32)]

    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_ulong), ("u", _U)]


_INPUT_KEYBOARD = 1
_KEYEVENTF_UNICODE = 0x0004
_KEYEVENTF_KEYUP = 0x0002


def _type_unicode(text: str) -> None:
    """Посимвольный ввод через SendInput KEYEVENTF_UNICODE - любая раскладка,
    любые символы (кириллица, эмодзи через суррогатные пары)."""
    raw = text.replace("\n", "\r").encode("utf-16-le")
    units = [int.from_bytes(raw[i:i + 2], "little") for i in range(0, len(raw), 2)]
    events: list[_INPUT] = []
    for unit in units:
        for flags in (_KEYEVENTF_UNICODE, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP):
            inp = _INPUT()
            inp.type = _INPUT_KEYBOARD
            inp.ki = _KEYBDINPUT(0, unit, flags, 0, None)
            events.append(inp)
    if not events:
        return
    arr = (_INPUT * len(events))(*events)
    ctypes.windll.user32.SendInput(len(events), arr, ctypes.sizeof(_INPUT))


def _get_clipboard_text() -> str | None:
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return None
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return None


def _set_clipboard_text(text: str) -> bool:
    for _ in range(3):
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                return True
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(0.05)  # буфер бывает занят другим процессом
    return False


def insert(text: str, mode: str = "paste", restore: bool = True) -> None:
    _wait_modifiers_released()
    if mode == "type":
        _type_unicode(text)
        return

    old = _get_clipboard_text() if restore else None
    if not _set_clipboard_text(text):
        _type_unicode(text)
        return
    time.sleep(0.05)
    _send_ctrl_v()
    if restore and old is not None:
        # дать целевому приложению забрать данные до восстановления буфера
        time.sleep(0.3)
        _set_clipboard_text(old)
