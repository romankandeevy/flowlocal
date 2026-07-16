"""Отрисованные элементы управления - порт компонентов Korti на PIL.

Штатные виджеты tkinter рисуются примитивами Tk без сглаживания: у
переключателя вместо круглой ручки получается лесенка. Поэтому каждый
контрол рисуется в PIL (суперсэмпл + ужатие), кладётся на Canvas
картинкой и там же ловит мышь. Фон канвы задаётся снаружи и совпадает с
фоном карточки - альфа PIL ложится на него без каймы.

Размеры и состояния взяты из .jsx компонентов системы, а не на глаз:
  Switch  - дорожка 38x22, ручка 16, включённый = чернила, ручка = бумага
  Seg     - контейнер --fill + линия, радиус 6, выбранный сегмент = бумага
  Slider  - дорожка 5px --fill-strong, заливка --accent, ручка 16 с линией
  Button  - высота 38, радиус 6, primary = чернила на бумаге
  Card    - линия --border, радиус 12 (--radius-lg), фон общий со страницей
  Input   - высота 38, радиус 6, --fill-subtle, в фокусе бумага + акцент
Ховер везде по правилу системы: заливка на ступень выше, цвет текста
muted -> primary. Никаких цветовых сдвигов - сдвигаться некуда.

Card и Input держат внутри настоящий tk-виджет (Frame, Entry) и рисуют вокруг
него скруглённую рамку: сам tkinter умеет только прямые углы, а система
требует 12 и 6 - см. комментарии у классов.

Все контролы зовут on_change(value) уже после изменения своего value.
"""

import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

import inputspec
import theme as T

_SS = 3
_BOX = Image.Resampling.BOX


class PilCanvas(tk.Canvas):
    """Canvas, в который блитится PIL-картинка. Держит ссылку на PhotoImage:
    без неё tkinter соберёт картинку мусором и покажет пустоту."""

    def __init__(self, master, w: int, h: int, bg, **kw):
        super().__init__(master, width=w, height=h, highlightthickness=0, bd=0,
                         bg=T.hx(bg), takefocus=0, **kw)
        # _cw/_ch, а не _w/_h: под этими именами tkinter держит собственный
        # путь виджета в Tcl, и перезапись превращает любой вызов в
        # «invalid command name»
        self._cw, self._ch = w, h
        self._bg = bg
        self._photo = None
        self._item = self.create_image(0, 0, anchor="nw")

    def blit(self, img: Image.Image) -> None:
        self._photo = ImageTk.PhotoImage(img)
        self.itemconfig(self._item, image=self._photo)

    def new(self) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        """Пустой холст в суперсэмпле."""
        img = Image.new("RGBA", (self._cw * _SS, self._ch * _SS), (0, 0, 0, 0))
        return img, ImageDraw.Draw(img)

    def done(self, img: Image.Image) -> None:
        self.blit(img.resize((self._cw, self._ch), _BOX))


