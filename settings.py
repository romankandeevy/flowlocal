"""Окно настроек, словаря и истории.

Раньше единственным способом что-то поменять был config.json в блокноте.
Здесь то же самое, но руками: боковое меню, карточки строк «название -
пояснение - контрол», сохранение сразу по изменению (кнопки «Применить»
нет намеренно - лишний шаг, о котором легко забыть).

Рамка окна - системная, но перекрашена в тёмное через DWM: получаем родные
snap/alt-tab/кнопки, без белой полосы над тёмным интерфейсом.

Всё живёт в потоке tkinter. Захват хоткея на время снимает хоткей
приложения через колбэк on_hotkey_capture - иначе нажатие Ctrl+Shift+Space
в поле захвата запустило бы запись.
"""

import json
import os
import subprocess
import tkinter as tk
from tkinter import ttk

import config as C
import models
import stats
import theme as T
from layered import style_titlebar, tk_hwnd
from util import plural
from widgets import (BarChart, Button, Card, HotkeyBox, Input, NavItem, Segmented,
                     Select, Slider, Toggle)

W, H = 900, 660
SIDEBAR = 214
PAD = 26

# Строка карточки - это .ins-card__header: padding 14px --pad-card, то есть
# 24 по горизонтали и 14 по вертикали. Отсчёт от края карточки, а пакуемся мы
# внутрь её содержимого - оно уже отступило от края на Card.INSET.
ROW_PAD_X = 24 - Card.INSET
ROW_PAD_Y = 14 - Card.INSET

# Список моделей - из каталога, а не руками: там же размеры, языки и лицензии.
MODELS = [(m.title, m.id) for m in models.CATALOG]
LANGS = [("авто", None), ("рус", "ru"), ("eng", "en")]
DEVICES = [("авто", "auto"), ("GPU", "cuda"), ("CPU", "cpu")]
INSERT = [("вставка", "paste"), ("посимвольно", "type")]
THEMES = [("система", "system"), ("светлая", "light"), ("тёмная", "dark")]


def _dur(sec: float) -> str:
    """Секунды по-человечески. «4361 с» не читается, а статистика - про то,
    чтобы с одного взгляда понять, много это или мало."""
    sec = max(0, round(sec))
    if sec < 60:
        return f"{sec} с"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m} мин"
    h, m = divmod(m, 60)
    return f"{h} ч {m:02d} мин"


class PairTable:
    """Таблица «слева -> справа» со строками, которые можно добавлять и убирать.

    Одна и та же машинерия нужна и заменам («моя почта» -> адрес), и правилам
    тона («outlook.exe» -> формально): разница только в подписях и в том, куда
    сохранять.

    Значение собирается из полей ЗАНОВО на каждую правку, а не правится по
    ключу: ключ редактируют прямо на месте, и «переименование» иначе
    превращалось бы в удалить-плюс-добавить с потерей значения на полпути.
    """

    def __init__(self, host, on_change, empty_text: str, left_w: int = 190,
                 right_w: int = 250):
        self.host = host
        self.on_change = on_change
        self.empty_text = empty_text
        self.left_w, self.right_w = left_w, right_w
        self.rows: list[tuple[tk.StringVar, tk.StringVar]] = []
        self._empty: tk.Label | None = None

    def fill(self, items: dict) -> None:
        for w in self.host.winfo_children():
            w.destroy()
        self.rows.clear()
        self._empty = None
        for k, v in (items or {}).items():
            self.add(str(k), str(v))
        self._placeholder()

    def add(self, key: str = "", value: str = "") -> None:
        if self._empty is not None:
            self._empty.destroy()
            self._empty = None
        row = tk.Frame(self.host, bg=T.hx(T.BG))
        row.pack(fill="x", padx=ROW_PAD_X, pady=5)
        pair = (tk.StringVar(value=key), tk.StringVar(value=value))
        self.rows.append(pair)

        def drop():
            if pair in self.rows:
                self.rows.remove(pair)
            row.destroy()
            self._placeholder()
            self.on_change()

        # порядок упаковки справа налево: ширина полей священна, тянуться
        # позволено только пустоте слева
        Button(row, "Убрать", drop, T.BG, w=70).pack(side="right", padx=(8, 0))
        Input(row, pair[1], T.BG, w=self.right_w).pack(side="right")
        tk.Label(row, text="→", bg=T.hx(T.BG), fg=T.hx(T.TEXT_FAINT),
                 font=(T.TK_SANS, -T.T_MD)).pack(side="right", padx=8)
        Input(row, pair[0], T.BG, w=self.left_w).pack(side="right")
        for var in pair:
            var.trace_add("write", lambda *_a: self.on_change())

    def value(self) -> dict:
        out: dict = {}
        for kv, vv in self.rows:
            k = kv.get().strip()
            if k:
                out[k] = vv.get()
        return out

    def blanks(self) -> int:
        """Строки без ключа. Они не сохранятся - и об этом надо сказать вслух,
        иначе человек напишет значение, закроет окно и потеряет его."""
        return sum(1 for kv, _vv in self.rows if not kv.get().strip())

    def _placeholder(self) -> None:
        if self.rows or self._empty is not None:
            return
        self._empty = tk.Label(self.host, text=self.empty_text, bg=T.hx(T.BG),
                               fg=T.hx(T.TEXT_FAINT), font=(T.TK_SANS, -T.T_SM))
        self._empty.pack(anchor="w", padx=ROW_PAD_X, pady=14)


