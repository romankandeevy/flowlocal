"""Мост «страница в вебвью <-> Python». Фаза 1 плана.

Зачем он вообще. У QtWebView нет QWebChannel - проверено по plugins.qmltypes:
есть runJavaScript, loadHtml, url, title, канала нет. Значит, дорогу назад из
страницы в Python надо строить самим, и строится она на том, что у вебвью есть
всегда: HTTP и WebSocket.

Два сервера, оба на QHostAddress.LocalHost и оба на порту 0 (порт выбирает ОС):

- QTcpServer отдаёт статику: web/dist целиком и assets/fonts под /fonts/.
  Шрифты нужны отдельной веткой, потому что theme.py ставит Onest и JetBrains
  Mono через AddFontResourceExW - это для Qt, странице они так не видны, ей
  нужен @font-face с локального сервера.
- QWebSocketServer держит сам мост.

Токен. secrets.token_urlsafe(32) на сеанс, проверяется на ОБОИХ серверах. Чужой
запрос получает 403 (HTTP) или закрытие сокета с CloseCodePolicyViolated (WS).
Привязка к 127.0.0.1 уже отсекает соседей по сети, токен отсекает соседей по
машине - другую программу, которая просто перебирает локальные порты.

Токен ездит двумя путями, и это не лишнее. В строке адреса он есть только у
первого запроса (страница открывается как /?t=...&w=...), а картинки, скрипты и
шрифты грузятся своими запросами, где никакого «?t=» уже нет. Поэтому на
успешном запросе с токеном ставим cookie и дальше принимаем её. Без cookie
пришлось бы либо открыть статику всем, либо разбирать Referer, а он
необязательный.

Протокол - JSON, четыре типа (PLAN, фаза 1, пункт 4):

    страница -> Python
    {"t":"get",  "path":"hotkey_hold"}
    {"t":"set",  "path":"hotkey_hold", "v":"ctrl+space"}
    {"t":"call", "m":"setModel", "a":["gigaam-v3"], "id":17}

    Python -> страница
    {"t":"val", "path":"hotkey_hold", "v":"ctrl+space"}
    {"t":"ret", "id":17, "v":null}
    {"t":"sig", "name":"flashed", "a":["сохранено",""]}

Два уточнения сверх плана, оба обратно совместимы:

1. У `ret` бывает поле `e` - текст жалобы, если вызов не прошёл. Без него
   страница не отличила бы «вернулось null» от «упало», а таймаут в 5 секунд
   ждать незачем, когда ответ уже есть.
2. После `set` мост рассылает `val` ВСЕМ клиентам. Это подтверждение записи и
   заодно синхронизация, если страниц открыто несколько.

Backend не меняется ни строкой - это условие плана. Мост зовёт его @Slot-методы
и читает Q_PROPERTY через тот же metaObject, по которому tools/gen_bridge.py
печатает клиента: один источник правды, разъехаться им негде.
"""

import json
import mimetypes
import os
import posixpath
import secrets
from urllib.parse import parse_qs, unquote, urlsplit

from PySide6.QtCore import QByteArray, QMetaMethod, QObject, Signal, Slot
from PySide6.QtNetwork import QHostAddress, QTcpServer
from PySide6.QtWebSockets import QWebSocketProtocol, QWebSocketServer

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Имя cookie короткое и своё: 127.0.0.1 общий для всех локальных программ, и
# «token» там мог бы быть чужой.
COOKIE = "flbridge"

PORT_ANY = 0

# Потолок на строку запроса с заголовками. Свой сервер обязан иметь предел,
# иначе один кривой клиент набивает нам память бесконечным заголовком.
MAX_HEAD = 16 * 1024

# Типы содержимого - своей таблицей, а не одним mimetypes.
#
# mimetypes на Windows лезет в реестр, и там .js регулярно оказывается
# text/plain: любая программа могла переписать эту ветку. Браузер на text/plain
# модуль не выполнит, и выглядит это как «страница пустая», а не как ошибка
# типа. Таблица идёт первой, mimetypes остаётся запасным путём для редкого.
_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".map": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}


