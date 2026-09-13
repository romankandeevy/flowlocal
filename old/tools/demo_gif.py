"""Демо-гифка для README: зажал - сказал - отпустил - текст на месте.

Что здесь настоящее, а что подделка - по пунктам, потому что гифка в README
это обещание, и оно должно быть выполнимым:

  настоящее   пилюля (overlay_qt.Overlay - тот же класс, что в приложении),
              её анимации, осциллограмма, распознавание (GigaAM v3 RNN-T int8
              на процессоре) и время, которое оно заняло на этой машине;
              текст в письме - дословный вывод модели, не набранный руками
  подделка    окно почты (снять чужое настоящее нельзя, не сняв заодно чужую
              переписку) и клавиши-бейджи (подпись к жесту)
  вместо мик- звук берётся из test.wav, а не с микрофона: скрипт должен давать
  рофона      один и тот же результат на любой машине и не зависеть от того,
              что в комнате

Уровни считаются той же формулой, что в recorder.py (RMS по LEVEL_N сэмплов),
и отдаются по правилу drain_levels: «появившиеся с прошлого вызова». Иначе
осциллограмма показала бы то, чего на живом микрофоне не бывает.

    python tools/demo_gif.py                 # светлая тема -> tools/demo.gif
    python tools/demo_gif.py dark
    python tools/demo_gif.py --fps 12 --out tools/demo_dark.gif
"""

import os
import sys
import threading
import time
import wave

# Масштаб фиксируем ДО QGuiApplication: гифка должна выходить одинаковой на
# любом мониторе, а не в полтора раза больше на ноутбуке с 150%.
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage  # noqa: E402
from PySide6.QtQuick import QQuickView  # noqa: E402

import theme as T  # noqa: E402

T.register_fonts()          # до создания окон, иначе интерфейс без шрифтов

import config  # noqa: E402
from cleaner import clean  # noqa: E402
from overlay_qt import Overlay  # noqa: E402
from theme_qt import Tokens  # noqa: E402
from transcriber import Transcriber  # noqa: E402
from util import plural  # noqa: E402

SR = 16000
LEVEL_N = SR * T.LEVEL_MS // 1000

# Из test.wav берём вторую фразу: первая («проверка связи») в кадре не нужна, а
# эта показывает и пунктуацию, и нормализацию числа («в 10:00 утра») - то, чего
# Whisper на том же файле не дал вовсе.
CLIP = (2.25, 7.30)

LEAD = 0.45         # сколько кадров до нажатия: пустое окно должно быть видно
TAIL = 0.70         # хвост после ухода пилюли, чтобы петля не рвалась встык


def _audio() -> np.ndarray:
    with wave.open("test.wav") as w:
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        data = raw.astype(np.float32) / 32768.0
        if w.getnchannels() == 2:
            data = data.reshape(-1, 2).mean(axis=1)
        if w.getframerate() != SR:
            raise SystemExit(f"test.wav должен быть {SR} Гц, а он {w.getframerate()}")
    return data[int(CLIP[0] * SR):int(CLIP[1] * SR)]


