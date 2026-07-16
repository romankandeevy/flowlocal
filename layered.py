"""Окно с попиксельной альфой поверх всех окон (Win32 layered window).

Зачем не tkinter: tk умеет только прямоугольник и глобальную прозрачность
(-alpha) либо цветовой ключ (-transparentcolor). Ключ режет сглаживание -
у скруглённых углов появляется кайма, а тень невозможна в принципе.
UpdateLayeredWindow берёт содержимое из RGBA-битмапа и композитит его с
экраном по альфе каждого пикселя: настоящие сглаженные углы и мягкая тень.

Окно создаётся голым Win32 в потоке tkinter: mainloop прокачивает очередь
сообщений потока, и наш DefWindowProc получает своё. Ввод окну не нужен -
WS_EX_TRANSPARENT пропускает клики насквозь, WS_EX_NOACTIVATE не даёт
украсть фокус у окна, в которое диктуют (украли бы - Ctrl+V ушёл бы не туда).

Битмап (DIB) создаётся один раз и переиспользуется: numpy пишет прямо в
его память, лишних копий на кадр нет.
"""

import ctypes
import os
from ctypes import wintypes

import numpy as np
from PIL import Image

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ---------- константы ----------

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4

HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010

ULW_ALPHA = 0x02
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01

MONITOR_DEFAULTTONEAREST = 2
MDT_EFFECTIVE_DPI = 0


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte),
        ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat", ctypes.c_ubyte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT), ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
    ]


# ---------- сигнатуры ----------
# Без argtypes ctypes считает хэндлы 32-битными int и на x64 молча рвёт
# старшие биты: SelectObject падает с OverflowError, а то и хуже - тихо
# работает не с тем объектом. Описываем всё, что зовём.

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)

user32.DefWindowProcW.restype = ctypes.c_longlong
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.RegisterClassW.restype = wintypes.ATOM
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.UpdateLayeredWindow.restype = wintypes.BOOL
user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT), ctypes.POINTER(wintypes.SIZE),
    wintypes.HDC, ctypes.POINTER(wintypes.POINT), wintypes.DWORD,
    ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HMONITOR
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromPoint.restype = wintypes.HMONITOR
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE,
                                   wintypes.DWORD]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]


# ---------- DPI ----------


def set_dpi_awareness() -> None:
    """Per-monitor v2. Без этого Windows растягивает окно на масштабе >100%
    и всё, что мы аккуратно сгладили, превращается в мыло.

    Звать до создания первого окна (в т.ч. до tk.Tk()).
    """
    try:  # Win10 1703+
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except (AttributeError, OSError):
        pass
    try:  # Win8.1+
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
        return
    except (AttributeError, OSError):
        pass
    try:
        user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def tk_hwnd(widget) -> int:
    """HWND верхнеуровневого окна tkinter.

    winfo_id() отдаёт хэндл внутреннего окна Tk, а стили и оформление живут
    на его родителе - системной рамке. Поэтому GetParent, а не winfo_id.
    """
    widget.update_idletasks()
    child = widget.winfo_id()
    parent = user32.GetParent(child)
    return parent or child


def style_titlebar(hwnd: int, caption=None, dark: bool = True) -> None:
    """Заголовок окна под нашу тему средствами DWM: рамка становится
    продолжением интерфейса, а не чужой полосой сверху.

    dark управляет цветом кнопок и текста заголовка - их рисует Windows, и
    подобрать их через caption нельзя: на светлой теме белые крестик и
    подпись просто исчезли бы. На старых сборках атрибуты игнорируются.
    """
    try:
        dwm = ctypes.WinDLL("dwmapi")
    except OSError:
        return

    def attr(code: int, value: int) -> None:
        try:
            dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), wintypes.DWORD(code),
                                      ctypes.byref(ctypes.c_int(value)),
                                      ctypes.sizeof(ctypes.c_int))
        except OSError:
            pass

    attr(20, int(dark))   # DWMWA_USE_IMMERSIVE_DARK_MODE
    attr(19, int(dark))   # то же на сборках 1809 (старый код атрибута)
    attr(33, 2)           # DWMWA_WINDOW_CORNER_PREFERENCE = ROUND
    if caption is not None:
        # COLORREF - это 0x00BBGGRR, а не привычный RGB
        attr(35, (caption[2] << 16) | (caption[1] << 8) | caption[0])
        attr(34, (caption[2] << 16) | (caption[1] << 8) | caption[0])


def _monitor_dpi(hmon) -> int:
    try:
        shcore = ctypes.WinDLL("shcore")
        x, y = wintypes.UINT(), wintypes.UINT()
        if shcore.GetDpiForMonitor(hmon, MDT_EFFECTIVE_DPI,
                                   ctypes.byref(x), ctypes.byref(y)) == 0:
            return int(x.value) or 96
    except (AttributeError, OSError):
        pass
    return 96


def foreground_process() -> str:
    """Имя exe окна, в которое сейчас пишут: 'outlook.exe', 'telegram.exe'.

    Нужно правилам тона: в почте формально, в чате свободно. Спрашиваем у окна,
    а не у списка процессов - важно именно то, куда уедет текст.

    Пустая строка, если спросить не удалось (окна нет, процесс чужого сеанса,
    доступ закрыт). Правила тона тогда просто не сработают - молча, потому что
    диктовка важнее тона.
    """
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    # PROCESS_QUERY_LIMITED_INFORMATION: минимум прав, которого хватает на имя.
    # PROCESS_QUERY_INFORMATION потребовал бы больше и ломался бы на чужих
    # процессах с более высокой целостностью.
    h = kernel32.OpenProcess(0x1000, False, pid.value)
    if not h:
        return ""
    try:
        size = wintypes.DWORD(260)
        buf = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return ""
        return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(h)