class SettingsWindow:
    def __init__(self, root: tk.Tk, on_change, on_hotkey_capture, info_fn,
                 history_path: str, log_path: str):
        self.root = root
        self.on_change = on_change
        self.on_hotkey_capture = on_hotkey_capture
        self.info_fn = info_fn
        self.history_path = history_path
        self.log_path = log_path
        self.win: tk.Toplevel | None = None
        self.cfg = C.load()
        self._save_job = None
        self._flash_job = None
        self._pages: dict[str, tk.Frame] = {}
        self._page_canvas: dict[str, tk.Canvas] = {}
        self._nav: dict[str, NavItem] = {}
        self._page = "Основное"
        self._icon = None

    # ---------- окно ----------

    def open(self) -> None:
        if self.win is not None and self.win.winfo_exists():
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
            self._refresh_dynamic()
            return
        # Каждое открытие - свежий конфиг с диска и заново собранные контролы.
        # Прятать окно и показывать обратно дешевле, но тогда правка config.json
        # руками осталась бы не видна, а первое же изменение в окне записало бы
        # поверх неё старые значения.
        self.cfg = C.load()
        self._build()

    def _build(self) -> None:
        w = tk.Toplevel(self.root)
        self.win = w
        w.title("FlowLocal")
        w.configure(bg=T.hx(T.BG))
        w.minsize(W, H)
        w.geometry(self._centered())
        w.protocol("WM_DELETE_WINDOW", self.close)
        try:
            import icons

            self._icon = icons.tk_icon(64)
            w.wm_iconphoto(False, self._icon)
        except Exception:  # noqa: BLE001 - иконка не критична
            pass
        w.update_idletasks()
        style_titlebar(tk_hwnd(w), T.BG, dark=T.mode() == "dark")
        self._style_scrollbar(w)

        body = tk.Frame(w, bg=T.hx(T.BG))
        body.pack(fill="both", expand=True)

        side = tk.Frame(body, bg=T.hx(T.BG), width=SIDEBAR)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        self._build_sidebar(side)

        self._content = tk.Frame(body, bg=T.hx(T.BG))
        self._content.pack(side="left", fill="both", expand=True)

        for name, builder in self._page_defs():
            fr = tk.Frame(self._content, bg=T.hx(T.BG))
            self._pages[name] = fr
            builder(fr)

        self._footer = tk.Label(w, text="", bg=T.hx(T.BG), fg=T.hx(T.TEXT_MUTED),
                                font=(T.TK_MONO, -T.T_2XS), anchor="w")
        self._footer.pack(fill="x", padx=PAD, pady=(0, 10))
        self._show_page(self._page)
        w.bind("<Escape>", lambda _e: self._escape())
        w.bind_all("<MouseWheel>", self._on_wheel)

    def _escape(self) -> None:
        # во время захвата Esc отменяет захват, а не закрывает окно
        for name in ("_hotkey_box", "_toggle_box", "_undo_box"):
            hb = getattr(self, name, None)
            if hb is not None and hb.winfo_exists() and hb._capturing:
                hb.cancel()
                return
        self.close()

    @staticmethod
    def _style_scrollbar(w) -> None:
        """Родная tk.Scrollbar на Windows рисуется системной темой и остаётся
        светлой полосой посреди тёмного окна. ttk с темой clam красится целиком."""
        st = ttk.Style(w)
        try:
            st.theme_use("clam")
        except tk.TclError:
            return
        st.configure("Flow.Vertical.TScrollbar", gripcount=0, borderwidth=0,
                     relief="flat", arrowsize=12,
                     background=T.hx(T.FILL_STRONG_FLAT), darkcolor=T.hx(T.BG),
                     lightcolor=T.hx(T.BG), troughcolor=T.hx(T.BG),
                     bordercolor=T.hx(T.BG), arrowcolor=T.hx(T.TEXT_MUTED))
        # ховер по правилу системы: заливка на ступень выше, без смены цвета
        st.map("Flow.Vertical.TScrollbar",
               background=[("active", T.hx(T.flat(0.20)))])

    def _centered(self) -> str:
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        return f"{W}x{H}+{max(0, (sw - W) // 2)}+{max(0, (sh - H) // 3)}"

    def _page_defs(self):
        """Страницы и их конструкторы. Один список на боковое меню и на
        содержимое: раньше их было два, и они норовили разъехаться."""
        return (
            ("Основное", self._page_general),
            ("Распознавание", self._page_asr),
            ("Ввод", self._page_input),
            ("Словарь", self._page_dict),
            ("Замены", self._page_snippets),
            ("История", self._page_history),
            ("Статистика", self._page_stats),
            ("О программе", self._page_about),
        )

    def _build_sidebar(self, side) -> None:
        head = tk.Frame(side, bg=T.hx(T.BG))
        head.pack(fill="x", padx=14, pady=(20, 16))
        # Вордмарк: тяжёлый вес и тесный трекинг - как задан бренд в Korti
        tk.Label(head, text="FlowLocal", bg=T.hx(T.BG), fg=T.hx(T.TEXT),
                 font=("Onest ExtraBold", -T.T_XL)).pack(anchor="w")
        self._sub = tk.Label(head, text="", bg=T.hx(T.BG), fg=T.hx(T.TEXT_MUTED),
                             font=(T.TK_MONO, -T.T_2XS))
        self._sub.pack(anchor="w", pady=(2, 0))

        for name, _builder in self._page_defs():
            item = NavItem(side, name, lambda n=name: self._show_page(n), T.BG)
            item.pack(padx=14, pady=1, anchor="w")
            self._nav[name] = item

    def _show_page(self, name: str) -> None:
        self._page = name
        for n, fr in self._pages.items():
            fr.pack_forget()
            self._nav[n].set_active(n == name)
        self._pages[name].pack(fill="both", expand=True)
        if name == "История":
            self._reload_history()
        if name == "Статистика":
            self._reload_stats()
        if name == "О программе":
            self._refresh_about()
        self._refresh_dynamic()

    def rebuild(self) -> None:
        """Пересобрать окно с нуля - для смены темы.

        Часть красок впечатывается в виджеты при создании (фон канвы, цвет
        метки, тема заголовка окна), и перекрашивать их по одному дороже и
        ненадёжнее, чем собрать заново: окно и так пересобирается при каждом
        открытии. Конфиг с диска НЕ перечитываем - его только что записали,
        и чтение вернуло бы то же самое, зато затёрло бы правку, если запись
        ещё не долетела.
        """
        if self.win is None or not self.win.winfo_exists():
            return
        self.win.destroy()      # без _flush: нас позвали уже после записи
        self.win = None
        self._pages.clear()
        self._page_canvas.clear()
        self._nav.clear()
        self._build()           # _build сам вернётся на self._page

    def close(self) -> None:
        self.destroy()      # destroy() сам дописывает несохранённое

    def destroy(self) -> None:
        self._flush()
        if self.win is not None and self.win.winfo_exists():
            self.win.destroy()
        self.win = None
        self._pages.clear()
        self._page_canvas.clear()
        self._nav.clear()

    # ---------- сохранение ----------

    def _set(self, path: str, value) -> None:
        C.set_(self.cfg, path, value)
        self._flash("сохранено")
        if self._save_job:
            self.root.after_cancel(self._save_job)
        # склеиваем частые правки (перетаскивание слайдера) в одну запись
        self._save_job = self.root.after(350, self._flush)

    def _flush(self) -> None:
        if self._save_job:
            try:
                self.root.after_cancel(self._save_job)
            except Exception:  # noqa: BLE001
                pass
            self._save_job = None
        try:
            C.save(self.cfg)
        except OSError as e:
            self._flash(f"не удалось сохранить: {e}", T.DANGER)
            return
        self.on_change(dict(self.cfg))

    def _flash(self, text: str, color=None) -> None:
        if self.win is None or not self.win.winfo_exists():
            return
        self._footer.config(text=text, fg=T.hx(color or T.TEXT_MUTED))
        if self._flash_job:
            self.root.after_cancel(self._flash_job)
        self._flash_job = self.root.after(2200, lambda: self._footer.config(text=""))

    # ---------- конструктор строк ----------

    def _scroll_host(self, parent, page: str):
        """Страница с прокруткой: контента может стать больше окна."""
        canvas = tk.Canvas(parent, bg=T.hx(T.BG), highlightthickness=0, bd=0)
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=T.hx(T.BG))
        wid = canvas.create_window(0, 0, anchor="nw", window=inner)

        def resize(_e=None):
            canvas.itemconfig(wid, width=canvas.winfo_width())
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", resize)
        canvas.bind("<Configure>", resize)
        # колесо привязано ОДИН раз на всё окно (в _build), а канва ищется по
        # текущей странице: bind_all на каждой странице затирал бы предыдущий
        # обработчик, и крутилась бы всегда последняя созданная - невидимая
        self._page_canvas[page] = canvas
        return inner

    def _on_wheel(self, e) -> None:
        canvas = self._page_canvas.get(self._page)
        if canvas is None or not canvas.winfo_exists():
            return
        bbox = canvas.bbox("all")
        if bbox and bbox[3] > canvas.winfo_height():
            canvas.yview_scroll(-e.delta // 120, "units")

    def _section(self, parent, title: str, action=None) -> tk.Frame:
        # Заголовок раздела - моноширинная капсовая метка: голос терминала,
        # --tracking-caps. Пробелы имитируют разрядку: tkinter не умеет
        # letter-spacing, а метка короткая и это дешевле своего рендера.
        head = tk.Frame(parent, bg=T.hx(T.BG))
        head.pack(fill="x", padx=PAD, pady=(24, 8))
        tk.Label(head, text=" ".join(title.upper()), bg=T.hx(T.BG),
                 fg=T.hx(T.TEXT_MUTED), font=(T.TK_MONO, -T.T_2XS, "bold")
                 ).pack(side="left")
        if action is not None:      # кнопка раздела, например «Добавить»
            action(head)
        # Карточка делит фон со страницей и отделяется волосяной линией -
        # система опирается на линии, а не на заливки и тени
        card = Card(parent)
        card.pack(fill="x", padx=PAD)
        return card.body

    def _caption(self, parent, text: str) -> tk.Label:
        """Пояснение под карточкой - тише строк, но не мельче: его читают один
        раз, зато оно должно объяснить, зачем этот раздел вообще нужен."""
        lbl = tk.Label(parent, text=text, bg=T.hx(T.BG), fg=T.hx(T.TEXT_MUTED),
                       font=(T.TK_SANS, -T.T_SM), anchor="w", justify="left",
                       wraplength=560)
        lbl.pack(anchor="w", padx=PAD, pady=(8, 0))
        return lbl

    def _row(self, card, title: str, subtitle: str, ctl_factory, first: bool = False):
        if not first:
            # разделитель по краю содержимого, а не встык к рамке: у карточки
            # скруглены углы, и линия во всю ширину упиралась бы в дугу
            tk.Frame(card, bg=T.hx(T.BORDER_FLAT), height=1).pack(fill="x",
                                                                 padx=ROW_PAD_X)
        row = tk.Frame(card, bg=T.hx(T.BG))
        row.pack(fill="x", padx=ROW_PAD_X, pady=ROW_PAD_Y)
        # Контрол пакуется ПЕРВЫМ: pack раздаёт место в порядке вызовов, и
        # если первым идёт растягивающийся текст, он съедает ширину, а контрол
        # уезжает за край карточки. Ширина контрола священна, текст - перенесётся.
        ctl = ctl_factory(row)
        if ctl is not None:
            ctl.pack(side="right", padx=(14, 0))
        left = tk.Frame(row, bg=T.hx(T.BG))
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=title, bg=T.hx(T.BG), fg=T.hx(T.TEXT),
                 font=(T.TK_SANS, -T.T_BASE), anchor="w").pack(anchor="w")
        if subtitle:
            sub = tk.Label(left, text=subtitle, bg=T.hx(T.BG), fg=T.hx(T.TEXT_MUTED),
                           font=(T.TK_SANS, -T.T_SM), anchor="w", justify="left",
                           wraplength=360)
            sub.pack(anchor="w", pady=(2, 0))
            # Переносим по ФАКТИЧЕСКОЙ ширине колонки, а не по константе: ширина
            # зависит от контрола справа, и у широкого (поле захвата с крестиком)
            # текст с фиксированным wraplength вылезал под него и обрезался.
            # Сравнение с текущим значением обязательно: configure() вызывает
            # перекладку, та шлёт новый <Configure> - без него получилась бы петля.
            def rewrap(e, lbl=sub):
                w = max(120, e.width)
                if lbl.cget("wraplength") != w:
                    lbl.configure(wraplength=w)

            left.bind("<Configure>", rewrap)
        return ctl

    def _toggle_row(self, card, title, subtitle, path, first=False, on_set=None):
        def factory(parent):
            def changed(v):
                self._set(path, v)
                if on_set:
                    on_set(v)
            return Toggle(parent, C.get(self.cfg, path, False), changed, T.BG)

        return self._row(card, title, subtitle, factory, first)

    # ---------- страницы ----------

    def _bind_ctl(self, parent, path: str, attr: str):
        """Поле захвата сочетания плюс крестик «стереть».

        Крестик снаружи поля, а не внутри: поле целиком - кнопка «нажмите
        сочетание», и клик по крестику внутри неё запускал бы захват вместо
        очистки. Стереть можно любой бинд, включая диктовку: человек вправе
        оставить себе только один жест из двух.
        """
        wrap = tk.Frame(parent, bg=T.hx(T.BG))
        box = HotkeyBox(wrap, str(C.get(self.cfg, path, "") or ""),
                        lambda v: self._set(path, v), T.BG,
                        on_capture=self.on_hotkey_capture, allow_clear=True)
        setattr(self, attr, box)
        box.pack(side="left")
        Button(wrap, "×", box.clear, T.BG, w=30).pack(side="left", padx=(6, 0))
        return wrap

    def _page_general(self, p) -> None:
        host = self._scroll_host(p, "Основное")
        card = self._section(host, "Диктовка")

        self._hotkey_box = None
        self._row(card, "Удерживать и говорить",
                  "Зажали - говорите, отпустили - текст вставился. "
                  "Можно назначить и боковую кнопку мыши",
                  lambda pr: self._bind_ctl(pr, "hotkey_hold", "_hotkey_box"),
                  first=True)

        self._toggle_box = None
        self._row(card, "Нажать и говорить",
                  "Нажали - пишем, нажали ещё раз - стоп. Руки свободны, "
                  "Esc отменяет запись",
                  lambda pr: self._bind_ctl(pr, "hotkey_toggle", "_toggle_box"))

        def mic(parent):
            self._mic_select = Select(parent, self._mic_options(),
                                      C.get(self.cfg, "mic_device"),
                                      lambda v: self._set("mic_device", v),
                                      T.BG, w=290)
            return self._mic_select

        self._row(card, "Микрофон", "Применится при следующей записи", mic)

        self._undo_box = None
        self._row(card, "Отменить последнюю диктовку",
                  "Уберёт ровно то, что вставило приложение - и только если "
                  "после вставки вы ничего не печатали",
                  lambda pr: self._bind_ctl(pr, "undo_hotkey", "_undo_box"))

        card2 = self._section(host, "Вид")

        def theme(parent):
            return Segmented(parent, THEMES, C.get(self.cfg, "theme", "system"),
                             lambda v: self._set("theme", v), T.BG)

        self._row(card2, "Оформление",
                  "«система» - как настроено в Windows", theme, first=True)

        card3 = self._section(host, "Система")

        # автозапуск живёт в реестре, а не в config.json - поэтому не _toggle_row
        def auto(parent):
            self._auto_toggle = Toggle(parent, self._get_autostart(),
                                       self._set_autostart, T.BG)
            return self._auto_toggle

        self._row(card3, "Запускать вместе с Windows",
                  "FlowLocal свернётся в трей при входе в систему", auto, first=True)
        self._toggle_row(card3, "Звуковые сигналы",
                         "Короткий тон на старте и в конце записи", "sounds")
        self._toggle_row(card3, "Вести историю",
                         "Записывать распознанный текст в history.jsonl", "history")

    def _page_asr(self, p) -> None:
        host = self._scroll_host(p, "Распознавание")
        card = self._section(host, "Модель")

        def model(parent):
            return Segmented(parent, MODELS, C.get(self.cfg, "model"),
                             self._on_model, T.BG)

        self._row(card, "Модель",
                  "GigaAM - для русского: 226 МБ, процессора хватает. Остальные - "
                  "если диктуете и на других языках. Скачается в models/ при "
                  "следующем запуске", model, first=True)

        def lang(parent):
            return Segmented(parent, LANGS, C.get(self.cfg, "language"),
                             lambda v: self._set("language", v), T.BG)

        self._row(card, "Язык",
                  "Только для Whisper и Parakeet. GigaAM знает один язык - русский",
                  lang)

        def dev(parent):
            return Segmented(parent, DEVICES, C.get(self.cfg, "device"),
                             lambda v: self._restart_needed("device", v), T.BG)

        self._row(card, "Устройство",
                  "«авто»: видеокарта, если onnxruntime собран с CUDA, иначе "
                  "процессор. Для GigaAM разницы почти нет", dev)

        card2 = self._section(host, "Обработка текста")
        self._toggle_row(card2, "Убирать «э-э» и «ммм»",
                         "Консервативные правила: только однозначные междометия",
                         "remove_fillers", first=True)
        self._toggle_row(card2, "Полировка локальной LLM",
                         "Через Ollama: убирает слова-паразиты, учитывает самоисправления",
                         "llm.enabled", on_set=lambda _v: self._refresh_dynamic())

        self._llm_url_row = self._row(card2, "Адрес Ollama", "",
                                      lambda p: self._entry("llm.url", p))
        self._llm_model_row = self._row(card2, "Модель Ollama",
                                        "Например qwen2.5:3b - быстрая и достаточная",
                                        lambda p: self._entry("llm.model", p))

    def _page_input(self, p) -> None:
        host = self._scroll_host(p, "Ввод")
        card = self._section(host, "Вставка")

        def mode(parent):
            return Segmented(parent, INSERT, C.get(self.cfg, "insert_mode"),
                             lambda v: self._set("insert_mode", v), T.BG)

        self._row(card, "Способ",
                  "«вставка» - через буфер и Ctrl+V, мгновенно. "
                  "«посимвольно» - для окон, где Ctrl+V не срабатывает",
                  mode, first=True)
        self._toggle_row(card, "Пробел в конце",
                         "Чтобы следующая фраза не слиплась с предыдущей", "append_space")
        self._toggle_row(card, "Возвращать буфер обмена",
                         "После вставки вернуть то, что лежало в буфере до неё",
                         "restore_clipboard")

        card2 = self._section(host, "Микрофон")
        self._toggle_row(card2, "Держать микрофон открытым",
                         "Не режет первое слово: поток пишет всегда, "
                         "начало берётся из пре-буфера",
                         "keep_mic_open", first=True)

        def pre(parent):
            return Slider(parent, 0.0, 1.5, 0.1, C.get(self.cfg, "pre_buffer_sec", 0.5),
                          lambda v: self._set("pre_buffer_sec", round(v, 2)),
                          T.BG, w=130, fmt="{:.1f} с")

        self._row(card2, "Пре-буфер",
                  "Сколько секунд звука до нажатия попадёт в запись", pre)

        def mn(parent):
            return Slider(parent, 0.1, 1.5, 0.1, C.get(self.cfg, "min_record_sec", 0.3),
                          lambda v: self._set("min_record_sec", round(v, 2)),
                          T.BG, w=130, fmt="{:.1f} с")

        self._row(card2, "Игнорировать нажатия короче",
                  "Защита от случайных касаний хоткея", mn)

    def _page_dict(self, p) -> None:
        self._label_caps(p, "Словарь")
        tk.Label(p, text="Имена, термины и названия. Похожее слово в распознанном "
                         "тексте починится по этому написанию. По одному на строку.",
                 bg=T.hx(T.BG), fg=T.hx(T.TEXT_SECONDARY), font=(T.TK_SANS, -T.T_BASE),
                 anchor="w", justify="left").pack(anchor="w", padx=PAD, pady=(0, 12))
        box = Card(p, autosize=False)
        box.pack(fill="both", expand=True, padx=PAD)
        self._dict_text = tk.Text(
            box.body, bg=T.hx(T.BG), fg=T.hx(T.TEXT), font=(T.TK_MONO, -T.T_SM),
            insertbackground=T.hx(T.ACCENT),
            selectbackground=T.hx(T.mix(T.PAPER, T.ACCENT, 0.30)),
            selectforeground=T.hx(T.TEXT),
            relief="flat", highlightthickness=0, bd=0, padx=14, pady=12, undo=True)
        self._dict_text.pack(fill="both", expand=True)
        self._dict_text.insert("1.0", "\n".join(C.get(self.cfg, "dictionary", []) or []))
        self._dict_text.bind("<KeyRelease>", lambda _e: self._dict_changed())
        bar = tk.Frame(p, bg=T.hx(T.BG))
        bar.pack(fill="x", padx=PAD, pady=12)
        self._dict_count = tk.Label(bar, text="", bg=T.hx(T.BG), fg=T.hx(T.TEXT_MUTED),
                                    font=(T.TK_MONO, -T.T_2XS))
        self._dict_count.pack(side="left")
        self._update_dict_count()

    @staticmethod
    def _label_caps(parent, title: str, side=None):
        lbl = tk.Label(parent, text=" ".join(title.upper()), bg=T.hx(T.BG),
                       fg=T.hx(T.TEXT_MUTED), font=(T.TK_MONO, -T.T_2XS, "bold"))
        if side:
            lbl.pack(side=side)
        else:
            lbl.pack(anchor="w", padx=PAD, pady=(24, 8))
        return lbl

    def _dict_changed(self) -> None:
        words = [w.strip() for w in self._dict_text.get("1.0", "end").splitlines()]
        self._set("dictionary", [w for w in words if w])
        self._update_dict_count()

    def _update_dict_count(self) -> None:
        n = len(C.get(self.cfg, "dictionary", []) or [])
        self._dict_count.config(
            text=f"{n} {plural(n, 'слово', 'слова', 'слов')} в словаре" if n
            else "словарь пуст")

    # ---------- замены ----------

    def _page_snippets(self, p) -> None:
        host = self._scroll_host(p, "Замены")

        card = self._section(host, "Замены", action=lambda h: Button(
            h, "Добавить", lambda: self._snip.add(), T.BG,
            kind="primary").pack(side="right"))
        self._snip = PairTable(card, self._snippets_changed,
                               "пока пусто - нажмите «Добавить»")
        self._snip.fill(C.get(self.cfg, "snippets", {}) or {})
        self._snip_note = self._caption(
            host, "Сказали «моя почта» - вставился адрес. Подстановка идёт после "
                  "распознавания, целыми словами, без учёта регистра. Слева - что "
                  "говорите, справа - что вставится.")

        card2 = self._section(host, "Тон под приложение", action=lambda h: Button(
            h, "Добавить", lambda: self._tone.add(), T.BG).pack(side="right"))
        self._tone = PairTable(card2, self._tone_changed,
                               "правил нет - тон не меняется")
        self._tone.fill(C.get(self.cfg, "tone_rules", {}) or {})
        self._tone_note = self._caption(host, "")
        self._update_pair_notes()

    def _snippets_changed(self) -> None:
        self._set("snippets", self._snip.value())
        self._update_pair_notes()

    def _tone_changed(self) -> None:
        self._set("tone_rules", self._tone.value())
        self._update_pair_notes()

    def _update_pair_notes(self) -> None:
        n = len(self._snip.value())
        note = ("Сказали «моя почта» - вставился адрес. Подстановка идёт после "
                "распознавания, целыми словами, без учёта регистра. Слева - что "
                "говорите, справа - что вставится.")
        if self._snip.blanks():
            # строка без фразы не сохранится - сказать сразу, а не после закрытия
            note += (f"  Строк без фразы: {self._snip.blanks()} - они не сохранятся.")
        elif n:
            note += f"  Сейчас {n} {plural(n, 'замена', 'замены', 'замен')}."
        self._snip_note.config(text=note)

        # Тон целиком зависит от Ollama - если полировка выключена, правила
        # лежат мёртвым грузом, и об этом честнее сказать прямо здесь, чем
        # оставить человека гадать, почему ничего не меняется.
        on = bool(C.get(self.cfg, "llm.enabled"))
        tone = ("Слева - имя программы (outlook.exe), справа - тон словами "
                "(«формально», «дружелюбно»). Тон переписывает текст вторым "
                "проходом LLM: это добавит секунды к задержке.")
        tone += ("  Полировка LLM включена - правила работают." if on else
                 "  Полировка LLM выключена, поэтому правила сейчас не "
                 "применяются: включите её на вкладке «Распознавание».")
        if self._tone.blanks():
            tone += f"  Строк без программы: {self._tone.blanks()} - не сохранятся."
        self._tone_note.config(text=tone)

    # ---------- статистика ----------

    def _page_stats(self, p) -> None:
        host = self._scroll_host(p, "Статистика")
        self._stat_labels: dict[str, tk.Label] = {}
        card = self._section(host, "Итого")
        self._stat_row(card, "Диктовок", "Сколько раз вы нажимали хоткей",
                       "dictations", first=True)
        self._stat_row(card, "Слов надиктовано", "По всей истории", "words")
        self._stat_row(card, "Средняя длина", "Слов за одну диктовку", "avg_words")
        self._stat_row(card, "Под запись", "Сколько всего звучал микрофон", "seconds")
        self._stat_row(card, "Сэкономлено против набора",
                       f"Оценка: речь ~{stats.SPEECH_WPM} слов/мин против "
                       f"~{stats.TYPING_WPM} слов/мин на клавиатуре", "saved_sec")

        card2 = self._section(host, "По дням")
        chart_row = tk.Frame(card2, bg=T.hx(T.BG))
        chart_row.pack(fill="x", padx=ROW_PAD_X, pady=ROW_PAD_Y)
        self._stat_chart = BarChart(chart_row, [], T.BG, w=560, h=120)
        self._stat_chart.pack(anchor="w")
        self._stat_range = tk.Label(chart_row, text="", bg=T.hx(T.BG),
                                    fg=T.hx(T.TEXT_MUTED), font=(T.TK_MONO, -T.T_2XS))
        self._stat_range.pack(anchor="w", pady=(8, 0))

    def _stat_row(self, card, title: str, subtitle: str, key: str, first: bool = False):
        def factory(parent):
            # Число - моноширинным: это метаданные, и цифры табличные, поэтому
            # соседние строки не пляшут по ширине.
            lbl = tk.Label(parent, text="—", bg=T.hx(T.BG), fg=T.hx(T.TEXT),
                           font=(T.TK_MONO, -T.T_LG))
            self._stat_labels[key] = lbl
            return lbl

        return self._row(card, title, subtitle, factory, first)

    def _reload_stats(self) -> None:
        rows = stats.load(self.history_path)
        s = stats.summary(rows)
        n = s["dictations"]
        w = s["words"]
        text = {
            "dictations": f"{n}",
            "words": f"{w}",
            "avg_words": f"{s['avg_words']:.0f}",
            "seconds": _dur(s["seconds"]),
            "saved_sec": _dur(s["saved_sec"]),
        }
        for key, lbl in self._stat_labels.items():
            if lbl.winfo_exists():
                lbl.config(text=text.get(key, "—"))
        days = stats.by_day(rows, 30)
        self._stat_chart.set_values([v for _d, v in days])
        if days:
            top = max(v for _d, v in days)
            self._stat_range.config(
                text=f"{days[0][0]} - {days[-1][0]}   ·   пик {top} "
                     f"{plural(top, 'слово', 'слова', 'слов')} в день")
        else:
            self._stat_range.config(text="пока пусто - продиктуйте что-нибудь")

    def _page_history(self, p) -> None:
        head = tk.Frame(p, bg=T.hx(T.BG))
        head.pack(fill="x", padx=PAD, pady=(24, 8))
        self._label_caps(head, "История", side="left")
        Button(head, "Очистить", self._clear_history, T.BG, kind="danger").pack(side="right")
        Button(head, "Обновить", self._reload_history, T.BG).pack(side="right", padx=6)

        box = Card(p, autosize=False)
        box.pack(fill="both", expand=True, padx=PAD)
        sb = ttk.Scrollbar(box.body, orient="vertical", style="Flow.Vertical.TScrollbar")
        sb.pack(side="right", fill="y")
        self._hist = tk.Text(box.body, bg=T.hx(T.BG), fg=T.hx(T.TEXT),
                             font=(T.TK_SANS, -T.T_BASE), relief="flat",
                             highlightthickness=0, bd=0, padx=14, pady=12, wrap="word",
                             yscrollcommand=sb.set, state="disabled", cursor="arrow",
                             selectbackground=T.hx(T.mix(T.PAPER, T.ACCENT, 0.30)),
                             selectforeground=T.hx(T.TEXT), spacing2=3)
        self._hist.pack(fill="both", expand=True)
        sb.config(command=self._hist.yview)
        # метаданные (время, длительность) - моноширинным: голос терминала
        self._hist.tag_config("meta", foreground=T.hx(T.TEXT_MUTED),
                              font=(T.TK_MONO, -T.T_2XS), spacing1=10)
        self._hist.tag_config("text", foreground=T.hx(T.TEXT), spacing3=8)
        self._hist_note = tk.Label(p, text="", bg=T.hx(T.BG), fg=T.hx(T.TEXT_MUTED),
                                   font=(T.TK_MONO, -T.T_2XS))
        self._hist_note.pack(anchor="w", padx=PAD, pady=12)

    def _reload_history(self) -> None:
        rows = []
        try:
            with open(self.history_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            rows.append(json.loads(line))
                        except ValueError:
                            pass
        except OSError:
            pass
        self._hist.config(state="normal")
        self._hist.delete("1.0", "end")
        for r in reversed(rows[-400:]):          # свежие сверху
            self._hist.insert("end", f"{r.get('ts', '')}   ·   {r.get('sec', 0)} с\n",
                              "meta")
            self._hist.insert("end", f"{r.get('text', '')}\n", "text")
        self._hist.config(state="disabled")
        total = sum(len(r.get("text", "").split()) for r in rows)
        n = len(rows)
        self._hist_note.config(
            text=f"{n} {plural(n, 'диктовка', 'диктовки', 'диктовок')} · "
                 f"примерно {total} {plural(total, 'слово', 'слова', 'слов')}" if rows
            else "пока пусто - продиктуйте что-нибудь")

    def _clear_history(self) -> None:
        try:
            open(self.history_path, "w", encoding="utf-8").close()
        except OSError as e:
            self._flash(f"не удалось очистить: {e}", T.DANGER)
            return
        self._reload_history()
        self._flash("история очищена")

    def _page_about(self, p) -> None:
        wrap = tk.Frame(p, bg=T.hx(T.BG))
        wrap.pack(fill="both", expand=True, padx=PAD, pady=24)
        # Дисплейный кегль: тяжёлый вес, тесный трекинг - так задан бренд
        tk.Label(wrap, text="FlowLocal", bg=T.hx(T.BG), fg=T.hx(T.TEXT),
                 font=("Onest ExtraBold", -T.T_3XL)).pack(anchor="w")
        tk.Label(wrap, text="Приватная диктовка. Звук и текст не покидают компьютер.",
                 bg=T.hx(T.BG), fg=T.hx(T.TEXT_SECONDARY),
                 font=(T.TK_SANS, -T.T_MD)).pack(anchor="w", pady=(4, 24))
        card = Card(wrap)
        card.pack(fill="x")
        self._about = tk.Label(card.body, text="", bg=T.hx(T.BG),
                               fg=T.hx(T.TEXT_SECONDARY), font=(T.TK_MONO, -T.T_XS),
                               justify="left", anchor="w")
        self._about.pack(anchor="w", padx=ROW_PAD_X, pady=24 - Card.INSET)

        bar = tk.Frame(wrap, bg=T.hx(T.BG))
        bar.pack(anchor="w", pady=16)
        Button(bar, "Папка приложения", lambda: self._reveal(C.APP_DIR), T.BG).pack(side="left")
        Button(bar, "config.json", lambda: self._open(C.CONFIG_PATH),
               T.BG).pack(side="left", padx=8)
        Button(bar, "Лог", lambda: self._open(self.log_path), T.BG).pack(side="left")

    def _refresh_about(self) -> None:
        info = self.info_fn()
        lines = [f"{k:<14} {v}" for k, v in info.items()]
        self._about.config(text="\n".join(lines))

    # ---------- динамика ----------

    def _refresh_dynamic(self) -> None:
        """Подтянуть то, что зависит от состояния приложения и других настроек."""
        if self.win is None or not self.win.winfo_exists():
            return
        info = self.info_fn()
        self._sub.config(text=info.get("состояние", ""))
        if hasattr(self, "_auto_toggle"):
            self._auto_toggle.set(self._get_autostart())
        if hasattr(self, "_mic_select"):
            self._mic_select.set_options(self._mic_options(),
                                         C.get(self.cfg, "mic_device"))
        # поля Ollama бессмысленны при выключенной полировке
        on = bool(C.get(self.cfg, "llm.enabled"))
        for w in (getattr(self, "_llm_url_row", None), getattr(self, "_llm_model_row", None)):
            if w is not None and w.winfo_exists():
                w.set_enabled(on)
        # та же полировка решает, работают ли правила тона - подпись про это
        # живёт на другой странице и про переключатель сама не узнает
        if getattr(self, "_tone_note", None) is not None and self._tone_note.winfo_exists():
            self._update_pair_notes()

    def _mic_options(self):
        from recorder import list_input_devices

        out = [("Системный по умолчанию", None)]
        for idx, name, api in list_input_devices():
            out.append((f"{name} · {api}", idx))
        return out

    def _entry(self, path: str, parent, w: int = 240):
        var = tk.StringVar(value=str(C.get(self.cfg, path, "") or ""))
        field = Input(parent, var, T.BG, w=w)
        var.trace_add("write", lambda *_a: self._set(path, var.get().strip()))
        return field

    def _restart_needed(self, path: str, value) -> None:
        self._set(path, value)
        self._flash("применится после перезапуска FlowLocal", T.ACCENT)

    def _on_model(self, model_id: str) -> None:
        """Модель едет вместе со своей квантизацией: у каждой в каталоге своя.

        Без этого выбор Whisper поверх int8-настройки GigaAM отправил бы
        загрузчик искать несуществующий файл.
        """
        m = models.get(model_id)
        C.set_(self.cfg, "quantization", models.quant_for(model_id))
        self._set("model", model_id)
        size = f"{m.size_mb} МБ, {m.langs}. " if m else ""
        self._flash(f"{size}Скачается и применится после перезапуска", T.ACCENT)

    # ---------- автозапуск ----------

    @staticmethod
    def _get_autostart() -> bool:
        import app_paths

        return app_paths.autostart_enabled()

    def _set_autostart(self, value: bool) -> None:
        import app_paths

        try:
            app_paths.set_autostart(bool(value))
            self._flash("автозапуск включён" if value else "автозапуск выключен")
        except OSError as e:
            self._flash(f"не удалось: {e}", T.DANGER)

    # ---------- файлы ----------

    def _open(self, path: str) -> None:
        try:
            if not os.path.exists(path):
                open(path, "a", encoding="utf-8").close()
            os.startfile(path)  # noqa: S606 - открыть в ассоциированном приложении
        except OSError as e:
            self._flash(f"не удалось открыть: {e}", T.DANGER)

    def _reveal(self, path: str) -> None:
        try:
            subprocess.Popen(["explorer", os.path.normpath(path)])
        except OSError as e:
            self._flash(f"не удалось открыть: {e}", T.DANGER)
