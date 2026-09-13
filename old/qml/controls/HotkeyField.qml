// HotkeyBox, привязанный к ключу конфига. Захват идёт в Python (там живут
// keyboard/mouse), сюда возвращается сигналом captureDone.

import QtQuick

HotkeyBox {
    id: hf
    property string field: ""

    value: B.get(field) || ""
    pretty: B.pretty(value)

    onStartCapture: { capturing = true; B.startCapture(field) }
    onCancelCapture: { capturing = false; B.cancelCapture() }
    onCleared: { B.set(field, ""); value = ""; pretty = "" }

    Connections {
        target: B
        function onCaptureDone(f, spec) {
            if (f !== hf.field) return;
            hf.capturing = false;
            hf.value = spec;
            hf.pretty = B.pretty(spec);
        }
    }
}
