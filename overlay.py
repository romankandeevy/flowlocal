"""Пилюля-индикатор над всеми окнами: загрузка / запись / распознавание / готово.

Оформление - дизайн-система Korti, рецепт её же Toast: поверхность цвета
бумаги, отделённая волосяной линией, тень --shadow-lg в два слоя, вход
«прозрачность 0->1 + сдвиг на 8px вверх» за 180 мс на --ease-out. Никакого
пружинения и масштабирования: система разрешает только фейды и небольшие
сдвиги.

Цвета статусов - по Korti: зелёный это «успех/в эфире», поэтому точка записи
зелёная, а не красная (красный там означает ошибку, и мигать им во время
нормальной диктовки - врать пользователю). Осциллограмма - чернила: данные
не статус, тонировать их нечем.

Рисуется целиком в PIL и отдаётся в layered-окно с попиксельной альфой -
отсюда сглаженные углы, мягкая тень и честная прозрачность на любом фоне.

Как это работает по кадрам (60 fps, тик из tkinter):
  «хром» (капсула + тень)  - режется из закэшированной базы по три куска
                             (левая шапка / тянущаяся середина / правая),
                             поэтому смена ширины при переходе состояний
                             не стоит ничего: размывать тень каждый кадр
                             было бы десятки мс, а так ~0.3 мс;
  «контент» (точка, волна, спиннер, галка) - рисуется в суперсэмпле x3 и
                             ужимается BOX-фильтром: PIL не сглаживает
                             фигуры сам, а текст, наоборот, рисуется в
                             натуральную величину - он и так сглажен, а
                             в суперсэмпле мылится.

Все методы звать только из потока tkinter (в app.py - через очередь UI).
"""

import math
import time

from PIL import Image, ImageDraw, ImageFilter

import theme as T
from layered import LayeredWindow, active_monitor

LOADING = "loading"
RECORDING = "recording"
PROCESSING = "processing"
DONE = "done"
ERROR = "error"

# --shadow-lg: 0 4px 8px rgb(0 0 0/.06), 0 16px 40px rgb(0 0 0/.12).
# CSS-радиус размытия r - это примерно гаусс с сигмой r/2.
_SHADOWS = ((4, 4, T.SHADOW_NEAR), (16, 20, T.SHADOW_FAR))   # (dy, sigma, color)
_SHADOW_REACH = 16 + 30       # дальше тень в 12% уже неразличима
_BOX = Image.Resampling.BOX

# Пол громкости для осциллограммы: RMS тише этого считается тишиной.
# Замерено на этой машине: тихая комната ~0.0004, речь в микрофон ~0.05-0.2,
# еле слышный источник ~0.005. 0.006 оставляет тишину ровной ниточкой (~15%
# высоты), но уже показывает тихий источник во весь размах.
_FLOOR = 0.006


class _Geom:
    """Метрика, пересчитанная под масштаб конкретного монитора."""

    def __init__(self, scale: float):
        self.s = scale
        self.pill_h = round(T.PILL_H * scale)
        self.r = self.pill_h // 2          # --radius-full: пилюля есть пилюля
        self.pad = round(T.PILL_PAD * scale)              # слева/справа/сверху
        self.pad_b = round(T.PILL_PAD_BOTTOM * scale)     # снизу - под хвост тени
        self.dy = [round(dy * scale) for dy, _s, _c in _SHADOWS]
        self.sigma = [s * scale for _dy, s, _c in _SHADOWS]
        self.cap = self.pad + self.r + round(3 * max(self.sigma)) + 2
        self.base_w = 2 * self.cap + 2
        self.canvas_h = self.pill_h + self.pad + self.pad_b
        self.wave_w = round(T.WAVE_W * scale)
        self.wave_h = round(T.WAVE_H * scale)
        self.bottom = round(T.PILL_BOTTOM * scale)

    def px(self, v: float) -> int:
        return round(v * self.s)


