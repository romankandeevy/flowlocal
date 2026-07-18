"""Каталог моделей распознавания - описание данными (PLAN 2.3).

Один список, из которого живут и настройки, и автовыбор, и загрузка. Добавить
модель = дописать строку сюда, а не править UI.

Размеры - не «на глаз» и не из статей: посчитаны по метаданным HuggingFace для
тех самых файлов, которые onnx-asr реально качает под нужную квантизацию
(16 июля 2026). В одном репозитории лежат все варианты сразу, поэтому размер
репозитория - не размер модели: у GigaAM папка целиком 852 МБ, а нужный набор
int8 - 226 МБ. План, кстати, ошибался: Parakeet int8 весит 670 МБ, а не 456.

Про sha256. Плановый пункт «проверка sha256» закрыт не своей таблицей хэшей, а
тем, что её и так делает huggingface_hub: он тянет файлы по sha-адресуемым
блобам и сверяет их сам. Свои константы пришлось бы править при каждой
переквантизации у автора репозитория - это ловушка, а не проверка.

Квантизация: int8 вчетверо легче fp32 и на нашей проверке не потеряла ни слова
(tools/bench_asr.py умеет сравнить оба варианта на вашей речи).
"""

from dataclasses import dataclass

DEFAULT = "gigaam-v3-e2e-rnnt"


@dataclass(frozen=True)
class Model:
    id: str                  # идентификатор для onnx-asr (или репозиторий HF)
    title: str               # как показать человеку
    quant: str | None        # int8 | None (fp32)
    size_mb: int             # столько скачается на самом деле
    langs: str               # словами, а не кодами: это читает человек
    device: str              # на чём разумно жить
    license: str
    url: str
    why: str                 # одна строка: зачем она вообще в списке


CATALOG: list[Model] = [
    Model(
        id="gigaam-v3-e2e-rnnt",
        title="GigaAM",
        quant="int8",
        size_mb=226,
        langs="русский",
        device="CPU",
        license="MIT",
        url="https://huggingface.co/ai-sage/GigaAM-v3",
        why="Лучшая для русского: 700 000 часов речи, сама ставит пунктуацию.",
    ),
    Model(
        id="nemo-parakeet-tdt-0.6b-v3",
        title="Parakeet",
        quant="int8",
        size_mb=670,
        langs="25 европейских, язык определяет сам",
        device="CPU",
        license="CC-BY-4.0",
        url="https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3",
        why="Если диктуете не только по-русски. Лицензия требует указать автора.",
    ),
    # Русские модели, которых у нас не было. Библиотека onnx-asr знает
    # девятнадцать, а возили мы четыре - остальные просто ни разу не смотрели.
    #
    # Про пунктуацию отдельно, потому что это главная разница на глаз. Наш
    # GigaAM v3 **e2e** сам ставит точки, запятые и пишет «10:00» цифрами. Все
    # пятеро ниже отдают сплошную строчную строку без знаков («в десять утра»
    # вместо «в 10:00»), кроме FastConformer - тот ставит заглавную и точку в
    # конце. Это не поломка и не признак худшей модели: они распознают слова, а
    # оформление - работа отдельного слоя, которого у них нет.
    Model(
        id="nemo-fastconformer-ru-rnnt",
        title="FastConformer",
        quant="int8",
        size_mb=136,
        langs="русский",
        device="CPU",
        license="CC-BY-4.0",
        url="https://huggingface.co/istupakov/stt_ru_fastconformer_hybrid_large_pc_onnx",
        why="Вдвое легче нашей и заметно быстрее. Ставит заглавную и точку.",
    ),
    Model(
        id="t-tech/t-one",
        title="T-one",
        quant=None,
        size_mb=144,
        langs="русский",
        device="CPU",
        license="Apache-2.0",
        url="https://huggingface.co/t-tech/T-one",
        why="Российская, от Т-Банка. Знаков препинания не ставит, грузится долго.",
    ),
    Model(
        id="alphacep/vosk-model-ru",
        title="Vosk",
        quant="int8",
        size_mb=72,
        langs="русский",
        device="CPU",
        license="Apache-2.0",
        url="https://huggingface.co/alphacep/vosk-model-ru",
        why="Втрое легче нашей и самая быстрая. Без знаков препинания.",
    ),
    Model(
        id="alphacep/vosk-model-small-ru",
        title="Vosk маленькая",
        quant="int8",
        size_mb=27,
        langs="русский",
        device="CPU",
        license="Apache-2.0",
        url="https://huggingface.co/alphacep/vosk-model-small-ru",
        why="Самая лёгкая: 27 МБ. Для слабой машины. Без знаков препинания.",
    ),
    Model(
        id="gigaam-v3-rnnt",
        title="GigaAM без пунктуации",
        quant="int8",
        size_mb=226,
        langs="русский",
        device="CPU",
        license="MIT",
        url="https://huggingface.co/ai-sage/GigaAM-v3",
        why="Та же GigaAM, но сырым текстом - если чистка мешает больше, чем помогает.",
    ),
    Model(
        id="onnx-community/whisper-large-v3-turbo",
        title="Whisper turbo",
        quant="int8",
        size_mb=1086,
        langs="99 языков",
        device="GPU",
        license="MIT",
        url="https://huggingface.co/onnx-community/whisper-large-v3-turbo",
        why="Кому нужен любой язык и не жалко гигабайта. На русском ошибается втрое чаще.",
    ),
    Model(
        id="whisper-base",
        title="Whisper base",
        quant="int8",
        size_mb=108,
        langs="99 языков",
        device="CPU",
        license="Apache-2.0",
        url="https://huggingface.co/istupakov/whisper-base-onnx",
        why="Для слабого железа. Точность заметно ниже - это разменная монета.",
    ),
]

BY_ID = {m.id: m for m in CATALOG}


def get(model_id: str) -> Model | None:
    return BY_ID.get(model_id)


def quant_for(model_id: str, fallback: str | None = "int8") -> str | None:
    m = BY_ID.get(model_id)
    return m.quant if m else fallback


def pick(language: str | None) -> str:
    """Автовыбор модели по языку (PLAN 2.4).

    Оказалось проще, чем задумывалось: спрашивать надо не про железо, а про
    язык. Русский - всегда GigaAM, независимо от видеокарты: он и на процессоре
    укладывается в секунду, и точнее Whisper втрое. Видеокарта тут ничего не
    решает, поэтому и вопроса про неё нет.
    """
    if language in (None, "ru"):
        return DEFAULT
    return "nemo-parakeet-tdt-0.6b-v3"
