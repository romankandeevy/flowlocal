"""Бэкенд распознавания FlowLocal для macOS.

Живёт отдельным процессом рядом со Swift-приложением и говорит с ним через
stdin/stdout. Модели те же, что в old/: GigaAM (русский) через onnx-asr, и
Parakeet TDT 0.6b v2 для английского переспроса.

Главное - распознавание НА ХОДУ (порт old/streaming.py): пока человек говорит,
сказанное режется по паузам и разбирается сразу, и после отпускания клавиши
остаётся только хвост. Минута речи на этом Маке целиком - около 13 с ожидания,
на ходу - доли секунды.

Протокол - строки JSON; звук идёт сразу после заголовка сырыми байтами
(float32 little-endian, 16 кГц, моно):

    -> {"cmd": "begin", "id": 7, "lang": "auto"}
    -> {"cmd": "audio", "id": 7, "samples": 4000} + байты      каждые ~0.25 с
    -> {"cmd": "finish", "id": 7}
    <- {"id": 7, "text": "...", "lang": "ru", "sec": 0.31, "audio_sec": 60.2,
        "streamed_sec": 55.1, "tail_sec": 5.1, "spec_hit": false, "parts": 7}
    -> {"cmd": "cancel", "id": 7}
    -> {"cmd": "transcribe", "id": 8, "samples": N} + байты     запасной путь: целиком

    <- {"event": "ready", "model": "ru"|"en"}
    <- {"event": "error", "message": "..."}

Проверка без приложения:

    .venv/bin/python server.py --file запись.wav          целиком
    .venv/bin/python server.py --stream-file запись.wav   как при диктовке, в реальном времени
"""

import json
import os
import re
import shutil
import sys
import threading
import time
import wave

import numpy as np

import langdetect

SR = 16000
HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.environ.get("FLOWLOCAL_MODELS", os.path.join(HERE, "models"))
RU_MODEL = "gigaam-v3-e2e-rnnt"
EN_MODEL = "nemo-parakeet-tdt-0.6b-v2"
QUANT = "int8"
# Два потока, и это замер на этом Маке (i5-8210Y, 2 ядра / 4 потока), а не
# привычка: 28.8 с речи - 4.0 с на двух потоках против 5.9 с на четырёх.
# Гиперпотоки делят те же два ядра, и на int8 это только мешает.
THREADS = 2

# Запасной путь (целиком): кусок не длиннее 30 с, рез в самой тихой паузе.
# У GigaAM потолок 200 с, а память самовнимания растёт квадратом от длины
# (old/transcriber.py); короче кусок - меньше работы.
MAX_SEC = 30.0
SEEK_SEC = 8.0

# --- разбор на ходу (old/streaming.py) --------------------------------------
WIN = int(0.2 * SR)          # окно громкости
QUIET_RATIO = 0.18           # пауза - заметно тише среднего по куску
MIN_TAIL_SEC = 5.0           # с какой длины берёмся резать (~10-12 слов)
KEEP_TAIL_SEC = 1.8          # последние 1.8 с не трогаем: человек ещё говорит
MAX_FEED_SEC = 10.0          # кусок не длиннее: отпускание не ждёт долгий кусок
LONG_PAUSE_WINS = 3          # пауза от 0.6 с - граница фразы, режем по ней
SHORT_PAUSE_OK_SEC = 12.0    # 200 мс паузы хватает, только если накопилось столько
# Упреждение начинаем рано: живой замер - человек отпускает клавишу сразу за
# последним словом, и при 0.35 с тишины и раз в 2 с заготовка не успевала
# начаться вовсе (46 с речи, хвост 2.6 с, ожидание 1.4 с). Начатая заранее,
# она к отпусканию уже наполовину посчитана - finish её дождётся.
SPEC_SILENCE_SEC = 0.3       # тишина в конце - «договорил», разбираем заранее
SPEC_MIN_GAP_SEC = 1.0
MIN_PIECE_SEC = 1.0          # куски короче - лишний прогон модели и риск разрезать слово
SPEC_MAX_TAIL_SEC = 10.0
TICK = 0.2

_out_lock = threading.Lock()
_proto = sys.stdout


def emit(obj: dict) -> None:
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    with _out_lock:
        _proto.write(line)
        _proto.flush()


def log(msg: str) -> None:
    sys.stderr.write(f"[backend] {msg}\n")
    sys.stderr.flush()


