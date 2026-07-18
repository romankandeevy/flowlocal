"""Локальная транскрипция: onnx-asr.

Было: faster-whisper (CTranslate2), 1.6 ГБ модели и обязательная CUDA -
колёса nvidia-cublas и nvidia-cudnn тянут за собой ещё полгигабайта.
Стало: onnxruntime и GigaAM v3 RNN-T int8 (226 МБ) на процессоре.

Почему (PLAN 0.2):

- GigaAM обучен на 700 000 часах русской речи: WER по доменам 8.4% против
  25.1% у Whisper. Для русского Whisper ошибается втрое чаще, и мы платили
  за это гигабайтом CUDA.
- RNN-T не авторегрессивный - галлюцинировать на тишине ему нечем. Фирменное
  whisper-овское «Спасибо за просмотр!» на паузах лечится архитектурой, а не
  порогами.
- Вариант e2e сам ставит пунктуацию и нормализует числа («в 10:00 утра»).
- И всё это на процессоре не медленнее, чем Whisper turbo на видеокарте.

Модель качается в models/ рядом с приложением, а не в кэш HuggingFace: кэш
лежит в C:/Users/<имя>, а имя бывает кириллицей. Папка на модель своя и
включает квантизацию: int8 и fp32 - разные файлы в одном репозитории, в общей
папке они бы смешались.

Оговорка про словарь: hotwords из faster-whisper здесь нет и быть не может -
у onnx-asr нет ни этого параметра, ни initial_prompt (подсказывать нечему,
декодер не авторегрессивный). Словарь поэтому работает постобработкой, в
cleaner.py.
"""

import os
import shutil
import time

import numpy as np

from app_paths import MODELS_DIR
from recorder import SAMPLE_RATE

# Модели, которые умеют принимать язык. Остальным (GigaAM) его передавать
# нельзя: русский там единственный, а лишний kwarg долетит до onnxruntime.
_LANG_MODELS = ("whisper", "canary")

DEFAULT_MODEL = "gigaam-v3-e2e-rnnt"


def model_dir(model: str, quant: str | None) -> str:
    """Папка модели в models/. Идентификатор бывает вида «org/repo» - слэш
    в имени папки Windows не переживёт."""
    return os.path.join(MODELS_DIR, model.replace("/", "--") + ("-" + quant if quant else "-fp32"))


