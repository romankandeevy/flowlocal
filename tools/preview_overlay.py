"""Контактный лист пилюли-оверлея: все состояния, обе темы, обе подложки.

Оверлей рисуется в PIL и уходит в layered-окно поверх экрана. Снимать его с
экрана нечестно: кадр тогда зависит от того, что сейчас на рабочем столе.
Окна тут поэтому нет вообще - кадр собирается из тех же двух кусков, из
которых его собирает Overlay._frame: «хром» (капсула с тенью, _chrome) плюс
«контент» (точка, волна, спиннер, галка - _content). Микрофон, модель и GPU
не нужны: уровни громкости синтетические.

Каждое состояние снимается на светлой и на тёмной плашке, и так для обеих тем
приложения. Пилюля всплывает над чужим окном - тень --shadow-lg и волосяная
линия обязаны читаться на любом фоне (на светлом тут уже ловили горизонтальный
шов от обрезанного хвоста тени, см. HANDOFF.md).

    python tools/preview_overlay.py     ->  tools/preview_overlay.png
"""

import math
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)                     # как app.py: приложение живёт от своего корня

from PIL import Image, ImageDraw  # noqa: E402

import layered  # noqa: E402

# До создания любого окна - как в app.py. Своих окон мы не создаём, но от этого
# зависит масштаб, который вернёт active_monitor(): без DPI-awareness Windows
# соврёт про 96 dpi, и на мониторе со 150% пилюля выйдет не того размера.
layered.set_dpi_awareness()

import overlay as OV  # noqa: E402
import theme as T  # noqa: E402

OUT = os.path.join(ROOT, "tools", "preview_overlay.png")

# Плашки под кадры - это не токены системы, а «чужое окно, куда диктуют»:
# белый редактор и тёмная IDE. Белый взят чистый: на нём хвост тени видно
# лучше всего, и шов, если он вернётся, вылезет именно там.
PLATES = (("на светлом", (255, 255, 255)), ("на тёмном", (16, 16, 16)))
THEMES = (("light", "светлая"), ("dark", "тёмная"))

HINT = "ещё раз - стоп"            # ровно то, что ставит app.py в режиме toggle
SEED = 20260715                    # превью должно быть одинаковым от запуска к запуску


class _Root:
    """Заглушка вместо tk-root.

    Overlay планирует перерисовку через root.after, а мы рисуем кадры сами и
    по своим часам - таймеры заводить нельзя, иначе «готово» успеет спрятаться
    прямо посреди съёмки. tkinter здесь не нужен вовсе: оверлей - чистый PIL.
    """

    def after(self, _ms, _fn=None, *_args):
        return None

    def after_cancel(self, _job):
        pass


class _Levels:
    """Синтетический микрофон: отдаёт RMS-уровни, как recorder.drain_levels().

    Отдаёт их НЕ на каждый вызов, и это здесь главное. Настоящие уровни
    приходят раз в T.LEVEL_MS (~31/с), а кадров 60/с - на большинстве кадров
    новых данных нет, и оверлей обязан это переживать. Генератор, который
    сыпал уровень на каждый вызов, ровно этим и спрятал баг: на живом
    микрофоне осциллограмма схлопывалась в ниточку, а превью показывало
    красивую волну (HANDOFF.md, «Звук / оверлей»).

    Часы синтетические: их двигает тот, кто просит кадр, - см. _shoot().
    """

    def __init__(self):
        self.now = 0.0
        self._next: float | None = None   # первый вызов задаст точку отсчёта
        self._t = 0.0
        self._rnd = random.Random(SEED)

    def __call__(self) -> list[float]:
        if self._next is None:
            self._next = self.now
        step = T.LEVEL_MS / 1000.0
        out = []
        while self.now >= self._next:
            out.append(self._rms(self._t))
            self._t += step
            self._next += step
        return out

    def _rms(self, t: float) -> float:
        """Речь - это не синус: слоги идут пачками, между фразами провалы.
        Медленная огибающая (фраза) на быстрой (слоги) плюс разброс. Числа -
        из замеров на живой машине: речь в микрофон даёт rms 0.05-0.2, тихая
        комната ~0.0004."""
        phrase = 0.5 + 0.5 * math.sin(2 * math.pi * 0.6 * t)
        syllables = 0.5 + 0.5 * math.sin(2 * math.pi * 4.7 * t + 1.2)
        loud = 0.05 + 0.15 * phrase ** 1.5 * (0.3 + 0.7 * syllables)
        return max(0.0004, loud * (0.7 + 0.6 * self._rnd.random()))


