"""Собрать FlowLocal.app под macOS - ЗАГОТОВКА.

    python3 tools/build_mac.py

ЧЕСТНО: сегодня это не работает и работать не может. Приложение насквозь
Windows-специфично (winreg, ctypes.WinDLL, keyboard, win32*), `import app` на
macOS падает - разбор в docs/macos-port-audit.md. Любой упаковщик, который
трассирует импорты (pyside6-deploy на Nuitka, py2app, PyInstaller), споткнётся
на том же самом. Скрипт всё равно нужен: он даёт единую точку сборки для
CI (.github/workflows/build.yml, macOS-job) и место, куда по мере порта ляжет
рабочий рецепт вместо заглушки. Пока порт не сделан, скрипт пробует собрать,
честно сообщает, где встал, и возвращает ненулевой код - job это ожидает
(continue-on-error).

Почему pyside6-deploy, а не py2app. pyside6-deploy - штатный инструмент PySide6:
он знает про QML, плагины Qt и rpath, и не тянет отдельной возни с рецептами,
как py2app. Обратная сторона - Nuitka под капотом компилирует всё, включая
onnxruntime, и это ставит тот же лицензионный вопрос про LGPL §4(d), что и
onefile на Windows (см. tools/build.py и licenses/README.txt): Qt нельзя
запечатывать так, чтобы его нельзя было подменить. Прежде чем делать это
основным способом раздачи - решить лицензионный вопрос, а не считать мегабайты.
Для «собрать .app и проверить вид на своём Маке» (самоподпись, $0) это не
блокер: раздачи нет, есть проверка.

Что ещё предстоит вписать сюда, когда порт дойдёт (в docs/macos-port-audit.md
подробно):
  - данные: assets/fonts, qml/ целиком, config.example.json, CHANGELOG.md,
    docs/history-0.x.md - ровно те же, что в flowlocal.spec (datas);
  - Info.plist: NSMicrophoneUsageDescription (иначе микрофон молча не дадут),
    LSUIElement=1 (жить в menu bar, без иконки в доке);
  - подпись: codesign самоподписанным сертификатом (см. probe_mac.py tcc),
    без неё Accessibility/Input Monitoring слетают на каждой пересборке.
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, "app.py")
DIST = os.path.join(ROOT, "dist")


def main() -> int:
    if sys.platform != "darwin":
        print("Этот скрипт собирает .app и запускается ТОЛЬКО на macOS.")
        print("Здесь -", sys.platform, "- нечего собирать. Windows-сборка:")
        print("  python tools/build.py cpu --installer")
        return 2

    # Предупреждаем заранее и по делу: пока приложение не импортируется, дальше
    # можно не ходить - любой упаковщик упрётся в тот же импорт.
    probe = subprocess.run([sys.executable, "-c", "import app"],
                           cwd=ROOT, capture_output=True, text=True)
    if probe.returncode != 0:
        tail = (probe.stderr.strip().splitlines() or ["<пусто>"])[-1]
        print("ЗАГОТОВКА: `import app` пока падает - порт не сделан.")
        print(f"  споткнулось на: {tail}")
        print("  что и чем чинить - docs/macos-port-audit.md, раздел A.")
        print("  Пробую упаковщик всё равно, чтобы проверить, что он вообще ставится…")

    os.makedirs(DIST, exist_ok=True)

    # pyside6-deploy идёт вместе с PySide6 (модуль, не отдельный пакет). Зовём
    # его как модуль, чтобы не зависеть от того, попал ли он на PATH.
    #   -f  - не спрашивать, перезаписать спеку (в CI интерактива нет);
    #   -c  - файл спеки рядом с проектом (создастся при первом запуске).
    cmd = [sys.executable, "-m", "PySide6.scripts.deploy", MAIN, "-f",
           "-c", os.path.join(ROOT, "pysidedeploy.spec")]
    print("сборка .app …", " ".join(cmd), sep="\n  ")
    try:
        rc = subprocess.call(cmd, cwd=ROOT)
    except FileNotFoundError:
        print("\nНЕ вышло: pyside6-deploy недоступен. Поставьте PySide6 с deploy:")
        print("  pip install PySide6 nuitka")
        return 1

    app = os.path.join(ROOT, "app.app")   # deploy кладёт рядом с main-файлом
    if rc == 0 and os.path.isdir(app):
        dmg = os.path.join(DIST, "FlowLocal-macos.dmg")
        print(f"\nготово (сырой каркас): {app}")
        print("  перенесите/подпишите и заверните в dmg - это делает CI, либо:")
        print(f"  hdiutil create -srcfolder {app} {dmg}")
        return 0

    print(f"\nупаковщик вернул {rc}, .app не собран.")
    print("Это ОЖИДАЕМО, пока не сделан порт (docs/macos-port-audit.md).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
