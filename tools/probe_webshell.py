"""Сквозная проверка фазы 1: страница React внутри Qt-окна говорит с Python.

Чем это отличается от того, что уже проверено. `test_bridge.py` проверяет
протокол обычным QWebSocket - то есть мост, но без вебвью. `probe_webview.py`
проверял вебвью пустой страницей - то есть вебвью, но без моста и без React.
Здесь оба конца соединены: настоящий `WebWindow`, настоящее WebView2, настоящая
собранная страница из `web/dist`, настоящий `Backend`.

Это последняя проверка, которую можно сделать машиной. Дальше - только глазами.

**Конфиг подменён.** Проба поднимает настоящий Backend, а он умеет писать
настройки. Без подмены она писала бы в `config.json` владельца. Тот же приём,
что в `test_bridge.py` и `tools/preview_settings_qt.py`.

    cd web && npm run build     # сперва собрать страницу
    python tools/probe_webshell.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as C  # noqa: E402

C.load = lambda path=None: dict(C.DEFAULTS)
C.save = lambda cfg, path=None: None

import webwindow  # noqa: E402  - он же зовёт add_dll_directory

webwindow.initialize()          # строго до QApplication

from PySide6.QtCore import QEventLoop, QMetaObject, QObject, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

import bridge as B  # noqa: E402
import settings_qt as S  # noqa: E402
import theme_qt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails: list = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ок ' if ok else 'СБОЙ'}  {name}" + (f" - {detail}" if detail else ""))
    if not ok:
        fails.append(name)


def pump(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main() -> int:
    dist = os.path.join(ROOT, "web", "dist", "index.html")
    if not os.path.exists(dist):
        print("нет web/dist - сперва `cd web && npm run build`")
        return 2

    app = QGuiApplication(sys.argv)

    backend = S.Backend(
        on_change=lambda *_a, **_k: None,
        on_hotkey_capture=lambda *_a, **_k: None,
        info_fn=lambda: {},
        history_path=os.devnull,
        log_path=os.devnull,
    )
    br = B.Bridge(backend)
    win = webwindow.WebWindow(br, theme_qt.Tokens(), theme_qt.Lang(), log=print)

    print(f"страница: {br.page_url()}")
    state = {"loaded": None, "t0": time.perf_counter(), "ms": 0.0}

    win.show()
    root = win.view.rootObject()

    def on_loaded(ok: bool, detail: str) -> None:
        if state["loaded"] is None:
            state["loaded"] = ok
            state["ms"] = (time.perf_counter() - state["t0"]) * 1000
            state["detail"] = detail

    root.loaded.connect(on_loaded)

    for _ in range(60):
        if state["loaded"] is not None:
            break
        pump(250)

    print("\nСТРАНИЦА")
    check("страница загрузилась в вебвью", state["loaded"] is True,
          state.get("detail", "") or f'{state["ms"]:.0f} мс')

    # Страница поднимает мост сама и кладёт итог в window.__bridge.
    #
    # Читаем его через document.title, а не через ответ runJavaScript. Причина
    # в том, что у WebShell.run ответа нет вовсе: обратный вызов там - функция
    # JS, и вернуть её результат в Python значило бы завести ради пробы ещё
    # один сигнал в рабочем файле. А title у WebView - обычное свойство, Qt
    # отдаёт его синхронно. Канал служебный, для пробы, и в окне не участвует.
    answers: dict = {}
    view = root.findChild(QObject, "view")

    for _ in range(40):
        QMetaObject.invokeMethod(
            root, "run", Qt.DirectConnection,
            _q('document.title = "bridge:" + (window.__bridge || "ждём")'))
        pump(250)
        title = str(view.property("title") or "")
        if title.startswith("bridge:") and title != "bridge:ждём":
            answers["bridge"] = title[7:]
            break

    print("\nМОСТ ИЗ НАСТОЯЩЕГО ВЕБВЬЮ")
    check("страница подняла мост", answers.get("bridge") == "ok",
          answers.get("bridge", "ответа нет"))
    check("мост видит подключённую страницу", len(br.clients) >= 1,
          f"клиентов {len(br.clients)}")

    print("\nПАМЯТЬ")
    win.hide()
    pump(2500)
    check("после закрытия окна вебвью отпущено", win.view is None)

    br.close()
    app.quit()
    print()
    if fails:
        print("СБОЙ: " + ", ".join(fails))
        return 1
    print("ОК")
    return 0


def _q(value: str):
    from PySide6.QtCore import Q_ARG

    return Q_ARG("QVariant", value)


if __name__ == "__main__":
    sys.exit(main())
