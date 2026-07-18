"""Тест обновлятора: сравнение версий и разбор ответа GitHub.

    python test_update.py

Настоящий GitHub не нужен: поднимаем заглушку, которая отдаёт то же, что и его
API, - в том числе мусор. Сеть в тесте означала бы, что он краснеет от чужих
неполадок, а это хуже, чем не тестировать вовсе.

Что здесь важнее всего: обновлятор обязан МОЛЧАТЬ на любой неурядице. Нет сети,
репозиторий приватный, GitHub отдал ерунду - во всех случаях None, и человек
ничего не замечает. Обновление - удобство; сломать им диктовку нельзя.
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import updater
from updater import _parse


class _Stub(BaseHTTPRequestHandler):
    payload: str = "{}"
    code: int = 200

    def do_GET(self):
        raw = self.payload.encode("utf-8")
        self.send_response(self.code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_a):
        pass


def serve(payload, code=200):
    _Stub.payload = payload if isinstance(payload, str) else json.dumps(payload)
    _Stub.code = code
    srv = HTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


def release(tag, name="FlowLocal-1.0.0-setup.exe", size=66_000_000):
    return {"tag_name": tag, "html_url": "https://example/r", "body": "заметки",
            "assets": [{"name": name, "size": size,
                        "browser_download_url": "https://example/s.exe"}]}


def check(name, got, want, fails):
    if got != want:
        fails.append(name)
        print(f"  ПРОВАЛ [{name}]\n    ждали: {want!r}\n    вышло: {got!r}")


def with_stub(payload, code=200, cur="0.1.0"):
    """Подменяем и адрес GitHub, и свою версию: сравнение зависит от обеих."""
    srv, url = serve(payload, code)
    old_api, old_ver = updater.urllib.request.Request, updater.__version__
    updater.__version__ = cur

    def fake_request(u, **kw):
        return old_api(url + "/x", **kw)

    updater.urllib.request.Request = fake_request
    try:
        return updater.check()
    finally:
        updater.urllib.request.Request = old_api
        updater.__version__ = old_ver
        srv.shutdown()


def main() -> None:
    fails = []

    # --- сравнение версий ---
    check("v-префикс не мешает", _parse("v1.2.3"), (1, 2, 3), fails)
    check("без префикса", _parse("0.2.0"), (0, 2, 0), fails)
    check("пререлиз обрезается", _parse("v0.2.0-beta.1"), (0, 2, 0), fails)
    # Четвёртое число - правка выпущенной версии (правило в CLAUDE.md).
    # Пока брали три, «0.3.1.1» разбиралось в тот же (0, 3, 1), что и «0.3.1»:
    # обновлятор считал их одинаковыми и молча ничего не предлагал.
    check("правка версии не теряется", _parse("v0.3.1.1"), (0, 3, 1, 1), fails)
    check("правка новее исходной",
          _parse("0.3.1.1") > _parse("0.3.1"), True, fails)
    check("следующая минорная новее правки",
          _parse("0.4.0") > _parse("0.3.1.1"), True, fails)
    check("мусор не роняет", _parse("не версия"), (0,), fails)
    check("пусто не роняет", _parse(""), (0,), fails)
    check("10 больше 9 (а не меньше, как у строк)",
          _parse("0.10.0") > _parse("0.9.0"), True, fails)

    # --- есть обновление ---
    got = with_stub(release("v0.2.0"), cur="0.1.0")
    check("свежая версия найдена", (got or {}).get("version"), "0.2.0", fails)
    check("размер посчитан", (got or {}).get("size_mb"), 66, fails)

    # --- нет обновления ---
    check("та же версия - молчим", with_stub(release("v0.1.0"), cur="0.1.0"), None, fails)
    check("старее нашей - молчим", with_stub(release("v0.0.9"), cur="0.1.0"), None, fails)

    # --- ЧТО НЕ ДОЛЖНО РОНЯТЬ ---
    check("нет установщика среди файлов",
          with_stub(release("v9.9.9", name="FlowLocal.zip"), cur="0.1.0"), None, fails)
    check("релизов нет вовсе (404)",
          with_stub({"message": "Not Found"}, code=404, cur="0.1.0"), None, fails)
    check("GitHub отдал не json", with_stub("<html>500</html>", cur="0.1.0"), None, fails)
    check("json без полей", with_stub({}, cur="0.1.0"), None, fails)
    check("assets пустой",
          with_stub({"tag_name": "v9.9.9", "assets": []}, cur="0.1.0"), None, fails)
    # Сети нет: стучимся в заведомо мёртвый порт. Раньше здесь стояла строка,
    # которая сравнивала None с None и проходила всегда, что бы ни случилось, -
    # такой тест хуже отсутствующего: он создаёт видимость проверки.
    old_repo = updater.GITHUB_REPO
    old_api = updater.urllib.request.Request
    updater.urllib.request.Request = lambda _u, **kw: old_api(
        "http://127.0.0.1:1/nothing", **kw)
    try:
        check("сети нет вовсе - молчим", updater.check(), None, fails)
    finally:
        updater.urllib.request.Request = old_api

    # Репозиторий не задан - проверку не делаем вовсе, даже в сеть не ходим.
    updater.GITHUB_REPO = ""
    try:
        check("репозиторий не задан - молчим", updater.check(), None, fails)
    finally:
        updater.GITHUB_REPO = old_repo

    # --- из исходников не обновляемся ---
    check("не frozen - обновлять нечего", updater.can_update(), False, fails)

    print(f"\n{'ОК' if not fails else 'ПРОВАЛЕНО: ' + ', '.join(fails)}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
