"""Локальная LLM в коробке: onnxruntime-genai, без Ollama и без сервера.

Зачем это вообще: полировка и тон - то, чем FlowLocal отличается от «просто
диктовки», - до сих пор требовали от человека поставить Ollama, поднять сервер
и скачать к нему модель. Владелец сформулировал приговор точнее некуда: «даже
я, разработчик этой программы, не знаю, как это делать». Функция, до которой
нельзя дойти, - это отсутствующая функция.

Рантайм не новый: `onnxruntime` уже лежит в сборке ради распознавания речи,
genai - надстройка над ним. То есть цена перехода - вес модели, а не второй
движок в установщике.

**Это НЕ отмена решения PLAN 2.6-бис.** Там отвергли не идею, а две конкретные
модели: Qwen3-0.6B превратила «Вот дом, в котором я живу» в «дом», а 1.7B без
рассуждения не делала ничего. Отвергли замером, и вернуться можно только тем
же способом - через `tools/bench_clean.py` как гейт. Правило прежнее: кандидат
с ненулевым «испорчено» не берётся, каким бы ни был процент починки.

Модель живёт в `models/`, рядом с GigaAM, и качается так же - по кнопке, с
прогрессом. Никаких серверов и портов.
"""

import os
import threading
import time

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

# Один загруженный экземпляр на процесс. Модель занимает гигабайты и грузится
# секунды - держим её, пока не попросят выгрузить. Замок нужен потому, что
# греть могут из фонового потока, а спрашивать - из рабочего.
_lock = threading.Lock()
_loaded: dict = {"path": None, "model": None, "tokenizer": None}


def model_dir(name: str) -> str:
    return os.path.join(MODELS_DIR, name)


def available(name: str) -> bool:
    """Есть ли модель на диске и полная ли она.

    Проверяем `genai_config.json`, а не саму папку: оборванная скачка
    оставляет папку с половиной файлов, и по её наличию мы бы решили, что всё
    хорошо, а упали бы уже при загрузке. Ровно на этом обжигались с моделью
    распознавания (см. `transcriber._load_once`).
    """
    return os.path.isfile(os.path.join(model_dir(name), "genai_config.json"))


def load(name: str, log) -> bool:
    """Поднять модель в память. False - не вышло, и это не повод падать.

    Полировка опциональна, диктовка - нет: любая беда здесь означает «работаем
    без LLM», а не «потеряли фразу».
    """
    path = model_dir(name)
    with _lock:
        if _loaded["path"] == path and _loaded["model"] is not None:
            return True
        if not available(name):
            log(f"llm local: нет модели в {path}")
            return False
        try:
            import onnxruntime_genai as og

            t0 = time.monotonic()
            model = og.Model(path)
            _loaded.update(path=path, model=model, tokenizer=og.Tokenizer(model))
            log(f"llm local: {name} поднята за {time.monotonic() - t0:.1f} с")
            return True
        except Exception as e:  # noqa: BLE001 - без LLM живём, без диктовки нет
            log(f"llm local: не поднялась - {e}")
            _loaded.update(path=None, model=None, tokenizer=None)
            return False


def unload() -> None:
    """Отдать память. Модель весит гигабайты, а приложение живёт в трее сутками."""
    with _lock:
        _loaded.update(path=None, model=None, tokenizer=None)


def ask(prompt: str, llm_cfg: dict, log, what: str) -> str:
    """Один запрос. Пустая строка - не получилось.

    Тот же контракт, что у `cleaner._ollama`: пусто вместо исключения. Выше по
    стеку `_sane()` всё равно проверит ответ на потерю слов, но до него надо
    ещё дойти живым.
    """
    name = str(llm_cfg.get("local_model") or "")
    if not name or not load(name, log):
        return ""
    with _lock:
        model = _loaded["model"]
        tok = _loaded["tokenizer"]
        if model is None:
            return ""
        try:
            import onnxruntime_genai as og

            # Qwen3 по умолчанию «думает вслух»: выдаёт блок <think> и тратит
            # на него весь бюджет токенов. Замерено: на вопрос из трёх слов -
            # 12 секунд и ответа нет вовсе, только рассуждение. Для правки
            # текста рассуждать нечего, поэтому просим не думать штатной
            # командой семейства. Другим моделям эта строка ничего не сделает.
            ask_text = prompt
            if "qwen3" in name.lower():
                ask_text = prompt + "\n/no_think"

            # Шаблон чата берём у самой модели: у Qwen это <|im_start|> с
            # ролями, у другой семьи будет своё. Прописать его руками - значит
            # молча сломаться на первой же смене модели.
            text = tok.apply_chat_template(
                messages=f'[{{"role": "user", "content": {_json(ask_text)}}}]',
                add_generation_prompt=True)

            params = og.GeneratorParams(model)
            # do_sample=False - жадный выбор. Нам не нужна фантазия, нужна
            # повторяемость: одна и та же фраза обязана чиститься одинаково,
            # иначе замер ничего не значит.
            params.set_search_options(
                do_sample=False,
                max_length=len(tok.encode(text)) + int(llm_cfg.get("max_new", 512)))
            gen = og.Generator(model, params)
            gen.append_tokens(tok.encode(text))

            deadline = time.monotonic() + float(llm_cfg.get("timeout_sec", 20))
            while not gen.is_done():
                gen.generate_next_token()
                # Свой таймаут, а не «сколько получится»: генератор может
                # уйти в долгие рассуждения, а человек ждёт вставку. Лучше
                # отдать сырой текст, чем задержать его на минуту.
                if time.monotonic() > deadline:
                    log(f"llm local {what}: не уложилась в таймаут")
                    return ""
            out = gen.get_sequence(0)[len(tok.encode(text)):]
            return _strip_think(str(tok.decode(out) or "").strip())
        except Exception as e:  # noqa: BLE001
            log(f"llm local {what} failed: {e}")
            return ""


def _strip_think(text: str) -> str:
    """Убрать блок рассуждения, если модель всё-таки подумала вслух.

    `/no_think` слушаются не все сборки и не всегда. Оставить <think> в ответе
    нельзя: `_sane()` в cleaner.py сравнит его с исходником, увидит вагон
    лишних слов и отвергнет ответ целиком - то есть полировка молча перестанет
    работать, и понять почему будет неоткуда.
    """
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return text.strip()


def _json(s: str) -> str:
    """Строка как литерал JSON - для шаблона чата, который ждёт JSON-массив."""
    import json
    return json.dumps(s, ensure_ascii=False)
