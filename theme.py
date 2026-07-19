"""Design-токены FlowLocal - порт дизайн-системы Korti.

Единственный источник правды по внешнему виду. Оверлей, иконка трея и окно
настроек берут значения отсюда, поэтому «сменить акцент» - это одна строка.

Система стоит на одном жёстком правиле: цветов ровно два - бумага и чернила.
Все «серые» - это чернила поверх бумаги с какой-то прозрачностью, отдельных
серых токенов нет. Ещё три цвета: зелёный и красный только для статуса, синий
акцент - только для «особенного» (фокус, ссылки, выделение). Больше оттенков
не заводить.

Отсюда и обе темы почти даром: тёмная - это та же система с переставленными
красками, а не второй набор токенов. Переключает set_theme(), пересчитывая
производные; виджеты берут T.BG в момент отрисовки, поэтому подхватывают сами.

Соответствие Korti -> сюда:
  --ink-rgb / --paper-rgb-> INK / PAPER (их и меняет тема)
  --bg, --surface        -> PAPER
  --text-primary/64/46   -> TEXT / TEXT_SECONDARY / TEXT_MUTED
  --border, --fill*      -> ink(0.13), ink(0.04/0.06/0.10)
  --dur-fast/--dur/--slow-> T_FAST / T_DUR / T_SLOW
  --ease-out             -> ease_out (тот же cubic-bezier, посчитанный честно)

Осознанные отступления от Korti (оба вынужденные, оба видны глазом):
  * Интерфейсный шрифт - Onest вместо Hanken Grotesk: в фирменном нет
    кириллицы, см. блок «типографика» ниже.
  * Точка записи зелёная, а не красная: в Korti зелёный - это «успех/в
    эфире», а красный - «ошибка». Мигать красным во время нормальной
    диктовки значило бы врать пользователю.
"""

import ctypes
import functools
import os
import sys

from PIL import ImageFont


def _assets_dir() -> str:
    """Где лежат шрифты.

    В собранном .exe их распаковывает PyInstaller во временную папку
    (sys._MEIPASS) - туда же, куда и код. Рядом с самим .exe их нет, поэтому
    от app_paths.APP_DIR тут отталкиваться нельзя: он намеренно указывает на
    папку .exe, где живут конфиг и история.
    """
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", "fonts")


ASSETS = _assets_dir()

# ---------- две краски ----------
# Korti светлая по умолчанию: --ink-rgb: 0 0 0, --paper-rgb: 255 255 255.
# Тёмная - ровно та же система с переставленными каналами. Больше тема не
# меняет ничего, кроме трёх сигнальных цветов: на чёрном они подняты, иначе
# не хватает контраста.
#
# Значения заполняет _apply() из _PALETTE - смотри set_theme() ниже. Здесь
# они объявлены, чтобы модуль читался сверху вниз, а не собирался в голове.

INK = PAPER = (0, 0, 0)

