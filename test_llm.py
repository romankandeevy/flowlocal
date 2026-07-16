"""Тест слоя LLM: автоопределение Ollama и предохранитель от потери текста.

    python test_llm.py

Настоящая Ollama не нужна и не желательна: тест поднимает заглушку на свободном
порту и заставляет её вести себя так, как ведут себя модели на самом деле - в
том числе плохо.

Плохо - это не выдумка. Замер (PLAN 2.6-бис) показал вживую:
    Qwen3-0.6B:  «Вот дом, в котором я живу.»          -> «дом»
    Qwen3-1.7B:  «Выручка выросла на 15% за квартал.»  -> «Выручка выросла за квартал.»
Поэтому предохранитель здесь - не перестраховка, а требование: диктовка не
должна терять текст, даже если модель решила иначе.
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from cleaner import _llm_polish, autoconfig_llm, pick_llm_model, probe_ollama


class _Stub(BaseHTTPRequestHandler):
    models: list = []
    reply: str = ""

    def do_GET(self):                       # /api/tags
        body = json.dumps({"models": [{"name": n} for n in self.models]})
        self._send(body)

    def do_POST(self):                      # /api/generate
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self._send(json.dumps({"response": self.reply}))

    def _send(self, body: str):
        raw = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_a):             # не сорить в вывод теста
        pass


def serve(models, reply=""):
    _Stub.models, _Stub.reply = models, reply
    srv = HTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


def check(name, got, want, fails: list):
    if got != want:
        fails.append(name)
        print(f"  ПРОВАЛ [{name}]\n    ждали: {want!r}\n    вышло: {got!r}")


def main() -> None:
    fails: list = []
    log = lambda *_a: None  # noqa: E731

    # --- нет Ollama ---
    check("нет Ollama - пустой список", probe_ollama("http://127.0.0.1:1"), [], fails)

    cfg = {"llm": {"enabled": None, "url": "http://127.0.0.1:1", "model": ""}}
    check("нет Ollama - не включаем", autoconfig_llm(cfg, log), "", fails)
    check("нет Ollama - enabled не тронут", cfg["llm"]["enabled"], None, fails)

    # --- есть Ollama ---
    srv, url = serve(["qwen2.5:3b", "nomic-embed-text:latest"])
    check("нашли модели", probe_ollama(url), ["qwen2.5:3b", "nomic-embed-text:latest"], fails)

    cfg = {"llm": {"enabled": None, "url": url, "model": ""}}
    check("есть Ollama - выбрали модель", autoconfig_llm(cfg, log), "qwen2.5:3b", fails)
    check("есть Ollama - включились сами", cfg["llm"]["enabled"], True, fails)

    # --- человек решил сам: не переигрываем ---
    cfg = {"llm": {"enabled": False, "url": url, "model": ""}}
    autoconfig_llm(cfg, log)
    check("выключено человеком - не включаем обратно", cfg["llm"]["enabled"], False, fails)

    # --- выбор модели ---
    check("embed-модель не берём", pick_llm_model(["nomic-embed-text:latest"]), "", fails)
    check("vision не берём", pick_llm_model(["llava:7b", "qwen2-vl:7b"]), "", fails)
    check("предпочтение работает",
          pick_llm_model(["llama3.1:8b", "qwen2.5:3b"]), "qwen2.5:3b", fails)
    check("выбор человека уважаем",
          pick_llm_model(["llama3.1:8b", "qwen2.5:3b"], "llama3.1:8b"), "llama3.1:8b", fails)
    check("незнакомая, но текстовая - берём",
          pick_llm_model(["some-new-model:4b"]), "some-new-model:4b", fails)
    srv.shutdown()

    # --- ПРЕДОХРАНИТЕЛЬ: модель портит текст ---
    src = "Вот дом, в котором я живу."
    bad = [
        ("съела почти всё (так делала Qwen3-0.6B)", "дом"),
        ("вернула пустоту", ""),
        ("дописала от себя", " ".join(["слово"] * 40)),
    ]
    for name, reply in bad:
        srv, url = serve(["qwen2.5:3b"], reply=reply)
        cfg = {"url": url, "model": "qwen2.5:3b", "timeout_sec": 5}
        check(f"ПРЕДОХРАНИТЕЛЬ: {name}", _llm_polish(src, cfg, log), src, fails)
        srv.shutdown()

    # --- хорошая правка проходит ---
    srv, url = serve(["qwen2.5:3b"], reply="Встреча в субботу в десять утра.")
    cfg = {"url": url, "model": "qwen2.5:3b", "timeout_sec": 5}
    check("хорошая правка проходит",
          _llm_polish("Встреча в пятницу, нет, в субботу в десять утра.", cfg, log),
          "Встреча в субботу в десять утра.", fails)
    srv.shutdown()

    # --- Ollama сломалась посреди работы ---
    check("мёртвый url - отдаём сырой текст",
          _llm_polish(src, {"url": "http://127.0.0.1:1", "model": "x", "timeout_sec": 1}, log),
          src, fails)
    check("битый конфиг - отдаём сырой текст",
          _llm_polish(src, {}, log), src, fails)

    # --- миграция старого конфига ---
    import config
    check("старый false -> null (это было умолчание, а не выбор)",
          config._migrate({"llm": {"enabled": False}})["llm"]["enabled"], None, fails)
    check("миграция одноразовая: выключил человек - оставляем",
          config._migrate({"llm": {"enabled": False, "llm_auto_v2": True}})["llm"]["enabled"],
          False, fails)
    check("включённое не трогаем",
          config._migrate({"llm": {"enabled": True}})["llm"]["enabled"], True, fails)

    print(f"\n{'ОК' if not fails else 'ПРОВАЛЕНО: ' + ', '.join(fails)}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
