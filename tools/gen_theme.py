"""web/src/theme.css из theme.py.

    python tools/gen_theme.py           # переписать файл
    python tools/gen_theme.py --check   # только сверить, ничего не трогая

Зачем генератор, а не второй набор токенов. Правило проекта - «токены в
theme.py, один источник правды», - до сих пор держалось само: и пилюля, и окна
читали Python напрямую. У страниц в вебвью такой возможности нет, CSS про
Python не знает, и любой ручной theme.css стал бы вторым источником правды.
Разъехались бы они не сразу и не громко: сперва на один оттенок подписи, потом
на радиус карточки, и заметил бы это владелец, а не тест.

Поэтому файл печатается отсюда и правится только через theme.py. `--check`
стоит в CI и падает, если сгенерированное разошлось с лежащим в репозитории, -
то есть если кто-то поправил CSS руками или поменял краску и забыл перегенерить.

Тёмная тема - отдельным блоком на `[data-theme="dark"]`, атрибут ставит Python
при retheme(). Не prefers-color-scheme: тему выбирают в настройках программы,
и системная там всего лишь один вариант из трёх - иначе выбор «светлая» на
тёмной Windows не сработал бы.
"""

import argparse
import difflib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import theme as T  # noqa: E402

OUT = os.path.join(ROOT, "web", "src", "theme.css")

# Разделы в @theme - по началу имени. Порядок здесь задаёт порядок в файле,
# внутри раздела порядок берётся из css_vars(). Не попавшее ни в один раздел
# печатается в конце: лучше лишняя строка без заголовка, чем потерянный токен.
SECTIONS = (
    ("краски: две настоящие, остальные - чернила поверх бумаги", ("--color-",)),
    ("тень", ("--shadow-",)),
    ("типографика", ("--font-", "--text-")),
    ("метрика", ("--spacing", "--radius-")),
    ("движение", ("--dur", "--ease-")),
)

HEAD = """\
/* Токены Korti для вебвью. СГЕНЕРИРОВАНО из theme.py - руками не править.
 *
 *   python tools/gen_theme.py           переписать
 *   python tools/gen_theme.py --check   сверить (стоит в CI)
 *
 * Подключать после `@import "tailwindcss"` - разбирать @theme больше некому.
 *
 * Тёмная тема - атрибут data-theme="dark" на <html>, его ставит Python при
 * смене темы. Не prefers-color-scheme: тему выбирают в настройках программы,
 * а системная там лишь один вариант из трёх.
 */
"""

# `static`, потому что иначе Tailwind выкидывает из :root переменные, которых
# не увидел в классах. Половина токенов у нас живёт не в классах, а в правилах,
# написанных руками, и в блоке тёмной темы - без static они пропали бы из
# сборки, и перекрашивать было бы нечего.
#
# Сброс `--color-*: initial` и остальных - не чистоплюйство. Умолчания Tailwind
# приносят свою палитру (red-500, slate-200, ...), девять кеглей и чужой
# --ease-out; при живых умолчаниях `bg-slate-100` пишется случайно и работает,
# а правило «цветов ровно два» держится только на памяти автора. Сброс делает
# его правилом сборки: нет токена - нет класса.
OPEN = """
@theme static {
  --color-*: initial;
  --font-*: initial;
  --text-*: initial;
  --radius-*: initial;
  --shadow-*: initial;
  --ease-*: initial;
"""

DARK_HEAD = """
/* Тёмная тема. Здесь только то, что от темы зависит: блок печатается разницей
 * двух css_vars(), поэтому радиусы и кегли сюда не попадают физически.
 *
 * Обе лестницы прозрачностей разные, и это не небрежность - у тёмной темы свои
 * доли, выправленные по замеру контраста (theme.py, ключ "alpha").
 *
 * Вне слоёв: @theme у Tailwind уезжает в @layer theme, а неслоёные правила
 * бьют слоёные при любой специфичности - значит, переопределение сработает,
 * что бы там ни насчитал каскад.
 */
:root[data-theme="dark"] {
"""


def render() -> str:
    """Весь файл строкой. Ничего не пишет - её же сверяет --check."""
    light = T.css_vars("light")
    dark = T.css_vars("dark")

    out = [HEAD, OPEN]
    left = dict(light)
    for title, prefixes in SECTIONS:
        keys = [k for k in light if k.startswith(prefixes)]
        if not keys:
            continue
        out.append(f"\n  /* {title} */\n")
        for k in keys:
            out.append(f"  {k}: {light[k]};\n")
            left.pop(k, None)
    for k in left:                      # раздел не нашёлся - токен всё равно наш
        out.append(f"  {k}: {light[k]};\n")
    out.append("}\n")

    out.append(DARK_HEAD)
    for k, v in dark.items():
        if v != light[k]:
            out.append(f"  {k}: {v};\n")
    out.append("}\n")
    return "".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="theme.py -> web/src/theme.css")
    ap.add_argument("--check", action="store_true",
                    help="не писать, а сверить: разошлось - выход 1")
    args = ap.parse_args()

    want = render()
    # newline="" на обоих концах: без него Windows подставит CRLF при записи,
    # и --check будет падать на файле, который сам же и написал.
    have = None
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8", newline="") as f:
            have = f.read()

    if args.check:
        if have is None:
            print(f"ПЛОХО: нет {os.path.relpath(OUT, ROOT)}")
            print("  собрать: python tools/gen_theme.py")
            sys.exit(1)
        if have != want:
            print(f"ПЛОХО: {os.path.relpath(OUT, ROOT)} разошёлся с theme.py")
            diff = difflib.unified_diff(
                have.splitlines(), want.splitlines(),
                fromfile="в репозитории", tofile="из theme.py", lineterm="")
            for line in list(diff)[:60]:
                print("  " + line)
            print("  починить: python tools/gen_theme.py")
            sys.exit(1)
        n = sum(1 for line in want.splitlines() if line.strip().startswith("--"))
        print(f"ОК: {os.path.relpath(OUT, ROOT)} совпадает с theme.py, {n} строк токенов")
        return

    if have == want:
        print(f"без изменений: {os.path.relpath(OUT, ROOT)}")
        return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write(want)
    print(f"записано: {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