def _log(msg: str) -> None:
    """Подробность - в журнал, не в интерфейс. Импорт внутри функции: app
    импортирует нас, и сверху вышло бы кольцо (тот же приём в settings_qt)."""
    try:
        from app import log

        log(msg)
    except Exception:  # noqa: BLE001 - молчащий журнал не роняет окно
        pass


def _mime(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in _TYPES:
        return _TYPES[ext]
    guess, _ = mimetypes.guess_type(path)
    return guess or "application/octet-stream"


def _qobject_names() -> set:
    """Имена методов и свойств самого QObject: deleteLater, destroyed и прочее.

    Нужны как чёрный список: своё от унаследованного мы отделяем по имени, а
    не по methodOffset() - почему именно так, разобрано в Bridge._surface.
    """
    out = set()
    mo = QObject.staticMetaObject
    for i in range(mo.methodCount()):
        out.add(bytes(mo.method(i).name()).decode())
    for i in range(mo.propertyCount()):
        out.add(mo.property(i).name())
    return out


def _jsonable(x):
    """Запасной переводчик для json.dumps.

    Backend отдаёт QVariantMap и QVariantList, а PySide превращает их в обычные
    dict и list - им переводчик не нужен. Он нужен редкому: QUrl, QColor, set.
    Молча уронить весь ответ из-за одного поля хуже, чем отдать его строкой.
    """
    if isinstance(x, (set, frozenset, tuple)):
        return list(x)
    return str(x)


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=_jsonable)


# --------------------------------------------------------------------------
# Статика


