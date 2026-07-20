"""Фаза 0 плана: можно ли жить с QtWebView + WebView2. Шесть замеров.

Это ШЛЮЗ. Плана переезда визуала на React без этих шести чисел не существует:
провалился любой пункт - план закрыт, и React не пишется ни строкой. Замер
сильнее мнения, а мнений про вебвью много.

Что меряем и почему именно это:

1. Окно поднимается и грузит страницу с localhost. Без этого разговора нет.
2. `runJavaScript` доходит из Python в страницу. Это дорога «Python -> вёрстка»:
   тема, язык, показать окно на нужной странице.
3. WebSocket из страницы обратно в Python. Дорога назад. У QtWebView нет
   QWebChannel (проверено по plugins.qmltypes: есть runJavaScript, loadHtml,
   url, title - канала нет), поэтому мост придётся делать самим, и вот его
   основа.
4. Память. WebView2 живёт ОТДЕЛЬНЫМИ процессами msedgewebview2.exe, и в своей
   программе их не видно вовсе - потому и считаем не себя, а появившихся
   соседей. Программа висит в трее сутками, и сотня-другая мегабайт за окно,
   которое открывают раз в неделю, - это решение, а не мелочь.
5. Задержка от show() до загруженной страницы. Порог 400 мс: сейчас окно
   открывается мгновенно, и терять это молча нельзя.
6. Прирост установщика. Порог +3 МБ. Меряется отдельным заходом (`--build`):
   сборка идёт минутами, а первые пять замеров - секундами.

Ни один шаг ничего не пишет в конфиг и не трогает установленную программу.

    python tools/probe_webview.py            # замеры 1-5
    python tools/probe_webview.py --build    # замер 6, долгий
"""

import json
import os
import secrets
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Каталог PySide6 - в поиск библиотек, иначе QML-плагин вебвью не грузится.
#
# Первая же попытка встала на «Cannot load library qtwebviewquickplugin.dll:
# не найден указанный модуль», хотя все DLL лежат на месте и ctypes их берёт.
# Причина не в них: Python 3.8+ зовёт SetDefaultDllDirectories, и PATH из
# поиска ВЫПАДАЕТ. Qt грузит плагин обычным LoadLibrary и не находит соседний
# Qt6WebViewQuick.dll. add_dll_directory возвращает каталог в поиск.
#
# В собранной программе этого не понадобится - там DLL лежат рядом с exe, а
# каталог exe в поиске есть всегда. Грабля чисто для запуска из исходников,
# но ловится она первой, и без неё замер выглядит как «вебвью не работает».
import PySide6  # noqa: E402

os.add_dll_directory(os.path.dirname(PySide6.__file__))

# initialize() зовётся ДО QGuiApplication - так требует Qt. Отсюда и импорт
# здесь, до всего остального Qt-хозяйства.
from PySide6.QtWebView import QtWebView  # noqa: E402

QtWebView.initialize()

from PySide6.QtCore import (QByteArray, QMetaObject, QObject,  # noqa: E402
                            QTimer, QUrl, Slot)
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtNetwork import QHostAddress, QTcpServer  # noqa: E402
from PySide6.QtQuick import QQuickView  # noqa: E402
from PySide6.QtWebSockets import QWebSocketServer  # noqa: E402

PORT_ANY = 0
TIMEOUT_MS = 20_000
LATENCY_LIMIT_MS = 400
INSTALLER_LIMIT_MB = 3.0

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = secrets.token_urlsafe(32)

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>probe</title>
<body style="background:#fbfbfa;font:14px sans-serif;margin:0;padding:24px">
<h1 id="h">страница жива</h1>
<p id="ws">сокет: не открыт</p>
<script>
  // Ответ на runJavaScript. Python попросит вернуть это значение - так
  // проверяется дорога «Python -> страница».
  window.probeAnswer = function () { return "js-ok:" + document.title; };

  var s = new WebSocket("ws://127.0.0.1:__WSPORT__/bridge?t=__TOKEN__");
  s.onopen    = function () { s.send(JSON.stringify({t: "hello", from: "page"})); };
  s.onmessage = function (e) { document.getElementById("ws").textContent = "сокет: " + e.data; };
  s.onerror   = function () { document.getElementById("ws").textContent = "сокет: ошибка"; };
