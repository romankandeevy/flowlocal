"""Контактный лист окна настроек: все страницы, обе темы.

    python tools/preview_settings_qt.py            # обе темы, в tools/
    python tools/preview_settings_qt.py dark       # только тёмная
    python tools/preview_settings_qt.py --show     # показать окно, ничего не снимать

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

_DEMO_TODAY = _dt.date(2026, 7, 16)          # последний день демо-истории
_summary = _stats.summary
_stats.summary = lambda rows, today=None: _summary(rows, today or _DEMO_TODAY)

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
    }


def shoot(mode: str, out: str, tmp: str) -> None:
    import theme as T

    T.set_theme(mode)
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    from settings_qt import SettingsWindow

    app = QApplication.instance() or QApplication(sys.argv)
    win = SettingsWindow(lambda *_a: None, lambda *_a: None, _info,
                         os.path.join(tmp, "history.jsonl"),
                         os.path.join(tmp, "flow.log"))
    win.open()
    root = win.view.rootObject()
    # pages в QML - обычный JS-массив, из Python он приезжает QJSValue,
    # а не списком: разворачиваем.
    pages = root.property("pages").toVariant()

    def settle(ms: int) -> None:
        """Дать Qt отрисоваться. grabWindow() снимает то, что уже нарисовано, а
        не то, что мы только что попросили: без паузы страница снимется старая."""
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    settle(700)                       # первый кадр: шрифты, QML, титул
    shots = []
    for page in pages:
        root.setProperty("page", page)
        # Ждём не переход между страницами (280 мс хватало), а анимации
        # появления: count-up чисел на Главной (~520 мс) и волну столбцов на
        # Статистике (~650 мс). Витрина должна снять дорисованный экран, а не
        # застать графику на полпути.
        settle(950)
        img = win.view.grabWindow()
        p = os.path.join(tmp, f"_pg_{pages.index(page)}.png")
        img.save(p)
        shots.append((page, p))

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
    rows = (len(imgs) + cols - 1) // cols
    w = max(i.width for _n, i in imgs)
    h = max(i.height for _n, i in imgs)
    pad, top = 16, 26
    # Подложка в цвет темы: лист - это витрина, а не отладка.
    bg = (18, 18, 18) if mode == "dark" else (245, 245, 245)
    ink = (150, 150, 150) if mode == "dark" else (110, 110, 110)
    sheet = Image.new("RGB", (cols * w + (cols + 1) * pad,
                              rows * (h + top) + (rows + 1) * pad), bg)
    d = ImageDraw.Draw(sheet)
    for n, (name, img) in enumerate(imgs):
        x = pad + (n % cols) * (w + pad)
        y = pad + (n // cols) * (h + top + pad)
        d.text((x + 2, y), f"{name} · {mode}", fill=ink, font=label)
        sheet.paste(img, (x, y + top))
    sheet.save(out)
    print(f"{out}: {len(imgs)} страниц, тема {mode}")
    win.view.hide()


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    modes = [args[0]] if args else ["light", "dark"]
    tmp = tempfile.mkdtemp(prefix="flowlocal_preview_")
    _seed_history(os.path.join(tmp, "history.jsonl"))
    open(os.path.join(tmp, "flow.log"), "w").close()

    import theme as T

    T.register_fonts()               # до окна: иначе интерфейс без шрифтов
    for mode in modes:
        shoot(mode, os.path.join(ROOT, "tools", f"preview_settings_qt_{mode}.png"), tmp)


if __name__ == "__main__":
    main()