_PALETTE = {
    "light": {
        "ink": (0, 0, 0),
        "paper": (255, 255, 255),
        "accent": (37, 99, 235),         # --blue-500
        "accent_hover": (29, 81, 199),   # --accent-hover
        "accent_fg": (255, 255, 255),
        "success": (18, 168, 95),        # --green-500
        "danger": (224, 31, 43),         # --red-500
    },
    "dark": {
        # Не чистый чёрный, и это не отступление от системы, а её же правило,
        # применённое честно. Korti строит тему из двух красок, но «бумага» -
        # это поверхность, а не отсутствие света: на светлой теме она белая и
        # даёт всему остальному, на чём лежать. Чистый (0,0,0) такой опоры не
        # даёт - карточка, фон и тень сливаются в одно поле, и владелец,
        # пройдя мастер вслух, сказал ровно это: «ничего не видно, всё как-то
        # странно». Двадцать единиц серого возвращают поверхность, оставаясь
        # чёрным для глаза.
        "ink": (255, 255, 255),
        "paper": (20, 20, 20),
        "accent": (110, 155, 255),       # --blue-400
        "accent_hover": (143, 180, 255),
        "accent_fg": (11, 18, 32),
        "success": (52, 208, 125),       # --green-400
        "danger": (255, 90, 97),         # --red-400
        # Своя лестница прозрачностей. Одна на обе темы не работает, и это
        # видно не на глаз, а по замеру: подпись flat(0.32) на белом даёт
        # контраст 5.7:1, на чёрном - 2.6:1. Того же серого на тёмном фоне
        # просто не хватает, потому что глаз меряет разницу, а её меньше.
        #
        # Сильнее всего страдал не текст, а `fill_strong`: на нём стоит
        # дорожка выключенного переключателя. Десять процентов белого на почти
        # чёрном - это ничто, поэтому «не видно, что он переключился» было
        # чистой правдой, а не придиркой.
        "alpha": {
            "text_secondary": 0.74,
            "text_muted": 0.60,
            "text_faint": 0.44,
            "border": 0.20,
            "border_strong": 0.34,
            "fill_subtle": 0.06,
            "fill": 0.10,
            "fill_strong": 0.20,
        },
    },
}

# Лестница светлой темы. Тёмная переопределяет её ключом "alpha".
#
# Три значения подняты против канона Korti, и вот почему. Тёмную тему чинили
# по жалобе владельца, а чинить взялись замером (test_theme.py) - и замер тут
# же показал, что на СВЕТЛОЙ теме дела были хуже: подпись под строкой давала
# 3.45:1 при норме 4.5:1, самый тихий текст - 2.24:1 при 3.0:1. Жалобы не было
# только потому, что чёрное на белом кажется читаемым и тогда, когда уже нет.
#
# Это тот случай, когда «сверяться с системой, а не рисовать на глаз»
# уступает правилу «замер сильнее мнения»: канон здесь не измерял контраст, а
# мы измерили. Расхождение с Korti осознанное и одно - три прозрачности.
_ALPHA = {
    "text_secondary": 0.64,   # канон, 6.69:1 - проходит
    "text_muted": 0.58,       # было 0.46 -> 3.45:1
    "text_faint": 0.45,       # было 0.32 -> 2.24:1
    "border": 0.13,
    "border_strong": 0.24,
    "fill_subtle": 0.04,
    "fill": 0.06,
    "fill_strong": 0.14,      # было 0.10: дорожка выключенного переключателя
}

_mode = "dark"


def hx(c) -> str:
    """RGB(A) -> '#rrggbb' для tkinter (альфа отбрасывается)."""
    return "#%02x%02x%02x" % (c[0], c[1], c[2])


def rgba(c, alpha: float):
    """Цвет с заданной непрозрачностью 0..1."""
    a = int(max(0.0, min(1.0, alpha)) * 255)
    return (c[0], c[1], c[2], a)


def mix(a, b, t: float):
    """Линейная интерполяция цвета (по RGB, альфа берётся из a/b если есть)."""
    t = max(0.0, min(1.0, t))
    out = tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))
    if len(a) > 3 and len(b) > 3:
        out += (int(round(a[3] + (b[3] - a[3]) * t)),)
    return out


def ink(alpha: float):
    """Чернила с прозрачностью - RGBA для наложения поверх чего угодно."""
    return (*INK, round(max(0.0, min(1.0, alpha)) * 255))


def paper(alpha: float = 1.0):
    return (*PAPER, round(max(0.0, min(1.0, alpha)) * 255))


def flat(alpha: float):
    """Тот же «серый», но уже сплавленный с бумагой в непрозрачный RGB.

    Нужен там, где альфы не бывает: tkinter принимает только '#rrggbb'.
    """
    return mix(PAPER, INK, alpha)


# ---------- семантика ----------
# Тень: только чёрная, никогда цветная, и в светлой теме тоже - это тот же
# --shadow-lg из системы, а не «чернила снизу». Поэтому она вне _apply().
SHADOW_NEAR = (0, 0, 0, 15)   # 0 4px 8px rgb(0 0 0 / .06)
SHADOW_FAR = (0, 0, 0, 31)    # 0 16px 40px rgb(0 0 0 / .12)


