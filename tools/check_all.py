"""Одна команда вместо восьми: всё, чем проверяется переезд визуала.

Зачем. В `PLAN.md` раздел «Проверка» - это восемь команд, и половина из них
появляется по ходу фаз. Гонять их поимённо на каждом шаге никто не будет, а
не гонять - значит узнавать о поломке через фазу.

Главное правило здесь - **пропущенное называется вслух**. Проверка, которой
ещё нет, печатается отдельной строкой «нет такого файла», а не молча
исчезает из отчёта: иначе зелёный итог на трёх пройденных проверках выглядит
ровно как зелёный итог на одиннадцати.

    python tools/check_all.py           # всё, что есть
    python tools/check_all.py --fast    # без сборки web, секунды
"""

import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Быстрые тесты логики. Переезд визуала их не касается, и покраснеть они не
# должны ни на одной фазе - в этом и смысл: если покраснели, тронуто не то.
TESTS = [
    "test_clean.py", "test_llm.py", "test_update.py", "test_stats.py",
    "test_clipboard.py", "test_intonation.py", "test_language.py",
    "test_stream.py", "test_theme.py", "test_e2e.py", "test_backup.py",
    "test_bridge.py",
]

# Генераторы: сгенерированное не должно расходиться с источником. Каждый умеет
# --check и падает при расхождении - иначе CSS и api.ts тихо устаревают.
GENERATED = [
    ("tools/gen_theme.py", ["--check"], "CSS против theme.py"),
    ("tools/gen_bridge.py", ["--check"], "api.ts против Backend"),
    ("tools/check_icons.py", [], "иконки против Icons.qml"),
    ("tools/check_i18n.py", [], "непереведённые строки"),
    ("tools/probe_mac_import.py", [], "импорт прошёл бы и на macOS"),
]


def run(cmd: list, cwd: str = ROOT, timeout: int = 600) -> tuple:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    t = time.perf_counter()
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        return r.returncode, (r.stdout + r.stderr), time.perf_counter() - t
    except subprocess.TimeoutExpired:
        return 1, f"не уложилось в {timeout} с", time.perf_counter() - t
    except Exception as e:  # noqa: BLE001
        return 1, f"{type(e).__name__}: {e}", time.perf_counter() - t


def main() -> int:
    fast = "--fast" in sys.argv
    rows, skipped = [], []

    print("тесты логики")
    for t in TESTS:
        if not os.path.exists(os.path.join(ROOT, t)):
            skipped.append((t, "нет такого файла"))
            continue
        code, out, sec = run([sys.executable, t])
        rows.append((t, code == 0, sec, out))
        print(f"  {'ок ' if code == 0 else 'СБОЙ'}  {t:22s} {sec:5.1f} с")

    print("\nсгенерированное против источника")
    for script, args, what in GENERATED:
        if not os.path.exists(os.path.join(ROOT, script)):
            skipped.append((script, "нет такого файла"))
            continue
        code, out, sec = run([sys.executable, script] + args)
        rows.append((script, code == 0, sec, out))
        print(f"  {'ок ' if code == 0 else 'СБОЙ'}  {what:34s} {sec:5.1f} с")

    web = os.path.join(ROOT, "web")
    if not os.path.exists(os.path.join(web, "package.json")):
        skipped.append(("web/", "каркас ещё не заведён"))
    elif fast:
        skipped.append(("web/", "пропущено ключом --fast"))
    elif shutil.which("npm") is None:
        skipped.append(("web/", "npm не найден"))
    else:
        print("\nweb")
        # Полный путь от which, а не голое «npm»: на Windows это npm.cmd, и
        # subprocess без shell его не находит - падает с «не удаётся найти
        # указанный файл», хотя which выше только что его нашёл.
        npm = shutil.which("npm")
        for name, cmd in (("сборка", [npm, "run", "build"]),
                          ("тесты", [npm, "run", "test"])):
            code, out, sec = run(cmd, cwd=web)
            rows.append((f"web {name}", code == 0, sec, out))
            print(f"  {'ок ' if code == 0 else 'СБОЙ'}  {name:34s} {sec:5.1f} с")

    bad = [r for r in rows if not r[1]]
    print("\n" + "=" * 62)
    print(f"пройдено {len(rows) - len(bad)} из {len(rows)}")
    if skipped:
        # Именно здесь, а не в тишине: зелёный итог на трёх проверках нельзя
        # путать с зелёным итогом на одиннадцати.
        print(f"НЕ ПРОВЕРЕНО ({len(skipped)}):")
        for name, why in skipped:
            print(f"    {name:24s} - {why}")
    for name, _ok, _sec, out in bad:
        print(f"\n--- {name} ---")
        print("\n".join(out.strip().splitlines()[-25:]))
    print("=" * 62)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
