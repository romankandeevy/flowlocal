"""Воспроизведение бага «вторая диктовка стирает первую».

Жалоба: надиктовал, надиктовал ещё раз - в поле осталась только вторая фраза.
Проверяем ровно то, что делает app._process: две вставки подряд, тем же
inserter'ом, в настоящий EDIT. Если после второй в поле обе фразы - виноват не
inserter, и копать надо в жест (ctrl+mouse4 доезжает до чужого окна) или в
целевое приложение.

Второй прогон - с зажатым Ctrl: человек держит его для ctrl+mouse4, и вставка
случается ровно в этот момент.

    python tools/repro_double_insert.py
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

from inserter import insert  # noqa: E402

VK_CONTROL = 0x11


def _force_foreground(hwnd: int) -> None:
    # Фокус берём кликом: трюк «нажать Alt перед SetForegroundWindow» ядовит -
    # отпускание Alt вводит окно в режим меню, и следующий Ctrl+V съедается
    # (HANDOFF, раздел Win32).
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
    r = win32gui.GetWindowRect(hwnd)
    x, y = (r[0] + r[2]) // 2, (r[1] + r[3]) // 2
    win32api.SetCursorPos((x, y))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.2)


def run(hold_ctrl: bool) -> str:
    hwnd = win32gui.CreateWindow(
        "EDIT", "repro",
        win32con.WS_OVERLAPPEDWINDOW | win32con.WS_VISIBLE | win32con.ES_MULTILINE,
        200, 200, 700, 180, 0, 0, 0, None)
    win32gui.SendMessage(hwnd, win32con.WM_SETTEXT, 0, "")
    _force_foreground(hwnd)

    done = threading.Event()

    def go() -> None:
        time.sleep(0.5)
        if hold_ctrl:
            win32api.keybd_event(VK_CONTROL, win32api.MapVirtualKey(VK_CONTROL, 0), 0, 0)
        insert("Первая фраза. ", mode="paste", restore=True)
        time.sleep(0.9)          # как между двумя диктовками
        if hold_ctrl:
            win32api.keybd_event(VK_CONTROL, win32api.MapVirtualKey(VK_CONTROL, 0), 0, 0)
        insert("Вторая фраза. ", mode="paste", restore=True)
        time.sleep(0.6)
        if hold_ctrl:
            win32api.keybd_event(VK_CONTROL, win32api.MapVirtualKey(VK_CONTROL, 0),
                                 win32con.KEYEVENTF_KEYUP, 0)
        done.set()

    threading.Thread(target=go, daemon=True).start()
    t0 = time.time()
    while not done.is_set() and time.time() - t0 < 20:
        win32gui.PumpWaitingMessages()   # качаем очередь СВОЕГО потока
        time.sleep(0.01)
    got = win32gui.GetWindowText(hwnd)
    win32gui.DestroyWindow(hwnd)
    return got


def main() -> None:
    print("Не трогайте клавиатуру ~10 с.\n")
    for hold in (False, True):
        got = run(hold)
        ok = "Первая" in got and "Вторая" in got
        print(f"Ctrl {'зажат' if hold else 'свободен'}: {'PASS' if ok else 'FAIL'}")
        print(f"  в поле: {got!r}")
        if not ok:
            print("  ^ первая фраза пропала - виноват inserter\n")
        else:
            print()


if __name__ == "__main__":
    main()
