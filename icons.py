"""Иконка микрофона для трея и окна настроек.

В трее иконка живёт в 16-20 пикселях, поэтому глиф нарочно толстый и без
мелочей: тонкие детали на таком размере превращаются в грязь. Рисуем в
суперсэмпле и ужимаем BOX-фильтром - PIL не сглаживает фигуры сам, а
несглаженный микрофон в трее выглядит как поделка.
"""

import functools

from PIL import Image, ImageDraw

import theme as T

_SS = 4
_G = 64.0   # опорная сетка глифа


def state_color(state: str):
    """Цвет состояния по сигналам Korti: зелёный - «в эфире», синий акцент -
    «думаю», красный остаётся за ошибками.

    Покой - нейтральный серый, а не чернила: иконка живёт на панели задач, а та
    бывает и светлой, и тёмной. Единственный цвет, читаемый на обеих, - средний.
    Это единственное место, где система «двух красок» неприменима: фон не наш.
    Поэтому же серый не меняется вместе с темой приложения - тема панели задач
    своя собственная.
    """
    return {
        "idle": (144, 144, 150),
        "rec": T.SUCCESS,
        "proc": T.ACCENT,
        "load": (100, 100, 106),
    }.get(state, (144, 144, 150))


def mic(state: str = "idle", size: int = 64) -> Image.Image:
    """RGBA-иконка микрофона size x size."""
    # Тема в ключе кэша не для красоты: rec/proc красятся сигнальными цветами,
    # а они у светлой и тёмной темы разные. Без неё после переключения трей
    # отдавал бы иконку от прошлой палитры.
    return _mic(state, size, T.mode())


def retheme() -> None:
    """Тема сменилась - забыть нарисованное в старых красках."""
    _mic.cache_clear()


@functools.lru_cache(maxsize=32)
def _mic(state: str, size: int, _mode: str) -> Image.Image:
    color = state_color(state)
    n = size * _SS
    k = n / _G                       # масштаб опорной сетки в пиксели картинки
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fill = color + (255,)

    def s(*v):
        return [x * k for x in v]

    # Пропорции сняты с классического «микрофона» и растянуты почти на всю
    # клетку: в трее каждый пиксель на счету, скромный глиф читается как мусор.
    d.rounded_rectangle(s(22, 5, 42, 41), radius=10 * k, fill=fill)   # капсула
    d.arc(s(12, 19, 52, 55), 0, 180, fill=fill, width=round(5 * k))   # 0..180 = низ эллипса
    d.rounded_rectangle(s(29.5, 52, 34.5, 60), radius=2.5 * k, fill=fill)  # ножка

    return img.resize((size, size), Image.Resampling.BOX)


def tk_icon(size: int = 64):
    """PhotoImage для окна настроек (wm_iconphoto). Держите ссылку живой -
    tkinter не считает её за владение, картинка исчезнет при сборке мусора."""
    from PIL import ImageTk

    return ImageTk.PhotoImage(mic("idle", size))
