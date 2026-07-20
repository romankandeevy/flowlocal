"""Проба: пройдёт ли `import` на macOS - не выходя из Windows.

Зачем. Список «мест, которые надо обернуть» устаревает быстрее, чем его
дочитывают: часть гардов уже расставлена, часть нет, и сверять их глазами по
списку - это верить списку, а не коду. Здесь мы притворяемся маком и честно
пытаемся импортировать. Что упало - то и осталось портировать.

Как притворяемся. Три вещи, которых на macOS нет по-настоящему:
  - `sys.platform` там `darwin`, и по нему ветвится `platform_api`;
  - модулей `winreg`, `win32*`, `keyboard`, `winsound` нет вовсе -
    подсовываем поисковик, который отвечает на них `ModuleNotFoundError`;
  - у `ctypes` нет `WinDLL`, `windll`, `WINFUNCTYPE` - они определены только
    в ветке `os.name == "nt"`. Поэтому обращение к ним даёт `AttributeError`,
    а не ошибку вызова, и ловится это только удалением атрибутов.

Что проба ДОКАЗЫВАЕТ: модуль грузится, на загрузке падать нечему.
Что она НЕ доказывает: что окно откроется и что функция заработает. Живой
запуск на Маке она не заменяет - Qt, шрифты и трей тут не проверяются.

Каждый модуль пробуем в отдельном процессе: упавший импорт оставляет мусор в
sys.modules, и следующий за ним получил бы чужую ошибку.

    python tools/probe_mac_import.py            # все модули, сводка
    python tools/probe_mac_import.py app        # один, с полной трассировкой
"""

import os
import subprocess
import sys

# Чего на macOS нет. `mouse` и `keyboard` ставятся только под win32 (маркер в
# requirements.txt), остальное - часть Windows или pywin32.
BLOCKED = {
    "winreg", "_winreg", "winsound", "msvcrt",
    "keyboard", "mouse",
    "win32api", "win32con", "win32gui", "win32clipboard", "win32process",
    "win32event", "win32com", "win32file", "win32ui", "pywintypes",
    "pythoncom", "win32comext", "ctypes.wintypes",
}

# Порядок неслучаен: сначала то, что ниже всех и тянется всеми, потом окна,
# потом app - он тянет вообще всё. Так первая же красная строка показывает
# корень, а не последствие.
MODULES = [
    "platform_api", "app_paths", "config", "theme",
    "layered", "inserter", "media", "wakeup", "audiofile",
    "cleaner", "intonation", "stats", "notes", "transforms", "updater",
    "theme_qt", "overlay_qt", "settings_qt", "onboarding_qt",
    # Переезд визуала на React, 20.07.2026. Дописаны сюда не для полноты:
    # webwindow.py звал `os.add_dll_directory` на уровне модуля, а такой
    # функции на macOS нет ВООБЩЕ - импорт падал бы с AttributeError. Проба
    # этого не поймала, потому что про новые модули не знала, и нашлось это
    # вопросом владельца, а не проверкой.
    #
    # Отсюда правило: завёл модуль - впиши сюда. Список руками, а не обходом
    # папки, нарочно: обход втянул бы и tools, и тесты, а у них своя жизнь.
    "bridge", "webwindow", "language",
    "app",
]


class _NoWindows:
    """Поисковик модулей, который отвечает «нет такого» на всё из BLOCKED.

    Стоит первым в sys.meta_path: на Windows эти модули реально установлены, и
    без перехвата импорт прошёл бы, а на Маке упал - то есть проба врала бы
    ровно в ту сторону, ради которой её и завели.
    """

    def find_module(self, name, path=None):
        return self if name in BLOCKED else None

    def find_spec(self, name, path=None, target=None):
        if name in BLOCKED:
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return None

    def load_module(self, name):
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)


