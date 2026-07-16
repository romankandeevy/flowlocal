"""Превью окна настроек: каждая страница в обеих темах, одной картинкой.

Нужно, чтобы сверять оформление с системой Korti глазами, а не на слово: тут
видно и скругления карточек (12px) с полями ввода (6px), и что светлая тема не
оставила где-то чёрный текст на чёрном.

    python tools/preview_settings.py

Модель и микрофон не нужны: приложение не поднимается, окно настроек живёт само
по себе на заглушках.
"""

import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import layered

# До создания любого окна, включая tk.Tk(): иначе на мониторе с масштабом >100%
# Windows отдаст растянутый мыльный интерфейс, и превью будет врать.
layered.set_dpi_awareness()

import tkinter as tk

from PIL import Image, ImageGrab

import theme as T
from settings import SettingsWindow

OUT = os.path.join(ROOT, "tools", "preview_settings.png")
GAP = 24
LABEL_H = 26


def fake_info() -> dict:
    """То же по форме, что отдаёт App._info, но без модели и микрофона."""
    return {
        "состояние": "large-v3-turbo · cuda",
        "модель": "large-v3-turbo",
        "устройство": "cuda / float16",
        "микрофон": "Микрофон (превью) · WASAPI",
        "хоткей": "ctrl+shift+space",
        "python": sys.version.split()[0],
        "папка": ROOT,
    }


def fake_history(path: str) -> None:
    """Синтетическая история: без неё страница статистики пустая и проверять
    на ней нечего. Настоящий history.jsonl не трогаем - там живые диктовки."""
    rows = []
    words = ["слово"] * 3
    for day in range(12):
        for k in range((day * 7) % 5 + 1):
            n = 4 + (day * 3 + k * 5) % 40
            rows.append({
                "ts": f"2026-07-{4 + day:02d} 1{k}:20:11",
                "sec": round(2.5 + n / 9, 1),
                "text": " ".join(words * (n // 3 + 1))[:n * 6],
            })
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def shoot(win: tk.Toplevel) -> Image.Image:
    """Снимок окна по его геометрии на экране.

    ImageGrab, а не отрисовка в PIL: настройки - это настоящие виджеты tkinter,
    нарисовать их мимо экрана нечем. Отсюда и требование: окно должно быть
    поверх и успеть отрисоваться.
    """
    win.update_idletasks()
    win.update()
    time.sleep(0.35)
    x, y = win.winfo_rootx(), win.winfo_rooty()
    return ImageGrab.grab((x, y, x + win.winfo_width(), y + win.winfo_height()))


def pages_for_theme(theme: str) -> list[tuple[str, Image.Image]]:
    # Тему ставим ДО создания окна: фон канвы и цвет метки виджеты запоминают
    # при создании, а не читают на каждый кадр.
    T.set_theme(theme)
    root = tk.Tk()
    root.withdraw()
    hist = os.path.join(tempfile.gettempdir(), f"flowlocal-preview-{theme}.jsonl")
    fake_history(hist)
    w = SettingsWindow(root, lambda _c: None, lambda _a: None, fake_info,
                       hist, os.path.join(ROOT, "flow.log"))
    w.open()
    w.win.attributes("-topmost", True)
    shots = []
    for name in list(w._pages):          # список страниц - из окна, не хардкодом
        w._show_page(name)
        shots.append((f"{name} · {theme}", shoot(w.win)))
        print("  снято:", name)
    w.destroy()
    root.destroy()
    try:
        os.unlink(hist)
    except OSError:
        pass
    return shots


def contact_sheet(shots: list[tuple[str, Image.Image]], cols: int) -> Image.Image:
    from PIL import ImageDraw

    cw = max(s.width for _n, s in shots)
    ch = max(s.height for _n, s in shots)
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (cw + GAP) + GAP,
                              rows * (ch + LABEL_H + GAP) + GAP), (28, 28, 30))
    d = ImageDraw.Draw(sheet)
    f = T.font(13, T.W_SEMIBOLD)
    for i, (name, img) in enumerate(shots):
        x = GAP + (i % cols) * (cw + GAP)
        y = GAP + (i // cols) * (ch + LABEL_H + GAP)
        d.text((x, y), name, font=f, fill=(235, 235, 240))
        sheet.paste(img, (x, y + LABEL_H))
    return sheet


def main() -> None:
    shots = []
    for theme in ("light", "dark"):
        print(f"--- тема {theme}")
        shots += pages_for_theme(theme)
    # по странице в столбце: светлая сверху, тёмная снизу - так расхождения
    # между темами видно сразу, а не листанием
    contact_sheet(shots, cols=len(shots) // 2).save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
