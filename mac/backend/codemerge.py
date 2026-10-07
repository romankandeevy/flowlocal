"""Склейка двух моделей для диктовки кода.

Код по-русски диктуют вперемешку: «let greeting равно привет». GigaAM слышит
русское («равно», «скобку», «привет»), но английские имена пишет кириллицей
(«Лед Гритинг»). Parakeet пишет английское как надо («Let greeting»), но
русское превращает в кашу («Kravno Privyte»). Поодиночке ни одна не годится.

Склейка - по словам и по времени: обе модели отдают время каждого токена.
Идём по словам GigaAM и каждое решаем отдельно:

- русское слово (служебное, команда кода вроде «равно», или с русским
  окончанием) - оставляем;
- похожее на английское, записанное кириллицей, - заменяем словами Parakeet,
  которые звучали в то же время, если они и правда звучат похоже
  («гритинг» ~ «greeting»);
- слова Parakeet, которым у GigaAM нет пары (она иногда проглатывает
  короткое «let»), вставляем, если они рядом с уже взятыми английскими.

Знаки и регистр дальше делает приложение (CodeSpeech.swift).
"""

from difflib import SequenceMatcher
import re

import langdetect

# Слова-команды кода по-русски: их не трогаем никогда, даже если похожи на
# что-то английское. Список - те же фразы, что в CodeSpeech.swift, по словам.
COMMAND_WORDS = {
    "равно", "равняется", "присвоить", "плюс", "минус", "умножить", "разделить", "делить",
    "больше", "меньше", "или", "чем", "стрелка", "стрелочка", "жирная", "логическое",
    "пустые", "скобки", "скобку", "скобка", "открыть", "закрыть", "открывающая",
    "закрывающая", "открывается", "закрывается", "круглую", "квадратную", "квадратная",
    "фигурную", "фигурная", "точка", "точку", "запятая", "запятую", "двоеточие",
    "вопросительный", "знак", "вопроса", "восклицательный", "подчёркивание",
    "подчеркивание", "нижнее", "обратный", "слэш", "слеш", "бэкслэш", "бэкслеш", "дефис",
    "тире", "новая", "строка", "новую", "строки", "собака", "собачка", "решётка",
    "решетка", "доллар", "амперсанд", "вертикальная", "черта", "тильда", "обратная",
    "кавычка", "кавычки", "кавычку", "кавычек", "одинарная", "одинарные", "одинарную",
    "апостроф", "пробел", "остаток", "деления", "комментарий", "коммент", "капс",
    "капсом", "константа", "слитно", "одним", "словом", "двойное",
    # команды регистра - их разбирает CodeSpeech, в любом написании
    "кэмел", "кемел", "камел", "кэмэл", "кэмл", "паскаль", "паскал", "снейк", "снэйк",
    "снек", "снэк", "кебаб", "кебап", "кейс", "кейз", "кэйс",
}

COMMENT_HEADS = {"комментарий", "коммент", "комментарии"}

QUOTE_WORDS = {"кавычка", "кавычки", "кавычку", "кавычек"}

# Короткие слова (до трёх букв) у GigaAM чаще русские: «мир», «код», «дом» -
# и Parakeet легко пишет их латиницей («Mir»). Меняем короткое, только если
# Parakeet услышал короткое слово из кода.
SHORT_EN = {
    "let", "var", "for", "int", "str", "get", "set", "map", "url", "api", "id", "key", "app",
    "log", "new", "try", "def", "len", "max", "min", "sum", "add", "end", "run", "use", "fun",
    "val", "nil", "out", "row", "tab", "css", "div", "img", "src", "env", "cmd", "git", "npm",
    "pip", "dev", "bug", "fix", "pop", "put", "obj", "arr", "num", "msg", "err", "res", "req",
    "db", "ui", "io", "is", "in", "if", "of", "or", "and", "not", "as", "do", "to", "on", "at",
    "by", "up", "all", "any", "has", "can", "the", "a", "an", "go", "fn", "mut", "pub", "ref",
    "box", "vec", "dict", "list", "test", "view", "item", "user", "name", "data", "self",
}

_CYR = re.compile(r"[а-яё]", re.I)
_LAT = re.compile(r"[a-z]", re.I)
_LETTERS = re.compile(r"[^a-zа-яё0-9]+", re.I)

# Похожесть для замены: обычное слово - от этой, «русское на вид» - только
# почти совпадение (иначе «привет» стал бы «private»).
SIMILAR = 0.6
SIMILAR_RU = 0.9
# Насколько слово Parakeet может выходить за границы слова GigaAM по времени.
SLACK = 0.08


class Word:
    __slots__ = ("text", "start", "end", "used")

    def __init__(self, text: str, start: float, end: float) -> None:
        self.text, self.start, self.end, self.used = text, start, end, False

    @property
    def mid(self) -> float:
        return (self.start + self.end) / 2

    def __repr__(self) -> str:  # для отладки
        return f"{self.text}@{self.start:.2f}-{self.end:.2f}"


