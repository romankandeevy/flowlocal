"""Клиент моста для страницы печатается из Backend, а не пишется руками.

Зачем генератор. Странице отдаётся 83 метода, 14 свойств и 13 сигналов.
Перенести столько в TypeScript руками - это 83 повода опечататься, и опечатка
вылезет не при сборке, а в работающем окне: страница попросит метод, которого
нет, и получит `ret` с жалобой. Сгенерированный клиент даёт типы, и опечатка
падает на `tsc`.

Источников ДВА, и оба те же, что у самого моста: `Backend` из settings_qt и
`_Extra` из onboarding_qt. Второй появился с мастером первого запуска - у него
свой API (уровни микрофона, превью тем, пробная диктовка), и в Backend его нет.
Разъехаться клиенту и мосту негде: оба обходят одни и те же metaObject.

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

HEAD = '''// Клиент моста. СГЕНЕРИРОВАНО из Backend и _Extra - руками не править.
//
//   python tools/gen_bridge.py           переписать
//   python tools/gen_bridge.py --check   сверить (стоит в CI)
//
// Восемьдесят три метода и тринадцать сигналов переносить руками незачем: тут
// не столько работа, сколько 83 повода опечататься, а опечатка вылезла бы не
// при сборке, а в работающем окне. Здесь она падает на tsc.
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
    # Мастер первого запуска говорит не с Backend, а со своим объектом
    # (onboarding_qt._Extra): уровни микрофона, превью тем, пробная диктовка.
    # Его методы странице нужны так же, как и Backend'овские, поэтому клиент
    # печатается с обоих.
    #
    # Приложение ему не передаём: конструктор только запоминает ссылку, а нам
    # нужен один metaObject, и ни один метод здесь не зовётся. Настоящее
    # приложение поднимать ради списка имён было бы и долго, и незачем.
    objects = [backend]
    try:
        import onboarding_qt as O

        objects.append(O._Extra(None))
    except Exception as e:  # noqa: BLE001 - без мастера клиент всё равно нужен
        print(f"  мастер пропущен: {type(e).__name__}: {e}", file=sys.stderr)

    own = B._qobject_names()
    mo = backend.metaObject()

    slots, signals, props = {}, {}, set()
    for obj in objects:
        mo = obj.metaObject()
        for i in range(mo.methodCount()):
            m = mo.method(i)
            name = _s(m.name())
            if name.startswith("_") or name in own or name in PROTOCOL:
                continue
            args = [(_s(t), _s(n) or f"a{k}")
                    for k, (t, n) in enumerate(zip(m.parameterTypes(),
                                                   m.parameterNames()))]
            if m.methodType() == QMetaMethod.Slot:
                # Перегрузки: одно имя, разные подписи. Берём самую длинную -
                # короткая обычно её частный случай с умолчаниями.
                if name not in slots or len(args) > len(slots[name][0]):
                    slots[name] = (args, _s(m.typeName()))
            elif m.methodType() == QMetaMethod.Signal:
                signals[name] = args
        for i in range(mo.propertyCount()):
            name = mo.property(i).name()
            if name not in own:
                props.add(name)
    props = sorted(props)
    keys = sorted(_paths(C.DEFAULTS))
    del app
    return slots, signals, keys, props


def _paths(d: dict, prefix: str = "") -> list:
    """Ключи конфига со вложенными - точкой: llm, llm.url, llm.model.

    Плоского списка мало. `Backend.get` умеет вложенные пути, и окно ими
    пользуется: `B.get("llm.url")` стоит прямо в Settings.qml. Без них союз
    SettingKey оказывался беднее того, что мост принимает, и типизированная
    страница не могла прочитать настройку, которую QML читал спокойно.

    Сам `llm` в списке тоже остаётся: словарь целиком иногда нужен, и
    выбрасывать его - значит решать за вызывающего.
    """
    out = []
    for key, value in d.items():
        path = f"{prefix}{key}"
        out.append(path)
        if isinstance(value, dict):
            out += _paths(value, f"{path}.")
    return out


def render() -> str:
    slots, signals, keys, props = surface()
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

    out.append("// ---------- свойства Backend ----------")
    out.append("//")
    out.append("// Списки для выпадающих меню и прочее, что Backend отдаёт")
    out.append("// свойством, а не методом: micOptions, themeOptions,")
    out.append("// modelOptions, autoEnterApps. Без них страница не нарисует ни")
    out.append("// одного выпадающего списка, а раньше они были ей недоступны")
    out.append("// вовсе - мост отвечал только за ключи конфига.")
    out.append("//")
    out.append("// Едут тем же сообщением get: мост различает их по имени.\n")
    for name in props:
        out.append(f"export function {name}(): Promise<unknown> {{")
        out.append(f'  return get("{name}");')
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
    slots, signals, keys, props = surface()
    print(f"записано: {OUT}")
    print(f"  методов {len(slots)}, свойств {len(props)}, "
          f"сигналов {len(signals)}, ключей {len(keys)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
