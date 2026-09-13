"""Опись контролов: что переносить в React и в каком порядке.

Зачем. Фаза 3 плана обещает «36 QML-контролов → ~20 React-компонентов», но
какие именно схлопываются и с чего начинать - там не сказано. Решать это на
глаз нельзя: контрол, стоящий в сорока девяти местах, и контрол, стоящий в
одном, - работа разного веса и разного риска.

Опись снимается разбором, а не чтением: считаем, сколько раз каждый контрол
поставлен во ВСЕЙ вёрстке, на чём он основан (`Item`, `Rectangle`, другой наш
контрол) и какие у него свойства и сигналы - это и есть будущий props-интерфейс.

Порядок переноса из этого следует прямо: сперва то, на чём стоит всё
остальное, потом частое, потом одиночки. Перенести редкий контрол раньше
несущего - значит переписать его дважды.

    python tools/controls_inventory.py           # опись в консоль
    python tools/controls_inventory.py --md      # docs/controls-inventory.md
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTRL = os.path.join(ROOT, "qml", "controls")

RE_PROP = re.compile(r'^\s*(?:readonly\s+)?property\s+(\S+)\s+(\w+)', re.M)
RE_ALIAS = re.compile(r'^\s*(?:default\s+)?property\s+alias\s+(\w+)', re.M)
RE_SIGNAL = re.compile(r'^\s*signal\s+(\w+)', re.M)
RE_FUNC = re.compile(r'^\s*function\s+(\w+)', re.M)


def qml_files() -> list:
    out = []
    for base, _dirs, files in os.walk(os.path.join(ROOT, "qml")):
        out += [os.path.join(base, f) for f in files if f.endswith(".qml")]
    return out


def base_type(body: str) -> str:
    """На чём стоит контрол - первый тип после блока импортов."""
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("//") or s.startswith("import"):
            continue
        m = re.match(r'^([A-Z][\w.]*)\s*\{', s)
        if m:
            return m.group(1)
    return "?"


def main() -> int:
    names = sorted(f[:-4] for f in os.listdir(CTRL) if f.endswith(".qml"))
    files = qml_files()
    texts = {p: open(p, encoding="utf-8").read() for p in files}

    rows = []
    for n in names:
        body = texts[os.path.join(CTRL, n + ".qml")]
        # Считаем постановки `Имя {`, но не в собственном файле контрола:
        # там это его же объявление, а не использование.
        used = 0
        where = set()
        for p, t in texts.items():
            if os.path.basename(p) == n + ".qml":
                continue
            # Постановка по типу - `Имя {`.
            k = len(re.findall(rf'(?<![\w.]){n}\s*\{{', t))
            # И постановка через Loader - `source: "Имя.qml"`. Её первая
            # редакция этой описи не считала, и CardShadow с PillShadow
            # оказались в списке «не ставят нигде» - то есть в списке на
            # выброс. Оба живые: Card.qml и Overlay.qml грузят их Loader'ом
            # именно строкой, чтобы `import QtQuick.Effects` не тянулся туда,
            # где тени нет. Ошибка нашлась проверкой грепом, а не чтением -
            # и стоила бы удалённой тени в фазе 7.
            # Путь перед именем допускаем: Overlay.qml грузит тень как
            # "../controls/PillShadow.qml", и точное совпадение с кавычкой
            # её не находило - контрол снова уезжал в список на выброс.
            k += len(re.findall(rf'source:\s*[^\n]*["/]{n}\.qml"', t))
            if k:
                used += k
                where.add(os.path.basename(p))
        props = [b for _a, b in RE_PROP.findall(body)] + RE_ALIAS.findall(body)
        rows.append({
            "name": n, "lines": body.count("\n") + 1, "used": used,
            "base": base_type(body), "props": sorted(set(props)),
            "signals": RE_SIGNAL.findall(body),
            "funcs": RE_FUNC.findall(body),
            "where": sorted(where),
        })

    # Наш контрол, стоящий внутри другого нашего, - несущий: его переносим
    # первым, иначе всё, что на нём стоит, придётся переписывать дважды.
    own = {r["name"] for r in rows}
    for r in rows:
        r["load_bearing"] = r["base"] in own or any(
            os.path.basename(w)[:-4] in own for w in r["where"])

    rows.sort(key=lambda r: (-r["used"], r["name"]))

    if "--md" not in sys.argv:
        print(f"{'контрол':22s} {'строк':>5s} {'ставят':>6s}  основа")
        for r in rows:
            print(f'  {r["name"]:20s} {r["lines"]:5d} {r["used"]:6d}  {r["base"]}')
        print(f"\nвсего {len(rows)} контролов, "
              f"{sum(r['lines'] for r in rows)} строк, "
              f"{sum(r['used'] for r in rows)} постановок")
        print("не ставят нигде:",
              " ".join(r["name"] for r in rows if not r["used"]) or "-")
        return 0

    total_used = sum(r["used"] for r in rows)
    out = [
        "# Опись контролов: что переносить и в каком порядке",
        "",
        "Снимается разбором: `python tools/controls_inventory.py --md`.",
        "Поменялись контролы - перегенерировать.",
        "",
        f"Всего {len(rows)} контролов, {sum(r['lines'] for r in rows)} строк,",
        f"{total_used} постановок во всей вёрстке.",
        "",
        "**Порядок переноса читается из колонки «ставят».** Контрол, который",
        "стоит в полусотне мест, держит на себе вид всего окна; одиночка не",
        "держит ничего. Начинать с редкого - значит переписывать его второй раз",
        "после того, как выяснится, каким должен быть частый.",
        "",
        "| Контрол | Строк | Ставят | Основа |",
        "|---|---|---|---|",
    ]
    for r in rows:
        out.append(f'| `{r["name"]}` | {r["lines"]} | {r["used"]} | '
                   f'`{r["base"]}` |')

    dead = [r for r in rows if not r["used"]]
    if dead:
        out += ["", "## Не ставят нигде", "",
                "Переносить незачем - выбросить вместе с QML-версией.",
                "Проверить перед этим, что их правда никто не зовёт из Python.",
                ""]
        out += [f'- `{r["name"]}` ({r["lines"]} строк)' for r in dead]

    out += ["", "## Интерфейс каждого", "",
            "Свойства - это будущие props, сигналы - обработчики. Переписывать",
            "интерфейс по дороге не надо: он уже прошёл через живое окно.", ""]
    for r in rows:
        if not r["used"]:
            continue
        out += [f'### `{r["name"]}`', "",
                f'{r["lines"]} строк, ставят {r["used"]} раз, основа '
                f'`{r["base"]}`.', ""]
        if r["props"]:
            out.append(f'- свойства: {", ".join("`" + p + "`" for p in r["props"])}')
        if r["signals"]:
            out.append(f'- сигналы: {", ".join("`" + s + "`" for s in r["signals"])}')
        if r["funcs"]:
            out.append(f'- функции: {", ".join("`" + f + "`" for f in r["funcs"])}')
        out.append(f'- где: {", ".join(r["where"][:6])}'
                   + (" и ещё" if len(r["where"]) > 6 else ""))
        out.append("")

    path = os.path.join(ROOT, "docs", "controls-inventory.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print(f"записано: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
