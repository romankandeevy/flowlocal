"""Заметки: хранение, поиск, уборка.

Отдельное окно, куда можно диктовать длинно, не целясь в чужое поле. Владелец
надиктовал этим окном (у конкурента) весь разбор их программы - страницу с
лишним, - и выбрал в нём все четыре свойства сразу: диктовать не целясь, ИИ
приводит в порядок, хранить и искать, копировать одной кнопкой.

Почему файлы, а не одна общая база. Заметка - самое личное, что человек тут
держит, и она должна переживать что угодно: битую запись, снятый процесс,
кривой конфиг. Отдельные файлы теряются поштучно и правятся блокнотом; общий
файл теряется целиком.

Имя файла - метка времени создания, оно же идентификатор: сортировка по имени
даёт сортировку по возрасту, и переименовывать ничего не надо, когда человек
меняет заголовок.
"""

import json
import os
import re
import time

import stats
from app_paths import APP_DIR

DIR = os.path.join(APP_DIR, "notes")

# Заголовок - первая строка текста, но не длиннее этого: он идёт в список
# слева, и длинный превратит список в стену.
TITLE_MAX = 60


def _path(note_id: str) -> str:
    # Идентификатор приходит из наших же файлов, но проверить дешевле, чем
    # однажды получить «..\..\config.json» и записать заметку поверх настроек.
    safe = re.sub(r"[^0-9a-zA-Z_-]", "", note_id)
    return os.path.join(DIR, safe + ".json")


def new_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime())


def title_of(text: str) -> str:
    """Заголовок из текста. Пусто - «Без названия»: список не должен зиять."""
    first = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    first = " ".join(first.split())
    if not first:
        return "Без названия"
    return first[:TITLE_MAX - 1] + "…" if len(first) > TITLE_MAX else first


# Превью для карточки списка: первая строка целиком, до этой длины. Заголовок
# уже урезан до 60 (TITLE_MAX) и стоит крупно; под ним видно начало подлиннее.
PREVIEW_MAX = 120


def preview_of(text: str) -> str:
    """Первая непустая строка со схлопнутыми пробелами, до PREVIEW_MAX знаков."""
    first = ""
    for line in (text or "").splitlines():
        if line.strip():
            first = " ".join(line.split())
            break
    return first[:PREVIEW_MAX - 1] + "…" if len(first) > PREVIEW_MAX else first


def save(note_id: str, text: str) -> str:
    """Записать заметку. Возвращает идентификатор; пусто - не вышло."""
    try:
        os.makedirs(DIR, exist_ok=True)
        nid = note_id or new_id()
        path = _path(nid)
        created = nid
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    created = json.load(f).get("created") or nid
            except (OSError, ValueError):
                pass
        # Пишем через временный файл: обрыв на середине записи оставил бы
        # заметку наполовину, а это её потеря.
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"id": nid, "created": created,
                       "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "text": text or ""}, f, ensure_ascii=False)
        os.replace(tmp, path)
        return nid
    except OSError:
        return ""


def load(note_id: str) -> dict | None:
    try:
        with open(_path(note_id), encoding="utf-8") as f:
            d = json.load(f)
        d["title"] = title_of(d.get("text", ""))
        return d
    except (OSError, ValueError):
        return None


def delete(note_id: str) -> None:
    try:
        os.remove(_path(note_id))
    except OSError:
        pass


def listing(query: str = "") -> list[dict]:
    """Заметки, свежие первыми. query - поиск по тексту и заголовку.

    Читаем все файлы целиком, а не индекс: заметок у человека десятки, не
    миллионы, а отдельный индекс - это ещё одно место, где данные разъезжаются
    с действительностью.
    """
    out = []
    try:
        names = sorted(os.listdir(DIR), reverse=True)
    except OSError:
        return out
    q = (query or "").strip().lower()
    for name in names:
        if not name.endswith(".json"):
            continue
        d = load(name[:-5])
        if d is None:
            continue
        text = d.get("text", "")
        if q and q not in text.lower():
            continue
        words = len(text.split())
        out.append({
            "id": d["id"],
            "title": d["title"],
            "updated": d.get("updated", ""),
            # Момент словами - той же строкой, что карточка «Истории»: один вид
            # даты на всю программу (stats.human_moment).
            "when": stats.human_moment(d.get("updated", "")),
            # Первая строка подлиннее заголовка - чтобы в списке было видно, о
            # чём заметка, а не только её обрезанное начало.
            "preview": preview_of(text),
            "note": f"{words} {_plural(words)}" if words else "пусто",
        })
    return out


def _plural(n: int) -> str:
    from util import plural

    return plural(n, "слово", "слова", "слов")
