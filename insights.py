"""Как вы говорите: разбор собственной речи по накопленной истории.

Всё считается здесь, на этой машине, по файлу, который и так лежит рядом. Ни
одного нового байта никуда не уходит - это то же правило, что и у статистики.

Что можно посчитать честно и что нельзя:

    можно    - любимое слово, присказка, часы пик, где диктуете,
               что программа за вас исправила, какое слово путает чаще
    нельзя   - «ваша сверхспособность» и прочие красивые ярлыки: у соседей их
               сочиняет облачная модель, а выдумывать про человека мы не станем.
               Роль подбираем правилами из того, что посчитали, и если данных
               мало - молчим.

Поля `app` и `raw` в истории появились 18.07.2026 (версия 0.10.1) ровно ради
этого файла. У записей старше их нет, и разделы, которые на них опираются,
просто не показываются, пока не накопится.
"""

import collections
import re

# Ниже этого числа диктовок считать что-либо про человека - гадание.
MIN_ROWS = 5
# А для разбора самих слов нужен объём побольше: на сотне слов «любимым»
# окажется случайное.
MIN_WORDS = 300

_WORD = re.compile(r"[а-яёa-z0-9-]+", re.IGNORECASE)

# Служебные слова в «любимое слово» не годятся: предлоги и местоимения
# возглавят любой список и не скажут о человеке ничего.
_STOP = frozenset("""
и в во не что он на я с со как а то все она так его но да ты к у же вы за бы
по её мне было вот от меня ещё нет о из ему теперь когда даже ну вдруг ли если
уже или ни быть был него до вас нибудь опять уж вам ведь там потом себя ничего
ей может они тут где есть надо ней для мы тебя их чем была сам чтоб без будто
чего раз тоже себе под будет ж тогда кто этот того потому этого какой совсем
ним здесь этом один почти мой тем чтобы нее сейчас были куда зачем всех никогда
можно при наконец два об другой хоть после над больше тот через эти нас про
всего них какая много разве три эту моя впрочем хорошо свою этой перед иногда
лучше чуть том нельзя такой им более всегда конечно всю между это как-то
просто типа вроде значит короче вообще именно тоже давай надо нужно можно
сделать сказать посмотреть понял понятно ладно окей хорошо давайте просто
""".split())

# Слова-паразиты сюда же, и вот почему их мало было. В cleaner.py «просто» и
# «вообще» намеренно НЕ вырезаются из текста: «просто нажми» - обычная фраза, и
# съесть там слово дороже, чем оставить. Но для вопроса «какое у вас любимое
# слово» они бесполезны: на живой истории владельца победило «просто» с 41
# повтором, и он справедливо сказал, что это не его любимое слово.
#
# То есть у двух задач разная цена ошибки: там - потеря текста, здесь -
# бессмысленная строка на экране. Поэтому списки и разные.

# Куда диктуют - по имени программы. Список короткий и очевидный: угадывать
# назначение незнакомой программы мы не беремся, она уйдёт в «остальное».
_KINDS = {
    "почта": ("outlook.exe", "thunderbird.exe", "mailbird.exe", "em client.exe"),
    "переписка": ("telegram.exe", "whatsapp.exe", "discord.exe", "slack.exe",
                  "teams.exe", "viber.exe", "skype.exe"),
    "документы": ("winword.exe", "notepad.exe", "notepad++.exe", "obsidian.exe",
                  "onenote.exe", "wps.exe", "libreoffice.exe"),
    "браузер": ("chrome.exe", "firefox.exe", "msedge.exe", "opera.exe",
                "browser.exe", "arc.exe"),
    "код": ("code.exe", "cursor.exe", "pycharm64.exe", "windsurf.exe",
            "devenv.exe", "sublime_text.exe", "idea64.exe", "rider64.exe",
            "webstorm64.exe", "goland64.exe", "clion64.exe", "zed.exe"),
    "ИИ": ("claude.exe", "chatgpt.exe", "perplexity.exe", "copilot.exe",
           "gemini.exe", "raycast.exe"),
    "заметки": ("notion.exe", "obsidian.exe", "logseq.exe", "craft.exe",
                "bear.exe", "notion calendar.exe", "todoist.exe"),
}


