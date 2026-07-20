"""Расшифровка готового файла: декодирование, память, битые файлы.

Модель здесь не нужна - проверяется всё ДО неё: что файл превратился в 16 кГц
моно float32, что часовой подкаст не съел память и что чужой файл не уронил
программу. Дальше начинается общий конвейер, и его покрывают test_long.py
(резка) и test_clean.py (чистка).

Образцы делаем на месте из синусоиды 440 Гц - libsndfile умеет писать wav, mp3,
ogg/opus и flac, то есть три обязательных формата из четырёх плюс подарочный.
Синусоида, а не шум, не случайно: по ней видно не только что «что-то
раскодировалось», но и что раскодировалось ПРАВИЛЬНО - тон обязан остаться на
440 Гц. Промах в частоте дискретизации вдвое сдвинул бы его на 880, и никакая
проверка длины этого бы не поймала.

Четвёртый формат - m4a. Его libsndfile не пишет и не читает (AAC в нём нет и не
будет), поэтому рядом лежит готовый `test.m4a` на 5.8 КБ. Сделать его на лету
нечем: единственная библиотека, которая умеет AAC, весит 66 МБ и в проект не
взята - почему, разобрано в шапке audiofile.py.

Запуск: python test_audiofile.py
"""

import os
import shutil
import sys
import tempfile
import tracemalloc

import numpy as np

import audiofile as A
from recorder import SAMPLE_RATE

ok = True

TONE_HZ = 440.0
M4A = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test.m4a")


def check(cond: bool, text: str) -> None:
    global ok
    ok = ok and bool(cond)
    print(("  ок   " if cond else "ПРОВАЛ ") + text)


def tone(seconds: float, rate: int, channels: int = 1) -> np.ndarray:
    t = np.arange(int(seconds * rate), dtype=np.float32) / rate
    wave = (0.5 * np.sin(2 * np.pi * TONE_HZ * t)).astype(np.float32)
    if channels == 1:
        return wave
    # Каналы делаем РАЗНЫМИ: одинаковые прошли бы и при «взять левый», и при
    # «усреднить», то есть не проверили бы ничего.
    return np.stack([wave, wave * 0.5], axis=1)


def peak_hz(audio: np.ndarray, rate: int = SAMPLE_RATE) -> float:
    """Самая громкая частота. По ней видно, что запись не только прочитана, но
    и прочитана с правильной частотой дискретизации."""
    if audio.size < 1024:
        return 0.0
    spec = np.abs(np.fft.rfft(audio * np.hanning(audio.size)))
    return float(np.fft.rfftfreq(audio.size, 1 / rate)[int(np.argmax(spec))])


def write(path: str, data: np.ndarray, rate: int, **kw) -> str:
    import soundfile as sf

    sf.write(path, data, rate, **kw)
    return path


def formats(tmp: str) -> None:
    """Каждый формат превращается в 16 кГц моно float32."""
    print("\n-- форматы --")
    cases = [
        ("wav 16 кГц моно", "a.wav", 16000, 1, {}),
        ("wav 44.1 кГц стерео", "b.wav", 44100, 2, {}),
        ("mp3 44.1 кГц стерео", "c.mp3", 44100, 2, {"format": "MP3"}),
        ("ogg/opus 48 кГц стерео (голосовое телеги)", "d.ogg", 48000, 2,
         {"format": "OGG", "subtype": "OPUS"}),
        ("flac 44.1 кГц моно", "e.flac", 44100, 1, {"format": "FLAC"}),
    ]
    for name, fname, rate, ch, kw in cases:
        path = write(os.path.join(tmp, fname), tone(3.0, rate, ch), rate, **kw)
        audio = A.decode(path)
        check(audio.dtype == np.float32, f"{name}: float32")
        check(audio.ndim == 1, f"{name}: одна дорожка, а не стерео")
        # Три секунды с допуском: у сжатия с потерями бывает хвост кодера.
        secs = audio.size / SAMPLE_RATE
        check(abs(secs - 3.0) < 0.2, f"{name}: длина {secs:.2f} с вместо 3.00")
        got = peak_hz(audio)
        check(abs(got - TONE_HZ) < 15,
              f"{name}: тон на {got:.0f} Гц - частота не уехала")

    # m4a: готовым файлом, собрать его на месте нечем - см. шапку.
    if not os.path.exists(M4A):
        check(False, f"m4a: рядом нет {os.path.basename(M4A)} - образец потерян")
        return
    audio = A.decode(M4A)
    check(audio.dtype == np.float32 and audio.ndim == 1,
          "m4a (через Media Foundation): 16 кГц моно float32")
    secs = audio.size / SAMPLE_RATE
    # ЛОВУШКА, на которой уже попадались. HE-AAC заявляет удвоенную частоту, и
    # пока мы верили заявленному, половина записи пропадала молча: две секунды
    # превращались в одну. Проверка на длину - единственное, что это ловит.
    check(1.9 < secs < 2.3,
          f"m4a: длина {secs:.2f} с - SBR не украл половину записи")
    check(float(np.abs(audio).max()) > 0.01, "m4a: в записи есть звук, а не ноль")


