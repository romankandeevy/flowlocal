"""Три пробы на живом Mac. Решают, существует ли этап 13 вообще.

Запускать НА MAC, по одной, и смотреть глазами - автотестом это не ловится:
проверяем ровно то, за чем в CI никто не смотрит (фокус, разрешения, реальная
вставка в чужое окно).

    python3 tools/probe_mac.py deps      # проба C: встанет ли всё без компилятора
    python3 tools/probe_mac.py paste     # проба A: доедет ли Cmd+V в чужое окно
    python3 tools/probe_mac.py hotkey    # проба A: ловится ли многоклавишный хоткей
    python3 tools/probe_mac.py tcc       # проба B: переживают ли разрешения пересборку

Почему пробы вообще нужны. План (5.3) снял с macOS главный ценник: $99 в год
покупают раздачу скачиванием, а её у нас нет, и для себя достаточно
самоподписанного сертификата за $0. Но осталась мина, которую деньги не лечат:
у Handy есть Developer ID и нотаризация, и при этом на macOS 26.5 у него **не
работают многоклавишные хоткеи** (issue #1578). Если это наша болезнь тоже -
этап 13 отменяется целиком, и никакие вложения его не спасают.

Поэтому порядок жёсткий: сперва `hotkey` и `paste`. Не прошли - дальше не идём.
"""

import platform
import subprocess
import sys
import time

MAC = sys.platform == "darwin"


def head(title: str) -> None:
    print(f"\n=== {title} ===")


def probe_deps() -> int:
    """Проба C: встанет ли всё без компилятора, и жив ли звук.

    Колёса проверены по PyPI (PLAN 5.3): PySide6 universal2, onnxruntime -
    только arm64 (Intel-Маки отпадают), остальное - чистый Python. Но проверка
    по индексу не заменяет установки, а перечисление аудиоустройств на Tahoe
    роняло Handy (issue #1643) - его смотрим отдельно.
    """
    head("зависимости и звук")
    print(f"macOS {platform.mac_ver()[0]}, {platform.machine()}, Python {sys.version.split()[0]}")
    if platform.machine() != "arm64":
        print("ВНИМАНИЕ: не Apple Silicon. Колёс onnxruntime под x86_64 нет - "
              "дальше можно не идти.")

    ok = True
    for mod, why in (("PySide6", "интерфейс"), ("onnxruntime", "распознавание"),
                     ("onnx_asr", "модель"), ("sounddevice", "микрофон"),
                     ("pynput", "хоткеи и мышь"), ("numpy", "звук"),
                     ("PIL", "иконка")):
        try:
            __import__(mod)
            print(f"  OK  {mod:<14} {why}")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"  НЕТ {mod:<14} {why}: {e}")

    try:
        import sounddevice as sd

        devs = [d for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]
        print(f"  OK  микрофонов найдено: {len(devs)}")
        for d in devs[:3]:
            print(f"        {d['name']}")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"  НЕТ перечисление устройств упало: {e}")
        print("      Ровно на этом падал Handy (issue #1643, cpal на CoreAudio).")
    return 0 if ok else 1


def probe_paste() -> int:
    """Проба A, половина первая: доедет ли Cmd+V в чужое окно.

    Это наш основной путь вставки, и по разбору источника (PLAN 5.3) он под
    фильтр Tahoe попадать не должен: обычная responder chain, а не таблица
    карбоновских хоткеев. Проверяем.
    """
    head("вставка Cmd+V в чужое окно")
    print("Откройте TextEdit, поставьте курсор в пустой документ.")
    print("Через 5 секунд отправлю Cmd+V с текстом в буфере.")
    try:
        from AppKit import NSPasteboard, NSStringPboardType
        from Quartz import (CGEventCreateKeyboardEvent, CGEventPost,
                            CGEventSetFlags, kCGHIDEventTap,
                            kCGEventFlagMaskCommand)
    except ImportError as e:
        print(f"  НЕТ нет pyobjc: {e}")
        print("      pip install pyobjc-framework-Quartz pyobjc-framework-Cocoa")
        return 2

    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_("Проверка вставки FlowLocal", NSStringPboardType)

    for i in (5, 4, 3, 2, 1):
        print(f"  {i}...", end="", flush=True)
        time.sleep(1)
    print()

    V = 9  # kVK_ANSI_V
    for down in (True, False):
        ev = CGEventCreateKeyboardEvent(None, V, down)
        CGEventSetFlags(ev, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, ev)
        time.sleep(0.02)

    print("  Текст появился в TextEdit? Если да - проба пройдена.")
    print("  Если нет: проверьте Системные настройки → Конфиденциальность →")
    print("  Универсальный доступ. Без него CGEventPost молчит.")
    return 0


