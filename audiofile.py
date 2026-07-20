"""Готовый аудиофайл -> 16 кГц моно float32.

Дальше запись идёт ТЕМ ЖЕ конвейером, что и микрофон: `transcriber.transcribe`
режет её на куски по 60 секунд, `cleaner.clean` ставит знаки, убирает бубнёж и
применяет словарь. Второго конвейера здесь нет и заводить его нельзя - иначе
расшифровка файла начнёт отставать от диктовки по качеству, причём молча.

---- Почему декодера два, а не один ----

Ни одна маленькая библиотека не берёт все четыре нужных формата. Замер (колёса
под Python 3.14, Windows, размер без numpy - он в сборке и так есть):

    декодер                   вес       wav  mp3  ogg/opus  m4a
    soundfile (libsndfile)    3.59 МБ   да   да   да        нет
    miniaudio 1.71            1.63 МБ   да   да   нет       нет
    PyAV 18 (ffmpeg внутри)  65.90 МБ   да   да   да        да
    Media Foundation          0         да   да   нет       да

Установщик сейчас 70 МБ. PyAV берёт всё, но почти удваивает его - за один
формат из четырёх это неприемлемо, и на этом он и отпал. miniaudio отпал на
opus: голосовые из телеграма - главный случай, ради которого задачу и завели.

Осталось сложить два: libsndfile закрывает opus, а AAC в нём нет вовсе и не
будет (в upstream его нет). AAC берёт Media Foundation - она уже стоит в каждой
Windows и весит ноль. Итог: +3.59 МБ на установщик вместо +65.90 МБ.

Порядок попыток - сначала libsndfile, потом Windows. Пересечение (wav, mp3)
достаётся первому намеренно: libsndfile одинаков на всех машинах, а набор
кодеков Windows у каждого свой, и отладить «у меня работает, у отца нет» на нём
нельзя. Media Foundation зовём только там, где libsndfile отказался.

Opus через Media Foundation НЕ проходит (проверено: 0xC00D36C4,
MF_E_UNSUPPORTED_BYTESTREAM_TYPE). Поддержку ogg в Windows добавляет отдельный
пакет Web Media Extensions, которого может не быть, - поэтому на неё и не
рассчитываем: opus держит libsndfile, и он в сборке.

---- Почему память не разъезжается на длинном файле ----

Час подкаста в 44.1 кГц стерео float32 - это 1.27 ГБ, если прочитать его
целиком. Поэтому читаем кусками: сводим в моно и пересчитываем частоту на лету,
и в памяти остаётся только итог - час в 16 кГц моно занимает 230 МБ, ровно
столько же, сколько заняла бы часовая диктовка с микрофона.

Кусок - целое число СЕКУНД исходной записи, и это не круглое число ради
красоты. Пересчёт частоты (`miniaudio.convert_frames`) не помнит предыдущий
вызов, поэтому на стыке кусков он в общем случае даёт разрыв. На границе целых
секунд разрыва нет: замер на mp3 44.1 кГц против пересчёта всей записи разом -

    кусок  1 с: макс. расхождение 0.06592
    кусок  5 с: макс. расхождение 0.00036
    кусок 30 с: макс. расхождение 0.00000   <- берём это

- при этом длина итога во всех трёх случаях совпадает с целым до отсчёта, то
есть время не уплывает. 30 секунд дают побитово тот же результат, что и чтение
целиком, и при этом держат в памяти 5 МБ вместо гигабайта.
"""

import os

import numpy as np

import platform_api
from recorder import SAMPLE_RATE

# Что открываем. Список ЗАКРЫТЫЙ: неизвестное расширение честнее отвергнуть
# фразой, чем пытаться и падать неизвестно как посреди работы.
#
# Обязательных по задаче четыре - wav, mp3, ogg/opus, m4a. Остальные приехали
# даром: flac умеет libsndfile, а mp4/aac/wma - Media Foundation, и каждый из
# них уже работает тем же кодом. Убирать работающее ради короткого списка
# незачем; человеку с голосовой заметкой в .wma объяснять, что формат «не
# поддерживается», пришлось бы на пустом месте.
SUPPORTED = (".wav", ".mp3", ".ogg", ".oga", ".opus", ".m4a", ".mp4", ".aac",
             ".flac", ".wma")