def _words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text or "")]


def _kind_of(app: str) -> str:
    """Куда диктовали: род занятия, а если он неизвестен - имя программы.

    Раньше всё незнакомое сваливалось в «остальное», и владелец сказал прямо:
    программа не определяет Claude, Notion и прочее, раздел бесполезен. Так и
    было - у него половина диктовок уходила в безымянную кучу.

    Список родов занятий мы не расширяем до бесконечности: угадывать назначение
    чужой программы мы по-прежнему не беремся. Но её ИМЯ мы знаем, и сказать
    «Obsidian - 14%» честнее и полезнее, чем «остальное - 40%». Человек узнаёт
    свою программу с первого взгляда, а мы не притворяемся, будто понимаем,
    чем он там занят.
    """
    a = (app or "").lower()
    if not a:
        return ""
    for kind, names in _KINDS.items():
        if a in names:
            return kind
    # «obsidian.exe» -> «Obsidian». Имя из системы, поэтому только снимаем
    # расширение и поднимаем первую букву - переписывать его мы не вправе.
    name = a[:-4] if a.endswith(".exe") else a
    name = name.strip()
    return (name[:1].upper() + name[1:]) if name else "остальное"


def top_word(rows: list[dict]) -> tuple[str, int]:
    """Любимое слово и сколько раз сказано. Пусто - данных мало."""
    c = collections.Counter()
    for r in rows:
        for w in _words(r.get("text")):
            # Цифры отсеиваем: «2026» из даты формально слово длиннее трёх,
            # но «ваше любимое слово - 2026» это не ответ.
            if len(w) > 3 and w not in _STOP and not w.replace("-", "").isdigit():
                c[w] += 1
    if not c:
        return "", 0
    word, n = c.most_common(1)[0]
    # Один-два раза - это не «любимое», а просто слово.
    return (word, n) if n >= 3 else ("", 0)


def catch_phrase(rows: list[dict]) -> tuple[str, int]:
    """Присказка - сочетание из трёх слов, которое вы повторяете.

    Три, а не два: пар вроде «и вот» в любой речи много, и они не о человеке.
    Три слова подряд, повторённые трижды, - это уже манера.
    """
    c = collections.Counter()
    for r in rows:
        ws = _words(r.get("text"))
        for i in range(len(ws) - 2):
            tri = ws[i:i + 3]
            # Тройка сплошь из служебных слов - не присказка, а склейка.
            if sum(1 for w in tri if w in _STOP) == 3:
                continue
            c[" ".join(tri)] += 1
    if not c:
        return "", 0
    phrase, n = c.most_common(1)[0]
    return (phrase, n) if n >= 3 else ("", 0)


def corrections(rows: list[dict]) -> tuple[int, str]:
    """Сколько слов программа исправила и какое путает чаще прочих.

    Считаем по разнице между тем, что услышала модель (`raw`), и тем, что
    вставилось (`text`). Записи без `raw` пропускаем: они старше этой затеи.
    """
    total = 0
    c = collections.Counter()
    for r in rows:
        raw = r.get("raw")
        if not raw:
            continue
        was, now = _words(raw), _words(r.get("text"))
        if not was:
            continue
        # Простой разбор: слова, которые были и пропали. Выравнивать
        # последовательности незачем - нам нужна не точность до слова, а
        # «какое слово чаще всего оказывается не тем».
        gone = collections.Counter(was) - collections.Counter(now)
        for w, k in gone.items():
            if len(w) > 3:
                c[w] += k
                total += k
    worst = c.most_common(1)[0][0] if c else ""
    return total, worst


