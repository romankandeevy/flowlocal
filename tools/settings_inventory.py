"""Опись настроек: что живёт на каждой из восьми страниц.

Зачем. Фаза 4 плана переносит `qml/windows/Settings.qml` (3 785 строк) на
React по одной странице, и критерий готовности там жёсткий: после прохода по
странице `config.json` должен совпадать с тем, что даёт QML-версия. Чтобы
такое сверить, надо сперва знать, ЧТО на странице есть, - а на глаз по трём
тысячам строк это не читается.

Опись снимается разбором исходника, а не глазами: ключ конфига попадает в
список только если он в файле действительно есть. Пропустить настройку при
переносе - значит молча потерять её у людей на руках; такое ловится не
ревью, а сверкой двух списков.

Что считаем настройкой:

- `B.get("ключ")` и `B.set("ключ", ...)` - прямое чтение и запись конфига;
- `path: "ключ"` - сахар `ToggleRow`, внутри он делает то же самое;
- `B.метод(...)` - действие, у которого нет ключа: скачать модель, открыть
  журнал, поставить Ollama. Их переносить тоже, а по ключам они не видны.

    python tools/settings_inventory.py            # опись в консоль
    python tools/settings_inventory.py --md       # готовый docs/settings-inventory.md
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "qml", "windows", "Settings.qml")

# Страницы - это Column на одном уровне вложенности внутри `content`. Опознаём
# их по отступу, а не по имени: id есть не у всех, а отступ есть у каждой.
PAGE_INDENT = 12
# Условие видимости стоит не сразу за скобкой: у половины страниц перед ним
# идут id, ширина и отступы. Восьми строк хватает на все девять.
HEAD_LINES = 10

RE_GET = re.compile(r'\bB\.get\(\s*"([^"]+)"')
RE_SET = re.compile(r'\bB\.set\(\s*"([^"]+)"')
RE_PATH = re.compile(r'^\s*path:\s*"([^"]+)"', re.M)
RE_CALL = re.compile(r'\bB\.([a-zA-Z_]\w*)\s*\(')
RE_VISIBLE = re.compile(r'^\s*visible:\s*(.+)$', re.M)
RE_PAGE_KEY = re.compile(r'page\s*===?\s*"([^"]+)"')

# Не настройки, а служебные вызовы моста. В опись их тащить незачем: они есть
# на каждой странице и ни о чём не говорят.
SKIP_CALLS = {"get", "set", "t"}


def blocks(lines: list) -> list:
    """Куски файла по фигурным скобкам, начиная с каждой страницы-Column."""
    out = []
    for i, line in enumerate(lines):
        indent = len(line) - len(line.lstrip())
        if indent != PAGE_INDENT or not line.strip().startswith("Column {"):
            continue
        depth, j = 0, i
        while j < len(lines):
            depth += lines[j].count("{") - lines[j].count("}")
            if depth == 0 and j > i:
                break
            j += 1
        out.append((i + 1, j + 1, "\n".join(lines[i:j + 1])))
    return out


def page_name(body: str, lines: list, start: int) -> str:
    """Имя страницы берём из её же условия видимости: `visible: page === "..."`."""
    head = "\n".join(lines[start - 1:start + HEAD_LINES])
    m = RE_PAGE_KEY.search(head)
    if m:
        return m.group(1)
    m = re.search(r'^\s*id:\s*(\w+)', head, re.M)
    return m.group(1) if m else "без имени"


def collect(body: str) -> dict:
    keys = sorted(set(RE_GET.findall(body)) | set(RE_SET.findall(body))
                  | set(RE_PATH.findall(body)))
    calls = sorted({c for c in RE_CALL.findall(body) if c not in SKIP_CALLS})
    return {"keys": keys, "calls": calls}


def main() -> int:
    lines = open(SRC, encoding="utf-8").read().splitlines()
    pages = []
    for start, end, body in blocks(lines):
        info = collect(body)
        if not info["keys"] and not info["calls"]:
            continue          # не страница, а вёрстка без настроек
        pages.append({"name": page_name(body, lines, start), "from": start,
                      "to": end, "lines": end - start + 1, **info})

    if "--md" not in sys.argv:
        for p in pages:
            print(f'\n{p["name"]}  (строки {p["from"]}-{p["to"]}, {p["lines"]})')
            print(f'  ключей {len(p["keys"])}: {" ".join(p["keys"]) or "-"}')
            print(f'  вызовов {len(p["calls"])}: {" ".join(p["calls"]) or "-"}')
        total_k = len({k for p in pages for k in p["keys"]})
        total_c = len({c for p in pages for c in p["calls"]})
        print(f"\nвсего: {len(pages)} страниц, {total_k} ключей, {total_c} вызовов")
        return 0

    out = [
        "# Опись настроек: что на каждой странице",
        "",
        "Снимается разбором `qml/windows/Settings.qml`, а не глазами:",
        "`python tools/settings_inventory.py --md`. Поменялась вёрстка -",
        "перегенерировать, иначе опись врёт.",
        "",
        "Зачем. Фаза 4 переносит страницы по одной, и критерий там жёсткий:",
        "после прохода `config.json` совпадает с тем, что даёт QML-версия.",
        "Сверять надо по списку, а не по памяти - пропущенная настройка тихо",
        "исчезает у людей на руках.",
        "",
        "| Страница | Строки | Ключей | Вызовов |",
        "|---|---|---|---|",
    ]
    for p in pages:
        out.append(f'| `{p["name"]}` | {p["from"]}-{p["to"]} ({p["lines"]}) | '
                   f'{len(p["keys"])} | {len(p["calls"])} |')

    n_keys = len({k for p in pages for k in p["keys"]})
    n_calls = len({c for p in pages for c in p["calls"]})
    out += [
        "",
        "## Чего критерий из плана не ловит",
        "",
        f"Настроек с ключом - {n_keys}, а действий без ключа - {n_calls}.",
        "Критерий фазы 4 («`config.json` после прохода совпадает с QML-версией»)",
        f"проверяет только первые {n_keys} из {n_keys + n_calls}: у остальных",
        "ключа нет вовсе, и в конфиге их пропажа не видна никак.",
        "",
        "Четыре страницы из восьми - `Статистика`, `Заметки`, `Слова`,",
        "`О программе` - не пишут в конфиг ни одного ключа. Для них этот",
        "критерий не значит ровно ничего: страницу можно перенести пустой и",
        "сверка пройдёт.",
        "",
        "Значит, на каждую страницу нужен второй критерий - список вызовов ниже",
        "пройден руками, каждый делает то же, что в QML-версии. Кнопка, которая",
        "молчит, - это не «мелочь на потом»: у человека она просто перестала",
        "работать, и узнает он об этом раньше нас.",
    ]
    for p in pages:
        out += ["", f'## `{p["name"]}`', "",
                f'Строки {p["from"]}-{p["to"]} в `Settings.qml`.', ""]
        if p["keys"]:
            out.append("**Ключи конфига.** Каждый должен читаться и писаться "
                       "после переноса.")
            out.append("")
            out += [f'- `{k}`' for k in p["keys"]]
            out.append("")
        if p["calls"]:
            out.append("**Вызовы `Backend`.** Ключа у них нет, по `config.json` "
                       "их пропажу не видно.")
            out.append("")
            out += [f'- `B.{c}()`' for c in p["calls"]]
    path = os.path.join(ROOT, "docs", "settings-inventory.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print(f"записано: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
