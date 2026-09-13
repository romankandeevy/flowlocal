"""Переживает ли библиотека keyboard цикл «привязал - снял - привязал»?

    python tools/probe_keyboard_rebind.py            # голая библиотека
    python tools/probe_keyboard_rebind.py --with-app # она же, но рядом живёт App

Вопрос ровно один: если хоткей перестаёт срабатывать после перепривязки, это
наша вина или её?

Голый прогон отвечает: библиотека НЕ виновата, 6 кругов из 6. Значит виновата
разница между пробой и тестом, а разница одна - `App()`. Флаг --with-app вносит
её и больше ничего: те же круги, тот же хоткей, но в процессе живут Qt, оверлей
и поток микрофона.

Подозрение - в устройстве keyboard (_generic.py, pre_process_event):

    with _pressed_events_lock:
        hotkey = tuple(sorted(_pressed_events))
    for callback in self.nonblocking_hotkeys[hotkey]:

Набор зажатых клавиш читается не в момент события, а когда до него дойдёт
очередь в потоке обработки. Отстанет поток - клавиши уже отпущены, набор
другой, совпадения нет, событие потеряно молча. HANDOFF про это и предупреждал:
«от захватов GIL голодает поток слушателя keyboard».

Зачем: test_hotkey.py валится недетерминированно (6 провалов в одном прогоне,
11 в следующем на том же коде), и у каждого провала событие просто не приходит.
Все провалы - после первого полного снятия хуков.

Подозрение на устройство keyboard: сочетание сопоставляется по ТОЧНОМУ набору
зажатых клавиш (`hotkey = tuple(sorted(_pressed_events))`), а `_pressed_events`
- глобальный словарь, который наполняет низкоуровневый хук. Застрянет в нём
лишняя клавиша - набор не совпадёт уже никогда, и хоткей умрёт молча.

Тест шлёт настоящие нажатия. Не трогать клавиатуру во время прогона.
"""

import sys
import time

import keyboard
import win32api
import win32con

HOTKEY = "ctrl+alt+f9"
_VK = {"ctrl": 0x11, "alt": 0x12, "f9": 0x78}
ROUNDS = 6


def _down(vk: int) -> None:
    win32api.keybd_event(vk, win32api.MapVirtualKey(vk, 0), 0, 0)
    time.sleep(0.01)


def _up(vk: int) -> None:
    win32api.keybd_event(vk, win32api.MapVirtualKey(vk, 0),
                         win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.01)


def tap() -> None:
    for k in ("ctrl", "alt", "f9"):
        _down(_VK[k])
    time.sleep(0.12)
    for k in ("f9", "alt", "ctrl"):
        _up(_VK[k])
    time.sleep(0.2)


def stuck() -> str:
    """Что keyboard считает зажатым прямо сейчас. Пусто - как и должно быть."""
    try:
        with keyboard._pressed_events_lock:  # noqa: SLF001
            ev = dict(keyboard._pressed_events)  # noqa: SLF001
    except Exception as e:  # noqa: BLE001
        return f"<не прочитать: {e}>"
    if not ev:
        return "-"
    return ", ".join(f"{e.name}(sc={sc})" for sc, e in sorted(ev.items()))


def main() -> None:
    app = None
    if "--with-app" in sys.argv:
        import os

        os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sys.path.insert(0, os.getcwd())
        from app import App

        app = App()          # Qt, оверлей, микрофон - и всё это в нашем GIL
        print("App поднят: Qt + оверлей + поток микрофона в процессе\n")

    fired = []
    ok = True
    print(f"{'раунд':<7}{'сработал':<10}{'зажато по мнению keyboard':<40}")
    print("-" * 60)
    for i in range(1, ROUNDS + 1):
        fired.clear()
        h = keyboard.add_hotkey(HOTKEY, lambda: fired.append(1), suppress=False)
        time.sleep(0.35)              # дать хуку встать
        tap()
        got = len(fired)
        left = stuck()
        mark = "да" if got == 1 else f"НЕТ ({got})"
        if got != 1:
            ok = False
        print(f"{i:<7}{mark:<10}{left:<40}")
        keyboard.remove_hotkey(h)     # ... и на следующем круге привяжем заново
        time.sleep(0.1)

    print()
    if app is not None:
        if ok:
            print("ВЫВОД: с App хоткеи тоже живы. Дело не в GIL - копать дальше.")
        else:
            print("ВЫВОД: голая библиотека - 6/6, а с App ломается.")
            print("       Значит виновата не keyboard, а то, чем App грузит процесс:")
            print("       поток обработки keyboard не успевает прочитать набор")
            print("       зажатых клавиш, пока они ещё зажаты.")
        try:
            app.recorder.close()
            app.overlay.destroy()
        except Exception:  # noqa: BLE001
            pass
    elif ok:
        print("ВЫВОД: keyboard переживает перепривязку. Виноват НАШ код.")
        print("       Теперь: python tools/probe_keyboard_rebind.py --with-app")
    else:
        print("ВЫВОД: keyboard НЕ переживает перепривязку - это её баг.")
        print("       Столбец «зажато» показывает, застряла ли клавиша.")
    sys.stdout.flush()
    import os

    os._exit(0 if ok else 1)     # мимо уборки Qt: она сорит в вывод


if __name__ == "__main__":
    main()
