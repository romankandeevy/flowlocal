#!/bin/bash
# Сборка FlowLocal.app: Swift-приложение + ссылка на Python-бэкенд с моделями.
#
#   ./build.sh          собрать mac/build/FlowLocal.app
#   ./build.sh run      собрать и запустить
set -euo pipefail
cd "$(dirname "$0")"
HERE="$(pwd)"
BACKEND="$HERE/backend"
APP="$HERE/build/FlowLocal.app"

# Окружение бэкенда. onnxruntime 1.23.2 - последняя ветка с колесом под Intel
# Mac и ещё до замедления int8 в 1.25 (см. old/requirements.txt).
if [ ! -x "$BACKEND/.venv/bin/python" ]; then
    PY="${PYTHON:-$HOME/.pyenv/versions/3.13.15/bin/python3}"
    [ -x "$PY" ] || PY="$(command -v python3)"
    echo "==> окружение бэкенда ($PY)"
    "$PY" -m venv "$BACKEND/.venv"
    "$BACKEND/.venv/bin/python" -m pip install -q --upgrade pip
    "$BACKEND/.venv/bin/python" -m pip install -q "onnxruntime==1.23.2" "onnx-asr[hub]==0.12.0" numpy
fi

# Прямой swiftc, без SwiftPM: на Command Line Tools 16.2 под macOS 14 манифест
# Package.swift не линкуется вовсе (в libPackageDescription нет Package.init,
# на который он ссылается). Xcode не нужен.
echo "==> swiftc"
mkdir -p "$HERE/build"

# Command Line Tools, обновлённые поверх старой версии, оставляют лишний
# usr/include/swift/module.modulemap (его нет в квитанциях установщика - это
# остаток CLT 2023 года). Он второй раз определяет SwiftBridging, и из-за этого
# не собираются CoreFoundation, а за ним Foundation, AppKit и SwiftUI; без них
# компилятор часами перебирает типы нашего кода. Системные файлы не трогаем -
# прячем дубль VFS-оверлеем только для этой сборки.
CLT_SWIFT_INC="/Library/Developer/CommandLineTools/usr/include/swift"
OVERLAY=()
if [ -f "$CLT_SWIFT_INC/module.modulemap" ] && [ -f "$CLT_SWIFT_INC/bridging.modulemap" ]; then
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
# тяжелее. Для быстрой отладочной сборки: SWIFT_OPT=-Onone ./build.sh
swiftc ${SWIFT_OPT:--O} -swift-version 5 -target "$(uname -m)-apple-macos14.0" \
    -sdk "$(xcrun --show-sdk-path)" ${OVERLAY[@]+"${OVERLAY[@]}"} \
    Sources/FlowLocal/*.swift -o "$HERE/build/FlowLocal" \
    -framework AppKit -framework AVFoundation -framework Carbon -framework ApplicationServices

echo "==> $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$HERE/build/FlowLocal" "$APP/Contents/MacOS/FlowLocal"
cp Resources/Info.plist "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :FLBackendDir string $BACKEND" "$APP/Contents/Info.plist"
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
SIGN_ID="-"
if security find-certificate -c "FlowLocal Dev" >/dev/null 2>&1; then
    SIGN_ID="FlowLocal Dev"
fi
echo "==> подпись: $([ "$SIGN_ID" = "-" ] && echo "ad-hoc (права сбрасываются при пересборке)" || echo "$SIGN_ID")"
codesign --force --sign "$SIGN_ID" "$APP"
echo "==> готово: $APP"

if [ "${1:-}" = "run" ]; then
    # Дождаться, пока старый экземпляр действительно выйдет: open, запущенный
    # раньше, получает от LaunchServices procNotFound (-600) и не открывает ничего.
    if pkill -x FlowLocal 2>/dev/null; then
        for _ in $(seq 1 50); do pgrep -x FlowLocal >/dev/null || break; sleep 0.1; done
    fi
    open "$APP"
fi
