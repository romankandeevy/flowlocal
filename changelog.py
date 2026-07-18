"""Разбор CHANGELOG.md - для окна «О программе» и для tools/release.py.

Зачем файлом, а не запросом к GitHub: «О программе» обязана работать без сети.
Вся её мысль - «интернет нужен один раз, скачать модель». Страница, которая на
самолёте показывает пустоту вместо истории версий, эту мысль опровергает.

Заодно это один источник правды: раньше заметки к релизу писались руками в
командной строке `tools/release.py --notes "..."` и нигде больше не жили.
Теперь наоборот - пишем в CHANGELOG, а релиз берёт оттуда.
"""

import os
import re
import sys

# Заголовок версии: «## 0.3.1.1 — 18.07.2026». Тире принимаем любое: в файле
# длинное, а руки набирают короткое, и падать из-за этого незачем.
_HEAD = re.compile(r"^##\s+(\d+(?:\.\d+)*)\s*[—–-]\s*(.+?)\s*$")


def path() -> str:
    """Рядом с приложением - и в сборке тоже: файл кладётся в _internal."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "CHANGELOG.md")


def parse(text: str) -> list[dict]:
    """[{version, date, title, items}] в порядке файла - от свежих к старым."""
    out: list[dict] = []
    cur: dict | None = None
    for line in text.splitlines():
        m = _HEAD.match(line)
        if m:
            cur = {"version": m.group(1), "date": m.group(2), "title": "", "items": []}
            out.append(cur)
            continue
        if cur is None:
            continue                      # преамбула файла - не про версии
        s = line.strip()
        if not s:
            continue
        if s.startswith("- "):
            cur["items"].append(s[2:].strip())
        elif not cur["items"] and not cur["title"]:
            # Первая непустая строка после заголовка - фраза о релизе целиком.
            cur["title"] = s
        elif cur["items"]:
            # Продолжение пункта на следующей строке: в файле мы переносим по
            # 79 колонок, а в окне текст переносится сам - склеиваем обратно.
            cur["items"][-1] += " " + s
    return out


def load() -> list[dict]:
    """Разобранный CHANGELOG или пустой список. Нет файла - не беда: окно
    просто не покажет раздел, а приложение работает дальше."""
    try:
        with open(path(), encoding="utf-8") as f:
            return parse(f.read())
    except OSError:
        return []


def notes_for(version: str) -> str:
    """Текст заметок к релизу: фраза плюс пункты списком. Для release.py."""
    for rel in load():
        if rel["version"] == version:
            body = "\n".join(f"- {i}" for i in rel["items"])
            return (rel["title"] + "\n\n" + body).strip()
    return ""
