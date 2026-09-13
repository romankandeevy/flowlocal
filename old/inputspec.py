"""Разбор и показ «сочетания»: клавиши и кнопки мыши в одной строке.

Один источник правды на всех, кто трогает хоткеи: приложение (app.py) вешает по
ним хуки, поле захвата (widgets.HotkeyBox) их собирает и показывает. Раньше
таблицы модификаторов лежали в двух местах и разъезжались - именно так и
случился баг, когда keyboard отдавал общее имя «ctrl», поле его не узнавало и
фиксировало сочетание на первой же клавише.

Формат строки - то, что лежит в config.json:

    "ctrl+shift+space"    клавиатура
    "ctrl+mouse4"         модификатор + боковая кнопка мыши
    "mouse5"              просто боковая кнопка
    ""                    ничего не назначено

Кнопки мыши по игровому счёту: mouse3 - колесо-кнопка, mouse4 и mouse5 -
боковые. Левую и правую не поддерживаем намеренно: диктовка на ЛКМ сделала бы
мышь неработоспособной, а отменить настройку было бы уже нечем.
"""

# keyboard называет модификатор то стороной («left ctrl»), то общим именем
# («ctrl») - в его all_modifiers есть оба вида. Принимаем любой.
_MOD_ALIASES = {
    "ctrl": "ctrl", "control": "ctrl", "left ctrl": "ctrl", "right ctrl": "ctrl",
    "shift": "shift", "left shift": "shift", "right shift": "shift",
    "alt": "alt", "alt gr": "alt", "left alt": "alt", "right alt": "alt",
    "win": "win", "windows": "win", "left windows": "win", "right windows": "win",
}

# Слева - наш токен в конфиге, справа - имя кнопки в библиотеке mouse.
TOKEN_TO_MOUSE = {"mouse3": "middle", "mouse4": "x", "mouse5": "x2"}
MOUSE_TO_TOKEN = {v: k for k, v in TOKEN_TO_MOUSE.items()}

# Порядок модификаторов в строке. Нужен, чтобы «shift+ctrl+space» и
# «ctrl+shift+space» были одним и тем же сочетанием, а не двумя разными.
_ORDER = {"ctrl": 0, "shift": 1, "alt": 2, "win": 3}

# Раскладка имён для показа человеку.
_MOD_LABELS = {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "win": "Win"}
_MOUSE_LABELS = {"middle": "Колесо", "x": "Мышь 4", "x2": "Мышь 5"}
_KEY_LABELS = {
    "space": "Space", "esc": "Esc", "enter": "Enter", "tab": "Tab",
    "caps lock": "Caps Lock", "backspace": "Backspace", "delete": "Delete",
    "page up": "Page Up", "page down": "Page Down",
    "right ctrl": "Right Ctrl", "left ctrl": "Left Ctrl",
    "right alt": "Right Alt", "right shift": "Right Shift",
}


def is_modifier(name: str) -> bool:
    """Имя клавиши - это модификатор? Принимает и «ctrl», и «left ctrl»."""
    return (name or "").lower() in _MOD_ALIASES


def canon_modifier(name: str) -> str | None:
    """«left ctrl» -> «ctrl». None, если это не модификатор."""
    return _MOD_ALIASES.get((name or "").lower())


def parse(spec: str) -> tuple[list[str], str | None, str | None]:
    """«ctrl+mouse4» -> (['ctrl'], None, 'x').

    Возвращает (модификаторы, клавиша, кнопка мыши). Клавиша и кнопка мыши
    взаимоисключающи: последняя названная выигрывает. Модификаторы всегда
    отсортированы - см. _ORDER.
    """
    mods: list[str] = []
    key: str | None = None
    mouse: str | None = None
    for part in (spec or "").split("+"):
        p = part.strip().lower()
        if not p:
            continue
        canon = _MOD_ALIASES.get(p)
        if canon:
            if canon not in mods:
                mods.append(canon)
        elif p in TOKEN_TO_MOUSE:
            mouse, key = TOKEN_TO_MOUSE[p], None
        else:
            key, mouse = p, None
    mods.sort(key=lambda m: _ORDER.get(m, 9))
    return mods, key, mouse


def build(mods, key: str | None = None, mouse: str | None = None) -> str:
    """Собрать строку обратно. mouse - имя кнопки из библиотеки mouse."""
    ordered = sorted({m for m in mods if m in _ORDER}, key=lambda m: _ORDER[m])
    tail = MOUSE_TO_TOKEN.get(mouse) if mouse else key
    return "+".join(ordered + ([tail] if tail else []))


def normalize(spec: str) -> str:
    """Привести к каноническому виду: «shift+ctrl+SPACE» -> «ctrl+shift+space»."""
    mods, key, mouse = parse(spec)
    return build(mods, key, mouse)


def is_mouse(spec: str) -> bool:
    return parse(spec)[2] is not None


def is_valid(spec: str) -> bool:
    """Есть ли что вешать: одни модификаторы сочетанием не считаются.

    Исключение - одиночный модификатор без всего («right ctrl» как хоткей):
    его parse() кладёт в mods, и клавиши там нет. Такое разрешаем.
    """
    mods, key, mouse = parse(spec)
    return bool(key or mouse or mods)


def pretty(spec: str) -> str:
    """Человеческое имя для поля настроек."""
    if not spec:
        return "не задано"
    mods, key, mouse = parse(spec)
    labels = [_MOD_LABELS[m] for m in mods]
    if mouse:
        labels.append(_MOUSE_LABELS.get(mouse, mouse))
    elif key:
        labels.append(_KEY_LABELS.get(key, key.title()))
    return " + ".join(labels) if labels else "не задано"