class Card(tk.Canvas):
    """Korti .ins-card: фон страницы, волосяная линия --border, радиус 12.

    tkinter рисует рамку только прямоугольником (highlightthickness), поэтому
    контур рисуем в PIL и блитим, а содержимое кладём поверх через
    create_window. Дочернее окно канвы всегда рисуется ПОВЕРХ её элементов -
    значит, оно обязано отступить от угла настолько, чтобы не закрыть дугу:
    прямоугольник влезает в скругление с отступом r - r/√2 ≈ 3.5px при r=12,
    берём 5 - с запасом на толщину линии. Углы видно, потому что внутренность
    карточки, фон строк и фон страницы - один и тот же BG.

    autosize=False - карточка тянется вместе с содержимым (боксы словаря и
    истории), иначе высота считается по содержимому: канва под ребёнка не растёт.
    """

    INSET = 5

    def __init__(self, master, bg=None, radius: int | None = None,
                 autosize: bool = True):
        bg = T.BG if bg is None else bg
        super().__init__(master, highlightthickness=0, bd=0, bg=T.hx(bg),
                         takefocus=0)
        self._bg = bg
        self._radius = T.RADIUS_LG if radius is None else radius
        self._autosize = autosize
        self._photo = None
        self._size = (0, 0)
        self._item = self.create_image(0, 0, anchor="nw")
        self.body = tk.Frame(self, bg=T.hx(bg))
        self._win = self.create_window(self.INSET, self.INSET, anchor="nw",
                                       window=self.body)
        self.bind("<Configure>", self._resize)
        if autosize:
            self.body.bind("<Configure>", self._fit)

    def _fit(self, _e=None) -> None:
        h = self.body.winfo_reqheight() + 2 * self.INSET
        if h != self.winfo_reqheight():
            self.configure(height=h)

    def _resize(self, _e=None) -> None:
        w, h = self.winfo_width(), self.winfo_height()
        self.itemconfig(self._win, width=max(1, w - 2 * self.INSET))
        if not self._autosize:
            self.itemconfig(self._win, height=max(1, h - 2 * self.INSET))
        if w < 2 or h < 2 or (w, h) == self._size:
            return
        self._size = (w, h)
        self._draw(w, h)

    def _draw(self, w: int, h: int) -> None:
        S = _SS
        line = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        ImageDraw.Draw(line).rounded_rectangle(
            [S / 2, S / 2, w * S - S / 2 - 1, h * S - S / 2 - 1],
            radius=self._radius * S, outline=T.BORDER, width=S)
        img = Image.new("RGBA", (w, h), (*self._bg, 255))
        img.alpha_composite(line.resize((w, h), _BOX))
        self._photo = ImageTk.PhotoImage(img)
        self.itemconfig(self._item, image=self._photo)