# Кусок чтения в секундах исходной записи - см. шапку, число выбрано замером.
_BLOCK_SEC = 30

# С этой длины предупреждаем оценкой времени до старта.
LONG_MINUTES = 30

# Во сколько раз распознавание быстрее реального времени. Число заниженное
# намеренно: обещать «две минуты» и уложиться в полторы не обидно, наоборот -
# обещать полторы и делать три значит соврать человеку, который на это
# рассчитывал. На этой машине GigaAM даёт около 9x (7.8 с записи за 0.85 с), на
# слабой - меньше; берём с запасом.
_SPEED = 4.0


class AudioFileError(Exception):
    """Причина, которую можно показать человеку.

    Обычное исключение сюда не годится: текст вида «LibsndfileError: Error
    opening ...: Format not recognised» человеку, который просто перетащил
    голосовое, не говорит ни что случилось, ни что делать. Поэтому каждый отказ
    ниже переведён во фразу, и фразы лежат в i18n.
    """


# ---------- разбор пути ----------


def supported(path: str) -> bool:
    return os.path.splitext(str(path or ""))[1].lower() in SUPPORTED


def check(path: str) -> None:
    """Можно ли вообще браться. Бросает AudioFileError с готовой фразой."""
    path = str(path or "")
    ext = os.path.splitext(path)[1].lower()
    if not ext:
        raise AudioFileError("у файла нет расширения - не пойму, что это")
    if ext not in SUPPORTED:
        raise AudioFileError("такие файлы я не открою - нужен wav, mp3, ogg или m4a")
    if not os.path.exists(path):
        raise AudioFileError("файла нет на месте")
    try:
        if os.path.getsize(path) == 0:
            raise AudioFileError("файл пустой")
    except OSError:
        raise AudioFileError("файл не читается") from None


# ---------- сколько это будет длиться ----------


def duration(path: str) -> float:
    """Длина записи в секундах. 0 - узнать не вышло.

    Спрашиваем ДО расшифровки: человеку с часовым подкастом надо сказать, во
    что он ввязывается, пока он ещё может передумать. Ноль - законный ответ:
    предупреждения просто не будет, а работа пойдёт.
    """
    try:
        import soundfile as sf

        return float(sf.info(path).duration)
    except Exception:  # noqa: BLE001 - libsndfile не знает AAC, спросим Windows
        pass
    try:
        return _mf_duration(path)
    except Exception:  # noqa: BLE001 - не узнали, и ладно
        return 0.0


def estimate(seconds: float) -> float:
    """Сколько примерно займёт расшифровка, в секундах."""
    return max(1.0, float(seconds) / _SPEED)


# ---------- пересчёт в 16 кГц моно ----------


