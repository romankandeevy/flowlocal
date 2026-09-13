"""Спасение записи, которую не удалось распознать.

Зачем это появилось. Владелец надиктовал пятнадцать минут - около тысячи слов -
и потерял их целиком: распознавание упало на потолке длины модели, исключение
ушло в лог, а звук жил только в локальной переменной и был собран сборщиком
мусора. Ни текста, ни записи, ни возможности повторить. Пятнадцать минут работы
в никуда.

В плане этот пункт стоял последним со словами «ценность невысокая, скорее всего
не будет сделан никогда». Оценка была неверной, и цена ошибки - ровно те
пятнадцать минут.

Правило теперь простое: **звук ложится на диск ДО распознавания и стирается
только после успеха.** Упало что угодно - на диске лежит wav, и его можно
распознать заново, когда причина устранена.

Место на диске это почти не ест: при успехе файл живёт секунду и удаляется.
Копятся только неудачи, а их единицы; сверх лимита сносим самые старые.
"""

import os
import time
import wave

import numpy as np

from app_paths import APP_DIR

DIR = os.path.join(APP_DIR, "recordings")

# Сколько неудачных записей храним. Больше десяти - это не «спасение», а свалка;
# к тому же каждая может весить десятки мегабайт.
KEEP = 10

SAMPLE_RATE = 16000


def _path(ts: float | None = None) -> str:
    stamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(ts or time.time()))
    return os.path.join(DIR, f"{stamp}.wav")


def save(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> str:
    """Положить запись на диск. Возвращает путь; пусто - не вышло.

    Пишем int16, а не float32: вчетверо легче, а для распознавания разницы нет -
    микрофон и так отдаёт 16 бит. Пятнадцать минут выходят в 28 МБ вместо 115.

    Ошибку глотаем намеренно и возвращаем пустую строку: не сумели подстелить
    соломки - это плохо, но не повод уронить саму диктовку.
    """
    try:
        os.makedirs(DIR, exist_ok=True)
        path = _path()
        pcm = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
        pcm = (pcm * 32767.0).astype(np.int16)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(pcm.tobytes())
        return path
    except (OSError, ValueError):
        return ""


def drop(path: str) -> None:
    """Распознали - запись больше не нужна."""
    if not path:
        return
    try:
        os.remove(path)
    except OSError:
        pass


def load(path: str) -> tuple[np.ndarray, int]:
    """Прочитать сохранённую запись обратно в массив."""
    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
        a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if w.getnchannels() == 2:
            a = a.reshape(-1, 2).mean(axis=1)
        return a, w.getframerate()


def kept() -> list[dict]:
    """Что лежит недораспознанного. Свежие первыми."""
    out = []
    try:
        names = os.listdir(DIR)
    except OSError:
        return out
    for name in names:
        if not name.lower().endswith(".wav"):
            continue
        path = os.path.join(DIR, name)
        try:
            size = os.path.getsize(path)
            with wave.open(path, "rb") as w:
                sec = w.getnframes() / float(w.getframerate() or SAMPLE_RATE)
        except (OSError, wave.Error):
            continue
        out.append({"path": path, "name": name[:-4].replace("_", " "),
                    "sec": sec, "mb": size / 1e6})
    out.sort(key=lambda r: r["path"], reverse=True)
    return out


def prune(keep: int = KEEP) -> None:
    """Оставить только последние keep записей."""
    rows = kept()
    for row in rows[keep:]:
        drop(row["path"])
