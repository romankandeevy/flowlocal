// Строка статистики: число справа моноширинным.
// Цифры табличные, поэтому соседние строки не пляшут по ширине.

import QtQuick

SettingRow {
    id: r
    property string value: "—"

    // Метрика по канону Korti (app-shell): дисплейный кегль 32, вес 800,
    // тесный трекинг. Это цифра, ради которой открывают страницу, - она и
    // должна быть первым, что видно. Моноширинным набирать не нужно: строки
    // разной длины тут не соседствуют по колонке.
    Text {
        text: r.value
        font.family: T.sans
        font.pixelSize: 32
        font.weight: Font.ExtraBold
        font.letterSpacing: -0.96      // -.03em
        color: T.text
    }
}
