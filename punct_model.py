"""Расстановка знаков моделью - уровень 2.

Уровень 1 (punct_rules) - правила: доли миллисекунды, ноль зависимостей, но
знает только то, чему его научили списком. Уровень 2 - обученная модель: ставит
запятые по смыслу, включая места, которые правилами не берутся (обороты,
однородные члены).

Что здесь есть и чего нет:

- **Токенизатор свой.** Из transformers его не берём: он тянет полбиблиотеки, а
  нужен из него один WordPiece на полторы сотни строк. Словарь лежит рядом с
  моделью, скачивается вместе с ней.
- **Модель ничего не сочиняет.** Это классификация токенов: на каждый токен -
  метка «после него запятая / точка / ничего» и «с заглавной или нет». Слово
  придумать или потерять она не может по устройству. Это важнее скорости: у
  диктовки главное правило - не терять текст.
- **Ollama здесь ни при чём.** Она осталась для самоисправлений и тона.

Модель необязательна. Нет её - работают правила, и это не деградация, а
запасной вариант, которым большинство и обойдётся.
"""

import json
import os
import re
import unicodedata

_MAX_LEN = 512

# Куда кладём модель и откуда берём.
#
# Раздаём из своих релизов на GitHub, а не с HuggingFace: там лежит исходная
# модель для PyTorch, а нам нужен ONNX, которого у неё нет. Конвертируем сами
# (tools/convert_punct.py) и выкладываем результат - тем же путём, которым и
# так раздаём саму программу.
FOLDER_NAME = "punct-ru"
ASSET = "punct-ru.zip"
TAG = "punct-v1"


def folder() -> str:
    from app_paths import MODELS_DIR

    return os.path.join(MODELS_DIR, FOLDER_NAME)


def installed() -> bool:
    d = folder()
    return all(os.path.exists(os.path.join(d, f))
               for f in ("model.int8.onnx", "vocab.txt", "labels.json"))


def size_mb() -> float:
    d = folder()
    if not os.path.isdir(d):
        return 0.0
    return sum(os.path.getsize(os.path.join(d, f))
               for f in os.listdir(d)) / 1e6


