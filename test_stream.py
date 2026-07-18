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

    print("\nИТОГ:", "всё сходится" if ok else "ЕСТЬ ПРОВАЛЫ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
