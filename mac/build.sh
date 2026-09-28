#!/bin/bash
# Сборка FlowLocal.app. Работает на любом Маке и из любой папки: ни одного
# абсолютного пути в сборке, всё машинное - в данных пользователя.
#
#   ./build.sh          собрать mac/build/FlowLocal.app
#   ./build.sh run      собрать и запустить
#   ./build.sh install  собрать, положить в /Applications и запустить оттуда
#
# Что где (см. Sources/FlowLocal/Paths.swift):
#   build/FlowLocal.app                          приложение, бэкенд внутри
#   ~/Library/Application Support/FlowLocal/     Python/ - окружение бэкенда,
#                                                Models/, Recordings/
#
# Переменные: PYTHON - какой python3 взять для окружения; SWIFT_OPT=-Onone -
# быстрая отладочная сборка; DEVELOPER_DIR - какой Xcode/CLT использовать.
set -euo pipefail
cd "$(dirname "$0")"
HERE="$(pwd)"
APP="$HERE/build/FlowLocal.app"
SUPPORT="$HOME/Library/Application Support/FlowLocal"
VENV="$SUPPORT/Python"

say() { printf '==> %s\n' "$*"; }
die() { printf '\n!!! %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- тулчейн
# На свежих SDK (macOS 15+) @State в SwiftUI - макрос, и его плагин
# (libSwiftUIMacros) есть только в Xcode, в Command Line Tools его нет. Есть
# Xcode - собираем им, даже если xcode-select смотрит на CLT. Нет - CLT:
# на SDK постарше их хватает.
if [ -z "${DEVELOPER_DIR:-}" ]; then
    CUR="$(xcode-select -p 2>/dev/null || true)"
    if [ -z "$CUR" ]; then
        die "Нет инструментов разработчика Apple. Выполните: xcode-select --install"
    fi
    if [[ "$CUR" != *Xcode*.app* ]]; then
        for X in /Applications/Xcode.app /Applications/Xcode*.app; do
            if [ -d "$X/Contents/Developer" ]; then
                export DEVELOPER_DIR="$X/Contents/Developer"
                break
            fi
        done
    fi
fi
SDK="$(xcrun --sdk macosx --show-sdk-path)"
say "тулчейн: ${DEVELOPER_DIR:-$(xcode-select -p)}"

# ------------------------------------------------------------- python 3.11+
# onnxruntime 1.23.2 - последняя ветка с колесом под Intel Mac и ещё до
# замедления int8 в 1.25 (см. old/requirements.txt); колёса у неё - для
# Python 3.10-3.13. Берём самый свежий подходящий из того, что есть.
py_ok() {
    [ -x "$1" ] && "$1" -c 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 13) else 1)' 2>/dev/null
}
find_python() {
    local c
    if [ -n "${PYTHON:-}" ]; then
        py_ok "$PYTHON" && { echo "$PYTHON"; return; }
        die "PYTHON=$PYTHON не подходит: нужен Python 3.11-3.13"
    fi
    for v in 3.13 3.12 3.11; do
        for c in \
            "$(command -v "python$v" 2>/dev/null || true)" \
            "/opt/homebrew/opt/python@$v/bin/python$v" \
            "/usr/local/opt/python@$v/bin/python$v" \
            "/Library/Frameworks/Python.framework/Versions/$v/bin/python$v" \
            $(ls -d "$HOME"/.pyenv/versions/$v*/bin/python$v 2>/dev/null | sort -r) ; do
            [ -n "$c" ] && py_ok "$c" && { echo "$c"; return; }
        done
    done
    c="$(command -v python3 2>/dev/null || true)"
    [ -n "$c" ] && py_ok "$c" && { echo "$c"; return; }
    return 1
}

# Окружение годное, если его python запускается и видит зависимости нужных
# версий. Скопированное с другого Мака (ссылки на чужой pyenv) или после
# обновления Python - негодное, заводим заново.
REQ="$HERE/backend/requirements.txt"
STAMP="$VENV/.flowlocal-requirements"
venv_ok() {
    [ -x "$VENV/bin/python3" ] &&
        cmp -s "$REQ" "$STAMP" &&
        "$VENV/bin/python3" -c 'import onnxruntime, onnx_asr, numpy' 2>/dev/null
}

