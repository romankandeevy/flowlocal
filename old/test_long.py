"""Длинная запись: где режем и не теряем ли её.

Модель здесь не нужна - проверяем арифметику разрезов. Она и есть то место,
где ошибка стоит дорого: кусок длиннее предела уронит распознавание целиком,
а рез посреди слова съест слово.

Почему это вообще написано. Владелец надиктовал пятнадцать минут и потерял их:
у модели потолок 5000 кадров по 40 мс, то есть 200 секунд, и всё длиннее падало
с ошибкой broadcast. Полтора года это никто не замечал, потому что короткие
фразы проходят, а длинную никто не пробовал.

Запуск: python test_long.py
"""

import sys

import numpy as np

import config as C
from recorder import SAMPLE_RATE
from transcriber import Transcriber

ok = True


def check(cond: bool, text: str) -> None:
    global ok
    ok = ok and bool(cond)
    print(("  ок   " if cond else "ПРОВАЛ ") + text)


def speech(sec: float) -> np.ndarray:
    """Ровный шум - «речь без пауз», худший случай для разрезов."""
    # Сразу float32: normal() отдаёт float64, и на часовой записи это лишние
    # полгигабайта только ради того, чтобы тут же их выбросить.
    rng = np.random.default_rng(1)
    out = np.empty(int(sec * SAMPLE_RATE), dtype=np.float32)
    rng.standard_normal(out.size, dtype=np.float32, out=out)
    out *= 0.1
    return out


def with_pauses(phrase_sec: float, pause_sec: float, total_sec: float):
    """Настоящая диктовка: фразы, между ними паузы."""
    block = np.concatenate([speech(phrase_sec),
                            np.zeros(int(pause_sec * SAMPLE_RATE), dtype=np.float32)])
    need = int(total_sec * SAMPLE_RATE)
    return np.tile(block, int(need / len(block)) + 1)[:need]


def main() -> int:
    t = Transcriber(dict(C.DEFAULTS), lambda _m: None)
    limit = t._MAX_SEC * SAMPLE_RATE

    # --- короткую не трогаем ---
    check(t._cut_points(speech(30)) == [], "тридцать секунд не режем")
    check(t._cut_points(speech(t._MAX_SEC - 1)) == [],
          "запись впритык под пределом не режется")

    # --- длинную режем, и каждый кусок ниже предела ---
    for sec in (200, 240, 540, 900, 3600):
        a = speech(sec)
        cuts = t._cut_points(a)
        bounds = [0, *cuts, a.size]
        parts = [bounds[i + 1] - bounds[i] for i in range(len(bounds) - 1)]
        check(bool(cuts), f"{sec} с режется ({len(parts)} частей)")
        check(all(p <= limit for p in parts),
              f"  каждый кусок из {sec} с ниже предела модели "
              f"(самый длинный {max(parts) / SAMPLE_RATE:.0f} с)")
        check(all(p > 0 for p in parts), f"  пустых кусков в {sec} с нет")
        check(sum(parts) == a.size, f"  куски покрывают всю запись {sec} с целиком")

    # --- ГЛАВНОЕ: рез попадает в паузу ---
    a = with_pauses(phrase_sec=8, pause_sec=1.2, total_sec=540)
    # Мерим 60 мс вокруг реза. Раньше здесь стояло 30 мс, и проверка краснела
    # на исправном коде: рез вставал на самую границу «речь кончилась - тишина
    # началась», и окно замера её седлало. Это и заставило поправить сам рез -
    # теперь он по середине паузы, с запасом в обе стороны.
    win = int(0.03 * SAMPLE_RATE)
    loud = float(np.abs(a).mean())
    quiet = [float(np.abs(a[max(0, c - win):c + win]).mean())
             for c in t._cut_points(a)]
    check(bool(quiet) and all(q < loud / 20 for q in quiet),
          "на речи с паузами все резы попадают в тишину, а не в середину слова")

    # --- ЛОВУШКИ ---
    silence = np.zeros(int(600 * SAMPLE_RATE), dtype=np.float32)
    cuts = t._cut_points(silence)
    check(len(cuts) < 100,
          "запись из одной тишины не уводит поиск реза в бесконечный цикл")
    check(all(cuts[i] < cuts[i + 1] for i in range(len(cuts) - 1)),
          "резы идут строго по возрастанию - иначе куски перекрылись бы")

    a = speech(400)
    cuts = t._cut_points(a)
    check(all(c > 0 and c < a.size for c in cuts),
          "рез не встаёт на самый край записи")

    check(t._cut_points(np.zeros(0, dtype=np.float32)) == [],
          "пустая запись не ломает разбор")
    check(t._MAX_SEC < 200,
          "предел с запасом: точное число кадров зависит от препроцессора, "
          "и цена промаха - пропавшая фраза")

    print("\nИТОГ:", "всё сходится" if ok else "ЕСТЬ ПРОВАЛЫ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
