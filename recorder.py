"""Захват микрофона: постоянно открытый поток + кольцевой пре-буфер.

Пре-буфер решает главную проблему диктовки по хоткею: между нажатием
клавиши и фактическим стартом записи проходит время, и первое слово
обрезается. Здесь поток пишет всегда, последние N мс хранятся в кольце
и подклеиваются к началу записи.
"""

import collections
import threading

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
BLOCK = 1024


class Recorder:
    def __init__(self, pre_buffer_sec: float = 0.5, keep_open: bool = True):
        self._lock = threading.Lock()
        self._recording = False
        self._chunks: list[np.ndarray] = []
        maxlen = max(1, int(pre_buffer_sec * SAMPLE_RATE / BLOCK))
        self._pre: collections.deque = collections.deque(maxlen=maxlen)
        self._keep_open = keep_open
        self._stream: sd.InputStream | None = None
        if keep_open:
            self._open()

    def _open(self) -> None:
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=BLOCK,
            callback=self._callback,
        )
        self._stream.start()

    def _close(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None

    def _callback(self, indata, frames, time_info, status) -> None:
        data = indata[:, 0].copy()
        with self._lock:
            if self._recording:
                self._chunks.append(data)
            else:
                self._pre.append(data)

    def start(self) -> None:
        if self._stream is None:
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

    def close(self) -> None:
        self._close()
