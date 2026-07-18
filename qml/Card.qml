// .ins-card: поверхность бумаги, волосяная линия, радиус 12.
//
// В tkinter это был холст с фоном, нарисованным в PIL суперсэмплом x3, потому
// что рамку tk умеет рисовать только прямоугольником - отсюда и известное
// расхождение с Korti («карточки квадратные, а должны быть скруглённые»).
// Здесь это одно слово: radius.

import QtQuick

Rectangle {
    id: card
    default property alias content: body.data

    // Две раскладки, один компонент. «Карточки» - канон Korti: бумага,
    // волосяная рамка, радиус 12. «Линии» - то же содержимое без коробки:
    // рамка и фон снимаются, строки разделяются линиями сами (это уже умеет
    // SettingRow). На длинных страницах вроде «Диктовки» рамок набиралось
    // столько, что они спорили с содержимым.
    //
    // Читаем из T, а не из конфига напрямую: токены - один источник правды, и
    // смена раскладки должна перерисовывать окно на лету, как смена темы.
    readonly property bool lines: T.layout === "lines"

    color: lines ? "transparent" : T.paper
    radius: lines ? 0 : T.radiusLg
    border.width: lines ? 0 : 1
    border.color: T.border
    implicitHeight: body.implicitHeight

    Column {
        id: body
        width: parent.width
        spacing: 0
    }
}