def _apply(p: dict) -> None:
    """Пересчитать всю палитру из двух красок. Порядок важен: flat()/ink()
    читают INK и PAPER, поэтому сперва краски, потом производные."""
    global INK, PAPER, BG, SURFACE, SURFACE_SUNKEN
    global TEXT, TEXT_SECONDARY, TEXT_MUTED, TEXT_FAINT, TEXT_INVERSE
    global BORDER, BORDER_STRONG, FILL_SUBTLE, FILL, FILL_STRONG
    global BORDER_FLAT, BORDER_STRONG_FLAT, FILL_SUBTLE_FLAT, FILL_FLAT, FILL_STRONG_FLAT
    global PRIMARY, PRIMARY_FG, ACCENT, ACCENT_HOVER, ACCENT_FG, SUCCESS, DANGER

    INK, PAPER = p["ink"], p["paper"]
    # Лестница прозрачностей: своя у темы, если задана, иначе канон.
    a = dict(_ALPHA)
    a.update(p.get("alpha") or {})

    BG = PAPER                    # --bg
    SURFACE = PAPER               # --surface: карточки живут на фоне страницы,
                                  # их отделяет линия, а не заливка
    SURFACE_SUNKEN = flat(0.03)   # --surface-sunken

    TEXT = INK                    # --text-primary
    TEXT_SECONDARY = flat(a["text_secondary"])
    TEXT_MUTED = flat(a["text_muted"])
    TEXT_FAINT = flat(a["text_faint"])
    TEXT_INVERSE = PAPER          # --text-inverse

    BORDER = ink(a["border"])            # RGBA: кладём поверх
    BORDER_STRONG = ink(a["border_strong"])
    FILL_SUBTLE = ink(a["fill_subtle"])
    FILL = ink(a["fill"])
    FILL_STRONG = ink(a["fill_strong"])

    # сплавленные варианты тех же токенов - для tkinter
    BORDER_FLAT = flat(a["border"])
    BORDER_STRONG_FLAT = flat(a["border_strong"])
    FILL_SUBTLE_FLAT = flat(a["fill_subtle"])
    FILL_FLAT = flat(a["fill"])
    FILL_STRONG_FLAT = flat(a["fill_strong"])

    PRIMARY = INK                 # --primary: главное действие - это чернила
    PRIMARY_FG = PAPER            # --primary-fg

    ACCENT = p["accent"]          # акцент, НЕ статус
    ACCENT_HOVER = p["accent_hover"]
    ACCENT_FG = p["accent_fg"]
    SUCCESS = p["success"]        # успех / «в эфире»
    DANGER = p["danger"]          # ошибка / разрушительное


_layout = "cards"


def layout() -> str:
    """Как расположены вещи: cards | lines. Один источник правды, как и краски."""
    return _layout


def set_layout(value: str) -> None:
    global _layout
    _layout = value if value in ("cards", "lines") else "cards"


def mode() -> str:
    """Действующая тема: 'light' или 'dark'. Никогда не 'system'."""
    return _mode


def system_theme() -> str:
    """Что выбрано в оформлении Windows. Не спросить нельзя: «системная» -
    умолчание, а Windows про свою тему рассказывает только через реестр."""
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as k:
            light, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
        return "light" if light else "dark"
    except OSError:      # ключа нет (старая сборка) - у нас всегда была тёмная
        return "dark"


def resolve(name: str) -> str:
    """'system' | 'light' | 'dark' -> 'light' | 'dark'."""
    return name if name in ("light", "dark") else system_theme()


def set_theme(name: str) -> str:
    """Переключить тему. Возвращает применённую ('light' или 'dark').

    Работает на живом приложении, потому что виджеты читают T.BG в момент
    отрисовки, а не при создании. Но всё, что закэшировано картинкой, надо
    сбросить руками: оверлей - Overlay.retheme(), трей - icons.retheme(),
    окно настроек пересобрать целиком (оно и так пересобирается при открытии).
    """
    global _mode
    _mode = resolve(name)
    _apply(_PALETTE[_mode])
    return _mode


