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

import platform_api

# win32* и SendInput/GetAsyncKeyState - только Windows. На macOS их нет
# (ModuleNotFoundError / у ctypes нет WinDLL), а вставка в чужое окно там идёт
# через CGEvent + NSPasteboard - отдельная большая задача. Пока: буфер обмена
# работает через Qt (см. _mac_* ниже), а сама вставка/backspace/enter - честные
# заглушки, возвращающие False. Импорт модуля при этом не падает.
if platform_api.IS_WINDOWS:
    import win32api
    import win32clipboard
    import win32con

VK_BACK = 0x08
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_A = 0x41
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


if platform_api.IS_WINDOWS:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.SendInput.restype = ctypes.c_uint
    _user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(_INPUT), ctypes.c_int]

_CHUNK = 400  # событий за один SendInput


def _mac_clipboard_get() -> str | None:
    """Буфер обмена через Qt - кроссплатформенный путь для не-Windows.

    Требует живого QApplication; в изоляции (без окна) вернёт None и не упадёт.
    """
    try:
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        if app is None:
            return None
        text = app.clipboard().text()
        return text if text else None
    except Exception:  # noqa: BLE001 - буфер не должен ронять диктовку
        return None


def _mac_clipboard_set(text: str) -> bool:
    try:
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        if app is None:
            return False
        app.clipboard().setText(text or "")
        return True
    except Exception:  # noqa: BLE001
        return False


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


def _tap(vk: int, up: bool = False) -> bool:
    """Одно нажатие или отпускание клавиши. False - система его не пустила.

    Скан-код обязателен, как и везде в этом файле: с нулём событие уходит, но
    приложения, читающие ввод по скан-кодам, его не видят (HANDOFF.md).
    """
    return _send([_key_event(vk, win32api.MapVirtualKey(vk, 0),
                             _KEYEVENTF_KEYUP if up else 0)])


def _send_ctrl_v() -> bool:
    """Послать Ctrl+V. False - система не пустила наши нажатия.

    Через SendInput, а не keybd_event, ровно из-за этого False. keybd_event
    ничего не возвращает: вставка в окно программы, запущенной от
    администратора, проваливалась молча - Windows глушит чужой ввод в процесс
    выше по правам (UIPI), а мы рапортовали успех и возвращали в буфер то, что
    человек копировал раньше. То есть своими руками стирали единственный след
    диктовки. SendInput в этом случае возвращает ноль, и мы наконец знаем, что
    отдавать текст было некуда.

    Паузы между событиями сохранены как были: часть окон не успевает увидеть
    зажатый Ctrl, если V приходит в ту же миллисекунду.
    """
    ok = _tap(VK_CONTROL)
    time.sleep(0.01)
    ok = _tap(VK_V) and ok
    time.sleep(0.02)
    # Отпускаем в любом случае, даже если нажатия не прошли: зажатый Ctrl,
    # оставленный нами, хуже непрошедшей вставки.
    ok = _tap(VK_V, up=True) and ok
    return _tap(VK_CONTROL, up=True) and ok


