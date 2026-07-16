"""Проверка главного риска этапа 6: удержит ли Qt фокус чужого окна.

Оверлей всплывает над окном, в которое человек диктует. Если он заберёт фокус -
Ctrl+V уедет не туда, и диктовка сломается. На Windows это лечится флагом
WS_EX_NOACTIVATE, который мы сейчас ставим руками в layered.py (426 строк
ctypes). План (0.6) утверждает, что Qt даёт его сам, кроссплатформенно:

    qwindowswindow.cpp:814
    if (flags & Qt::WindowDoesNotAcceptFocus) exStyle |= WS_EX_NOACTIVATE;

Проверяем не по исходникам Qt, а на живой машине - и сразу оба варианта:

  full  - Frameless | WindowStaysOnTop | Tool | WindowDoesNotAcceptFocus
  trap  - то же БЕЗ WindowDoesNotAcceptFocus. Это ходовой рецепт из интернета,
          он же стоит в whisper-writer (status_window.py:26). План называет его
          ловушкой - проверяем и это тоже: тест обязан покраснеть.

Меряем два факта, а не один:
  1. стоит ли WS_EX_NOACTIVATE в реальном ex-стиле окна;
  2. осталось ли активным чужое окно после show() - это и есть то, что ломается.

    python tools/probe_qt_overlay.py
"""

import ctypes
import ctypes.wintypes as wt
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080

u32 = ctypes.WinDLL("user32", use_last_error=True)
# argtypes обязательны: без них ctypes считает хэндлы 32-битными и на x64
# рвёт старшие биты (см. HANDOFF, раздел Win32).
u32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
u32.GetForegroundWindow.restype = wt.HWND
u32.GetWindowTextW.argtypes = [wt.HWND, ctypes.c_wchar_p, ctypes.c_int]


def _title(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(200)
    u32.GetWindowTextW(hwnd, buf, 200)
    return buf.value or "?"


def probe(name: str, no_focus: bool) -> dict:
    flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    if no_focus:
        flags |= Qt.WindowDoesNotAcceptFocus

    before = u32.GetForegroundWindow()
    w = QWidget()
    w.setWindowFlags(flags)
    w.setAttribute(Qt.WA_TranslucentBackground)
    w.setGeometry(60, 60, 260, 44)
    w.show()
    QApplication.processEvents()

    hwnd = int(w.winId())
    ex = u32.GetWindowLongPtrW(wt.HWND(hwnd), GWL_EXSTYLE)
    after_show = u32.GetForegroundWindow()

    # Показать мало: Qt::Tool сам по себе окно не активирует, и на одном show()
    # оба варианта выглядят одинаково безобидно. Ломается всё, когда окно
    # ПЫТАЮТСЯ активировать - кликом по пилюле или случайным raise/activate из
    # кода. Вот тут WS_EX_NOACTIVATE и оказывается единственной защитой.
    w.raise_()
    w.activateWindow()
    QApplication.processEvents()
    after_activate = u32.GetForegroundWindow()

    w.hide()
    w.deleteLater()
    QApplication.processEvents()

    return {
        "name": name,
        "noactivate": bool(ex & WS_EX_NOACTIVATE),
        "topmost": bool(ex & WS_EX_TOPMOST),
        "toolwindow": bool(ex & WS_EX_TOOLWINDOW),
        "kept_show": bool(before) and before == after_show,
        "kept_activate": bool(before) and before == after_activate,
        "before": _title(before),
        "after": _title(after_activate),
    }


def main() -> None:
    app = QApplication(sys.argv)
    print(f"Qt {app.applicationVersion() or ''} — активное окно сейчас: "
          f"{_title(u32.GetForegroundWindow())!r}\n")

    rows = [probe("full (с WindowDoesNotAcceptFocus)", True),
            probe("trap (рецепт из интернета)", False)]

    print(f"{'вариант':<36} {'NOACTIVATE':>11} {'TOPMOST':>8} {'TOOL':>5} "
          f"{'цел:show':>9} {'цел:activate':>13}")
    print("-" * 90)
    for r in rows:
        print(f"{r['name']:<36} {str(r['noactivate']):>11} {str(r['topmost']):>8} "
              f"{str(r['toolwindow']):>5} {str(r['kept_show']):>9} "
              f"{str(r['kept_activate']):>13}")
    print()
    for r in rows:
        if not r["kept_activate"]:
            print(f"  {r['name']}: фокус ушёл {r['before']!r} -> {r['after']!r}")

    full, trap = rows
    ok = full["noactivate"] and full["kept_activate"]
    print()
    print(f"Qt ставит WS_EX_NOACTIVATE сам:     {'ДА' if full['noactivate'] else 'НЕТ'}")
    print(f"Оверлей не крадёт фокус даже при activateWindow(): "
          f"{'ДА' if full['kept_activate'] else 'НЕТ'}")
    print(f"Рецепт без флага - ловушка:         "
          f"{'ДА, покраснел' if not trap['kept_activate'] else 'на show() не краснеет'}")
    print()
    print("ИТОГ:", "layered.py можно выбрасывать" if ok else
          "ЭТАП 6 ПОД ВОПРОСОМ - Qt фокус не удержал")


if __name__ == "__main__":
    main()
