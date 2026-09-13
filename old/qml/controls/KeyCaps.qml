// Сочетание клавиш плашками: [Ctrl] + [Shift] + [Space].
//
// Приём - из мастера первого запуска (HotkeyBox): заливка --fill-subtle,
// волосяная линия, радиус 6, моноширинный шрифт. Сочетание клавиш - голос
// терминала, и в системе оно всегда набрано моноширинным.
//
// Разница с мастером одна, и она по назначению. Там это ОДНО поле на всё
// сочетание, потому что в него жмут: поле должно выглядеть полем. Здесь его
// читают, а не нажимают, поэтому клавиши разнесены по штуке - так строка
// перестаёт быть текстом и становится картинкой клавиатуры, которую видно
// боковым зрением.
//
// Flow, а не Row: содержимому главного окна достаётся 420 пикселей, и
// «Ctrl + Alt + Shift + Space» обязано переноситься само, а не уезжать за край.

import QtQuick

Flow {
    id: caps

    // Готовая строка от inputspec.pretty: «Ctrl + Shift + Space». Разбираем её
    // сами, а не просим Python отдать список: склеивает эти куски тоже
    // inputspec, и второго мнения о разделителе в программе быть не должно -
    // поменяется там, поменяется и здесь.
    property string combo: ""
    property int keySize: T.tMd

    // ---------- отклик на настоящее нажатие ----------
    //
    // Умолчания подобраны так, чтобы прежний вызов ничего не заметил: главное
    // окно передаёт одно `combo`, про нажатия не знает, и плашки в нём
    // выглядят ровно как раньше. Отклик нужен мастеру первого запуска - там
    // человек первый раз в жизни жмёт это сочетание и должен увидеть, что
    // программа его слышит, а не поверить на слово.

    // Какие плашки зажаты прямо сейчас - по индексу в `parts`. Пустой массив
    // значит «никто не жмёт».
    property var down: []

    // Сочетание собрано целиком. Цвет тут зелёный, а не синий, и это не выбор
    // на глаз: в системе зелёный - «работает, в эфире» (им же горит точка
    // записи на пилюле), а синий - «фокус, выделение». Нажатое сочетание -
    // первое, а не второе.
    property bool lit: false

    readonly property var parts: combo ? combo.split(" + ") : []
    readonly property int capH: keySize + 20

    spacing: 8

    Repeater {
        model: caps.parts

        // Плюс едет вместе со своей клавишей, а не отдельным элементом Flow:
        // при переносе он обязан уйти на новую строку с ней, иначе строка
        // закончится висящим «+».
        Row {
            spacing: 8

            Text {
                visible: index > 0
                height: caps.capH
                verticalAlignment: Text.AlignVCenter
                text: "+"
                font.family: T.sans
                font.pixelSize: T.tSm
                color: T.textFaint
            }

            Rectangle {
                id: cap
                // Зажата ли ИМЕННО эта клавиша. `down` короче parts или пуст -
                // получаем undefined, и сравнение с true честно даёт false.
                readonly property bool held: caps.down[index] === true

                width: label.implicitWidth + 22
                height: caps.capH
                radius: T.radiusSm
                color: caps.lit ? Qt.rgba(T.success.r, T.success.g, T.success.b, 0.12)
                     : cap.held ? T.fillStrong : T.fillSubtle
                border.width: 1
                border.color: caps.lit ? T.success
                            : cap.held ? T.borderStrong : T.border
                // Масштаб, а не сдвиг вниз: клавиша должна утонуть под пальцем,
                // но Flow считает раскладку по геометрии детей, и подвинутая
                // плашка потащила бы за собой всю строку. Масштаб на раскладку
                // не влияет вовсе.
                scale: cap.held && !caps.lit ? 0.96 : 1

                Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
                Behavior on border.color { ColorAnimation { duration: T.durFast * 1000 } }
                Behavior on scale { NumberAnimation { duration: T.durFast * 1000
                                                      easing.type: Easing.Bezier
                                                      easing.bezierCurve: T.easeOut } }

                Text {
                    id: label
                    anchors.centerIn: parent
                    text: modelData
                    font.family: T.mono
                    font.pixelSize: caps.keySize
                    font.weight: Font.Medium
                    color: caps.lit ? T.success : T.text
                    Behavior on color { ColorAnimation { duration: T.durFast * 1000 } }
                }
            }
        }
    }
}
