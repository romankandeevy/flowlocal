"""Локальная транскрипция: onnx-asr.

Было: faster-whisper (CTranslate2), 1.6 ГБ модели и обязательная CUDA -
колёса nvidia-cublas и nvidia-cudnn тянут за собой ещё полгигабайта.
Стало: onnxruntime и GigaAM v3 RNN-T int8 (226 МБ) на процессоре.

Почему (PLAN 0.2):

- GigaAM обучен на 700 000 часах русской речи и на русском ошибается ВДВОЕ
  реже Whisper, а мы платили за Whisper гигабайтом CUDA.

  Цифра осторожная намеренно. На независимом стенде (11 наборов, сентябрь
  2025, стенд ведёт автор Vosk - то есть свидетельство против собственного
  интереса) GigaAM v2 RNN-T дал WER 8.64 против 16.21 у Whisper large-v3.
  Это 1.9 раза.

  Раньше здесь стояло «втрое, 8.4 против 25.1». Так писать было нельзя по двум
  причинам: 8.4 - это цифра Сбера для ОБЫЧНОГО v3_rnnt, а возим мы v3_e2e_rnnt,
  у которого в том же файле 11.2; и оба числа вендорские. Проверил бы кто-то -
  и поймал бы нас на завышении в свою пользу. Для v3 независимого замера не
  существует вовсе, поэтому опираемся на v2 и говорим «вдвое».

  Оговорка про e2e: его WER выглядит хуже обычного RNN-T, но это артефакт
  замера, а не деградация. E2E ставит пунктуацию, пишет числа цифрами и правит
  согласование - WER считает всё это ошибками. Менять e2e на обычный ради
  красивой цифры значит потерять то, ради чего его и брали.
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

        DirectML - третий путь между этими двумя (PLAN 10). Он приезжает своим
        колесом onnxruntime-directml и работает на любой видеокарте с DirectX
        12, а не только на NVIDIA. Порядок «CUDA, потом DirectML, потом
        процессор» не случаен: у кого стоит onnxruntime-gpu, тот поставил его
        осознанно, и отбирать у него CUDA ради универсального пути незачем.

        Ставится DirectML кнопкой «Ускорить на видеокарте» (dml_setup.py), и
        замер там же решает, оставлять его или нет: на этой машине он вышел
        медленнее процессора, см. шапку dml_setup.
        """
        import onnxruntime as rt

        have = set(rt.get_available_providers())
        # Явный выбор «видеокарта» - это про КАРТУ, а не про CUDA: так он и
        # подписан в настройках. Поэтому здесь тоже перебор, а не одна попытка -
        # у человека с DirectML вместо onnxruntime-gpu единственная попытка
        # «CUDA» уронила бы загрузку целиком, хотя карта у него есть.
        if device == "cuda":
            gpu = []
            if "CUDAExecutionProvider" in have:
                gpu.append(("cuda", ["CUDAExecutionProvider", "CPUExecutionProvider"]))
            if "DmlExecutionProvider" in have:
                gpu.append(("dml", ["DmlExecutionProvider", "CPUExecutionProvider"]))
            # Список провайдеров, которых в сборке нет, onnxruntime не прощает -
            # он бросает на создании сессии. Пустой перебор означал бы «модель
            # не загрузилась» вместо «видеокарты не нашлось», поэтому оставляем
            # прежнюю попытку как была: пусть ошибка придёт от onnxruntime и
            # ляжет в журнал со своим текстом.
            return gpu or [("cuda", ["CUDAExecutionProvider", "CPUExecutionProvider"])]
        if device == "cpu":
            return [("cpu", ["CPUExecutionProvider"])]
        attempts = []
        if "CUDAExecutionProvider" in have:
            attempts.append(("cuda", ["CUDAExecutionProvider", "CPUExecutionProvider"]))
        if "DmlExecutionProvider" in have:
            attempts.append(("dml", ["DmlExecutionProvider", "CPUExecutionProvider"]))
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
        # Не крутить процессор вхолостую между фразами. По умолчанию рабочие
        # потоки onnxruntime после прогона уходят в busy-wait: ждут следующую
        # работу, сжигая ядро. Настроено это под серверы, где запросы идут
        # сплошным потоком; у нас между фразами минуты тишины.
        #
        # Замер (test.wav, 2 потока, по 7 прогонов с секундой тишины после
        # каждого, повторено дважды): процессорного времени на фразу 2.28 с
        # против 0.92 с - спин догорал уже после ответа. На настенных часах
        # при этом ноль разницы: 0.472 с в обоих режимах, худший случай даже
        # лучше (0.487 против 0.547). То есть платы за это нет вообще.
        #
        # На ноутбуке это слышно вентилятором после каждой диктовки. Оговорка:
        # к «ноль в покое» из «О программе» отношения не имеет - спин и так
        # кончался по таймауту, речь про секунды сразу после фразы.
        so.add_session_config_entry("session.force_spinning_stop", "1")
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

    # У модели ЖЁСТКИЙ потолок длины, и стоил он дорого: владелец надиктовал
    # пятнадцать минут - около тысячи слов - и потерял их целиком.
    #
    #   process error: [ONNXRuntimeError] Mul node '/layers.0/self_attn/Mul_1'
    #   Attempting to broadcast an axis by a dimension other than 1. 5000 by 21336
    #
    # Позиционные коды в самовнимании энкодера рассчитаны на 5000 кадров. Кадр
    # после свёрточного прореживания - 40 мс, то есть предел ровно 200 секунд.
    # Его 21336 кадров - это 853 секунды, те самые четырнадцать с лишним минут.
    # Всё длиннее 3 минут 20 секунд падало ВСЕГДА, с первого дня.
    #
    # Но одного потолка мало, и вторая беда нашлась замером. Самовнимание
    # держит матрицу «каждый кадр против каждого», то есть памяти нужно КВАДРАТ
    # от длины куска. На 150 секундах onnxruntime просит 792 МБ одним куском:
    #
    #   Failed to allocate memory for requested buffer of size 792084736
    #
    # То есть пятнадцать минут упали бы и по памяти, даже не будь потолка длины.
    # На машине с исчерпанным файлом подкачки это ломается и на свободной
    # физической памяти.
    #
    # 60 секунд вместо 150 - это в шесть с лишним раз меньше памяти (около
    # 130 МБ вместо 792) и вчетверо запас до потолка модели. Платы за это нет:
    # резы всё равно ложатся в паузы между фразами, а качество куска от его
    # длины не зависит - модель не авторегрессивная, контекст ей через границу
    # не нужен.
    _MAX_SEC = 60.0
    # Где искать тишину для реза. Резать по счётчику нельзя: разрез посреди
    # слова даёт две половинки, которых модель не узнает ни ту, ни другую.
    # Зона поиска паузы - 8 секунд при куске в 60. Больше делать нельзя: рез
    # уехал бы слишком далеко от границы, и куски вышли бы очень разной длины.
    _SEEK_SEC = 8.0

    def _cut_points(self, audio: np.ndarray) -> list[int]:
        """Границы кусков: не длиннее предела, рез - в самом тихом месте.

        Тишину ищем окном в 30 мс по средней громкости и берём минимум в зоне
        поиска перед границей. Это не разбор речи, а именно «где потише»: между
        фразами человек делает паузу, и попасть в неё достаточно, чтобы не
        разрубить слово пополам.
        """
        step = int(self._MAX_SEC * SAMPLE_RATE)
        seek = int(self._SEEK_SEC * SAMPLE_RATE)
        # Окно в 200 мс, а не в 30: ищем не «мгновение потише», а паузу между
        # фразами. С коротким окном самым тихим оказывался первый же тихий
        # отрезок, и рез вставал ровно на границу «речь кончилась» - с нулевым
        # запасом. Хвостовой согласный от такого реза отрезается.
        win = int(0.2 * SAMPLE_RATE)
        points, pos = [], 0
        while audio.size - pos > step:
            hard = pos + step
            start = max(pos, hard - seek)
            zone = audio[start:hard]
            if zone.size >= win * 2:
                # Средняя громкость по окнам; argmin - самая тихая пауза.
                n = zone.size // win
                power = np.abs(zone[:n * win].reshape(n, win)).mean(axis=1)
                # Режем по СЕРЕДИНЕ тихого окна: так запас есть с обеих сторон.
                cut = start + int(np.argmin(power)) * win + win // 2
            else:
                cut = hard
            # Защита от вырождения: рез обязан двигать нас вперёд, иначе
            # цикл встанет намертво на файле из одной тишины.
            cut = max(cut, pos + step // 2)
            points.append(cut)
            pos = cut
        return points

    def transcribe(self, audio: np.ndarray, on_part=None) -> str:
        """Распознать запись. Длинную режем на куски и склеиваем.

        on_part(номер, всего) - если передан, зовётся перед каждым куском:
        человеку, наговорившему десять минут, надо видеть, что работа идёт.
        """
        if self.model is None:
            raise RuntimeError("модель ещё не загружена")
        if audio.size < SAMPLE_RATE // 20:   # <50 мс: распознавать нечего
            return ""
        opts = {}
        name = str(self.cfg.get("model") or DEFAULT_MODEL).lower()
        if any(m in name for m in _LANG_MODELS) and self.cfg.get("language"):
            opts["language"] = self.cfg["language"]

        cuts = self._cut_points(audio)
        if not cuts:
            return self._one(audio, opts)

        bounds = [0, *cuts, audio.size]
        total = len(bounds) - 1
        self.log(f"запись {audio.size / SAMPLE_RATE:.0f} с - режу на {total} "
                 f"частей (предел модели 200 с)")
        parts = []
        for i in range(total):
            if on_part is not None:
                on_part(i + 1, total)
            piece = audio[bounds[i]:bounds[i + 1]]
            got = self._one(piece, opts)
            if got:
                parts.append(got)
        # Пробел между кусками, а не пустая строка: это одна речь, разрезанная
        # нами, и склеивать её надо так, будто разреза не было.
        return " ".join(parts).strip()

    def _one(self, audio: np.ndarray, opts: dict) -> str:
        return str(self.model.recognize(audio, sample_rate=SAMPLE_RATE,
                                        **opts) or "").strip()
