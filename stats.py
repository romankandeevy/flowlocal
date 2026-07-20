"""Расчётный слой статистики диктовки: страница «Статистика» главного окна.

Чистая арифметика поверх history.jsonl: ни tkinter, ни PIL здесь не нужны -
страница статистики потянет только этот модуль, а не половину окна через
случайный импорт. `settings_qt.Backend._stats` дёргает load(), summary(),
week(), best_day() и ago() по этим именам - не переименовывать.

`by_day()` сейчас не зовёт никто: страница показывает неделю (week), а не
тридцать дней. Функция оставлена как есть - тридцатидневный вид может
вернуться, и переписывать её заново было бы дороже, чем не трогать.

history.jsonl дописывается построчно живым процессом (см. app.py) - процесс
мог упасть на середине строки, кто-то мог открыть файл руками и накосячить.
Поэтому все публичные функции тихо пропускают всё битое вместо того, чтобы
бросать: считалка статистики не должна ронять окно из-за одной кривой строки
в истории.
"""

import json
from datetime import date, datetime, timedelta

from app_paths import HISTORY_PATH
from util import plural

# Скорость обычного (не слепого) набора на клавиатуре - грубая оценка порядка,
# не замер конкретного пользователя. Нужна для saved_sec: прикинуть, сколько
# заняло бы напечатать руками то, что человек продиктовал. Скорость речи не
# оценкой, а замером - фактические секунды записи (см. summary).
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


def summary(rows: list[dict], today: date | None = None) -> dict:
    """Сводка по истории диктовок: сколько их было, сколько слов, и сколько
    времени сэкономлено по сравнению с набором того же текста на клавиатуре.

    `today` нужен только серии дней - см. _streak. По умолчанию сегодняшний
    день: приложению нужен именно он, а тест подставляет свой.
    """
    dictations = 0
    words = 0
    seconds = 0.0
    first_ts = None
    last_ts = None
    days: set[date] = set()

    for row in rows:
        parsed = _parsed(row)
        if parsed is None:
            continue
        dt, sec, w, ts = parsed
        dictations += 1
        words += w
        seconds += sec
        days.add(dt.date())        # копим здесь же - серии второй проход не нужен
        if first_ts is None or ts < first_ts:
            first_ts = ts
        if last_ts is None or ts > last_ts:
            last_ts = ts

    # Экономия: сколько занял бы набор этих слов руками минус сколько человек
    # реально проговорил в микрофон. Вторая половина - замер (sec из истории),
    # а не средняя скорость речи из учебника: «замер сильнее мнения». max(0)
    # на случай, если говорили медленнее, чем печатали бы: экономии нет, но и
    # отрицательной она быть не может - иначе на Главной появится «-45 с».
    saved_sec = max(0.0, words / TYPING_WPM * 60 - seconds)

    # Личная скорость речи - тоже замер: слова из истории на минуты записи.
    # На паре коротких фраз число случайное, поэтому потребителям (Главная)
    # отдаём его вместе с сырьём - решать «показывать ли» им.
    speech_wpm = words / (seconds / 60) if seconds > 0 else 0.0

    return {
        "dictations": dictations,
        "words": words,
        "seconds": seconds,
        "saved_sec": saved_sec,
        "speech_wpm": speech_wpm,
        "streak_days": _streak(days, today or date.today()),
        # Самая длинная серия за всю историю - потолок для дуги «дней подряд»
        # на «Статистике»: текущая серия рисуется долей от неё, и полная дуга
        # значит «вы на своём рекорде». Число честное, из тех же дней, что и
        # текущая серия, - не выдуманная цель вроде «до семи».
        "best_streak": _best_streak(days),
        "first_ts": first_ts,
        "last_ts": last_ts,
    }


def _best_streak(days: set[date]) -> int:
    """Самая длинная цепочка дней подряд за всю историю.

    Не зависит от «сегодня» вовсе, в отличие от _streak: рекорд серии - это
    свойство самих данных, и через год на тех же днях он обязан быть тем же.
    Считаем в лоб: у дня нет предыдущего в множестве - значит он начало
    цепочки, отсюда и тянем вперёд. Каждый день так осматривается один раз.
    """
    best = 0
    for d in days:
        if d - timedelta(days=1) in days:
            continue                       # не начало цепочки - его посчитают с начала
        n = 1
        while d + timedelta(days=n) in days:
            n += 1
        best = max(best, n)
    return best


def _streak(days: set[date], today: date) -> int:
    """Сколько дней подряд человек диктовал, считая назад от сегодня.

    Дни приходят готовым множеством (собраны в summary), а не парсятся заново:
    strptime по всей истории - самая дорогая часть, гонять её трижды незачем.

    Серия, оборвавшаяся неделю назад, - уже не серия: вчера ещё считается
    (сегодня человек мог просто не успеть), позавчера - нет. `today` приходит
    аргументом, а не из системных часов: на тех же данных ответ обязан быть
    одинаков что сегодня, что через год - иначе это не проверить тестом.
    """
    if not days:
        return 0
    d = today if today in days else today - timedelta(days=1)
    n = 0
    while d in days:
        n += 1
        d -= timedelta(days=1)
    return n


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


# Родительный падеж: подпись собирается как «12 июля», а не «12 июль».
_MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня",
           "июля", "августа", "сентября", "октября", "ноября", "декабря")

# date.weekday(): 0 - понедельник. Порядок кортежа обязан совпадать с ним.
_WEEKDAYS = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")


def human_date(d: date) -> str:
    """«16 июля». Год не пишем: подпись живёт в графике за последнюю неделю и
    в строке рекорда, где год - лишний шум. Год есть в самой истории."""
    return f"{d.day} {_MONTHS[d.month - 1]}"


