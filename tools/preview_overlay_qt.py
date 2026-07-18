"""Живое превью Qt-оверлея: все состояния по кругу, микрофон не нужен.

Аналог tools/preview_overlay.py для PIL-версии, но тот собирал контактный лист
картинкой, а этот показывает настоящее окно - потому что проверять надо ровно
то, что картинкой не проверяется: флаги окна, удержание фокуса, живую анимацию
и то, что волна не схлопывается в ниточку.

    python tools/preview_overlay_qt.py            # цикл состояний, тема из системы
    python tools/preview_overlay_qt.py dark       # принудительно тёмная
    python tools/preview_overlay_qt.py light --shot tools/preview_overlay_qt.png

Уровни синтетические. Ловушка, на которой уже обжигались: генерить их на каждый
вызов level_fn() нечестно - на живом микрофоне уровни приходят ~31/с, а кадров
60/с, и на большинстве кадров новых данных нет. Поэтому здесь они отдаются с
той же частотой, что и настоящие, - иначе превью покажет то, чего не бывает.
"""

import math
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

import theme as T  # noqa: E402

# До создания окна - как в app.py: иначе интерфейс останется без шрифтов.
T.register_fonts()

from overlay_qt import Overlay  # noqa: E402

LEVEL_HZ = 1000 / T.LEVEL_MS          # столько уровней в секунду даёт recorder


class FakeMic:
    """Уровни как из recorder.drain_levels(): «те, что появились с прошлого
    вызова», а не «последние N». Молчит между тиками - и это главное.

    Речь модулируется слогами (~4.5 Гц) и изредка прерывается короткой паузой.
    Первая версия генератора качала синус на 1.7 рад/с и уходила в тишину на
    1.85 с подряд - превью показывало ровную ниточку и выглядело как баг
    осциллограммы. Живая речь так не молчит: если полоски легли, значит либо
    правда тишина, либо сломано, и путать эти два случая превью не должно.

    У каждого уровня своё время, а не «время вызова»: за один тик их набегает
    сразу несколько, и с общим временем вся пачка вышла бы одинаковой.
    """

    def __init__(self) -> None:
        self.t0 = time.perf_counter()
        self.produced = 0

    def __call__(self) -> list[float]:
        want = int((time.perf_counter() - self.t0) * LEVEL_HZ)
        n = want - self.produced
        if n <= 0:
            return []                  # новых данных нет - так и должно быть
        out = []
        for i in range(self.produced, want):
            t = i / LEVEL_HZ
            syllable = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * 4.5 * t))
            pause = 0.05 if (t % 3.2) < 0.45 else 1.0     # вдох между фразами
            room = 0.0005                                  # шум тихой комнаты
            out.append(room + pause * syllable * random.uniform(0.05, 0.18))
        self.produced = want
        return out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    shot = None
    if "--shot" in sys.argv:
        shot = sys.argv[sys.argv.index("--shot") + 1]
    T.set_theme(args[0] if args else "system")

    app = QGuiApplication(sys.argv)
    ov = Overlay(level_fn=FakeMic())

    # Сценарий - настоящий путь диктовки, а не список состояний: так видно
    # переходы, ради которых всё и затевалось.
    script = [
        (0.0, lambda: ov.show_loading()),
        (1.8, lambda: (ov.set_hint(""), ov.show_recording())),
        (5.0, lambda: ov.show_processing()),
        (6.4, lambda: ov.show_done("готово")),
        # Единственная оставшаяся надпись-канал: скачивание обновления. Все
        # подсказки с пилюли ушли 18.07.2026, показывать там больше нечего.
        (7.6, lambda: (ov.set_hint("обновление 0.3.1"), ov.show_processing())),
        (9.0, lambda: (ov.set_hint(""), ov.show_recording())),
        # Тишину включаем напрямую: FakeMic всегда «говорит», а настоящий
        # детект (_pump_bars) ждал бы 3 с честного молчания. Hint при этом
        # гасим: надпись «не слышно» уступает подсказке, и в toggle-режиме
        # (где hint есть) её не увидеть - показываем случай удержания.
        (10.2, lambda: ov.root.setProperty("silence", True)),
        (11.2, lambda: ov.show_error("модель не загрузилась")),
        (13.5, lambda: ov.hide()),
    ]
    for at, fn in script:
        QTimer.singleShot(int(at * 1000), fn)

    if shot:
        # Контактный лист: каждое состояние снимается в свой момент и клеится
        # в столбик. Снимать одно «красивое» состояние нечестно - ломается
        # обычно соседнее.
        frames: list = []

        def grab(tag: str):
            def fn():
                img = ov.view.grabWindow()
                frames.append((tag, img))
            return fn

        for at, tag in ((0.9, "loading"), (4.2, "recording"), (5.6, "processing"),
                        (6.8, "done"), (8.4, "обновление"),
                        (11.0, "recording+тишина"), (12.0, "error")):
            QTimer.singleShot(int(at * 1000), grab(tag))

        def sheet():
            from PIL import Image
            shots = []
            for tag, img in frames:
                img.save(os.path.join(os.environ.get("TEMP", "."), f"_ov_{tag}.png"))
                shots.append((tag, Image.open(
                    os.path.join(os.environ.get("TEMP", "."), f"_ov_{tag}.png")).convert("RGBA")))
            if not shots:
                return
            w = max(s.width for _t, s in shots)
            h = sum(s.height for _t, s in shots)
            # Подложка в цвет противоположной темы: пилюля всплывает над чужим
            # окном, и тень с волосяной линией обязаны читаться на любом фоне.
            bg = (255, 255, 255, 255) if T._mode == "dark" else (24, 24, 24, 255)
            sheet_img = Image.new("RGBA", (w, h), bg)
            y = 0
            for _tag, s in shots:
                sheet_img.alpha_composite(s, ((w - s.width) // 2, y))
                y += s.height
            sheet_img.save(shot)
            print(f"контактный лист ({len(shots)} состояний): {shot}")

        QTimer.singleShot(int(13.0 * 1000), sheet)

    QTimer.singleShot(int(15.0 * 1000), app.quit)
    print("Показываю цикл состояний ~14 с. Фокус не должен уходить из этого окна.")
    app.exec()


if __name__ == "__main__":
    main()
