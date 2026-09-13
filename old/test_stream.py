"""Разбор речи на ходу: где режем и не теряем ли слова.

Модель здесь не нужна - подменяем её заглушкой и проверяем арифметику. Именно
в ней цена ошибки: рез посреди слова съест слово, а сбитый счётчик consumed
либо потеряет кусок речи, либо вставит его дважды.

Живой замер (15 июля 2026, речь с паузами, GigaAM): диктовка на 3 минуты -
ожидание 12.8 с до правки и 0.7 с после, потерь слов нет.

Запуск: python test_stream.py
"""

import sys

import numpy as np

import streaming as S

ok = True


def check(cond: bool, text: str) -> None:
    global ok
    ok = ok and bool(cond)
    print(("  ок   " if cond else "ПРОВАЛ ") + text)


def speech(sec: float, loud: float = 0.1) -> np.ndarray:
    rng = np.random.default_rng(7)
    out = np.empty(int(sec * S.SAMPLE_RATE), dtype=np.float32)
    rng.standard_normal(out.size, dtype=np.float32, out=out)
    out *= loud
    return out


def quiet(sec: float) -> np.ndarray:
    return np.zeros(int(sec * S.SAMPLE_RATE), dtype=np.float32)


def main() -> int:
    # --- когда резать нельзя ---
    check(S.find_pause(speech(5)) is None,
          "в пяти секундах сплошной речи паузы нет - не режем")
    check(S.find_pause(np.zeros(0, dtype=np.float32)) is None,
          "пустой звук не ломает поиск")
    check(S.find_pause(speech(30)) is None,
          "полминуты речи без единой паузы - режем только по паузе, а не по часам")

    # --- пауза находится ---
    a = np.concatenate([speech(8), quiet(1.5), speech(8)])
    cut = S.find_pause(a)
    check(cut is not None, "пауза между фразами находится")
    win = int(0.03 * S.SAMPLE_RATE)
    around = float(np.abs(a[cut - win:cut + win]).mean())
    check(around < float(np.abs(a).mean()) / 20,
          "рез попадает в тишину, а не в середину слова")

    # --- ЛОВУШКА: хвост не отдаём ---
    a = np.concatenate([speech(8), quiet(1.0)])
    cut = S.find_pause(a)
    check(cut is None or cut < a.size - S.KEEP_TAIL_SEC * S.SAMPLE_RATE * 0.9,
          "последние секунды не отдаём: человек ещё говорит, и эта пауза "
          "может быть серединой фразы")

    # --- ЛОВУШКА: берём самую позднюю паузу, а не самую тихую ---
    a = np.concatenate([speech(6), quiet(2.0),          # тихая, но ранняя
                        speech(6), quiet(1.0),          # позднее
                        speech(4)])
    cut = S.find_pause(a)
    check(cut is not None and cut > 10 * S.SAMPLE_RATE,
          "берём позднюю паузу: чем больше разобрали на ходу, тем меньше "
          "ждать в конце")

    # --- счётчик consumed ---
    said = []
    st = S.Stream(lambda x: f"[{x.size // S.SAMPLE_RATE}с]", lambda _m: None)
    full = np.concatenate([speech(20), quiet(1.5), speech(20), quiet(1.5),
                           speech(10)])
    pos = 0
    while True:
        chunk, total = full[st.consumed:], full.size
        if not st.feed(chunk, total):
            break
        said.append(st.consumed)
    check(st.runs >= 1, f"на ходу что-то разобрано ({st.runs} захода)")
    check(all(said[i] < said[i + 1] for i in range(len(said) - 1)),
          "счётчик разобранного только растёт - иначе кусок ушёл бы дважды")
    check(st.consumed < full.size,
          "хвост остался на конец, целиком запись на ходу не съедается")

    text = st.finish(full[st.consumed:])
    check(text.count("[") == st.runs + 1,
          "в итог попали все куски: разобранные на ходу плюс хвост")

    # --- ЛОВУШКА: короткая диктовка вообще не режется ---
    st = S.Stream(lambda x: "текст", lambda _m: None)
    check(st.feed(speech(5), int(5 * S.SAMPLE_RATE)) is False,
          "фразу в пять секунд на ходу не трогаем - резать нечего")
    check(st.runs == 0 and st.consumed == 0,
          "и счётчики от этого не сдвинулись")
    check(st.finish(speech(5)) == "текст",
          "короткая диктовка разбирается целиком в конце, как раньше")

    # --- ЛОВУШКА: тишина целиком ---
    st = S.Stream(lambda x: "", lambda _m: None)
    st.feed(quiet(30), int(30 * S.SAMPLE_RATE))
    check(st.finish(quiet(1)) == "",
          "из тишины не рождается текст")

    check(S.KEEP_TAIL_SEC > 0 and S.MIN_TAIL_SEC > S.KEEP_TAIL_SEC,
          "пороги согласованы: берёмся за работу позже, чем оставляем хвост")

    # --- ГЛАВНОЕ: короткая фраза тоже разбирается на ходу ---
    #
    # Порог был 12 секунд, и это обесценивало всю затею: обычная диктовка
    # короче, то есть девять фраз из десяти уходили в хвост целиком.
    def phrase(*parts):
        out = []
        for kind, sec in parts:
            out.append(speech(sec) if kind == "г" else quiet(sec))
        return np.concatenate(out)

    for name, a, ждём in (
        ("8 с с паузой", phrase(("г", 4), ("т", 0.7), ("г", 3.3)), True),
        ("10 с, две паузы", phrase(("г", 4), ("т", 0.6), ("г", 3),
                                   ("т", 0.6), ("г", 2)), True),
        ("6 с с паузой", phrase(("г", 3), ("т", 0.6), ("г", 2.4)), True),
        ("4 с - ниже порога", phrase(("г", 2), ("т", 0.5), ("г", 1.5)), False),
        ("8 с без пауз", speech(8), False),
    ):
        st = S.Stream(lambda x: "т", lambda _m: None, min_tail=5.0)
        got = st.feed(a, a.size)
        check(got is ждём, f"фраза {name}: "
              f"{'разбирается на ходу' if ждём else 'уходит в хвост целиком'}")

    check(S.min_tail_sec({"stream_min_tail_sec": 7.5}) == 7.5,
          "порог читается из конфига - откатить можно без новой версии")
    check(S.WEAK_MIN_TAIL_SEC > S.MIN_TAIL_SEC,
          "на слабой машине порог выше: там разбор на ходу отбирал бы "
          "процессор у микрофона, а потерянный звук хуже медленной работы")

    # --- ЛОВУШКА: кусок не длиннее MAX_FEED_SEC ---
    #
    # Модель одна и считает по очереди. Отпустил клавишу, пока она жуёт
    # сорокасекундный кусок, - и хвост ждёт в очереди за ним.
    длинный = phrase(("г", 18), ("т", 0.6), ("г", 18), ("т", 0.6), ("г", 5))
    st = S.Stream(lambda x: "т", lambda _m: None, min_tail=5.0)
    st.feed(длинный, длинный.size)
    check(st.consumed <= S.MAX_FEED_SEC * S.SAMPLE_RATE,
          f"за один заход отдаём не больше {S.MAX_FEED_SEC:.0f} с "
          f"(отдали {st.consumed / S.SAMPLE_RATE:.0f})")

    # --- упреждающий хвост ---
    #
    # Человек замолкает раньше, чем отпускает клавишу. За эти 200-500 мс модель
    # успевает разобрать остаток - и ожидание становится нулевым.
    говорил = phrase(("г", 4), ("т", 0.7), ("г", 4))
    молчит = np.concatenate([говорил, quiet(0.6)])

    check(S.trailing_silence(молчит) is True,
          "тишина в конце замечается - это и есть «человек договорил»")
    check(S.trailing_silence(говорил) is False,
          "речь в конце за тишину не принимаем - иначе резали бы на полуслове")

    st = S.Stream(lambda x: "заготовка", lambda _m: None, min_tail=5.0)
    check(st.speculate(молчит, молчит.size) is True, "заготовка снимается")
    check(st.spec is not None and st.spec[0] == молчит.size,
          "заготовка помнит, на каком месте записи она снята")
    check(st.finish(молчит) == "заготовка" and st.spec_hit,
          "отпустил в тишине - берём готовое, модель не зовём вовсе")

    # ЛОВУШКА: заговорил снова - заготовка обязана протухнуть.
    st = S.Stream(lambda x: "свежее", lambda _m: None, min_tail=5.0)
    st.speculate(молчит, молчит.size)
    ещё = np.concatenate([молчит, speech(3)])
    check(st.finish(ещё) == "свежее" and not st.spec_hit,
          "человек заговорил после паузы - заготовка выброшена, считаем заново")

    st = S.Stream(lambda x: "т", lambda _m: None, min_tail=5.0)
    check(st.speculate(говорил, говорил.size) is False,
          "пока человек говорит, заготовку не снимаем")

    st = S.Stream(lambda x: "т", lambda _m: None, min_tail=5.0)
    длинный = np.concatenate([speech(20), quiet(0.6)])
    check(st.speculate(длинный, длинный.size) is False,
          "слишком длинный хвост заранее не гоняем - дорого")

    st = S.Stream(lambda x: "т", lambda _m: None, min_tail=5.0)
    st.speculate(молчит, молчит.size)
    check(st.speculate(молчит, молчит.size + 100) is False,
          "заготовку снимаем не чаще, чем раз в пару секунд - лишние прогоны "
          "модели отбирают процессор у микрофона")

    print("\nИТОГ:", "всё сходится" if ok else "ЕСТЬ ПРОВАЛЫ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
