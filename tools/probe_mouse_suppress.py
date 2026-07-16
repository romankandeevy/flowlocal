"""Проверка: умеет ли pynput глотать боковую кнопку мыши.

Зачем. Наш мышиный бинд ловится библиотекой `mouse`, а она подавлять события
не умеет вовсе - кнопка долетает до чужого окна. Для X1 это не мелочь: в
Chromium и Electron X1 - это «Назад». Диктуешь в поле, жмёшь ctrl+mouse4, чтобы
начать вторую диктовку, - приложение уходит назад, поле очищается, и вторая
фраза ложится в пустое. Симптом ровно тот, на который жаловались: «прошлое
стирается полностью».

Здесь проверяется механизм, а не догадка: шлём X1 сам себе и смотрим, дошёл ли
он до окна, пока фильтр его глотает.

    python tools/probe_mouse_suppress.py
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
from pynput import mouse as pmouse  # noqa: E402

WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
XBUTTON1 = 1

seen = {"filter": 0, "click": 0}
listener: pmouse.Listener | None = None


def _filter(msg, data):
    if msg in (WM_XBUTTONDOWN, WM_XBUTTONUP):
        seen["filter"] += 1
        # Глотаем: до чужого окна кнопка не долетит.
        listener.suppress_event()


def _on_click(x, y, button, pressed):
    if button in (pmouse.Button.x1, pmouse.Button.x2):
        seen["click"] += 1


def main() -> None:
    global listener
    listener = pmouse.Listener(on_click=_on_click, win32_event_filter=_filter)
    listener.start()
    listener.wait()
    time.sleep(0.3)

    print("Шлю X1 сам себе (мышь не трогать)...")
    for _ in range(3):
        win32api.mouse_event(win32con.MOUSEEVENTF_XDOWN, 0, 0, XBUTTON1, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_XUP, 0, 0, XBUTTON1, 0)
        time.sleep(0.15)
    time.sleep(0.5)
    listener.stop()

    print(f"  фильтр увидел событий: {seen['filter']} (ждали 6: 3 нажатия + 3 отпускания)")
    print(f"  колбэк on_click:       {seen['click']} (ждали 0 - глотаем же)")
    # Ключевой вывод: suppress_event() глушит событие ЦЕЛИКОМ, включая наш
    # собственный on_click. Значит вся работа должна происходить в фильтре, а
    # колбэки pynput для подавляемых кнопок бесполезны.
    ok = seen["filter"] >= 6 and seen["click"] == 0
    print()
    print("ИТОГ:", "pynput ловит X1 и глотает его — работать надо в фильтре" if ok
          else "неожиданно: подавление ведёт себя иначе")


if __name__ == "__main__":
    main()
