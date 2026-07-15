"""Постобработка текста - аналог "AI-полировки" Wispr Flow.

Базовый слой - консервативные regex-правила (убрать междометия,
поправить пробелы/запятые). Опциональный слой - локальная LLM через
Ollama (config.llm.enabled): чистит слова-паразиты и самоисправления.
При любой ошибке LLM возвращается исходный текст - диктовка не должна
ломаться из-за недоступной Ollama.
"""

import json
import re
import urllib.request

# Только однозначные междометия. Кириллица и латиница - разные кодпоинты,
# поэтому английское "um" не зацепит русское слово "ум".
_FILLERS = re.compile(
    r"(?i)(?:^|(?<=[\s,;:]))"
    r"(?:э[-э]+м*|эм+|м{3,}|uh+m*|um+|hm{2,})"
    r"(?=[\s,.!?;:…-]|$)",
)

_LLM_PROMPT = (
    "Ты - фильтр диктовки. Ниже сырая расшифровка речи. "
    "Убери слова-паразиты и оговорки, учти самоисправления говорящего "
    "(если человек поправил себя - оставь только финальный вариант), "
    "поправь пунктуацию. Ничего не добавляй и не сокращай по смыслу. "
    "Сохрани язык оригинала. Верни ТОЛЬКО итоговый текст без пояснений.\n\n"
    "Расшифровка: {text}"
)


def _strip_fillers(text: str) -> str:
    started_upper = bool(text[:1].isupper())
    text = _FILLERS.sub("", text)
    text = re.sub(r"\s+([,.!?;:…])", r"\1", text)      # пробел перед знаком
    text = re.sub(r"([,;:])(\s*[,;:])+", r"\1", text)  # "раз, , вот" после вырезания
    text = re.sub(r"^[\s,;:…-]+", "", text)            # осиротевшая пунктуация в начале
    text = re.sub(r"\s{2,}", " ", text)
    text = text.strip()
    # фраза начиналась с заглавной, а после вырезания филлера начало сменилось
    if started_upper and text[:1].islower():
        text = text[0].upper() + text[1:]
    return text


def _llm_polish(text: str, llm_cfg: dict, log) -> str:
    req = urllib.request.Request(
        llm_cfg["url"].rstrip("/") + "/api/generate",
        data=json.dumps(
            {
                "model": llm_cfg["model"],
                "prompt": _LLM_PROMPT.format(text=text),
                "stream": False,
                "options": {"temperature": 0.1},
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=llm_cfg.get("timeout_sec", 20)) as resp:
            out = json.loads(resp.read().decode("utf-8")).get("response", "").strip()
        return out or text
    except Exception as e:  # noqa: BLE001 - LLM опциональна, диктовка важнее
        log(f"ollama polish failed: {e}")
        return text


def clean(text: str, cfg: dict, log) -> str:
    if cfg.get("remove_fillers", True):
        text = _strip_fillers(text)
    llm = cfg.get("llm", {})
    if text and llm.get("enabled"):
        text = _llm_polish(text, llm, log)
    return text
