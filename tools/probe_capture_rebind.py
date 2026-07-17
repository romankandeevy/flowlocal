"""Почему хоткей не оживает после захвата в настройках.

    python tools/probe_capture_rebind.py

Что уже известно (замерено, не предположено):
  - голая keyboard: привязка/снятие/привязка - 6 кругов из 6, работает;
  - она же рядом с App (Qt, оверлей, микрофон) - тоже 6 из 6;
  - но test_hotkey.py валится, и всегда после первого _on_hotkey_capture.

Значит дело не в библиотеке и не в GIL, а в том, ЧЕМ наш _hotkey_bind
отличается от голого add_hotkey: он вешает вокруг хоткея ещё хуки отпускания
(по одному на каждое имя модификатора), Esc и отмену.

Здесь воспроизводится ровно та последовательность, что валится в тесте, и после
каждого шага печатается, что об этом думает сама keyboard: какие сочетания у неё
зарегистрированы и на какие скан-коды висят хуки клавиш.
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import keyboard  # noqa: E402
import win32api  # noqa: E402
import win32con  # noqa: E402

from app import App  # noqa: E402

HK = "ctrl+alt+f9"
_VK = {"ctrl": 0x11, "alt": 0x12, "f9": 0x78}


def _down(vk):
    win32api.keybd_event(vk, win32api.MapVirtualKey(vk, 0), 0, 0)
    time.sleep(0.01)


def _up(vk):
    win32api.keybd_event(vk, win32api.MapVirtualKey(vk, 0), win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.01)


def tap():
    for k in ("ctrl", "alt", "f9"):
        _down(_VK[k])
    time.sleep(0.12)
    for k in ("f9", "alt", "ctrl"):
        _up(_VK[k])
    time.sleep(0.25)


def dump(tag: str) -> None:
    """Что keyboard считает зарегистрированным прямо сейчас."""
    ls = keyboard._listener  # noqa: SLF001
    nb_hk = {k: len(v) for k, v in ls.nonblocking_hotkeys.items() if v}
    nb_keys = {k: len(v) for k, v in ls.nonblocking_keys.items() if v}
    print(f"  [{tag}]")
    print(f"    nonblocking_hotkeys (набор скан-кодов -> сколько колбэков): {nb_hk}")
    print(f"    nonblocking_keys    (скан-код -> сколько хуков):            {nb_keys}")
    print(f"    _hotkeys записей: {len(keyboard._hotkeys)}  "  # noqa: SLF001
          f"_hooks записей: {len(keyboard._hooks)}")  # noqa: SLF001


def main() -> None:
    app = App()
    fired = []
    app._start_recording = lambda mode="hold": fired.append("start")
    app._finish_recording = lambda: fired.append("finish")
    app._cancel_recording = lambda: fired.append("cancel")
    app.cfg["hotkey_hold"] = HK
    app.cfg["hotkey_toggle"] = ""
    app.cfg["undo_hotkey"] = ""

    print("\n=== ШАГ 1: первая привязка (в тесте ПРОХОДИТ) ===")
    app._hotkey_bind()
    time.sleep(0.35)
    dump("после _hotkey_bind")
    fired.clear()
    tap()
    print(f"  сработало: {fired or 'НЕТ'}")
    step1 = bool(fired)

    print("\n=== ШАГ 2: захват включён - хоткей снят (в тесте ПРОХОДИТ) ===")
    app._on_hotkey_capture(True)
    dump("после _on_hotkey_capture(True)")
    fired.clear()
    tap()
    print(f"  сработало: {fired or 'НЕТ'}  (и не должно)")

    print("\n=== ШАГ 3: захват выключен - хоткей вернулся (в тесте ВАЛИТСЯ) ===")
    app._on_hotkey_capture(False)
    time.sleep(0.35)
    dump("после _on_hotkey_capture(False)")
    fired.clear()
    tap()
    print(f"  сработало: {fired or 'НЕТ'}")
    step3 = bool(fired)

    print("\n" + "=" * 62)
    if step1 and step3:
        print("Хоткей пережил захват. Значит валит тест что-то ДО этого места.")
    elif step1 and not step3:
        print("ВОСПРОИЗВЕЛОСЬ: после захвата хоткей мёртв.")
        print("Сравните строки nonblocking_hotkeys на шаге 1 и на шаге 3 -")
        print("если набор скан-кодов разный, значит перепривязка вешает хоткей")
        print("не туда, куда первая привязка.")
    else:
        print("Не сработал даже первый - проба неверна, чинить её.")

    try:
        app._hotkey_unbind()
        app.recorder.close()
        app.overlay.destroy()
    except Exception:  # noqa: BLE001
        pass
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
