"""Собрать FlowLocal — папку с .exe, чтобы «скачал и запустил», без Python.

    python tools/build.py cpu     # работает у всех. Друзьям это.
    python tools/build.py cuda    # только если стоит onnxruntime-gpu

Собираем ПАПКОЙ (onedir), а не одним файлом: Qt под LGPLv3, а §4(d) требует
оставить возможность подменить библиотеку и перелинковать приложение. В onefile
всё запечатано внутрь .exe - подменить нечего. Подробности в licenses/README.txt.

Что проверять - в tools/BUILD.md. Рецепт сборки живёт в flowlocal.spec, здесь
только обвязка: выбор варианта, чистка, проверка лицензий и отчёт о размере.
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "flowlocal.spec")

# Без этих файлов сборку раздавать нельзя - см. licenses/README.txt.
REQUIRED_LICENSES = ("LICENSE", "licenses/README.txt", "licenses/Qt-LGPLv3.txt",
                     "licenses/GPLv3.txt")


def check_licenses() -> bool:
    """Молча собрать пакет, который нельзя раздавать, - худшее из возможного:
    нарушение обнаружится уже после публикации."""
    missing = [p for p in REQUIRED_LICENSES if not os.path.exists(os.path.join(ROOT, p))]
    if missing:
        print("ПРОВАЛ: нет текстов лицензий, раздавать такую сборку нельзя:")
        for m in missing:
            print(f"  {m}")
        print("Тексты LGPL и GPL: https://www.gnu.org/licenses/")
        return False
    return True


def size_of(path: str) -> str:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return f"{total / 1024 / 1024:.0f} МБ"


def main() -> int:
    variant = (sys.argv[1] if len(sys.argv) > 1 else "cpu").lower()
    if variant not in ("cpu", "cuda"):
        print("использование: python tools/build.py cpu|cuda")
        return 2
    if not check_licenses():
        return 2

    out = os.path.join(ROOT, "dist", variant)
    work = os.path.join(ROOT, "build", variant)
    # Чистим начисто: PyInstaller переиспользует кэш анализа, и после
    # переключения cpu<->cuda в сборке остались бы библиотеки от прошлого
    # варианта - как раз тот гигабайт, ради которого всё и затевалось.
    for d in (out, work):
        shutil.rmtree(d, ignore_errors=True)

    env = dict(os.environ, FLOWLOCAL_CUDA="1" if variant == "cuda" else "0")
    cmd = [sys.executable, "-m", "PyInstaller", SPEC, "--noconfirm",
           "--distpath", out, "--workpath", work]
    print("сборка", variant, "…", " ".join(cmd), sep="\n  ")
    rc = subprocess.call(cmd, cwd=ROOT, env=env)
    if rc != 0:
        print(f"\nПРОВАЛ: PyInstaller вернул {rc}")
        return rc

    # onedir: PyInstaller кладёт всё в подпапку с именем из COLLECT
    app_dir = os.path.join(out, "FlowLocal")
    exe = os.path.join(app_dir, "FlowLocal.exe")
    if not os.path.exists(exe):
        print(f"\nПРОВАЛ: {exe} не появился")
        return 1

    # Проверяем то, что легко потерять молча: Qt должен лежать отдельными
    # файлами (иначе §4(d) нарушен), тексты лицензий - доехать в сборку, а
    # GPL-only модулей Qt в сборке быть не должно (PLAN 3).
    #
    # PyInstaller 6 кладёт всё в _internal рядом с .exe, а Qt - в _internal/PySide6.
    internal = os.path.join(app_dir, "_internal")
    qt_dir = os.path.join(internal, "PySide6")
    qt_dlls = [f for f in os.listdir(qt_dir) if f.lower().startswith("qt6")] \
        if os.path.isdir(qt_dir) else []
    gpl = [f for f in qt_dlls
           if any(k in f.lower() for k in ("graphs", "quick3d", "timeline",
                                           "qmlcompiler", "virtualkeyboard", "lottie"))]
    lic = os.path.join(internal, "licenses")
    print(f"\nготово: {exe}")
    print(f"размер dist/{variant}: {size_of(out)}")
    print(f"библиотек Qt отдельными файлами: {len(qt_dlls)} (нужны для LGPL §4(d))")
    print(f"тексты лицензий в сборке: {'да' if os.path.isdir(lic) else 'НЕТ - не раздавать!'}")
    if gpl:
        print(f"ВНИМАНИЕ: GPL-only модули Qt в сборке: {', '.join(gpl)}")
        print("  Их надо выбросить в flowlocal.spec (_QT_KEEP), иначе раздавать нельзя.")
    if variant == "cpu":
        print("Модель качается при первом запуске в models/ рядом с .exe.")
    print("Раздавать — папку целиком, а не один .exe: см. licenses/README.txt.")
    print("Проверять — на машине БЕЗ Python: см. tools/BUILD.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