def human_moment(ts: str) -> str:
    """«16 июля, 12:20» - дата словами и время из метки «%Y-%m-%d %H:%M:%S».

    Один вид момента на всю программу: и карточка «Истории» (settings_qt._rows),
    и список заметок (notes.listing) показывают дату этой строкой, и разъехаться
    им нельзя. Не разобрали ts - пустая строка: та же терпимость к битым меткам,
    что у ago(), и по той же причине - подпись без даты лучше «Invalid Date»."""
    try:
        dt = datetime.strptime(str(ts), _TS_FORMAT)
    except (TypeError, ValueError):
        return ""
    return f"{human_date(dt.date())}, {dt.strftime('%H:%M')}"


def week(rows: list[dict], today: date | None = None) -> list[dict]:
    """Семь последних календарных дней, заканчивая сегодняшним: слова по дням.

    Отдельная функция, а не `by_day(rows, 7)`, из-за одного слова - «сегодня».
    by_day считает сегодняшним максимальный день в истории: так его ответ не
    зависит от системных часов, и его можно проверить тестом. Недельному
    графику нужно ровно обратное: сегодняшний столбик подсвечен акцентом, и
    подсветить он обязан настоящий сегодняшний день. Иначе после трёх дней
    молчания акцент встанет на прошлый четверг и назовёт его сегодня.

    Детерминированность при этом не теряется: `today` приходит аргументом, как
    в summary(), - тест подставляет свой день и получает тот же ответ в любой
    момент времени.
    """
    today = today or date.today()
    start = today - timedelta(days=6)

    totals: dict = {}
    for row in rows:
        parsed = _parsed(row)
        if parsed is None:
            continue
        dt, _sec, w, _ts = parsed
        d = dt.date()
        if start <= d <= today:
            totals[d] = totals.get(d, 0) + w

    out: list[dict] = []
    d = start
    while d <= today:
        out.append({
            "date": d.strftime("%Y-%m-%d"),
            "label": _WEEKDAYS[d.weekday()],
            "human": human_date(d),
            "words": totals.get(d, 0),
            "today": d == today,
        })
        d += timedelta(days=1)
    return out


def best_day(rows: list[dict]) -> dict | None:
    """Самый плодовитый день за всю историю: {date, human, words}. Пусто - None.

    По ВСЕЙ истории, а не по последней неделе, и это принципиально: строка
    рекорда - то самое число, которым хвастаются, и урезать её до семи дней
    значило бы стирать рекорд на восьмой день.

    День без единого слова рекордом не считается: «лучший день - 0 слов»
    честнее не показывать вовсе (за это отвечает вызывающий: пустая история
    даёт None, а история из одних пустых строк до сюда не доходит - их
    отсеивает _parsed).
    """
    totals: dict = {}
    for row in rows:
        parsed = _parsed(row)
        if parsed is None:
            continue
        dt, _sec, w, _ts = parsed
        totals[dt.date()] = totals.get(dt.date(), 0) + w

    totals = {d: w for d, w in totals.items() if w > 0}
    if not totals:
        return None
    # Ничья - берём поздний день: свежий рекорд интереснее прошлогоднего, а
    # без второго ключа порядок зависел бы от порядка строк в файле.
    d, w = max(totals.items(), key=lambda kv: (kv[1], kv[0]))
    return {"date": d.strftime("%Y-%m-%d"), "human": human_date(d), "words": w}


def ago(ts: str, now: datetime | None = None) -> str:
    """Когда это было, по-человечески: «только что», «2 минуты назад», «вчера».

    Нужна карточке последней диктовки на «Главной». Точное «2026-07-19
    14:03:11» отвечает там не на тот вопрос: человек смотрит на карточку,
    чтобы понять «это то, что я только что сказал?», а не во сколько это
    было. Секунды и дата остаются в истории, где их и ищут.

    Дальше недели - дата словами («12 июля»), а не «34 дня назад»: считать
    недели в уме человек не станет. Год дописываем только чужой: «12 июля»
    про прошлую неделю читается легко, а «12 июля 2025» - это уже архив.

    Не разобрали ts - отдаём пустую строку. Подпись без времени лучше, чем
    карточка с «Invalid Date»: та же терпимость к битым строкам, что у
    load() выше, и по той же причине.

    `now` аргументом, а не из системных часов: на тех же данных ответ обязан
    быть одинаков что сегодня, что через год - иначе это не проверить тестом.
    Тот же приём, что у summary() и by_day().
    """
    try:
        then = datetime.strptime(str(ts), _TS_FORMAT)
    except (TypeError, ValueError):
        return ""

    now = now or datetime.now()
    sec = (now - then).total_seconds()
    # Запись из будущего - это переведённые назад часы или чужая история, а не
    # повод показывать «-3 минуты назад». Такое честнее назвать свежим.
    if sec < 90:
        return "только что"

    minutes = int(sec // 60)
    if minutes < 60:
        return f"{minutes} {plural(minutes, 'минуту', 'минуты', 'минут')} назад"

    # Дальше считаем календарными днями, а не делением секунд на 86400:
    # «вчера в 23:00» и «сегодня в 01:00» разделяют два часа, но человек
    # называет их разными днями, и подпись обязана называть так же.
    days = (now.date() - then.date()).days
    if days == 0:
        hours = int(sec // 3600)
        return f"{hours} {plural(hours, 'час', 'часа', 'часов')} назад"
    if days == 1:
        return "вчера"
    if days < 7:
        return f"{days} {plural(days, 'день', 'дня', 'дней')} назад"

    head = human_date(then.date())
    return head if then.year == now.year else f"{head} {then.year}"