def active_monitor() -> tuple[wintypes.RECT, float]:
    """Рабочая область монитора с активным окном и его масштаб (1.0 = 96 dpi).

    Именно с активным, а не главным: пилюля должна всплыть там, куда человек
    сейчас смотрит и диктует. Если активного окна нет - берём монитор под курсором.
    """
    hwnd = user32.GetForegroundWindow()
    if hwnd:
        hmon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    else:
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
        r = wintypes.RECT(0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
        return r, 1.0
    return mi.rcWork, _monitor_dpi(hmon) / 96.0


# ---------- окно ----------

_CLASS_NAME = "FlowLocalLayered"
_class_atom = None
_wndproc_ref = None  # ctypes не держит ссылку на колбэк - держим сами, иначе GC


def _register_class() -> None:
    global _class_atom, _wndproc_ref
    if _class_atom is not None:
        return

    def proc(hwnd, msg, wparam, lparam):
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    _wndproc_ref = WNDPROC(proc)
    wc = WNDCLASSW()
    wc.style = 0
    wc.lpfnWndProc = ctypes.cast(_wndproc_ref, ctypes.c_void_p)
    wc.hInstance = ctypes.WinDLL("kernel32").GetModuleHandleW(None)
    wc.lpszClassName = _CLASS_NAME
    atom = user32.RegisterClassW(ctypes.byref(wc))
    if not atom:
        err = ctypes.get_last_error()
        if err != 1410:  # ERROR_CLASS_ALREADY_EXISTS
            raise ctypes.WinError(err)
    _class_atom = atom or 1


class LayeredWindow:
    """Прозрачное окно поверх всех, содержимое - RGBA-картинка PIL.

    Не потокобезопасно: создавать и дёргать только из потока tkinter.
    """

    def __init__(self, w: int, h: int):
        _register_class()
        self._w = self._h = 0
        self._screen_dc = user32.GetDC(None)
        self._mem_dc = gdi32.CreateCompatibleDC(self._screen_dc)
        self._hbmp = None
        self._old_bmp = None
        self._arr = None
        self._visible = False
        self._x = self._y = 0
        self.hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
            | WS_EX_NOACTIVATE | WS_EX_TOPMOST,
            _CLASS_NAME, "FlowLocal", WS_POPUP,
            0, 0, w, h, None, None, None, None)
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self._alloc(w, h)

    def _alloc(self, w: int, h: int) -> None:
        if w == self._w and h == self._h:
            return
        self._free_bitmap()
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h        # top-down: строка 0 сверху, как у PIL
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0    # BI_RGB
        bits = ctypes.c_void_p()
        self._hbmp = gdi32.CreateDIBSection(self._screen_dc, ctypes.byref(bmi), 0,
                                            ctypes.byref(bits), None, 0)
        if not self._hbmp:
            raise ctypes.WinError(ctypes.get_last_error())
        self._old_bmp = gdi32.SelectObject(self._mem_dc, self._hbmp)
        buf = (ctypes.c_ubyte * (w * h * 4)).from_address(bits.value)
        self._arr = np.ctypeslib.as_array(buf).reshape(h, w, 4)
        self._w, self._h = w, h

    def _free_bitmap(self) -> None:
        self._arr = None
        if self._hbmp:
            if self._old_bmp:
                gdi32.SelectObject(self._mem_dc, self._old_bmp)
                self._old_bmp = None
            gdi32.DeleteObject(self._hbmp)
            self._hbmp = None

    def push(self, img: Image.Image, x: int, y: int, alpha: float = 1.0) -> None:
        """Показать кадр в точке (x, y). alpha 0..1 - общая непрозрачность.

        Общая альфа идёт через BLENDFUNCTION, а не домножением пикселей:
        так дешевле и точнее - анимация появления не трогает картинку.
        """
        if img.size != (self._w, self._h):
            self._alloc(*img.size)
        src = np.frombuffer(img.tobytes("raw", "BGRA"), dtype=np.uint8)
        src = src.reshape(self._h, self._w, 4)
        # UpdateLayeredWindow ждёт premultiplied alpha: RGB уже умножены на A
        a = src[:, :, 3].astype(np.uint16)
        rgb = src[:, :, :3].astype(np.uint16)
        rgb *= a[:, :, None]
        rgb //= 255
        self._arr[:, :, :3] = rgb.astype(np.uint8)
        self._arr[:, :, 3] = src[:, :, 3]

        if not self._visible:
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self._visible = True
        pt_dst = wintypes.POINT(int(x), int(y))
        size = wintypes.SIZE(self._w, self._h)
        pt_src = wintypes.POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, int(max(0.0, min(1.0, alpha)) * 255), AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(self.hwnd, self._screen_dc, ctypes.byref(pt_dst),
                                   ctypes.byref(size), self._mem_dc, ctypes.byref(pt_src),
                                   0, ctypes.byref(blend), ULW_ALPHA)
        self._x, self._y = int(x), int(y)

    def raise_(self) -> None:
        """Вернуть поверх всех: чужое topmost-окно могло всплыть выше."""
        user32.SetWindowPos(self.hwnd, wintypes.HWND(HWND_TOPMOST), 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def hide(self) -> None:
        if self._visible:
            user32.ShowWindow(self.hwnd, SW_HIDE)
            self._visible = False

    @property
    def visible(self) -> bool:
        return self._visible

    def destroy(self) -> None:
        self.hide()
        self._free_bitmap()
        if self._mem_dc:
            gdi32.DeleteDC(self._mem_dc)
            self._mem_dc = None
        if self._screen_dc:
            user32.ReleaseDC(None, self._screen_dc)
            self._screen_dc = None
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