class Input(tk.Canvas):
    """Korti Input: высота 38, радиус 6, заливка --fill-subtle, линия --border.

    В фокусе - бумага и акцентная линия: фокус в системе это всегда акцент и
    всегда линия, а не свечение. tk.Entry живёт внутри канвы по той же причине,
    что и карточка: своя рамка у него только прямоугольная.

    Шрифт моноширинный: сюда пишут адрес и имя модели - это метаданные, а их
    в Korti набирают терминальным голосом.
    """

    H = 38
    PAD = 12          # --pad-control, как padding в .ins-input

    def __init__(self, master, textvariable, bg=None, w: int = 240):
        bg = T.BG if bg is None else bg
        super().__init__(master, width=w, height=self.H, highlightthickness=0,
                         bd=0, bg=T.hx(bg), takefocus=0)
        self._cw = w
        self._bg = bg
        self._focus = False
        self._hover = False
        self._enabled = True
        self._photo = None
        self._item = self.create_image(0, 0, anchor="nw")
        self.entry = tk.Entry(
            self, textvariable=textvariable, relief="flat", bd=0,
            highlightthickness=0, fg=T.hx(T.TEXT),
            disabledforeground=T.hx(T.TEXT_FAINT),
            insertbackground=T.hx(T.ACCENT),
            selectbackground=T.hx(T.mix(T.PAPER, T.ACCENT, 0.30)),
            selectforeground=T.hx(T.TEXT), font=(T.TK_MONO, -T.T_SM))
        self.create_window(self.PAD, self.H // 2, anchor="w", window=self.entry,
                           width=w - 2 * self.PAD, height=self.H - 2)
        self.entry.bind("<FocusIn>", lambda _e: self._set(focus=True))
        self.entry.bind("<FocusOut>", lambda _e: self._set(focus=False))
        for wdg in (self, self.entry):
            wdg.bind("<Enter>", lambda _e: self._set(hover=True))
            wdg.bind("<Leave>", lambda _e: self._set(hover=False))
        self._draw()

    def set_enabled(self, value: bool) -> None:
        """Поле бессмысленно при выключенной настройке - гасим и не пускаем."""
        self._enabled = bool(value)
        self.entry.configure(state="normal" if self._enabled else "disabled")
        self._draw()

    def _set(self, focus: bool | None = None, hover: bool | None = None) -> None:
        if focus is not None:
            self._focus = focus
        if hover is not None:
            self._hover = hover
        self._draw()

    def _draw(self) -> None:
        S = _SS
        fill = T.BG if self._focus else T.FILL_SUBTLE_FLAT
        if self._focus:
            line = T.ACCENT
        elif self._hover and self._enabled:
            line = T.BORDER_STRONG_FLAT      # .ins-input:hover
        else:
            line = T.BORDER_FLAT
        img = Image.new("RGBA", (self._cw * S, self.H * S), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle(
            [S / 2, S / 2, self._cw * S - S / 2 - 1, self.H * S - S / 2 - 1],
            radius=T.RADIUS_SM * S, fill=(*fill, 255), outline=(*line, 255), width=S)
        out = Image.new("RGBA", (self._cw, self.H), (*self._bg, 255))
        out.alpha_composite(img.resize((self._cw, self.H), _BOX))
        self._photo = ImageTk.PhotoImage(out)
        self.itemconfig(self._item, image=self._photo)
        self.entry.configure(bg=T.hx(fill), disabledbackground=T.hx(fill))


class Toggle(PilCanvas):
    """Korti Switch: 38x22, ручка 16. Включённый - это чернила, а не акцент:
    акцент в системе выделяет особое, а не «включено»."""

    W, H = 38, 22

    def __init__(self, master, value: bool, on_change, bg):
        super().__init__(master, self.W, self.H, bg, cursor="hand2")
        self.value = bool(value)
        self.on_change = on_change
        self._pos = 1.0 if self.value else 0.0
        self._hover = False
        self._job = None
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self._draw()

    def _set_hover(self, v):
        self._hover = v
        self._draw()

    def _click(self, _e=None):
        self.value = not self.value
        self._animate()
        self.on_change(self.value)

    def _animate(self):
        if self._job:
            self.after_cancel(self._job)
        target = 1.0 if self.value else 0.0
        start, t0 = self._pos, [0]
        steps = max(1, int(T.T_DUR * T.FPS))

        def step():
            if not self.winfo_exists():   # окно закрыли посреди анимации
                self._job = None
                return
            t0[0] += 1
            k = min(1.0, t0[0] / steps)
            self._pos = T.lerp(start, target, T.ease_out(k))
            self._job = None if k >= 1.0 else self.after(int(1000 / T.FPS), step)
            self._draw()

        step()

    def set(self, value: bool) -> None:
        self.value = bool(value)
        self._animate()

    def _draw(self):
        img, d = self.new()
        S = _SS
        p = self._pos
        # выкл: --fill-strong + линия; вкл: --primary (чернила)
        track = T.mix(T.FILL_STRONG_FLAT, T.INK, p)
        if self._hover and p < 0.5:
            track = T.mix(track, T.INK, 0.06)
        d.rounded_rectangle([0, 0, self.W * S, self.H * S], radius=self.H * S / 2,
                            fill=(*track, 255),
                            outline=T.BORDER if p < 0.5 else (*T.INK, 255),
                            width=max(1, S))
        r = 8 * S / 2
        cx = (2 + 8) * S + p * 16 * S
        cy = self.H * S / 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*T.BG, 255))
        self.done(img)