class WavMic:
    """Уровни из файла - ровно так, как их отдаёт recorder.drain_levels().

    «Появившиеся с прошлого вызова», а не «последние N»: оверлей досыпает их в
    осциллограмму, и повтор дал бы стоячую картинку. Формула RMS - из
    recorder._on_audio, чтобы волна в гифке была той же, что на микрофоне.
    """

    def __init__(self, audio: np.ndarray) -> None:
        self.audio = audio
        self.t0 = 0.0
        self.sent = 0

    def start(self) -> None:
        self.t0 = time.perf_counter()
        self.sent = 0

    def __call__(self) -> list[float]:
        if not self.t0:
            return []
        want = min(int((time.perf_counter() - self.t0) * SR) // LEVEL_N,
                   len(self.audio) // LEVEL_N)
        out = []
        for i in range(self.sent, want):
            chunk = self.audio[i * LEVEL_N:(i + 1) * LEVEL_N]
            out.append(float(np.sqrt(np.mean(chunk * chunk)) + 1e-9))
        self.sent = want
        return out


def _pil(img: QImage) -> Image.Image:
    img = img.convertToFormat(QImage.Format_RGBA8888)
    return Image.frombytes("RGBA", (img.width(), img.height()),
                           bytes(img.constBits())).copy()


def _save_gif(frames: list[Image.Image], stamps: list[float], out: str) -> None:
    """Общая палитра на всю гифку.

    По палитре на кадр GIF раздувается вдвое и на переходах идёт рябью: у
    соседних кадров разъезжаются одни и те же чернила. Палитру берём с кадров,
    где на экране всё сразу - пилюля с тенью и текст, - иначе в ней не окажется
    полутонов, которыми они нарисованы.
    """
    picks = [frames[i] for i in range(len(frames) // 3, len(frames), max(1, len(frames) // 6))]
    stack = Image.new("RGB", (frames[0].width, frames[0].height * len(picks)))
    for i, f in enumerate(picks):
        stack.paste(f.convert("RGB"), (0, i * f.height))
    master = stack.quantize(colors=128, method=Image.MEDIANCUT)

    out_frames = [f.convert("RGB").quantize(palette=master, dither=Image.Dither.NONE)
                  for f in frames]
    # Длительности - измеренные, а не номинальные: захват кадра занимает
    # десятки миллисекунд, и по номиналу гифка играла бы быстрее, чем всё это
    # происходило на самом деле.
    durs = [max(20, int(round((stamps[i + 1] - stamps[i]) * 100)) * 10)
            for i in range(len(stamps) - 1)]
    durs.append(durs[-1] if durs else 60)
    out_frames[0].save(out, save_all=True, append_images=out_frames[1:],
                       duration=durs, loop=0, disposal=1, optimize=False)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode = args[0] if args else "light"
    fps = int(sys.argv[sys.argv.index("--fps") + 1]) if "--fps" in sys.argv else 16
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv \
        else os.path.join("tools", "demo.gif")
    T.set_theme(mode)

    audio = _audio()
    rec_sec = len(audio) / SR

    app = QGuiApplication(sys.argv)

    # Конфиг - умолчания, а не config.load(): в живом конфиге лежат словарь с
    # именами и замены с почтой владельца, и clean() вставил бы их в кадр.
    cfg = config._merge(config.DEFAULTS, {})
    cfg["llm"]["enabled"] = False        # полировка требует Ollama, в гифке её нет

    tr = Transcriber(cfg, lambda m: print("  " + m))
    print("гружу модель...")
    tr.load()

    tokens = Tokens(1.0)
    scene = QQuickView()
    scene.setColor(QColor(*T.BG[:3]))
    scene.rootContext().setContextProperty("T", tokens)
    scene.setSource(QUrl.fromLocalFile(os.path.join(ROOT, "tools", "demo_scene.qml")))
    if scene.status() == QQuickView.Error:
        raise SystemExit("; ".join(str(e) for e in scene.errors()))
    root = scene.rootObject()
    scene.show()

    mic = WavMic(audio)
    ov = Overlay(level_fn=mic)
    # Пилюлю никуда не ставим: в кадр она попадает подклейкой, а не съёмкой
    # экрана. _place() иначе увёл бы её на край монитора и подмешал бы туда
    # масштаб экрана, от которого мы только что избавились.
    ov._place = lambda: None
    ov.tokens.set_scale(1.0)

    frames: list[Image.Image] = []
    stamps: list[float] = []
    done: dict = {}

    def grab() -> None:
        img = _pil(scene.grabWindow()).convert("RGB")
        if ov.view.isVisible():
            pill = _pil(ov.view.grabWindow())
            img.paste(pill, ((img.width - pill.width) // 2, img.height - pill.height),
                      pill)
        frames.append(img)
        stamps.append(time.perf_counter())

    def transcribe() -> None:
        """Работает в своём потоке, как worker в app.py, и по той же причине
        ничего не трогает в Qt напрямую: результат кладётся в dict, забирает
        его главный поток. QTimer из чужого потока молча не заводится - на
        этом скрипт уже висел, набирая кадры до упора."""
        t0 = time.perf_counter()
        try:
            text = clean(tr.transcribe(audio), cfg, lambda m: None)
        except Exception as e:  # noqa: BLE001 - иначе поток умрёт молча
            done.update(err=repr(e))
            return
        done.update(text=text, sec=time.perf_counter() - t0)

    def landed(text: str) -> None:
        root.setProperty("body", text)
        n = len(text.split())
        ov.show_done(f"{n} {plural(n, 'слово', 'слова', 'слов')}")
        print(f"распознано за {done['sec']:.2f} с: {text}")

    def press() -> None:
        root.setProperty("held", True)
        mic.start()
        ov.set_hint("")
        ov.show_recording()

    def release() -> None:
        root.setProperty("held", False)
        ov.show_processing()
        threading.Thread(target=transcribe, daemon=True).start()

    QTimer.singleShot(int(LEAD * 1000), press)
    QTimer.singleShot(int((LEAD + rec_sec) * 1000), release)

    ticker = QTimer()
    ticker.timeout.connect(grab)
    ticker.start(int(1000 / fps))

    def finish() -> None:
        ticker.stop()
        print(f"кадров: {len(frames)}, {(stamps[-1] - stamps[0]):.1f} с")
        _save_gif(frames, stamps, out)
        print(f"{out}: {os.path.getsize(out) / 1024 / 1024:.2f} МБ")
        app.quit()

    # Конца ждём по факту (распознавание длится сколько длится), а не по
    # расписанию: захардкоженная секунда однажды обрежет кадр на полуслове.
    # Но и ждать вечно нельзя - сорвавшийся поток оставлял бы кадры копиться,
    # пока не кончится память. Отсюда потолок.
    watch = QTimer()

    def check() -> None:
        if done.get("err"):
            watch.stop()
            raise SystemExit(f"распознавание упало: {done['err']}")
        if "text" in done and not done.get("shown"):
            done["shown"] = True
            landed(done["text"])
        if done.get("shown") and not ov.view.isVisible():
            watch.stop()
            QTimer.singleShot(int(TAIL * 1000), finish)
        elif len(frames) > fps * 40:
            watch.stop()
            raise SystemExit("сценарий не кончился за 40 с - смотри, где встал")

    watch.timeout.connect(check)
    watch.start(50)

    app.exec()


if __name__ == "__main__":
    main()
