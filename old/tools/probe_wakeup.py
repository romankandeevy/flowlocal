"""Проба слуха за пробуждением - без усыпления машины.

Настоящую проверку («закрыл ноутбук, открыл, ввёл PIN, нажал хоткей») машина
за нас не сделает, и она всё равно обязательна. Но всё остальное проверяется
здесь и сейчас, а без этого настоящая проверка просто не имеет смысла:

  1. окно создаётся и подписка на события сеанса принята системой;
  2. WM_WTSSESSION_CHANGE доходит до нашей оконной процедуры через обычный
     цикл сообщений - то есть Qt его не съест;
  3. залипшие клавиши вычищаются;
  4. смерть служебных потоков библиотеки замечается, а поднимать их мы
     соглашаемся только когда это безопасно.

Запуск: python tools/probe_wakeup.py
"""

import ctypes
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import keyboard  # noqa: E402
import wakeup  # noqa: E402

ok = True


class _DeadThread:
    """Поток, который «умер». Настоящий убить нельзя - подменяем."""

    def is_alive(self):
        return False


def say(good: bool, text: str) -> None:
    global ok
    ok = ok and good
    print(("  ок   " if good else "ПРОВАЛ ") + text)


def main() -> int:
    lines: list[str] = []
    woke: list[str] = []

    w = wakeup.WakeWatcher(lambda: woke.append("wake"), lines.append)
    say(w.start(), "окно создано, подписка на события сеанса принята")
    if not w.hwnd:
        print("\n".join(lines))
        return 1

    # Шлём себе то же сообщение, что пришлёт система при разблокировке.
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    u32.SendMessageW(w.hwnd, wakeup.WM_WTSSESSION_CHANGE,
                     wakeup.WTS_SESSION_UNLOCK, 0)
    say(len(woke) == 1, f"разблокировка сеанса разбужена ({len(woke)} раз)")

    # Пробуждение из сна - другое сообщение, тот же итог.
    u32.SendMessageW(w.hwnd, wakeup.WM_POWERBROADCAST,
                     wakeup.PBT_APMRESUMEAUTOMATIC, 0)
    say(len(woke) == 2, f"пробуждение из сна разбужено ({len(woke)} раз)")

    # Ловушка: посторонние значения тех же сообщений будить НЕ должны, иначе
    # хоткеи пересобирались бы на каждый чих (WM_POWERBROADCAST шлётся и при
    # смене режима питания, и при разряде батареи).
    u32.SendMessageW(w.hwnd, wakeup.WM_POWERBROADCAST, 0x0004, 0)  # PBT_APMSUSPEND
    u32.SendMessageW(w.hwnd, wakeup.WM_WTSSESSION_CHANGE, 0x7, 0)  # SESSION_LOCK
    say(len(woke) == 2, f"засыпание и блокировка не будят ({len(woke)} раз)")

    # Залипшие клавиши.
    keyboard._pressed_events[42] = object()
    n = wakeup.clear_stuck_keys(keyboard, lines.append)
    say(n >= 1 and not keyboard._pressed_events,
        f"залипшие клавиши вычищены (было {n})")

    # --- сторож глухоты ---
    keyboard.add_hotkey("ctrl+alt+f24", lambda: None)   # поднять слушателя
    say(wakeup.listener_dead(keyboard) == "", "живого слушателя не считаем мёртвым")

    listener = keyboard._listener
    for attr, what in (("listening_thread", "поток хука"),
                       ("processing_thread", "поток разбора")):
        real = getattr(listener, attr)
        setattr(listener, attr, _DeadThread())
        say(bool(wakeup.listener_dead(keyboard)), f"{what} умер - заметили")
        setattr(listener, attr, real)
    say(wakeup.listener_dead(keyboard) == "", "после починки снова тихо")

    # ЛОВУШКА, ради которой условие и сужено: пока хоть один поток жив,
    # поднимать слушателя нельзя - получим второй хук и двойную вставку.
    real = listener.listening_thread
    listener.listening_thread = _DeadThread()
    say(not wakeup.can_revive(keyboard),
        "один поток жив - поднимать отказываемся (иначе задвоится вставка)")
    proc = listener.processing_thread
    listener.processing_thread = _DeadThread()
    say(wakeup.can_revive(keyboard), "оба потока мертвы - поднять можно")
    listener.listening_thread, listener.processing_thread = real, proc
    say(not wakeup.can_revive(keyboard), "на живом слушателе поднимать нечего")

    w.stop()
    say(w.hwnd is None, "окно снято")

    print("\n".join("       " + line for line in lines))
    print("\nИТОГ:", "всё сходится" if ok else "ЕСТЬ ПРОВАЛЫ")
    print("Осталось руками: усыпить, разбудить, нажать хоткей.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