class Segmented(PilCanvas):
    """Korti SegmentedControl: контейнер --fill, выбранный сегмент - бумага."""

    H = 30

    def __init__(self, master, options: list[tuple[str, object]], value, on_change, bg):
        self.options = options
        self.value = value
        self.on_change = on_change
        f = T.font(T.T_SM * _SS, T.W_MEDIUM)
        self._pad = 12
        self._segw = [max(36, round(f.getlength(lbl) / _SS) + self._pad * 2)
                      for lbl, _ in options]
        super().__init__(master, sum(self._segw) + 6, self.H, bg, cursor="hand2")
        self._hover = -1
        self._sel = float(self._index())
        self._job = None
        self.bind("<Button-1>", self._click)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda _e: self._set_hover(-1))
        self._draw()

    def _index(self) -> int:
        for i, (_lbl, v) in enumerate(self.options):
            if v == self.value:
                return i
        return 0

    def _at(self, x: int) -> int:
        acc = 3
        for i, w in enumerate(self._segw):
            if acc <= x < acc + w:
                return i
            acc += w
        return -1

    def _motion(self, e):
        self._set_hover(self._at(e.x))

    def _set_hover(self, i):
        if i != self._hover:
            self._hover = i
            self._draw()

    def _click(self, e):
        i = self._at(e.x)
        if i < 0 or self.options[i][1] == self.value:
            return
        self.value = self.options[i][1]
        self._animate()
        self.on_change(self.value)

    def set(self, value) -> None:
        self.value = value
        self._animate()

    def _animate(self):
        if self._job:
            self.after_cancel(self._job)
        target = float(self._index())
        start, t0 = self._sel, [0]
        steps = max(1, int(T.T_DUR * T.FPS))

        def step():
            if not self.winfo_exists():
                self._job = None
                return
            t0[0] += 1
            k = min(1.0, t0[0] / steps)
            self._sel = T.lerp(start, target, T.ease_out(k))
            self._job = None if k >= 1.0 else self.after(int(1000 / T.FPS), step)
            self._draw()

        step()

    def _x_of(self, idx: float) -> float:
        """Левый край сегмента при дробном индексе - для плавной езды выделения."""
        i = int(idx)
        frac = idx - i
        acc = 3.0 + sum(self._segw[:i])
        if frac > 0 and i + 1 < len(self._segw):
            acc += frac * self._segw[i]
        return acc

    def _draw(self):
        img, d = self.new()
        S = _SS
        d.rounded_rectangle([0, 0, self._cw * S, self.H * S], radius=T.RADIUS_SM * S,
                            fill=(*T.FILL_FLAT, 255), outline=T.BORDER, width=max(1, S))
        i = int(round(self._sel))
        x = self._x_of(self._sel) * S
        w = T.lerp(self._segw[int(self._sel)],
                   self._segw[min(len(self._segw) - 1, int(self._sel) + 1)],
                   self._sel - int(self._sel)) * S
        d.rounded_rectangle([x, 3 * S, x + w, (self.H - 3) * S],
                            radius=(T.RADIUS_SM - 1) * S, fill=(*T.BG, 255))
        acc = 3.0
        for j, (lbl, _v) in enumerate(self.options):
            sel = j == i
            c = T.TEXT if (sel or self._hover == j) else T.TEXT_SECONDARY
            d.text(((acc + self._segw[j] / 2) * S, self.H * S / 2), lbl,
                   font=T.font(T.T_SM * S, T.W_MEDIUM if not sel else T.W_SEMIBOLD),
                   fill=(*c, 255), anchor="mm")
            acc += self._segw[j]
        self.done(img)


