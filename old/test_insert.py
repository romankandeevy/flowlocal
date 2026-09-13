"""Автотест вставки в нативный Win32 EDIT-контрол.

EDIT обрабатывает Ctrl+V на уровне класса окна (WM_CHAR 0x16) - так же,
как реальные приложения, и независимо от раскладки. tkinter для этого
теста не годится: его биндинг <Control-v> привязан к латинскому keysym
и молчит на русской раскладке.

Буфер обмена перед проверкой засеивается известным текстом: иначе, если в
буфере лежала картинка, восстанавливать нечего и проверка «вернули как
было» врёт (текстом восстанавливается только текст - см. README).

Запуск: python test_insert.py [paste|type|both]
"""

import ctypes
import sys
import threading
import time

import win32api
import win32con
import win32gui

from inserter import (
    _get_clipboard_text,
    _set_clipboard_text,
    _wait_modifiers_released,
    insert,
)

EXPECT = "Привет, FlowLocal - проверка вставки 123. "
SEED = "буфер-до-вставки-42"
VK_MENU = 0x12
VK_SHIFT = 0x10

_user32 = ctypes.windll.user32


def _force_foreground(hwnd) -> bool:
    """Дотащить окно в фокус и дождаться, пока это правда случится.

    Windows защищает активное окно от кражи фокуса, и голый
    SetForegroundWindow часто молча не срабатывает - тогда Ctrl+V уходит в
    чужое окно и тест краснеет на ровном месте.

    Классический обход «нажать Alt перед SetForegroundWindow» здесь ЯДОВИТ:
    отпускание Alt вводит окно в режим меню, и следующее нажатие съедается.
    Съедается ровно наш Ctrl+V (в режиме paste не вставлялось ничего, в type
    пропадала первая буква: «ривет» вместо «Привет»). Поэтому фокус берём
    через AttachThreadInput - он не трогает клавиатуру вообще.
    """
    user32 = ctypes.windll.user32
    k32 = ctypes.windll.kernel32
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    def try_attach() -> None:
        fg = user32.GetForegroundWindow()
        tid_me = k32.GetCurrentThreadId()
        tid_fg = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        attached = bool(tid_fg and tid_fg != tid_me
                        and user32.AttachThreadInput(tid_me, tid_fg, True))
        try:
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
            user32.SetActiveWindow(hwnd)
            user32.SetFocus(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(tid_me, tid_fg, False)

    def settled() -> bool:
        for _ in range(20):
            if win32gui.GetForegroundWindow() == hwnd:
                return True
            time.sleep(0.05)
        return False

    if win32gui.GetForegroundWindow() == hwnd:
        return True
    try_attach()
    if settled():
        return True

    # Не пустили: право поднять себя в фокус даётся тому, кто получил
    # последний ввод от пользователя. Кликаем по самому окну - это ровно то,
    # что сделал бы человек перед диктовкой, и клавиатуру это не портит.
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    old = win32api.GetCursorPos()
    try:
        win32api.SetCursorPos(((left + right) // 2, (top + bottom) // 2))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.02)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    finally:
        win32api.SetCursorPos(old)      # вернуть курсор туда, где он был
    try_attach()
    return settled()


def _run_modifier_release() -> bool:
    """Зажатый Shift должен быть отжат принудительно по таймауту.

    Проверяем сам механизм, а не вставку в EDIT: EDIT обрабатывает
    Ctrl+Shift+V ровно как Ctrl+V, и разницы бы не показал (проверено -
    тест проходил и со сломанным отжатием). А вот в реальных приложениях
    Ctrl+Shift+V - совсем другая команда: «вставить без форматирования» в
    Chrome и VS Code, «специальная вставка» в Word. Поэтому вставлять,
    пока человек ещё держит модификаторы хоткея, нельзя.
    """
    user32 = ctypes.windll.user32
    user32.keybd_event(VK_SHIFT, 0, 0, 0)
    try:
        for _ in range(100):        # keybd_event асинхронный - ждём, пока дойдёт
            if win32api.GetAsyncKeyState(VK_SHIFT) & 0x8000:
                break
            time.sleep(0.01)
        else:
            print("--- отжатие модификаторов\n  не удалось зажать Shift\n  FAIL")
            return False
        t0 = time.time()
        _wait_modifiers_released(timeout=0.4)
        dt = time.time() - t0
        released = not (win32api.GetAsyncKeyState(VK_SHIFT) & 0x8000)
    finally:
        user32.keybd_event(VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)

    waited = dt >= 0.4          # обязан честно подождать, а не сдаться сразу
    print("--- отжатие модификаторов")
    print(f"  ждал {dt:.2f} с (таймаут 0.4)      {waited}")
    print(f"  Shift отжат принудительно:      {released}")
    ok = waited and released
    print(f"  {'PASS' if ok else 'FAIL'}")
    return ok


def _window_text(hwnd) -> str:
    """Забрать текст окна целиком.

    Не win32gui.GetWindowText: он читает в буфер фиксированного размера и молча
    обрезает на 511 знаках. Проверено прямо здесь - положили 900, получили 511.
    Ровно на этом тест длинной вставки покраснел на исправном коде: текст
    вставился весь, а читалка вернула огрызок. Обрезание тихое, и выглядит оно
    в точности как тот баг, который тест и должен ловить.
    """
    n = _user32.SendMessageW(hwnd, win32con.WM_GETTEXTLENGTH, 0, 0)
    buf = ctypes.create_unicode_buffer(n + 1)
    _user32.SendMessageW(hwnd, win32con.WM_GETTEXT, n + 1, buf)
    return buf.value


def _run(mode: str, expect: str = EXPECT, label: str = "") -> bool:
    _set_clipboard_text(SEED)
    hwnd = win32gui.CreateWindow(
        "EDIT",
        f"FlowLocal insert test - {mode}",
        win32con.WS_OVERLAPPEDWINDOW | win32con.WS_VISIBLE | win32con.ES_MULTILINE,
        100, 100, 640, 200,
        0, 0, 0, None,
    )
    win32gui.SetWindowPos(
        hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE,
    )
    win32gui.SendMessage(hwnd, win32con.WM_SETTEXT, 0, "")
    _force_foreground(hwnd)

    state = {"fg": None, "ok": None}
    done = threading.Event()

    def go() -> None:
        time.sleep(0.8)
        state["fg"] = win32gui.GetForegroundWindow()
        state["ok"] = insert(expect, mode)
        time.sleep(0.8)
        done.set()

    threading.Thread(target=go, daemon=True).start()
    t0 = time.time()
    while not done.is_set() and time.time() - t0 < 15:
        win32gui.PumpWaitingMessages()
        time.sleep(0.01)

    got = _window_text(hwnd)
    clip = _get_clipboard_text()
    try:
        win32gui.DestroyWindow(hwnd)
    except Exception:  # noqa: BLE001 - окно могли закрыть вручную
        pass

    text_ok = got == expect
    # в режиме type буфер вообще не трогается, в paste - должен вернуться
    clip_ok = clip == SEED
    focus_ok = state["fg"] == hwnd
    print(f"--- {label or mode}")
    print(f"  insert() -> {state['ok']}")
    print(f"  focus was ours:    {focus_ok}")
    print(f"  text inserted:     {text_ok}  {got!r}")
    print(f"  clipboard restored:{clip_ok}  {clip!r}")
    if not text_ok and _intruded(got, expect):
        # Окно теста топмостовое и в фокусе - в него влезает всё, что печатают
        # рядом. Дважды тест краснел именно так («оман к…ндее» - куски чужой
        # диктовки), и каждый раз это выглядело как баг вставки. Отличаем по
        # простому признаку: наш текст пришёл целиком, но вокруг налипло чужое.
        print("  ^ похоже на посторонний ввод в тестовое окно, а не на баг "
              "вставки: наш текст на месте, но окно поймало ещё чужой.\n"
              "    Во время прогона нельзя печатать и диктовать - перезапустите.")
        return False
    ok = text_ok and clip_ok and focus_ok and state["ok"]
    print(f"  {'PASS' if ok else 'FAIL'}")
    return ok


def _intruded(got: str, expect: str = EXPECT) -> bool:
    """Наш текст доехал целиком, но в окне есть и что-то ещё."""
    return expect.strip() in got and got != expect


LONG = ("Здравствуйте! Отправляю письмо целиком, как его наговаривают на "
        "самом деле: длинным куском, а не фразой в три слова. " * 6)


def _run_long() -> bool:
    """Длинный текст - тот случай, где вставка отказывала МОЛЧА.

    Приложение читает буфер не в момент Ctrl+V, а позже, разобрав WM_PASTE.
    Пока мы возвращали прежний буфер через фиксированные 300 мс, оно не
    успевало, и человек получал свой старый буфер вместо письма - при том
    что конвейер рапортовал успех. У соседей это воспроизведено с точностью
    до цифр: до 90 знаков вставлялось всегда, 202 и 520 - уже нет.

    Владелец диктует именно письма, то есть живёт ровно в этой длине.

    Честно про границы этой проверки: нативный EDIT читает буфер прямо в
    обработчике WM_PASTE, синхронно, и потому успевал всегда - он прошёл бы и
    со старым кодом. Значит этот случай доказывает не «починили», а «не
    сломали»: длинный текст доезжает целиком и уборка за собой не мешает.
    Тормозят с чтением буфера Electron и браузеры, а их сюда не затащить.
    """
    return _run("paste", LONG, label=f"paste, длинный текст ({len(LONG)} знаков)")


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "both"
    if arg == "both":
        results = [_run("paste"), _run_long(), _run("type"),
                   _run_modifier_release()]
    elif arg == "long":
        results = [_run_long()]
    elif arg == "shift":
        results = [_run_modifier_release()]
    else:
        results = [_run(arg)]
    print("\nИТОГ:", "PASS" if all(results) else "FAIL")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