def probe_hotkey() -> int:
    """Проба A, половина вторая: ловится ли МНОГОКЛАВИШНЫЙ хоткей.

    Самая важная проба из трёх. У Handy - Developer ID и нотаризация, и при
    этом на macOS 26.5 односоставные хоткеи работают, а многоклавишные нет
    (issue #1578). Если это воспроизводится у нас, этап 13 отменяется: наш
    хоткей по умолчанию как раз из трёх клавиш, а деньги эту болезнь не лечат.
    """
    head("многоклавишный хоткей")
    try:
        from pynput import keyboard
    except ImportError as e:
        print(f"  НЕТ нет pynput: {e}")
        return 2

    print("Зажмите Ctrl+Shift+Space (можно несколько раз). Esc - выход.")
    print("Считаем срабатывания 20 секунд.\n")

    hits = {"combo": 0, "bare": 0}
    pressed = set()

    def on_press(key):
        pressed.add(key)
        ctrl = any(k in pressed for k in (keyboard.Key.ctrl, keyboard.Key.ctrl_l,
                                          keyboard.Key.ctrl_r))
        shift = any(k in pressed for k in (keyboard.Key.shift, keyboard.Key.shift_l,
                                           keyboard.Key.shift_r))
        if key == keyboard.Key.space:
            if ctrl and shift:
                hits["combo"] += 1
                print(f"  сочетание поймано ({hits['combo']})")
            else:
                hits["bare"] += 1
                print(f"  голый пробел ({hits['bare']})")
        if key == keyboard.Key.esc:
            return False
        return True

    def on_release(key):
        pressed.discard(key)
        return True

    with keyboard.Listener(on_press=on_press, on_release=on_release) as lis:
        lis.join(20)

    print(f"\n  сочетание: {hits['combo']}, голый пробел: {hits['bare']}")
    if hits["combo"]:
        print("  ПРОШЛА. Многоклавишный хоткей ловится - болезнь Handy не наша.")
        return 0
    if hits["bare"]:
        print("  ПРОВАЛ. Голые клавиши ловятся, сочетания - нет.")
        print("  Это ровно то, на что жалуются у Handy (#1578), и денег это не лечит.")
        print("  Этап 13 отменяется - см. PLAN 5.3.")
        return 1
    print("  Не поймано ничего: скорее всего нет разрешения Input Monitoring.")
    return 2


def probe_tcc() -> int:
    """Проба B: переживают ли разрешения пересборку.

    План (5.3) утверждает, что самоподписанный сертификат даёт стабильный
    designated requirement и разрешения не слетают. Прямого подтверждения в
    открытых источниках нет - это вывод по устройству. Здесь он проверяется.
    """
    head("TCC и пересборка")
    print("Проба ручная, автоматизировать нечего. Порядок:")
    print()
    print("  1. Сделайте сертификат один раз:")
    print("     openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 3650 \\")
    print("       -subj '/CN=FlowLocal Dev' -keyout k.pem -out c.pem")
    print("     openssl pkcs12 -export -legacy -inkey k.pem -in c.pem -out d.p12")
    print("     Импортируйте d.p12 в связку «Вход», поставьте «Always Trust».")
    print()
    print("  2. Соберите .app и подпишите:")
    print("     codesign --force --deep --sign 'FlowLocal Dev' FlowLocal.app")
    print()
    print("  3. Выдайте Универсальный доступ и Мониторинг ввода, проверьте хоткей.")
    print("  4. Пересоберите и подпишите ЗАНОВО тем же сертификатом.")
    print("  5. Смотрите: галки на месте или система спросила снова?")
    print()
    print("  На месте  -> схема из PLAN 5.3 работает, порт стоит $0.")
    print("  Спросила  -> живём на ad-hoc и переставляем галки каждую сборку.")
    print("               Противно, но не смертельно.")
    ident = subprocess.run(["security", "find-identity", "-v", "-p", "codesigning"],
                           capture_output=True, text=True)
    print("\nсертификаты для подписи, которые видит система:")
    print(ident.stdout.strip() or "  (ни одного)")
    return 0


def main() -> int:
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if not MAC:
        print("Эти пробы запускаются НА MAC. Здесь -", sys.platform)
        print("Смысл в том, чтобы проверить то, что с Windows не проверяется:")
        print("разрешения TCC, CGEventPost и сборку .app.")
        return 2
    return {"deps": probe_deps, "paste": probe_paste,
            "hotkey": probe_hotkey, "tcc": probe_tcc}.get(
                what, lambda: (print(__doc__), 2)[1])()


if __name__ == "__main__":
    sys.exit(main())