def _states():
    """Что снимаем: подпись, чем это включается, подсказка, сколько крутить.

    Порядок - жизненный цикл диктовки. Подписи у DONE и ERROR настоящие, из
    app.py: по ним видно реальную ширину пилюли, а не выдуманную. Секунды
    нужны только записи (волне надо натечь на все WAVE_BARS полосок) и
    спиннеру - остальные состояния статичны с первого же кадра.
    """
    return (
        ("loading", lambda ov: ov.show_loading(), "", 0.5),
        ("recording", lambda ov: ov.show_recording(), "", 2.0),
        ("recording + подсказка", lambda ov: ov.show_recording(), HINT, 2.0),
        ("processing", lambda ov: ov.show_processing(), "", 0.5),
        ("done", lambda ov: ov.show_done("7 слов"), "", 0.4),
        ("error", lambda ov: ov.show_error("не удалось вставить"), "", 0.4),
    )


def _shoot(ov, enter, hint: str, dur: float) -> Image.Image:
    """Прогнать состояние по кадрам и собрать последний кадр целиком.

    Кадры считаются по синтетическим часам, но от настоящих: Overlay ставит
    отсчёт записи по time.perf_counter() у себя внутри, и «now» из другой
    эпохи он принял бы за прошлое - таймер показал бы чушь.

    Крутить все dur секунд нужно ради волны: _content на каждом кадре качает
    уровни через _pump_bars, и полоски набегают только со временем. Склеиваем
    же только последний кадр - кросс-фейда между состояниями на превью не
    надо, там нужна пилюля, а не середина перехода.
    """
    levels = _Levels()
    ov.level_fn = levels
    ov.set_hint(hint)              # до enter(): в app.py hint ставится первым
    enter(ov)
    w = ov._width(ov._state)       # ширина состояния постоянна, пока оно одно
    t0 = time.perf_counter()
    content = None
    for i in range(max(1, round(dur * T.FPS))):
        levels.now = now = t0 + i / T.FPS
        content = ov._content(ov._state, w, now)
    img = ov._chrome(w).copy()
    img.alpha_composite(content)
    return img


def _frames() -> dict:
    """{тема: [(подпись, кадр)]}.

    Overlay один на обе темы - ровно как в приложении: тему там переключают на
    живом оверлее. Поэтому и retheme(): капсула с тенью кэшируется картинкой,
    а картинка про смену палитры не знает.
    """
    ov = OV.Overlay(_Root())
    out = {}
    for name, _title in THEMES:
        T.set_theme(name)
        ov.retheme()
        out[name] = [(label, _shoot(ov, enter, hint, dur))
                     for label, enter, hint, dur in _states()]
    ov.destroy()
    return out


def _sheet(by_theme: dict) -> Image.Image:
    """Собрать лист: состояния сверху вниз, тема x плашка - слева направо."""
    scale = layered.active_monitor()[1]

    def px(v: float) -> int:
        return max(1, round(v * scale))

    head_f = T.font(px(T.T_MD), T.W_SEMIBOLD)
    lab_f = T.font(px(T.T_XS), T.W_MEDIUM, mono=True)
    pad, head_h, lab_h = px(18), px(44), px(22)

    cols = [(f"тема {ttl} · {ptitle}", name, bg)
            for name, ttl in THEMES for ptitle, bg in PLATES]
    frames = [f for fr in by_theme.values() for f in fr]
    fw = max(img.width for _l, img in frames)
    fh = max(img.height for _l, img in frames)
    col_w = fw + 2 * pad
    col_h = head_h + max(len(fr) for fr in by_theme.values()) * (lab_h + fh)

    sheet = Image.new("RGB", (col_w * len(cols), col_h))
    for i, (title, name, bg) in enumerate(cols):
        plate = Image.new("RGBA", (col_w, col_h), (*bg, 255))
        # подписи - чернилами этой плашки, а не темы: лист читают глазами,
        # а не через токены
        pen = (0, 0, 0) if sum(bg) > 3 * 128 else (255, 255, 255)
        d = ImageDraw.Draw(plate)
        d.text((pad, head_h / 2), title, font=head_f, fill=(*pen, 255), anchor="lm")
        y = head_h
        for label, img in by_theme[name]:
            d.text((pad, y + lab_h / 2), label, font=lab_f, fill=(*pen, 160), anchor="lm")
            plate.alpha_composite(img, ((col_w - img.width) // 2, y + lab_h))
            y += lab_h + fh
        sheet.paste(plate.convert("RGB"), (i * col_w, 0))
    return sheet


def main() -> None:
    _sheet(_frames()).save(OUT, optimize=True)
    print(OUT)


if __name__ == "__main__":
    main()
