"""Расчётный слой статистики диктовки - для будущей вкладки в настройках
(PLAN.md, пункт 5).

Чистая арифметика поверх history.jsonl: ни tkinter, ни PIL здесь не нужны -
вкладка статистики потянет только этот модуль, а не половину окна настроек
через случайный импорт. settings.py дёргает load()/summary()/by_day() по
этим именам - не переименовывать.

history.jsonl дописывается построчно живым процессом (см. app.py) - процесс
мог упасть на середине строки, кто-то мог открыть файл руками и накосячить.
Поэтому обе публичные функции тихо пропускают всё битое вместо того, чтобы
бросать: считалка статистики не должна ронять окно настроек из-за одной
кривой строки в истории.
"""

import json
from datetime import datetime, timedelta

from app_paths import HISTORY_PATH

# Грубая оценка порядка, не измерение на конкретном пользователе: типичная
# скорость разговорной речи и обычного (не слепого) набора на клавиатуре.
# Нужны только для saved_sec - прикинуть, сколько времени сэкономила диктовка
# по сравнению с ручным набором того же текста.
SPEECH_WPM = 150   # слов в минуту речью
TYPING_WPM = 40    # слов в минуту набором на клавиатуре

_TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def load(path: str = HISTORY_PATH) -> list[dict]:
    """Прочитать историю диктовок.

    Файла нет или строка - не json: молча пропускаем. Файл пишется построчно
    на живом приложении (app.py), оборванная последняя строка - обычное дело,
    а не повод падать.
    """
    rows: list[dict] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        return []
    return rows


def _parsed(row: dict):
    """Разобрать одну строку истории в (datetime, секунды, слова, ts) или
    вернуть None, если строка битая.

    Общий фильтр для summary() и by_day(): обеим нужен один и тот же критерий
    "это настоящая диктовка, а не мусор" - отсутствующий ключ, "sec": null,
    ts не того формата, text не строка. Раньше был риск завести два чуть
    разных фильтра и получить разные числа dictations в summary() и суммы
    слов в by_day() на одной и той же истории.
    """
    if not isinstance(row, dict):
        return None
    text = row.get("text")
    sec = row.get("sec")
    ts = row.get("ts")
    if not isinstance(text, str):
        return None
    if not isinstance(sec, (int, float)) or isinstance(sec, bool):
        return None
    if not isinstance(ts, str):
        return None
    try:
        dt = datetime.strptime(ts, _TS_FORMAT)
    except ValueError:
        return None
    return dt, float(sec), len(text.split()), ts


def summary(rows: list[dict]) -> dict:
    """Сводка по истории диктовок: сколько их было, сколько слов, и сколько
    времени сэкономлено по сравнению с набором того же текста на клавиатуре.
    """
    dictations = 0
    words = 0
    seconds = 0.0
    first_dt: datetime | None = None
    last_dt: datetime | None = None
    first_ts = None
    last_ts = None

    for row in rows:
        parsed = _parsed(row)
        if parsed is None:
            continue
        dt, sec, w, ts = parsed
        dictations += 1
        words += w
        seconds += sec
        if first_dt is None or dt < first_dt:
            first_dt, first_ts = dt, ts
        if last_dt is None or dt > last_dt:
            last_dt, last_ts = dt, ts

    # Печатать столько же слов на клавиатуре дольше, чем произнести - разница
    # и есть экономия. Буквальная формула из плана (речь минус печать) даёт
    # отрицательное число, потому что речь быстрее печати, - разворачиваем,
    # чтобы экономия была положительной при words > 0.
    saved_sec = words / TYPING_WPM * 60 - words / SPEECH_WPM * 60

    return {
        "dictations": dictations,
        "words": words,
        "avg_words": words / dictations if dictations else 0.0,
        "seconds": seconds,
        "saved_sec": saved_sec,
        "first_ts": first_ts,
        "last_ts": last_ts,
    }


def by_day(rows: list[dict], days: int = 30) -> list[tuple[str, int]]:
    """Слов по дням за последние `days` календарных дней, с нулями там, где
    диктовок не было - иначе график по дням соврёт о равномерности.

    "Сегодня" - это максимальная дата в rows, а не системное время: модуль
    должен считать одинаково что сегодня, что через год на тех же данных
    (детерминированность нужна, чтобы это можно было протестировать).
    """
    parsed = [p for p in (_parsed(r) for r in rows) if p is not None]
    if not parsed:
        return []

    today = max(dt for dt, _sec, _w, _ts in parsed).date()
    start = today - timedelta(days=days - 1)

    totals: dict = {}
    for dt, _sec, w, _ts in parsed:
        d = dt.date()
        if start <= d <= today:
            totals[d] = totals.get(d, 0) + w

    out: list[tuple[str, int]] = []
    d = start
    while d <= today:
        out.append((d.strftime("%Y-%m-%d"), totals.get(d, 0)))
        d += timedelta(days=1)
    return out
