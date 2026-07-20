// Строка с переключателем, привязанным к ключу конфига. Сахар: таких строк
// в настройках восемь, и каждый раз писать Toggle с обработчиком - шум.

import QtQuick

SettingRow {
    id: r
    property string path: ""
    property bool value: B.get(path) === true

    Toggle {
        value: r.value
        onToggled: (v) => { r.value = v; B.set(r.path, v) }
    }
}
