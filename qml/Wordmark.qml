// Знак плюс имя. Канон Korti (templates/app-shell): квадрат со скруглением 6,
// внутри знак чернилами по бумаге, справа имя дисплейным весом с тесным
// трекингом. У korti знак - буква «i», у нас микрофон: то, чем занят продукт.
//
// Живёт отдельным файлом, потому что мест уже два - боковая панель и «О
// программе», - и они обязаны совпадать: вордмарк, нарисованный дважды на
// глаз, расходится на первой же правке.

import QtQuick

Row {
    id: mark
    property int box: 28             // сторона квадрата со знаком
    property real nameSize: T.tXl

    spacing: 10

    // Высота задана явно, а не набегает от детей, и это не педантизм. Row
    // кладёт детей по верхнему краю: квадрат прижимался к верху, а имя
    // центрировалось якорем - и на крупном кегле в «О программе» знак заметно
    // висел выше имени (владелец прислал скриншот). Явная высота позволяет
    // центрировать обоих: привязать высоту к детям, которые сами привязаны к
    // этой высоте, нельзя - это петля.
    height: Math.max(box, name.implicitHeight)

    Icons { id: ic }

    Rectangle {
        anchors.verticalCenter: parent.verticalCenter
        width: mark.box; height: mark.box; radius: T.radiusSm
        color: T.ink
        Icon {
            anchors.centerIn: parent
            // Подъём на пару процентов от размера - оптическая центровка, и
            // она замерена, а не на глаз. По геометрии микрофон стоит ровно:
            // поле сверху 6.00 px, снизу 6.07 при знаке 28. Но у иконки Lucide
            // тяжёлая часть - дуга под капсулой, она идёт во всю ширину ниже
            // середины, и глаз читает знак съехавшим вниз (владелец заметил
            // первым). Смещение считаем от размера, иначе на крупном знаке в
            // «О программе» поправка стала бы вдвое слабее.
            anchors.verticalCenterOffset: -Math.round(mark.box * 0.045)
            path: ic.mic
            size: Math.round(mark.box * 0.57)
            color: T.bg
            weight: 2.2
        }
    }
    Text {
        id: name
        anchors.verticalCenter: parent.verticalCenter
        text: "FlowLocal"
        font.family: T.sans
        font.pixelSize: mark.nameSize
        font.weight: Font.Bold          // 700, не 800: Onest в ExtraBold чернит
        // -.03em, как дисплейные кегли в системе.
        font.letterSpacing: -0.03 * mark.nameSize
        color: T.text
    }
}
