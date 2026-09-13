"""int8 против fp32 на нашей модели - этап 26 плана.

Зачем вообще спрашивать. Мы возим int8 с самого этапа 2 и ни разу не проверяли,
что он даёт. Считается, что квантизация - размен точности на скорость. Но
собственный бенчмарк onnx-asr на Ryzen 9800X3D показывает для GigaAM v3 RNN-T
RTFx 42.6 (fp32) против 42.8 (int8) - то есть разницы нет вовсе, и int8 у нас
может оказаться разменом точности НИ НА ЧТО.

Верить той таблице напрямую нельзя по двум причинам, и обе честные:
  - там не наш вариант модели: мы возим e2e (с пунктуацией и нормализацией),
    а в таблице обычный RNN-T. Совпадают ли цифры - не сказано;
  - эффект квантизации у каждой модели свой, и сильно. В той же таблице у
    GigaAM v2 RNN-T int8 медленнее ВДВОЕ (39.7 против 15.9), а у Whisper base
    вдвое быстрее (23.7 против 51.6). По чужой модели про свою не судят.

Что этот замер решает и чего НЕ решает. Он меряет скорость и память. Точность
он не меряет: для неё нужны samples/ - своя речь и свой эталон, написанный
человеком, - а их на машине нет. Но скорость решает, стоит ли вообще заводить
разговор про точность: окажется fp32 заметно медленнее - вопрос закрыт, и
никаких образцов записывать не надо.

Каждый режим - в отдельном процессе: иначе пики памяти двух моделей сложатся и
цифра будет враньём.

    python tools/bench_quant.py            # прогнать оба и сравнить
    python tools/bench_quant.py one int8   # один режим (так его зовёт первый)
"""

import json
import os
import statistics
import subprocess
import sys
import time
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

RUNS = 7
WAV = os.path.join(ROOT, "test.wav")


def peak_mb() -> float:
    """Пик рабочего набора процесса. Через Win32, без psutil - лишняя
    зависимость ради одной цифры не нужна."""
    import ctypes
    import ctypes.wintypes as wt

    class _PMC(ctypes.Structure):
        _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]

    # restype и argtypes обязательны. Без них ctypes считает, что функции
    # возвращают и принимают int, дескриптор процесса на 64 битах обрезается,
    # вызов проваливается - и, поскольку код возврата никто не смотрел, замер
    # молча печатал «0 МБ». Ровно так и было в первом прогоне.
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    k32.GetCurrentProcess.restype = wt.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(_PMC), wt.DWORD]
    psapi.GetProcessMemoryInfo.restype = wt.BOOL

    pmc = _PMC()
    pmc.cb = ctypes.sizeof(_PMC)
    if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(),
                                      ctypes.byref(pmc), pmc.cb):
        raise OSError(f"GetProcessMemoryInfo: {ctypes.get_last_error()}")
    return pmc.PeakWorkingSetSize / 1e6


def read_wav(path):
    import numpy as np

    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
        a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if w.getnchannels() == 2:
            a = a.reshape(-1, 2).mean(axis=1)
        return a, w.getframerate(), w.getnframes() / w.getframerate()


def dir_mb(path: str) -> float:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total / 1e6


def one(quant: str) -> dict:
    import onnx_asr

    from transcriber import model_dir

    name = "gigaam-v3-e2e-rnnt"
    q = None if quant == "fp32" else quant
    path = model_dir(name, q)

    t0 = time.perf_counter()
    # Настройки те же, что в бою, - иначе меряли бы не то, чем пользуемся.
    import onnxruntime as rt

    so = rt.SessionOptions()
    so.intra_op_num_threads = 2
    so.inter_op_num_threads = 1
    so.add_session_config_entry("session.force_spinning_stop", "1")
    m = onnx_asr.load_model(name, path=path, quantization=q,
                            providers=["CPUExecutionProvider"], sess_options=so)
    load = time.perf_counter() - t0

    audio, sr, secs = read_wav(WAV)
    text = m.recognize(audio, sample_rate=sr)   # прогрев, он же проверка текста

    walls = []
    for _ in range(RUNS):
        t = time.perf_counter()
        m.recognize(audio, sample_rate=sr)
        walls.append(time.perf_counter() - t)

    return {"quant": quant, "load": load,
            "med": statistics.median(walls), "max": max(walls),
            "rtfx": secs / statistics.median(walls),
            "peak_mb": peak_mb(), "disk_mb": dir_mb(path), "text": text}


def main() -> int:
    if len(sys.argv) > 2 and sys.argv[1] == "one":
        print("@@" + json.dumps(one(sys.argv[2]), ensure_ascii=False))
        return 0

    if not os.path.exists(WAV):
        print("нет test.wav - мерить не на чем")
        return 2

    out = []
    for quant in ("int8", "fp32"):
        print(f"--- {quant}: считаю (модель может качаться, это надолго)")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, __file__, "one", quant],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env)
        line = next((x for x in r.stdout.splitlines() if x.startswith("@@")), None)
        if line is None:
            print(f"  ПРОВАЛ: {(r.stderr or r.stdout).strip()[:400]}")
            return 1
        d = json.loads(line[2:])
        out.append(d)
        print(f"  загрузка {d['load']:.1f} с | распознавание {d['med']:.3f} с "
              f"(худшее {d['max']:.3f}) | RTFx {d['rtfx']:.1f} | "
              f"память {d['peak_mb']:.0f} МБ | диск {d['disk_mb']:.0f} МБ")

    a, b = out
    print(f"\n{'':10} {'загрузка':>10} {'распозн.':>10} {'худшее':>10} "
          f"{'RTFx':>7} {'память':>9} {'диск':>9}")
    for d in out:
        print(f"{d['quant']:10} {d['load']:9.1f}с {d['med']:9.3f}с "
              f"{d['max']:9.3f}с {d['rtfx']:7.1f} {d['peak_mb']:8.0f}М "
              f"{d['disk_mb']:8.0f}М")

    slower = (b["med"] / a["med"] - 1) * 100
    print(f"\nfp32 против int8: по скорости {slower:+.0f}%, "
          f"по памяти {b['peak_mb'] - a['peak_mb']:+.0f} МБ, "
          f"по диску {b['disk_mb'] - a['disk_mb']:+.0f} МБ")
    print("\nТекст (одна фраза - это НЕ замер точности, только признак жизни):")
    for d in out:
        print(f"  {d['quant']}: {d['text']}")
    if a["text"] != b["text"]:
        print("  ^ тексты РАЗОШЛИСЬ - повод записать свою речь в samples/ и "
              "мерить точность всерьёз")
    else:
        print("  ^ тексты совпали, но одна фраза ничего не доказывает")
    return 0


if __name__ == "__main__":
    sys.exit(main())