class Static(QTcpServer):
    """HTTP на 127.0.0.1: web/dist и assets/fonts. Только GET и HEAD.

    Свой сервер, а не http.server: тот держит свой поток и свою очередь, а нам
    нужно жить в цикле событий Qt рядом с окном. Плюс QTcpServer сам умеет
    слушать строго один адрес.
    """

    def __init__(self, token: str, roots: dict, parent=None) -> None:
        super().__init__(parent)
        self.token = token
        # {"/fonts": "...assets/fonts", "": "...web/dist"} - длинные приставки
        # первыми, чтобы /fonts не съел корень.
        self.roots = {k: os.path.realpath(v) for k, v in roots.items()}
        self.rejected = 0          # сколько запросов отбито по токену
        # Недочитанное по каждому соединению. Обычным dict, а не свойством
        # сокета: QVariant по дороге туда-обратно меняет QByteArray на bytes и
        # обратно, и на этом легко потерять половину заголовка.
        self._bufs: dict = {}
        self.newConnection.connect(self._accept)

    @Slot()
    def _accept(self) -> None:
        while self.hasPendingConnections():
            sock = self.nextPendingConnection()
            self._bufs[sock] = b""
            sock.readyRead.connect(lambda s=sock: self._read(s))
            sock.disconnected.connect(lambda s=sock: self._drop(s))

    def _drop(self, sock) -> None:
        self._bufs.pop(sock, None)
        sock.deleteLater()

    def _read(self, sock) -> None:
        if sock not in self._bufs:
            return
        buf = self._bufs[sock] + bytes(sock.readAll())
        # Держим keep-alive: WebView2 тянет десяток файлов, и по соединению на
        # файл - это лишние рукопожатия там, где замер 5 и так вышел за порог.
        while True:
            head_end = buf.find(b"\r\n\r\n")
            if head_end < 0:
                if len(buf) > MAX_HEAD:
                    sock.disconnectFromHost()
                    return
                self._bufs[sock] = buf
                return
            head = buf[:head_end].decode("latin-1", "replace")
            buf = buf[head_end + 4:]
            self._bufs[sock] = buf
            if not self._handle(sock, head):
                return
            if not buf:
                return

    def _handle(self, sock, head: str) -> bool:
        """Один запрос. False - соединение закрыто, разбирать дальше нечего."""
        lines = head.split("\r\n")
        parts = lines[0].split(" ")
        if len(parts) < 2:
            sock.disconnectFromHost()
            return False
        method, target = parts[0].upper(), parts[1]
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        if method not in ("GET", "HEAD"):
            self._send(sock, 405, b"method not allowed", "text/plain; charset=utf-8")
            return False

        split = urlsplit(target)
        by_query = self.token in parse_qs(split.query).get("t", ())
        by_cookie = f"{COOKIE}={self.token}" in headers.get("cookie", "")
        if not (by_query or by_cookie):
            self.rejected += 1
            self._send(sock, 403, b"forbidden", "text/plain; charset=utf-8")
            return False

        path = self._resolve(split.path)
        if path is None:
            self._send(sock, 404, b"not found", "text/plain; charset=utf-8")
            return True
        try:
            with open(path, "rb") as f:
                body = f.read()
        except OSError as e:
            _log(f"мост: не отдал {path}: {e}")
            self._send(sock, 404, b"not found", "text/plain; charset=utf-8")
            return True

        # Cookie ставим только там, где токен пришёл строкой адреса, - то есть
        # на самой странице. Вешать её на каждый файл незачем.
        extra = (f"Set-Cookie: {COOKIE}={self.token}; Path=/; SameSite=Strict\r\n"
                 if by_query else "")
        # index.html не кэшируем: пересборка web/dist меняет его, а имена
        # остального Vite хеширует - тем можно и полежать.
        cache = ("no-store" if path.endswith(".html") else "max-age=86400")
        self._send(sock, 200, b"" if method == "HEAD" else body, _mime(path),
                   extra=extra + f"Cache-Control: {cache}\r\n",
                   length=len(body))
        return True

    def _resolve(self, url_path: str):
        """URL -> файл на диске или None. Здесь же защита от выхода из корня."""
        p = posixpath.normpath(unquote(url_path or "/"))
        for prefix in sorted(self.roots, key=len, reverse=True):
            if prefix and not (p == prefix or p.startswith(prefix + "/")):
                continue
            rel = p[len(prefix):].lstrip("/")
            root = self.roots[prefix]
            if rel in ("", "."):
                rel = "index.html"
            full = os.path.realpath(os.path.join(root, rel.replace("/", os.sep)))
            # Сравниваем уже разрешённые пути: иначе «..» или ссылка на диске
            # вывели бы отдачу за пределы web/dist.
            if full != root and not full.startswith(root + os.sep):
                return None
            if os.path.isfile(full):
                return full
            return None
        return None

    def _send(self, sock, code: int, body: bytes, mime: str,
              extra: str = "", length: int | None = None) -> None:
        reason = {200: "OK", 403: "Forbidden", 404: "Not Found",
                  405: "Method Not Allowed"}.get(code, "OK")
        n = len(body) if length is None else length
        head = (f"HTTP/1.1 {code} {reason}\r\n"
                f"Content-Type: {mime}\r\n"
                f"Content-Length: {n}\r\n"
                # Страница локальная и в рамку никого не пускает.
                f"X-Content-Type-Options: nosniff\r\n"
                f"{extra}"
                f"Connection: {'keep-alive' if code == 200 else 'close'}\r\n\r\n")
        sock.write(QByteArray(head.encode("latin-1") + body))
        if code != 200:
            sock.disconnectFromHost()


# --------------------------------------------------------------------------
# Мост


