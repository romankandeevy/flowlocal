"""Мост «страница <-> Python»: критерий готовности фазы 1, машиной.

Критерий из плана дословно: «пустая страница читает B.get(...) и пишет
обратно, значение доезжает до config.json. Запрос без токена отбивается».
Здесь всё это и проверяется - настоящим Backend, настоящим HTTP и настоящим
WebSocket, без заглушек на месте моста.

**Конфиг подменён, и это не удобство, а защита.** `config.load` и
`config.save` заменены на работу со словарём в памяти: тест пишет настройки,
и без подмены он писал бы в `config.json` владельца - в живые хоткеи и
словарь. Тот же приём, что в `tools/preview_settings_qt.py`, и по той же
причине: защита структурная, а не по договорённости. Забыть тут нечего,
потому что настоящий конфиг в тест не попадает вовсе.

Страницы в тесте нет намеренно: вебвью поднимать незачем, оно проверено
пробником фазы 0. Здесь проверяется протокол, а его собеседник - обычный
QWebSocket, который ведёт себя как браузерный.
"""

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import config as C  # noqa: E402

# --- Подмена конфига. ДО того, как Backend его прочитает. ---
_MEM = dict(C.DEFAULTS)
_SAVED: list = []

C.load = lambda path=None: dict(_MEM)


def _save(cfg, path=None):
    _MEM.clear()
    _MEM.update(cfg)
    _SAVED.append(dict(cfg))


C.save = _save

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer, QUrl  # noqa: E402
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest  # noqa: E402
from PySide6.QtWebSockets import QWebSocket  # noqa: E402

import bridge as B  # noqa: E402
import settings_qt as S  # noqa: E402

fails: list = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ок ' if ok else 'СБОЙ'}  {name}" + (f" - {detail}" if detail else ""))
    if not ok:
        fails.append(name)


def pump(ms: int) -> None:
    """Покрутить очередь событий. Сеть здесь асинхронная вся."""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def http_get(url: str) -> tuple:
    """(код ответа, тело). Обычным клиентом, а не своим разбором сокета."""
    nam = QNetworkAccessManager()
    reply = nam.get(QNetworkRequest(QUrl(url)))
    loop = QEventLoop()
    reply.finished.connect(loop.quit)
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
    return code, bytes(reply.readAll())


class Page:
    """Собеседник моста - тот же WebSocket, что и у браузера."""

    def __init__(self, url: str) -> None:
        self.sock = QWebSocket()
        self.got: list = []
        self.closed = False
        self.sock.textMessageReceived.connect(
            lambda m: self.got.append(json.loads(m)))
        self.sock.disconnected.connect(self._bye)
        self.sock.open(QUrl(url))

    def _bye(self) -> None:
        self.closed = True

    def send(self, obj: dict) -> None:
        self.sock.sendTextMessage(json.dumps(obj, ensure_ascii=False))

    def wait_for(self, kind: str, ms: int = 3000) -> dict | None:
        step, spent = 50, 0
        while spent < ms:
            for m in self.got:
                if m.get("t") == kind:
                    return m
            pump(step)
            spent += step
        return None


def main() -> int:
    QCoreApplication(sys.argv)

    backend = S.Backend(
        on_change=lambda *_a, **_k: None,
        on_hotkey_capture=lambda *_a, **_k: None,
        info_fn=lambda: {},
        history_path=os.devnull,
        log_path=os.devnull,
    )
    br = B.Bridge(backend)
    print(f"мост поднят: http {br.http_port}, ws {br.ws_port}")

    print("\nТОКЕН")
    code, _body = http_get(f"http://127.0.0.1:{br.http_port}/")
    check("статика без токена не отдаётся", code == 403, f"код {code}")

    bad = Page(f"ws://127.0.0.1:{br.ws_port}/?t=нетакой&w=0")
    pump(600)
    check("сокет с чужим токеном закрыт", bad.closed and br.rejected >= 1,
          f"отбито {br.rejected}")

    print("\nЧТЕНИЕ И ЗАПИСЬ")
    page = Page(f"ws://127.0.0.1:{br.ws_port}/?t={br.token}&w={br.ws_port}")
    pump(600)
    check("сокет со своим токеном принят", not page.closed and len(br.clients) == 1)

    page.send({"t": "get", "path": "hotkey_hold"})
    got = page.wait_for("val")
    check("get возвращает значение", got is not None and got.get("path") == "hotkey_hold",
          str(got))

    page.got.clear()
    page.send({"t": "set", "path": "min_record_sec", "v": 0.7})
    pump(1200)
    # Backend копит записи и сбрасывает их отложенно - ждём именно записи в
    # конфиг, а не ответа сокета: критерий говорит про config.json.
    for _ in range(20):
        if any(c.get("min_record_sec") == 0.7 for c in _SAVED):
            break
        pump(200)
    check("set доезжает до конфига",
          any(c.get("min_record_sec") == 0.7 for c in _SAVED),
          f"записей {len(_SAVED)}")

    echo = next((m for m in page.got if m.get("t") == "val"), None)
    check("после set мост подтверждает значение",
          echo is not None and echo.get("v") == 0.7, str(echo))

    print("\nВЫЗОВЫ")
    page.got.clear()
    page.send({"t": "call", "m": "modelsInfo", "a": [], "id": 17})
    ret = page.wait_for("ret")
    check("call возвращает ret с тем же id",
          ret is not None and ret.get("id") == 17, str(ret)[:80])
    check("modelsInfo вернул список",
          ret is not None and isinstance(ret.get("v"), list))

    page.got.clear()
    page.send({"t": "call", "m": "этогоНетВовсе", "a": [], "id": 18})
    ret = page.wait_for("ret")
    check("несуществующий метод даёт жалобу, а не молчание",
          ret is not None and bool(ret.get("e")), str(ret)[:80])

    print("\nСИГНАЛЫ")
    page.got.clear()
    backend.flashed.emit("сохранено", "")
    pump(600)
    sig = next((m for m in page.got if m.get("t") == "sig"), None)
    check("сигнал Backend доезжает до страницы",
          sig is not None and sig.get("name") == "flashed", str(sig)[:80])

    br.close()
    print()
    if fails:
        print("СБОЙ: " + ", ".join(fails))
        return 1
    print("ОК")
    return 0


if __name__ == "__main__":
    sys.exit(main())
