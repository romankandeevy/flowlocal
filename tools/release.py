"""Выложить сборку в GitHub Releases - отсюда её возьмёт обновлятор.

    python tools/build.py cpu --installer     # сперва собрать
    python tools/release.py                   # потом выложить
    python tools/release.py --notes "Что нового"

Версия берётся из version.py и нигде больше не пишется. Тег - v{версия}.

Почему GitHub Releases, а не своё хранилище: обновлятор (updater.py) ходит в
/releases/latest, TLS и подпись коммитов уже есть, платить и настраивать нечего.

Проверки перед выкладкой - не бюрократия. Выложить релиз с версией, которая уже
есть, или с несобранным установщиком - значит сломать обновление у всех, кто
его нажмёт, а откатить релиз задним числом нельзя: кто-то успеет скачать.
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from version import GITHUB_REPO, __version__  # noqa: E402

TAG = f"v{__version__}"
SETUP = os.path.join(ROOT, "dist", f"FlowLocal-{__version__}-setup.exe")


def gh() -> str:
    for p in (r"C:\Program Files\GitHub CLI\gh.exe",
              r"C:\Program Files (x86)\GitHub CLI\gh.exe"):
        if os.path.exists(p):
            return p
    return shutil.which("gh") or ""


def run(args: list, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def main() -> int:
    # Заметки берём из CHANGELOG.md - там же, откуда их показывает окно
    # «О программе». Пока они писались ключом --notes, они жили ровно один раз,
    # в истории команд: приложение о них не знало, а человек, обновившийся
    # неделю назад, не мог посмотреть, что было в промежуточных версиях.
    # --notes оставлен, чтобы можно было перебить руками.
    import changelog

    notes = changelog.notes_for(__version__)
    if "--notes" in sys.argv:
        notes = sys.argv[sys.argv.index("--notes") + 1]
    elif not notes:
        print(f"в CHANGELOG.md нет раздела «## {__version__} — дата» - "
              f"допишите его или передайте --notes")
        return 2

    cli = gh()
    if not cli:
        print("gh не найден: winget install GitHub.cli")
        return 2
    if not os.path.exists(SETUP):
        print(f"нет установщика: {os.path.relpath(SETUP, ROOT)}")
        print("сперва: python tools/build.py cpu --installer")
        return 2

    # Тег уже есть - значит эту версию уже выкладывали. Молча перезаписать
    # нельзя: кто-то мог её скачать, и «та же версия, но другая» - худший сорт
    # неразберихи. Поднимите версию в version.py.
    if run([cli, "release", "view", TAG, "--repo", GITHUB_REPO]).returncode == 0:
        print(f"релиз {TAG} уже существует.")
        print("Поднимите версию в version.py, пересоберите и повторите.")
        return 1

    # Незакоммиченное - это сборка не из того, что лежит в репозитории. Потом
    # не восстановить, из чего собран выложенный .exe.
    dirty = run(["git", "status", "--porcelain"]).stdout.strip()
    if dirty:
        print("в рабочем дереве есть незакоммиченное - выкладывать нельзя:")
        print("\n".join("  " + line for line in dirty.splitlines()[:10]))
        print("иначе не восстановить, из чего собран выложенный установщик.")
        return 1

    size = os.path.getsize(SETUP) / 1e6
    print(f"выкладываю {TAG}: {os.path.basename(SETUP)} ({size:.0f} МБ)")
    r = run([cli, "release", "create", TAG, SETUP,
             "--repo", GITHUB_REPO,
             "--title", f"FlowLocal {__version__}",
             "--notes", notes or f"FlowLocal {__version__}",
             "--latest"])
    if r.returncode != 0:
        print("ПРОВАЛ:", (r.stderr or r.stdout).strip()[:400])
        return 1
    print(r.stdout.strip())
    print("\nОбновлятор увидит это на следующем запуске тех, у кого версия ниже.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
