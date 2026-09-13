// Korti SegmentedControl: контейнер --fill, выбранный сегмент - бумага.
// Радиус контейнера 8, сегмента - на отступ меньше (см. ниже, где считается).
//
// С клавиатуры переключается стрелками влево-вправо, как и положено группе из
// двух-трёх взаимоисключающих значений: таб входит в группу целиком, а не
// обходит каждый сегмент.

import QtQuick

Item {
    id: seg
    // [{label: "тёмная", value: "dark"}, ...] - value любого типа, в том числе null
    property var options: []
    property var value
    signal picked(var value)

    height: 30
    implicitWidth: box.implicitWidth
    width: implicitWidth

    // Поле вокруг бегунка. Одно число на все места, где оно нужно (отступ,
    // высота, радиус, ширина контейнера), - иначе радиус тихо разъезжается с
    // геометрией.
    readonly property int inset: 3

    activeFocusOnTab: enabled

    // Мышиный ли фокус - разобрано в шапке FocusRing.qml.
    property bool mouseFocus: false
    readonly property bool visualFocus: activeFocus && !mouseFocus
    onActiveFocusChanged: if (!activeFocus) mouseFocus = false

    opacity: enabled ? 1 : 0.4
    Behavior on opacity { NumberAnimation { duration: T.durFast * 1000 } }

    function indexOf(v) {
        for (var i = 0; i < options.length; i++)
            if (options[i].value === v) return i;
        return 0;
    }

    function step(delta) {
        if (options.length === 0)
            return;
        // По кругу: на двух вариантах (а их чаще всего два) упереться в край и
        // перестать переключаться - худшее, что может сделать стрелка.
        var i = (indexOf(value) + delta + options.length) % options.length;
        seg.value = options[i].value;
        seg.picked(options[i].value);
    }

    Keys.onPressed: (e) => {
        if (e.key === Qt.Key_Left) { step(-1); e.accepted = true; }
        else if (e.key === Qt.Key_Right) { step(1); e.accepted = true; }
    }

    Rectangle {
        id: box
        anchors.fill: parent
        radius: T.radiusMd
        color: T.fill
        implicitWidth: rowItems.implicitWidth + 2 * seg.inset

        // Бегунок выбранного сегмента - бумага. Едет той же кривой, что и всё
        // остальное: система разрешает фейды и сдвиги, пружин нет.
        Rectangle {
            id: thumb
            visible: rowItems.children.length > 0
            y: seg.inset
            height: parent.height - 2 * seg.inset
            // Внутренний радиус = внешний минус отступ. Стояло T.radiusSm (6)
            // при внешних 8 и отступе 3, то есть на единицу больше нужного:
            // дуги бегунка и контейнера шли не эквидистантно, и угол читался
            // «толще» остальных. Глаз ловит это раньше, чем успевает понять, за
            // что зацепился, - потому и считаем, а не подбираем.
            radius: T.radiusMd - seg.inset
            color: T.paper
            border.width: 1
            border.color: T.border
            x: {
                var acc = seg.inset;
                for (var i = 0; i < seg.indexOf(seg.value) && i < rowItems.children.length; i++)
                    acc += rowItems.children[i].width;
                return acc;
            }
            width: {
                var i = seg.indexOf(seg.value);
                return i < rowItems.children.length ? rowItems.children[i].width : 0;
            }
            Behavior on x { NumberAnimation { duration: T.durBase * 1000
                                              easing.type: Easing.Bezier
                                              easing.bezierCurve: T.easeOut } }
            Behavior on width { NumberAnimation { duration: T.durBase * 1000
                                                  easing.type: Easing.Bezier
                                                  easing.bezierCurve: T.easeOut } }
        }

        Row {
            id: rowItems
            x: seg.inset
            y: seg.inset
            height: parent.height - 2 * seg.inset
            Repeater {
                model: seg.options
                Item {
                    height: rowItems.height
                    width: Math.max(36, lbl.implicitWidth + 24)
                    Text {
                        id: lbl
                        anchors.centerIn: parent
                        // Подписи приходят из двух мест: собранные тут же (уже
                        // через L.t) и готовые списки из Python (B.themeOptions
                        // и прочие) - вот эти до сих пор оставались русскими
                        // при английском интерфейсе. L.t идемпотентен: то, что
                        // уже переведено, ключом не является и проходит как
                        // есть, - поэтому одно место, а не два.
                        text: L.t(modelData.label)
                        font.family: T.sans
                        font.pixelSize: T.tSm
                        font.weight: Font.Medium
                        color: seg.indexOf(seg.value) === index ? T.text
                             : ma.containsMouse ? T.textSecondary : T.textMuted
                        Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
                        // Нажатие: подпись чуть тонет. Бегунок в этот момент
                        // ещё едет к сегменту, и без отклика на самом сегменте
                        // первые 180 мс выглядят как «не нажалось».
                        scale: ma.pressed ? 0.94 : 1
                        Behavior on scale { NumberAnimation { duration: T.durFast * 1000
                                                              easing.type: Easing.Bezier
                                                              easing.bezierCurve: T.easeOut } }
                    }
                    // Ховер невыбранного сегмента: подложка на ступень выше.
                    // Одной подписи мало - на трёх сегментах непонятно, куда
                    // именно попадёт клик.
                    Rectangle {
                        anchors.fill: parent
                        z: -1
                        radius: T.radiusMd - seg.inset
                        visible: ma.containsMouse && seg.indexOf(seg.value) !== index
                        color: T.fillSubtle
                    }
                    MouseArea {
                        id: ma
                        anchors.fill: parent
                        hoverEnabled: true
                        enabled: seg.enabled
                        cursorShape: seg.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onPressed: { seg.mouseFocus = true; seg.forceActiveFocus() }
                        onClicked: { seg.value = modelData.value; seg.picked(modelData.value) }
                    }
                }
            }
        }
    }

    FocusRing { target: box; on: seg.visualFocus }
}
