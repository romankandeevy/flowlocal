"""Выгрузка и загрузка личного: что переносится, что нет, что не затирается.

Главная ловушка здесь - затирание. Человек грузит выгрузку не на чистую машину,
а поверх того, чем уже пользуется. Потерять его сегодняшний словарь, влив
вчерашнюю копию, нечем отменить.

    $env:PYTHONIOENCODING="utf-8"
    python test_backup.py
"""

import json
import os
import sys
import tempfile

import backup


def check(name, got, want, fails):
    ok = got == want
    print(f"  {'OK ' if ok else 'НЕТ'} {name}")
    if not ok:
        print(f"      ждали: {want}")
        print(f"      вышло: {got}")
        fails.append(name)


def main() -> int:
    fails: list = []
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "flowlocal-backup.json")

    cfg = {
        "dictionary": ["Соколов"],
        "snippets": {"моя почта": "a@b.ru"},
        "tone_rules": {"outlook.exe": "формально"},
        "hotkey_hold": "ctrl+shift+space",
        "theme": "dark",
        # служебное - уезжать не должно
        "onboarded": True,
        "model": "gigaam-v3-e2e-rnnt",
        "llm": {"url": "http://127.0.0.1:11434"},
    }

    print("ВЫГРУЗКА")
    backup.save(path, cfg)
    data = backup.load(path)
    check("личное уехало", data["settings"]["snippets"], {"моя почта": "a@b.ru"}, fails)
    check("служебное не уехало: onboarded",
          "onboarded" in data["settings"], False, fails)
    check("служебное не уехало: адрес Ollama",
          "llm" in data["settings"], False, fails)
    check("история без спроса не уезжает", "history" in data, False, fails)

    backup.save(path, cfg, history=[{"ts": "2026-07-18 10:00:00", "text": "тест"}])
    check("история уезжает по просьбе",
          len(backup.load(path)["history"]), 1, fails)

    print("\nЗАГРУЗКА: СЛИЯНИЕ, А НЕ ЗАТИРАНИЕ")
    mine = {
        "dictionary": ["Петров"],
        "snippets": {"адрес офиса": "Ленина 1"},
        "hotkey_hold": "ctrl+alt+d",     # своё сочетание уже назначено
    }
    added, replaced = backup.merge(mine, data)
    check("свой словарь на месте", "Петров" in mine["dictionary"], True, fails)
    check("чужой словарь добавлен", "Соколов" in mine["dictionary"], True, fails)
    check("своя подстановка цела", mine["snippets"]["адрес офиса"], "Ленина 1", fails)
    check("чужая подстановка добавлена", mine["snippets"]["моя почта"], "a@b.ru", fails)
    check("своё сочетание НЕ заменено", mine["hotkey_hold"], "ctrl+alt+d", fails)

    empty = {"hotkey_hold": ""}
    backup.merge(empty, data)
    check("пустое сочетание заполняется из файла",
          empty["hotkey_hold"], "ctrl+shift+space", fails)

    print("\nЛОВУШКИ")
    bad = os.path.join(tmp, "bad.json")
    with open(bad, "w", encoding="utf-8") as f:
        json.dump({"app": "ЧужаяПрограмма", "settings": {}}, f)
    try:
        backup.load(bad)
        check("чужой файл отвергнут", False, True, fails)
    except ValueError:
        check("чужой файл отвергнут", True, True, fails)

    future = os.path.join(tmp, "future.json")
    with open(future, "w", encoding="utf-8") as f:
        json.dump({"app": "FlowLocal", "format": 99, "settings": {}}, f)
    try:
        backup.load(future)
        check("файл из будущего отвергнут", False, True, fails)
    except ValueError:
        check("файл из будущего отвергнут", True, True, fails)

    broken = os.path.join(tmp, "broken.json")
    with open(broken, "w", encoding="utf-8") as f:
        f.write("{это не json")
    try:
        backup.load(broken)
        check("битый файл отвергнут", False, True, fails)
    except (ValueError, json.JSONDecodeError):
        check("битый файл отвергнут", True, True, fails)

    print()
    print("ЗАБЫВАНИЕ СТАРОГО")
    # Удаление истории - потеря данных, и её надо проверять, а не надеяться.
    import datetime

    import app as A

    hist = os.path.join(tmp, "history.jsonl")
    today = datetime.date.today()

    def day(n):
        return (today - datetime.timedelta(days=n)).isoformat()

    rows = [f"{day(400)} 10:00:00", f"{day(200)} 10:00:00",
            f"{day(40)} 10:00:00", f"{day(2)} 10:00:00"]

    def seed():
        with open(hist, "w", encoding="utf-8") as f:
            for ts in rows:
                f.write(json.dumps({"ts": ts, "text": "тест"},
                                   ensure_ascii=False) + os.linesep)
            f.write("{битая строка" + os.linesep)

    class Fake:
        def __init__(self, days):
            self.cfg = {"history_days": days}
        _forget_old_history = A.App._forget_old_history

    A.HISTORY_PATH = hist
    # «Всегда» не трогает ничего, включая битую строку: чего не просили, того
    # не делаем. Остальные сроки её выбрасывают заодно - тащить дальше нечего.
    for days, want, why in ((0, 5, "всегда - не трогаем ничего"),
                            (365, 3, "год"), (180, 2, "полгода"), (30, 1, "месяц")):
        seed()
        Fake(days)._forget_old_history()
        with open(hist, encoding="utf-8") as f:
            left = len([ln for ln in f if ln.strip()])
        check(f"срок {why}", left, want, fails)

    print()
    if fails:
        print(f"ПРОВАЛЕНО: {len(fails)} - {', '.join(fails)}")
        return 1
    print("ОК")
    return 0


if __name__ == "__main__":
    sys.exit(main())
