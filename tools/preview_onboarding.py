"""Контактный лист мастера первого запуска: все экраны, обе темы.

Скрипта до сих пор не было - картинка в README снималась руками. Значит и
проверить мастер было нечем: экран, добавленный неделю назад, никто не видел
целиком, а именно этот мастер человек проходит ровно один раз, и второго
впечатления не будет.

Как и у превью настроек, всё поддельное намеренно. Конфиг подменён, приложение
поддельное, микрофон рисует синтетическую волну, Ollama «не установлена» -
чтобы витрина показывала то, что видит новый человек, а не то, что видит
разработчик на своей обжитой машине.

    python tools/preview_onboarding.py
    python tools/preview_onboarding.py dark
"""

import json
import os
import sys

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import config as C  # noqa: E402

DEMO = json.load(open(os.path.join(ROOT, "config.example.json"), encoding="utf-8"))
C.load = lambda path=None: json.loads(json.dumps(DEMO))
C.save = lambda cfg, path=None: None

# Ollama «нет»: новый человек видит именно это состояние, и ради него экран и
# существует. На машине разработчика она стоит, и витрина показывала бы «всё
# уже готово» - то есть самое интересное было бы не видно.
import ollama_setup as _O  # noqa: E402

_O.serving = lambda timeout=1.5: False
_O.has_model = lambda name: False

import theme as T  # noqa: E402

T.register_fonts()

from PIL import Image  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import models  # noqa: E402


class FakeRecorder:
    """Микрофон, которого нет: волна на третьем экране должна шевелиться."""

    def __init__(self):
        self.fell_back = False
        self._n = 0

    def drain_levels(self):
        import math
        import random

        self._n += 1
        return [0.02 + 0.12 * abs(math.sin(self._n / 3)) * random.uniform(0.5, 1.2)
                for _ in range(3)]

    def start(self):
        pass

    def stop(self):
        import numpy as np

        return np.zeros(16000, dtype="float32")


class FakeApp:
    """Столько приложения, сколько нужно мастеру."""

    def __init__(self):
        self.cfg = C.load()
        self.recorder = FakeRecorder()
        self.transcriber = None
        self.onboarding = None

    def _on_config_change(self, new):
        self.cfg = new

    def _on_hotkey_capture(self, on):
        pass

    def install_ollama(self, on_stage=None):
        pass

    def ui(self, fn, *a):
        fn(*a)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode = args[0] if args else "light"
    T.set_theme(mode)

    app = QApplication(sys.argv)
    from onboarding_qt import OnboardingWindow

    win = OnboardingWindow(FakeApp())
    win.open()
    root = win.view.rootObject()
    last = int(root.property("last"))

    shots = []

    def grab(step: int):
        def fn():
            root.setProperty("step", step)
            QTimer.singleShot(450, lambda: _save(step))
        return fn

    def _save(step: int):
        img = win.view.grabWindow()
        path = os.path.join(ROOT, "tools", f"_ob_{step}.png")
        img.save(path)
        shots.append(path)

    # По 900 мс на экран: анимации входа должны доиграть, иначе в витрину
    # попадёт недорисованное - на этом уже обжигались с графиком статистики.
    for i in range(last + 1):
        QTimer.singleShot(600 + i * 900, grab(i))

    def sheet():
        ims = [Image.open(p).convert("RGB") for p in shots]
        if not ims:
            print("нечего клеить")
            app.quit()
            return
        cols = 2
        rows = (len(ims) + cols - 1) // cols
        w, h = ims[0].size
        gap = 16
        out = Image.new("RGB", (cols * w + (cols + 1) * gap,
                                rows * h + (rows + 1) * gap),
                        (24, 24, 24) if T.mode() == "light" else (245, 245, 245))
        for i, im in enumerate(ims):
            x = gap + (i % cols) * (w + gap)
            y = gap + (i // cols) * (h + gap)
            out.paste(im, (x, y))
        name = f"preview_onboarding{'' if mode == 'light' else '_dark'}.png"
        out.save(os.path.join(ROOT, "tools", name))
        for p in shots:
            os.remove(p)
        print(f"tools/{name}: {len(ims)} экранов, тема {T.mode()}")
        app.quit()

    QTimer.singleShot(600 + (last + 1) * 900 + 700, sheet)
    app.exec()


if __name__ == "__main__":
    main()