class _ToTarget:
    """Копилка: принимает куски как есть, отдаёт 16 кГц моно float32.

    Держит остаток, не добравший до целой секунды исходной частоты, и
    пересчитывает только целые секунды - почему именно так, см. шапку модуля.
    """

    def __init__(self, rate: int, channels: int, expect: int = 0) -> None:
        self.rate = int(rate)
        self.channels = max(1, int(channels))
        self._pending: list[np.ndarray] = []   # моно, исходная частота
        self._held = 0
        self._out: list[np.ndarray] = []
        self._block = max(self.rate, self.rate * _BLOCK_SEC)
        # expect - сколько отсчётов ждём на выходе. Знаем заранее только на
        # дороге libsndfile (info.frames), и знать стоит дорого: без этого итог
        # собирается склейкой, а склейка в момент выделения держит и куски, и
        # готовый массив - то есть просит вдвое больше итога ровно в конце
        # работы, когда отступать уже некуда.
        #
        # Замер, 20 минут 44.1 кГц стерео, итог 73 МБ:
        #     без оценки  пик 160 МБ
        #     с оценкой   пик 105 МБ
        #     прочитать целиком стоило бы 404 МБ
        #
        # На коротких записях разницы почти нет (шесть минут: 58 против 54) -
        # там пик держат не куски, а рабочие буферы одного блока. Склейка
        # обгоняет их примерно с девяти минут, дальше растёт вдвое быстрее
        # итога, и именно длинные записи ради этого и разбираются.
        #
        # Запас в секунду: пересчёт частоты округляет, и итог бывает на
        # несколько отсчётов длиннее расчётного. Не хватило и его - молча
        # переходим на склейку, правильность от этого не страдает.
        self._buf = (np.empty(int(expect) + SAMPLE_RATE, dtype=np.float32)
                     if expect > 0 else None)
        self._at = 0

    def feed(self, block: np.ndarray) -> None:
        """block - (кадры, каналы) или (кадры,), float32."""
        if block.size == 0:
            return
        if block.ndim == 2:
            # Сводим в моно средним по каналам, а не берём первый: в записи с
            # разговором по телефону собеседники нередко разведены по каналам,
            # и «взять левый» потеряло бы половину разговора.
            mono = block.mean(axis=1, dtype=np.float32)
        else:
            mono = block.astype(np.float32, copy=False)
        self._pending.append(np.ascontiguousarray(mono, dtype=np.float32))
        self._held += mono.size
        if self._held >= self._block:
            self._drain(whole_only=True)

    def _drain(self, whole_only: bool) -> None:
        if not self._pending:
            return
        buf = np.concatenate(self._pending) if len(self._pending) > 1 \
            else self._pending[0]
        take = buf.size - buf.size % self._block if whole_only else buf.size
        if take <= 0:
            self._pending = [buf]
            self._held = buf.size
            return
        self._put(_resample(buf[:take], self.rate))
        rest = buf[take:]
        self._pending = [rest] if rest.size else []
        self._held = rest.size

    def _put(self, piece: np.ndarray) -> None:
        if self._buf is not None and self._at + piece.size <= self._buf.size:
            self._buf[self._at:self._at + piece.size] = piece
            self._at += piece.size
            return
        # Оценка не сошлась. Уже написанное отдаём ВИДОМ, а не копией: копия
        # здесь удвоила бы память ровно в том случае, ради которого всё и
        # затевалось.
        if self._buf is not None:
            self._out.append(self._buf[:self._at])
            self._buf = None
        self._out.append(piece)

    def result(self) -> np.ndarray:
        self._drain(whole_only=False)
        if self._buf is not None and not self._out:
            # Вид на чуть больший буфер: лишним остаётся не больше секунды
            # (64 КБ), и копировать ради них весь массив незачем.
            return self._buf[:self._at]
        if self._buf is not None:
            self._out.insert(0, self._buf[:self._at])
            self._buf = None
        return _join(self._out)


def _join(parts: list[np.ndarray]) -> np.ndarray:
    """Склеить куски в один массив, не удваивая память на последнем шаге.

    np.concatenate держит и список, и результат одновременно - то есть на
    часовой записи просит вдвое больше, чем нужно, ровно в конце работы, когда
    отступать уже некуда. Здесь кусок освобождается сразу после того, как его
    скопировали: в пике лежит итог плюс один кусок, а не итог дважды.

    Запасной путь: обычно итог собирается не здесь, а сразу в один буфер (см.
    _ToTarget). Сюда попадают только те, у кого длину заранее не спросить, -
    дорога Media Foundation, - и те, у кого оценка не сошлась.
    """
    total = sum(p.size for p in parts)
    if not total:
        return np.zeros(0, dtype=np.float32)
    out = np.empty(total, dtype=np.float32)
    at = 0
    for i, part in enumerate(parts):
        out[at:at + part.size] = part
        at += part.size
        parts[i] = None          # кусок больше не нужен - пусть уходит сейчас
    parts.clear()
    return out


def _resample(mono: np.ndarray, rate: int) -> np.ndarray:
    """Моно любой частоты -> моно 16 кГц. Своей частоте пересчёт не нужен."""
    if rate == SAMPLE_RATE:
        return np.ascontiguousarray(mono, dtype=np.float32)
    import miniaudio

    raw = miniaudio.convert_frames(
        miniaudio.SampleFormat.FLOAT32, 1, rate, mono.tobytes(),
        miniaudio.SampleFormat.FLOAT32, 1, SAMPLE_RATE)
    # frombuffer отдаёт вид на чужую память и только для чтения; копию делаем
    # сразу - дальше массив уедет в onnxruntime, а тот пишет по буферам.
    return np.frombuffer(raw, dtype=np.float32).copy()