class Bridge(QObject):
    """Сервера, токен и разбор протокола. Один на приложение.

    Backend сюда передаётся готовым и не меняется: мост ходит по его
    metaObject - тому же, по которому tools/gen_bridge.py печатает api.ts.
    """

    # Страница подключилась или отключилась - окну это нужно, чтобы понимать,
    # можно ли уже что-то ей говорить.
    clientsChanged = Signal(int)

    def __init__(self, backend, parent=None) -> None:
        super().__init__(parent)
        self.backend = backend
        self.token = secrets.token_urlsafe(32)

        self.http = Static(self.token, {
            "": os.path.join(APP_DIR, "web", "dist"),
            "/fonts": os.path.join(APP_DIR, "assets", "fonts"),
        }, parent=self)
        if not self.http.listen(QHostAddress.LocalHost, PORT_ANY):
            raise RuntimeError(f"мост: HTTP не поднялся: {self.http.errorString()}")

        self.ws = QWebSocketServer("flowlocal", QWebSocketServer.NonSecureMode, self)
        if not self.ws.listen(QHostAddress.LocalHost, PORT_ANY):
            raise RuntimeError(f"мост: сокет не поднялся: {self.ws.errorString()}")
        self.ws.newConnection.connect(self._join)

        self.clients: list = []
        self.rejected = 0          # отбито сокетов с чужим токеном

        self._slots, self._props = self._surface()
        self._wire_signals()

    # ---------- адреса ----------

    @property
    def http_port(self) -> int:
        return self.http.serverPort()

    @property
    def ws_port(self) -> int:
        return self.ws.serverPort()

    def page_url(self, path: str = "/") -> str:
        """Адрес страницы. Порт сокета едет вместе с токеном: страница читает
        оба из location.search - другого способа узнать их у неё нет."""
        return (f"http://127.0.0.1:{self.http_port}{path}"
                f"?t={self.token}&w={self.ws_port}")

    # ---------- что вообще разрешено звать ----------

    def _surface(self) -> tuple:
        """Имена слотов и свойств Backend - белым списком.

        Токен уже никого чужого не пускает, но getattr по имени из сети без
        списка - это доступ ко всему объекту, включая _flush и cfg. Список
        строится из metaObject, поэтому новый @Slot появляется здесь сам.

        **Обход начинается с нуля, а не с methodOffset(), и это не небрежность.**
        У обычного C++-класса methodOffset() - это граница «своё против
        унаследованного». У питоновского наследника QObject в PySide она значит
        не то: слоты и сигналы, объявленные в Python, лежат ДО неё. У Backend
        methodOffset() = 92 при methodCount() = 96, а из восьмидесяти слотов за
        границей оказываются четыре, и ни одного из шестнадцати сигналов.
        Мост на этом молча терял почти весь Backend: modelsInfo отвечал «нет
        такого метода», сигналы не доходили вовсе. Поймано test_bridge.py -
        глазами такое не видно, список выглядит наполненным.

        Поэтому идём по всем методам, а чужое отсекаем по имени: то, что
        принадлежит самому QObject (deleteLater, destroyed, objectNameChanged),
        странице не адресовано.
        """
        own = _qobject_names()
        mo = self.backend.metaObject()
        slots, sigs = set(), set()
        for i in range(mo.methodCount()):
            m = mo.method(i)
            name = bytes(m.name()).decode()
            if name.startswith("_") or name in own:
                continue
            if m.methodType() == QMetaMethod.Slot:
                slots.add(name)
            elif m.methodType() == QMetaMethod.Signal:
                sigs.add(name)
        props = set()
        for i in range(mo.propertyCount()):
            name = mo.property(i).name()
            if name not in own:
                props.add(name)
        self._signal_names = sigs
        return slots, props

    def _wire_signals(self) -> None:
        """Каждый публичный сигнал Backend - в страницу как {"t":"sig"}.

        Приватные (с подчёркиванием) не трогаем: ими Backend перебрасывает
        результат из рабочего потока в главный, странице они не адресованы.

        Список берём из _surface - там же, где слоты, и по той же причине:
        methodOffset() у питоновского наследника не отделяет своё от чужого,
        и обход по нему не находил ни одного сигнала.
        """
        for name in sorted(self._signal_names):
            try:
                sig = getattr(self.backend, name)
            except AttributeError:
                continue
            # *a, а не фиксированная арность: сигналы Backend от нуля до трёх
            # аргументов, и перечислять их здесь значило бы держать второй
            # список рядом с metaObject.
            sig.connect(lambda *a, n=name: self.emit_signal(n, *a))

    # ---------- сокет ----------

    @Slot()
    def _join(self) -> None:
        c = self.ws.nextPendingConnection()
        if c is None:
            return
        if f"t={self.token}" not in c.requestUrl().query():
            self.rejected += 1
            # Рукопожатие к этому моменту уже прошло - 403 послать нечем,
            # поэтому закрываем с кодом «нарушение правил». Страница увидит
            # onclose с 1008, а не молчание.
            c.close(QWebSocketProtocol.CloseCode.CloseCodePolicyViolated,
                    "forbidden")
            _log("мост: сокет с чужим токеном отбит")
            return
        self.clients.append(c)
        c.textMessageReceived.connect(lambda s, cc=c: self._on_text(cc, s))
        c.disconnected.connect(lambda cc=c: self._leave(cc))
        self.clientsChanged.emit(len(self.clients))

    def _leave(self, client) -> None:
        if client in self.clients:
            self.clients.remove(client)
            self.clientsChanged.emit(len(self.clients))
        # Сокет к этому моменту может быть уже снесён самим Qt - например,
        # когда сервер закрывается и рвёт соединения сам. Тогда shiboken
        # честно говорит «C++ object already deleted», и это не ошибка, а
        # гонка порядка: обработчик disconnected приходит после сноса.
        try:
            client.deleteLater()
        except RuntimeError:
            pass

    def _send(self, client, obj: dict) -> None:
        try:
            client.sendTextMessage(_dumps(obj))
        except RuntimeError:
            # Клиент мог уйти между проверкой и отправкой - это не событие.
            pass

    def broadcast(self, obj: dict) -> None:
        for c in list(self.clients):
            self._send(c, obj)

    def emit_signal(self, name: str, *args) -> None:
        """Сигнал в страницу. Зовётся и из Backend, и из рамки QML (перетаскивание)."""
        self.broadcast({"t": "sig", "name": name, "a": list(args)})

    # ---------- протокол ----------

    def _on_text(self, client, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except ValueError:
            _log(f"мост: не разобрал сообщение ({raw[:80]})")
            return
        if not isinstance(msg, dict):
            return
        kind = msg.get("t")
        if kind == "get":
            self._do_get(client, msg)
        elif kind == "set":
            self._do_set(msg)
        elif kind == "call":
            self._do_call(client, msg)
        else:
            _log(f"мост: неизвестный тип {kind!r}")

    def _do_get(self, client, msg: dict) -> None:
        path = str(msg.get("path") or "")
        self._send(client, {"t": "val", "path": path,
                            "v": self.backend.get(path)})

    def _do_set(self, msg: dict) -> None:
        path = str(msg.get("path") or "")
        if not path:
            return
        value = msg.get("v")
        self.backend.set(path, value)
        # Всем, а не только приславшему: страниц может быть открыто несколько,
        # и вторая обязана увидеть чужую правку.
        self.broadcast({"t": "val", "path": path, "v": value})

    def _do_call(self, client, msg: dict) -> None:
        name = str(msg.get("m") or "")
        args = msg.get("a") or []
        call_id = msg.get("id")
        if not isinstance(args, list):
            args = [args]

        if name in self._slots:
            try:
                value = getattr(self.backend, name)(*args)
            except Exception as e:  # noqa: BLE001 - страница не должна ронять окно
                _log(f"мост: {name}() упал: {e}")
                self._send(client, {"t": "ret", "id": call_id, "v": None,
                                    "e": f"{type(e).__name__}: {e}"})
                return
        elif name in self._props:
            # Q_PROPERTY слотом не является, а читать её странице надо. Тем же
            # `call` без аргументов - заводить пятый тип сообщения ради чтения
            # свойства не за что.
            value = self.backend.property(name)
        else:
            self._send(client, {"t": "ret", "id": call_id, "v": None,
                                "e": f"нет такого метода: {name}"})
            return
        self._send(client, {"t": "ret", "id": call_id, "v": value})

    # ---------- уборка ----------

    def close(self) -> None:
        for c in list(self.clients):
            c.close()
        self.clients.clear()
        self.ws.close()
        self.http.close()
