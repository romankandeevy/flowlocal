"""Конфиг: значения по умолчанию, чтение, запись, доступ по «точечному» пути.

Отдельный модуль, потому что конфиг трогают трое: приложение, окно настроек
и тесты. Раньше каждый читал json сам и падал на отсутствующем ключе -
теперь любой недостающий ключ добирается из DEFAULTS, и удалить строку из
config.json стало безопасно.
"""

import json
import os
import re
import shutil
import tempfile

from app_paths import (APP_DIR, CONFIG_PATH,  # noqa: F401 - реэкспорт для удобства
                       EXAMPLE_PATH)

DEFAULTS: dict = {
    # Два независимых бинда, а не один хоткей с переключателем режима: человек
    # сам решает, каким жестом диктовать, и может держать оба сразу.
    #   hold   - зажал и говоришь, отпустил и вставилось;
    #   toggle - нажал, говоришь со свободными руками, нажал ещё раз - стоп.
    # Пусто = бинд выключен. Оба могут быть и клавишами, и кнопками мыши
    # («ctrl+mouse4») - разбор в inputspec.py.
    "hotkey_hold": "ctrl+shift+space",
    "hotkey_toggle": "",
    # Command mode: выделил текст, зажал, сказал «сделай короче» - выделенное
    # заменилось результатом. Требует Ollama: правка по произвольному указанию -
    # это понимание смысла, регэкспом не берётся. Пусто = выключено; умолчание
    # пустое намеренно, потому что без Ollama функция немая.
    "hotkey_command": "",
    "undo_hotkey": "",           # пусто = отмена последней вставки выключена
    "theme": "system",           # system | light | dark
    "language": None,            # только для Whisper/Canary; GigaAM - русский и точка
    # GigaAM v3 RNN-T: 226 МБ, процессор, для русского втрое точнее Whisper.
    # Каталог моделей - в models.py, переезд описан в transcriber.py.
    "model": "gigaam-v3-e2e-rnnt",
    "quantization": "int8",      # int8 | null (fp32): int8 вчетверо легче
    "device": "auto",            # auto | cpu | cuda
    "mic_device": None,          # None = системный по умолчанию
    "keep_mic_open": True,
    "pre_buffer_sec": 0.5,
    "min_record_sec": 0.3,
    "insert_mode": "paste",
    "append_space": True,
    "restore_clipboard": True,
    "sounds": True,
    # Мастер первого запуска уже пройден? Ставится в конце мастера; false у
    # старых конфигов покажет его один раз - это намеренно, мастер новый.
    "onboarded": False,
    "remove_fillers": True,
    # Голосовые команды: «с новой строки», «с нового абзаца», «нажми энтер»
    # в конце фразы. Формы без предлога не распознаются намеренно - см. cleaner.
    "voice_commands": True,
    "history": True,
    "dictionary": [],
    # «сказать» -> «вставить». Личное по природе (почта, реквизиты), поэтому в
    # config.example.json уезжает пустым.
    "snippets": {},
    # exe активного окна -> тон, которым переписать текст. Требует включённой
    # полировки LLM: тон делает Ollama, больше нечем.
    "tone_rules": {},
    "llm": {
        # Три состояния, а не два. null - «человек ещё не решал»: тогда на старте
        # ищем Ollama сами и включаемся молча, если она есть. true/false - решение
        # человека, и лезть с автоопределением мы больше не имеем права.
        #
        # Зачем: полировка - это то, чем мы отличаемся от простого распознавателя,
        # а по умолчанию она была выключена, потому что Ollama есть не у всех.
        # Выходило, что у постороннего человека наша главная функция не работала
        # ни разу и он о ней не узнавал. Кто поставил Ollama - тот согласен на
        # локальную модель по определению, спрашивать его второй раз незачем.
        "enabled": None,
        "url": "http://127.0.0.1:11434",
        # Пусто - выберем из установленных сами (cleaner.pick_llm_model).
        "model": "",
        "timeout_sec": 20,
    },
}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def bootstrap(path: str = CONFIG_PATH, example: str = EXAMPLE_PATH) -> None:
    """Первый запуск: сделать config.json из примера, если своего ещё нет.

    Отдельным вызовом, а не внутри load(): load() зовут и настройки, и тесты, и
    молча создавать файлы на диске из функции чтения - неожиданно. Без конфига
    приложение и так работает на умолчаниях; пример нужен, чтобы человек увидел,
    что вообще можно настроить, и правил файл, а не догадывался.
    """
    if os.path.exists(path) or not os.path.exists(example):
        return
    try:
        shutil.copyfile(example, path)
    except OSError:
        pass          # не скопировалось - не беда, load() отдаст умолчания


