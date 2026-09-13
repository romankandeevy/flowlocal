"""Вопрос по голосу: находит подъём тона и НЕ находит там, где его нет.

Сигналы синтетические и потому детерминированные: настоящий голос в тесте
означал бы, что тест зависит от того, как сегодня звучит человек. Проверяем
физику - умеем ли мы отличить восходящий тон от нисходящего, - а не модель речи.

Половина случаев - ловушки. Лишний вопросительный знак заметен и раздражает
сильнее, чем недостающий: пропущенный человек допишет не глядя, а лишний
заставит перечитать и усомниться во всей чистке.

    $env:PYTHONIOENCODING="utf-8"
    python test_intonation.py
"""

import sys

import numpy as np

import intonation as I

SR = I.SAMPLE_RATE


def voice(f_base: float, f_end: float, seconds: float = 1.2,
          amp: float = 0.2, sharp: float = 0.28) -> np.ndarray:
    """Голосоподобный сигнал с интонацией русского вопроса или утверждения.

    Первая версия теста двигала тон линейно через всю фразу - и детектор её не
    ловил, будучи прав. Русская вопросительная интонация (ИК-3) устроена иначе:
    тон держится ровно и РЕЗКО идёт вверх на последнем ударном слоге. Плавный
    дрейф через всю фразу вопросом не является - это просто человек оживился.

    sharp - сколько секунд с конца занимает движение тона.

    Не чистая синусоида: у голоса есть обертоны, и автокорреляция на них ведёт
    себя иначе. Добавляем вторую и третью гармоники, как у гласной.
    """
    n = int(seconds * SR)
    f = np.full(n, float(f_base))
    # Движение не длиннее самого сигнала: короткий обрывок фразы - законный
    # случай, и генератор не должен на нём падать.
    k = min(int(sharp * SR), n)
    if k > 0:
        f[-k:] = np.linspace(f_base, f_end, k)
    phase = 2 * np.pi * np.cumsum(f) / SR
    wave = (np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.25 * np.sin(3 * phase))
    return (amp * wave / 1.75).astype(np.float32)


def check(name, got, want, fails):
    ok = got == want
    print(f"  {'OK ' if ok else 'НЕТ'} {name}")
    if not ok:
        print(f"      ждали: {want!r}")
        print(f"      вышло: {got!r}")
        fails.append(name)


def main() -> int:
    fails: list = []

    print("СЛЫШИМ ПОДЪЁМ")
    check("тон вверх на терцию - вопрос",
          I.rises(voice(120, 170)), True, fails)
    check("тон вверх сильно - вопрос",
          I.rises(voice(110, 200)), True, fails)
    check("низкий голос тоже слышим",
          I.rises(voice(80, 115)), True, fails)

    print("\nЛОВУШКИ - подъёма нет")
    check("тон вниз - утверждение", I.rises(voice(170, 120)), False, fails)
    check("тон ровный - утверждение", I.rises(voice(140, 142)), False, fails)
    check("подъём слабый - не считается", I.rises(voice(140, 152)), False, fails)
    # Плавный дрейф через всю фразу - это не ИК-3, а просто оживление голоса.
    check("плавный дрейф через всю фразу - не вопрос",
          I.rises(voice(120, 170, sharp=1.2)), False, fails)
    check("тишина не роняет", I.rises(np.zeros(SR, dtype=np.float32)), False, fails)
    check("шум - не голос",
          I.rises((np.random.default_rng(1).normal(0, .05, SR)).astype(np.float32)),
          False, fails)
    check("слишком коротко - не судим",
          I.rises(voice(120, 180, seconds=0.1)), False, fails)

    print("\nТЕКСТ: ставим знак")
    up, down = voice(120, 175), voice(175, 120)
    check("точка меняется на вопрос",
          I.maybe_question("Ты придёшь.", up), "Ты придёшь?", fails)
    check("пробел в конце сохраняется",
          I.maybe_question("Ты придёшь. ", up), "Ты придёшь? ", fails)
    check("меняется только последнее предложение",
          I.maybe_question("Я подумал. Ты придёшь.", up),
          "Я подумал. Ты придёшь?", fails)

    print("\nЛОВУШКИ ТЕКСТА - не трогаем")
    check("утверждение остаётся утверждением",
          I.maybe_question("Ты придёшь.", down), "Ты придёшь.", fails)
    check("вопрос уже стоит - не трогаем",
          I.maybe_question("Ты придёшь?", up), "Ты придёшь?", fails)
    check("восклицание не трогаем",
          I.maybe_question("Приходи!", up), "Приходи!", fails)
    check("многоточие не трогаем",
          I.maybe_question("Ну не знаю...", up), "Ну не знаю...", fails)
    check("без знака в конце не трогаем",
          I.maybe_question("Ты придёшь", up), "Ты придёшь", fails)
    check("вопросительное слово - интонация другая, не лезем",
          I.maybe_question("Где ты был.", up), "Где ты был.", fails)
    check("«что» в середине не мешает последнему предложению",
          I.maybe_question("Я знаю, что он ушёл. Ты придёшь.", up),
          "Я знаю, что он ушёл. Ты придёшь?", fails)
    check("вопросительное слово в ПРОШЛОМ предложении не защищает текущее",
          I.maybe_question("Где он. Ты придёшь.", up),
          "Где он. Ты придёшь?", fails)
    check("пусто не роняет", I.maybe_question("", up), "", fails)
    check("нет звука - оставляем как есть",
          I.maybe_question("Ты придёшь.", np.zeros(100, dtype=np.float32)),
          "Ты придёшь.", fails)

    print()
    if fails:
        print(f"ПРОВАЛЕНО: {len(fails)} - {', '.join(fails)}")
        return 1
    print("ОК")
    return 0


if __name__ == "__main__":
    sys.exit(main())
