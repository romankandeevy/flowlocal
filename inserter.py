"""Вставка текста в активное окно.

Режим paste (по умолчанию): текст кладётся в буфер обмена, шлётся
Ctrl+V, затем прежний текстовый буфер восстанавливается - как делает
Wispr Flow. Мгновенно при любой длине текста.

Режим type: посимвольный ввод через SendInput - медленнее, но работает
там, где Ctrl+V не вставляет (старая cmd.exe и т.п.).
"""

import time

import keyboard
import win32clipboard
import win32con


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
    if mode == "type":
        keyboard.write(text, delay=0.005)
        return

    old = _get_clipboard_text() if restore else None
    if not _set_clipboard_text(text):
        keyboard.write(text, delay=0.005)
        return
    time.sleep(0.05)
    keyboard.send("ctrl+v")
    if restore and old is not None:
        # дать целевому приложению забрать данные до восстановления буфера
        time.sleep(0.3)
        _set_clipboard_text(old)