# Имена моделей faster-whisper. onnx-asr их не понимает вообще: для него
# модель - это либо свой идентификатор, либо репозиторий HuggingFace с onnx.
_FASTER_WHISPER = re.compile(
    r"^(tiny|base|small|medium|large(-v[123])?|large-v3-turbo|turbo|distil-.+)"
    r"(\.en)?$|whisper", re.IGNORECASE)


def _migrate(raw: dict) -> dict:
    """Старая схема -> новая. Правим СЫРОЙ словарь, до подмешивания умолчаний:
    после _merge уже не отличить «человек не задавал» от «взято по умолчанию».
    """
    raw = dict(raw)

    # Было: один "hotkey" плюс "hotkey_mode" (hold|toggle) - переключатель.
    # Стало: два независимых бинда "hotkey_hold" и "hotkey_toggle".
    # Старый хоткей переезжает в тот бинд, которым он и работал.
    if "hotkey" in raw and "hotkey_hold" not in raw and "hotkey_toggle" not in raw:
        old = str(raw.pop("hotkey", "") or "")
        mode = str(raw.pop("hotkey_mode", "hold") or "hold")
        raw["hotkey_toggle" if mode == "toggle" else "hotkey_hold"] = old

    # Было: faster-whisper. Стало: onnx-asr (PLAN, этап 2). Миграция здесь не
    # вкусовщина, а необходимость: со старым именем модели приложение не
    # поднимется - onnx-asr пойдёт искать репозиторий «large-v3-turbo» и не
    # найдёт. Уводим на GigaAM: для русского он точнее втрое и не требует CUDA.
    # Кому нужен Whisper - выбирает его заново в настройках, уже по onnx-имени.
    if isinstance(raw.get("model"), str) and _FASTER_WHISPER.search(raw["model"]):
        raw.pop("model")
    # beam_size был параметром декодера Whisper, compute_type - CTranslate2.
    # У onnx-asr ни того, ни другого: точность выбирается квантизацией.
    raw.pop("beam_size", None)
    raw.pop("compute_type", None)

    # llm.enabled: false в старых конфигах - это не выбор человека, а прежнее
    # умолчание. Тогда полировка требовала руками поставить Ollama, поэтому
    # умолчанием было «выключено», и у большинства она не работала ни разу.
    # Теперь false значит «человек выключил осознанно», а null - «не решал, ищем
    # Ollama сами». Поднимаем старый false до null ровно один раз: метка
    # остаётся в конфиге, и второй раз мы решение человека не переиграем.
    llm = raw.get("llm")
    if isinstance(llm, dict) and "llm_auto_v2" not in llm:
        if llm.get("enabled") is False:
            llm["enabled"] = None
        llm["llm_auto_v2"] = True
    return raw


def load(path: str = CONFIG_PATH) -> dict:
    """Конфиг с подставленными умолчаниями. Файла нет или он битый - вернём
    умолчания: без конфига диктовка должна работать, а не падать."""
    try:
        with open(path, encoding="utf-8") as f:
            return _merge(DEFAULTS, _migrate(json.load(f)))
    except (OSError, ValueError):
        return _merge(DEFAULTS, {})


def save(cfg: dict, path: str = CONFIG_PATH) -> None:
    """Атомарная запись: пишем во временный файл рядом и заменяем.

    Прямая запись поверх оставила бы обрезанный config.json, если процесс
    умрёт на середине, - а это единственная настройка приложения.
    """
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".config-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def get(cfg: dict, path: str, default=None):
    """get(cfg, 'llm.model')"""
    cur = cfg
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def set_(cfg: dict, path: str, value) -> None:
    """set_(cfg, 'llm.model', 'qwen2.5:3b')"""
    parts = path.split(".")
    cur = cfg
    for part in parts[:-1]:
        if not isinstance(cur.get(part), dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value
