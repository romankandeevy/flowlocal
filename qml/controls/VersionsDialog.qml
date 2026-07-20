// Выплывающая панель со списком прежних версий - архив 0.x из docs/history-0.x.md.
//
// Зачем выплывающей панелью, а не страницей. Это редкая справка «как программа
// дошла до 1.0»: её открывают раз, читают и закрывают. Своего пункта в панели
// она не заслуживает - всплыть поверх «О программе» и уйти по клику мимо ровно
// её вес. Полная история версий 0.x в CHANGELOG.md схлопнута в строку «1.0»
// намеренно; кому нужны подробности - вот они, но не на виду.
//
// QtQuick.Controls (штатный Popup) здесь НЕТ: его плагин не грузится из нашей
// сборки по тем же граблям, что разобраны в overlay_qt._preload_qml_deps.
// Поэтому оверлей собран руками: подложка на всё окно гасит фон и ловит клик
// мимо, панель по центру, крестик в шапке. Esc закрывает на уровне окна
// (Settings.qml) - у оверлея нет фокуса, чтобы ловить клавиши самому.
//
// `B` здесь НЕ трогаем: данные приходят свойством `versions` (готовый список от
// settings_qt.oldVersions), как combo/hint приходят в EmptyState. Так панель не
// привязана к окну, в котором висит, и её можно поднять где угодно.

import QtQuick

Item {
    id: dlg

    property bool open: false
    // [{version, date, title, items}] - разобранный архив. Пусто - панель и не
    // покажут: кнопку-открывашку прячет тот, у кого этот список есть.
    property var versions: []
    property string title: ""

    // Закрытие наружу сигналом, а не своим open=false: `open` привязан к флагу
    // окна (одностороннее связывание), и сбросить его должен владелец флага,
    // иначе связывание порвётся. Внутренние действия (клик мимо, крестик) лишь
    // просят закрыть.
    signal closed()

    anchors.fill: parent
    z: 200
    visible: opacity > 0.001
    opacity: open ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: T.durBase * 1000 } }

    Icons { id: ic }

    // Подложка: гасит окно под собой и ловит клик мимо панели.
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(T.bg.r, T.bg.g, T.bg.b, 0.92)
        MouseArea { anchors.fill: parent; onClicked: dlg.closed() }
    }

    Rectangle {
        id: panel
        anchors.centerIn: parent
        width: Math.min(560, dlg.width - 96)
        height: Math.min(dlg.height - 120, 620)
        radius: T.radiusLg
        color: T.paper
        border.width: 1
        border.color: T.border

        // Клик по самой панели не должен доходить до подложки и закрывать её.
        MouseArea { anchors.fill: parent }

        // Шапка: заголовок и «Закрыть».
        Item {
            id: head
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 56

            Text {
                anchors { left: parent.left; leftMargin: 24
                          verticalCenter: parent.verticalCenter }
                text: dlg.title
                font.family: T.sans; font.pixelSize: T.tXl
                font.weight: Font.DemiBold
                color: T.text
            }
            FlowButton {
                anchors { right: parent.right; rightMargin: 16
                          verticalCenter: parent.verticalCenter }
                label: L.t("Закрыть")
                onClicked: dlg.closed()
            }
            Rectangle {
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                height: 1; color: T.border
            }
        }

        Flickable {
            id: flick
            anchors { left: parent.left; right: parent.right; top: head.bottom
                      bottom: parent.bottom; topMargin: 8; bottomMargin: 8 }
            clip: true
            contentHeight: col.implicitHeight
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: col
                width: flick.width

                // Первой строкой - что это за список, чтобы архив не начинался
                // сразу с номеров без объяснения.
                SectionTitle {
                    leftPadding: 24
                    topPadding: 12
                    bottomPadding: 4
                    text: L.t("Все выпуски до 1.0")
                }

                // Ряды - те же, что у «Как обновлялось» на странице: номер и
                // дата в строке, пункты выпуска под «подробнее» разметкой
                // (в файле они с полужирным зачином, как в CHANGELOG.md).
                Repeater {
                    model: dlg.versions
                    SettingRow {
                        first: index === 0
                        icon: ic.about
                        title: L.t("Версия ") + modelData.version
                        subtitle: modelData.title
                        moreFormat: Text.MarkdownText
                        more: (modelData.items || [])
                              .map(function (s) { return "- " + s }).join("\n")

                        Text {
                            text: modelData.date
                            font.family: T.mono; font.pixelSize: T.t2xs
                            color: T.textMuted
                        }
                    }
                }
            }
        }
    }
}