def _pretend_mac() -> None:
    """Сделать процесс похожим на macOS настолько, насколько важно импорту."""
    import ctypes

    # Только sys.platform: по нему ветвится platform_api, а значит и весь
    # проект. `os.name` НЕ трогаем - от него стандартная библиотека начинает
    # искать модуль `posix`, которого на Windows нет, и проба краснеет там,
    # где на настоящем Маке всё цело.
    # Грузим ДО подмены платформы - и это не поблажка, а граница пробы.
    #
    # Проба проверяет НАШИ гарды, а не чужие колёса. Оба модуля ниже на macOS
    # работают, но под нашей подменой сломались бы по причинам, которых на
    # настоящем Маке нет:
    #   - `ctypes.util` ветвится по `os.name`, а не по sys.platform (его мы
    #     намеренно не трогаем), взял бы Windows-ветку и потянул `wintypes`;
    #     на маке там posix-ветка;
    #   - `sounddevice` ищет нативную PortAudio под текущую платформу, и на
    #     этой машине лежит только windows-DLL; в macOS-колесе рядом лежит
    #     libportaudio.dylib.
    # Загруженные заранее, они просто берутся из кеша. Обратная сторона честная:
    # про них проба НИЧЕГО не доказывает - это проверит только запуск на Маке.
    import ctypes.util  # noqa: F401

    try:
        import sounddevice  # noqa: F401
    except Exception:  # noqa: BLE001 - нет звука в системе, для пробы неважно
        pass

    sys.platform = "darwin"
    sys.meta_path.insert(0, _NoWindows())
    # Обратное к BLOCKED: на настоящем Маке `_scproxy` ЕСТЬ (им urllib читает
    # системные прокси), а на Windows его нет. Стоит объявить себя маком - и
    # любой модуль, тянущий urllib, краснеет на ровном месте. Подсовываем
    # заглушку: проба должна ловить наши недоделки, а не свою же подмену.
    if "_scproxy" not in sys.modules:
        import types

        stub = types.ModuleType("_scproxy")
        stub._get_proxy_settings = lambda: {}
        stub._get_proxies = lambda: {}
        sys.modules["_scproxy"] = stub
    for attr in ("WinDLL", "windll", "OleDLL", "WINFUNCTYPE", "HRESULT",
                 "GetLastError", "WinError", "FormatError", "get_last_error",
                 "set_last_error"):
        if hasattr(ctypes, attr):
            delattr(ctypes, attr)
    # Уже загруженное до подмены выкидываем, иначе модуль возьмёт настоящий
    # win32 из кеша и проба ничего не заметит.
    for name in list(sys.modules):
        if name.split(".")[0] in BLOCKED:
            del sys.modules[name]


def _probe_one(name: str) -> int:
    """Импортировать один модуль под видом мака. 0 - прошло."""
    # Корень проекта в путь: запущены мы из tools/, и sys.path[0] указывает
    # туда же - без этого не найдётся ни один свой модуль, и проба покажет
    # двадцать красных строк вместо настоящей картины.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _pretend_mac()
    try:
        __import__(name)
    except BaseException:  # noqa: BLE001 - печатаем любую, в том числе SystemExit
        import traceback

        traceback.print_exc()
        return 1
    return 0


def _short_error(text: str) -> str:
    """Последняя содержательная строка трассировки - без простыни."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else "(пусто)"


def main() -> int:
    if len(sys.argv) > 1:
        return _probe_one(sys.argv[1])

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bad = []
    for name in MODULES:
        got = subprocess.run(
            [sys.executable, os.path.abspath(__file__), name],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        if got.returncode == 0:
            print(f"  ok      {name}")
        else:
            bad.append(name)
            print(f"  ПАДАЕТ  {name}: {_short_error(got.stderr)}")

    print()
    if bad:
        print(f"на macOS не импортируется: {len(bad)} из {len(MODULES)} - "
              + ", ".join(bad))
        print(f"подробно: python tools/probe_mac_import.py {bad[0]}")
        return 1
    print(f"все {len(MODULES)} модулей импортируются под macOS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
