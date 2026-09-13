// Расшифровка файла: сам текст и две кнопки - скопировать и сохранить .txt.
//
// Почему окно, а не вставка в активное поле. Диктовка целится в то место, где
// человек сейчас стоит курсором, и это правильно: он сам туда встал секунду
// назад. С файлом всё наоборот - он перетащил его на окно программы, то есть
// стоит ЗДЕСЬ, а не в письме. Вставить час подкаста в случайное поле под
// курсором было бы не услугой, а происшествием.
//
// Поле для правки, а не просто надпись: расшифровку почти всегда правят перед
// тем, как куда-то деть, и делать это удобнее сразу, а не после вставки.
// Поэтому «Скопировать» и «Сохранить» берут текст ИЗ ПОЛЯ, а не то, что
// приехало из Python.
//
// QtQuick.Controls тут нет: его плагин не поднимается из нашей сборки по тем же
// граблям, что разобраны в overlay_qt._preload_qml_deps. Flickable + TextEdit
// делают то же самое.
import QtQuick
import "../controls"

Rectangle {
    id: root
    width: 760
    height: 560
    color: T.bg

    // Имя исходного файла - шапкой. Расшифровок за вечер бывает несколько, и
    // без имени они неотличимы друг от друга.
    property string source: ""
    property string note: ""

    signal copy(string text)
    signal save(string text)

    function setText(t) { editor.text = t }

    Icons { id: ic }

    // ---------- шапка ----------
    Item {
        id: head
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 64

        Icon {
            id: headIcon
            path: ic.file
            size: 20
            color: T.textSecondary
            anchors { left: parent.left; leftMargin: 20; verticalCenter: parent.verticalCenter }
        }
        Column {
            anchors { left: headIcon.right; leftMargin: 12; right: parent.right
                      rightMargin: 20; verticalCenter: parent.verticalCenter }
            spacing: 2
            Text {
                width: parent.width
                text: L.t("Расшифровка")
                elide: Text.ElideRight
                font.family: T.sans; font.pixelSize: T.tXl; font.weight: Font.DemiBold
                color: T.text
            }
            Text {
                width: parent.width
                text: root.source
                elide: Text.ElideMiddle
                font.family: T.sans; font.pixelSize: T.tSm
                color: T.textMuted
            }
        }
        Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                    height: 1; color: T.border }
    }

    // ---------- сам текст ----------
    Item {
        anchors { left: parent.left; right: parent.right; top: head.bottom
                  bottom: bar.top; margins: 16 }

        Flickable {
            id: flick
            anchors.fill: parent
            contentWidth: width
            contentHeight: editor.paintedHeight + 20
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            TextEdit {
                id: editor
                width: flick.width
                wrapMode: TextEdit.Wrap
                selectByMouse: true
                font.family: T.sans
                font.pixelSize: T.tMd
                color: T.text
                selectionColor: T.accent
                selectedTextColor: T.accentFg
            }
        }
    }

    // ---------- низ: что с этим делать ----------
    Rectangle {
        id: bar
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 56
        color: "transparent"
        Rectangle { anchors { left: parent.left; right: parent.right; top: parent.top }
                    height: 1; color: T.border }

        Row {
            anchors { left: parent.left; leftMargin: 16
                      verticalCenter: parent.verticalCenter }
            spacing: 8
            FlowButton {
                label: L.t("Скопировать")
                kind: "primary"
                enabled: editor.text.trim().length > 0
                onClicked: root.copy(editor.text)
            }
            FlowButton {
                label: L.t("Сохранить .txt")
                enabled: editor.text.trim().length > 0
                onClicked: root.save(editor.text)
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                visible: root.note !== ""
                text: root.note
                font.family: T.sans; font.pixelSize: T.tSm
                color: T.textMuted
            }
        }

        // Сколько получилось - справа. Не украшение: по числу слов видно, что
        // расшифровалась вся запись, а не первые полминуты.
        Text {
            anchors { right: parent.right; rightMargin: 16
                      verticalCenter: parent.verticalCenter }
            text: editor.text.trim().length === 0 ? ""
                  : editor.text.trim().split(/\s+/).length + L.t(" слов")
            font.family: T.mono; font.pixelSize: T.t2xs
            color: T.textFaint
        }
    }
}