_apply(_PALETTE[_mode])

# ---------- метрика ----------
# Шаг сетки 4px, плотность - «воздушно».

SPACE = 4

RADIUS_XS = 4
RADIUS_SM = 6                 # кнопки, поля, квадратные бейджи - дефолт
RADIUS_MD = 8                 # карточки, меню
RADIUS_LG = 12                # крупные карточки, панели
RADIUS_XL = 16                # модалки
RADIUS_FULL = 999             # пилюли, точки, аватары

# Пилюля. Уменьшена 18.07.2026 по замечанию владельца: «слишком большая,
# слишком много текста». Ориентир - Flow Bar у Wispr: компактная капсула у края
# экрана, внутри волна и ничего лишнего. Было 44 высоты и 188 волны.
PILL_H = 34                   # высота пилюли-оверлея
# Ширина ОКНА пилюли - постоянная, сама капсула центрируется внутри него.
# Раньше окно подгонялось под капсулу, а x ставился один раз при показе: от
# смены состояния капсула меняла ширину, окно росло вправо, и пилюля уезжала
# из центра экрана. Постоянная ширина эту болезнь снимает целиком.
PILL_W_MAX = 320
# Поле вокруг пилюли под тень. Снизу больше: тень смещена вниз, поэтому
# симметричное поле обрезало бы её хвост - на светлом фоне это давало заметный
# горизонтальный шов (замерено: 12/255 альфы на нижней строке холста).
PILL_PAD = 24
PILL_PAD_BOTTOM = 44
PILL_BOTTOM = 92              # отступ пилюли от низа экрана
WAVE_W = 116                  # ширина осциллограммы
WAVE_H = 14
WAVE_BARS = 24                # 24 полоски x 32 мс = окно ~0.8 с
LEVEL_MS = 32                 # шаг замера громкости; он же шаг прокрутки волны

SS = 3                        # суперсэмплинг: PIL не сглаживает фигуры,
                              # поэтому рисуем в SS раз крупнее и ужимаем

# ---------- типографика ----------
# JetBrains Mono - код, метаданные, метки: ровно как в Korti.
#
# А вот с интерфейсным шрифтом система разошлась с реальностью. Korti требует
# Hanken Grotesk, но в нём НЕТ кириллицы (проверено по таблице cmap: U+0420
# отсутствует) - весь русский интерфейс превращался в ряды ▯▯▯. Сам токен
# --font-sans это предвидит и объявляет цепочку подмены до Segoe UI, но Segoe
# UI - гуманистический шрифт другого характера, да ещё и без веса 800, которым
# в Korti набран вордмарк.
#
# Поэтому взят Onest: та же геометрия, круглость и высота строчных, что у
# Hanken Grotesk (сравнивали начертания бок о бок), но с кириллицей и полной
# осью весов 100-900. Из кандидатов Manrope оказался уже и характернее, Golos
# Text - более узким и квадратным.
#
# Оба шрифта лежат в assets/fonts (OFL): в системе их нет, а на CDN настольному
# приложению рассчитывать нечего - оно должно рисовать себя без сети.

FONT_SANS = os.path.join(ASSETS, "Onest-Variable.ttf")
FONT_MONO = os.path.join(ASSETS, "JetBrainsMono-Variable.ttf")

W_REGULAR = 400
W_MEDIUM = 500
W_SEMIBOLD = 600
W_BOLD = 700
W_BLACK = 800

# размеры (px) - шкала Korti
T_2XS, T_XS, T_SM, T_BASE, T_MD, T_LG, T_XL, T_2XL, T_3XL = 11, 12, 13, 14, 15, 17, 20, 24, 30