class Slider(PilCanvas):
    """Korti Slider: дорожка 5px, заливка акцентом, ручка бумажная с линией.

    Значение подписано справа: без него ползунок бесполезен - «где-то
    посередине» это не настройка, человеку нужно видеть, что он выставил.
    """

    H = 22
    VAL_W = 54

    def __init__(self, master, lo: float, hi: float, step: float, value: float,
                 on_change, bg, w: int = 150, fmt="{:.1f}"):
        self._track_w = w
        super().__init__(master, w + self.VAL_W, self.H, bg, cursor="hand2")
        self.lo, self.hi, self.step = lo, hi, step
        self.value = min(hi, max(lo, value))
        self.on_change = on_change
        self.fmt = fmt
        self._drag = False
        self._hover = False
        self.bind("<Button-1>", self._down)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", self._up)
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self._draw()

    def _set_hover(self, v):
        self._hover = v
        self._draw()

    @property
    def _pad(self):
        return 8

    def _from_x(self, x):
        t = (x - self._pad) / max(1, self._track_w - 2 * self._pad)
        v = self.lo + max(0.0, min(1.0, t)) * (self.hi - self.lo)
        v = round(v / self.step) * self.step
        return min(self.hi, max(self.lo, v))

    def _down(self, e):
        self._drag = True
        self._apply(self._from_x(e.x))

    def _move(self, e):
        if self._drag:
            self._apply(self._from_x(e.x))

    def _up(self, _e):
        self._drag = False
        self._draw()

    def _apply(self, v):
        if abs(v - self.value) > 1e-9:
            self.value = v
            self.on_change(v)
        self._draw()

    def _draw(self):
        img, d = self.new()
        S = _SS
        t = (self.value - self.lo) / (self.hi - self.lo) if self.hi > self.lo else 0
        cy = self.H * S / 2
        x0, x1 = self._pad * S, (self._track_w - self._pad) * S
        cx = x0 + t * (x1 - x0)
        d.rounded_rectangle([x0, cy - 2.5 * S, x1, cy + 2.5 * S], radius=2.5 * S,
                            fill=(*T.FILL_STRONG_FLAT, 255))
        if cx > x0:
            d.rounded_rectangle([x0, cy - 2.5 * S, cx, cy + 2.5 * S], radius=2.5 * S,
                                fill=(*T.ACCENT, 255))
        r = 8 * S / 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*T.BG, 255),
                  outline=T.BORDER_STRONG if not (self._hover or self._drag)
                  else (*T.INK, 255), width=max(1, S))
        d.text((self._cw * S, cy), self.fmt.format(self.value),
               font=T.font(T.T_XS * S, T.W_MEDIUM, mono=True),
               fill=(*T.TEXT_SECONDARY, 255), anchor="rm")
        self.done(img)


