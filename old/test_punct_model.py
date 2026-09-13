"""Модель расстановки знаков - уровень 2.

Саму модель не требует: она необязательна и весит 30 МБ, а в CI её нет.
Проверяем то, что от неё не зависит и что легче всего сломать, - разбор меток
и наш собственный токенизатор. Если модель установлена, прогоняем и её.

Токенизатор здесь свой, без transformers, и это самое опасное место файла:
разойдись он с эталонным BertTokenizer хоть на один номер - модель получит не
те токены и разметит не то. Молча.

Запуск: python test_punct_model.py
"""

import sys

import punct_model as PM

ok = True


def check(cond: bool, text: str) -> None:
    global ok
    ok = ok and bool(cond)
    print(("  ок   " if cond else "ПРОВАЛ ") + text)


def main() -> int:
    # --- разбор меток ---
    #
    # У RUPunct 33 метки, у sbert 13, и номера у них разные. Разбираем по
    # ИМЕНИ, а не по номеру - иначе одна модель ставила бы знаки другой.
    for name, знак, регистр in (
        ("LOWER_O", "", "lower"),
        ("LOWER_COMMA", ",", "lower"),
        ("UPPER_PERIOD", ".", "title"),
        ("UPPER_TOTAL_QUESTION", "?", "upper"),
        ("LOWER_EXCLAM", "!", "lower"),
        ("UPPER_O", "", "title"),
    ):
        got = PM._decode_label(name)
        check(got == (знак, регистр), f"метка {name} -> знак {знак!r}, {регистр}")

    # --- токенизатор ---
    import os
    import tempfile

    d = tempfile.mkdtemp()
    vocab = os.path.join(d, "vocab.txt")
    with open(vocab, "w", encoding="utf-8") as f:
        f.write("\n".join(["[PAD]", "[UNK]", "[CLS]", "[SEP]",
                           "привет", "как", "де", "##ла", "мир", "!", ","]))
    t = PM.WordPiece(vocab)

    check(t.words("Привет, как дела!") == ["привет", ",", "как", "дела", "!"],
          "разбиение на слова отделяет знаки от слов")
    check(t.encode_word("привет") == [4], "целое слово из словаря - один номер")
    check(t.encode_word("дела") == [6, 7],
          "слова нет целиком - разбирается на куски с «##»")
    check(t.encode_word("абракадабра") == [1],
          "слово не разобралось - [UNK], а не падение")

    ids, owner = t.encode(["привет", "дела"])
    check(ids == [4, 6, 7], "номера идут подряд по всем словам")
    check(owner == [0, 1, 1],
          "карта «токен -> слово» верна: без неё знак после «дела» "
          "поставился бы дважды, по разу на кусок")

    check(t.words("ПРИВЕТ") == ["привет"], "приведение к строчным работает")

    # --- ЛОВУШКА: пустое и мусор ---
    check(t.words("") == [], "пустая строка не ломает разбор")
    check(t.encode([]) == ([], []), "пустой список слов не ломает кодирование")

    # --- живая модель, если установлена ---
    if PM.installed():
        p = PM.Punctuator(PM.folder())
        p.warmup()
        got = p.apply("привет как дела")
        check(bool(got) and got[0].isupper(),
              f"модель отвечает и ставит заглавную: {got!r}")
        check(len(got.replace(",", "").replace(".", "").replace("?", "").split())
              == 3, "модель не теряет и не добавляет слов")
        import time

        p.apply("разогрев")
        t0 = time.perf_counter()
        p.apply("встреча в пятницу давай перенесём на понедельник")
        dt = (time.perf_counter() - t0) * 1000
        check(dt < 200, f"модель укладывается в 200 мс ({dt:.1f} мс)")
    else:
        print("  --   модель не установлена, её проверки пропущены")

    print("\nИТОГ:", "всё сходится" if ok else "ЕСТЬ ПРОВАЛЫ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
