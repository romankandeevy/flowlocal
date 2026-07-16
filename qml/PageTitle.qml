// Заголовок страницы. Дисплейный кегль по канону Korti (app-shell, h1):
// 26px, вес 800, трекинг -.02em - так задан голос бренда, и мельче он
// перестаёт быть заголовком.
import QtQuick

Text {
    font.family: T.sans
    font.pixelSize: 26
    font.weight: Font.ExtraBold
    font.letterSpacing: -0.52      // -.02em от 26px
    color: T.text
}