def resampling(tmp: str) -> None:
    """Пересчёт частоты и сведение в моно - там, где ошибка не видна глазом."""
    print("\n-- пересчёт --")
    for rate in (8000, 22050, 44100, 48000):
        path = write(os.path.join(tmp, f"r{rate}.wav"), tone(2.0, rate), rate)
        audio = A.decode(path)
        check(abs(audio.size - 2 * SAMPLE_RATE) <= SAMPLE_RATE // 100,
              f"{rate} Гц -> {audio.size} отсчётов (ждали {2 * SAMPLE_RATE})")
        got = peak_hz(audio)
        check(abs(got - TONE_HZ) < 15, f"  тон после {rate} Гц остался на {got:.0f}")

    # Своя частота пересчёта не требует - и не должна его получить.
    path = write(os.path.join(tmp, "native.wav"), tone(2.0, SAMPLE_RATE), SAMPLE_RATE)
    audio = A.decode(path)
    check(audio.size == 2 * SAMPLE_RATE,
          "16 кГц проходит насквозь без единого лишнего отсчёта")

    # Стерео сводится СРЕДНИМ. Каналы в tone() разной громкости, поэтому
    # «взять левый» дал бы 0.5, а среднее даёт 0.375.
    path = write(os.path.join(tmp, "st.wav"), tone(2.0, 16000, 2), 16000)
    audio = A.decode(path)
    check(abs(float(np.abs(audio).max()) - 0.375) < 0.02,
          "стерео сведено средним по каналам, а не обрезано до левого")


def memory(tmp: str) -> None:
    """Длинный файл не съедает память.

    Проверяем не абсолютное число (оно поедет на другой машине), а СВОЙСТВО:
    расход растёт вместе с ИТОГОМ, а не вместе с исходником. Итог - это 16 кГц
    моно, то есть в 11 раз легче, чем 44.1 кГц стерео на входе. Если бы файл
    читался целиком, вдвое более длинная запись стоила бы вдвое большего
    исходника; у нас она стоит вдвое большего итога, а это в 11 раз меньше.
    """
    print("\n-- память на длинной записи --")
    import soundfile as sf

    rate = 44100
    seen = {}
    for secs in (180, 360):
        path = os.path.join(tmp, f"long{secs}.wav")
        # Пишем кусками: сама проверка не должна держать в памяти то, чего она
        # не разрешает держать проверяемому.
        with sf.SoundFile(path, "w", samplerate=rate, channels=2,
                          subtype="PCM_16") as f:
            for _ in range(secs):
                f.write(tone(1.0, rate, 2))
        tracemalloc.start()
        audio = A.decode(path)
        _cur, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        whole = secs * rate * 2 * 4          # если бы прочитали целиком
        seen[secs] = (peak, audio.nbytes)
        check(abs(audio.size - secs * SAMPLE_RATE) <= SAMPLE_RATE,
              f"{secs} с: раскодировано целиком ({audio.size / SAMPLE_RATE:.1f} с)")
        check(peak < whole,
              f"{secs} с: пик {peak / 1048576:.0f} МБ меньше, чем чтение "
              f"целиком ({whole / 1048576:.0f} МБ)")
        del audio
        os.remove(path)

    grew = seen[360][0] - seen[180][0]
    out_grew = seen[360][1] - seen[180][1]
    check(grew < 2 * out_grew,
          f"вдвое более длинная запись стоила +{grew / 1048576:.0f} МБ при "
          f"итоге +{out_grew / 1048576:.0f} МБ - расход идёт за итогом, "
          f"а не за исходником")


def human(message: str) -> bool:
    """Годится ли фраза человеку, который просто перетащил голосовое."""
    bad = ("0x", "Error", "error", "Traceback", "Exception", "None",
           "libsndfile", "HRESULT")
    return (bool(message.strip()) and len(message) < 90
            and not any(b in message for b in bad))


