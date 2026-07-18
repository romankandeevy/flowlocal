"""Разбор сочетаний: детерминированная половина того, что раньше жило в
test_hotkey.py.

Почему отдельно. `test_hotkey.py` шлёт НАСТОЯЩИЕ нажатия в живую Windows, где
событие может съесть любой чужой хук или смена фокуса. Раздел 9.1-бис плана
доказал четырьмя пробами, что недетерминирован сам тест, а не библиотека, - и
это хуже красного теста: красный не значит ничего, а значит и зелёный тоже.

Здесь только то, что не требует нажатий: разбор, сборка, проверка и показ
сочетаний. Эти таблицы общие у хука и у поля захвата в настройках, и HANDOFF
помнит, чем кончилось их расхождение - поле и хук поняли «ctrl» по-разному.

    $env:PYTHONIOENCODING="utf-8"
    python test_inputspec.py
"""

import sys

import inputspec as I


def check(name, got, want, fails):
    ok = got == want
    print(f"  {'OK ' if ok else 'НЕТ'} {name}")
    if not ok:
        print(f"      ждали: {want!r}")
        print(f"      вышло: {got!r}")
        fails.append(name)


def main() -> int:
    fails: list = []

    print("РАЗБОР")
    check("клавиша с модификаторами", I.parse("ctrl+shift+space"),
          (["ctrl", "shift"], "space", None), fails)
    check("кнопка мыши с модификатором", I.parse("ctrl+mouse4"),
          (["ctrl"], None, "x"), fails)
    check("голая клавиша", I.parse("f9"), ([], "f9", None), fails)
    check("пусто", I.parse(""), ([], None, None), fails)

    print("\nПОРЯДОК И ФОРМА")
    # Порядок модификаторов обязан быть один и тот же, иначе «shift+ctrl+space»
    # и «ctrl+shift+space» окажутся разными хоткеями для одного жеста.
    check("модификаторы приводятся к порядку",
          I.normalize("shift+ctrl+space"), "ctrl+shift+space", fails)
    check("регистр не важен", I.normalize("CTRL+Shift+SPACE"),
          "ctrl+shift+space", fails)
    check("синонимы модификаторов", I.normalize("control+space"),
          I.normalize("ctrl+space"), fails)
    check("разбор и сборка сходятся",
          I.build(*I.parse("ctrl+shift+space")), "ctrl+shift+space", fails)

    print("\nПРОВЕРКА")
    check("обычное сочетание годится", I.is_valid("ctrl+shift+space"), True, fails)
    check("мышь годится", I.is_valid("ctrl+mouse4"), True, fails)
    check("пусто не годится", I.is_valid(""), False, fails)
    # Одиночный модификатор разрешён намеренно: «right ctrl» как хоткей -
    # законный выбор, и parse кладёт его в mods, а клавиши там нет.
    check("одиночный модификатор разрешён", I.is_valid("ctrl"), True, fails)
    # is_valid отвечает на «есть ли что вешать», а не «существует ли такая
    # клавиша»: имена клавиш проверяет уже библиотека хука, и дублировать её
    # таблицу здесь значило бы завести вторую правду. Проверка на выдуманное
    # имя живёт в test_hotkey.py, где хоткей вешается по-настоящему.
    check("несуществующее имя тут не отсеивается", I.is_valid("нетакойклавиши"),
          True, fails)

    print("\nМЫШЬ")
    check("мышиный бинд опознаётся", I.is_mouse("ctrl+mouse4"), True, fails)
    check("клавиатурный - нет", I.is_mouse("ctrl+shift+space"), False, fails)
    # ЛКМ и ПКМ не поддерживаются намеренно: диктовка на левой кнопке сделала
    # бы мышь неработоспособной, а отменить настройку было бы уже нечем.
    # Отказ устроен не запретом, а отсутствием: их нет в таблице кнопок, и
    # слушатель их не ловит. «mouse1» разберётся как клавиша с таким именем -
    # и никогда не сработает, потому что такой клавиши не существует.
    check("левая кнопка не считается мышью", I.is_mouse("mouse1"), False, fails)
    check("правая кнопка не считается мышью", I.is_mouse("mouse2"), False, fails)
    check("в таблице только колесо и боковые",
          sorted(I.TOKEN_TO_MOUSE), ["mouse3", "mouse4", "mouse5"], fails)

    print("\nПОКАЗ ЧЕЛОВЕКУ")
    check("сочетание читается", I.pretty("ctrl+shift+space"),
          "Ctrl + Shift + Space", fails)
    check("мышь по-русски", I.pretty("ctrl+mouse4"), "Ctrl + Мышь 4", fails)
    # Поле настроек не должно быть пустым: пустота читается как «сломалось».
    check("пусто читается словами", I.pretty(""), "не задано", fails)

    print()
    if fails:
        print(f"ПРОВАЛЕНО: {len(fails)} - {', '.join(fails)}")
        return 1
    print("ОК")
    return 0


if __name__ == "__main__":
    sys.exit(main())
