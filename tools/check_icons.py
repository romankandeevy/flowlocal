"""Не разъехался ли набор иконок между QML и React.

    $env:PYTHONIOENCODING="utf-8"
    python tools/check_icons.py

Зачем инструмент, а не внимательность. Иконок 53, и живут они теперь в двух
местах: `qml/controls/Icons.qml` (пилюля и старые окна) и `web/src/ui/icons.tsx`
(страницы на React). Пока переезд не закончен, обе стороны рабочие, и правка
попадает то в одну, то в другую.

Ошибка при этом молчит. Забыли перенести иконку - ряд останется без картинки,
и заметить это можно только открыв нужную страницу глазами. Перепутали путь -
нарисуется чужая иконка, и она тоже выглядит как иконка. Ни сборка, ни тесты
такого не видят: с точки зрения TypeScript строка есть строка.

Сверяем три вещи, и все три - в обе стороны:

1. имена иконок: чего нет в TSX и чего в нём лишнего;
2. сами path-данные: путь под одинаковым именем должен совпадать посимвольно;
3. обе карты имён - страницы (`forPage`) и готовые преобразования
   (`forTransform`). Карта - это как раз то место, где опечатка в ключе
   («Диктовка» с другой буквой) не ломает ничего, кроме картинки.

Разбор текстовый, без запуска ноды: TypeScript в проекте не исполняется, а
формат обоих файлов простой и оговорён - одна строка `имя: "данные"`, длинные
пути склеены через `+`. Ради разбора файлы и держат в таком виде.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QML = os.path.join(ROOT, "qml", "controls", "Icons.qml")
TSX = os.path.join(ROOT, "web", "src", "ui", "icons.tsx")

# Комментарии режем перед разбором: в них те же кавычки и те же имена иконок,
# что и в данных, и без чистки закомментированная строка считалась бы живой.
COMMENT = re.compile(r"//[^\n]*")
# Одна иконка: имя, двоеточие, один или несколько строковых литералов через +.
ENTRY = re.compile(r'(\w+)\s*:\s*((?:"[^"]*"\s*\+\s*)*"[^"]*")')
# Пара «ключ -> имя иконки» в карте TSX.
PAIR = re.compile(r'"([^"]+)"\s*:\s*"(\w+)"')
# Та же пара в QML: ветка switch.
CASE = re.compile(r'case\s+"([^"]+)"\s*:\s*return\s+(\w+)\s*;')


def read(path: str) -> str:
    if not os.path.exists(path):
        sys.exit(f"нет файла: {path}")
    with open(path, encoding="utf-8") as f:
        return f.read()


def joined(literals: str) -> str:
    """Склеенные литералы: `"a" + "b"` -> `ab`.

    Склейка убирает разбиение по строкам, поэтому перенос длинного пути на
    другие места не считается расхождением - важны только сами данные.
    """
    return "".join(re.findall(r'"([^"]*)"', literals))


def block(text: str, opener: str) -> str:
    """Тело объекта от `opener` до закрывающей скобки в нулевой колонке.

    Скобки не считаем: оба объекта объявлены на верхнем уровне файла, значит
    их `}` - единственная, что стоит без отступа. Дешевле и надёжнее, чем
    разбирать вложенность в файле, где её нет.
    """
    start = text.index(opener) + len(opener)
    end = text.index("\n}", start)
    return text[start:end]


def qml_icons(text: str) -> dict[str, str]:
    body = COMMENT.sub("", text)
    out = {}
    for name, lits in re.findall(
        r'readonly property string\s+(\w+)\s*:\s*((?:"[^"]*"\s*\+\s*)*"[^"]*")', body
    ):
        out[name] = joined(lits)
    return out


def qml_switch(text: str, fn: str) -> dict[str, str]:
    start = text.index(f"function {fn}(")
    body = text[start:]
    nxt = body.find("\n    function ", 1)
    if nxt != -1:
        body = body[:nxt]
    return dict(CASE.findall(COMMENT.sub("", body)))


def tsx_icons(text: str) -> dict[str, str]:
    body = COMMENT.sub("", block(text, "export const ICON_PATHS = {"))
    return {name: joined(lits) for name, lits in ENTRY.findall(body)}


def tsx_map(text: str, const: str) -> dict[str, str]:
    body = COMMENT.sub("", block(text, f"export const {const}: Record<string, IconName | undefined> = {{"))
    return dict(PAIR.findall(body))


def compare(what: str, qml: dict[str, str], tsx: dict[str, str]) -> bool:
    """Печатает расхождения. True - сошлось."""
    print(f"{what}: в Icons.qml {len(qml)}, в icons.tsx {len(tsx)}")
    missing = sorted(set(qml) - set(tsx))
    extra = sorted(set(tsx) - set(qml))
    changed = sorted(k for k in set(qml) & set(tsx) if qml[k] != tsx[k])
    for key in missing:
        print(f"  не перенесено: {key}")
    for key in extra:
        print(f"  лишнее (нет в Icons.qml): {key}")
    for key in changed:
        print(f"  разошлось: {key}")
        print(f"    qml: {qml[key][:90]}")
        print(f"    tsx: {tsx[key][:90]}")
    return not (missing or extra or changed)


def main() -> int:
    qml = read(QML)
    tsx = read(TSX)

    ok = compare("иконок", qml_icons(qml), tsx_icons(tsx))
    ok &= compare("страниц", qml_switch(qml, "forPage"), tsx_map(tsx, "PAGE_ICONS"))
    ok &= compare(
        "преобразований", qml_switch(qml, "forTransform"), tsx_map(tsx, "TRANSFORM_ICONS")
    )

    # Карта не должна ссылаться на иконку, которой нет: в QML такую опечатку
    # ловил бы компилятор QML, в TSX - тип IconName, но карту могли собрать и
    # из строк, пришедших с той стороны моста.
    names = set(tsx_icons(tsx))
    for what, mapping in (
        ("страниц", tsx_map(tsx, "PAGE_ICONS")),
        ("преобразований", tsx_map(tsx, "TRANSFORM_ICONS")),
    ):
        for key, icon in sorted(mapping.items()):
            if icon not in names:
                print(f"карта {what}: «{key}» ссылается на несуществующую иконку {icon}")
                ok = False

    print("сошлось" if ok else "\nрасхождение: набор иконок в React неполный или лишний")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
