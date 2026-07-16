"""E2E-тест конвейера без микрофона: WAV -> Transcriber -> cleaner.

WAV генерируется заранее Windows-TTS (см. make_test_wav.ps1).
Запуск: python test_e2e.py [путь_к_wav]
"""

import sys
import time
import wave

import numpy as np

import config
from cleaner import clean
from transcriber import Transcriber


def read_wav(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        assert w.getsampwidth() == 2, "нужен PCM16"
        assert w.getframerate() == 16000, "нужно 16 кГц"
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if w.getnchannels() > 1:
            data = data.reshape(-1, w.getnchannels()).mean(axis=1).astype(np.int16)
    return (data.astype(np.float32)) / 32768.0


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "test.wav"
    cfg = config.load()

    audio = read_wav(path)
    print(f"audio: {audio.size / 16000:.1f}s")

    tr = Transcriber(cfg, print)
    tr.load()
    print(f"backend: {tr.device}/{tr.compute_type}")

    t0 = time.time()
    raw = tr.transcribe(audio)
    dt = time.time() - t0
    print(f"raw ({dt:.2f}s): {raw}")

    cleaned = clean("Эм, " + raw + " ммм, вот.", cfg, print)
    print(f"cleaned: {cleaned}")

    # повторный прогон - реальная латентность после прогрева
    t0 = time.time()
    tr.transcribe(audio)
    print(f"second run: {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()