# ---------- дорога первая: libsndfile ----------


def _read_sndfile(path: str, on_progress=None) -> np.ndarray:
    import soundfile as sf

    info = sf.info(path)
    if info.frames <= 0 or info.samplerate <= 0:
        raise AudioFileError("в файле нет звука")
    # Сколько ждём на выходе - чтобы копилка выделила итог один раз, а не
    # собирала его склейкой (см. _ToTarget.__init__).
    expect = int(info.frames * SAMPLE_RATE / info.samplerate)
    acc = _ToTarget(info.samplerate, info.channels, expect=expect)
    step = max(info.samplerate, info.samplerate * _BLOCK_SEC)
    done = 0
    for block in sf.blocks(path, blocksize=step, dtype="float32", always_2d=True):
        acc.feed(block)
        done += block.shape[0]
        if on_progress is not None and info.frames:
            on_progress(min(1.0, done / info.frames))
    return acc.result()


# ---------- дорога вторая: Media Foundation ----------
#
# Ровно ради AAC (.m4a) - того единственного формата из четырёх, которого нет в
# libsndfile. Пишем на ctypes, а не берём обёртку: обёртка была бы ещё одной
# зависимостью в сборке ради двадцати вызовов, а сами вызовы не меняются с
# Windows Vista.
#
# COM здесь руками, поэтому два правила соблюдаются буквально: у каждого
# полученного указателя есть свой Release, и MFShutdown зовётся в finally.
# Забыть их значит подтекать памятью при каждой расшифровке, а программа висит
# в трее сутками.

import ctypes  # noqa: E402 - только для этой дороги, держим рядом с ней
from ctypes import POINTER, byref, c_uint32, c_uint64, c_void_p  # noqa: E402

_FIRST_AUDIO = 0xFFFFFFFD
_MEDIASOURCE = 0xFFFFFFFF
_MF_VERSION = 0x00020070
_ENDOFSTREAM = 0x2


class _GUID(ctypes.Structure):
    _fields_ = [("d1", ctypes.c_uint32), ("d2", ctypes.c_uint16),
                ("d3", ctypes.c_uint16), ("d4", ctypes.c_ubyte * 8)]


class _PROPVARIANT(ctypes.Structure):
    # Длительность приезжает как VT_UI8, то есть в поле val. Полный PROPVARIANT
    # - это union на десятки типов; расписывать его целиком незачем, нам нужен
    # ровно один, а размер структуры (24 байта) держим с запасом.
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort),
                ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort),
                ("val", ctypes.c_uint64), ("pad", ctypes.c_uint64)]


# ctypes.windll / ctypes.WINFUNCTYPE - только Windows. Модуль импортируется
# лениво (app.py зовёт его на расшифровке файла), но GUID-константы и прототипы
# ниже считаются на уровне модуля - то есть при самом импорте. Чтобы `import
# audiofile` не падал на маке, _guid под darwin отдаёт нулевой GUID (он там всё
# равно не используется: libsndfile берёт wav/mp3/ogg/opus сам, а ветка Media
# Foundation для AAC/m4a под darwin отвергается в _mf_reader понятной фразой), а
# прототипы строим через кроссплатформенный CFUNCTYPE-псевдоним.
_WINFUNC = ctypes.WINFUNCTYPE if platform_api.IS_WINDOWS else ctypes.CFUNCTYPE


def _guid(text: str) -> _GUID:
    out = _GUID()
    if platform_api.IS_WINDOWS:
        ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p("{" + text + "}"),
                                            byref(out))
    return out


