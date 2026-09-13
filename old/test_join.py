"""Склейка подряд идущих диктовок и автоввод Enter.

Обе функции трогают чужой текст, поэтому половина случаев - ловушки, где
верный ответ «не трогать». Склеить то, что склеивать не просили, хуже, чем не
склеить: человек получит строчную букву посреди документа и не поймёт откуда.

    $env:PYTHONIOENCODING="utf-8"
    python test_join.py
"""

import sys
import time

import app as A


class Fake:
    """Только то, что нужно двум методам: конфиг и память о прошлой вставке."""

    _join_with_previous = A.App._join_with_previous
    _auto_enter_here = A.App._auto_enter_here

    def __init__(self, **cfg):
        self.cfg = {"smart_join": True, "join_window_sec": 90,
                    "auto_enter_apps": ["telegram.exe"], **cfg}
        self._last_insert = None

    def after(self, text, where="telegram.exe", ago=0.0):
        self._last_insert = (where, time.time() - ago, text)
        return self


def check(name, got, want, fails):
    ok = got == want
    print(f"  {'OK ' if ok else 'НЕТ'} {name}")
    if not ok:
        print(f"      ждали: {want!r}")
        print(f"      вышло: {got!r}")
        fails.append(name)


def main() -> int:
    fails: list = []

    print("СКЛЕЙКА")
    check("продолжение мысли: пробел и строчная",
          Fake().after("Привет, слушай")._join_with_previous("Давай завтра", "telegram.exe"),
          " давай завтра", fails)
    check("первая диктовка не трогается",
          Fake()._join_with_previous("Давай завтра", "telegram.exe"),
          "Давай завтра", fails)

    print("\nЛОВУШКИ СКЛЕЙКИ - верный ответ «не трогать»")
    check("после точки начинается новое предложение",
          Fake().after("Привет.")._join_with_previous("Давай завтра", "telegram.exe"),
          "Давай завтра", fails)
    check("после вопроса - тоже",
          Fake().after("Ты тут?")._join_with_previous("Давай завтра", "telegram.exe"),
          "Давай завтра", fails)
    check("другое окно - другая мысль",
          Fake().after("Привет, слушай", where="word.exe")
          ._join_with_previous("Давай завтра", "telegram.exe"),
          "Давай завтра", fails)
    check("через полчаса это уже не продолжение",
          Fake().after("Привет, слушай", ago=1800)
          ._join_with_previous("Давай завтра", "telegram.exe"),
          "Давай завтра", fails)
    check("выключено настройкой",
          Fake(smart_join=False).after("Привет, слушай")
          ._join_with_previous("Давай завтра", "telegram.exe"),
          "Давай завтра", fails)
    check("«Я» остаётся заглавным",
          Fake().after("Привет, слушай")._join_with_previous("Я приду", "telegram.exe"),
          " Я приду", fails)
    check("имя собственное не ломается на аббревиатуре",
          Fake().after("Привет, слушай")._join_with_previous("МТС звонили", "telegram.exe"),
          " МТС звонили", fails)
    check("пустая фраза не роняет",
          Fake().after("Привет")._join_with_previous("", "telegram.exe"), "", fails)

    print("\nАВТОВВОД ENTER")
    check("в списке - отправляем", Fake()._auto_enter_here("telegram.exe"), True, fails)
    check("регистр имени не важен", Fake()._auto_enter_here("Telegram.EXE"), True, fails)

    print("\nЛОВУШКИ ENTER - верный ответ «не отправлять»")
    check("не в списке", Fake()._auto_enter_here("winword.exe"), False, fails)
    check("окно неизвестно", Fake()._auto_enter_here(""), False, fails)
    check("список пуст", Fake(auto_enter_apps=[])._auto_enter_here("telegram.exe"),
          False, fails)

    print()
    if fails:
        print(f"ПРОВАЛЕНО: {len(fails)} - {', '.join(fails)}")
        return 1
    print("ОК")
    return 0


if __name__ == "__main__":
    sys.exit(main())