class Overlay:
    def __init__(self, root, level_fn=None):
        """level_fn() -> list[float] свежих RMS-уровней (последний - самый новый)."""
        self.root = root
        self.level_fn = level_fn
        self.win: LayeredWindow | None = None
        self.g = _Geom(1.0)

        self._state: str | None = None
        self._prev: str | None = None
        self._morph_at = 0.0
        self._msg = ""
        self._hint = ""
        self._shown = False
        self._vis_at = 0.0          # начало анимации появления/ухода
        self._rec_at = 0.0
        self._job = None
        self._done_job = None
        self._raise_at = 0.0

        self._chrome_cache: dict[int, Image.Image] = {}
        self._base: Image.Image | None = None
        self._peak = 0.02           # плавающая точка отсчёта громкости
        self._bars: list[float] = [0.0] * T.WAVE_BARS
        self._last_level_at = 0.0
        self._rect, _ = active_monitor()

    # ---------- публичный API ----------

    @property
    def state(self) -> str | None:
        """Текущее состояние или None, если пилюля спрятана."""
        return self._state if self._shown else None

    def set_hint(self, text: str) -> None:
        """Подпись у таймера на время записи. Пусто - нет подписи.

        Нужна в режиме «переключателя»: руки с клавиш сняты, и без подсказки
        непонятно, чем запись остановить. В режиме удержания она была бы враньём -
        там останавливает отпускание клавиши.
        """
        self._hint = text or ""

    def retheme(self) -> None:
        """Тема сменилась - выбросить всё, что нарисовано в старых красках.

        Капсула с тенью и нарезка по ширинам кэшируются картинками (иначе
        размывать тень пришлось бы каждый кадр), а картинки про смену палитры
        не знают.
        """
        self._base = None
        self._chrome_cache.clear()

    def show_loading(self) -> None:
        self._to(LOADING)

    def show_recording(self) -> None:
        self._rec_at = time.perf_counter()
        self._peak = 0.02
        self._bars = [0.0] * T.WAVE_BARS
        self._last_level_at = self._rec_at
        self._to(RECORDING)

    def show_processing(self) -> None:
        self._to(PROCESSING)

    def show_done(self, msg: str = "готово") -> None:
        self._msg = msg
        self._to(DONE)
        self._cancel_done()
        self._done_job = self.root.after(int(T.T_DONE_HOLD * 1000), self.hide)

    def show_error(self, msg: str) -> None:
        self._msg = msg
        self._to(ERROR)
        self._cancel_done()
        self._done_job = self.root.after(2200, self.hide)

    def hide(self) -> None:
        self._cancel_done()
        if not self._shown:
            return
        self._shown = False
        self._vis_at = time.perf_counter()
        self._ensure_tick()

    def destroy(self) -> None:
        self._cancel_done()
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:  # noqa: BLE001 - tk уже мог уйти
                pass
            self._job = None
        if self.win is not None:
            self.win.destroy()
            self.win = None

    # ---------- внутреннее ----------

    def _cancel_done(self) -> None:
        if self._done_job is not None:
            try:
                self.root.after_cancel(self._done_job)
            except Exception:  # noqa: BLE001
                pass
            self._done_job = None

    def _to(self, state: str) -> None:
        self._cancel_done()
        now = time.perf_counter()
        if not self._shown:
            # всплываем: стартового кросс-фейда нет, сразу нужное состояние
            self._prev = None
            self._state = state
            self._shown = True
            self._vis_at = now
            self._morph_at = now - T.T_MORPH
            self._place()
        elif state != self._state:
            self._prev = self._state
            self._state = state
            self._morph_at = now
        self._ensure_tick()

    def _place(self) -> None:
        rect, scale = active_monitor()
        if abs(scale - self.g.s) > 0.01:
            self.g = _Geom(scale)
            self._chrome_cache.clear()
            self._base = None
        self._rect = rect

    def _ensure_tick(self) -> None:
        if self._job is None:
            self._job = self.root.after(1, self._tick)

    def _tick(self) -> None:
        self._job = None
        now = time.perf_counter()
        try:
            alive = self._frame(now)
        except Exception:  # noqa: BLE001 - оверлей не должен ронять диктовку
            alive = False
            if self.win is not None:
                self.win.hide()
        if alive:
            self._job = self.root.after(max(1, int(1000 / T.FPS)), self._tick)

    # ---------- кадр ----------

    def _frame(self, now: float) -> bool:
        # Вход/уход: только прозрачность и сдвиг по вертикали - как у Toast.
        if self._shown:
            t = min(1.0, (now - self._vis_at) / T.T_SHOW)
            e = T.ease_out(t)
            alpha = e
            rise = (1.0 - e) * T.RISE * self.g.s
        else:
            t = min(1.0, (now - self._vis_at) / T.T_HIDE)
            e = T.ease_in(t)
            alpha = 1.0 - e
            rise = e * T.RISE * self.g.s
            if t >= 1.0:
                if self.win is not None:
                    self.win.hide()
                self._state = self._prev = None
                return False

        m = min(1.0, (now - self._morph_at) / T.T_MORPH) if self._prev else 1.0
        me = T.ease_in_out(m)
        if m >= 1.0:
            self._prev = None

        w_new = self._width(self._state)
        w = w_new if not self._prev else round(T.lerp(self._width(self._prev), w_new, me))

        img = self._chrome(w).copy()
        if self._prev:
            img.alpha_composite(self._fade(self._content(self._prev, w, now), 1.0 - me))
        img.alpha_composite(self._fade(self._content(self._state, w, now), me))

        g = self.g
        cw, ch = img.size
        x = self._rect.left + (self._rect.right - self._rect.left - cw) // 2
        y = round(self._rect.bottom - g.bottom - g.pad - g.pill_h + rise)

        if self.win is None:
            self.win = LayeredWindow(cw, ch)
        self.win.push(img, x, y, alpha)
        if now - self._raise_at > 0.5:           # чужой topmost мог накрыть
            self.win.raise_()
            self._raise_at = now
        return True

    @staticmethod
    def _fade(img: Image.Image, f: float) -> Image.Image:
        if f >= 0.999:
            return img
        if f <= 0.001:
            return Image.new("RGBA", img.size, (0, 0, 0, 0))
        out = img.copy()
        out.putalpha(img.getchannel("A").point(lambda v: int(v * f)))
        return out

    # ---------- хром: капсула + тень ----------

    def _render_chrome(self, cw: int) -> Image.Image:
        """Капсула с тенью на холсте шириной cw, честно и целиком.

        Тень рисуется в натуральную величину, а не в суперсэмпле. Её всё равно
        размывает гаусс с сигмой 20 - он сам себе сглаживание, и лучше от
        суперсэмпла не станет. Зато в суперсэмпле это девятикратно больше
        пикселей и втрое большее ядро: замерено 17.5 мс на кадр при бюджете
        16.7. Именно эта цена и заставляла резать капсулу из готовой базы.
        Капсула же остаётся в суперсэмпле - её край обязан быть чётким, а
        фигуры PIL сам не сглаживает.
        """
        g = self.g
        S = T.SS
        H = g.canvas_h
        box = [g.pad, g.pad, cw - g.pad, g.pad + g.pill_h]

        # --shadow-lg двумя слоями: близкий подхват и дальний мягкий ореол.
        # Тень всегда чёрная - цветных теней в системе нет.
        out = Image.new("RGBA", (cw, H), (0, 0, 0, 0))
        for i, (_dy, _sig, color) in enumerate(_SHADOWS):
            sh = Image.new("RGBA", (cw, H), (0, 0, 0, 0))
            ImageDraw.Draw(sh).rounded_rectangle(
                [box[0], box[1] + g.dy[i], box[2], box[3] + g.dy[i]],
                radius=g.r, fill=color)
            out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(g.sigma[i])))

        big = Image.new("RGBA", (cw * S, H * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        sbox = [v * S for v in box]
        d.rounded_rectangle(sbox, radius=g.r * S, fill=(*T.SURFACE, 255))
        # волосяная линия - основной разделитель системы: она, а не тень,
        # отделяет поверхность от того, что под ней
        d.rounded_rectangle(sbox, radius=g.r * S, outline=T.BORDER, width=max(1, S))
        out.alpha_composite(big.resize((cw, H), _BOX))
        return out

    def _chrome_base(self) -> Image.Image:
        if self._base is None:
            self._base = self._render_chrome(self.g.base_w)
        return self._base

    def _chrome(self, pill_w: int) -> Image.Image:
        cw = pill_w + 2 * self.g.pad
        hit = self._chrome_cache.get(cw)
        if hit is not None:
            return hit
        g = self.g
        if cw < g.base_w:
            # Уже базы - нарезка не поможет, и обрезать базу нельзя: у неё
            # капсула фиксированной ширины, и обрезка холста съедала бы поля,
            # оставляя саму капсулу прежней. Так узкая пилюля («7 слов»)
            # получалась во всю ширину холста, без скруглений и без тени - на
            # чёрном фоне этого не видно, а на светлом видно сразу.
            # Тени двух торцов тут перекрываются (3 сигмы = 60px при капсуле в
            # 55px прямой части), так что разложить её на куски нечестно -
            # рисуем целиком.
            out = self._render_chrome(cw)
        else:
            # 3-slice: середина капсулы горизонтально однородна (мы отступили
            # от угла на 3 сигмы тени), поэтому её честно тянуть одним пикселем
            base = self._chrome_base()
            out = Image.new("RGBA", (cw, g.canvas_h), (0, 0, 0, 0))
            out.paste(base.crop((0, 0, g.cap, g.canvas_h)), (0, 0))
            mid = base.crop((g.cap, 0, g.cap + 1, g.canvas_h))
            out.paste(mid.resize((cw - 2 * g.cap, g.canvas_h), _BOX), (g.cap, 0))
            out.paste(base.crop((g.base_w - g.cap, 0, g.base_w, g.canvas_h)), (cw - g.cap, 0))
        if len(self._chrome_cache) > 96:
            self._chrome_cache.clear()
        self._chrome_cache[cw] = out
        return out

    # ---------- ширина состояния ----------

    def _label(self, state: str) -> str:
        return {
            LOADING: "загружаю модель",
            PROCESSING: "распознаю",
            DONE: self._msg,
            ERROR: self._msg,
        }.get(state, "")

    def _hint_font(self):
        return T.font(self.g.px(T.T_2XS), T.W_MEDIUM, mono=True)

    def _width(self, state: str) -> int:
        g = self.g
        if state == RECORDING:
            timer = T.font(g.px(T.T_XS), T.W_MEDIUM, mono=True)
            w = (g.px(14) + g.px(8) + g.px(12) + g.wave_w + g.px(12)
                 + round(timer.getlength("0:00")) + g.px(14))
            if self._hint:
                w += round(self._hint_font().getlength(self._hint)) + g.px(12)
            return w
        f = T.font(g.px(T.T_SM), T.W_SEMIBOLD)
        return g.px(14) + g.px(16) + g.px(10) + round(f.getlength(self._label(state))) + g.px(16)

    # ---------- контент ----------

    def _content(self, state: str, pill_w: int, now: float) -> Image.Image:
        g = self.g
        img = Image.new("RGBA", (pill_w + 2 * g.pad, g.canvas_h), (0, 0, 0, 0))
        inner = Image.new("RGBA", (pill_w, g.pill_h), (0, 0, 0, 0))
        if state == RECORDING:
            self._draw_recording(inner, now)
        else:
            self._draw_labelled(inner, state, now)
        img.paste(inner, (g.pad, g.pad))
        return img

    def _draw_recording(self, img: Image.Image, now: float) -> None:
        g = self.g
        S = T.SS
        w, h = img.size
        big = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)

        # Точка «в эфире». Пульсируем только прозрачностью: масштаб - это уже
        # пружинка, а система разрешает фейды. Ореола нет - свечения в Korti нет.
        pulse = 0.5 + 0.5 * math.sin((now - self._rec_at) * 3.4)
        cx = (g.px(14) + g.px(4)) * S
        cy = h * S / 2
        rr = 4.0 * g.s * S
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                  fill=T.rgba(T.SUCCESS, 0.45 + 0.55 * pulse))

        # Осциллограмма - чернила: это данные, а не статус.
        self._pump_bars(now)
        x0 = (g.px(14) + g.px(8) + g.px(12)) * S
        pitch = g.wave_w * S / T.WAVE_BARS
        bw = pitch * 0.55
        half = g.wave_h * S / 2
        for i, lv in enumerate(self._bars):
            bh = max(1.5 * g.s * S, lv * half * 2)
            x = x0 + i * pitch + (pitch - bw) / 2
            # хвост слева гаснет - полоски будто уплывают за край
            a = 0.90 * min(1.0, (i + 1) / (T.WAVE_BARS * 0.16))
            d.rounded_rectangle([x, cy - bh / 2, x + bw, cy + bh / 2],
                                radius=bw / 2, fill=T.rgba(T.INK, a))
        img.alpha_composite(big.resize((w, h), _BOX))

        # Таймер - моноширинный: это метаданные, голос терминала. Цифры
        # табличные, поэтому 0:09 -> 0:10 не дёргает вёрстку.
        d2 = ImageDraw.Draw(img)
        right = w - g.px(14)
        if self._hint:
            # подсказка тише таймера: она читается один раз и больше не нужна
            f = self._hint_font()
            d2.text((right, h / 2), self._hint, font=f, fill=(*T.TEXT_MUTED, 255),
                    anchor="rm")
            right -= round(f.getlength(self._hint)) + g.px(12)
        secs = max(0.0, now - self._rec_at)
        d2.text((right, h / 2), f"{int(secs // 60)}:{int(secs % 60):02d}",
                font=T.font(g.px(T.T_XS), T.W_MEDIUM, mono=True),
                fill=(*T.TEXT_SECONDARY, 255), anchor="rm")

    def _pump_bars(self, now: float) -> None:
        """Подтянуть свежие уровни микрофона и подогнать масштаб под голос.

        Уровни приходят раз в LEVEL_MS (~31/с), а кадров 60/с: на большинстве
        кадров новых данных просто нет, и это норма - картинка стоит. Раньше
        такой кадр гасил все полоски, и на живом микрофоне осциллограмма
        схлопывалась в ровную ниточку (в синтетическом превью не всплывало:
        там уровни генерились на каждый вызов).

        Затухание пика привязано к числу уровней, а не к кадрам: иначе
        чувствительность зависела бы от частоты отрисовки.

        _FLOOR - нижняя граница масштаба, «тише этого считаем тишиной». Он же
        не даёт раздуть шум комнаты до пляшущей волны, когда никто не говорит.
        Ставить его высоко нельзя: на тихом микрофоне (или далёком источнике)
        он придавливает и речь - проверено, при 0.015 запись с rms 0.001
        распознавалась моделью, а на волне была ровная ниточка.
        """
        levels = self.level_fn() if self.level_fn else []
        if levels:
            self._last_level_at = now
            self._peak = max(self._peak * (0.992 ** len(levels)), max(levels), _FLOOR)
            for lv in levels[-T.WAVE_BARS:]:
                self._bars.append(min(1.0, (lv / self._peak) ** 0.65))
            del self._bars[:-T.WAVE_BARS]
        elif now - self._last_level_at > 0.3:
            # звука нет совсем (устройство отвалилось) - гасим, чтобы застывшая
            # картинка не выдавала себя за живую
            self._bars = [v * 0.90 for v in self._bars]

    def _draw_labelled(self, img: Image.Image, state: str, now: float) -> None:
        g = self.g
        S = T.SS
        w, h = img.size
        color = {LOADING: T.ACCENT, PROCESSING: T.ACCENT,
                 DONE: T.SUCCESS, ERROR: T.DANGER}[state]
        big = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        cx = (g.px(14) + g.px(8)) * S
        cy = h * S / 2
        r = 8.0 * g.s * S                       # иконка 16px - «в строку с текстом»
        stroke = max(1.0, 1.75 * g.s * S)       # обводка Lucide: 1.75-2px

        if state in (LOADING, PROCESSING):
            self._draw_spinner(d, cx, cy, r, now, color, stroke)
        elif state == DONE:
            self._draw_check(d, cx, cy, r, color, stroke)
        else:
            self._draw_alert(d, cx, cy, r, color, stroke)

        img.alpha_composite(big.resize((w, h), _BOX))

        d2 = ImageDraw.Draw(img)
        # Текст статуса чернилами, цвет несёт иконка - как в Toast.
        tint = T.TEXT if state in (LOADING, PROCESSING, DONE) else color
        d2.text((g.px(14) + g.px(16) + g.px(10), h / 2), self._label(state),
                font=T.font(g.px(T.T_SM), T.W_SEMIBOLD), fill=(*tint, 255), anchor="lm")

    @staticmethod
    def _draw_spinner(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float,
                      now: float, color, stroke: float) -> None:
        """Кольцо с вырезанной четвертью, крутится линейно - спиннер Korti
        (border 2px + border-top-color:transparent + rotate .6s linear)."""
        deg = (now / 0.6 * 360.0) % 360.0
        box = [cx - r * 0.86, cy - r * 0.86, cx + r * 0.86, cy + r * 0.86]
        d.arc(box, deg, deg + 270, fill=(*color, 255), width=round(stroke))

    @staticmethod
    def _draw_check(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float,
                    color, stroke: float) -> None:
        """Lucide check: M20 6 L9 17 L4 12 на сетке 24."""
        k = r * 2 / 24.0
        pts = [(cx + (20 - 12) * k, cy + (6 - 12) * k),
               (cx + (9 - 12) * k, cy + (17 - 12) * k),
               (cx + (4 - 12) * k, cy + (12 - 12) * k)]
        d.line(pts, fill=(*color, 255), width=round(stroke), joint="curve")
        for p in pts:  # круглые торцы - PIL сам их не делает
            d.ellipse([p[0] - stroke / 2, p[1] - stroke / 2,
                       p[0] + stroke / 2, p[1] + stroke / 2], fill=(*color, 255))

    @staticmethod
    def _draw_alert(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float,
                    color, stroke: float) -> None:
        """Lucide alert-circle: окружность + палочка + точка."""
        k = r * 2 / 24.0
        d.ellipse([cx - 10 * k, cy - 10 * k, cx + 10 * k, cy + 10 * k],
                  outline=(*color, 255), width=round(stroke))
        d.line([(cx, cy - 4.5 * k), (cx, cy + 1.0 * k)], fill=(*color, 255),
               width=round(stroke))
        d.ellipse([cx - stroke / 2, cy + 4 * k - stroke / 2,
                   cx + stroke / 2, cy + 4 * k + stroke / 2], fill=(*color, 255))
