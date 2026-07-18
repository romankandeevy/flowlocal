// Заголовок страницы. Дисплейный кегль по канону Korti (app-shell, h1):
// 26px, трекинг -.02em - так задан голос бренда, и мельче он перестаёт быть
// заголовком. Вес 700, а не канонические 800: Onest (кириллическая замена
// Hanken Grotesk) в ExtraBold заметно чернее оригинала и читается тяжело -
// на живом экране 800 придавливал страницу. 700 держит вес заголовка, не
// перегружая.
import QtQuick

Text {
    font.family: T.sans
    font.pixelSize: 26
    font.weight: Font.Bold
    font.letterSpacing: -0.52      // -.02em от 26px
    color: T.text
}
