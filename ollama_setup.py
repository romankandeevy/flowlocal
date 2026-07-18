"""Поставить Ollama за человека: скачать, установить, забрать модель.

Зачем это существует. Полировка и тон - то, чем FlowLocal отличается от
«просто диктовки». Обе работают через Ollama, и до сегодняшнего дня в
интерфейсе про это было написано ровно «нужна Ollama». Всё. Ни ссылки, ни
объяснения, какую модель качать, ни слова про сервер. Владелец сформулировал
приговор точнее, чем это сделал бы любой отчёт: «даже я, разработчик этой
программы, не знаю, как это делать». Функция, до которой нельзя дойти, - это
отсутствующая функция.

Здесь поэтому весь путь целиком, кнопкой: скачали установщик, поставили,
дождались сервера, забрали модель, включили полировку. Терминал человек не
видит ни разу.

Своя модель в коробке рассматривалась и отвергнута дважды. Первый раз замером
(PLAN 2.6-бис: Qwen3-0.6B превратила «Вот дом, в котором я живу» в «дом»),
второй - 18.07.2026 на полном наборе `bench_clean.py`: 1.7B через
onnxruntime-genai дала 10/20 против 18/20 у Ollama и **потеряла слова в двух
случаях**, то есть провалила главный критерий. Решение владельца после этого
короткое: качаем Ollama, своё не изобретаем.

Честная цена, которую интерфейс обязан назвать ДО начала: установщик Ollama
~1.4 ГБ плюс модель ~1.9 ГБ. Это втрое больше самого FlowLocal вместе с
моделью распознавания, и узнать об этом человек должен до нажатия, а не после.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request

# Официальный установщик. Ставится в профиль пользователя, прав администратора
# не просит - как и наш собственный.
SETUP_URL = "https://ollama.com/download/OllamaSetup.exe"
API = "http://127.0.0.1:11434"

# Что забираем после установки. 3B - замеренный оптимум для нашей работы:
# 1.7B уже теряет слова, 7B думает дольше, чем человек готов ждать вставку.
DEFAULT_MODEL = "qwen2.5:3b"

# Сколько ждём, пока поднимется сервер после установки. Ollama регистрирует
# себя в автозапуске и стартует сама, но не мгновенно.
_SERVE_WAIT = 90

_UA = {"User-Agent": "FlowLocal"}


def exe() -> str:
    """Путь к ollama.exe или пустая строка. Ищем там, куда ставит установщик."""
    found = shutil.which("ollama")
    if found:
        return found
    guess = os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         "Programs", "Ollama", "ollama.exe")
    return guess if os.path.isfile(guess) else ""


def serving(timeout: float = 1.5) -> bool:
    """Отвечает ли сервер. Это и есть настоящая проверка «Ollama есть»:
    установленная, но не запущенная, нам бесполезна."""
    try:
        with urllib.request.urlopen(API + "/api/tags", timeout=timeout):
            return True
    except Exception:  # noqa: BLE001 - нет так нет
        return False


def has_model(name: str) -> bool:
    try:
        with urllib.request.urlopen(API + "/api/tags", timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return any(str(m.get("name", "")).startswith(name.split(":")[0])
                   for m in data.get("models", []))
    except Exception:  # noqa: BLE001
        return False


def download(on_progress=None) -> str:
    """Скачать установщик во временную папку. Возвращает путь.

    on_progress(доля, всего_байт) - чтобы окно могло показать и проценты, и
    честный размер: 1.4 ГБ - это не та цифра, которую прячут за процентами.
    """
    dst = os.path.join(tempfile.mkdtemp(prefix="flowlocal_ollama_"),
                       "OllamaSetup.exe")
    req = urllib.request.Request(SETUP_URL, headers=_UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(dst, "wb") as f:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if on_progress:
                    on_progress(done / total if total else 0.0, total)
    return dst


def install(setup_path: str, log) -> bool:
    """Поставить и дождаться сервера. False - не вышло.

    Сначала молча (/VERYSILENT). Флаг не описан в документации Ollama, но
    установщик у них на Inno Setup - это видно по единственному документированному
    ключу `/DIR="..."`, синтаксис ровно его. Если молча не вышло (в трекере
    Ollama есть жалобы на неинтерактивную установку), показываем установщик
    как есть: пусть человек нажмёт «Install» сам - это всё равно лучше, чем
    инструкция из шести шагов в справке.
    """
    for args, how in (([setup_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], "молча"),
                      ([setup_path], "с окном")):
        try:
            log(f"ollama: ставлю {how}")
            subprocess.run(args, timeout=600, check=False)
        except Exception as e:  # noqa: BLE001
            log(f"ollama: установщик {how} не отработал - {e}")
            continue
        if _wait_serving(log):
            return True
    return False


def _wait_serving(log) -> bool:
    """Ollama после установки поднимает сервер сама, но не мгновенно."""
    deadline = time.monotonic() + _SERVE_WAIT
    while time.monotonic() < deadline:
        if serving():
            return True
        time.sleep(2)
    # Установили, но не запустилась - пробуем поднять руками.
    path = exe()
    if path:
        try:
            log("ollama: сервер не поднялся сам, запускаю")
            subprocess.Popen([path, "serve"],
                             creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP
                                            | getattr(subprocess, "DETACHED_PROCESS", 0)),
                             close_fds=True)
        except Exception as e:  # noqa: BLE001
            log(f"ollama: запустить не вышло - {e}")
        for _ in range(15):
            if serving():
                return True
            time.sleep(2)
    log("ollama: сервер так и не ответил")
    return False


def pull(model: str, on_progress=None, log=print) -> bool:
    """Забрать модель. Прогресс отдаём наружу построчно, как его шлёт Ollama.

    Через HTTP, а не `ollama pull` в консоли: нам нужен прогресс в своём окне,
    а не чужое окно с бегущими строками. Ответ - поток JSON по строке на
    событие, у части строк есть completed/total.
    """
    body = json.dumps({"model": model, "stream": True}).encode("utf-8")
    req = urllib.request.Request(API + "/api/pull", data=body,
                                 headers={"Content-Type": "application/json", **_UA})
    # Модель приезжает слоями, и у каждого свои completed/total. Показывать
    # прогресс слоя нельзя: он добегает до 100%, а следом начинается новый с
    # нуля - полоса дёргается назад по нескольку раз. Считаем сумму по всем
    # слоям, которые видели, - это и есть честный общий прогресс.
    layers: dict = {}
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            for line in resp:
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line.decode("utf-8"))
                except Exception:  # noqa: BLE001 - битую строку просто пропустим
                    continue
                if ev.get("error"):
                    log(f"ollama pull: {ev['error']}")
                    return False
                digest = str(ev.get("digest") or "")
                if digest and ev.get("total"):
                    layers[digest] = (ev.get("completed") or 0, ev["total"])
                total = sum(t for _c, t in layers.values())
                done = sum(c for c, _t in layers.values())
                if on_progress:
                    on_progress(_human(str(ev.get("status") or "")),
                                done / total if total else 0.0, total)
        return has_model(model)
    except Exception as e:  # noqa: BLE001
        log(f"ollama pull failed: {e}")
        return False


def _human(status: str) -> str:
    """Служебные статусы Ollama - человеческими словами.

    «pulling 797b70c4edf8» человеку не говорит ничего, а пугает - выглядит как
    ошибка. Правило проекта: служебное живёт в flow.log.
    """
    s = status.lower()
    if s.startswith("pulling"):
        return "скачиваю модель"
    if s.startswith("verifying"):
        return "проверяю"
    if s.startswith("writing"):
        return "сохраняю"
    if s.startswith("success"):
        return "готово"
    return "скачиваю модель"


def ensure(model: str = DEFAULT_MODEL, on_stage=None, log=print) -> bool:
    """Весь путь одной кнопкой. True - полировкой можно пользоваться.

    on_stage(этап, доля, всего) - для окна. Этапы человеческие, без «pulling
    manifest»: «скачиваю Ollama», «устанавливаю», «скачиваю модель».
    """
    def stage(name, frac=0.0, total=0):
        if on_stage:
            on_stage(name, frac, total)

    if not serving():
        if not exe():
            stage("скачиваю Ollama")
            try:
                path = download(lambda f, t: stage("скачиваю Ollama", f, t))
            except Exception as e:  # noqa: BLE001
                log(f"ollama: скачать не вышло - {e}")
                stage("не удалось скачать")
                return False
            stage("устанавливаю")
            if not install(path, log):
                stage("не удалось установить")
                return False
            shutil.rmtree(os.path.dirname(path), ignore_errors=True)
        elif not _wait_serving(log):
            stage("Ollama установлена, но не запускается")
            return False

    if not has_model(model):
        stage("скачиваю модель")
        if not pull(model, lambda s, f, t: stage("скачиваю модель", f, t), log):
            stage("не удалось скачать модель")
            return False

    stage("готово", 1.0)
    return True