def _send_ctrl_c() -> None:
    win32api.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(0.01)
    win32api.keybd_event(VK_C, 0, 0, 0)
    time.sleep(0.02)
    win32api.keybd_event(VK_C, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


def _send_ctrl_a() -> None:
    """Выделить весь текст поля - Ctrl+A через keybd_event с VK-кодами.

    Тот же приём, что и у _send_ctrl_c рядом: 'A' здесь виртуальный код, а не
    буква, поэтому жест не срывается на русской раскладке - ровно на этом
    спотыкалась библиотека keyboard (см. шапку файла).
    """
    win32api.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(0.01)
    win32api.keybd_event(VK_A, 0, 0, 0)
    time.sleep(0.02)
    win32api.keybd_event(VK_A, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


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
    if not platform_api.IS_WINDOWS:
        platform_api.note_unsupported("нажатие Enter в чужом окне")
        return False
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
    if not platform_api.IS_WINDOWS:
        platform_api.note_unsupported("стирание вставленного (backspace)")
        return False
    _wait_modifiers_released()
    scan = win32api.MapVirtualKey(VK_BACK, 0)
    return _send([_key_event(VK_BACK, scan, flags)
                  for _ in range(count)
                  for flags in (0, _KEYEVENTF_KEYUP)])


def _get_clipboard_text() -> str | None:
    if not platform_api.IS_WINDOWS:
        return _mac_clipboard_get()
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
    if not platform_api.IS_WINDOWS:
        return _mac_clipboard_set(text)
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


# Метка, которой мы чистим буфер перед Ctrl+C.
#
# Ловушка, ради которой она заведена: если ничего не выделено, Ctrl+C НЕ
# ОЧИЩАЕТ буфер - в нём останется то, что человек копировал час назад. Без
# метки мы приняли бы вчерашнюю копию за текст поля и переписали бы Ollama
# чужой текст, а результат вставили бы поверх пустого места.
#
# Метка, а не пустая строка: EmptyClipboard() снимает формат CF_UNICODETEXT
# целиком, и _get_clipboard_text вернёт None и на «пусто», и на «в буфере
# картинка». Своя метка отличает «мы вычистили, и Ctrl+C ничего не дал» от
# всего остального.
_PROBE = "\x00flowlocal-selection-probe\x00"


def _await_probe(timeout: float) -> str | None:
    """Дождаться, пока Ctrl+C сменит нашу метку на настоящий текст.

    None - метка на месте, значит копировать было нечего.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        cur = _get_clipboard_text()
        if cur is not None and cur != _PROBE:
            return cur
        time.sleep(0.03)
    return None


def _drop_probe(old: str | None) -> None:
    """Убрать метку за собой: вернуть прежний буфер, а не было его - оставить пусто."""
    _set_clipboard_text(old if old is not None else "")


def copy_selection(timeout: float = 0.6) -> tuple[str | None, str | None]:
    """Забрать выделенное в активном окне. Возвращает (выделение, прежний буфер).

    Выделение - None, если не выделено ничего. Прежний буфер отдаём наружу,
    чтобы вызвавший вернул его на место, когда закончит.

    Ничего в чужом окне не меняет: Ctrl+C только читает. Про метку в буфере -
    см. комментарий к _PROBE выше.
    """
    if not platform_api.IS_WINDOWS:
        # Забрать выделение из чужого окна = послать ему Ctrl+C, а это тот же
        # CGEvent, что и вставка (пока не сделан). Без выделения список
        # преобразований просто не запустится - молча, как и на «ничего не
        # выделено».
        platform_api.note_unsupported("захват выделения из чужого окна")
        return None, None
    _wait_modifiers_released()
    old = _get_clipboard_text()
    if not _set_clipboard_text(_PROBE):
        return None, old
    _send_ctrl_c()
    sel = _await_probe(timeout)
    if sel is not None:
        return sel, old
    # Метка на месте - Ctrl+C ничего не положил, выделения не было.
    _drop_probe(old)
    return None, old


def select_all() -> None:
    """Выделить весь текст активного поля - Ctrl+A, и ничего больше.

    Нужна перед вставкой результата преобразования, но ТОЛЬКО когда поле
    целиком мы же и забирали (grab_text вернул третьим значением True). Фокус
    уходил к пилюле выбора, прежнее выделение могло сняться, и весь текст надо
    выделить заново, чтобы вставка легла ПОВЕРХ него, а не рядом.

    Если текст выделял человек - звать эту функцию НЕЛЬЗЯ: она расширит его
    выделение с абзаца на весь документ, и результат ляжет поверх всего.

    Модификаторы ждём сами: сочетание-хоткей могло прийти с зажатым Shift, и
    Ctrl+A под ним превратился бы в Ctrl+Shift+A - не выделение (та же ловушка,
    что у вставки, отсюда и _wait_modifiers_released).
    """
    if not platform_api.IS_WINDOWS:
        platform_api.note_unsupported("выделение всего текста поля")
        return
    _wait_modifiers_released()
    _send_ctrl_a()


def grab_text(timeout: float = 0.6) -> tuple[str | None, str | None, bool]:
    """Взять текст активного поля. Возвращает (текст, прежний буфер, взяли ли всё).

    Два шага, и порядок у них не про удобство, а про безопасность.

    Сперва спрашиваем выделение одним Ctrl+C - это чтение, в чужом окне оно не
    меняет ничего. Выделил человек сам - берём ровно его кусок и Ctrl+A не жмём
    вовсе. Только если выделения нет (или в нём одни пробелы), выделяем поле
    целиком сами.

    Ctrl+A в чужом окне - самое опасное, что мы вообще делаем: он снимает
    выделение человека и ставит своё на ВЕСЬ документ, а поверх этого выделения
    потом ляжет результат. Отсюда третье возвращаемое значение: «поле целиком».
    Только при нём вставляющая сторона имеет право выделить всё заново; при
    выделении человека такое переписало бы документ вместо правки абзаца.

    Метка ставится заново ПЕРЕД каждым Ctrl+C. Первый шаг мог оставить в буфере
    пробелы, и второй тогда принял бы их за свежую копию, не дождавшись
    настоящей.

    Метка на месте после обоих шагов - честное «текста нет»: поле пустое, либо
    это вовсе не текст (Ctrl+C в проводнике кладёт файлы, а не CF_UNICODETEXT).
    Наверх уходит None, и трогать там ничего не станут. Наше «выделить всё» в
    таком окне остаётся висеть - в проводнике это подсвеченные файлы. Обидно,
    но безобидно: выделение снимется первым же щелчком, а вставки не будет.

    Вернуть прежний буфер на место - забота вызвавшего, как и у copy_selection.
    """
    if not platform_api.IS_WINDOWS:
        platform_api.note_unsupported("захват текста поля")
        return None, None, False
    _wait_modifiers_released()
    old = _get_clipboard_text()

    # 1) выделение человека, если оно есть
    if not _set_clipboard_text(_PROBE):
        # Буфер занят намертво. Поле не трогаем: без метки мы не отличим
        # свежую копию от вчерашней, а гадать тут нечем.
        return None, old, False
    _send_ctrl_c()
    sel = _await_probe(timeout)
    if sel is not None and sel.strip():
        return sel, old, False

    # 2) выделения нет - выделяем поле целиком
    if not _set_clipboard_text(_PROBE):
        _drop_probe(old)
        return None, old, False
    _send_ctrl_a()
    time.sleep(0.03)      # дать полю выделиться, прежде чем копировать
    _send_ctrl_c()
    whole = _await_probe(timeout)
    if whole is not None and whole.strip():
        return whole, old, True
    _drop_probe(old)
    return None, old, True


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


def to_clipboard(text: str) -> bool:
    """Положить текст в буфер обмена и ничего больше. False - буфер занят.

    Единственная дверь для всех обходных путей: не вставилось, диктовали
    нарочно в буфер, файл голосового инбокса недоступен. Раньше на каждый такой
    случай звался приватный _set_clipboard_text - снаружи модуля и по-разному.
    """
    if not text:
        return True
    return _set_clipboard_text(text)


def insert(text: str, mode: str = "paste", restore: bool = True) -> bool:
    """Вставить текст в активное окно. True - получилось.

    Провалились - оставляем диктовку в буфере обмена: тогда человека спасает
    Ctrl+V, не открывая окно программы. Иначе текст живёт только в «Повторить
    последнюю», за которой надо лезть в трей.
    """
    if not text:
        return True
    if not platform_api.IS_WINDOWS:
        # Вставка в чужое окно (CGEvent Cmd+V) на macOS пока не сделана.
        # Кладём текст в буфер и возвращаем False - вызвавший покажет на пилюле
        # «в буфере», и человека выручает Cmd+V руками. Диктовку не теряем.
        platform_api.note_unsupported("вставка текста в активное окно")
        _set_clipboard_text(text)
        return False
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
    if not _send_ctrl_v():
        # Наши нажатия не пустили (окно выше по правам - UIPI). Прежний буфер
        # НЕ возвращаем: диктовка сейчас единственная копия текста, и человеку
        # остаётся Ctrl+V руками - об этом ему скажет пилюля.
        return False
    if restore and old is not None:
        time.sleep(_restore_wait(len(text)))
        # Возвращаем прежний буфер, только если в буфере всё ещё наша диктовка.
        # Успел человек за это время скопировать своё - его копия важнее нашей
        # уборки, и затирать её мы не имеем права.
        if _get_clipboard_text() == text:
            _set_clipboard_text(old)
    return True
