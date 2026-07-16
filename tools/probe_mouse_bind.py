"""Проверка мышиного бинда после переезда на pynput.

Главное, что здесь проверяется, - не «сработал ли бинд» (это видно и так), а
что кнопка НЕ долетает до чужого окна. Ради этого рядом поднимается настоящий
EDIT: он получает WM_XBUTTONDOWN, если событие просочилось.

Симптом, который лечим: X1 в Chromium и Electron - это «Назад». Диктуешь,
жмёшь ctrl+mouse4 ради второй диктовки, приложение уходит назад, поле
очищается, вторая фраза ложится в пустое.

    python tools/probe_mouse_bind.py
"""

import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import win32api  # noqa: E402
import win32con  # noqa: E402
import win32gui  # noqa: E402

import app as A  # noqa: E402

XBUTTON1 = 1
WM_XBUTTONDOWN = 0x020B
VK_CONTROL = 0x11


def main() -> None:
    got = {"xbutton": 0}
    fired = {"press": 0, "release": 0}

    def wndproc(hwnd, msg, wp, lp):
        if msg == WM_XBUTTONDOWN:
            got["xbutton"] += 1        # событие просочилось до окна
        return win32gui.DefWindowProc(hwnd, msg, wp, lp)

    cls = win32gui.WNDCLASS()
    cls.lpszClassName = "FlowLocalProbe"
    cls.lpfnWndProc = wndproc
    win32gui.RegisterClass(cls)
    hwnd = win32gui.CreateWindow(
        "FlowLocalProbe", "probe",
        win32con.WS_OVERLAPPEDWINDOW | win32con.WS_VISIBLE,
        300, 300, 420, 140, 0, 0, 0, None)
    win32gui.SetForegroundWindow(hwnd)
    # Курсор - НАД окном: события мыши уходят в окно под курсором, а не в
    # активное. Без этого проба ничего не доказывает - X1 просто улетал мимо,
    # и «просочилось 0» получалось само собой.
    r = win32gui.GetWindowRect(hwnd)
    win32api.SetCursorPos(((r[0] + r[2]) // 2, (r[1] + r[3]) // 2))
    time.sleep(0.3)

    a = A.App.__new__(A.App)               # без модели и микрофона
    a._mouse_binds = []
    a._mouse_listener = None
    a._held = {"hold": False, "toggle": False}
    a._dictation_press = lambda m: fired.__setitem__("press", fired["press"] + 1)
    a._dictation_release = lambda m: fired.__setitem__("release", fired["release"] + 1)
    a.ui = lambda fn, *args: fn(*args)     # без Qt: зовём сразу
    a._bind_mouse("toggle", ["ctrl"], "x")
    time.sleep(0.5)

    print("Шлю Ctrl+X1 (мышь и клавиатуру не трогать)...")
    scan = win32api.MapVirtualKey(VK_CONTROL, 0)
    for _ in range(3):
        win32api.keybd_event(VK_CONTROL, scan, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_XDOWN, 0, 0, XBUTTON1, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_XUP, 0, 0, XBUTTON1, 0)
        win32api.keybd_event(VK_CONTROL, scan, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.2)
        t0 = time.time()
        while time.time() - t0 < 0.2:
            win32gui.PumpWaitingMessages()
            time.sleep(0.01)

    print("\nШлю X1 БЕЗ Ctrl - это не наш жест, обязан пройти в окно...")
    before = got["xbutton"]
    for _ in range(2):
        win32api.mouse_event(win32con.MOUSEEVENTF_XDOWN, 0, 0, XBUTTON1, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_XUP, 0, 0, XBUTTON1, 0)
        t0 = time.time()
        while time.time() - t0 < 0.3:
            win32gui.PumpWaitingMessages()
            time.sleep(0.01)
    leaked_plain = got["xbutton"] - before

    a._hotkey_unbind() if hasattr(a, "_hk_handles") else a._mouse_listener.stop()
    win32gui.DestroyWindow(hwnd)

    print()
    print(f"  бинд сработал раз:            {fired['press']} (ждали 3)")
    print(f"  Ctrl+X1 просочилось в окно:   {got['xbutton'] - leaked_plain} (ждали 0)")
    print(f"  голый X1 дошёл до окна:       {leaked_plain} (ждали 2 - не наш жест)")
    ok = fired["press"] == 3 and (got["xbutton"] - leaked_plain) == 0 and leaked_plain == 2
    print()
    print("ИТОГ:", "PASS - свой жест глотаем, чужой пропускаем" if ok else "FAIL")


if __name__ == "__main__":
    main()