if ! venv_ok; then
    PY="$(find_python || true)"
    if [ -z "$PY" ] && command -v brew >/dev/null 2>&1; then
        say "подходящего Python нет - ставлю python@3.13 через Homebrew"
        brew install python@3.13
        PY="$(find_python || true)"
    fi
    [ -n "$PY" ] || die "Нужен Python 3.11-3.13 (есть: $(python3 --version 2>&1 || echo нет)).
    Поставьте: brew install python@3.13  или  https://www.python.org/downloads/
    и повторите ./build.sh (или укажите PYTHON=/путь/к/python3)."
    say "окружение бэкенда: $("$PY" --version 2>&1) -> $VENV"
    rm -rf "$VENV"
    mkdir -p "$SUPPORT"
    "$PY" -m venv "$VENV"
    "$VENV/bin/python3" -m pip install -q --disable-pip-version-check --upgrade pip
    "$VENV/bin/python3" -m pip install -q --disable-pip-version-check -r "$REQ"
    cp "$REQ" "$STAMP"
fi

# Модели раньше лежали в mac/backend/models - переносим, а не качаем заново.
if [ -d "$HERE/backend/models" ] && [ ! -e "$SUPPORT/Models" ]; then
    say "переношу скачанные модели в $SUPPORT/Models"
    mkdir -p "$SUPPORT"
    mv "$HERE/backend/models" "$SUPPORT/Models"
fi

# ------------------------------------------------------------------- swiftc
# Прямой swiftc, без SwiftPM: на Command Line Tools 16.2 под macOS 14 манифест
# Package.swift не линкуется вовсе (в libPackageDescription нет Package.init,
# на который он ссылается).
say "swiftc"
mkdir -p "$HERE/build"

# Command Line Tools, обновлённые поверх старой версии, оставляют лишний
# usr/include/swift/module.modulemap (его нет в квитанциях установщика - это
# остаток CLT 2023 года). Он второй раз определяет SwiftBridging, и из-за этого
# не собираются CoreFoundation, а за ним Foundation, AppKit и SwiftUI; без них
# компилятор часами перебирает типы нашего кода. Системные файлы не трогаем -
# прячем дубль VFS-оверлеем только для этой сборки.
CLT_SWIFT_INC="/Library/Developer/CommandLineTools/usr/include/swift"
OVERLAY=()
rm -f "$HERE/build/clt-overlay.yaml" "$HERE/build/empty.modulemap"
if [ -z "${DEVELOPER_DIR:-}" ] && [ -f "$CLT_SWIFT_INC/module.modulemap" ] && [ -f "$CLT_SWIFT_INC/bridging.modulemap" ]; then
    printf '// пусто: скрывает устаревший дубль SwiftBridging\n' > "$HERE/build/empty.modulemap"
    cat > "$HERE/build/clt-overlay.yaml" <<EOF
{"version": 0, "case-sensitive": "false", "roots": [
  {"type": "directory", "name": "$CLT_SWIFT_INC",
   "contents": [{"type": "file", "name": "module.modulemap", "external-contents": "$HERE/build/empty.modulemap"}]}
]}
EOF
    OVERLAY=(-vfsoverlay "$HERE/build/clt-overlay.yaml" -Xcc -ivfsoverlay -Xcc "$HERE/build/clt-overlay.yaml")
fi

