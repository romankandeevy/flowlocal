"""Пути приложения и автозапуск через реестр.

Отдельно от app.py, потому что этим пользуется и окно настроек: тянуть
ради двух функций весь app.py (а с ним модель и хоткеи) - лишнее.
"""

import os
import sys
import winreg

def _app_dir() -> str:
    """Папка, рядом с которой живут данные: конфиг, лог, история, модель.

    При обычном запуске это папка с исходниками. В собранном .exe __file__
    указывает внутрь временной распаковки PyInstaller - она стирается при
    выходе, и настройки с историей пропадали бы после каждого закрытия.
    Поэтому там берём папку самого .exe.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = _app_dir()
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
# Личный конфиг в репозиторий не уезжает (словарь и сниппеты - личное), поэтому
# у свежего клона его нет: приложение делает свой из примера. См. config.bootstrap.
#
# Пример ищем не рядом с конфигом, а рядом с кодом: в собранном .exe он лежит
# ВНУТРИ, во временной распаковке (sys._MEIPASS), а рядом с .exe его нет -
# оттуда и копируем наружу при первом запуске.
EXAMPLE_PATH = os.path.join(
    getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__)),
    "config.example.json")
LOG_PATH = os.path.join(APP_DIR, "flow.log")
HISTORY_PATH = os.path.join(APP_DIR, "history.jsonl")
MODELS_DIR = os.path.join(APP_DIR, "models")

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "FlowLocal"


def autostart_command() -> str:
    """Команда автозапуска для реестра.

    Собранный .exe запускает сам себя - никакого Python рядом нет.
    Из исходников зовём pythonw, а не python: иначе при каждом входе в систему
    всплывает и висит чёрное окно консоли.

    `--silent` отличает вход в систему от клика по ярлыку, и это не мелочь:
    команда была одна и та же, поэтому «показывать окно при запуске» включить
    было нельзя - оно всплывало бы при каждой загрузке Windows. Теперь ярлык
    открывает настройки, а автозапуск молча садится в трей.
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --silent'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    return f'"{pythonw}" "{os.path.join(APP_DIR, "app.py")}" --silent'


def autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            value, _ = winreg.QueryValueEx(k, RUN_NAME)
        return bool(value)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_autostart(enabled: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass


def autostart_command_current() -> str:
    """Что сейчас записано в реестре. Пусто - записи нет.

    Нужна тому, кто решает, лечить запись или не трогать: из исходников
    переписывать команду, указывающую на установленную сборку, нельзя.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            value, _ = winreg.QueryValueEx(k, RUN_NAME)
        return str(value or "")
    except OSError:
        return ""


def autostart_command_stale() -> bool:
    """Записанная в реестре команда разошлась с той, что нужна сегодня.

    Такое бывает не только от нашей правки: папку приложения перенесли, Python
    обновили, появился новый флаг. Пока команда не совпадает, автозапуск либо
    не сработает, либо сработает не так - например, откроет окно настроек при
    каждом входе в систему, потому что в старой записи нет `--silent`.

    Чинится на старте (app.py). Не при выключенном автозапуске: чего нет, то и
    чинить нечего.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            value, _ = winreg.QueryValueEx(k, RUN_NAME)
    except OSError:
        return False
    return bool(value) and str(value) != autostart_command()