class HotkeyBox(PilCanvas):
    """Поле «нажмите сочетание». Клик -> захват, Esc -> отмена.

    Ловит и клавиши, и боковые кнопки мыши: «ctrl+mouse4» - законный бинд.
    Клавиши читаются библиотекой keyboard, а не биндингами tk: приложение
    вешает хоткей через неё же, и имена должны совпадать. Плюс tk на русской
    раскладке отдаёт кириллические keysym'ы, из которых хоткей не собрать.
    Кнопки мыши - библиотекой mouse: keyboard про мышь ничего не знает.

    Разбор и показ сочетаний - в inputspec: таблицы имён общие с приложением,
    иначе поле и хук понимали бы «ctrl» по-разному (так уже случался баг).

    allow_clear - разрешить пустое значение (Backspace/Delete при захвате или
    крестик снаружи). Для необязательных биндов «выключено» - законное
    состояние.
    """

    W, H = 200, 34
    # Левую и правую кнопки не ловим намеренно: ими человек кликает по этому же
    # окну, и захват сделал бы настройки неуправляемыми.
    _MOUSE_OK = ("middle", "x", "x2")

    def __init__(self, master, value: str, on_change, bg, on_capture=None,
                 allow_clear: bool = False):
        super().__init__(master, self.W, self.H, bg, cursor="hand2")
        self.value = value
        self.on_change = on_change
        self.on_capture = on_capture or (lambda _active: None)
        self.allow_clear = allow_clear
        self._capturing = False
        self._hover = False
        self._hook = None
        self._mouse_hook = None
        self._mods: list[str] = []
        self.bind("<Button-1>", lambda _e: self._start())
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        # Окно могут закрыть прямо во время захвата. Тогда без этого хук
        # keyboard остался бы висеть, а приложение - вообще без хоткея:
        # снять-то мы его сняли, а вернуть было бы уже некому.
        self.bind("<Destroy>", lambda _e: self.cancel())
        self._draw()

    def cancel(self) -> None:
        """Прервать захват, если он идёт. Безопасно звать всегда."""
        if self._capturing:
            self._stop()

    def _set_hover(self, v):
        self._hover = v
        self._draw()

    # ---------- захват ----------

    def clear(self) -> None:
        """Стереть бинд (крестик рядом с полем)."""
        self.cancel()
        if self.value:
            self.value = ""
            self._draw()
            self.on_change("")

    def _start(self):
        if self._capturing:
            return
        import keyboard
        import mouse

        self._capturing = True
        self._mods = []
        self.on_capture(True)          # приложение снимает свои хоткеи
        self._hook = keyboard.hook(self._event)
        self._mouse_hook = mouse.hook(self._mouse_event)
        self._draw()

    def _stop(self):
        import keyboard
        import mouse

        if self._hook is not None:
            try:
                keyboard.unhook(self._hook)
            except (KeyError, ValueError):
                pass
            self._hook = None
        if self._mouse_hook is not None:
            try:
                mouse.unhook(self._mouse_hook)
            except (KeyError, ValueError):
                pass
            self._mouse_hook = None
        self._capturing = False
        self.on_capture(False)         # приложение вешает хоткеи обратно
        if self.winfo_exists():
            self._draw()

    def _event(self, e):
        # колбэк прилетает из потока keyboard - в tk только через after
        try:
            self.after(0, lambda: self._handle(e))
        except tk.TclError:            # виджет уже уничтожен
            pass

    def _mouse_event(self, e):
        import mouse

        if not isinstance(e, mouse.ButtonEvent) or e.event_type != mouse.DOWN:
            return
        if e.button not in self._MOUSE_OK:
            return
        try:
            self.after(0, lambda b=e.button: self._handle_mouse(b))
        except tk.TclError:
            pass

    def _handle_mouse(self, button: str):
        if not self._capturing:
            return
        self._commit(inputspec.build(self._mods, mouse=button))

    def _handle(self, e):
        if not self._capturing:
            return
        name = (e.name or "").lower()
        if e.event_type == "down":
            if name == "esc":
                self._stop()
                return
            if self.allow_clear and name in ("backspace", "delete") and not self._mods:
                self._commit("")     # без модификаторов - значит именно «стереть»
                return
            canon = inputspec.canon_modifier(name)
            if canon:
                if canon not in self._mods:
                    self._mods.append(canon)
                self._draw()
                return
            self._commit(inputspec.build(self._mods, key=name))
        elif e.event_type == "up":
            canon = inputspec.canon_modifier(name)
            if canon and self._mods:
                # отпустили модификатор, ничего больше не нажав ->
                # это одноклавишный хоткей вида "right ctrl"
                if len(self._mods) == 1 and self._mods[0] == canon:
                    self._commit(name)
                else:
                    self._mods = [m for m in self._mods if m != canon]
                    self._draw()

    def _commit(self, hk: str):
        self.value = hk
        self._stop()
        self.on_change(hk)

    # ---------- вид ----------

    pretty = staticmethod(inputspec.pretty)

    def _draw(self):
        img, d = self.new()
        S = _SS
        if self._capturing:
            bg, br, fg, txt = T.FILL_FLAT, T.ACCENT, T.ACCENT, "нажмите сочетание"
        else:
            bg = T.FILL_FLAT if self._hover else T.BG
            br, txt = T.BORDER_STRONG_FLAT, self.pretty(self.value)
            fg = T.TEXT if self.value else T.TEXT_MUTED   # «не задано» - не значение
        d.rounded_rectangle([S, S, self.W * S - S, self.H * S - S], radius=T.RADIUS_SM * S,
                            fill=(*bg, 255), outline=(*br, 255), width=max(1, S))
        # Сочетание - метаданные, а метаданные в Korti набирают моноширинным.
        d.text((self.W * S / 2, self.H * S / 2), txt,
               font=T.font(T.T_XS * S, T.W_MEDIUM, mono=True),
               fill=(*fg, 255), anchor="mm")
        self.done(img)


