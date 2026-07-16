"""Тест хоткеев: привязка, пересборка при смене, снятие на время захвата,
режимы удержания и переключателя.

Модель не грузится - проверяется только слой хоткеев, поэтому быстро.
Настоящие нажатия шлются через keyboard, как это делает человек.

Запуск: python test_hotkey.py
"""

import sys
import time

import keyboard
import win32api
import win32con

from app import App

OLD = "ctrl+shift+space"
NEW = "ctrl+alt+f9"

# Нажимаем через keybd_event, а не keyboard.press: keyboard помечает свои
# посылки как «replay» и её же слушатель их пропускает - хук в том же процессе
# не сработал бы никогда, и тест бы молча врал.
#
# Скан-код обязателен. keybd_event(vk, 0, ...) хук ещё увидит, но add_hotkey
# сопоставляет сочетания именно по скан-кодам, и с нулём не срабатывает:
# сырые события идут, а хоткей - нет.
_VK = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12, "space": 0x20, "f9": 0x78,
       "esc": 0x1B}


def _down(vk: int) -> None:
    win32api.keybd_event(vk, win32api.MapVirtualKey(vk, 0), 0, 0)
    time.sleep(0.01)


def _up(vk: int) -> None:
    win32api.keybd_event(vk, win32api.MapVirtualKey(vk, 0),
                         win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.01)


def tap(hotkey: str, hold: float = 0.12) -> None:
    keys = [_VK[p.strip()] for p in hotkey.split("+")]
    for vk in keys:
        _down(vk)
    time.sleep(hold)
    for vk in reversed(keys):
        _up(vk)
    time.sleep(0.15)


def tap_repeat(hotkey: str, times: int = 4) -> None:
    """Зажатая клавиша: Windows шлёт KEYDOWN снова и снова, пока держат.

    Пришлось воспроизводить руками: автоповтор рождается в драйвере клавиатуры,
    и у события, посланного keybd_event, его просто нет - подержать подольше
    недостаточно. Ради этого всё и затевалось: в режиме переключателя
    автоповтор без защиты дёргал бы старт-стоп-старт десятки раз в секунду.
    """
    keys = [_VK[p.strip()] for p in hotkey.split("+")]
    for vk in keys:
        _down(vk)
    for _ in range(times):
        _down(keys[-1])
        time.sleep(0.03)
    for vk in reversed(keys):
        _up(vk)
    time.sleep(0.15)


