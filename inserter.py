"""Вставка текста в активное окно.

Режим paste (по умолчанию): текст кладётся в буфер обмена, шлётся
Ctrl+V, затем прежний текстовый буфер восстанавливается - как делает
Wispr Flow. Мгновенно при любой длине текста.

Ctrl+V шлётся через keybd_event с виртуальными кодами (VK_CONTROL, 'V'):
библиотека keyboard маппит буквы через текущую раскладку, и на русской
раскладке "ctrl+v" у неё не срабатывает. VK-коды от раскладки не зависят.

Режим type: посимвольный ввод юникод-событиями SendInput - медленнее,
но работает там, где Ctrl+V не вставляет (старая cmd.exe и т.п.).
"""

import ctypes
import time

import win32api
import win32clipboard
import win32con

VK_BACK = 0x08
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_C = 0x43
VK_V = 0x56


_MODS = (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN)
# Ctrl/Shift/Alt корёжат вставку, и их безопасно «отжать» программно.
# Win не трогаем: его одиночный KEYUP открывает меню «Пуск».
_FORCE_RELEASE = (VK_SHIFT, VK_CONTROL, VK_MENU)


def _held(vk: int) -> bool:
    return bool(win32api.GetAsyncKeyState(vk) & 0x8000)


def _wait_modifiers_released(timeout: float = 1.5) -> None:
    """Ждём, пока физически отпущены Ctrl/Shift/Alt/Win: иначе наш Ctrl+V
    превратится в Ctrl+Shift+V и т.п.

    Если хоткей - комбинация, «отпустил» ловится по первой же клавише, и
    человек вполне может ещё держать Ctrl+Shift, пока мы распознаём. Ждать
    его вечно нельзя, вставлять с зажатым Shift - тоже, поэтому по истечении
    таймаута отжимаем модификаторы сами. Физическое отпускание позже пришлёт
    ещё один KEYUP - он безвреден.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not any(_held(vk) for vk in _MODS):
            return
        time.sleep(0.02)
    for vk in _FORCE_RELEASE:
        if _held(vk):
            win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.03)


def _send_ctrl_v() -> None:
    win32api.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(0.01)
    win32api.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.02)
    win32api.keybd_event(VK_V, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


def _send_ctrl_c() -> None:
    win32api.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(0.01)
    win32api.keybd_event(VK_C, 0, 0, 0)
    time.sleep(0.02)
    win32api.keybd_event(VK_C, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("padding", ctypes.c_ubyte * 32)]

    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_ulong), ("u", _U)]


_INPUT_KEYBOARD = 1
_KEYEVENTF_UNICODE = 0x0004
_KEYEVENTF_KEYUP = 0x0002


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.SendInput.restype = ctypes.c_uint
_user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(_INPUT), ctypes.c_int]

_CHUNK = 400  # событий за один SendInput


def _key_event(vk: int, scan: int, flags: int) -> _INPUT:
    inp = _INPUT()
    inp.type = _INPUT_KEYBOARD
    inp.ki = _KEYBDINPUT(vk, scan, flags, 0, None)
    return inp


def _send(events: list[_INPUT]) -> bool:
    """Отправить события порциями.

    Очередь ввода не резиновая: один гигантский SendInput на несколько тысяч
    событий часть из них просто теряет.
    """
    if not events:
        return True
    ok = True
    for i in range(0, len(events), _CHUNK):
        part = events[i:i + _CHUNK]
        arr = (_INPUT * len(part))(*part)
        sent = _user32.SendInput(len(part), arr, ctypes.sizeof(_INPUT))
        ok = ok and sent == len(part)
        if len(events) > _CHUNK:
            time.sleep(0.005)
    return ok


def _type_unicode(text: str) -> bool:
    """Посимвольный ввод через SendInput KEYEVENTF_UNICODE - любая раскладка,
    любые символы (кириллица, эмодзи через суррогатные пары).
    """
    raw = text.replace("\n", "\r").encode("utf-16-le")
    units = [int.from_bytes(raw[i:i + 2], "little") for i in range(0, len(raw), 2)]
    return _send([_key_event(0, unit, flags)
                  for unit in units
                  for flags in (_KEYEVENTF_UNICODE,
                                _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP)])


VK_RETURN = 0x0D


def press_enter() -> bool:
    """Нажать Enter - голосовая команда «нажми энтер» (отправка в чатах).

    Скан-код обязателен, как и везде: с нулём события уходят, но приложения,
    читающие ввод по скан-кодам, их не видят (HANDOFF.md).
    """
    _wait_modifiers_released()
    scan = win32api.MapVirtualKey(VK_RETURN, 0)
    return _send([_key_event(VK_RETURN, scan, flags)
                  for flags in (0, _KEYEVENTF_KEYUP)])


def backspace(count: int) -> bool:
    """Стереть count символов - отмена последней вставки.

    Backspace, а не Ctrl+Z: отмена у каждого приложения своя, где-то её нет
    вовсе, а где-то она откатит не наш кусок, а весь абзац разом. Backspace
    предсказуем везде, где вообще есть текстовое поле.

    Скан-код обязателен: с нулём события уходят, но приложения, читающие ввод
    по скан-кодам, их не видят - те же грабли, что с хоткеями (HANDOFF.md).
    """
    if count <= 0:
        return True
    _wait_modifiers_released()
    scan = win32api.MapVirtualKey(VK_BACK, 0)
    return _send([_key_event(VK_BACK, scan, flags)
                  for _ in range(count)
                  for flags in (0, _KEYEVENTF_KEYUP)])


def _get_clipboard_text() -> str | None:
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return None
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return None


def _set_clipboard_text(text: str) -> bool:
    for _ in range(3):
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                return True
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(0.05)  # буфер бывает занят другим процессом
    return False


def copy_selection(timeout: float = 0.6) -> tuple[str | None, str | None]:
    """Забрать выделенное в активном окне. Возвращает (выделение, прежний буфер).

    Выделение - None, если не выделено ничего. Прежний буфер отдаём наружу,
    чтобы вызвавший вернул его на место, когда закончит.

    Ловушка, ради которой всё и написано так: если ничего не выделено, Ctrl+C
    НЕ ОЧИЩАЕТ буфер - в нём останется то, что человек копировал час назад. Без
    проверки мы приняли бы это за выделение и молча переписали бы Ollama чужой
    текст, а результат вставили бы поверх пустого места. Поэтому: чистим буфер
    сами, жмём Ctrl+C, ждём - и если пусто, значит выделения не было.

    Метка вместо пустой строки: EmptyClipboard() оставляет буфер вовсе без
    формата CF_UNICODETEXT, и _get_clipboard_text вернёт None и на «пусто», и
    на «в буфере картинка». Своя метка отличает «мы вычистили, и Ctrl+C ничего
    не дал» от всего остального.
    """
    _wait_modifiers_released()
    old = _get_clipboard_text()
    mark = "\x00flowlocal-selection-probe\x00"
    if not _set_clipboard_text(mark):
        return None, old
    _send_ctrl_c()
    deadline = time.time() + timeout
    while time.time() < deadline:
        cur = _get_clipboard_text()
        if cur is not None and cur != mark:
            return cur, old
        time.sleep(0.03)
    # Метка на месте - Ctrl+C ничего не положил, выделения не было.
    if old is not None:
        _set_clipboard_text(old)
    else:
        _set_clipboard_text("")
    return None, old


# Сколько ждать после Ctrl+V, прежде чем вернуть прежний буфер.
#
# Ждём вслепую, потому что узнать «приложение уже забрало текст» нельзя: буфер
# не сообщает о чтении, а WM_RENDERFORMAT требует своего окна с очередью
# сообщений в том же потоке - у рабочего потока её нет.
#
# Фиксированные 300 мс были ошибкой, и вот почему. Приложение читает буфер не в
# момент Ctrl+V, а позже, разобрав WM_PASTE, и на длинном тексте не успевает.
# У соседей это воспроизведено с точностью до цифр: до 90 знаков вставлялось
# всегда, 202 и 520 - молча не вставлялось ничего. Молча - это худшая часть:
# конвейер рапортует успех, а человек получает свой прошлый буфер вместо письма
# и винит распознавание.
#
# Но и «просто поднять задержку» - неправильный ответ, там есть обратная
# ловушка: чем дольше наша диктовка лежит в буфере, тем вероятнее, что человек
# скопировал ссылку ДО диктовки, жмёт Ctrl+V после неё и получает диктовку
# второй раз. У соседей это вылезло регрессией на 2000 мс.
#
# Поэтому ждём по длине: короткому тексту - прежние 300 мс (то есть для обычной
# фразы не меняется ничего и регрессии взяться неоткуда), длинному - до 1.2 с,
# ровно там, где отказ иначе стопроцентный.
_RESTORE_MIN = 0.3
_RESTORE_MAX = 1.2
_RESTORE_PER_CHAR = 0.45 / 1000   # +450 мс на тысячу знаков


def _restore_wait(n: int) -> float:
    return min(_RESTORE_MAX, _RESTORE_MIN + _RESTORE_PER_CHAR * max(0, n))


def insert(text: str, mode: str = "paste", restore: bool = True) -> bool:
    """Вставить текст в активное окно. True - получилось.

    Провалились - оставляем диктовку в буфере обмена: тогда человека спасает
    Ctrl+V, не открывая окно программы. Иначе текст живёт только в «Повторить
    последнюю», за которой надо лезть в трей.
    """
    if not text:
        return True
    _wait_modifiers_released()
    if mode == "type":
        if _type_unicode(text):
            return True
        _set_clipboard_text(text)
        return False

    old = _get_clipboard_text() if restore else None
    if not _set_clipboard_text(text):
        return _type_unicode(text)   # буфер занят намертво - хотя бы напечатаем
    time.sleep(0.05)
    # Перед самим Ctrl+V убеждаемся, что в буфере всё ещё НАШ текст. Менеджеры
    # буфера (Ditto, Punto, «Журнал буфера обмена» Windows) подписаны на
    # изменения и умеют переписать буфер сразу после нас - тогда Ctrl+V вставил
    # бы их версию.
    if _get_clipboard_text() != text and not _set_clipboard_text(text):
        return _type_unicode(text)
    _send_ctrl_v()
    if restore and old is not None:
        time.sleep(_restore_wait(len(text)))
        # Возвращаем прежний буфер, только если в буфере всё ещё наша диктовка.
        # Успел человек за это время скопировать своё - его копия важнее нашей
        # уборки, и затирать её мы не имеем права.
        if _get_clipboard_text() == text:
            _set_clipboard_text(old)
    return True