def correction_pairs(rows: list[dict]) -> list[tuple[str, str, int]]:
    """Пары «что услышала модель -> что вставилось», от частых к редким.

    Нужны, чтобы предложить одним нажатием добавить слово в словарь: человек
    видит «чаще всего путается «сокалов»» и жмёт кнопку, вместо того чтобы
    открывать «Слова» и вспоминать, как оно пишется.

    Пару считаем надёжной только когда в диктовке ровно одно слово пропало и
    ровно одно появилось: иначе непонятно, что во что превратилось, а гадать
    здесь нельзя - неверная пара испортит все будущие диктовки.
    """
    c = collections.Counter()
    for r in rows:
        raw = r.get("raw")
        if not raw:
            continue
        was, now = _words(raw), _words(r.get("text"))
        gone = list((collections.Counter(was) - collections.Counter(now)).elements())
        came = list((collections.Counter(now) - collections.Counter(was)).elements())
        if len(gone) == 1 and len(came) == 1 and len(gone[0]) > 3:
            c[(gone[0], came[0])] += 1
    return [(a, b, n) for (a, b), n in c.most_common(5)]


def peak_hour(rows: list[dict]) -> tuple[int, int]:
    """Час, в который диктуют чаще всего, и сколько диктовок в нём."""
    c = collections.Counter()
    for r in rows:
        ts = str(r.get("ts") or "")
        if len(ts) >= 13 and ts[11:13].isdigit():
            c[int(ts[11:13])] += 1
    if not c:
        return -1, 0
    return c.most_common(1)[0]


def where(rows: list[dict]) -> list[dict]:
    """Куда диктуете: по видам программ, от частого к редкому."""
    c = collections.Counter()
    words = collections.Counter()
    for r in rows:
        kind = _kind_of(r.get("app"))
        if not kind:
            continue
        c[kind] += 1
        words[kind] += len(_words(r.get("text")))
    total = sum(c.values())
    if not total:
        return []
    return [{"kind": k, "share": round(100 * n / total),
             "words": words[k], "count": n}
            for k, n in c.most_common()]


def persona(rows: list[dict], places: list[dict]) -> str:
    """Одна фраза о том, как вы пользуетесь программой.

    Правилами, а не моделью. У соседей это сочиняет облачная LLM, и выходит
    красиво; но выдумывать про человека мы не станем, а маленькая модель на
    таком задании выдаёт банальность. Правило скажет меньше, зато правду.
    """
    if len(rows) < MIN_ROWS or not places:
        return ""
    top = places[0]["kind"]
    hour, _n = peak_hour(rows)
    когда = ("по утрам" if 5 <= hour < 11 else
             "днём" if 11 <= hour < 17 else
             "вечерами" if 17 <= hour < 23 else
             "ночами" if hour >= 0 else "")
    куда = {"почта": "письма", "переписка": "сообщения",
            "документы": "документы", "браузер": "в браузере",
            "код": "код и задачи", "ИИ": "запросы к ИИ",
            "заметки": "заметки"}.get(top, "")
    # «остальное» в роль не берём: фраза «больше всего - разное» не говорит
    # ни о чём. Лучше сказать только про время и манеру, чем добавить пустое.
    if not когда:
        return ""
    длинно = sum(len(_words(r.get("text"))) for r in rows) / max(1, len(rows))
    манера = "длинными кусками" if длинно >= 25 else "короткими фразами"
    if not куда:
        return f"Диктуете {когда}, {манера}."
    return f"Диктуете {когда}, {манера}. Чаще всего - {куда}."


def summary(rows: list[dict]) -> dict:
    """Всё сразу. Пустые поля значат «пока не набралось», а не ноль."""
    words_total = sum(len(_words(r.get("text"))) for r in rows)
    enough = len(rows) >= MIN_ROWS and words_total >= MIN_WORDS
    word, word_n = top_word(rows) if enough else ("", 0)
    phrase, phrase_n = catch_phrase(rows) if enough else ("", 0)
    fixed, worst = corrections(rows)
    hour, hour_n = peak_hour(rows)
    places = where(rows)
    return {
        "enough": enough,
        "rows": len(rows),
        "words": words_total,
        "need_rows": max(0, MIN_ROWS - len(rows)),
        "need_words": max(0, MIN_WORDS - words_total),
        "top_word": word, "top_word_n": word_n,
        "phrase": phrase, "phrase_n": phrase_n,
        "fixed": fixed, "worst_word": worst,
        "pairs": [{"heard": a, "fixed": b, "n": n}
                  for a, b, n in correction_pairs(rows)],
        "hour": hour, "hour_n": hour_n,
        "where": places,
        "persona": persona(rows, places),
    }