class Select(PilCanvas):
    """Выпадающий список. Меню - штатное tk.Menu: перерисовывать системное
    меню ради красоты не стоит, оно и так ведёт себя правильно."""

    H = 34

    def __init__(self, master, options: list[tuple[str, object]], value, on_change,
                 bg, w: int = 260):
        super().__init__(master, w, self.H, bg, cursor="hand2")
        self.options = options
        self.value = value
        self.on_change = on_change
        self._hover = False
        self.bind("<Button-1>", self._open)
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self._draw()

    def _set_hover(self, v):
        self._hover = v
        self._draw()

    def _label(self) -> str:
        for lbl, v in self.options:
            if v == self.value:
                return lbl
        return str(self.value)

    def set_options(self, options, value=None):
        self.options = options
        if value is not None:
            self.value = value
        self._draw()

    def _open(self, _e):
        m = tk.Menu(self, tearoff=0, bg=T.hx(T.BG), fg=T.hx(T.TEXT),
                    activebackground=T.hx(T.FILL_STRONG_FLAT),
                    activeforeground=T.hx(T.TEXT),
                    bd=0, font=(T.TK_SANS, -T.T_SM))
        for lbl, v in self.options:
            m.add_command(label=("  " + lbl) if v != self.value else ("✓ " + lbl),
                          command=lambda vv=v: self._pick(vv))
        try:
            m.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.H)
        finally:
            m.grab_release()

    def _pick(self, v):
        if v == self.value:
            return
        self.value = v
        self._draw()
        self.on_change(v)

    def _draw(self):
        img, d = self.new()
        S = _SS
        bg = T.FILL_FLAT if self._hover else T.BG
        d.rounded_rectangle([S, S, self._cw * S - S, self.H * S - S], radius=T.RADIUS_SM * S,
                            fill=(*bg, 255), outline=(*T.BORDER_STRONG_FLAT, 255),
                            width=max(1, S))
        f = T.font(T.T_SM * S, T.W_REGULAR)
        label = self._label()
        maxw = (self._cw - 40) * S
        while f.getlength(label) > maxw and len(label) > 4:
            label = label[:-2]
            if f.getlength(label + "…") <= maxw:
                label += "…"
                break
        d.text((12 * S, self.H * S / 2), label, font=f, fill=(*T.TEXT, 255), anchor="lm")
        # шеврон - Lucide chevron-down, обводка 1.75px
        cx, cy, r = (self._cw - 14) * S, self.H * S / 2, 3.4 * S
        d.line([(cx - r, cy - r * 0.5), (cx, cy + r * 0.55), (cx + r, cy - r * 0.5)],
               fill=(*T.TEXT_MUTED, 255), width=round(1.75 * S), joint="curve")
        self.done(img)