def main() -> None:
    app = App()
    calls: list[str] = []

    # Заглушки повторяют ровно одно свойство настоящих методов - ранний выход
    # по состоянию записи. Без него счётчики врут: отпускание комбинации
    # прилетает по разу на КАЖДУЮ её клавишу, и «finish» насчиталось бы три.
    # А режим переключателя без живого _recording вообще нечем проверить: он
    # решает «старт или стоп» именно по нему.
    def fake_start(mode="hold"):
        if app._recording:
            return
        app._recording = True
        app._rec_mode = mode
        calls.append("start")

    def fake_finish():
        if not app._recording:
            return
        app._recording = False
        calls.append("finish")

    def fake_cancel():
        if not app._recording:
            return
        app._recording = False
        calls.append("cancel")

    # подменяем до привязки: add_hotkey запоминает переданную функцию
    app._start_recording = lambda mode="hold": fake_start(mode)
    app._finish_recording = fake_finish
    app._cancel_recording = fake_cancel
    app.cfg["hotkey_hold"] = OLD
    app.cfg["hotkey_toggle"] = ""

    results = []

    def check(name: str, cond: bool) -> None:
        results.append(cond)
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")

    try:
        app._hotkey_bind()
        print("--- привязка")
        calls.clear()
        tap(OLD)
        check("хоткей срабатывает", calls.count("start") == 1)
        check("отпускание ловится", "finish" in calls)

        print("--- смена хоткея через настройки")
        new_cfg = dict(app.cfg)
        new_cfg["hotkey_hold"] = NEW
        app._on_config_change(new_cfg)
        calls.clear()
        tap(OLD)
        check("старый хоткей больше не срабатывает", calls.count("start") == 0)
        calls.clear()
        tap(NEW)
        check("новый хоткей срабатывает", calls.count("start") == 1)

        print("--- захват хоткея в настройках")
        app._on_hotkey_capture(True)
        calls.clear()
        tap(NEW)
        check("на время захвата хоткей снят", calls.count("start") == 0)
        app._on_hotkey_capture(False)
        calls.clear()
        tap(NEW)
        check("после захвата хоткей вернулся", calls.count("start") == 1)

        print("--- битый хоткей в конфиге")
        bad = dict(app.cfg)
        bad["hotkey_hold"] = "нетакойклавиши"
        app._on_config_change(bad)
        check("откат на умолчание", app.cfg["hotkey_hold"] == "ctrl+shift+space")
        calls.clear()
        tap("ctrl+shift+space")
        check("умолчательный хоткей работает", calls.count("start") == 1)

        print("--- бинд-переключатель")
        tog = dict(app.cfg)
        tog["hotkey_hold"] = ""        # оставляем только переключатель
        tog["hotkey_toggle"] = NEW
        app._on_config_change(tog)
        calls.clear()
        tap(NEW)
        check("первое нажатие - старт", calls == ["start"])
        tap(NEW)
        check("второе нажатие - стоп", calls == ["start", "finish"])
        check("отпускание само по себе не останавливает", app._recording is False)

        calls.clear()
        tap_repeat(NEW)
        check("автоповтор зажатой клавиши не мигает старт-стоп", calls == ["start"])
        tap(NEW)                       # гасим запись за собой
        calls.clear()

        print("--- Esc отменяет запись переключателя")
        tap(NEW)
        tap("esc")
        check("Esc отменил", calls == ["start", "cancel"])
        check("после отмены не пишем", app._recording is False)

        print("--- пустой бинд ничего не вешает")
        none_cfg = dict(app.cfg)
        none_cfg["hotkey_hold"] = ""
        none_cfg["hotkey_toggle"] = ""
        app._on_config_change(none_cfg)
        calls.clear()
        tap(NEW)
        tap(OLD)
        check("без биндов ничего не срабатывает", calls == [])

        print("--- оба бинда живут одновременно")
        both = dict(app.cfg)
        both["hotkey_hold"] = OLD
        both["hotkey_toggle"] = NEW
        app._on_config_change(both)
        calls.clear()
        tap(OLD)
        check("удержание: старт+стоп за одно нажатие", calls == ["start", "finish"])
        calls.clear()
        tap(NEW)
        check("переключатель: только старт", calls == ["start"])
        tap(NEW)
        check("переключатель: второе нажатие - стоп", calls == ["start", "finish"])

        calls.clear()
        tap("esc")
        check("Esc без записи ничего не делает", calls == [])

        print("--- удержание не отменяется по Esc")
        # Esc-хук висит, пока есть бинд-переключатель, но отменять он обязан
        # только запись, начатую переключателем.
        calls.clear()
        _down(_VK["ctrl"]); _down(_VK["shift"]); _down(_VK["space"])
        time.sleep(0.15)
        tap("esc")
        check("Esc не трогает запись от удержания", calls == ["start"])
        _up(_VK["space"]); _up(_VK["shift"]); _up(_VK["ctrl"])
        time.sleep(0.2)
        check("удержание закончилось отпусканием", calls == ["start", "finish"])

        print("--- битый хоткей отмены")
        bad_undo = dict(app.cfg)
        bad_undo["undo_hotkey"] = "нетакойклавиши"
        app._on_config_change(bad_undo)
        calls.clear()
        tap(OLD)                       # OLD - бинд удержания: старт и стоп
        check("битая отмена не сломала диктовку", calls == ["start", "finish"])
    finally:
        app._hotkey_unbind()
        keyboard.unhook_all()
        app.recorder.close()
        app.overlay.destroy()
        # Был app.root.destroy() - корень tkinter, которого нет с этапа 7
        # (переезд на Qt). Тест из-за этого падал в уборке: проверки проходили,
        # но процесс валился с AttributeError и итог не печатался никогда.
        app.qapp.quit()

    print("\nИТОГ:", "PASS" if all(results) else "FAIL")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