def claim_stdout() -> None:
    """Протокол - на своём дескрипторе, а fd 1 уводим в stderr.

    Любой print библиотеки или C-кода в stdout без перевода строки приклеился
    бы к следующей строке протокола, и Swift выбросил бы её вместе с ответом.
    """
    global _proto
    fd = os.dup(1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    _proto = os.fdopen(fd, "w", buffering=1, encoding="utf-8")


# --- язык --------------------------------------------------------------------

_LATIN = re.compile(r"[A-Za-z]+")
_CYRILLIC = re.compile(r"[А-Яа-яЁё]+")


def is_english(text: str) -> bool:
    """Английская ли фраза, судя по выходу GigaAM.

    langdetect из old/ ловит английскую речь, записанную кириллицей, - так
    пишет GigaAM v2. Но v3 e2e пишет её латиницей, и наугад («Place end meda
    Report by Friday» вместо «Please send me the report by Friday»), а
    langdetect смотрит только кириллицу и такого не видит вовсе.

    Второй признак поэтому - латиница без русского. Строгий нарочно, по тому
    же правилу, что в old/: ложное срабатывание дороже пропуска. «Сделай PR в
    main branch» остаётся русской: русские слова в ней есть, латинских мало.
    """
    lat = len(_LATIN.findall(text))
    cyr = len(_CYRILLIC.findall(text))
    return (langdetect.looks_english(text)
            or (lat >= 2 and cyr == 0)
            or (lat >= 4 and lat >= 3 * cyr))


def majority(parts: list[tuple[str, str]]) -> str:
    en = sum(len(t.split()) for t, lang in parts if lang == "en")
    ru = sum(len(t.split()) for t, lang in parts if lang != "en")
    return "en" if en > ru else "ru"


# --- модели ------------------------------------------------------------------

def _session_options():
    import onnxruntime as rt

    so = rt.SessionOptions()
    so.intra_op_num_threads = THREADS
    so.inter_op_num_threads = 1
    # Не жечь ядро busy-wait'ом между фразами (замер в old/transcriber.py:
    # 2.28 с процессора на фразу против 0.92 при той же скорости).
    so.add_session_config_entry("session.force_spinning_stop", "1")
    return so


def load(name: str):
    """Загрузка модели. Папку удаляем ТОЛЬКО если в ней не хватает файлов.

    onnx-asr считает существующую папку офлайн-копией и сам докачивать в неё не
    пойдёт, поэтому оборванную скачку приходится сносить. Но любая другая
    ошибка (не хватило памяти, сломался onnxruntime) - не повод удалять
    скачанные сотни мегабайт: без сети приложение осталось бы без моделей.
    """
    import onnx_asr
    try:
        from onnx_asr.utils import ModelFileNotFoundError
    except ImportError:  # другая версия onnx-asr
        ModelFileNotFoundError = FileNotFoundError

    d = os.path.join(MODELS_DIR, name + "-" + QUANT)
    kw = dict(path=d, quantization=QUANT, providers=["CPUExecutionProvider"],
              sess_options=_session_options())
    t0 = time.time()
    try:
        model = onnx_asr.load_model(name, **kw)
    except (ModelFileNotFoundError, FileNotFoundError) as e:
        if not os.path.isdir(d):
            raise
        log(f"{name}: {e} - папка неполная, качаю заново")
        shutil.rmtree(d, ignore_errors=True)
        model = onnx_asr.load_model(name, **kw)
    # Прогрев: первый прогон инициализирует кернелы.
    model.recognize(np.zeros(SR, dtype=np.float32), sample_rate=SR)
    log(f"{name} загружена за {time.time() - t0:.1f} с")
    return model


def window_power(audio: np.ndarray) -> np.ndarray:
    n = audio.size // WIN
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    return np.abs(audio[:n * WIN].reshape(n, WIN)).mean(axis=1)


def cut_points(audio: np.ndarray) -> list[int]:
    """Запасной путь: границы не длиннее MAX_SEC, рез в самой тихой паузе."""
    step = int(MAX_SEC * SR)
    seek = int(SEEK_SEC * SR)
    points, pos = [], 0
    while audio.size - pos > step:
        hard = pos + step
        start = max(pos, hard - seek)
        power = window_power(audio[start:hard])
        cut = start + int(np.argmin(power)) * WIN + WIN // 2 if power.size >= 2 else hard
        cut = max(cut, pos + step // 2)
        points.append(cut)
        pos = cut
    return points


def recognize(model, audio: np.ndarray) -> str:
    if audio.size < SR // 20:
        return ""
    bounds = [0, *cut_points(audio), audio.size]
    parts = []
    for a, b in zip(bounds, bounds[1:]):
        got = str(model.recognize(audio[a:b], sample_rate=SR) or "").strip()
        if got:
            parts.append(got)
    return " ".join(parts).strip()


# --- паузы -------------------------------------------------------------------

def find_pause(audio: np.ndarray, allow_short: bool) -> tuple[int, float] | None:
    """(позиция реза, длина паузы в секундах) или None.

    Ищем в уже сказанном - не ближе KEEP_TAIL_SEC к концу. Берём САМУЮ
    ПОЗДНЮЮ паузу: чем больше отдадим модели сейчас, тем меньше останется на
    конец. Длинная пауза (от 0.6 с) - граница фразы, и e2e-точка на стыке там
    к месту. Паузу в 200 мс берём, только если allow_short: это может быть
    вдох посреди фразы, и точка на таком стыке была бы лишней.
    """
    usable = audio.size - int(KEEP_TAIL_SEC * SR)
    if usable < WIN * 3:
        return None
    power = window_power(audio[:usable])
    loud = float(power.mean()) if power.size else 0.0
    if loud <= 0:
        return None
    quiet = power < loud * QUIET_RATIO
    short = None
    i = quiet.size - 1
    while i >= 0:
        if not quiet[i]:
            i -= 1
            continue
        j = i
        while j > 0 and quiet[j - 1]:
            j -= 1
        mid = (j + i + 1) * WIN // 2
        length = (i - j + 1) * WIN / SR
        if i - j + 1 >= LONG_PAUSE_WINS:
            return mid, length
        if short is None:
            short = (mid, length)
        i = j - 1
    return short if allow_short else None


def quietest(audio: np.ndarray) -> int:
    """Середина самого тихого окна. Для монолога без пауз: резать всё равно
    надо, но не по счётчику посреди слова, а там, где тише всего."""
    power = window_power(audio)
    if power.size == 0:
        return audio.size
    return int(np.argmin(power)) * WIN + WIN // 2


def trailing_silence(audio: np.ndarray) -> bool:
    """Кончается ли кусок тишиной - признак того, что человек договорил."""
    need = int(SPEC_SILENCE_SEC * SR)
    if audio.size < need + WIN * 3:
        return False
    power = window_power(audio)
    loud = float(power.mean())
    if loud <= 0:
        return False
    return bool(power[-max(1, need // WIN):].max() < loud * QUIET_RATIO)


def is_quiet(audio: np.ndarray, loud: float) -> bool:
    """Тишина ли всё, что записано после заготовки. Сверяем с громкостью
    самой заготовки: к отпусканию микрофон дописывает тишину, и требовать
    точного совпадения позиции (как в old/) значило почти никогда не попадать."""
    if audio.size < WIN:
        return True
    power = window_power(audio)
    return bool(power.max() < max(loud, 1e-6) * QUIET_RATIO)


# --- диктовка ----------------------------------------------------------------

class Session:
    """Одна диктовка от нажатия до отпускания. Звук копится в растущем
    буфере; рабочий поток читает из него срезы, читатель дописывает в конец -
    области не пересекаются, а старый буфер после расширения держит numpy."""

    def __init__(self, sid: int, lang: str) -> None:
        self.id = sid
        self.lang = lang
        self.buf = np.empty(SR * 30, dtype=np.float32)
        self.size = 0
        self.consumed = 0
        self.streamed = 0
        self.parts: list[tuple[str, str]] = []
        self.tried_at = 0
        self.spec: tuple[int, str, str, float] | None = None
        self.spec_at = 0
        self.finishing = False
        self.finish_t0 = 0.0
        self.cancelled = False

    def append(self, chunk: np.ndarray) -> None:
        need = self.size + chunk.size
        if need > self.buf.size:
            grown = np.empty(max(need, self.buf.size * 2), dtype=np.float32)
            grown[:self.size] = self.buf[:self.size]
            self.buf = grown
        self.buf[self.size:need] = chunk
        self.size = need


class Engine:
    def __init__(self) -> None:
        self.ru = None
        self.en = None
        self.lock = threading.Lock()
        self.cond = threading.Condition(self.lock)
        self.session: Session | None = None
        self.jobs: list[tuple[object, np.ndarray, str, float]] = []

    # --- загрузка

    def load_ru(self) -> bool:
        try:
            self.ru = load(RU_MODEL)
            emit({"event": "ready", "model": "ru"})
            return True
        except Exception as e:  # noqa: BLE001
            emit({"event": "error", "message": f"Русская модель не загрузилась: {e}"})
            return False

    def load_en_async(self) -> None:
        def run() -> None:
            try:
                self.en = load(EN_MODEL)
                emit({"event": "ready", "model": "en"})
            except Exception as e:  # noqa: BLE001
                emit({"event": "error", "message": f"Английская модель не загрузилась: {e}"})
        threading.Thread(target=run, daemon=True).start()

    # --- команды (зовёт читатель)

    def begin(self, sid: int, lang: str) -> None:
        with self.cond:
            if self.session is not None:
                self.session.cancelled = True
            self.session = Session(sid, lang)
            self.cond.notify()

    def add_audio(self, sid: int, chunk: np.ndarray) -> None:
        with self.cond:
            s = self.session
            if s is not None and s.id == sid and not s.finishing:
                s.append(chunk)
                self.cond.notify()

    def request_finish(self, sid: int) -> bool:
        with self.cond:
            s = self.session
            if s is None or s.id != sid:
                return False
            s.finishing = True
            s.finish_t0 = time.time()
            self.cond.notify()
            return True

    def cancel(self, sid: int) -> None:
        with self.cond:
            if self.session is not None and self.session.id == sid:
                self.session.cancelled = True
                self.session = None

    def add_job(self, sid, audio: np.ndarray, lang: str) -> None:
        with self.cond:
            self.jobs.append((sid, audio, lang, time.time()))
            self.cond.notify()

    # --- рабочий поток: единственный, кто трогает модели

    def rec_piece(self, audio: np.ndarray, lang: str) -> tuple[str, str]:
        """Кусок: GigaAM, и если похоже на английский - Parakeet. Parakeet не
        ждём: пока грузится, лучше русский текст сейчас, чем очередь на минуту."""
        if lang == "en" and self.en is not None:
            return recognize(self.en, audio), "en"
        text = recognize(self.ru, audio)
        if lang == "auto" and self.en is not None and is_english(text):
            en_text = recognize(self.en, audio)
            if en_text:
                return en_text, "en"
        return text, "ru"

    def segmented(self, audio: np.ndarray, lang: str) -> tuple[str, str]:
        """Целиком, но теми же кусками, что и на ходу: не длиннее MAX_FEED_SEC,
        рез по самой поздней паузе, язык - по каждому куску.

        Одним куском английская фраза посреди русской диктовки портилась: язык
        решался по всей записи, она в основном русская - и Parakeet не звали
        («Plas sent Me report by Frida» на тестовой минуте). Заодно короче куски
        - меньше работы: самовнимание растёт квадратом от длины.
        """
        limit = int(MAX_FEED_SEC * SR)
        keep = int(KEEP_TAIL_SEC * SR)
        parts: list[tuple[str, str]] = []
        pos = 0
        while audio.size - pos > limit:
            found = find_pause(audio[pos:pos + limit + keep], True)
            cut = found[0] if found is not None else quietest(audio[pos:pos + limit])
            cut = max(cut, WIN)
            text, got = self.rec_piece(audio[pos:pos + cut], lang)
            if text:
                parts.append((text, got))
            pos += cut
        text, got = self.rec_piece(audio[pos:], lang)
        if text:
            parts.append((text, got))
        return " ".join(t for t, _ in parts).strip(), majority(parts)

    def _has_work(self) -> bool:
        s = self.session
        return bool(self.jobs) or (s is not None and (s.finishing or s.size - s.tried_at >= int(TICK * SR)))

    def worker(self) -> None:
        while True:
            with self.cond:
                self.cond.wait_for(self._has_work, timeout=TICK)
                s = self.session
                job = None
                if not (s is not None and s.finishing) and self.jobs:
                    job = self.jobs.pop(0)
            try:
                if s is not None and s.finishing:
                    self._finish(s)
                elif job is not None:
                    self._transcribe(job)
                elif s is not None and not s.cancelled:
                    self._stream(s)
            except Exception as e:  # noqa: BLE001 - рабочий поток не должен умирать
                log(f"ошибка распознавания: {type(e).__name__}: {e}")
                if s is not None and s.finishing:
                    emit({"id": s.id, "error": f"{type(e).__name__}: {e}"})
                    with self.cond:
                        if self.session is s:
                            self.session = None
                elif job is not None:
                    emit({"id": job[0], "error": f"{type(e).__name__}: {e}"})

    def _stream(self, s: Session) -> None:
        with self.cond:
            if s is not self.session or s.cancelled or s.finishing:
                return
            start, total = s.consumed, s.size
            audio = s.buf[start:total]
            s.tried_at = total
        pending = audio.size
        if pending >= MIN_TAIL_SEC * SR:
            limit = int(MAX_FEED_SEC * SR)
            found = find_pause(audio, pending > SHORT_PAUSE_OK_SEC * SR)
            cut, pause = (found if found is not None else (None, 0.0))
            if cut is not None and cut > limit:
                # Ищем паузу внутри первых MAX_FEED_SEC (find_pause сама
                # отступает KEEP_TAIL_SEC от конца - добавляем их к окну).
                inner = find_pause(audio[:limit + int(KEEP_TAIL_SEC * SR)], True)
                cut, pause = inner if inner is not None else (quietest(audio[:limit]), 0.0)
            elif cut is None and pending > 2 * limit:
                cut, pause = quietest(audio[:limit]), 0.0
            # Пауза у самого начала даёт огрызок в полсекунды (живой замер:
            # куски 0.3 и 0.5 с). Ждём следующей паузы - она будет дальше.
            if cut is not None and cut < MIN_PIECE_SEC * SR and pending < SHORT_PAUSE_OK_SEC * SR:
                cut = None
            if cut is not None and cut > 0:
                text, lang = self.rec_piece(audio[:cut], s.lang)
                with self.cond:
                    if s is not self.session or s.cancelled:
                        return
                    s.consumed = start + cut
                    s.streamed += cut
                    s.spec = None
                    if text:
                        s.parts.append((text, lang))
                    joined = " ".join(t for t, _ in s.parts).strip()
                log(f"на ходу: {cut / SR:.1f} с (пауза {pause:.1f} с, {lang}), "
                    f"осталось {(total - start - cut) / SR:.1f} с")
                # Уже разобранное - окну: расшифровка в ходе речи и счёт слов.
                # Куски окончательные, текст только дописывается и не мигает.
                if text:
                    emit({"event": "partial", "id": s.id, "text": joined,
                          "words": len(joined.split())})
                return
        # Упреждающий хвост: человек замолчал - разбираем остаток заранее.
        if (0 < pending <= SPEC_MAX_TAIL_SEC * SR
                and total - s.spec_at >= SPEC_MIN_GAP_SEC * SR
                and trailing_silence(audio)):
            s.spec_at = total
            text, lang = self.rec_piece(audio, s.lang)
            power = window_power(audio)
            loud = float(power.mean()) if power.size else 0.0
            with self.cond:
                if s is self.session and not s.cancelled and s.consumed == start:
                    s.spec = (total, text, lang, loud)

    def _finish(self, s: Session) -> None:
        with self.cond:
            start, total = s.consumed, s.size
            tail = s.buf[start:total]
            spec = s.spec
            after_spec = s.buf[spec[0]:total] if spec is not None else None
            parts = list(s.parts)
        spec_hit = False
        if spec is not None and spec[0] <= total and is_quiet(after_spec, spec[3]):
            spec_hit = True
            if spec[1]:
                parts.append((spec[1], spec[2]))
        elif tail.size >= SR // 20:
            text, lang = self.rec_piece(tail, s.lang)
            # Хвост из пары слов определителю не судим (меньше трёх слов) -
            # берём язык большинства уже разобранного.
            if (lang == "ru" and s.lang == "auto" and self.en is not None
                    and 0 < len(text.split()) < 3 and parts and majority(parts) == "en"):
                en_text = recognize(self.en, tail)
                if en_text:
                    text, lang = en_text, "en"
            if text:
                parts.append((text, lang))
        emit({"id": s.id, "text": " ".join(t for t, _ in parts).strip(),
              "lang": majority(parts), "sec": round(time.time() - s.finish_t0, 3),
              "audio_sec": round(total / SR, 2), "streamed_sec": round(s.streamed / SR, 2),
              "tail_sec": 0.0 if spec_hit else round((total - start) / SR, 2),
              "spec_hit": spec_hit, "parts": len(parts)})
        with self.cond:
            if self.session is s:
                self.session = None

    def _transcribe(self, job) -> None:
        sid, audio, lang, t0 = job
        text, got = self.segmented(audio, lang)
        emit({"id": sid, "text": text, "lang": got, "sec": round(time.time() - t0, 3),
              "audio_sec": round(audio.size / SR, 2), "streamed_sec": 0.0,
              "tail_sec": round(audio.size / SR, 2), "spec_hit": False, "parts": 1})


# --- ввод --------------------------------------------------------------------

def read_floats(stream, n: int) -> np.ndarray:
    """Прочитать n float32 прямо в массив, без промежуточных копий."""
    out = np.empty(n, dtype="<f4")
    view = memoryview(out).cast("B")
    got = 0
    while got < n * 4:
        k = stream.readinto(view[got:])
        if not k:
            raise EOFError
        got += k
    return out


def serve() -> None:
    claim_stdout()
    eng = Engine()
    if not eng.load_ru():
        return
    eng.load_en_async()
    threading.Thread(target=eng.worker, daemon=True).start()
    stdin = sys.stdin.buffer
    while True:
        line = stdin.readline()
        if not line:
            return
        try:
            req = json.loads(line)
        except ValueError:
            continue
        if not isinstance(req, dict):
            continue
        cmd = req.get("cmd")
        try:
            if cmd == "quit":
                return
            if cmd == "ping":
                emit({"event": "pong"})
            elif cmd == "begin":
                eng.begin(int(req["id"]), str(req.get("lang", "auto")))
            elif cmd == "audio":
                chunk = read_floats(stdin, int(req.get("samples", 0)))
                eng.add_audio(int(req["id"]), chunk)
            elif cmd == "finish":
                if not eng.request_finish(int(req["id"])):
                    emit({"id": req.get("id"), "error": "Нет такой диктовки"})
            elif cmd == "cancel":
                eng.cancel(int(req["id"]))
            elif cmd == "transcribe":
                audio = read_floats(stdin, int(req.get("samples", 0)))
                eng.add_job(req.get("id"), audio, str(req.get("lang", "auto")))
        except EOFError:
            return
        except Exception as e:  # noqa: BLE001 - одна плохая команда не роняет процесс
            log(f"команда {cmd}: {type(e).__name__}: {e}")
            if "id" in req and cmd in ("finish", "transcribe"):
                emit({"id": req.get("id"), "error": str(e)})


# --- проверка без приложения -------------------------------------------------

def read_wav(path: str) -> np.ndarray:
    with wave.open(path) as w:
        if w.getframerate() != SR or w.getsampwidth() != 2:
            raise SystemExit("нужен wav 16 кГц 16 бит: afconvert -f WAVE -d LEI16@16000 -c 1 in out.wav")
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
        if w.getnchannels() > 1:
            data = data.reshape(-1, w.getnchannels()).mean(axis=1)
    return data.astype(np.float32) / 32768.0


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] in ("--file", "--stream-file"):
        eng = Engine()
        eng.ru = load(RU_MODEL)
        eng.en = load(EN_MODEL)
        audio = read_wav(sys.argv[2])
        if sys.argv[1] == "--file":
            t0 = time.time()
            text, lang = eng.segmented(audio, "auto")
            print(json.dumps({"text": text, "lang": lang, "sec": round(time.time() - t0, 3),
                              "audio_sec": round(audio.size / SR, 2)}, ensure_ascii=False))
            return
        # Как при диктовке: порции по 0.25 с в реальном времени, потом finish.
        threading.Thread(target=eng.worker, daemon=True).start()
        eng.begin(1, "auto")
        step = int(0.25 * SR)
        for i in range(0, audio.size, step):
            eng.add_audio(1, audio[i:i + step])
            time.sleep(0.25)
        eng.request_finish(1)
        deadline = time.time() + 120
        while eng.session is not None and time.time() < deadline:
            time.sleep(0.02)
        return
    serve()


if __name__ == "__main__":
    main()
