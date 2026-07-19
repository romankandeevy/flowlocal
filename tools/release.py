"""Выложить сборку в GitHub Releases - отсюда её возьмёт обновлятор.

    python tools/build.py cpu --installer     # сперва собрать
    python tools/release.py                   # потом выложить
    python tools/release.py --otp 123456      # если npm просит код (2FA)
    python tools/release.py --npm-only        # дослать пакет, не выпуская
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


def npm_version(v: str = __version__) -> str:
    """Наша версия -> версия для npm. «1.0» -> «1.0.0».

    Реестр npm принимает только semver, то есть ровно три числа: «1.0» он
    отвергает с `Invalid version`. Своя схема из двух чисел (см. version.py)
    в это не укладывается, поэтому недостающие нули дописываем здесь и только
    здесь - наружу трёхчисленная форма не показывается нигде, кроме
    package.json.

    Обратное преобразование не нужно и не делается: npm у нас витрина, а не
    источник правды о версии.
    """
    parts = [p for p in str(v).split(".") if p.isdigit()]
    while len(parts) < 3:
        parts.append("0")
    return ".".join(parts[:3])


def git() -> str:
    return shutil.which("git") or "git"


def gh() -> str:
    for p in (r"C:\Program Files\GitHub CLI\gh.exe",
              r"C:\Program Files (x86)\GitHub CLI\gh.exe"):
        if os.path.exists(p):
            return p
    return shutil.which("gh") or ""


def run(args: list, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def arg(name: str) -> str:
    return (sys.argv[sys.argv.index(name) + 1]
            if name in sys.argv and len(sys.argv) > sys.argv.index(name) + 1
            else "")


def main() -> int:
    otp = arg("--otp")

    # Догнать реестр, не выпуская ничего: релиз уже создан, а пакет не уехал.
    # Без этого режима единственным способом дослать пакет было выпустить
    # версию заново - то есть выпустить лишнюю версию ради витрины.
    if "--npm-only" in sys.argv:
        return 0 if publish_npm(otp) else 1

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

    # Версия пакета npm - за версией программы. Разъедься они, и `npx flowlocal`
    # стал бы обещать одно, а ставить другое. Правим до выкладки, чтобы правка
    # уехала тем же коммитом.
    npm_pkg = os.path.join(ROOT, "npm", "package.json")
    if os.path.exists(npm_pkg):
        import json as _json

        with open(npm_pkg, encoding="utf-8") as f:
            pkg = _json.load(f)
        if pkg.get("version") != npm_version():
            pkg["version"] = npm_version()
            with open(npm_pkg, "w", encoding="utf-8") as f:
                _json.dump(pkg, f, ensure_ascii=False, indent=2)
                f.write("\n")
            print(f"npm/package.json: версия -> {npm_version()}")
            # И сразу коммитим - иначе сами себе устроим грязное дерево, на
            # котором проверка ниже откажется выкладывать. Ровно это и вышло
            # при первом выпуске: скрипт правил файл и тут же на него ругался.
            #
            # Коммитим ТОЛЬКО этот файл и только когда правка наша: чужие
            # изменения так проскочить не могут, проверка их всё равно поймает.
            run([git(), "add", "npm/package.json"], cwd=ROOT)
            run([git(), "commit", "-m", f"npm: версия {npm_version()}",
                 "--only", "npm/package.json"], cwd=ROOT)

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

    # Про код подтверждения говорим ДО выкладки. После неё поздно: релиз уже
    # создан, а человек уже ушёл считать дело сделанным.
    if not otp and npm_needs_otp():
        print("предупреждение: npm попросит код подтверждения, а вводить его")
        print("некуда - пакет не опубликуется. Прервите (Ctrl+C) и повторите с")
        print("`--otp 123456`, либо дошлите потом: `--npm-only --otp 123456`.")

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
    ok_npm = publish_npm(otp)
    print("\nОбновлятор увидит это на следующем запуске тех, у кого версия ниже.")
    if not ok_npm:
        print("npm отстал - дошлите: python tools/release.py --npm-only --otp 123456")
    return 0


PACKAGE = "@usekorti/flowlocal"


def _npm() -> str:
    return shutil.which("npm") or shutil.which("npm.cmd") or ""


def npm_needs_otp() -> bool:
    """Требует ли учётка одноразовый код на публикацию.

    Это и есть причина, по которой пакет отстал на четыре выпуска. У учётки
    стоит `two-factor auth: auth-and-writes`, то есть npm просит шестизначный
    код при КАЖДОЙ публикации. Скрипт запускает npm без терминала, ввести код
    некуда - publish падает, а сообщение об этом тонуло последней строкой
    длинного вывода. Релиз при этом создавался, и всё выглядело успешным.

    Спрашиваем ДО выкладки, чтобы сказать про код заранее, а не после.
    """
    npm = _npm()
    if not npm:
        return False
    p = run([npm, "profile", "get"], cwd=os.path.join(ROOT, "npm"))
    return "auth-and-writes" in (p.stdout or "")


def npm_published(version: str) -> bool:
    """Лежит ли эта версия в реестре. Спрашиваем реестр, а не свой код возврата.

    Проверка появилась потому, что «publish отработал» и «версия в реестре»
    оказались разными событиями: код возврата был нулевым, а версии не было.
    Правду знает только реестр, и стоит она один запрос.
    """
    npm = _npm()
    if not npm:
        return False
    r = run([npm, "view", f"{PACKAGE}@{version}", "version"],
            cwd=os.path.join(ROOT, "npm"))
    return r.returncode == 0 and version in (r.stdout or "")


def publish_npm(otp: str = "") -> bool:
    """Выложить пакет в npm той же версией. Возвращает: лежит ли он там теперь.

    Зачем в этом скрипте, а не руками. Версию в npm/package.json мы правим
    выше, но пакет никто не публиковал - и он отстал: в реестре лежали 0.15.0 и
    0.17.0, когда программа была уже 0.21.0. Человек, набравший
    `npx @usekorti/flowlocal`, получал позавчерашний установщик и не знал об этом.

    Провал публикации НЕ роняет выпуск: релиз на GitHub уже создан, установщик
    уже лежит, обновлятор уже его видит. npm - витрина, а не путь доставки. Но
    молчать о провале мы больше не будем: ровно из-за молчания он и повторился
    четыре раза подряд.

    Первая публикация пакета с областью (@usekorti/...) требует --access public:
    иначе npm считает его закрытым и просит платную подписку.
    """
    ver = npm_version()
    pkg = os.path.join(ROOT, "npm")
    if not os.path.exists(os.path.join(pkg, "package.json")):
        return True
    npm = _npm()
    if not npm:
        print("npm не найден - пакет не опубликован (это не мешает выпуску)")
        return False

    if npm_published(ver):
        print(f"npm: {ver} уже в реестре - публиковать нечего")
        return True

    who = run([npm, "whoami"], cwd=pkg)
    if who.returncode != 0:
        print("npm: не выполнен вход (`npm login`) - пакет не опубликован")
        return False

    cmd = [npm, "publish", "--access", "public"]
    if otp:
        cmd += ["--otp", otp]
    r = run(cmd, cwd=pkg)
    # Спрашиваем реестр, а не верим коду возврата: см. npm_published.
    if npm_published(ver):
        print(f"npm: опубликован {PACKAGE} {ver} (от имени {who.stdout.strip()})")
        return True

    out = ((r.stderr or "") + (r.stdout or "")).strip()
    low = out.lower()
    print()
    print("!" * 68)
    print(f"npm: пакет НЕ опубликован. В реестре по-прежнему нет {ver}.")
    if "otp" in low or "one-time" in low or "eotp" in low or npm_needs_otp():
        print()
        print("Причина: у учётки включён код подтверждения на публикацию")
        print("(two-factor auth: auth-and-writes). Ввести его скрипту некуда.")
        print()
        print("Дальше два пути, оба делаются один раз:")
        print(f"  1) повторить с кодом:  python tools/release.py --npm-only --otp 123456")
        print("  2) убрать код из уравнения навсегда - завести токен автоматизации:")
        print("     npmjs.com -> Access Tokens -> Generate -> Automation,")
        print("     затем `npm config set //registry.npmjs.org/:_authToken <токен>`.")
        print("     Токен автоматизации обходит 2FA намеренно, для таких скриптов.")
    elif "auth" in low or "eneedauth" in low:
        print("Причина: нужен вход. В папке npm/: `npm login` (откроется браузер),")
        print("потом `python tools/release.py --npm-only`.")
    else:
        print("Причина (последняя строка вывода npm):")
        print("  " + (out.splitlines()[-1][:200] if out else "(без вывода)"))
    print()
    print("Выпуск это НЕ отменяет: релиз на GitHub создан, обновлятор его видит.")
    print("Отстанет только `npx` - он принесёт установщик прошлой версии.")
    print("!" * 68)
    return False


if __name__ == "__main__":
    sys.exit(main())
