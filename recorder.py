"""Захват микрофона: постоянно открытый поток, кольцевой пре-буфер, замер громкости.

Пре-буфер решает главную проблему диктовки по хоткею: между нажатием
клавиши и фактическим стартом записи проходит время, и первое слово
обрезается. Здесь поток пишет всегда, последние N мс хранятся в кольце
и подклеиваются к началу записи.

Заодно поток считает RMS каждые LEVEL_MS - из них оверлей рисует живую
осциллограмму. Считаем в аудио-колбэке: 512 сэмплов - это микросекунды
работы, зато уровень честный и не требует второго прохода по данным.
"""

import collections
import threading

import numpy as np
import sounddevice as sd

import theme as T

SAMPLE_RATE = 16000
BLOCK = 1024                                   # 64 мс
LEVEL_N = SAMPLE_RATE * T.LEVEL_MS // 1000     # 512 сэмплов = 32 мс на одну полоску


def list_input_devices() -> list[tuple[int, str, str]]:
    """[(индекс, имя, host-api)] микрофонов.

    Один физический микрофон PortAudio показывает по разу на каждый host-api
    (MME, DirectSound, WASAPI...), поэтому имя без api - это три одинаковые
    строки в списке и гадание, какую выбрать. Отдаём api отдельно.
    Пустой список - если звуковой подсистемы нет вообще.
    """
    out = []
    try:
        apis = [a.get("name", "?") for a in sd.query_hostapis()]
        for i, d in enumerate(sd.query_devices()):
            if d.get("max_input_channels", 0) > 0:
                api = apis[d["hostapi"]] if d.get("hostapi", -1) < len(apis) else "?"
                out.append((i, str(d.get("name", f"устройство {i}")), api))
    except Exception:  # noqa: BLE001 - без звука приложение всё равно стартует
        pass
    return out


def default_input_name() -> str:
    try:
        idx = sd.default.device[0]
        if idx is None or idx < 0:
            return "по умолчанию"
        return str(sd.query_devices(idx).get("name", "по умолчанию"))
    except Exception:  # noqa: BLE001
        return "по умолчанию"


class Recorder:
    def __init__(self, pre_buffer_sec: float = 0.5, keep_open: bool = True,
                 device: int | None = None):
        self._lock = threading.Lock()
        self._recording = False
        self._chunks: list[np.ndarray] = []
        maxlen = max(1, int(pre_buffer_sec * SAMPLE_RATE / BLOCK))
        self._pre: collections.deque = collections.deque(maxlen=maxlen)
        self._keep_open = keep_open
        self._device = device
        self._stream: sd.InputStream | None = None

        self._levels: collections.deque = collections.deque(maxlen=256)
        self._level_seq = 0      # сколько уровней произведено всего
        self._drained = 0        # сколько уже забрал оверлей
        self.overflows = 0       # пропуски данных: индикатор перегруза системы
        self.fell_back = False   # выбранный микрофон умер, пишем с системного

        if keep_open:
            self._open()

    # ---------- поток ----------

    def _open(self) -> None:
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=BLOCK,
                device=self._device,
                callback=self._callback,
            )
        except Exception:
            # Выбранный в настройках микрофон отключили (ноутбук закрыли,
            # гарнитуру сняли с зарядки). Молча падать - значит «диктовка
            # умерла до перезапуска». Пробуем системный по умолчанию: хоть
            # какой-то звук лучше немоты. fell_back остаётся взведённым,
            # чтобы приложение один раз сказало об этом человеку.
            if self._device is None:
                raise
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=BLOCK,
                device=None,
                callback=self._callback,
            )
            self.fell_back = True
        self._stream.start()

    def _close(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:  # noqa: BLE001 - устройство могли выдернуть
                pass
            finally:
                self._stream = None

    def _healthy(self) -> bool:
        if self._stream is None:
            return False
        try:
            return bool(self._stream.active)
        except Exception:  # noqa: BLE001
            return False

    def _callback(self, indata, frames, time_info, status) -> None:
        if status and status.input_overflow:
            self.overflows += 1
        data = indata[:, 0].copy()
        # RMS по кусочкам фиксированной длины: шаг полосок не должен зависеть
        # от того, каким размером блока нас позвала звуковая подсистема
        levels = []
        for i in range(0, len(data) - LEVEL_N + 1, LEVEL_N):
            chunk = data[i:i + LEVEL_N]
            levels.append(float(np.sqrt(np.mean(chunk * chunk)) + 1e-9))
        with self._lock:
            if self._recording:
                self._chunks.append(data)
            else:
                self._pre.append(data)
            for lv in levels:
                self._levels.append(lv)
                self._level_seq += 1

    # ---------- запись ----------

    def start(self) -> None:
        if not self._healthy():
            # мог быть закрыт (keep_open=False) или умереть вместе с устройством
            self._close()
            self._open()
        with self._lock:
            self._chunks = list(self._pre)
            self._pre.clear()
            self._recording = True

    def stop(self) -> np.ndarray:
        """Останавливает запись и возвращает всё аудио (float32, 16 кГц, моно)."""
        with self._lock:
            self._recording = False
            chunks = self._chunks
            self._chunks = []
        if not self._keep_open:
            self._close()
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks)

    # ---------- громкость ----------

    def drain_levels(self) -> list[float]:
        """Уровни, появившиеся с прошлого вызова (последний - самый свежий).

        Именно «с прошлого вызова», а не «последние N»: оверлей досыпает их
        в осциллограмму, и повтор дал бы стоячую картинку.
        """
        with self._lock:
            n = min(self._level_seq - self._drained, len(self._levels))
            self._drained = self._level_seq
            if n <= 0:
                return []
            return list(self._levels)[-n:]

    def close(self) -> None:
        self._close()