class BarChart(PilCanvas):
    """Korti BarChart: столбики, зазор 4, минимальная высота 2.

    Углы намеренно НЕ скруглены и суперсэмпла тут нет: в системе у столбиков
    квадратные торцы («crisp, square-cornered bars» прямо в BarChart.jsx), а
    сглаживание вертикальных граней их бы только замылило. Цвет - чернила, а не
    сигнальный tone: слова в день это данные, а не статус, тонировать их нечем.
    """

    GAP = 4
    MIN_H = 2

    def __init__(self, master, values, bg=None, w: int = 560, h: int = 120):
        super().__init__(master, w, h, T.BG if bg is None else bg)
        self.values = list(values)
        self._draw()

    def set_values(self, values) -> None:
        self.values = list(values)
        self._draw()

    def _draw(self) -> None:
        img = Image.new("RGBA", (self._cw, self._ch), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        n = len(self.values)
        if n:
            # делим на max, а не на сумму: столбик показывает день против
            # самого урожайного дня, иначе на длинном ряду всё ляжет в пол
            top = max(max(self.values), 1)
            pitch = self._cw / n
            bw = max(1, round(pitch - self.GAP))
            for i, v in enumerate(self.values):
                bh = max(self.MIN_H, round(v / top * self._ch))
                x = round(i * pitch)
                d.rectangle([x, self._ch - bh, x + bw - 1, self._ch - 1],
                            fill=(*T.TEXT, 255))
        self.blit(img)


class NavItem(PilCanvas):
    """Строка бокового меню. Выбранное - заливка на ступень выше и чернильный
    текст: цветом система не выделяет, выделять нечем."""

    H = 34

    def __init__(self, master, label: str, on_click, bg, w: int = 186):
        super().__init__(master, w, self.H, bg, cursor="hand2")
        self.label = label
        self.on_click = on_click
        self.active = False
        self._hover = False
        self.bind("<Button-1>", lambda _e: self.on_click())
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self._draw()

    def _set_hover(self, v):
        self._hover = v
        self._draw()

    def set_active(self, v: bool):
        self.active = v
        self._draw()

    def _draw(self):
        img, d = self.new()
        S = _SS
        if self.active:
            d.rounded_rectangle([0, 0, self._cw * S, self.H * S], radius=T.RADIUS_SM * S,
                                fill=(*T.FILL_FLAT, 255))
        elif self._hover:
            d.rounded_rectangle([0, 0, self._cw * S, self.H * S], radius=T.RADIUS_SM * S,
                                fill=(*T.FILL_SUBTLE_FLAT, 255))
        c = T.TEXT if (self.active or self._hover) else T.TEXT_SECONDARY
        d.text((12 * S, self.H * S / 2), self.label,
               font=T.font(T.T_SM * S, T.W_SEMIBOLD if self.active else T.W_REGULAR),
               fill=(*c, 255), anchor="lm")
        self.done(img)


class Button(PilCanvas):
    """Korti Button: высота 38 (sm - 30), радиус 6, вес 600.

    primary  = чернила на бумаге (главное действие системы)
    secondary= --fill + линия
    ghost    = прозрачная, проявляется заливкой на ховере
    danger   = красный, только для разрушительного
    """

    H = 30      # --sm: в наших барах кнопки компактные

    def __init__(self, master, label: str, on_click, bg, kind="secondary",
                 w: int | None = None):
        f = T.font(T.T_SM * _SS, T.W_SEMIBOLD)
        w = w or max(72, round(f.getlength(label) / _SS) + 24)
        super().__init__(master, w, self.H, bg, cursor="hand2")
        self.label = label
        self.on_click = on_click
        self.kind = kind
        self._hover = False
        self._press = False
        self.bind("<Button-1>", self._down)
        self.bind("<ButtonRelease-1>", self._up)
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self._draw()

    def _set_hover(self, v):
        self._hover = v
        self._press = self._press and v
        self._draw()

    def _down(self, _e):
        self._press = True
        self._draw()

    def _up(self, _e):
        was = self._press
        self._press = False
        self._draw()
        if was:
            self.on_click()

    def _draw(self):
        img, d = self.new()
        S = _SS
        if self.kind == "primary":
            bg = T.mix(T.INK, T.PAPER, 0.14) if self._hover else T.INK
            fg, outline = T.PRIMARY_FG, None
        elif self.kind == "danger":
            bg = T.BG
            fg, outline = T.DANGER, T.mix(T.PAPER, T.DANGER, 0.32)
            if self._hover:
                bg = T.mix(T.PAPER, T.DANGER, 0.14)
        else:
            bg = T.FILL_STRONG_FLAT if self._hover else T.FILL_FLAT
            fg, outline = T.TEXT, T.BORDER_STRONG_FLAT
        # нажатие - сдвиг на 1px вниз: кнопка физически продавливается
        dy = 1 * S if self._press else 0
        d.rounded_rectangle([S, S + dy, self._cw * S - S, self.H * S - S + dy],
                            radius=T.RADIUS_SM * S, fill=(*bg, 255),
                            outline=(*outline, 255) if outline else None,
                            width=max(1, S) if outline else 0)
        d.text((self._cw * S / 2, self.H * S / 2 + dy), self.label,
               font=T.font(T.T_SM * S, T.W_SEMIBOLD), fill=(*fg, 255), anchor="mm")
        self.done(img)
