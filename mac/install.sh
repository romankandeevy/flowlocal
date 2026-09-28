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

# 2. Python для бэкенда распознавания ищет и заводит build.sh: берёт 3.11-3.13
#    из системы (brew, python.org, pyenv), а если такого нет и есть Homebrew -
#    ставит python@3.13 сам. Нет ни того, ни другого - скажет, что поставить.

# 3. Код - клонируем, если ещё нет, иначе подтягиваем свежее.
if [ -d "$DEST/.git" ]; then
    echo "== обновляю код в $DEST =="
    git -C "$DEST" pull --ff-only
else
    echo "== скачиваю код в $DEST =="
    git clone --depth 1 "$REPO" "$DEST"
fi

# 4. Сборка. build.sh заводит окружение бэкенда в ~/Library/Application
#    Support/FlowLocal (своё на этом Маке) и собирает самодостаточный .app.
echo "== собираю (несколько минут при первом разе) =="
cd "$DEST/mac"
./build.sh install

# 5. В Программы и запуск - это делает сам build.sh.