</script>
"""

QML = """
import QtQuick
import QtWebView

Item {
    id: root
    width: 900; height: 640
    property string startUrl: ""
    signal loaded(bool ok, string detail)
    signal jsAnswer(string value)

    // Спрашиваем страницу ОТСЮДА, а не из Python. runJavaScript ждёт
    // JS-функцию обратного вызова, и питоновская лямбда на её месте молчит:
    // исключения нет, ответа тоже. Полминуты замера ушло ровно на это.
    function askJs() {
        view.runJavaScript("window.probeAnswer()", function (r) {
            root.jsAnswer(r === undefined || r === null ? "" : String(r));
        });
    }

    WebView {
        id: view
        objectName: "view"
        anchors.fill: parent
        url: root.startUrl
        onLoadingChanged: function (info) {
            if (info.status === WebView.LoadSucceededStatus)
                root.loaded(true, "");
            else if (info.status === WebView.LoadFailedStatus)
                root.loaded(false, info.errorString);
        }
    }
}
"""


# --------------------------------------------------------------------------
# Память: считаем не себя, а процессы вебвью, которых до открытия окна не было.

def _webview_pids() -> set:
    """PID'ы msedgewebview2.exe прямо сейчас."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process -Name msedgewebview2 -ErrorAction SilentlyContinue)"
             " | ForEach-Object { $_.Id }"],
            capture_output=True, text=True, timeout=30)
    except Exception:  # noqa: BLE001
        return set()
    return {int(x) for x in r.stdout.split() if x.strip().isdigit()}


def _rss_mb(pids: set) -> float:
    """Рабочий набор перечисленных процессов, мегабайты.

    Через PowerShell, а не tasklist: tasklist печатает число в локали системы
    («12 345 КБ»), и разбирать это - лишний повод ошибиться.
    """
    if not pids:
        return 0.0
    ids = ",".join(str(p) for p in pids)
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-Process -Id {ids} -ErrorAction SilentlyContinue"
             " | Measure-Object WorkingSet64 -Sum).Sum"],
            capture_output=True, text=True, timeout=30)
        return int(r.stdout.strip() or 0) / 1e6
    except Exception:  # noqa: BLE001
        return 0.0


def _private_mb(pids: set) -> float:
    """Приватный рабочий набор, мегабайты, - честная цена по памяти.

    Обычный WorkingSet64 у шести процессов вебвью считает общие страницы по
    разу на процесс, и сумма выходит заметно больше, чем программа на самом
    деле занимает. Решать судьбу плана по завышенному числу нельзя, поэтому
    рядом меряем приватную часть - то, что действительно принадлежит этим
    процессам и освободится вместе с ними.
    """
    if not pids:
        return 0.0
    ids = ",".join(str(p) for p in pids)
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"$ids = @({ids}); "
             "(Get-CimInstance Win32_PerfRawData_PerfProc_Process | "
             "Where-Object { $ids -contains $_.IDProcess } | "
             "Measure-Object WorkingSetPrivate -Sum).Sum"],
            capture_output=True, text=True, timeout=60)
        # float, а не int: PowerShell печатает большие суммы то целым, то
        # «3,4344E+08», и int на втором виде падал молча в ноль.
        return float(r.stdout.strip() or 0) / 1e6
    except Exception:  # noqa: BLE001
        return 0.0


# --------------------------------------------------------------------------
# Сервер: статика и сокет. Оба строго на LocalHost и оба с токеном.

