"""Локальная транскрипция: faster-whisper (CTranslate2).

device=auto: пробуем CUDA (float16), при любой ошибке - CPU (int8).
Ошибка CUDA может вылезти не при создании модели, а на первом вызове,
поэтому после загрузки делаем прогрев секундой тишины - он же греет
кернелы, чтобы первая реальная фраза не ждала инициализации.

download_root=models/ рядом с приложением: CTranslate2 плохо переносит
кириллицу в путях, а дефолтный кэш HuggingFace лежит в C:/Users/<имя>.
"""

import os
import time

import numpy as np

from recorder import SAMPLE_RATE

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")


def _add_cuda_dlls() -> None:
    """cuBLAS/cuDNN из pip-пакетов nvidia-* должны быть видны до импорта ctranslate2."""
    import site

    paths = []
    try:
        paths = site.getsitepackages() + [site.getusersitepackages()]
    except Exception:  # noqa: BLE001
        pass
    for sp in paths:
        nv = os.path.join(sp, "nvidia")
        if not os.path.isdir(nv):
            continue
        for pkg in os.listdir(nv):
            b = os.path.join(nv, pkg, "bin")
            if os.path.isdir(b):
                try:
                    os.add_dll_directory(b)
                    os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")
                except OSError:
                    pass


_add_cuda_dlls()


class Transcriber:
    def __init__(self, cfg: dict, log) -> None:
        self.cfg = cfg
        self.log = log
        self.model = None
        self.device = "?"
        self.compute_type = "?"

    def load(self) -> None:
        from faster_whisper import WhisperModel

        name = self.cfg.get("model", "large-v3-turbo")
        device = self.cfg.get("device", "auto")
        compute = self.cfg.get("compute_type", "auto")

        if device == "auto":
            attempts = [
                ("cuda", "float16" if compute == "auto" else compute),
                ("cpu", "int8" if compute == "auto" else compute),
            ]
        else:
            ct = compute if compute != "auto" else ("float16" if device == "cuda" else "int8")
            attempts = [(device, ct)]

        last_err: Exception | None = None
        for dev, ct in attempts:
            try:
                t0 = time.time()
                model = WhisperModel(name, device=dev, compute_type=ct, download_root=MODELS_DIR)
                # прогрев и одновременно проверка, что бэкенд реально работает
                warmup = np.zeros(SAMPLE_RATE, dtype=np.float32)
                segments, _ = model.transcribe(warmup, beam_size=1, language="ru")
                list(segments)
                self.model = model
                self.device = dev
                self.compute_type = ct
                self.log(f"model={name} device={dev} compute={ct} load={time.time() - t0:.1f}s")
                return
            except Exception as e:  # noqa: BLE001 - фолбэк на следующий бэкенд
                last_err = e
                self.log(f"backend {dev}/{ct} failed: {e}")
        raise RuntimeError(f"не удалось загрузить модель: {last_err}")

    def transcribe(self, audio: np.ndarray) -> str:
        lang = self.cfg.get("language") or None
        hotwords = " ".join(self.cfg.get("dictionary", [])) or None
        segments, _info = self.model.transcribe(
            audio,
            language=lang,
            beam_size=int(self.cfg.get("beam_size", 5)),
            vad_filter=True,
            condition_on_previous_text=False,
            hotwords=hotwords,
        )
        return " ".join(s.text.strip() for s in segments).strip()
