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

    color: T.paper
    radius: T.radiusLg
    border.width: 1
    border.color: T.border
    implicitHeight: body.implicitHeight

    Column {
        id: body
        width: parent.width
        spacing: 0
    }
}