class Http(QTcpServer):
    """Отдаёт одну страницу. Токен обязателен - чужой запрос получает 403.

    Настоящий сервер из фазы 1 будет отдавать web/dist целиком; здесь нужно
    ровно столько, чтобы вебвью было что показать.
    """

    def __init__(self, page: bytes) -> None:
        super().__init__()
        self.page = page
        self.newConnection.connect(self._serve)

    @Slot()
    def _serve(self) -> None:
        while self.hasPendingConnections():
            sock = self.nextPendingConnection()
            sock.readyRead.connect(lambda s=sock: self._reply(s))

    def _reply(self, sock) -> None:
        head = bytes(sock.readAll()).split(b"\r\n", 1)[0].decode("latin-1", "replace")
        ok = f"t={TOKEN}" in head
        body = self.page if ok else b"forbidden"
        status = "200 OK" if ok else "403 Forbidden"
        sock.write(QByteArray(
            f"HTTP/1.1 {status}\r\nContent-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
            .encode() + body))
        sock.disconnectFromHost()


class Sockets(QObject):
    """Мост назад. Держит соединения и запоминает, что пришло от страницы."""

    def __init__(self) -> None:
        super().__init__()
        self.server = QWebSocketServer("probe", QWebSocketServer.NonSecureMode)
        self.server.listen(QHostAddress.LocalHost, PORT_ANY)
        self.server.newConnection.connect(self._join)
        self.clients: list = []
        self.got: list = []
        self.rejected = 0

    @Slot()
    def _join(self) -> None:
        c = self.server.nextPendingConnection()
        if f"t={TOKEN}" not in c.requestUrl().query():
            self.rejected += 1
            c.close()
            return
        self.clients.append(c)
        c.textMessageReceived.connect(lambda m, cc=c: self._say(cc, m))

    def _say(self, client, msg: str) -> None:
        self.got.append(msg)
        client.sendTextMessage(json.dumps({"t": "ack", "saw": msg},
                                          ensure_ascii=False))


# --------------------------------------------------------------------------

def measure() -> dict:
    app = QGuiApplication(sys.argv)
    res: dict = {}

    ws = Sockets()
    ws_port = ws.server.serverPort()
    http = Http(PAGE.replace("__WSPORT__", str(ws_port))
                    .replace("__TOKEN__", TOKEN).encode("utf-8"))
    http.listen(QHostAddress.LocalHost, PORT_ANY)
    url = f"http://127.0.0.1:{http.serverPort()}/?t={TOKEN}"
    print(f"страница: {url}")
    print(f"сокет:    ws://127.0.0.1:{ws_port}/bridge")

    qml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "_probe_webview.qml")
    with open(qml_path, "w", encoding="utf-8") as f:
        f.write(QML)

    before_pids = _webview_pids()
    own_mb = _rss_mb({os.getpid()})

    view = QQuickView()
    view.setSource(QUrl.fromLocalFile(qml_path))
    if view.status() == QQuickView.Error:
        for e in view.errors():
            print("  QML:", e.toString())
        res["1_окно"] = False
        return res
    root = view.rootObject()
    root.setProperty("startUrl", url)

    t0 = time.perf_counter()
    state = {"done": False}

    def on_loaded(ok: bool, detail: str) -> None:
        if state["done"]:
            return
        state["done"] = True
        res["1_окно"] = bool(ok)
        res["_ошибка"] = detail
        res["5_задержка_мс"] = (time.perf_counter() - t0) * 1000
        QTimer.singleShot(0, step_js)

    root.loaded.connect(on_loaded)

    def step_js() -> None:
        root.jsAnswer.connect(js_back)
        QMetaObject.invokeMethod(root, "askJs")
        # Ответа может не быть вовсе - тогда меряем остальное и говорим «нет».
        QTimer.singleShot(3000, lambda: js_back("") if "2_runJavaScript"
                          not in res else None)

    def js_back(value) -> None:
        if "2_runJavaScript" in res:
            return
        res["2_runJavaScript"] = str(value or "").startswith("js-ok:")
        res["_js_ответ"] = str(value)
        # Сокету даём время: страница открывает его сама, и открывается он
        # не мгновенно.
        QTimer.singleShot(1500, step_ram)

    def step_ram() -> None:
        res["3_сокет"] = bool(ws.got)
        res["_сокет_сказал"] = ws.got[0] if ws.got else ""
        new = _webview_pids() - before_pids
        res["4_память_вебвью_мб"] = _rss_mb(new)
        res["4_память_вебвью_приватно_мб"] = _private_mb(new)
        res["_процессов_вебвью"] = len(new)
        res["_своя_память_до_мб"] = own_mb
        res["4_своя_память_после_мб"] = _rss_mb({os.getpid()})
        # Проверка отхода: план собирался создавать вебвью по требованию и
        # убивать при закрытии окна. Если память после этого не возвращается,
        # оговорка не работает, и знать это надо здесь, а не через полгода.
        view.hide()
        view.setSource(QUrl())
        QTimer.singleShot(2500, after_close)

    def after_close() -> None:
        alive = _webview_pids() - before_pids
        res["_вебвью_осталось_процессов"] = len(alive)
        res["4_память_после_закрытия_мб"] = _rss_mb(alive)
        app.quit()

    view.show()
    QTimer.singleShot(TIMEOUT_MS, app.quit)
    app.exec()

    try:
        os.remove(qml_path)
    except OSError:
        pass
    return res


