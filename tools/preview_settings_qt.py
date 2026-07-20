"""Контактный лист окна: все страницы, обе темы.

    python tools/preview_settings_qt.py            # обе темы, в tools/
    python tools/preview_settings_qt.py dark       # только тёмная
    python tools/preview_settings_qt.py --show     # показать окно, ничего не снимать

Окно одно (1060x700), страниц семь: Главная, История, Статистика, Диктовка,
Слова, Дополнительно, О программе. Их список окно отдаёт само, свойством
`pages`, - так витрина не может отстать от программы, когда страницу добавят.

**Почему здесь свой конфиг, а не настоящий.** Прошлое превью снималось с живого
приложения - и вместе с интерфейсом сняло почту из «Замен» и расшифровки из
«Истории». В репозиторий такая картинка уехать не должна, а `.gitignore` её не
ловит: для него это просто png, личное внутри он не видит.

Поэтому снимаем не с живого. `config.load` и `config.save` подменены: скрипт
физически не может ни прочитать ваш `config.json`, ни записать в него. История -
синтетическая, здесь же в файле. Защита структурная, а не по договорённости:
забыть подчистить конфиг перед съёмкой теперь нельзя, потому что настоящий
конфиг сюда не попадает вовсе.

Заодно демо-данные показывают то, чего пустой конфиг не покажет: словарь с
терминами, замену, правило тона. Пустые страницы - плохая витрина.
"""

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import config as C  # noqa: E402

# Демо-конфиг: пример из репозитория плюс то, что стоит показать в витрине.
# Ничего личного здесь нет и быть не может - файл лежит в гите.
DEMO = json.load(open(os.path.join(ROOT, "config.example.json"), encoding="utf-8"))
DEMO.update({
    "hotkey_toggle": "ctrl+mouse4",
    "undo_hotkey": "ctrl+shift+z",
    "dictionary": ["Соколов", "Кубернетес", "Постгрес"],
    "snippets": {"моя почта": "hello@example.com",
                 "адрес офиса": "Ленина 1, офис 42"},
    "tone_rules": {"outlook.exe": "формально", "telegram.exe": "дружелюбно"},
})

# Подмена до любого импорта, который дёрнет конфиг. save - в никуда: превью не
# имеет права трогать диск пользователя.
C.load = lambda path=None: json.loads(json.dumps(DEMO))
C.save = lambda cfg, path=None: None

# Сегодняшний день тоже подменяем. Даты в демо-истории прибиты намеренно (см.
# ниже), а `stats.summary` без аргумента берёт date.today() - и «Дней подряд»
# зависит от того, когда снимают витрину: 16-17 июля это 3, 18-го уже 0.
# Картинка обязана быть одинаковой в любой день, иначе гит видит diff на
# полумегабайтном png, а в README уезжает ноль.
import datetime as _dt  # noqa: E402

import stats as _stats  # noqa: E402

# Ollama тоже подменяем. У владельца она стоит, и витрина снималась бы в
# состоянии «всё уже установлено» - то есть кнопку установки, которую увидит
# любой другой человек, на картинке было бы не разглядеть. Показываем то, что
# видит большинство, а не то, что видит разработчик.
import ollama_setup as _ollama  # noqa: E402

_ollama.serving = lambda timeout=1.5: False
_ollama.has_model = lambda name: False
# exe() тоже: с задачи 9 окна различают «не установлена» и «установлена, но
# молчит», и различают по наличию файла на диске. У владельца файл есть - без
# этой подмены витрина показывала бы «не отвечает» на его машине и «не
# установлена» на любой другой, то есть снова зависела бы от того, кто снимает.
_ollama.exe = lambda: ""

_DEMO_TODAY = _dt.date(2026, 7, 16)          # последний день демо-истории
_summary = _stats.summary
_stats.summary = lambda rows, today=None: _summary(rows, today or _DEMO_TODAY)
# `week` подменяем по той же причине и той же подменой: недельный график
# заканчивается НАСТОЯЩИМ сегодня (иначе акцентом подсвечивался бы не тот
# столбик - см. его docstring), а значит без подмены картинка ехала бы каждый
# день, и через неделю после съёмки витрина показывала бы семь нулей.
_week = _stats.week
_stats.week = lambda rows, today=None: _week(rows, today or _DEMO_TODAY)

