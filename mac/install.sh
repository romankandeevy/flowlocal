#!/bin/bash
# Установка FlowLocal одной командой - для человека без Xcode и опыта в
# терминале. Собирает нативно на ЕГО Маке (не переносит чужой бинарник):
# так не упирается в архитектуру (Intel/Apple Silicon) и не ловит Gatekeeper
# "приложение повреждено" - файл, собранный локально, не помечен карантином
# в отличие от скачанного .dmg.
#
# Запуск (одной строкой, из Terminal.app - Command+Пробел, набрать Terminal):
#
#   curl -fsSL https://raw.githubusercontent.com/romankandeevy/flowlocal/main/mac/install.sh | bash
#
set -euo pipefail

DEST="$HOME/FlowLocal"
REPO="https://github.com/romankandeevy/flowlocal.git"

echo "== FlowLocal: установка =="

# 1. Command Line Tools - без них нет ни git, ни swiftc. Первая попытка git
#    сама покажет системное окно установки, если их ещё нет.
if ! xcode-select -p >/dev/null 2>&1; then
    echo
    echo "Нужны инструменты разработчика Apple (Command Line Tools) - без них не"
    echo "собрать приложение. Сейчас откроется системное окно установки."
    echo "Нажмите в нём «Установить», дождитесь окончания (несколько минут,"
    echo "качает Apple), затем запустите эту же команду ещё раз."
    echo
    xcode-select --install || true
    exit 1
fi

# 2. Python 3.11+ - для бэкенда распознавания. Берём то, что уже есть в
#    системе или поставлено любым способом (brew, python.org, pyenv);
#    ставить его самим - не наше дело, только проверяем и подсказываем.
PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
    echo
    echo "Нужен Python 3 - его не нашлось. Поставьте с https://www.python.org/downloads/"
    echo "(кнопка «Download Python»), затем запустите эту команду ещё раз."
    exit 1
fi
PY_OK="$("$PY" -c 'import sys; print(1 if sys.version_info >= (3, 11) else 0)')"
if [ "$PY_OK" != "1" ]; then
    echo
    echo "Найден Python $("$PY" --version 2>&1), а нужен 3.11 или новее."
    echo "Поставьте свежий с https://www.python.org/downloads/ и повторите команду."
    exit 1
fi
echo "== Python: $("$PY" --version 2>&1) =="

# 3. Код - клонируем, если ещё нет, иначе подтягиваем свежее.
if [ -d "$DEST/.git" ]; then
    echo "== обновляю код в $DEST =="
    git -C "$DEST" pull --ff-only
else
    echo "== скачиваю код в $DEST =="
    git clone --depth 1 "$REPO" "$DEST"
fi

# 4. Сборка. build.sh сам заведёт venv бэкенда при первом запуске и соберёт
#    .app - переменной PYTHON подсказываем ему тот python3, что нашли выше.
echo "== собираю (несколько минут при первом разе - тянет модели распознавания) =="
cd "$DEST/mac"
PYTHON="$PY" ./build.sh

# 5. В Программы и запуск.
APP="$DEST/mac/build/FlowLocal.app"
rm -rf "/Applications/FlowLocal.app"
cp -R "$APP" /Applications/
echo "== готово: /Applications/FlowLocal.app =="
open "/Applications/FlowLocal.app"
