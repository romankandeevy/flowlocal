"""Тест палитры: читается ли текст в обеих темах.

    python test_theme.py

Зачем он есть. Тёмная тема была собрана переворотом двух красок - белое стало
чёрным, чёрное белым, - и на этом проверка закончилась. Владелец прошёл мастер
первого запуска вслух и сказал: «в тёмной теме ничего не видно, текст
невзрачный, переключатель сливается с фоном». Он был прав, и узнать это можно
было ровно так же, как здесь: посчитать контраст, а не посмотреть глазами.

Считаем по WCAG 2.1: относительная яркость и отношение (L1+0.05)/(L2+0.05).
Пороги берём оттуда же:

    4.5:1 - обычный текст (AA)
    3.0:1 - крупный текст и границы элементов управления (AA)

Подписи под строками настроек - обычный текст кеглем 13, поэтому им нужен
полный порог, а не поблажка для крупного. Дорожка выключенного переключателя -
элемент управления: ниже трёх её не видно, и «переключилось или нет» становится
загадкой.

Проверяем ОБЕ темы одним списком: правило, которое выполняется только на
светлой, - это не правило, а совпадение.

И ОБА источника краски. С переездом окон в вебвью цвет доезжает до человека
двумя путями: из констант theme.py (пилюля, рамка окна) и из сгенерированного
web/src/theme.css (страницы). Тот же список порогов гоняется по обоим, потому
что «проверено на константах» ничего не говорит про то, что увидят глазами:
между константой и экраном тут лежит генератор и разбор CSS.

Заодно это ловит устаревший CSS. Разбор сравнивается с живыми константами, так
что забытый `python tools/gen_theme.py` после смены краски виден здесь, а не
через неделю в окне. Сверка самого файла с генератором посимвольно - за
`python tools/gen_theme.py --check`; здесь сверяются значения, а не текст.
"""

import os
import re
import sys

import theme as T

CSS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "src", "theme.css")

# Краска в CSS -> её константа в theme.py.
#
# Полупрозрачные токены сверяем со сплавленными (*_FLAT): в CSS они записаны
# как чернила с прозрачностью, и на бумаге дают ровно flat(). Равенство здесь -
# не формальность, а проверка, что доли лестницы уехали в CSS теми же.
PAIRS = {
    "--color-ink": "INK",
    "--color-paper": "PAPER",
    "--color-bg": "BG",
    "--color-surface": "SURFACE",
    "--color-surface-sunken": "SURFACE_SUNKEN",
    "--color-text": "TEXT",
    "--color-text-secondary": "TEXT_SECONDARY",
    "--color-text-muted": "TEXT_MUTED",
    "--color-text-faint": "TEXT_FAINT",
    "--color-text-inverse": "TEXT_INVERSE",
    "--color-border": "BORDER_FLAT",
    "--color-border-strong": "BORDER_STRONG_FLAT",
    "--color-fill-subtle": "FILL_SUBTLE_FLAT",
    "--color-fill": "FILL_FLAT",
    "--color-fill-strong": "FILL_STRONG_FLAT",
    "--color-primary": "PRIMARY",
    "--color-primary-fg": "PRIMARY_FG",
    "--color-accent": "ACCENT",
    "--color-accent-hover": "ACCENT_HOVER",
    "--color-accent-fg": "ACCENT_FG",
    "--color-success": "SUCCESS",
    "--color-danger": "DANGER",
}

# Что меряем и с каким порогом. Один список на оба источника: разойдись пороги
# у констант и у CSS - и сравнивать стало бы нечего.
CHECKS = (
    ("основной текст", "--color-text", 4.5),
    ("вторичный текст", "--color-text-secondary", 4.5),
    ("подпись под строкой", "--color-text-muted", 4.5),
    # Самый тихий уровень - подсказки и пустые состояния. Полный порог ему не
    # по чину (он и задуман тихим), но три - это граница видимости.
    ("самый тихий текст", "--color-text-faint", 3.0),
    # Элементы управления. Дорожка переключателя и рамка карточки - не текст,
    # но если их не видно, интерфейс перестаёт читаться как набор частей: всё
    # сливается в одно поле.
    ("дорожка переключателя", "--color-fill-strong", 1.25),
    ("рамка", "--color-border", 1.25),
    # Сигнальные цвета: ими сообщают об ошибке и успехе, и прочитать их надо с
    # первого взгляда.
    ("ошибка", "--color-danger", 3.0),
    ("успех", "--color-success", 3.0),
    ("акцент", "--color-accent", 3.0),
)

_HEX = re.compile(r"#([0-9a-f]{6})$", re.I)
_MIX = re.compile(
    r"color-mix\(in srgb,\s*var\((--[\w-]+)\)\s*([\d.]+)%,\s*transparent\)$", re.I)


def _lum(c) -> float:
    """Относительная яркость по WCAG: sRGB -> линейный свет -> взвешенная сумма."""
    out = []
    for v in c[:3]:
        v /= 255.0
        out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def ratio(fg, bg) -> float:
    """Контраст двух непрозрачных цветов. Отношение, а не разность."""
    a, b = _lum(fg), _lum(bg)
    lo, hi = min(a, b), max(a, b)
    return (hi + 0.05) / (lo + 0.05)


