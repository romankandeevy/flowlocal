"""Приглушить музыку на время диктовки.

Зачем. Диктовать поверх музыки нельзя: слышно и вам, и микрофону. Просьба
подтверждена у соседей трижды и независимо - её просят чаще многих функций.

Почему пауза, а не приглушение. Приглушение идёт через системный микшер и
попадает не всегда: с USB-аудиоинтерфейсом оно просто не работает. Пауза
доходит до плеера в любом случае.

ГЛАВНАЯ ЛОВУШКА, ради которой здесь половина файла. Ходовой рецепт -
APPCOMMAND_MEDIA_PLAY_PAUSE - это ПЕРЕКЛЮЧАТЕЛЬ. Если музыка не играла, он её
ЗАПУСТИТ: человек начал диктовать в тишине, а ему заиграло. Поэтому:

    - шлём раздельные команды PAUSE и PLAY, а не переключатель;
    - и жмём их только тогда, когда звук ДЕЙСТВИТЕЛЬНО идёт.

«Действительно идёт» проверяем по уровню на выходе звуковой карты
(IAudioMeterInformation): тишина на выходе - значит паузить нечего, и мы не
трогаем ничего. Возобновляем только то, что сами и остановили.
"""

import ctypes
from ctypes import wintypes   # чистые псевдонимы типов, есть и на macOS

import platform_api

WM_APPCOMMAND = 0x0319
HWND_BROADCAST = 0xFFFF

APPCOMMAND_MEDIA_PLAY = 46
APPCOMMAND_MEDIA_PAUSE = 47

# Ниже этого уровня на выходе считаем, что ничего не играет.
#
# 0.001 было мало: сразу после любого звука счётчик показывает ещё 0.018 -
# хвост затухания, - и мы приняли бы его за играющую музыку. Замер на живой
# машине: тишина 0.000, хвост 0.018, системный звук 0.35.
_SILENCE = 0.01
# И меряем дважды с паузой: хвост затухания за это время падает, а музыка нет.
_SAMPLE_GAP = 0.07

# WM_APPCOMMAND и весь замер уровня через COM - только Windows. На macOS
# «системная пауза любому плееру» - частный API (MediaRemote), в открытом виде
# его нет; практичный путь - AppleScript конкретным плеерам, но это отдельная
# задача. Пока пауза музыки под darwin - заглушка: _send ничего не шлёт,
# output_level честно отвечает «не спросил», и Music поэтому просто не трогает
# ничего (playing() == False).
if platform_api.IS_WINDOWS:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.SendMessageW.argtypes = [wintypes.HWND, ctypes.c_uint,
                                     wintypes.WPARAM, wintypes.LPARAM]


def _send(command: int) -> None:
    if not platform_api.IS_WINDOWS:
        return
    _user32.SendMessageW(wintypes.HWND(HWND_BROADCAST), WM_APPCOMMAND,
                         wintypes.WPARAM(0), wintypes.LPARAM(command << 16))


# --------------------------------------------------------------------------
# Уровень на выходе - через COM, минимальным набором.

_CLSID_MMDeviceEnumerator = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
_IID_IMMDeviceEnumerator = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
_IID_IAudioMeterInformation = "{C02216F6-8C67-4B5B-9D00-D008E73E0064}"

_CLSCTX_ALL = 23
_eRender, _eConsole = 0, 0


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]


def _guid(text: str) -> _GUID:
    g = _GUID()
    ctypes.oledll.ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(g))
    return g


def output_level() -> float:
    """Насколько громко сейчас играет звук. -1 - спросить не удалось.

    Через COM руками: pycaw ради одного числа тянуть не станем, а comtypes у
    нас нет и не нужен.
    """
    if not platform_api.IS_WINDOWS:
        return -1.0            # не Windows: спросить нечем, значит «не играет»
    ole32 = ctypes.oledll.ole32
    try:
        ole32.CoInitializeEx(None, 0)
    except OSError:
        pass                       # уже инициализирован в этом потоке - не беда
    enum = ctypes.c_void_p()
    dev = ctypes.c_void_p()
    meter = ctypes.c_void_p()
    try:
        ole32.CoCreateInstance(ctypes.byref(_guid(_CLSID_MMDeviceEnumerator)),
                               None, _CLSCTX_ALL,
                               ctypes.byref(_guid(_IID_IMMDeviceEnumerator)),
                               ctypes.byref(enum))
        # Порядок методов в таблице COM-интерфейса: GetDefaultAudioEndpoint -
        # четвёртый (после трёх методов IUnknown и EnumAudioEndpoints).
        vt = ctypes.cast(enum, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        proto = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.c_int,
                                   ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))
        proto(vt[4])(enum, _eRender, _eConsole, ctypes.byref(dev))

        vt = ctypes.cast(dev, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        activate = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(_GUID),
            ctypes.c_uint, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
        activate(vt[3])(dev, ctypes.byref(_guid(_IID_IAudioMeterInformation)),
                        _CLSCTX_ALL, None, ctypes.byref(meter))

        vt = ctypes.cast(meter, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        peak = ctypes.c_float()
        getpeak = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p,
                                     ctypes.POINTER(ctypes.c_float))
        getpeak(vt[3])(meter, ctypes.byref(peak))
        return float(peak.value)
    except Exception:  # noqa: BLE001 - музыка не стоит диктовки
        return -1.0
    finally:
        for p in (meter, dev, enum):
            if p:
                try:
                    vt = ctypes.cast(p, ctypes.POINTER(
                        ctypes.POINTER(ctypes.c_void_p)))[0]
                    ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt[2])(p)
                except Exception:  # noqa: BLE001
                    pass


def playing() -> bool:
    """Идёт ли сейчас звук из колонок.

    Два замера с паузой, и оба должны быть выше порога. Одного мало: сразу
    после системного звука счётчик ещё не упал, и мы поставили бы на паузу
    музыку, которой нет, - а потом «вернули» бы её, включив человеку то, чего
    он не слушал.
    """
    import time

    if output_level() <= _SILENCE:
        return False
    time.sleep(_SAMPLE_GAP)
    return output_level() > _SILENCE


class Music:
    """Пауза на время диктовки. Возобновляет только то, что сама остановила."""

    def __init__(self, log) -> None:
        self.log = log
        self._paused = False

    def pause(self) -> None:
        if self._paused:
            return
        if not platform_api.IS_WINDOWS:
            platform_api.note_unsupported("пауза музыки на время диктовки")
            return
        if not playing():
            return                 # нечего останавливать - и не трогаем
        _send(APPCOMMAND_MEDIA_PAUSE)
        self._paused = True
        self.log("музыка на паузе")

    def resume(self) -> None:
        """Вернуть, если ставили мы. Иначе молчим.

        Флаг обязателен: без него мы жали бы «играть» после каждой диктовки и
        включали музыку человеку, который её не слушал.
        """
        if not self._paused:
            return
        self._paused = False
        _send(APPCOMMAND_MEDIA_PLAY)
        self.log("музыка снова играет")