def words(result, offset: float = 0.0) -> list[Word]:
    """Слова с временем из TimestampedResult: новое слово - токен с пробелом
    в начале. Конец слова - начало следующего."""
    tokens = result.tokens or []
    stamps = result.timestamps or []
    out: list[Word] = []
    for tok, ts in zip(tokens, stamps):
        if tok.startswith(" ") or not out:
            out.append(Word(tok.strip(), ts + offset, ts + offset))
        else:
            out[-1].text += tok
        out[-1].end = ts + offset
    for a, b in zip(out, out[1:]):
        a.end = max(a.end, b.start)
    if out:
        out[-1].end += 0.3
    return [w for w in out if _LETTERS.sub("", w.text)]


# --- похожесть звучания -----------------------------------------------------

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "o", "ж": "zh",
    "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "u",
    "я": "a",
}


def _squeeze(s: str) -> str:
    return re.sub(r"(.)\1+", r"\1", s)


def sound_ru(word: str) -> str:
    return _squeeze("".join(_TRANSLIT.get(c, "") for c in word.lower()))


def sound_en(word: str) -> str:
    s = re.sub(r"[^a-z]", "", word.lower())
    for a, b in (("ph", "f"), ("th", "t"), ("ck", "k"), ("ee", "i"), ("ea", "i"), ("oo", "u"),
                 ("ou", "u"), ("qu", "kv"), ("c", "k"), ("q", "k"), ("w", "v"), ("x", "ks"),
                 ("y", "i")):
        s = s.replace(a, b)
    if len(s) > 3 and s.endswith("e"):
        s = s[:-1]
    return _squeeze(s)


def similar(ru_word: str, en_words: list[str]) -> float:
    a, b = sound_ru(ru_word), sound_en("".join(en_words))
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


# --- решение по слову -------------------------------------------------------

def _plain(text: str) -> str:
    return _LETTERS.sub("", text).lower()


def is_command(text: str) -> bool:
    return _plain(text) in COMMAND_WORDS


def looks_russian(text: str) -> bool:
    w = _plain(text)
    return is_command(text) or langdetect._is_russian(w)


def is_comment(ru_text: str) -> bool:
    first = ru_text.strip().split(" ", 1)[0] if ru_text.strip() else ""
    return _plain(first) in COMMENT_HEADS or _plain(first) == "comment"


def merge(ru: list[Word], en: list[Word]) -> str:
    """Слова GigaAM, где английское заменено словами Parakeet."""
    if not ru:
        return " ".join(w.text for w in en)
    if not en:
        return " ".join(w.text for w in ru)
    if is_comment(ru[0].text):
        return " ".join(w.text for w in ru)

    out: list[tuple[float, str]] = []
    quoted = False
    for w in ru:
        plain = _plain(w.text)
        # Внутри «кавычки … кавычки» - строка: русское остаётся русским.
        if plain in QUOTE_WORDS:
            quoted = not quoted
            out.append((w.start, w.text))
            continue
        if quoted and _CYR.search(w.text):
            out.append((w.start, w.text))
            continue
        near = [e for e in en if not e.used and w.start - SLACK <= e.mid < w.end + SLACK]
        if not _CYR.search(w.text):
            # Латиницу GigaAM пишет наугад - у Parakeet английское точнее.
            if near and _LAT.search(w.text) and not plain.isdigit():
                for e in near:
                    e.used = True
                out.append((w.start, " ".join(e.text for e in near)))
            else:
                out.append((w.start, w.text))
            continue
        if is_command(w.text) or not near:
            out.append((w.start, w.text))
            continue
        # Рядом может оказаться и лишнее («Gritch and» на месте «гритинг»):
        # берём подряд идущий отрезок, который звучит похожее всего.
        rank, score, best = -1.0, 0.0, near
        for a in range(len(near)):
            for b in range(a + 1, len(near) + 1):
                sc = similar(plain, [e.text for e in near[a:b]])
                # Выбор - со штрафом за каждое лишнее слово: при равной
                # похожести короче честнее («Gritch», а не «Gritch and»).
                # Порог - по самой похожести, без штрафа.
                if sc - 0.05 * (b - a - 1) > rank:
                    rank, score, best = sc - 0.05 * (b - a - 1), sc, near[a:b]
        need = SIMILAR_RU if langdetect._is_russian(plain) else SIMILAR
        if len(plain) <= 3 and _plain("".join(e.text for e in best)) not in SHORT_EN:
            need = 2.0
        if score >= need:
            for e in best:
                e.used = True
            out.append((w.start, " ".join(e.text for e in best)))
        else:
            out.append((w.start, w.text))

    # Слова Parakeet без пары у GigaAM: вставляем, если сосед по Parakeet уже
    # взят и на этом месте у GigaAM ничего не звучало.
    for i, e in enumerate(en):
        if e.used or not _LAT.search(e.text):
            continue
        neighbour = (i + 1 < len(en) and en[i + 1].used) or (i > 0 and en[i - 1].used)
        covered = any(w.start - SLACK <= e.mid < w.end + SLACK for w in ru)
        if neighbour and not covered:
            e.used = True
            out.append((e.start, e.text))

    out.sort(key=lambda x: x[0])
    return " ".join(t for _, t in out)


def lang_of(text: str) -> str:
    lat = len(re.findall(r"[A-Za-z]+", text))
    cyr = len(re.findall(r"[А-Яа-яЁё]+", text))
    return "en" if lat > cyr else "ru"
