"""Клиент моста для страницы печатается из Backend, а не пишется руками.

Зачем генератор. Backend отдаёт странице 75 методов и 10 сигналов (из 80 и 16 -
остальное приватное, им Backend перебрасывает работу между потоками). Перенести
столько в TypeScript руками - это 75 поводов опечататься, и опечатка вылезет не
при сборке, а в работающем окне: страница попросит метод, которого нет, и
получит `ret` с жалобой. Сгенерированный клиент даёт типы, и опечатка падает на
`tsc`.

Источник один и тот же, что у самого моста, - `Backend.metaObject()`. Значит,
разъехаться клиенту и мосту негде: оба видят одно.

**Обход metaObject идёт с нуля, а не с methodOffset().** Причина разобрана в
`bridge.Bridge._surface` и стоила трёх ошибок: у питоновского наследника
QObject объявленные в Python слоты и сигналы лежат ДО этой границы, и обход по
ней находит четыре метода из восьмидесяти и ни одного сигнала.

    python tools/gen_bridge.py           переписать web/src/bridge/api.ts
    python tools/gen_bridge.py --check   сверить (стоит в CI)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import config as C  # noqa: E402

# Конфиг подменяем ДО того, как Backend его прочитает. Генератору настройки
# владельца не нужны вовсе, а прочитать их значило бы дать личному шанс
# просочиться в сгенерированный файл, который лежит в репозитории.
C.load = lambda path=None: dict(C.DEFAULTS)
C.save = lambda cfg, path=None: None

from PySide6.QtCore import QCoreApplication, QMetaMethod  # noqa: E402

import bridge as B  # noqa: E402
import settings_qt as S  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "web", "src", "bridge", "api.ts")

# `get` и `set` у Backend - это сам протокол, а не действие. Мост возит их
# отдельными типами сообщений, а странице они уже отданы как getSetting и
# setSetting - с типизированным ключом вместо голой строки. Печатать их ещё раз
# значит завести в api.ts вторые `get` и `set`, которые столкнутся с
# импортированными из client.ts. Ровно на это и наткнулся tsc.
PROTOCOL = {"get", "set"}

HEAD = '''// Клиент моста. СГЕНЕРИРОВАНО из Backend - руками не править.
//
//   python tools/gen_bridge.py           переписать
//   python tools/gen_bridge.py --check   сверить (стоит в CI)
//
// Семьдесят пять методов и десять сигналов переносить руками незачем: тут не
// столько работа, сколько 75 поводов опечататься, а опечатка вылезла бы не при
// сборке, а в работающем окне. Здесь она падает на tsc.
//
// Типы аргументов взяты из metaObject, то есть из того же места, откуда их
// берёт сам мост. QVariant и QVariantMap приезжают как unknown и Record -
// точнее Qt про них не знает, и выдумывать за него не надо.

import { call, get, set, onSignal } from "./client";

'''


def _ts_type(qt: str) -> str:
    """Тип Qt -> тип TypeScript. Чего не знаем - unknown, а не any.

    any выключает проверку молча и заражает всё, к чему прикоснулся; unknown
    заставляет разобраться на месте использования. Для генератора это важнее
    удобства: сгенерированное читают редко, а пользуются им всюду.
    """
    t = qt.replace("const ", "").replace("&", "").strip()
    if t in ("QString", "QByteArray"):
        return "string"
    if t in ("int", "uint", "long", "qlonglong", "double", "float", "qreal"):
        return "number"
    if t == "bool":
        return "boolean"
    if t in ("QVariantList", "QStringList"):
        return "unknown[]"
    if t in ("QVariantMap", "QJsonObject"):
        return "Record<string, unknown>"
    if t in ("void", ""):
        return "void"
    return "unknown"


def _s(x) -> str:
    """QByteArray или str - в str.

    В PySide6 metaObject отдаёт то одно, то другое: `method().name()` - это
    QByteArray, а `typeName()` уже строка. Единого правила нет, и `bytes(x)`
    на строке падает с «string argument without an encoding».
    """
    return x if isinstance(x, str) else bytes(x).decode()


def surface() -> tuple:
    app = QCoreApplication.instance() or QCoreApplication([])
    backend = S.Backend(
        on_change=lambda *_a, **_k: None,
        on_hotkey_capture=lambda *_a, **_k: None,
        info_fn=lambda: {},
        history_path=os.devnull,
        log_path=os.devnull,
    )
    own = B._qobject_names()
    mo = backend.metaObject()

    slots, signals = {}, {}
    for i in range(mo.methodCount()):
        m = mo.method(i)
        name = _s(m.name())
        if name.startswith("_") or name in own:
            continue
        args = [(_s(t), _s(n) or f"a{k}")
                for k, (t, n) in enumerate(zip(m.parameterTypes(),
                                               m.parameterNames()))]
        if name in PROTOCOL:
            continue
        if m.methodType() == QMetaMethod.Slot:
            # Перегрузки: одно имя, разные подписи. Берём самую длинную -
            # короткая обычно её частный случай с умолчаниями.
            if name not in slots or len(args) > len(slots[name][0]):
                slots[name] = (args, _s(m.typeName()))
        elif m.methodType() == QMetaMethod.Signal:
            signals[name] = args

    keys = sorted(C.DEFAULTS)
    del app
    return slots, signals, keys


def render() -> str:
    slots, signals, keys = surface()
    out = [HEAD]

    out.append("/** Ключи конфига - все, что есть в config.DEFAULTS. */")
    out.append("export type SettingKey =")
    out += [f'  | "{k}"' for k in keys]
    out.append(";\n")

    out.append("/** Прочитать настройку. */")
    out.append("export function getSetting(key: SettingKey): Promise<unknown> {")
    out.append("  return get(key);")
    out.append("}\n")
    out.append("/** Записать настройку. Мост подтвердит её всем страницам. */")
    out.append("export function setSetting(key: SettingKey, value: unknown): void {")
    out.append("  set(key, value);")
    out.append("}\n")

    out.append("// ---------- методы Backend ----------\n")
    for name in sorted(slots):
        args, ret = slots[name]
        sig = ", ".join(f"{n}: {_ts_type(t)}" for t, n in args)
        names = ", ".join(n for _t, n in args)
        rt = _ts_type(ret)
        out.append(f"export function {name}({sig}): "
                   f"Promise<{'void' if rt == 'void' else rt}> {{")
        out.append(f'  return call("{name}"{", " + names if names else ""}) '
                   f"as Promise<{'void' if rt == 'void' else rt}>;")
        out.append("}\n")

    out.append("// ---------- сигналы Backend ----------\n")
    out.append("export interface Signals {")
    for name in sorted(signals):
        types = ", ".join(_ts_type(t) for t, _n in signals[name]) or ""
        out.append(f"  {name}: [{types}];")
    out.append("}\n")
    out.append("/** Подписаться на сигнал. Возвращает функцию отписки. */")
    out.append("export function on<K extends keyof Signals>(")
    out.append("  name: K,")
    out.append("  fn: (...args: Signals[K]) => void,")
    out.append("): () => void {")
    out.append("  return onSignal(name as string, fn as (...a: unknown[]) => void);")
    out.append("}")

    return "\n".join(out) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        if not os.path.exists(OUT):
            print(f"нет {OUT} - запустите без --check")
            return 1
        have = open(OUT, encoding="utf-8").read()
        if have != text:
            print("api.ts разъехался с Backend - перегенерируйте:")
            print("  python tools/gen_bridge.py")
            return 1
        print("api.ts совпадает с Backend")
        return 0

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    slots, signals, keys = surface()
    print(f"записано: {OUT}")
    print(f"  методов {len(slots)}, сигналов {len(signals)}, ключей {len(keys)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