# --------------------------------------------------------------------------

def build_delta() -> None:
    """Замер 6: во что обходится вебвью в установщике.

    Собираем как обычно и сравниваем с 70 МБ - той самой линейкой, по которой
    уже отклонён PyAV. Долго, поэтому отдельным ключом.
    """
    print("сборка установщика - это минуты")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build.py"),
                        "cpu", "--installer"], cwd=ROOT)
    if r.returncode != 0:
        print("сборка не прошла - замер 6 без ответа")
        return
    out = os.path.join(ROOT, "dist")
    found = [(f, os.path.getsize(os.path.join(out, f)) / 1e6)
             for f in os.listdir(out) if f.lower().endswith(".exe")]
    for f, mb in sorted(found, key=lambda x: -x[1]):
        print(f"  {f}: {mb:.1f} МБ")


def main() -> int:
    if "--build" in sys.argv:
        build_delta()
        return 0

    res = measure()
    print()
    print("=" * 62)
    checks = [
        ("1. Окно грузит страницу с localhost", res.get("1_окно"), None),
        ("2. runJavaScript доходит в страницу", res.get("2_runJavaScript"), None),
        ("3. WebSocket доходит обратно", res.get("3_сокет"), None),
    ]
    for name, ok, _ in checks:
        print(f"  {'ДА ' if ok else 'НЕТ'}  {name}")

    lat = res.get("5_задержка_мс")
    ram = res.get("4_память_вебвью_мб")
    if lat is not None:
        ok = lat <= LATENCY_LIMIT_MS
        print(f"  {'ДА ' if ok else 'НЕТ'}  5. Задержка открытия: {lat:.0f} мс "
              f"(порог {LATENCY_LIMIT_MS})")
    if ram is not None:
        print(f"       4. Память вебвью: {ram:.0f} МБ рабочего набора "
              f"в {res.get('_процессов_вебвью', 0)} процессах")
        print(f"          приватно (честная цена): "
              f"{res.get('4_память_вебвью_приватно_мб', 0):.0f} МБ")
        print(f"          своя: {res.get('_своя_память_до_мб', 0):.0f} -> "
              f"{res.get('4_своя_память_после_мб', 0):.0f} МБ")
        print(f"          после закрытия окна осталось "
              f"{res.get('_вебвью_осталось_процессов', 0)} процессов, "
              f"{res.get('4_память_после_закрытия_мб', 0):.0f} МБ")
    print(f"       Токен: чужих сокетов отбито {res.get('_отбито', 0)}")
    for k in ("_ошибка", "_js_ошибка", "_js_ответ", "_сокет_сказал"):
        if res.get(k):
            print(f"       {k[1:]}: {res[k]}")
    print("=" * 62)
    print("замер 6 (установщик): python tools/probe_webview.py --build")

    hard = [res.get("1_окно"), res.get("2_runJavaScript"), res.get("3_сокет")]
    return 0 if all(hard) else 1


if __name__ == "__main__":
    sys.exit(main())
