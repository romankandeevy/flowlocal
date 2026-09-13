"""Замер моделей распознавания на своей речи - этап 1 плана.

Решает судьбу этапов 2 и 6: переезжаем на onnx-asr + GigaAM или остаёмся на
Whisper с полутора гигабайтами CUDA. Цифрам из статей не верим: у Сбера свой
интерес, на Хабре датасет синтетический и крошечный. Меряем на своём
микрофоне, своими словами, на своём железе.

    python tools/bench_asr.py record        # записать образцы: Enter - старт, Enter - стоп
    python tools/bench_asr.py run           # прогнать все модели по образцам
    python tools/bench_asr.py run --only gigaam-rnnt-int8 whisper-turbo-gpu

Образцы - в samples/: NN.wav (16 кГц, PCM16, моно) и NN.txt рядом с ним - что
было сказано на самом деле. Эталон пишет человек, поэтому WER получается
честный: модель сверяется с речью, а не с другой моделью.

Эталон пишем так, как хотим увидеть текст на экране: с пунктуацией и цифрами
там, где они уместны. Для диктовки это и есть цель, а не «набор слов» - модель,
которая распознала всё верно, но вывалила поток без точек, работу не сделала.

Каждая модель считается в отдельном процессе. Так честно меряется память (в
одном процессе пики моделей сложились бы), onnxruntime не делит CUDA-контекст с
CTranslate2, а падение одной модели не уносит весь замер.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import wave
from dataclasses import dataclass

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)                     # как app.py: приложение живёт от своего корня

SAMPLES_DIR = os.path.join(ROOT, "samples")
RESULT_MARK = "##RESULT##"         # по этой метке родитель выкусывает json из stdout


# --------------------------------------------------------------------------
# что с чем сравниваем


@dataclass(frozen=True)
class Spec:
    model: str                     # идентификатор для загрузчика
    kind: str                      # onnx | faster-whisper
    quant: str | None = None       # int8 | None (fp32)
    device: str = "cpu"            # cpu | cuda
    note: str = ""


SPECS: dict[str, Spec] = {
    # Кандидат на умолчание: RNN-T точнее CTC, e2e сам ставит пунктуацию.
    "gigaam-rnnt-int8": Spec("gigaam-v3-e2e-rnnt", "onnx", "int8", "cpu",
                             "кандидат в умолчание"),
    # Тот же RNN-T без квантизации: показывает, сколько точности стоят
    # сэкономленные 660 МБ (int8 226 МБ против fp32 885 МБ).
    "gigaam-rnnt-fp32": Spec("gigaam-v3-e2e-rnnt", "onnx", None, "cpu",
                             "цена квантизации"),
    # Ослабленный вариант - ровно его возит Handy. Меряем, чтобы знать, на
    # сколько именно лидер ниши сделал русский вполсилы.
    "gigaam-ctc-int8": Spec("gigaam-v3-e2e-ctc", "onnx", "int8", "cpu",
                            "то, что возит Handy"),
    # Действующий чемпион: 1.6 ГБ и обязательная CUDA.
    # Требует faster-whisper, которого в requirements уже нет: этот замер -
    # прощание с ним, а не поддержка. Нет пакета - строка выпадет из таблицы.
    "whisper-turbo-gpu": Spec("large-v3-turbo", "faster-whisper", None, "cuda",
                              "то, что возили до переезда"),
}

DEFAULT_ORDER = list(SPECS)


# --------------------------------------------------------------------------
# WER


_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def normalize(s: str) -> list[str]:
    """Слова для сравнения: без регистра, без пунктуации, ё = е.

    Пунктуацию для WER снимаем намеренно: иначе модель без неё получила бы
    штраф дважды - и за отсутствие точки, и за «слипшиеся» слова. Пунктуация
    меряется отдельной колонкой.
    """
    s = s.lower().replace("ё", "е")
    return _PUNCT.sub(" ", s).split()


def edit_distance(ref: list[str], hyp: list[str]) -> int:
    """Левенштейн по словам. Матрицу целиком не держим - хватает строки."""
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1,            # удаление
                           cur[j - 1] + 1,         # вставка
                           prev[j - 1] + (r != h)))  # замена
        prev = cur
    return prev[-1]


def punct_density(s: str) -> float:
    """Знаков препинания на 100 слов. Ноль = модель отдаёт голый поток слов."""
    words = len(s.split()) or 1
    return 100.0 * len(re.findall(r"[.,!?;:—-]", s)) / words


# --------------------------------------------------------------------------
# образцы


def read_wav(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        assert w.getsampwidth() == 2, "нужен PCM16"
        assert w.getframerate() == 16000, "нужно 16 кГц"
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if w.getnchannels() > 1:
            data = data.reshape(-1, w.getnchannels()).mean(axis=1).astype(np.int16)
    return data.astype(np.float32) / 32768.0


def write_wav(path: str, audio: np.ndarray) -> None:
    pcm = np.clip(audio * 32768.0, -32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm.tobytes())


def load_samples(d: str = SAMPLES_DIR) -> list[tuple[str, np.ndarray, str]]:
    """[(имя, аудио, эталон)] из папки. Без .txt образец не годится: сверять не с чем."""
    out = []
    if not os.path.isdir(d):
        return out
    for name in sorted(os.listdir(d)):
        if not name.endswith(".wav"):
            continue
        stem = name[:-4]
        ref_path = os.path.join(d, stem + ".txt")
        if not os.path.exists(ref_path):
            print(f"  {stem}: нет {stem}.txt - пропускаю")
            continue
        with open(ref_path, encoding="utf-8") as f:
            ref = f.read().strip()
        if not ref:
            continue
        out.append((stem, read_wav(os.path.join(d, name)), ref))
    return out


def cmd_record(_args) -> None:
    """Диктуем образцы. Хоткей и оверлей не нужны - консоли достаточно."""
    from recorder import Recorder

    os.makedirs(SAMPLES_DIR, exist_ok=True)
    used = {n[:-4] for n in os.listdir(SAMPLES_DIR) if n.endswith(".wav")}
    n = 1

    print("Запись образцов. Говорите то, что реально диктуете: рабочие фразы,")
    print("имена, термины, числа. Нужно 15-20 штук по 5-15 секунд.")
    print("Эталон пишите так, как хотите увидеть текст на экране.")
    print("Пустая строка вместо эталона - образец выбрасывается. Ctrl+C - выход.\n")

    rec = Recorder(pre_buffer_sec=0.3, keep_open=True)
    try:
        while True:
            while f"{n:02d}" in used:
                n += 1
            stem = f"{n:02d}"
            try:
                input(f"[{stem}] Enter - начать запись...")
            except (EOFError, KeyboardInterrupt):
                break
            rec.start()
            t0 = time.time()
            try:
                input("      говорите, Enter - стоп...")
            except (EOFError, KeyboardInterrupt):
                rec.stop()
                break
            audio = rec.stop()
            dur = time.time() - t0
            if audio.size < 16000 // 2:
                print("      слишком коротко, ещё раз\n")
                continue
            print(f"      {audio.size / 16000:.1f} с записано")
            try:
                ref = input("      что вы сказали? ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not ref:
                print("      выброшено\n")
                continue
            write_wav(os.path.join(SAMPLES_DIR, stem + ".wav"), audio)
            with open(os.path.join(SAMPLES_DIR, stem + ".txt"), "w", encoding="utf-8") as f:
                f.write(ref + "\n")
            used.add(stem)
            print(f"      сохранено -> samples/{stem}.wav ({dur:.1f} с)\n")
    finally:
        rec.close()

    print(f"\nВсего образцов: {len(used)}. Дальше: python tools/bench_asr.py run")


# --------------------------------------------------------------------------
# прогон одной модели (в своём процессе)


def _peak_ram_mb() -> float:
    """Пик рабочего набора процесса. psutil не тянем ради одного числа."""
    import ctypes
    import ctypes.wintypes as wt

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]

    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
    psapi.GetProcessMemoryInfo.restype = wt.BOOL
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wt.HANDLE

    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
        return 0.0
    return pmc.PeakWorkingSetSize / 1e6


def _onnx_size_mb(model) -> float:
    """Сколько весит модель на диске - по файлам, которые онжу реально открыл.

    Не по маске имён и не по размеру репозитория: в одном репозитории лежат все
    варианты сразу (fp32 и int8, ctc и rnnt), и папка целиком - это 852 МБ
    вместо честных 226.
    """
    import onnxruntime as rt

    total = 0.0
    seen: set[str] = set()
    for name in dir(model.asr):
        if name.startswith("__"):
            continue
        try:
            v = getattr(model.asr, name)
        except Exception:  # noqa: BLE001 - свойство может быть с побочкой
            continue
        if isinstance(v, rt.InferenceSession):
            p = getattr(v, "_model_path", None)
            if p and p not in seen and os.path.exists(p):
                seen.add(p)
                total += os.path.getsize(p)
    return total / 1e6


def _dir_size_mb(d: str) -> float:
    """Размер папки. Симлинки не считаем: кэш HuggingFace хранит файл один раз в
    blobs/, а в snapshots/ кладёт ссылку на него - без этой проверки Whisper
    насчитывал 3.2 ГБ вместо своих 1.6."""
    total = 0
    for root, _dirs, files in os.walk(d):
        for f in files:
            p = os.path.join(root, f)
            try:
                if os.path.islink(p):
                    continue
                total += os.path.getsize(p)
            except OSError:
                pass
    return total / 1e6


def _load_onnx(spec: Spec):
    import onnx_asr

    providers = ["CUDAExecutionProvider"] if spec.device == "cuda" else ["CPUExecutionProvider"]
    model = onnx_asr.load_model(spec.model, quantization=spec.quant, providers=providers)
    return model, (lambda a: model.recognize(a)), _onnx_size_mb(model)


def _add_cuda_dlls() -> None:
    """cuBLAS/cuDNN из колёс nvidia-* должны быть видны ДО импорта ctranslate2.

    Жило в transcriber.py, пока он был на faster-whisper. После переезда на
    onnx-asr там этого нет и не нужно - а здесь нужно: иначе Whisper молча
    свалится с CUDA на CPU, и замер сравнит GigaAM не с чемпионом, а с калекой.
    """
    import site

    try:
        paths = site.getsitepackages() + [site.getusersitepackages()]
    except Exception:  # noqa: BLE001
        return
    for sp in paths:
        nv = os.path.join(sp, "nvidia")
        if not os.path.isdir(nv):
            continue
        for pkg in os.listdir(nv):
            b = os.path.join(nv, pkg, "bin")
            if os.path.isdir(b):
                try:
                    os.add_dll_directory(b)
                    os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")
                except OSError:
                    pass


def _load_faster_whisper(spec: Spec):
    """Старый бэкенд - ради него весь замер и затевался.

    Зовём faster-whisper напрямую, а не через transcriber.py: тот уже переехал
    на onnx-asr и слова «large-v3-turbo» больше не понимает. Пакета может не
    быть вовсе (из requirements он ушёл) - тогда модель просто выпадет из
    сравнения, о чём родитель и напишет.
    """
    from app_paths import MODELS_DIR

    _add_cuda_dlls()
    from faster_whisper import WhisperModel

    ct = "float16" if spec.device == "cuda" else "int8"
    model = WhisperModel(spec.model, device=spec.device, compute_type=ct,
                         download_root=MODELS_DIR)

    def run(audio: np.ndarray) -> str:
        # Те же параметры, с которыми модель работала в приложении до переезда:
        # сравниваем с тем, что было на самом деле, а не с идеальным Whisper.
        segments, _info = model.transcribe(
            audio, language="ru", beam_size=5, vad_filter=True,
            condition_on_previous_text=False)
        return " ".join(s.text.strip() for s in segments).strip()

    key = spec.model.split("/")[-1].replace("-", "").lower()
    size = 0.0
    for name in os.listdir(MODELS_DIR) if os.path.isdir(MODELS_DIR) else []:
        if name.startswith("models--") and key in name.replace("-", "").lower():
            size = _dir_size_mb(os.path.join(MODELS_DIR, name))
    return model, run, size


def cmd_one(args) -> None:
    """Прогон одной модели. Пишет json в stdout - его читает родитель."""
    key = args.key
    spec = SPECS[key]
    samples = load_samples()
    if not samples:
        print(RESULT_MARK + json.dumps({"key": key, "error": "нет образцов"}))
        return

    t0 = time.time()
    if spec.kind == "onnx":
        _model, run, size_mb = _load_onnx(spec)
    else:
        _model, run, size_mb = _load_faster_whisper(spec)
    load_s = time.time() - t0

    # Прогрев. Одного вызова мало: у onnxruntime первые прогоны тратятся на рост
    # арены памяти и раскрутку пула потоков, и на одном образце этот хвост
    # уезжал прямо в медиану (1.4 с вместо честных 0.65 с). Греем настоящим
    # аудио и трижды - дальше время выходит на полку.
    for _ in range(3):
        run(samples[0][1])

    ref_words = hyp_errors = 0
    times: list[float] = []
    audio_s = 0.0
    worst: tuple[str, float, str, str] | None = None
    punct: list[float] = []
    texts = []

    for stem, audio, ref in samples:
        t = time.time()
        hyp = run(audio)
        dt = time.time() - t
        times.append(dt)
        audio_s += audio.size / 16000

        r, h = normalize(ref), normalize(hyp)
        err = edit_distance(r, h)
        wer = err / max(1, len(r))
        ref_words += len(r)
        hyp_errors += err
        punct.append(punct_density(hyp))
        texts.append({"stem": stem, "ref": ref, "hyp": hyp, "wer": wer})
        if worst is None or wer >= worst[1]:
            worst = (stem, wer, ref, hyp)
        print(f"  {stem}: {dt:.2f}s wer={wer:.1%} {hyp[:60]}", file=sys.stderr)

    times.sort()
    result = {
        "key": key,
        "model": spec.model,
        "quant": spec.quant or "fp32",
        "device": spec.device,
        "note": spec.note,
        "wer": hyp_errors / max(1, ref_words),
        "median_s": times[len(times) // 2],
        "max_s": times[-1],
        "xrt": audio_s / max(1e-9, sum(times)),
        "load_s": load_s,
        "ram_mb": _peak_ram_mb(),
        "size_mb": size_mb,
        "punct": sum(punct) / len(punct),
        "worst": {"stem": worst[0], "wer": worst[1], "ref": worst[2], "hyp": worst[3]}
                 if worst else None,
        "texts": texts,
    }
    print(RESULT_MARK + json.dumps(result, ensure_ascii=False))


# --------------------------------------------------------------------------
# прогон всех моделей


def cmd_run(args) -> None:
    samples = load_samples()
    if not samples:
        print("Образцов нет. Сначала: python tools/bench_asr.py record")
        return
    total_s = sum(a.size for _n, a, _r in samples) / 16000
    print(f"Образцов: {len(samples)}, {total_s:.0f} с речи\n")

    keys = args.only or DEFAULT_ORDER
    results = []
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    for key in keys:
        if key not in SPECS:
            print(f"неизвестная модель: {key}")
            continue
        spec = SPECS[key]
        print(f"--- {key}  ({spec.model}, {spec.quant or 'fp32'}, {spec.device})")
        t0 = time.time()
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "_one", key],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        line = next((ln for ln in proc.stdout.splitlines() if ln.startswith(RESULT_MARK)), None)
        if line is None:
            print(f"    упало за {time.time() - t0:.0f} с:")
            print("    " + (proc.stderr or proc.stdout or "").strip()[-500:].replace("\n", "\n    "))
            continue
        r = json.loads(line[len(RESULT_MARK):])
        if "error" in r:
            print("    " + r["error"])
            continue
        results.append(r)
        print(f"    wer={r['wer']:.1%}  {r['median_s']:.2f}s  {r['ram_mb']:.0f}MB  "
              f"{r['size_mb']:.0f}MB\n")

    if not results:
        return

    print()
    print(f"{'модель':<20} {'WER':>7} {'медиана':>9} {'xRT':>6} {'RAM':>7} "
          f"{'диск':>8} {'зн/100сл':>9}")
    print("-" * 72)
    for r in sorted(results, key=lambda x: x["wer"]):
        print(f"{r['key']:<20} {r['wer']:>6.1%} {r['median_s']:>8.2f}s "
              f"{r['xrt']:>5.1f}x {r['ram_mb']:>6.0f}M {r['size_mb']:>7.0f}M "
              f"{r['punct']:>8.1f}")
    print()
    for r in sorted(results, key=lambda x: x["wer"]):
        w = r["worst"]
        if not w or not w["wer"]:
            continue                        # ошибок нет - показывать нечего
        print(f"{r['key']}: худший образец {w['stem']} ({w['wer']:.0%})")
        print(f"   сказано: {w['ref']}")
        print(f"   выдано:  {w['hyp']}")

    out = os.path.join(ROOT, "tools", "bench_asr.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nПодробности: {os.path.relpath(out, ROOT)}")

    # Критерий из плана 2.1: GigaAM на CPU не хуже turbo на GPU и укладывается
    # в секунду -> переключаем умолчание и отказываемся от обязательной CUDA.
    best = min(results, key=lambda x: x["wer"])
    whisper = next((r for r in results if r["key"] == "whisper-turbo-gpu"), None)
    giga = next((r for r in results if r["key"] == "gigaam-rnnt-int8"), None)
    print()
    if giga and whisper:
        verdict = ("ДА" if giga["wer"] <= whisper["wer"] and giga["median_s"] <= 1.0
                   else "НЕТ")
        print(f"Критерий 2.1 (GigaAM на CPU не хуже turbo на GPU и < 1 с): {verdict}")
        print(f"  GigaAM  {giga['wer']:.1%} / {giga['median_s']:.2f}s / {giga['size_mb']:.0f} МБ")
        print(f"  Whisper {whisper['wer']:.1%} / {whisper['median_s']:.2f}s / {whisper['size_mb']:.0f} МБ")
    print(f"Лучшая по WER: {best['key']} ({best['wer']:.1%})")


def main() -> None:
    p = argparse.ArgumentParser(description="Замер моделей распознавания")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("record", help="записать образцы с микрофона")
    r = sub.add_parser("run", help="прогнать модели по образцам")
    r.add_argument("--only", nargs="+", metavar="KEY",
                   help=f"что мерить: {', '.join(SPECS)}")
    o = sub.add_parser("_one", help=argparse.SUPPRESS)
    o.add_argument("key")
    args = p.parse_args()
    {"record": cmd_record, "run": cmd_run, "_one": cmd_one}[args.cmd](args)


if __name__ == "__main__":
    main()