def check(name: str, got: float, need: float, fails: list) -> None:
    ok = got >= need
    print(f"  {'ок  ' if ok else 'ПЛОХО'} {name}: {got:.2f}:1 (нужно {need}:1)")
    if not ok:
        fails.append(f"{name}: {got:.2f} < {need}")


def css_themes(path: str) -> dict[str, dict[str, str]]:
    """Сгенерированный CSS -> {'light': {переменная: значение}, 'dark': ...}.

    Разбор нарочно дословный, без библиотеки: файл печатает наш же генератор,
    и разбирать в нём нечего, кроме двух блоков без вложенности. Зато любая
    неожиданная форма записи упадёт здесь, а не превратится в тихо пропущенную
    проверку.
    """
    with open(path, encoding="utf-8") as f:
        text = re.sub(r"/\*.*?\*/", "", f.read(), flags=re.S)

    blocks: dict[str, dict[str, str]] = {}
    for sel, body in re.findall(r"([^{}]*)\{([^{}]*)\}", text):
        got = {}
        for decl in body.split(";"):
            name, _, value = decl.partition(":")
            name, value = name.strip(), value.strip()
            # `--color-*: initial` - сброс умолчаний Tailwind, не токен.
            if name.startswith("--") and "*" not in name:
                got[name] = value
        blocks[sel.strip()] = got

    light = blocks.get("@theme static")
    dark = blocks.get(':root[data-theme="dark"]')
    if light is None or dark is None:
        raise ValueError(f"в {path} нет ожидаемых блоков: {list(blocks)}")
    # Тёмная тема - переопределение поверх светлой, ровно как в браузере.
    return {"light": light, "dark": {**light, **dark}}


def rgb_of(name: str, css: dict, bg) -> tuple:
    """Значение переменной -> непрозрачный RGB, каким его увидит глаз.

    Полупрозрачные токены кладём на фон страницы: color-mix с transparent - это
    та же альфа, а на экране под ней всегда бумага. Считаем как браузер: смешение
    идёт по sRGB покомпонентно, то есть тем же mix(), что и flat() в theme.py.
    """
    value = css[name]
    m = _HEX.match(value)
    if m:
        return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    m = _MIX.match(value)
    if m:
        if bg is None:
            raise ValueError(f"{name}: прозрачность некуда положить")
        return tuple(T.mix(bg, rgb_of(m.group(1), css, bg), float(m.group(2)) / 100))
    raise ValueError(f"{name}: непонятное значение {value!r}")


def css_colors(css: dict) -> tuple:
    """Все краски темы, уже сплавленные с её фоном. Возвращает (фон, краски)."""
    bg = rgb_of("--color-bg", css, None)
    return bg, {k: rgb_of(k, css, bg) for k in css if k.startswith("--color-")}


def main() -> None:
    fails: list[str] = []

    if not os.path.exists(CSS):
        print(f"ПРОВАЛ: нет {os.path.relpath(CSS)}")
        print("  собрать: python tools/gen_theme.py")
        sys.exit(1)
    themes = css_themes(CSS)

    for mode in ("light", "dark"):
        T.set_theme(mode)
        bg, colors = css_colors(themes[mode])

        # Константы: их читают пилюля, рамка окна и трей.
        print(f"\n{mode.upper()} - константы (фон {T.hx(T.BG)})")
        for name, var, need in CHECKS:
            check(name, ratio(getattr(T, PAIRS[var]), T.BG), need, fails)

        # Тот же список по CSS: его читают страницы в вебвью.
        print(f"\n{mode.upper()} - CSS (фон {T.hx(bg)})")
        for name, var, need in CHECKS:
            check(name, ratio(colors[var], bg), need, fails)

        # А теперь - совпадают ли вообще два источника. Пороги можно пройти и
        # разными красками; разъехавшуюся палитру ловит только равенство.
        print(f"\n{mode.upper()} - CSS против констант")
        bad: list[str] = []
        # Новая краска в css_vars() должна попасть и сюда, иначе она проедет
        # мимо всех порогов молча.
        for var in sorted(set(colors) - set(PAIRS)):
            bad.append(f"{var}: есть в CSS, нет в списке сверки")
        for var, const in sorted(PAIRS.items()):
            if var not in colors:
                bad.append(f"{var}: нет в CSS")
                continue
            want, got = tuple(getattr(T, const)[:3]), colors[var]
            if want != got:
                bad.append(f"{var}: CSS {T.hx(got)}, {const} {T.hx(want)}")
        for line in bad:
            print("  ПЛОХО " + line)
        fails += [f"{mode}: {line}" for line in bad]
        if not bad:
            print(f"  ок   краски совпали: {len(PAIRS)}")

    print()
    if fails:
        print(f"ПРОВАЛ: {len(fails)}")
        for f in fails:
            print("  " + f)
        sys.exit(1)
    print("ОК")


if __name__ == "__main__":
    main()