def download(on_progress=None, repo: str = "") -> str:
    """Скачать и распаковать модель. Пустая строка - получилось, иначе причина.

    on_progress(доля) - от 0 до 1, чтобы человек видел, что идёт работа:
    тридцать мегабайт на медленном интернете - это минуты.
    """
    import shutil
    import tempfile
    import urllib.request
    import zipfile

    if not repo:
        from version import GITHUB_REPO

        repo = GITHUB_REPO
    url = f"https://github.com/{repo}/releases/download/{TAG}/{ASSET}"
    d = folder()
    tmp = ""
    try:
        os.makedirs(d, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as r:
            total = int(r.headers.get("Content-Length") or 0)
            fd, tmp = tempfile.mkstemp(suffix=".zip")
            got = 0
            with os.fdopen(fd, "wb") as f:
                while True:
                    chunk = r.read(262144)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    if on_progress and total:
                        on_progress(got / total)
        with zipfile.ZipFile(tmp) as z:
            # Распаковываем поимённо: доверять путям из чужого архива нельзя,
            # «../» в имени вылезло бы за папку моделей.
            for name in z.namelist():
                base = os.path.basename(name)
                if not base:
                    continue
                with z.open(name) as src, open(os.path.join(d, base), "wb") as dst:
                    shutil.copyfileobj(src, dst)
        return "" if installed() else "распаковалось не полностью"
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {e}"[:200]
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def remove() -> None:
    import shutil

    shutil.rmtree(folder(), ignore_errors=True)


# --------------------------------------------------------------------------
# WordPiece - ровно тот, что в BertTokenizer, без transformers.

class WordPiece:
    """Токенизатор BERT: нормализация, разбиение на слова, разбор на куски.

    Проверяется сверкой с transformers в tools/convert_punct.py: если наш
    разбор разойдётся с их, модель получит не те номера и разметит не то.
    """

    def __init__(self, vocab_path: str, lower: bool = True,
                 unk: str = "[UNK]") -> None:
        self.lower = lower
        self.unk = unk
        self.vocab: dict[str, int] = {}
        with open(vocab_path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                self.vocab[line.rstrip("\n")] = i

    @staticmethod
    def _strip_accents(text: str) -> str:
        out = []
        for ch in unicodedata.normalize("NFD", text):
            if unicodedata.category(ch) != "Mn":
                out.append(ch)
        return "".join(out)

    def words(self, text: str) -> list[str]:
        """Разбить на слова так же, как BasicTokenizer: пробелы и пунктуация."""
        t = text.lower() if self.lower else text
        if self.lower:
            t = self._strip_accents(t)
        return re.findall(r"\w+|[^\w\s]", t, re.UNICODE)

    def encode_word(self, word: str) -> list[int]:
        """Разобрать одно слово на куски словаря. Не вышло - [UNK]."""
        if word in self.vocab:
            return [self.vocab[word]]
        ids, start = [], 0
        while start < len(word):
            end = len(word)
            piece_id = None
            while start < end:
                piece = word[start:end]
                if start > 0:
                    piece = "##" + piece
                if piece in self.vocab:
                    piece_id = self.vocab[piece]
                    break
                end -= 1
            if piece_id is None:
                return [self.vocab.get(self.unk, 0)]
            ids.append(piece_id)
            start = end
        return ids

    def encode(self, words: list[str]) -> tuple[list[int], list[int]]:
        """Номера токенов и для каждого - номер слова, из которого он вышел.

        Второе обязательно: метку ставит модель на токен, а знак нам нужен
        после СЛОВА. Без этой карты «привет» из трёх кусков дал бы три знака.
        """
        ids, owner = [], []
        for i, w in enumerate(words):
            for tid in self.encode_word(w):
                ids.append(tid)
                owner.append(i)
        return ids, owner


# --------------------------------------------------------------------------
# Метки. У разных моделей свои наборы, поэтому разбираем имя, а не номер.

_PUNCT_BY_NAME = (
    ("PERIOD", "."), ("COMMA", ","), ("QUESTION", "?"), ("EXCLAM", "!"),
    ("DASH", " -"), ("COLON", ":"), ("SEMICOLON", ";"),
)


def _decode_label(name: str) -> tuple[str, str]:
    """Из имени метки - (знак после слова, как писать слово).

    Имена бывают «LOWER_COMMA», «UPPER_PERIOD», «UPPER_TOTAL_O». Разбираем по
    подстрокам, а не по номеру: у RUPunct 33 метки, у sbert 13, и номера у них
    разные. Имя же читается одинаково.
    """
    up = name.upper()
    mark = ""
    for key, ch in _PUNCT_BY_NAME:
        if key in up:
            mark = ch
            break
    if "UPPER_TOTAL" in up:
        case = "upper"
    elif "UPPER" in up:
        case = "title"
    else:
        case = "lower"
    return mark, case


class Punctuator:
    """Модель расстановки знаков. Загружается один раз и живёт в памяти."""

    def __init__(self, folder: str, threads: int = 2) -> None:
        import onnxruntime as rt

        with open(os.path.join(folder, "labels.json"), encoding="utf-8") as f:
            meta = json.load(f)
        self.labels = meta["labels"]
        self.decoded = [_decode_label(x) for x in self.labels]
        self.tok = WordPiece(os.path.join(folder, "vocab.txt"),
                             lower=bool(meta.get("do_lower_case", True)),
                             unk=meta.get("unk") or "[UNK]")
        self.cls = self.tok.vocab.get(meta.get("cls") or "[CLS]", 0)
        self.sep = self.tok.vocab.get(meta.get("sep") or "[SEP]", 0)

        so = rt.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        so.add_session_config_entry("session.force_spinning_stop", "1")
        path = os.path.join(folder, "model.int8.onnx")
        if not os.path.exists(path):
            path = os.path.join(folder, "model.onnx")
        self.sess = rt.InferenceSession(path, sess_options=so,
                                        providers=["CPUExecutionProvider"])
        self.inputs = [i.name for i in self.sess.get_inputs()]

    def warmup(self) -> None:
        """Первый прогон всегда дороже остальных - делаем его заранее."""
        try:
            self.apply("проверка связи")
        except Exception:  # noqa: BLE001
            pass

    def apply(self, text: str) -> str:
        """Расставить знаки и заглавные. Пусто на входе - пусто на выходе."""
        import numpy as np

        words = self.tok.words(text)
        if not words:
            return text
        ids, owner = self.tok.encode(words)
        # Обрезаем по длине модели: длинная диктовка приходит сюда уже
        # разрезанной, но подстраховаться дешевле, чем упасть.
        limit = _MAX_LEN - 2
        ids, owner = ids[:limit], owner[:limit]
        seq = [self.cls, *ids, self.sep]

        feed = {"input_ids": np.array([seq], dtype=np.int64),
                "attention_mask": np.ones((1, len(seq)), dtype=np.int64),
                "token_type_ids": np.zeros((1, len(seq)), dtype=np.int64)}
        out = self.sess.run(["logits"],
                            {k: v for k, v in feed.items() if k in self.inputs})[0]
        best = out[0].argmax(axis=-1)[1:len(ids) + 1]

        # Метку слова берём по ПЕРВОМУ его куску: разбор на куски - дело
        # словаря, а знак относится к слову целиком.
        per_word: dict[int, int] = {}
        for tok_i, w_i in enumerate(owner):
            per_word.setdefault(w_i, int(best[tok_i]))

        out_words = []
        for i, w in enumerate(words):
            mark, case = self.decoded[per_word.get(i, 0)] \
                if per_word.get(i, 0) < len(self.decoded) else ("", "lower")
            if case == "upper":
                w = w.upper()
            elif case == "title":
                w = w[:1].upper() + w[1:]
            out_words.append(w + mark)
        res = " ".join(out_words)
        res = re.sub(r"\s+([,.!?;:])", r"\1", res)
        res = re.sub(r"\s{2,}", " ", res).strip()
        if res and res[-1] not in ".!?…":
            res += "."
        return res