_MT_MAJOR = _guid("48eba18e-f8c9-4687-bf11-0a74c9f96a8f")
_MT_SUBTYPE = _guid("f7e34c9a-42e8-4714-b74b-cb29d72c35e5")
_AUDIO = _guid("73647561-0000-0010-8000-00AA00389B71")
_FLOAT = _guid("00000003-0000-0010-8000-00AA00389B71")
_CHANNELS = _guid("37e48bf5-645e-4c5b-89de-ada9e29b696a")
_RATE = _guid("5faeeae7-0290-4c31-9e8a-c534f68d9dba")
_PD_DURATION = _guid("6c990d33-bb8e-477a-8598-0d5d96fcd88a")

_BITS = _guid("f2deb57f-40fa-4764-aa33-ed4f2d1ff669")
_BLOCK_ALIGN = _guid("322de230-9eeb-43bd-ab7a-ff412251541d")
_BYTES_PER_SEC = _guid("1aab75c8-cfef-451c-ab95-ac034b8e1731")

_HR = ctypes.c_long
_Release = _WINFUNC(ctypes.c_ulong, c_void_p)
_SetGUID = _WINFUNC(_HR, c_void_p, POINTER(_GUID), POINTER(_GUID))
_SetU32 = _WINFUNC(_HR, c_void_p, POINTER(_GUID), c_uint32)
_GetU32 = _WINFUNC(_HR, c_void_p, POINTER(_GUID), POINTER(c_uint32))
_SetCurrentType = _WINFUNC(_HR, c_void_p, c_uint32,
                           POINTER(c_uint32), c_void_p)
_GetCurrentType = _WINFUNC(_HR, c_void_p, c_uint32, POINTER(c_void_p))
_GetPresentation = _WINFUNC(_HR, c_void_p, c_uint32, POINTER(_GUID),
                            POINTER(_PROPVARIANT))
_ReadSample = _WINFUNC(_HR, c_void_p, c_uint32, c_uint32,
                       POINTER(c_uint32), POINTER(c_uint32),
                       POINTER(c_uint64), POINTER(c_void_p))
_ToContiguous = _WINFUNC(_HR, c_void_p, POINTER(c_void_p))
_Lock = _WINFUNC(_HR, c_void_p, POINTER(POINTER(ctypes.c_byte)),
                 POINTER(c_uint32), POINTER(c_uint32))
_Unlock = _WINFUNC(_HR, c_void_p)

# Номера методов в таблице интерфейса. Держим именами, а не числами по месту:
# промах на единицу здесь - это не исключение, а вызов чужой функции с чужими
# аргументами, то есть падение всего процесса без следа в журнале.
_I_RELEASE = 2
_ATTR_GETU32 = 7
_ATTR_SETU32 = 21
_ATTR_SETGUID = 24
_RDR_GETCURRENT = 6
_RDR_SETCURRENT = 7
_RDR_READSAMPLE = 9
_RDR_PRESENTATION = 12
_SMP_CONTIGUOUS = 41
_BUF_LOCK = 3
_BUF_UNLOCK = 4


def _vt(ptr, index, proto):
    table = ctypes.cast(ptr, POINTER(POINTER(c_void_p))).contents
    return proto(table[index])


def _ok(what: str, code: int) -> None:
    if code < 0:
        raise AudioFileError(f"{what}: 0x{code & 0xFFFFFFFF:08X}")


def _mf_reader(path: str):
    """Открыть файл через Media Foundation. Зовущий обязан Release и MFShutdown."""
    if not platform_api.IS_WINDOWS:
        # Media Foundation - Windows-only, и это единственная дорога к AAC/m4a.
        # На маке замена - AVFoundation, отдельная задача; пока честный отказ.
        # Ветку зовут _read_mf и _mf_duration, обе - только когда libsndfile
        # уже отказался, то есть ровно на m4a/aac/wma.
        raise AudioFileError("файлы m4a/aac на macOS пока не открою - "
                             "пересохраните в wav, mp3 или ogg")
    mfplat = ctypes.windll.mfplat
    _ok("MFStartup", mfplat.MFStartup(_MF_VERSION, 1))
    reader = c_void_p()
    code = ctypes.windll.mfreadwrite.MFCreateSourceReaderFromURL(
        ctypes.c_wchar_p(os.path.abspath(path)), None, byref(reader))
    if code < 0:
        mfplat.MFShutdown()
        raise AudioFileError("файл не открылся - формат не тот или запись битая")
    return reader