def broken(tmp: str) -> None:
    """Битый файл не роняет программу, а объясняется словами."""
    print("\n-- битые и чужие файлы --")
    rng = np.random.default_rng(7)

    cases = []
    # Мусор под каждым из расширений: и там, где читает libsndfile, и там, где
    # Media Foundation. Обе дороги обязаны вернуться с фразой, а не с падением.
    for ext in (".wav", ".mp3", ".ogg", ".m4a", ".flac"):
        path = os.path.join(tmp, "junk" + ext)
        with open(path, "wb") as f:
            f.write(bytes(rng.integers(0, 256, 4096, dtype=np.uint8)))
        cases.append(("мусор в " + ext, path))

    # Обрезанный настоящий файл - беда правдоподобнее случайных байтов:
    # заголовок на месте, данных нет. Скачанное наполовину голосовое выглядит
    # ровно так.
    good = write(os.path.join(tmp, "whole.ogg"), tone(3.0, 48000), 48000,
                 format="OGG", subtype="OPUS")
    half = os.path.join(tmp, "half.ogg")
    with open(good, "rb") as src, open(half, "wb") as dst:
        dst.write(src.read()[:200])
    cases.append(("обрезанный ogg", half))

    # Пустой файл нулевой длины.
    empty = os.path.join(tmp, "empty.wav")
    open(empty, "wb").close()
    cases.append(("пустой файл", empty))

    for name, path in cases:
        try:
            A.decode(path)
            check(False, f"{name}: прошёл молча, хотя не должен был")
        except A.AudioFileError as e:
            check(human(str(e)), f"{name}: отказ фразой - «{e}»")
        except Exception as e:  # noqa: BLE001 - это и есть проверяемый провал
            check(False, f"{name}: улетело чужое исключение "
                         f"{type(e).__name__}: {e}")

    # ГЛАВНОЕ: после всех отказов программа жива и следующий файл читается.
    path = write(os.path.join(tmp, "after.wav"), tone(1.0, 16000), 16000)
    try:
        audio = A.decode(path)
        check(audio.size == SAMPLE_RATE,
              "после всех битых файлов обычный читается как ни в чём не бывало")
    except Exception as e:  # noqa: BLE001
        check(False, f"после битых файлов сломалось чтение обычного: {e}")


def unknown(tmp: str) -> None:
    """Неизвестное расширение отвергается понятной фразой."""
    print("\n-- не наши файлы --")
    cases = [
        ("документ Word", "письмо.docx"),
        ("картинка", "снимок.png"),
        ("программа", "setup.exe"),
        ("видео, которого мы не обещали", "клип.avi"),
        ("без расширения вовсе", "заметка"),
        ("точка есть, расширения нет", "странный."),
    ]
    for name, fname in cases:
        path = os.path.join(tmp, fname)
        with open(path, "wb") as f:
            f.write(b"x" * 64)
        try:
            A.decode(path)
            check(False, f"{name}: приняли, хотя не умеем такое открывать")
        except A.AudioFileError as e:
            check(human(str(e)), f"{name}: «{e}»")
        except Exception as e:  # noqa: BLE001
            check(False, f"{name}: чужое исключение {type(e).__name__}")

    # Отсутствующий файл - отдельная беда с отдельной фразой: «нет на месте» и
    # «не тот формат» человек чинит по-разному.
    try:
        A.decode(os.path.join(tmp, "нетуменя.mp3"))
        check(False, "несуществующий файл прошёл")
    except A.AudioFileError as e:
        check(human(str(e)) and "мест" in str(e),
              f"несуществующий файл: «{e}»")

    # ЛОВУШКА: расширение в верхнем регистре. Телеграм отдаёт .OGG, айфон -
    # .M4A, и отказать им значило бы отказать половине настоящих случаев.
    check(A.supported("голосовое.OGG") and A.supported("Запись.M4A"),
          "РАСШИРЕНИЕ В ВЕРХНЕМ РЕГИСТРЕ принимается наравне со строчным")
    check(not A.supported("письмо.docx"), "чужое расширение не принимается")


def estimate() -> None:
    """Предупреждение о длинной записи: оценка честная, а не выдуманная."""
    print("\n-- оценка времени --")
    check(A.LONG_MINUTES == 30, "порог предупреждения - 30 минут, как в плане")
    hour = A.estimate(3600)
    check(0 < hour < 3600,
          f"час записи расшифруется быстрее часа (обещаем {hour / 60:.0f} мин)")
    check(A.estimate(3600) > A.estimate(1800),
          "чем длиннее запись, тем больше обещанное время")
    check(A.estimate(0) >= 1, "нулевая запись не обещает ноль минут")


def duration_probe(tmp: str) -> None:
    """Длину спрашиваем ДО расшифровки - иначе предупреждать нечем."""
    print("\n-- длина до расшифровки --")
    path = write(os.path.join(tmp, "dur.ogg"), tone(5.0, 48000), 48000,
                 format="OGG", subtype="OPUS")
    check(abs(A.duration(path) - 5.0) < 0.2,
          f"ogg: длина {A.duration(path):.2f} с известна до чтения")
    if os.path.exists(M4A):
        check(abs(A.duration(M4A) - 2.0) < 0.3,
              f"m4a: длина {A.duration(M4A):.2f} с известна до чтения")
    # Не узнали - это законный ответ, а не падение: без длины просто не будет
    # предупреждения, а работа пойдёт.
    junk = os.path.join(tmp, "nolen.wav")
    with open(junk, "wb") as f:
        f.write(b"\0" * 100)
    check(A.duration(junk) == 0.0, "нечитаемому файлу длина отвечает нулём")


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="flowlocal_audio_")
    try:
        formats(tmp)
        resampling(tmp)
        memory(tmp)
        broken(tmp)
        unknown(tmp)
        estimate()
        duration_probe(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nИТОГ:", "всё сходится" if ok else "ЕСТЬ ПРОВАЛЫ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
