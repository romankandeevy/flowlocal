"""Ускорение распознавания на видеокарте: колесо onnxruntime-directml (PLAN 10).

Зачем это существует. У владельцев видеокарт распознавание считает процессор,
и узнать об этом им неоткуда. CUDA-путь отменён давно и по делу: полгига
раздачи ради машин с NVIDIA. DirectML - тот же выигрыш, но через DirectX 12,
то есть на любой карте: NVIDIA, AMD, Intel, встроенная в процессор. Приезжает
отдельным колесом (26 МБ архивом, 70 МБ на диске), в дистрибутив не входит.

Здесь весь путь кнопкой, как в ollama_setup: замерили, скачали, подменили,
замерили снова, сказали цифры. Терминал человек не видит ни разу.

ГЛАВНОЕ ПРО ЭТУ КНОПКУ: она чаще говорит «не помогло», чем «помогло», и это
не поломка, а результат замера. Замер на машине владельца (RTX 5060, GigaAM v3
e2e-rnnt int8, 2 потока, медиана из 5 прогонов, одна и та же запись разной
длины):

    длина записи   процессор   видеокарта   во сколько раз
       3 с           0.109 с     0.280 с      0.39   медленнее
       5 с           0.156 с     0.291 с      0.54   медленнее
       8 с           0.239 с     0.316 с      0.76   медленнее
      12 с           0.361 с     0.342 с      1.06   вровень
      16 с           0.489 с     0.379 с      1.29
      20 с           0.643 с     0.409 с      1.57
      30 с           1.030 с     0.495 с      2.08
      45 с           1.734 с     0.633 с      2.74   быстрее

Видно одним взглядом: у видеокарты постоянная плата за вход около 0.27 с
(собрать команды, переслать данные, дождаться), зато дальше она почти не
растёт - 8 мс на секунду записи против 37 мс у процессора. Перелом на
двенадцати секундах.

А теперь то, из-за чего кнопка и говорит «не помогло». Диктуют люди фразами по
три-восемь секунд - это левая половина таблицы, где процессор быстрее вдвое.
Плюс стрим (streaming.py) разбирает речь кусками ПОКА человек говорит, так что
даже пятнадцатиминутная диктовка приходит сюда кусками, а не целиком. Правая
половина таблицы в этой программе почти не встречается.

Отсюда правило: решает замер на короткой фразе - той самой, ожидание после
которой человек и чувствует. Проиграла видеокарта - честно называем обе цифры
и оставляем процессор (`device: cpu`), а не молча делаем хуже. Выиграла -
оставляем «авто», и transcriber._providers сам возьмёт DirectML.

И вторая ловушка, из-за которой замеров здесь три, а не два. Колесо DirectML
несёт СВОЮ версию onnxruntime, и она не та, что стояла. На машине владельца
разница вышла больше самой видеокарты: обычное колесо 1.27.0 считает ту же
короткую фразу за 0.45 с, а колесо DirectML 1.24.4 - за 0.24 с, и всё это на
процессоре. Сравнение «было 0.45 - стало 0.32» показало бы ускорение и записало
его на счёт видеокарты, хотя видеокарта здесь ПРОИГРАЛА процессору. Поэтому
приговор выносит только сравнение «видеокарта против процессора на одном и том
же колесе», см. setup().

Настройки сессии под DirectML пробовались и выброшены: документация советует
гасить enable_mem_pattern и параллельное выполнение, но замер разницы не
показал (0.322 против 0.322 на короткой, 0.746 против 0.730 на длинной).
Кода без замера за спиной здесь не держим.

ПОЧЕМУ НУЖЕН ПЕРЕЗАПУСК, и почему обойти это нельзя. К моменту нажатия кнопки
onnxruntime в нашем процессе уже загружен - модель поднялась на старте. Колесо
подменяет `onnxruntime/capi/onnxruntime_pybind11_state.pyd`, но Windows держит
загруженные библиотеки по пути: новый файл по старому пути просто не будет
прочитан, сколько ни перезагружай модель. importlib.reload расширение тоже не
перезагрузит - Python кэширует такие модули на весь процесс. Поэтому замеры
идут в ОТДЕЛЬНЫХ процессах (они и видят новое колесо), а приложению нужен
перезапуск. Кнопка так и говорит.

ЧТО В СБОРКЕ PyInstaller. Кнопка там выключена, и это единственный честный
вариант: в сборке нет ни pip, ни site-packages, ни python рядом - подменять
нечего и нечем (см. blocked()). Что будет, если колесо подменить ДО сборки
(`pip install onnxruntime-directml`, потом `python tools/build.py cpu`):
flowlocal.spec соберётся и заработает. Фильтр `_is_cuda` выбрасывает по именам
cublas/cudnn/cudart/..., а DirectML.dll под них не попадает; тянет её сам
onnxruntime_pybind11_state.pyd своей таблицей импортов, то есть PyInstaller
найдёт её без подсказок и хидден-импортов. Сборка потяжелеет примерно на 40 МБ
(DirectML.dll 18.5 МБ плюс разница в самих библиотеках onnxruntime). Это
разбор спека и содержимого колеса, а НЕ настоящая сборка - см. отчёт задачи 10.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

PACKAGE = "onnxruntime-directml"

# Колёса конфликтуют, и это не про версии: все три кладут ОДНУ и ту же папку
# `onnxruntime` в site-packages. Поставить второе поверх первого значит
# получить вперемешку файлы двух пакетов и два .dist-info, каждый из которых
# считает файлы своими. Поэтому строго: сначала снести, потом поставить.
CONFLICTS = ("onnxruntime", "onnxruntime-gpu", "onnxruntime-directml")

# Метка, по которой родитель выкусывает json из stdout замерочного процесса.
# Тот же приём, что в tools/bench_asr.py: в stdout летит ещё и лог модели.
MARK = "##DML##"

# Длина «длинной» записи для замера, секунды. 55, а не больше: 60 - предел
# куска в transcriber (_MAX_SEC), дальше запись режется, и мы мерили бы уже
# склейку, а не работу модели.
LONG_SEC = 55

# Насколько процессору позволено просесть от подмены колеса, прежде чем мы
# сочтём это поломкой и откатимся. Версия onnxruntime в directml-колесе своя и
# обычно отстаёт от обычного - просадка возможна. 25% - это заметно больше
# разброса между прогонами (он тут в пределах 5%) и заметно меньше, чем разница
# между процессором и видеокартой.
_CPU_TOLERANCE = 1.25

# Сколько ждём pip. Скачать 26 МБ и распаковать 70 - это секунды на нормальной
# связи, но связь бывает и не нормальная.
_PIP_TIMEOUT = 900
# Замер: загрузка модели (2-5 с) плюс восемь прогонов. Минуты хватает с
# запасом, но на холодном диске первая загрузка бывает и десятком секунд.
_BENCH_TIMEOUT = 300


def available() -> bool:
    """Видит ли DirectML ЭТОТ процесс. Именно этот - см. шапку про перезапуск."""
    try:
        import onnxruntime as rt

        return "DmlExecutionProvider" in rt.get_available_providers()
    except Exception:  # noqa: BLE001 - нет onnxruntime, нет и разговора
        return False


def installed() -> bool:
    """Лежит ли колесо на диске, даже если процесс его ещё не видит.

    Спрашиваем метаданные, а не провайдеров: сразу после установки провайдер в
    этом процессе не появится никогда, а кнопка «Установить» второй раз - это
    человек, который нажал и ждёт впустую.
    """
    try:
        from importlib.metadata import distribution

        distribution(PACKAGE)
        return True
    except Exception:  # noqa: BLE001
        return False


def blocked() -> str:
    """Почему кнопку нажимать нельзя. Пустая строка - можно.

    Отвечаем ФРАЗОЙ, а не флагом: причина у отказа одна на всю кнопку, и
    человеку надо показать именно её, а не серую кнопку без объяснения.
    """
    if os.name != "nt":
        return "Видеокарта через DirectML работает только в Windows"
    if getattr(sys, "frozen", False):
        # В сборке нет ни pip, ни папки с пакетами: подменять нечего. Кнопка,
        # которая ничего не сделает, хуже честного отказа.
        return "В установленной программе не получится - соберите из исходников"
    return ""


# ---------- pip ----------


def _pip(args: list[str], log, timeout: int = _PIP_TIMEOUT) -> tuple[int, str]:
    """Позвать pip тем же питоном, что выполняет нас. Возвращает (код, вывод).

    Отдельным процессом и без консоли: своё окно pip-а поверх настроек - это
    ровно тот терминал, которого человек видеть не должен.
    """
    cmd = [sys.executable, "-m", "pip", *args]
    log("dml: " + " ".join(cmd[2:]))
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as e:  # noqa: BLE001 - pip может не запуститься вовсе
        log(f"dml: pip не отработал - {e}")
        return 1, str(e)
    out = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        log(f"dml: pip вернул {p.returncode}\n{out[-2000:]}")
    return p.returncode, out


def install(on_stage=None, log=print) -> bool:
    """Подменить колесо. True - на диске лежит onnxruntime-directml.

    Порядок здесь важнее самих команд: СНАЧАЛА качаем во временную папку и
    только потом сносим старое. Наоборот было бы так - снесли onnxruntime,
    связь оборвалась, и у человека не осталось распознавания вовсе, до
    следующего похода в консоль. Ради этого лишний шаг и терпим.
    """
    def stage(name: str, frac: float) -> None:
        if on_stage:
            on_stage(name, frac)

    tmp = tempfile.mkdtemp(prefix="flowlocal_dml_")
    try:
        stage("скачиваю", 0.30)
        code, out = _pip(["download", "--no-deps", "--dest", tmp, PACKAGE], log)
        wheels = [f for f in os.listdir(tmp) if f.endswith(".whl")] if code == 0 else []
        if not wheels:
            # Самая частая причина - колеса нет под эту версию Python: они
            # выходят с задержкой после каждого релиза. В выводе pip это видно,
            # человеку знать незачем, в журнал - обязательно.
            log(f"dml: колесо не скачалось\n{out[-1000:]}")
            stage("не удалось скачать", 0.0)
            return False
        wheel = os.path.join(tmp, wheels[0])

        stage("ставлю", 0.45)
        # Сносим ВСЕ конфликтующие, а не только onnxruntime: у энтузиаста может
        # стоять onnxruntime-gpu, и конфликтует он ровно так же.
        _pip(["uninstall", "-y", *CONFLICTS], log)
        code, out = _pip(["install", wheel], log)
        if code != 0 or not installed():
            log(f"dml: установка не удалась\n{out[-1000:]}")
            # Вернуть распознавание на место обязаны в любом случае: без
            # onnxruntime программа не поднимется вообще.
            stage("возвращаю как было", 0.5)
            _pip(["install", "onnxruntime"], log)
            stage("не удалось поставить", 0.0)
            return False
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def restore(log=print) -> bool:
    """Вернуть обычное колесо: колесо стало не нужно или сделало хуже."""
    _pip(["uninstall", "-y", *CONFLICTS], log)
    code, _out = _pip(["install", "onnxruntime"], log)
    return code == 0


# ---------- замер ----------


def measure(device: str, log=print) -> dict:
    """Замер в ОТДЕЛЬНОМ процессе: {device, short, long} или {error}.

    Отдельным - по двум причинам, и вторая важнее. Первая: только свежий
    процесс видит подменённое колесо (шапка модуля). Вторая: замер поднимает
    вторую копию модели на 370 МБ и гоняет её восемь раз - делать это в
    процессе, который в это же время обязан слышать хоткей, нельзя.
    """
    script = os.path.abspath(__file__)
    cmd = [sys.executable, script, "--bench", device]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=_BENCH_TIMEOUT,
                           cwd=os.path.dirname(script),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as e:  # noqa: BLE001
        log(f"dml: замер не запустился - {e}")
        return {"error": str(e)}
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    for line in out.splitlines():
        if line.startswith(MARK):
            try:
                return json.loads(line[len(MARK):])
            except Exception:  # noqa: BLE001 - разберём по отсутствию ключей ниже
                break
    log(f"dml: замер не дал результата\n{out[-1500:]}")
    return {"error": "замер не дал результата"}


def _bench(device: str) -> dict:
    """Тело замерочного процесса. Секунды на короткой записи и на длинной.

    Короткая - это test.wav как есть (7.8 с): обычная фраза, ради которой всё и
    затевалось. Длинную склеиваем из неё же - работа модели зависит от числа
    кадров, а не от того, что на них сказано.

    Медиана, а не среднее и не лучший прогон: среднее уводит один случайный
    провал, а лучший врёт в свою пользу - именно так и получаются рекламные
    цифры, которых потом никто не видит.
    """
    import wave

    import numpy as np

    import config
    from recorder import SAMPLE_RATE
    from transcriber import Transcriber

    with wave.open("test.wav", "rb") as w:
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    short = raw.astype(np.float32) / 32768.0
    long_ = np.tile(short, LONG_SEC * SAMPLE_RATE // short.size + 1)[
        : LONG_SEC * SAMPLE_RATE]

    cfg = config.load()
    cfg["device"] = device
    tr = Transcriber(cfg, lambda _m: None)
    tr.load()

    def med(audio, n):
        runs = []
        for _ in range(n):
            t0 = time.time()
            tr.transcribe(audio)
            runs.append(time.time() - t0)
        runs.sort()
        return runs[len(runs) // 2]

    tr.transcribe(short)                 # прогрев, в счёт не идёт
    return {"device": tr.device, "short": med(short, 5), "long": med(long_, 3)}


def setup(on_stage=None, log=print) -> dict:
    """Весь путь одной кнопкой. Возвращает разбор для окна.

    Ключи: ok - видеокарта быстрее процессора на короткой фразе; device - на
    чём она считала («dml»/«cuda»); before - секунды до всего, gpu и cpu -
    секунды на новом колесе, long_* - то же на длинной записи; broke_cpu -
    подмена испортила процессорный путь и мы откатились; error - фраза для
    человека, если не вышло вовсе.

    `error` - всегда НАША фраза, никогда не текст исключения. Это условие, а не
    случайность: measure() возвращает наружу `{"error": "TypeError: ..."}`
    (замер идёт отдельным процессом, и родитель обязан получить хоть что-то), а
    окно ставит `error` прямо в подпись ряда. Каждая ветка ниже поэтому
    перезаписывает его своим текстом, и питоновские потроха остаются в журнале -
    туда их кладут сами measure() и _pip().

    Замеряем ТРИЖДЫ, и третий замер - главный. Он появился не из
    аккуратности, а из пойманного вранья: на машине владельца обычное колесо
    (onnxruntime 1.27.0) считает короткую фразу за 0.45 с, а колесо DirectML
    (1.24.4) - за 0.24 с НА ТОМ ЖЕ ПРОЦЕССОРЕ. Сравнение «до и после» показало
    бы 0.45 -> 0.32 и радостно записало ускорение на счёт видеокарты, хотя на
    деле видеокарта проиграла процессору (0.32 против 0.24), а весь выигрыш
    дала смена версии onnxruntime.

    Поэтому приговор выносит только сравнение видеокарты с процессором НА ОДНОМ
    И ТОМ ЖЕ колесе. Замер «до» остаётся - его человеку и показываем как «было»,
    - но решает не он.
    """
    def stage(name: str, frac: float) -> None:
        if on_stage:
            on_stage(name, frac)

    why = blocked()
    if why:
        return {"ok": False, "error": why}

    stage("меряю, как сейчас", 0.08)
    before = measure("auto", log)
    if before.get("error") or not before.get("short"):
        return {"ok": False, "error": "не вышло замерить - смотрите журнал работы"}

    if not installed():
        if not install(stage, log):
            return {"ok": False, "error": "не удалось поставить - смотрите журнал"}
    log("dml: колесо на месте, меряю видеокарту")

    stage("меряю на видеокарте", 0.60)
    gpu = measure("auto", log)
    res = {
        "installed": True,
        "before": before.get("short"),
        "before_device": str(before.get("device") or ""),
        "long_before": before.get("long"),
        "gpu": gpu.get("short"),
        "long_gpu": gpu.get("long"),
        "device": str(gpu.get("device") or ""),
    }
    if gpu.get("error") or res["device"] not in ("dml", "cuda"):
        # Колесо встало, а видеокарта не завелась: старый драйвер, карта без
        # DirectX 12, виртуалка без проброса. Диктовка при этом цела - в том же
        # колесе лежит и процессорный провайдер.
        res["ok"] = False
        res["error"] = "видеокарта не отозвалась"
        stage("видеокарта не отозвалась", 1.0)
        return res

    stage("проверяю процессор", 0.82)
    cpu = measure("cpu", log)
    res["cpu"] = cpu.get("short")
    res["long_cpu"] = cpu.get("long")
    if not res["cpu"]:
        res["ok"] = False
        res["error"] = "не вышло замерить процессор - смотрите журнал"
        return res

    # Откат - только если новое колесо испортило САМ процессор. Сравнивать
    # можно лишь с процессорным замером «до»: если до этого считала видеокарта,
    # сравнивать нечего и откатываться не с чего.
    if (res["before_device"] == "cpu"
            and res["cpu"] > res["before"] * _CPU_TOLERANCE):
        log(f"dml: новое колесо испортило процессор "
            f"({res['before']:.3f} -> {res['cpu']:.3f} с) - откатываюсь")
        res["broke_cpu"] = True
        res["ok"] = False
        res["error"] = "новое колесо оказалось медленнее - вернул как было"
        stage("возвращаю как было", 0.95)
        restore(log)
        res["installed"] = False
        stage("вернул как было", 1.0)
        return res

    res["ok"] = bool(res["gpu"] < res["cpu"])
    stage("готово", 1.0)
    return res


if __name__ == "__main__":
    # Замерочный процесс. Зовётся из measure(), руками полезен для проверки:
    #     python dml_setup.py --bench auto
    if len(sys.argv) > 1 and sys.argv[1] == "--bench":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            out = _bench(sys.argv[2] if len(sys.argv) > 2 else "auto")
        except Exception as e:  # noqa: BLE001 - родитель ждёт метку в любом случае
            out = {"error": f"{type(e).__name__}: {e}"}
        print(MARK + json.dumps(out))
    else:
        print("сейчас считает:", "видеокарта" if available() else "процессор")
        print("колесо на диске:", installed())
        print("почему нельзя: ", blocked() or "-")
