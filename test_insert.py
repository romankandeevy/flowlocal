"""Автотест вставки в нативный Win32 EDIT-контрол.

EDIT обрабатывает Ctrl+V на уровне класса окна (WM_CHAR 0x16) - так же,
как реальные приложения, и независимо от раскладки. tkinter для этого
теста не годится: его биндинг <Control-v> привязан к латинскому keysym
и молчит на русской раскладке.

Печатает RESULT и PASS/FAIL. Запуск: python test_insert.py [paste|type]
"""

import ctypes
import sys
import threading
import time

import win32con
import win32gui

from inserter import _get_clipboard_text, insert

EXPECT = "Привет, FlowLocal - проверка вставки 123. "
VK_MENU = 0x12


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "paste"
    before = _get_clipboard_text()

    hwnd = win32gui.CreateWindow(
        "EDIT",
        "FlowLocal insert test",
        win32con.WS_OVERLAPPEDWINDOW | win32con.WS_VISIBLE | win32con.ES_MULTILINE,
        100, 100, 640, 200,
        0, 0, 0, None,
    )
    win32gui.SetWindowPos(
        hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE,
    )
    win32gui.SendMessage(hwnd, win32con.WM_SETTEXT, 0, "")

    # обход foreground-lock: короткий Alt перед SetForegroundWindow
    user32 = ctypes.windll.user32
    user32.keybd_event(VK_MENU, 0, 0, 0)
    try:
        win32gui.SetForegroundWindow(hwnd)
    finally:
        user32.keybd_event(VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

    state = {"fg_at_paste": None}
    done = threading.Event()

    def go() -> None:
        time.sleep(0.8)
        state["fg_at_paste"] = win32gui.GetForegroundWindow()
        insert(EXPECT, mode)
        time.sleep(0.8)
        done.set()

    threading.Thread(target=go, daemon=True).start()

    t0 = time.time()
    while not done.is_set() and time.time() - t0 < 10:
        win32gui.PumpWaitingMessages()
        time.sleep(0.01)

    got = win32gui.GetWindowText(hwnd)
    print("focus was ours at paste:", state["fg_at_paste"] == hwnd)
    print("RESULT:", repr(got))
    print("CLIPBOARD RESTORED:", _get_clipboard_text() == before)
    print("PASS" if got == EXPECT else "FAIL")
    try:
        win32gui.DestroyWindow(hwnd)
    except Exception:  # noqa: BLE001 - окно могли закрыть вручную
        pass


if __name__ == "__main__":
    main()