class Transcriber:
    def __init__(self, cfg: dict, log) -> None:
        self.cfg = cfg
        self.log = log
        self.model = None
        self.device = "?"
        self.compute_type = "?"      # int8 | fp32 - как называется в UI и логах

    # ---------- загрузка ----------

    def _providers(self, device: str) -> list[tuple[str, list[str]]]:
        """[(имя устройства, providers)] в порядке попыток.

        auto: CUDA только если onnxruntime реально её собрал (это отдельное
        колесо onnxruntime-gpu). Обычная сборка отдаёт CPU, и это нормальный
        режим работы, а не деградация: GigaAM на процессоре укладывается в
        секунду. Спрашиваем сам onnxruntime, а не наличие видеокарты: карта
        может быть, а провайдера под неё в сборке нет.
        """
        import onnxruntime as rt

        have = set(rt.get_available_providers())
        if device == "cuda":
            return [("cuda", ["CUDAExecutionProvider", "CPUExecutionProvider"])]
        if device == "cpu":
            return [("cpu", ["CPUExecutionProvider"])]
        attempts = []
        if "CUDAExecutionProvider" in have:
            attempts.append(("cuda", ["CUDAExecutionProvider", "CPUExecutionProvider"]))
        attempts.append(("cpu", ["CPUExecutionProvider"]))
        return attempts

    def _session_options(self):
        """Настройки сессии onnxruntime. None - оставить умолчания.

        Единственное, что мы здесь трогаем, - число потоков, и трогаем по
        замеру: умолчание берёт потоков по числу ядер и на короткой фразе
        оказывается вдвое медленнее двух потоков (цифры в config.py).

        Больше ядер тут не помогает, а мешает: модель маленькая, фраза
        короткая, и раздача работы стоит дороже самой работы.
        """
        n = int(self.cfg.get("asr_threads") or 0)
        if n <= 0:
            return None
        import onnxruntime as rt

        so = rt.SessionOptions()
        so.intra_op_num_threads = n
        # Межоператорную параллельность не трогаем: у последовательной модели
        # параллельных веток нет, и потоки под них - чистые накладные расходы.
        so.inter_op_num_threads = 1
        return so

    def _load_once(self, name: str, quant: str | None, providers: list[str]):
        """Загрузка с одной попыткой докачки.

        onnx-asr считает существующую папку признаком «работаем офлайн» и
        качать в неё уже не пойдёт. Оборванная скачка оставляет папку с
        неполным набором файлов - и приложение после этого не поднимется
        никогда, пока папку не снести руками. Сносим сами.
        """
        import onnx_asr
        from onnx_asr.utils import ModelFileNotFoundError

        d = model_dir(name, quant)
        kw = {}
        so = self._session_options()
        if so is not None:
            kw["sess_options"] = so
        try:
            return onnx_asr.load_model(name, path=d, quantization=quant,
                                       providers=providers, **kw)
        except ModelFileNotFoundError:
            if not os.path.isdir(d):
                raise
            self.log(f"модель в {d} неполная - качаю заново")
            shutil.rmtree(d, ignore_errors=True)
            return onnx_asr.load_model(name, path=d, quantization=quant,
                                       providers=providers, **kw)

    def load(self) -> None:
        name = str(self.cfg.get("model") or DEFAULT_MODEL)
        quant = self.cfg.get("quantization", "int8") or None
        device = str(self.cfg.get("device", "auto") or "auto")

        os.makedirs(MODELS_DIR, exist_ok=True)
        last_err: Exception | None = None
        for dev, providers in self._providers(device):
            try:
                t0 = time.time()
                model = self._load_once(name, quant, providers)
                # Прогрев - он же проверка, что бэкенд живой: ошибка провайдера
                # вылезает не на создании сессии, а на первом прогоне. Заодно
                # первая настоящая фраза не ждёт инициализации кернелов.
                model.recognize(np.zeros(SAMPLE_RATE, dtype=np.float32))
                self.model = model
                self.device = dev
                self.compute_type = quant or "fp32"
                threads = int(self.cfg.get("asr_threads") or 0)
                self.log(f"model={name} device={dev} quant={self.compute_type} "
                         f"threads={threads or 'умолчание'} "
                         f"load={time.time() - t0:.1f}s")
                return
            except Exception as e:  # noqa: BLE001 - фолбэк на следующий бэкенд
                last_err = e
                self.log(f"backend {dev} failed: {e}")
        raise RuntimeError(f"не удалось загрузить модель: {last_err}")

    def unload(self) -> None:
        """Отпустить модель и вернуть память.

        Приложение живёт в трее сутками, а модель занимает под 370 МБ. У
        человека, который диктует пять раз в день, эти мегабайты просто лежат.
        Обратная загрузка - 2-3 секунды, поэтому по умолчанию не выгружаем: у
        того, кто диктует часто, задержка была бы хуже мегабайтов.

        Ссылку рвём, дальше память отдаёт сборщик: своих буферов у нас нет,
        всё внутри onnxruntime, и звать у него ничего не надо.
        """
        if self.model is None:
            return
        self.model = None
        self.log("модель выгружена из памяти")

    @property
    def loaded(self) -> bool:
        return self.model is not None

    # ---------- распознавание ----------

    def transcribe(self, audio: np.ndarray) -> str:
        if self.model is None:
            raise RuntimeError("модель ещё не загружена")
        if audio.size < SAMPLE_RATE // 20:   # <50 мс: распознавать нечего
            return ""
        opts = {}
        name = str(self.cfg.get("model") or DEFAULT_MODEL).lower()
        if any(m in name for m in _LANG_MODELS) and self.cfg.get("language"):
            opts["language"] = self.cfg["language"]
        return str(self.model.recognize(audio, sample_rate=SAMPLE_RATE, **opts) or "").strip()