def _mf_duration(path: str) -> float:
    reader = _mf_reader(path)
    try:
        pv = _PROPVARIANT()
        code = _vt(reader, _RDR_PRESENTATION, _GetPresentation)(
            reader, _MEDIASOURCE, byref(_PD_DURATION), byref(pv))
        if code < 0:
            return 0.0
        return pv.val / 1e7            # сотни наносекунд
    finally:
        _vt(reader, _I_RELEASE, _Release)(reader)
        ctypes.windll.mfplat.MFShutdown()


def _mf_want_target(media) -> None:
    """Заказать у Media Foundation ровно то, что нам нужно: 16 кГц моно float32.

    ЗДЕСЬ ПЕРЕСЧЁТ ДЕЛАЕТ WINDOWS, А НЕ MINIAUDIO - и это единственное место в
    модуле, где дороги расходятся. Сделано не из лени, а по замеру, и вот по
    какому.

    Сначала было «взять как есть и пересчитать самим», как на дороге
    libsndfile. На AAC это молча теряет половину записи. Файл: 2.000 секунды,
    16 кГц. Media Foundation отдаёт 33792 кадра (это верно - 2 секунды с
    хвостом кодера) и при этом ЗАЯВЛЯЕТ частоту 32000 Гц. Мы честно верили
    заявленному и пересчитывали 32000 -> 16000, то есть делили на два:

        как есть  -> 2 кан, 32000 Гц, 33792 кадра, «1.056 с»   <- враньё
        с заказом -> 1 кан, 16000 Гц, 33792 кадра,  2.112 с    <- правда

    Это SBR (spectral band replication) в HE-AAC: декодер сообщает удвоенную
    частоту. Проверить заявленное нечем - сам себе он противоречит (его же
    MF_PD_DURATION говорит 2.000 с), и разбирать этот спор в нашем коде
    значило бы гадать. Заказ снимает спор целиком: мы говорим, что хотим на
    выходе, и получаем ровно это. На обычном 44.1 кГц AAC результат тот же
    самый (125945 кадров и там и там) - то есть заказ ничего не портит, а
    ломающийся случай чинит.

    Полный набор полей, а не только частота с каналами: без BLOCK_ALIGNMENT и
    AVG_BYTES_PER_SECOND часть декодеров отказывает на SetCurrentMediaType.
    Для float32 моно это 4 байта на кадр и 64000 байт в секунду.
    """
    set_guid = _vt(media, _ATTR_SETGUID, _SetGUID)
    _ok("major", set_guid(media, byref(_MT_MAJOR), byref(_AUDIO)))
    _ok("subtype", set_guid(media, byref(_MT_SUBTYPE), byref(_FLOAT)))
    set_u32 = _vt(media, _ATTR_SETU32, _SetU32)
    set_u32(media, byref(_CHANNELS), 1)
    set_u32(media, byref(_RATE), SAMPLE_RATE)
    set_u32(media, byref(_BITS), 32)
    set_u32(media, byref(_BLOCK_ALIGN), 4)
    set_u32(media, byref(_BYTES_PER_SEC), SAMPLE_RATE * 4)


