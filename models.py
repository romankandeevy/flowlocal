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
