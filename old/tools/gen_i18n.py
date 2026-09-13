"""Английский словарь для страницы печатается из i18n.py, а не пишется заново.

Источник один - `i18n.py`, тот же, по которому живёт QML. Иначе два словаря
разъедутся в первый же день, и разъедутся молча: строка переведена в одном
окне и не переведена в соседнем.

**Словарь НЕ попадает в бандл, и это не мелочь.** 880 пар - это около 20 КБ
gzip, а бандл уже 115 из 120 разрешённых планом. Поэтому словарь кладётся
отдельным файлом `i18n.en.json` рядом со страницей, и подтягивается только
если человек включил английский. У русского - большинства - он не стоит ни
байта, ни запроса.

Запрос при этом дешёвый: страница раздаётся нашим же QTcpServer с 127.0.0.1,
это не поход в сеть.

    python tools/gen_i18n.py           переписать web/public/i18n.en.json
    python tools/gen_i18n.py --check   сверить (стоит в CI)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import i18n  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "web", "public", "i18n.en.json")


def render() -> str:
    # Сортировка по ключу, а не порядок объявления: иначе перестановка двух
    # строк в i18n.py даёт diff на весь файл, и --check в CI начинает падать
    # на пустом месте.
    return json.dumps(dict(sorted(i18n.EN.items())),
                      ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        if not os.path.exists(OUT):
            print(f"нет {OUT} - запустите без --check")
            return 1
        if open(OUT, encoding="utf-8").read() != text:
            print("i18n.en.json разъехался с i18n.py - перегенерируйте:")
            print("  python tools/gen_i18n.py")
            return 1
        print(f"i18n.en.json совпадает с i18n.py ({len(i18n.EN)} пар)")
        return 0

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"записано: {OUT}")
    print(f"  пар {len(i18n.EN)}, {len(text.encode('utf-8')) / 1024:.0f} КБ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
