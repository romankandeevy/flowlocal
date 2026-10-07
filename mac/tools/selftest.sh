#!/bin/bash
# Самопроверка логики без окна: словарь, обучение на правках, стили, шёпот.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
xcrun swiftc -O -swift-version 5 \
    Sources/FlowLocal/TextCleaner.swift Sources/FlowLocal/Vocabulary.swift \
    Sources/FlowLocal/TextStyle.swift Sources/FlowLocal/CodeSpeech.swift Sources/FlowLocal/WhisperGain.swift \
    tools/selftest/main.swift -o build/selftest
build/selftest