# История: правдоподобная, но выдуманная. Даты фиксированные, иначе картинка
# меняется от каждого прогона и гит видит diff там, где ничего не менялось.
DEMO_HISTORY = [
    ("2026-07-14 10:02:11", 4.1, "Собери, пожалуйста, сводку по продажам за июнь "
                                 "и пришли до конца дня."),
    ("2026-07-14 10:05:03", 1.2, "Встречу двигаем на четверг."),
    ("2026-07-14 11:41:55", 7.8, "Черновик письма: поблагодарить за встречу, "
                                 "напомнить про сроки, приложить смету. "
                                 "Тон - формальный."),
    ("2026-07-15 09:12:40", 2.6, "Добавь в тесты случай с пустой строкой."),
    ("2026-07-15 09:30:07", 0.9, "Готово."),
    ("2026-07-16 12:20:18", 5.4, "Стратегическая сессия начинается в пятницу "
                                 "в 10:00 утра."),
]


def _seed_history(path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for ts, sec, text in DEMO_HISTORY:
            f.write(json.dumps({"ts": ts, "sec": sec, "words": len(text.split()),
                                "text": text}, ensure_ascii=False) + "\n")


# Заметки для витрины страницы «Заметки». Как и история - выдуманные и с
# фиксированными датами: страница читает НАСТОЯЩИЙ каталог заметок (notes.DIR),
# и без подмены витрина сняла бы личные заметки того, кто её собирает, ровно как
# когда-то сняла почту из «Замен». Пишем файлы напрямую, а не через notes.save:
# так дата «updated» фиксирована, и картинка не едет от прогона к прогону.
DEMO_NOTES = [
    ("20260716-143000", "2026-07-16 14:30:00",
     "Разбор конкурента\nПосмотрел их приложение: слева список заметок, справа "
     "редактор. Понравилось, что причесать можно одной кнопкой. Забрать себе: "
     "карточки со временем и превью первой строки."),
    ("20260715-101200", "2026-07-15 10:12:00",
     "Идеи к встрече в пятницу: сначала цифры за квартал, потом план на "
     "следующий, в конце - вопросы от команды."),
    ("20260714-090500", "2026-07-14 09:05:00",
     "Список покупок: хлеб, молоко, кофе, батарейки."),
]


def _seed_notes(dir_: str) -> None:
    os.makedirs(dir_, exist_ok=True)
    for nid, updated, text in DEMO_NOTES:
        with open(os.path.join(dir_, nid + ".json"), "w", encoding="utf-8") as f:
            json.dump({"id": nid, "created": nid, "updated": updated,
                       "text": text}, f, ensure_ascii=False)


def _info() -> dict:
    """То же, что app._info(), но без живого транскрайбера и микрофона.

    Ключи обязаны совпадать с настоящими: превью - это витрина, и если она
    показывает поля, которых в приложении нет, она врёт. Разъедется - заметит
    тот, кто будет по ней сверяться, то есть уже поздно.
    """
    return {
        "состояние": "готов · Ctrl + Shift + Space",
        "версия": "0.2.0",
        "распознаёт": "GigaAM · русский",
        "слушает": "Microphone (Realtek)",
        "диктовать": "Ctrl + Shift + Space · Ctrl + Мышь 4",
        "понимает поправки": "да",
        # Служебные ключи для статус-строки «Главной». В «О программе» они не
        # видны (about() пропускает подчёркивание), но без них витрина сняла бы
        # статус-строку без модели и устройства - то есть не то, что видит
        # человек.
        "_device": "cpu",
        "_model": "gigaam-v2-ctc",
    }


def shoot(mode: str, out: str, tmp: str) -> None:
    import theme as T

    T.set_theme(mode)
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    from settings_qt import SettingsWindow

    app = QApplication.instance() or QApplication(sys.argv)

    def settle(ms: int) -> None:
        """Дать Qt отрисоваться. grabWindow() снимает то, что уже нарисовано, а
        не то, что мы только что попросили: без паузы страница снимется старая."""
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    # Список страниц окно отдаёт само, свойством `pages`. Витрина обязана
    # показывать всю программу, а не тот набор страниц, который кто-то однажды
    # переписал сюда руками.
    shots = []
    win = SettingsWindow(lambda *_a: None, lambda *_a: None, _info,
                         os.path.join(tmp, "history.jsonl"),
                         os.path.join(tmp, "flow.log"))
    win.open()
    root = win.view.rootObject()
    # pages в QML - обычный JS-массив, из Python он приезжает QJSValue,
    # а не списком: разворачиваем.
    pages = root.property("pages").toVariant()
    settle(700)                       # первый кадр: шрифты, QML, титул
    for page in pages:
        root.setProperty("page", page)
        # Ждём не переход между страницами, а анимации появления: count-up
        # чисел на Главной и волну столбцов на Статистике. Витрина должна
        # снять дорисованный экран, а не застать графику на полпути.
        #
        # После приведения движения к токенам (PLAN, задача 8) обе стали
        # короче: 280 мс на число и 520 мс на волну столбцов с учётом
        # лесенки. Паузу оставляем прежней - она с запасом, а подгонять её
        # под текущие числа значило бы ловить их заново при каждой правке
        # токенов.
        settle(950)
        img = win.view.grabWindow()
        p = os.path.join(tmp, f"_pg_{len(shots)}.png")
        img.save(p)
        shots.append((page, p))
    win.view.hide()

    from PIL import Image, ImageDraw, ImageFont
    # Шрифт подписей - свой: у шрифта PIL по умолчанию нет кириллицы, и
    # «Основное» превращалось в ряд ▯▯▯. Тот же Onest, что и в интерфейсе.
    try:
        label = ImageFont.truetype(
            os.path.join(ROOT, "assets", "fonts", "Onest-Variable.ttf"), 15)
    except OSError:
        label = ImageFont.load_default()

    imgs = [(name, Image.open(p).convert("RGB")) for name, p in shots]
    cols = 3
    pad, top = 16, 26
    # Снимки одного окна, значит все одного размера: колонка одна на весь лист.
    # Считать ширину по строке приходилось, пока окон было два и второе было
    # вдвое уже; теперь это лишняя развилка.
    grid = [imgs[i:i + cols] for i in range(0, len(imgs), cols)]
    w = max(i.width for _n, i in imgs)
    h = max(i.height for _n, i in imgs)
    # Подложка в цвет темы: лист - это витрина, а не отладка.
    bg = (18, 18, 18) if mode == "dark" else (245, 245, 245)
    ink = (150, 150, 150) if mode == "dark" else (110, 110, 110)
    sheet = Image.new(
        "RGB",
        (cols * w + (cols + 1) * pad,
         len(grid) * (h + top + pad) + pad), bg)
    d = ImageDraw.Draw(sheet)
    y = pad
    for row in grid:
        for n, (name, img) in enumerate(row):
            x = pad + n * (w + pad)
            d.text((x + 2, y), f"{name} · {mode}", fill=ink, font=label)
            sheet.paste(img, (x, y + top))
        y += h + top + pad
    sheet.save(out)
    print(f"{out}: {len(imgs)} страниц, тема {mode}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    modes = [args[0]] if args else ["light", "dark"]
    tmp = tempfile.mkdtemp(prefix="flowlocal_preview_")
    _seed_history(os.path.join(tmp, "history.jsonl"))
    open(os.path.join(tmp, "flow.log"), "w").close()

    # Заметки читают свой каталог напрямую (notes.DIR), а не мокнутый конфиг:
    # уводим его в tmp с выдуманными заметками, иначе витрина снимет личные.
    import notes  # noqa: E402

    notes.DIR = os.path.join(tmp, "notes")
    _seed_notes(notes.DIR)

    import theme as T

    T.register_fonts()               # до окна: иначе интерфейс без шрифтов
    for mode in modes:
        shoot(mode, os.path.join(ROOT, "tools", f"preview_settings_qt_{mode}.png"), tmp)


if __name__ == "__main__":
    main()
