"""Русские строки на странице, не прошедшие через t(). Падает, если такие есть.

Зачем отдельный скрипт. `check_i18n.py` смотрит `qml/` и после переезда будет
вечно зелёным на пустом месте: в QML строк не останется вовсе. Этот смотрит
`web/src` и ловит ровно то же самое - подпись, которую забыли обернуть, и
которая поэтому останется русской при английском интерфейсе.

Что считается нарушением: русский текст, видимый человеку, - в JSX между
тегами или в строковом литерале, - не обёрнутый в `t(...)`.

Что нарушением НЕ считается и почему:

- комментарии. Их не видно, и писать их надо по-русски - это правило проекта;
- витрины и тесты (`*.showcase.tsx`, `*.test.tsx`). Они не едут пользователю;
- `console.warn` и прочая отладка - её читает разработчик, а не человек.

    python tools/check_web_i18n.py
    python tools/check_web_i18n.py --list   печатать все находки, а не первые
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "web", "src")

CYR = re.compile(r"[а-яёА-ЯЁ]")
# Строковый литерал в кавычках любого вида.
STRING = re.compile(r'"([^"\n]*)"|\x27([^\x27\n]*)\x27|`([^`]*)`')
# Текст между тегами: >...< без фигурных скобок внутри.
JSX_TEXT = re.compile(r">([^<>{}]+)<")
# Уже обёрнутое: t("..."), t('...'). Эти находки выбрасываем.
WRAPPED = re.compile(r'\bt\(\s*["\x27`]([^"\x27`]*)["\x27`]')

SKIP_FILES = ("showcase", ".test.")
SKIP_LINES = ("console.", "throw new Error", "// ", "* ", "/*")

# Русская строка в роли ИДЕНТИФИКАТОРА, а не подписи. Оборачивать такие в t()
# нельзя: их сверяют посимвольно с QML (tools/check_icons.py) и по ним ходит
# мост. Перевод сломал бы связь, а не улучшил интерфейс.
#
# Список поимённый, а не «пропускать все объекты»: пропуск по форме записи
# однажды укроет настоящую подпись, и найти её будет нечем.
IDENTIFIER_MAPS = (
    "PAGE_ICONS",       # имя страницы -> иконка, сверяется с Icons.qml
    "TRANSFORM_ICONS",  # то же для преобразований
    "export const PAGES",  # реестр страниц: ключ приходит от Python
)
# Одиночные постоянные, чьё значение - ключ, а не подпись. Их видно по типу:
# `: PageKey =` значит «ключ страницы», и перевод сломал бы совпадение с
# реестром. Ловим по объявлению целиком, а не по значению: так исключение
# нельзя случайно распространить на настоящую подпись с тем же текстом.
IDENTIFIER_CONSTS = (r"DEFAULT_PAGE\s*:\s*PageKey\s*=\s*$",)
# Диагностика, а не интерфейс: это читает разработчик в консоли или в журнале.
DIAGNOSTIC = ("window.__bridge", "__bridge =")
# Названия языков в собственном выборе языка. Переводить нельзя по смыслу:
# человек ищет глазами слово «Русский», а не «Russian».
LANGUAGE_NAMES = {"Русский", "English"}


def strip_comments(src: str) -> list:
    """(номер строки, текст) без комментариев. Блочные выкидываем целиком."""
    out, block = [], False
    for i, line in enumerate(src.splitlines(), 1):
        s = line.strip()
        if block:
            block = "*/" not in s
            continue
        if s.startswith("/*") or s.startswith("{/*"):
            block = "*/" not in s
            continue
        if s.startswith("//") or s.startswith("*"):
            continue
        # Хвостовой комментарий после кода: режем, но только если он не внутри
        # строки. Дёшево и достаточно - строк с «//» внутри кавычек у нас нет.
        if "//" in line and line.count('"') % 2 == 0 and line.count("'") % 2 == 0:
            line = line.split("//")[0]
        out.append((i, line))
    return out


def findings(path: str) -> list:
    """Русские строки без t(). Разбор идёт по ВСЕМУ файлу, а не построчно.

    Построчно не выходит, и первая редакция на этом и сыпала ложными:

    - подпись, перенесённая на две строки, - это одна строка исходника,
      разбитая переносом. Построчный разбор видел два обрывка и ругался на
      оба, хотя обёрнута она была целиком;
    - шаблон вида `${t("рекорд")} ${n}` содержит t() ВНУТРИ себя. Построчный
      разбор брал содержимое бэктиков целиком и не находил его в списке
      обёрнутого - потому что обёрнута там часть, а не всё.

    Проверка с ложными срабатываниями хуже, чем никакой: её перестают читать,
    и настоящая находка тонет среди шума.
    """
    src = open(path, encoding="utf-8").read()
    text = "\n".join(line for _num, line in strip_comments(src))
    text = _drop_identifier_maps(text)

    def line_of(pos: int) -> int:
        return text.count("\n", 0, pos) + 1

    out = []
    for m in STRING.finditer(text):
        body = next(g for g in m.groups() if g is not None)
        if not CYR.search(body):
            continue
        whole = m.group(0)
        # Шаблон, внутри которого уже зовут t(), - обёрнут по частям, и это
        # правильный способ склеивать перевод с подстановкой.
        if whole.startswith("`") and "t(" in whole:
            continue
        # Литерал за `t(` - обёрнут. Смотрим назад С ЗАПАСОМ: между скобкой и
        # строкой бывает перенос с отступом, и коротким окном такие обёртки
        # читались как необёрнутые - на этом проверка ругалась на собственный
        # же правильно обёрнутый текст.
        before = text[max(0, m.start() - 60):m.start()]
        if re.search(r"\bt\(\s*$", before):
            continue
        # Текст исключения: его читает разработчик в журнале, а не человек в
        # окне. Тоже с запасом - вызов бывает многострочным.
        if re.search(r"new Error\(\s*$", before):
            continue
        # Отладочный вывод - туда же.
        if re.search(r"console\.\w+\(\s*$", before):
            continue
        if any(re.search(p, before) for p in IDENTIFIER_CONSTS):
            continue
        # Название языка в его же выборе. «Русский» переводить нельзя по
        # смыслу: человек, который ищет русский язык в английском интерфейсе,
        # ищет глазами слово «Русский», а не «Russian».
        if body.strip() in LANGUAGE_NAMES:
            continue
        if any(s in text[max(0, m.start() - 200):m.start()].rsplit("\n", 1)[-1]
               for s in DIAGNOSTIC):
            continue
        out.append((line_of(m.start()), body.strip()[:70]))

    for m in JSX_TEXT.finditer(text):
        body = m.group(1).strip()
        if not body or not CYR.search(body):
            continue
        # Обобщённые типы TypeScript тоже дают пару «> ... <»:
        # `useState<PageKey>("Главная")` разбирался как текст между тегами, и
        # проверка печатала обрывок кода вместо подписи. Настоящий текст между
        # тегами не содержит скобок, точек с запятой и знака равенства.
        if any(ch in body for ch in ";=(){}"):
            continue
        out.append((line_of(m.start()), body[:70]))
    return out


def _drop_identifier_maps(text: str) -> str:
    """Вырезать карты-идентификаторы целиком: там ключи, а не подписи."""
    for mark in IDENTIFIER_MAPS:
        while mark in text:
            start = text.index(mark)
            open_at = text.find("{", start)
            if open_at < 0:
                break
            depth, i = 0, open_at
            while i < len(text):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            text = text[:start] + text[i + 1:]
    return text


def main() -> int:
    total, files = 0, 0
    show_all = "--list" in sys.argv
    for base, _dirs, fs in os.walk(SRC):
        for f in sorted(fs):
            if not f.endswith((".tsx", ".ts")):
                continue
            if any(s in f for s in SKIP_FILES):
                continue
            path = os.path.join(base, f)
            hits = findings(path)
            if not hits:
                continue
            files += 1
            total += len(hits)
            rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
            print(f"\n{rel}")
            for num, text in (hits if show_all else hits[:6]):
                print(f"  {num:4d}  {text}")
            if not show_all and len(hits) > 6:
                print(f"  ... ещё {len(hits) - 6}")

    print()
    if total:
        print(f"не через t(): {total} строк в {files} файлах")
        print("Оберните в t(\"...\") из web/src/i18n.ts, перевод добавьте в i18n.py.")
        return 1
    print("все русские строки на странице проходят через t()")
    return 0


if __name__ == "__main__":
    sys.exit(main())
