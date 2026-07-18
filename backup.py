"""Выгрузить и загрузить личное: словарь, замены, правила тона, сочетания.

Зачем. Словарь и замены копятся годами и не воспроизводятся ничем. Живут они в
`config.json` рядом с приложением, а он в `.gitignore` - то есть копии не
существует нигде. Переустановка Windows, переезд папки, сбой диска - и самое
ценное, что есть в программе, исчезает вместе с ней. Раздел 0.8 плана уже ловил
этот класс риска на самом проекте («работа висит на одном диске») и сделал
вывод; на данных владельца вывод тот же, а лечения не было.

Второй довод: без выгрузки словарь не попадёт на вторую машину. Это
предусловие любого переезда, в том числе на macOS.

**Что выгружаем и что нет.** Личное - да: словарь, замены, тон, сочетания,
настройки чистки. Служебное - нет: пути, версия, состояние мастера, адрес
Ollama. Иначе файл с одной машины утащит на другую то, что верно только там, и
человек будет искать, почему на новом компьютере всё сломалось.

История - отдельно и по галочке: это самое личное, что тут есть, и класть её в
файл, который человек кому-нибудь перешлёт, нельзя молча.
"""

import json
import os
import time

# Что уезжает в файл. Список явный, а не «всё кроме»: добавится завтра ключ с
# путём или токеном - и он молча окажется в выгрузке, которой делятся.
KEYS = (
    "dictionary",        # имена и термины
    "snippets",          # «сказать» -> «вставить»
    "snippets_declined",  # от чего человек отказался: чтобы не предлагать снова
    "tone_rules",        # exe -> тон
    "hotkey_hold",
    "hotkey_toggle",
    "hotkey_command",
    "undo_hotkey",
    "remove_fillers",
    "voice_commands",
    "insert_mode",
    "append_space",
    "restore_clipboard",
    "overlay_position",
    "theme",
)

FORMAT = 1


def export_data(cfg: dict, history: list | None = None) -> dict:
    """Словарь для записи в файл. history - только если человек попросил."""
    out = {
        "format": FORMAT,
        "app": "FlowLocal",
        "saved": time.strftime("%Y-%m-%d %H:%M:%S"),
        "settings": {k: cfg[k] for k in KEYS if k in cfg},
    }
    if history is not None:
        out["history"] = history
    return out


def save(path: str, cfg: dict, history: list | None = None) -> int:
    """Записать файл. Возвращает число выгруженных настроек."""
    data = export_data(cfg, history)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)          # атомарно: оборванная запись не съест старый файл
    return len(data["settings"])


def load(path: str) -> dict:
    """Прочитать файл выгрузки. Бросает ValueError, если это не он.

    Проверяем формат, а не доверяем расширению: подсунутый json от другой
    программы иначе молча затёр бы настройки пустотой.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get("app") != "FlowLocal":
        raise ValueError("это не выгрузка FlowLocal")
    if int(data.get("format") or 0) > FORMAT:
        raise ValueError("файл от более новой версии - обновите программу")
    if not isinstance(data.get("settings"), dict):
        raise ValueError("в файле нет настроек")
    return data


def merge(cfg: dict, data: dict) -> tuple:
    """Влить выгрузку в конфиг. Возвращает (сколько добавлено, что заменено).

    СЛИВАЕМ, а не затираем, и это главное решение здесь. Человек загружает
    выгрузку не на чистую машину, а поверх того, чем уже пользуется: затереть
    его сегодняшний словарь вчерашней копией - потеря, которую нечем отменить.
    Списки и словари объединяются, одиночные значения берутся из файла только
    если их там нет у нас.
    """
    src = data.get("settings") or {}
    added = 0
    replaced: list = []

    for key in ("dictionary", "snippets_declined"):
        if isinstance(src.get(key), list):
            have = list(cfg.get(key) or [])
            for item in src[key]:
                if item not in have:
                    have.append(item)
                    added += 1
            cfg[key] = have

    for key in ("snippets", "tone_rules"):
        if isinstance(src.get(key), dict):
            have = dict(cfg.get(key) or {})
            for k, v in src[key].items():
                if k in have and have[k] != v:
                    replaced.append(k)
                if k not in have:
                    added += 1
                have[k] = v
            cfg[key] = have

    # Одиночные настройки: сочетания и тумблеры. Их не сливают - их либо берут,
    # либо нет. Берём, только если у нас пусто: своё сочетание человек назначил
    # руками, и молча заменить его чужим - худшее, что можно сделать.
    for key in ("hotkey_hold", "hotkey_toggle", "hotkey_command", "undo_hotkey"):
        if src.get(key) and not cfg.get(key):
            cfg[key] = src[key]
            added += 1

    return added, replaced