# ${OVERLAY[@]+...} - потому что bash 3.2 из macOS с set -u падает на пустом массиве.
# -O по умолчанию: на двухъядерном Intel интерфейс без оптимизации заметно
# тяжелее. Архитектура - та, на которой собираем (Intel или Apple Silicon).
SWIFT_LOG="$HERE/build/swiftc.log"
if ! xcrun swiftc ${SWIFT_OPT:--O} -swift-version 5 -target "$(uname -m)-apple-macos14.0" \
    -sdk "$SDK" ${OVERLAY[@]+"${OVERLAY[@]}"} \
    Sources/FlowLocal/*.swift -o "$HERE/build/FlowLocal" \
    -framework AppKit -framework AVFoundation -framework Carbon -framework ApplicationServices \
    2> >(tee "$SWIFT_LOG" >&2); then
    if grep -q "SwiftUIMacros" "$SWIFT_LOG"; then
        die "SDK этой macOS требует плагин макросов SwiftUI, а он есть только в Xcode.
    Поставьте Xcode из App Store (запускать не обязательно) и повторите ./build.sh."
    fi
    die "swiftc не собрал приложение - ошибки выше и в $SWIFT_LOG"
fi

say "$APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/backend"
cp "$HERE/build/FlowLocal" "$APP/Contents/MacOS/FlowLocal"
cp Resources/Info.plist "$APP/Contents/Info.plist"
# Бэкенд едет внутри приложения - .app самодостаточен, репозиторий можно
# двигать и удалять.
cp backend/server.py backend/langdetect.py backend/requirements.txt "$APP/Contents/Resources/backend/"
# Локализация ru: меню «Правка», «Окно», «Службы», «Завершить», поле поиска и
# «Отменить удаление…» macOS подписывает по-русски, в тон нашим строкам.
mkdir -p "$APP/Contents/Resources/ru.lproj"
# Шрифты - системные SF Pro и SF Mono, своих файлов в сборке нет.
# Иконка - Resources/AppIcon.icns (рисует tools/make_icon.py); нет её -
# старый значок из old/.
if [ -f Resources/AppIcon.icns ]; then
    cp Resources/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"
    /usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string AppIcon" "$APP/Contents/Info.plist"
elif sips -s format icns ../old/assets/FlowLocal.ico --out "$APP/Contents/Resources/AppIcon.icns" >/dev/null 2>&1; then
    /usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string AppIcon" "$APP/Contents/Info.plist"
fi

# Подпись. Ad-hoc привязывает права к хэшу бинарника, и после каждой пересборки
# «Универсальный доступ» перестаёт действовать. Постоянный сертификат это
# снимает: права привязываются к нему, а не к хэшу. Завести один раз руками -
# «Связка ключей» -> Ассистент сертификации -> Создать сертификат, имя
# «FlowLocal Dev», тип «Самоподписанный корневой», тип сертификата «Подпись
# кода». Нет сертификата - подписываем ad-hoc, как раньше.
# Годится и общий сертификат разработки «Local Dev Signing», если он уже
# есть в связке: право тоже привязывается к нему, а не к хэшу.
SIGN_ID="-"
for CERT in "FlowLocal Dev" "Local Dev Signing"; do
    if security find-identity -v -p codesigning 2>/dev/null | grep -q "\"$CERT\""; then
        SIGN_ID="$CERT"
        break
    fi
done
say "подпись: $([ "$SIGN_ID" = "-" ] && echo "ad-hoc (права сбрасываются при пересборке)" || echo "$SIGN_ID")"
codesign --force --deep --sign "$SIGN_ID" "$APP"
say "готово: $APP"

stop_running() {
    # Дождаться, пока старый экземпляр действительно выйдет: open, запущенный
    # раньше, получает от LaunchServices procNotFound (-600) и не открывает ничего.
    if pkill -x FlowLocal 2>/dev/null; then
        for _ in $(seq 1 50); do pgrep -x FlowLocal >/dev/null || break; sleep 0.1; done
    fi
}

case "${1:-}" in
run)
    stop_running
    open "$APP"
    ;;
install)
    # Постоянная установка: приложение живёт в «Программах», а не в папке
    # сборки - Spotlight, Launchpad, Док и «Открывать при входе» видят его там.
    # /Applications обычно доступна владельцу Мака без sudo; нет - ~/Applications.
    DEST_DIR="/Applications"
    [ -w "$DEST_DIR" ] || { DEST_DIR="$HOME/Applications"; mkdir -p "$DEST_DIR"; }
    stop_running
    rm -rf "$DEST_DIR/FlowLocal.app"
    cp -R "$APP" "$DEST_DIR/"
    say "установлено: $DEST_DIR/FlowLocal.app"
    open "$DEST_DIR/FlowLocal.app"
    ;;
esac
