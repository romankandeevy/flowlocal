"""Единственное место, где программа ветвится по операционной системе.

Правило: остальной код НЕ трогает `ctypes.WinDLL` / `win32*` / `winreg`
напрямую, а зовёт функции отсюда. На Windows здесь настоящая реализация, на
macOS и прочих - заглушка, которая пишет в журнал понятную фразу и возвращает
безопасное «ничего не сделал». Так ветка по ОС живёт в одном файле, а не
расползается по коду невидимыми `if`-ами.

Признак ОС - `sys.platform` (win32 / darwin / прочее), а НЕ `os.name`: у macOS и
Linux `os.name` одинаковый ('posix'), различить их по нему нельзя.

Почему часть Win32 всё же осталась в своих модулях (`layered`, `inserter`,
`media`, `wakeup`, `audiofile`), а не переехала сюда целиком. Там она уже заперта
по одному концерну на файл и снабжена собственной заглушкой под darwin;
перетащить её сюда значило бы завести второе место, где однажды починят только
одно. Отсюда берётся ровно то, что раньше лежало в `app.py` голым ctypes и
ломало не-Windows на ровном месте: сигнал (`beep`), защита от второго запуска и
фатальное окно. Флаги `IS_WINDOWS`/`IS_MAC`/`CAN_HOTKEYS` - общий источник
правды об ОС для всех остальных модулей.

macOS сейчас только ЗАПУСКАЕТСЯ и показывает окна. Хоткеи, вставка текста,
автозапуск, пауза музыки, слух за сном - мёртвые заглушки: они логируют и
деградируют, но не работают. Это осознанно, а не забыто.
"""

import sys

PLATFORM = sys.platform
IS_WINDOWS = PLATFORM == "win32"
IS_MAC = PLATFORM == "darwin"

# Библиотека keyboard - только под Windows (requirements.txt), а вся привязка
# глобальных хоткеев в app.py стоит на ней. На macOS путь другой (pynput поверх
# Quartz) и это отдельная большая работа. Пока флаг честно говорит «эта ОС
# хоткеи ещё не умеет», и привязка тихо не делается, вместо того чтобы упасть.
CAN_HOTKEYS = IS_WINDOWS

_OS_HUMAN = "macOS" if IS_MAC else ("Windows" if IS_WINDOWS else "этой системе")

_logger = None
_noted: set[str] = set()


def set_logger(fn) -> None:
    """Куда писать сообщения заглушек. app.py отдаёт сюда свой `log` сразу после
    его объявления, чтобы строки шли в тот же flow.log (с ротацией и меткой
    времени), а не в разные места."""
    global _logger
    _logger = fn


def _log(msg: str) -> None:
    if _logger is not None:
        try:
            _logger(msg)
            return
        except Exception:  # noqa: BLE001 - журнал не должен ронять вызвавшего
            pass
    # Запасной путь, если логгер ещё не отдан: тот же файл, лениво - иначе
    # получился бы цикл импорта (app_paths импортирует нас).
    try:
        import time

        from app_paths import LOG_PATH

        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:  # noqa: BLE001
        try:
            print(msg)
        except Exception:  # noqa: BLE001
            pass


def note_unsupported(feature: str) -> None:
    """Сказать в журнал ОДИН раз, что функция на этой ОС пока не работает.

    Один раз - потому что часть заглушек зовётся по таймеру (проверка глухоты,
    пересборка хоткеев после «пробуждения»), и без дедупликации журнал забился
    бы одной и той же строкой круглые сутки.
    """
    if feature in _noted:
        return
    _noted.add(feature)
    _log(f"{feature}: на {_OS_HUMAN} пока не работает")


# ---------- сигнал (был winsound прямо в app.py) ----------


def beep(freq: int, dur: int, enabled: bool) -> None:
    """Короткий звук - подтверждение старта/конца диктовки. Выключен - молчим."""
    if not enabled:
        return
    if not IS_WINDOWS:
        # winsound - только Windows. На macOS звука пока нет, и это не повод
        # шуметь в журнале на каждую диктовку: звук - украшение, не диктовка.
        return
    import threading
    import winsound

    threading.Thread(target=winsound.Beep, args=(freq, dur), daemon=True).start()


# ---------- один экземпляр (был CreateMutexW прямо в app.py) ----------


def single_instance() -> bool:
    """True - мы единственный экземпляр и можем работать дальше.

    Windows: именованный мьютекс, `ERROR_ALREADY_EXISTS` - значит второй.
    macOS/прочее: пока без блокировки (всегда True). Защита от второго запуска
    на маке - отдельная задача (лок-файл или опора на QLocalServer); для «просто
    показать окно» второй экземпляр максимум заведёт второй значок в menu bar.
    """
    if not IS_WINDOWS:
        note_unsupported("защита от второго запуска")
        return True
    import ctypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    # хэндл намеренно не закрываем: мьютекс должен жить, пока живёт процесс
    k32.CreateMutexW(None, False, "FlowLocal_single_instance")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def already_running_notice() -> None:
    """Сказать «уже запущен», когда достучаться до живого экземпляра не вышло."""
    if IS_WINDOWS:
        import ctypes

        try:
            ctypes.windll.user32.MessageBoxW(
                None, "FlowLocal уже запущен - иконка в трее.", "FlowLocal", 0x40)
        except Exception:  # noqa: BLE001
            pass
        return
    _log("FlowLocal уже запущен - иконка в menu bar")


def fatal_message(text: str, log_path: str) -> None:
    """Показать фатальную ошибку, когда своего окна ещё/уже нет.

    Windows: MessageBoxW. macOS: osascript (`display alert`) - `ctypes.windll`
    там нет вовсе, и обращение к нему само стало бы второй ошибкой поверх первой.
    И там, и там это лучшее усилие: сама ошибка уже в журнале, окно - лишь чтобы
    человек без консоли вообще узнал, что что-то случилось.
    """
    body = f"{text}\n\nЧто случилось - записано в журнале работы:\n{log_path}"
    if IS_WINDOWS:
        import ctypes

        try:
            ctypes.windll.user32.MessageBoxW(None, body, "FlowLocal", 0x10)
        except Exception:  # noqa: BLE001
            pass
        return
    try:
        import subprocess

        # AppleScript-строка не любит сырые кавычки, слэши и переводы строк -
        # экранируем первое и сводим второе в одну строку.
        safe = (body.replace("\\", "\\\\").replace('"', '\\"')
                    .replace("\n", " / "))
        subprocess.run(
            ["osascript", "-e", f'display alert "FlowLocal" message "{safe}"'],
            check=False, timeout=10)
    except Exception:  # noqa: BLE001 - окно не показалось, но ошибка уже в журнале
        pass
