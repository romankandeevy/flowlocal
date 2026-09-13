"""Подстановки, найденные по истории: находки и ловушки.

Половина случаев - ловушки, где верный ответ «ничего не предлагать». Цена
ошибки несимметрична: не заметить повтор - полбеды, человек и так диктует
руками. А предложить ерунду - значит научить его закрывать наши предложения не
читая, и тогда не сработает уже ничего.

    $env:PYTHONIOENCODING="utf-8"
    python test_suggest.py
"""

import sys

import suggest


def rows(*texts):
    return [{"text": t} for t in texts]


def values(found):
    return [c["value"] for c in found]


def check(name, got, want, fails):
    ok = got == want
    print(f"  {'OK ' if ok else 'НЕТ'} {name}")
    if not ok:
        print(f"      ждали: {want}")
        print(f"      вышло: {got}")
        fails.append(name)


def main() -> int:
    fails: list = []
    print("НАХОДКИ")

    check("почта после двух раз",
          values(suggest.find(rows(
              "Пришли отчёт на roman@example.com до пятницы",
              "Мой адрес roman@example.com, пиши туда"))),
          ["roman@example.com"], fails)

    check("длинная фраза после трёх раз",
          values(suggest.find(rows(
              "Собери сводку по продажам за июнь и пришли",
              "Собери сводку по продажам за июнь, пожалуйста",
              "Ещё раз собери сводку по продажам за июнь"))),
          ["Собери сводку по продажам за июнь"], fails)

    check("телефон",
          values(suggest.find(rows(
              "Мой номер +7 916 123 45 67, звони",
              "Запиши +7 916 123 45 67"))),
          ["+7 916 123 45 67"], fails)

    print("\nЛОВУШКИ - верный ответ «ничего»")

    check("служебная связка не предлагается",
          suggest.find(rows("я хочу чтобы ты сделал", "я хочу чтобы ты проверил",
                            "я хочу чтобы ты успел")),
          [], fails)

    check("двух раз для фразы мало",
          suggest.find(rows("Собери сводку по продажам за июнь",
                            "Собери сводку по продажам за июнь")),
          [], fails)

    check("одного раза для почты мало",
          suggest.find(rows("Пиши на roman@example.com")), [], fails)

    check("уже заведённое не предлагаем снова",
          suggest.find(rows("Пиши на roman@example.com",
                            "Адрес roman@example.com"),
                       snippets={"моя почта": "roman@example.com"}),
          [], fails)

    check("отклонённое не возвращается",
          suggest.find(rows("Пиши на roman@example.com",
                            "Адрес roman@example.com"),
                       skip=["roman@example.com"]),
          [], fails)

    check("повтор внутри одной диктовки - не повтор",
          suggest.find(rows("roman@example.com и ещё раз roman@example.com")),
          [], fails)

    check("пустая история не роняет", suggest.find([]), [], fails)

    print("\nОТБОР")
    long_found = suggest.find(rows(
        "Собери сводку по продажам за июнь и пришли до конца дня",
        "Собери сводку по продажам за июнь и пришли до конца дня, пожалуйста",
        "Ещё: собери сводку по продажам за июнь и пришли до конца дня"))
    check("из вложенных повторов берётся самый длинный",
          len(long_found) == 1 and len(long_found[0]["value"].split()) >= 8,
          True, fails)

    print()
    if fails:
        print(f"ПРОВАЛЕНО: {len(fails)} - {', '.join(fails)}")
        return 1
    print("ОК")
    return 0


if __name__ == "__main__":
    sys.exit(main())