# Имена семейств, как их видит Windows после приватной регистрации:
# GDI показывает каждый именованный инстанс вариативного шрифта отдельным
# семейством, поэтому вес в tkinter выбирается именем, а не weight=.
TK_SANS = "Onest"
TK_SANS_MEDIUM = "Onest Medium"
TK_SANS_SEMIBOLD = "Onest SemiBold"
TK_MONO = "JetBrains Mono"

_registered = False


def register_fonts() -> bool:
    """Отдать шрифты Windows только для этого процесса (FR_PRIVATE).

    Без этого tkinter их не видит: он берёт шрифты по имени семейства из
    системы, а ставить что-то в систему ради запуска приложения - хамство.
    Звать ДО создания tk.Tk(): Tk спрашивает список семейств у GDI.
    """
    global _registered
    if _registered:
        return True
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    gdi32.AddFontResourceExW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
    gdi32.AddFontResourceExW.restype = ctypes.c_int
    added = 0
    for path in (FONT_SANS, FONT_MONO):
        if os.path.exists(path):
            added += gdi32.AddFontResourceExW(path, 0x10, None)  # FR_PRIVATE
    _registered = added > 0
    return _registered


register_fonts()


@functools.lru_cache(maxsize=128)
def font(size: int, weight: int = W_REGULAR, mono: bool = False) -> ImageFont.FreeTypeFont:
    """Шрифт нужного кегля и веса для PIL.

    Кегль передавайте уже умноженным на SS, если рисуете в суперсэмпле.
    Вес берётся с оси вариативного шрифта - отсюда честные 500/600, а не
    синтетический жир. lru_cache отдаёт на каждый (size, weight) свой объект:
    set_variation_by_axes меняет шрифт на месте, и общий объект утёк бы весом.
    """
    path = FONT_MONO if mono else FONT_SANS
    try:
        f = ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()
    try:
        f.set_variation_by_axes([weight])
    except (OSError, AttributeError):
        pass
    return f


# ---------- движение ----------
# Korti: быстро и чётко. 120/180/280 мс, --ease-out, только фейды и
# небольшие сдвиги. Никакого пружинения - ease_out_back тут вне закона.

T_FAST = 0.12                 # --dur-fast
T_DUR = 0.18                  # --dur
T_SLOW = 0.28                 # --dur-slow

T_SHOW = T_DUR                # всплытие пилюли
T_HIDE = T_FAST
T_MORPH = T_DUR               # смена состояния: ширина + кросс-фейд
T_DONE_HOLD = 0.65            # сколько «готово» висит перед уходом
RISE = 8                      # translateY на входе, как у Toast
FPS = 60


def _bezier(x1: float, y1: float, x2: float, y2: float):
    """CSS cubic-bezier(x1,y1,x2,y2) -> функция t->прогресс.

    Считаем как браузер: по x ищем параметр кривой Ньютоном, из него берём y.
    Приближать это «похожей» формулой смысла нет - кривая в токенах задана
    точно, и на глаз разница в тайминге видна.
    """
    def bez(a, b, t):
        return 3 * (1 - t) ** 2 * t * a + 3 * (1 - t) * t ** 2 * b + t ** 3

    def dbez(a, b, t):
        return (3 * (1 - t) ** 2 * a + 6 * (1 - t) * t * (b - a)
                + 3 * t ** 2 * (1 - b))

    def ease(t: float) -> float:
        t = max(0.0, min(1.0, t))
        if t in (0.0, 1.0):
            return t
        u = t
        for _ in range(8):
            x = bez(x1, x2, u) - t
            if abs(x) < 1e-6:
                break
            d = dbez(x1, x2, u)
            if abs(d) < 1e-6:
                break
            u -= x / d
        return bez(y1, y2, max(0.0, min(1.0, u)))

    return ease


ease_out = _bezier(0.2, 0.8, 0.2, 1)       # --ease-out
ease_in_out = _bezier(0.4, 0, 0.2, 1)      # --ease-in-out
ease_in = _bezier(0.4, 0, 1, 1)            # --ease-in


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