def _read_mf(path: str, on_progress=None) -> np.ndarray:
    reader = _mf_reader(path)
    media = c_void_p()
    current = c_void_p()
    try:
        _ok("MFCreateMediaType",
            ctypes.windll.mfplat.MFCreateMediaType(byref(media)))
        _mf_want_target(media)
        code = _vt(reader, _RDR_SETCURRENT, _SetCurrentType)(
            reader, _FIRST_AUDIO, None, media)
        if code < 0:
            raise AudioFileError("в файле нет звуковой дорожки")

        # Что вышло на самом деле. Спрашиваем, хотя и заказывали: отказать нам
        # SetCurrentMediaType мог бы только ошибкой, но молча выдать другое -
        # ровно та беда, из-за которой заказ и появился. Проверка стоит одного
        # вызова, а её отсутствие стоило половины записи.
        _ok("GetCurrentMediaType", _vt(reader, _RDR_GETCURRENT, _GetCurrentType)(
            reader, _FIRST_AUDIO, byref(current)))
        get_u32 = _vt(current, _ATTR_GETU32, _GetU32)
        channels = c_uint32()
        rate = c_uint32()
        _ok("каналы", get_u32(current, byref(_CHANNELS), byref(channels)))
        _ok("частота", get_u32(current, byref(_RATE), byref(rate)))
        if channels.value != 1 or rate.value != SAMPLE_RATE:
            raise AudioFileError("в файле нет звуковой дорожки")

        total = 0.0
        try:
            pv = _PROPVARIANT()
            if _vt(reader, _RDR_PRESENTATION, _GetPresentation)(
                    reader, _MEDIASOURCE, byref(_PD_DURATION), byref(pv)) >= 0:
                total = pv.val / 1e7
        except Exception:  # noqa: BLE001 - без длины просто не будет доли
            total = 0.0

        parts: list[np.ndarray] = []
        read = _vt(reader, _RDR_READSAMPLE, _ReadSample)
        done = 0
        while True:
            flags = c_uint32()
            index = c_uint32()
            stamp = c_uint64()
            sample = c_void_p()
            _ok("ReadSample", read(reader, _FIRST_AUDIO, 0, byref(index),
                                   byref(flags), byref(stamp), byref(sample)))
            if flags.value & _ENDOFSTREAM:
                break
            if not sample:
                # Законное состояние: поток ещё разгоняется, кадра пока нет.
                continue
            buf = c_void_p()
            try:
                _ok("ConvertToContiguousBuffer",
                    _vt(sample, _SMP_CONTIGUOUS, _ToContiguous)(sample, byref(buf)))
                data = POINTER(ctypes.c_byte)()
                cap = c_uint32()
                length = c_uint32()
                _ok("Lock", _vt(buf, _BUF_LOCK, _Lock)(buf, byref(data),
                                                       byref(cap), byref(length)))
                try:
                    # Копию делаем ОБЯЗАТЕЛЬНО и до Unlock: после него буфер
                    # принадлежит Media Foundation и может быть переиспользован
                    # под следующий кадр. Вид на чужую память пережил бы Unlock
                    # молча и отдал бы в конце кашу вместо речи.
                    raw = ctypes.string_at(data, length.value)
                finally:
                    _vt(buf, _BUF_UNLOCK, _Unlock)(buf)
                chunk = np.frombuffer(raw, dtype=np.float32).copy()
                parts.append(chunk)
                done += chunk.size
                if on_progress is not None and total > 0:
                    on_progress(min(1.0, done / (total * SAMPLE_RATE)))
            finally:
                if buf:
                    _vt(buf, _I_RELEASE, _Release)(buf)
                _vt(sample, _I_RELEASE, _Release)(sample)
        return _join(parts)
    finally:
        for ptr in (current, media, reader):
            if ptr:
                _vt(ptr, _I_RELEASE, _Release)(ptr)
        ctypes.windll.mfplat.MFShutdown()


# ---------- то, ради чего всё ----------


def decode(path: str, on_progress=None) -> np.ndarray:
    """Файл -> 16 кГц моно float32. Бросает AudioFileError с готовой фразой.

    on_progress(доля от 0 до 1) - если передан, зовётся по ходу чтения: час
    подкаста декодируется не мгновенно, и человек должен видеть, что работа
    идёт, а не гадать, зависло ли.
    """
    check(path)
    first: Exception | None = None
    try:
        audio = _read_sndfile(path, on_progress)
    except AudioFileError as e:
        first = e
        audio = None
    except Exception as e:  # noqa: BLE001 - libsndfile не знает AAC, это норма
        first = e
        audio = None
    if audio is None:
        try:
            audio = _read_mf(path, on_progress)
        except AudioFileError:
            raise
        except Exception as e:  # noqa: BLE001
            raise AudioFileError("файл не читается - похоже, запись битая") from e
    if audio.size < SAMPLE_RATE // 20:      # меньше 50 мс: распознавать нечего
        # Отдельная фраза, а не общий отказ: пустой файл и битый файл человек
        # чинит по-разному, и путать их значит отправлять его не туда.
        raise AudioFileError("в записи нет звука") from first
    return audio
