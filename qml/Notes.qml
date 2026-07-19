// Заметки - отдельное окно, куда можно диктовать длинно.
//
// Почему отдельное, а не страница в главном окне: диктуют в него, а не рядом с
// ним. Главное окно при этом остаётся открытым - человек не должен выбирать
// между «вижу свои настройки» и «пишу заметку».
//
// Диктовка сюда работает сама и без единой строки кода: текст мы вставляем
// в активное окно через Ctrl+V, а активным в этот момент будет это окно с
// полем в фокусе. Ничего специального для этого делать не понадобилось - и
// это тот случай, когда стоит порадоваться, а не изобретать.

import QtQuick

// QtQuick.Controls здесь НЕТ намеренно. Его плагин (qtquickcontrols2plugin.dll)
// не грузится из нашей сборки по тем же граблям, что описаны в
// overlay_qt._preload_qml_deps: зависимости DLL ищет штатный загрузчик Windows,
// а он не видит папку PySide6, которую питон прописал себе через
// add_dll_directory.
//
// Чинить это подгрузкой ещё одной библиотеки можно, но незачем: во всём
// остальном проекте Controls не используется, а поле и прокрутка прекрасно
// делаются Flickable + TextEdit - тем же способом, что FlowInput.

Rectangle {
    id: root
    width: 860
    height: 600
    color: T.bg

    property var items: []
    property string current: ""
    property bool busy: false

    signal pick(string id)
    signal create()
    signal remove(string id)
    signal store(string id, string text)
    signal improve(string id, string text)
    signal copy(string text)
    signal search(string query)

    function setText(t) {
        if (editor.text !== t)
            editor.text = t;
    }

    // Сохраняем не на каждую букву, а через паузу после последней: заметку
    // пишут диктовкой, то есть кусками по десятку слов, и писать файл на
    // каждое нажатие незачем.
    Timer {
        id: autosave
        interval: 700
        onTriggered: root.store(root.current, editor.text)
    }

    // ---------- слева: список ----------
    Rectangle {
        id: side
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        width: 260
        color: T.paper
        Rectangle { anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
                    width: 1; color: T.border }

        Column {
            anchors { fill: parent; margins: 12 }
            spacing: 8

            Row {
                spacing: 8
                width: parent.width
                FlowButton {
                    label: L.t("Новая")
                    kind: "primary"
                    onClicked: root.create()
                }
                FlowInput {
                    width: parent.width - 90
                    placeholder: L.t("Найти…")
                    onTextChanged: root.search(text)
                }
            }

            ListView {
                id: list
                width: parent.width
                height: parent.height - 46
                clip: true
                model: root.items
                spacing: 2
                delegate: Rectangle {
                    width: list.width
                    height: 48
                    radius: T.radiusMd
                    color: modelData.id === root.current ? T.fill : "transparent"
                    Column {
                        anchors { left: parent.left; right: parent.right
                                  leftMargin: 10; rightMargin: 10
                                  verticalCenter: parent.verticalCenter }
                        spacing: 2
                        Text {
                            width: parent.width
                            text: modelData.title
                            elide: Text.ElideRight
                            font.family: T.sans; font.pixelSize: T.tSm
                            color: T.text
                        }
                        Text {
                            text: modelData.note + " · " + modelData.updated.slice(5, 16)
                            font.family: T.sans; font.pixelSize: T.t2xs
                            color: T.textMuted
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.pick(modelData.id)
                    }
                }
                // Пусто - зовём попробовать, а не показываем пустоту.
                Text {
                    anchors.centerIn: parent
                    width: parent.width - 30
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    visible: root.items.length === 0
                    text: L.t("Заметок пока нет.\nНажмите «Новая» и диктуйте прямо сюда.")
                    font.family: T.sans; font.pixelSize: T.tXs
                    color: T.textMuted
                    lineHeight: 1.4
                }
            }
        }
    }

    // ---------- справа: сама заметка ----------
    Item {
        anchors { left: side.right; right: parent.right; top: parent.top
                  bottom: bar.top; margins: 16 }

        Flickable {
            id: flick
            anchors.fill: parent
            contentWidth: width
            contentHeight: editor.paintedHeight + 20
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            function ensureVisible(r) {
                if (contentY >= r.y)
                    contentY = r.y;
                else if (contentY + height <= r.y + r.height)
                    contentY = r.y + r.height - height;
            }

            TextEdit {
                id: editor
                width: flick.width
                wrapMode: TextEdit.Wrap
                selectByMouse: true
                font.family: T.sans
                font.pixelSize: T.tBase
                color: T.text
                selectionColor: T.accent
                selectedTextColor: T.accentFg
                onTextChanged: if (root.current) autosave.restart()
                // Курсор не должен уезжать за край: текст прибывает кусками,
                // и без этого человек смотрит в конец страницы, а пишется ниже.
                onCursorRectangleChanged: flick.ensureVisible(cursorRectangle)
            }

            // Подсказка вместо placeholderText, которого у TextEdit нет.
            Text {
                visible: editor.text.length === 0
                text: L.t("Диктуйте или пишите. Сохраняется само.")
                font.family: T.sans
                font.pixelSize: T.tBase
                color: T.textFaint
            }
        }
    }

    // ---------- низ: действия ----------
    Rectangle {
        id: bar
        anchors { left: side.right; right: parent.right; bottom: parent.bottom }
        height: 56
        color: "transparent"
        Rectangle { anchors { left: parent.left; right: parent.right; top: parent.top }
                    height: 1; color: T.border }

        Row {
            anchors { left: parent.left; leftMargin: 16
                      verticalCenter: parent.verticalCenter }
            spacing: 8
            FlowButton {
                label: root.busy ? L.t("Причёсываю…") : L.t("Привести в порядок")
                enabled: !root.busy && editor.text.trim().length > 0
                onClicked: { root.busy = true; root.improve(root.current, editor.text) }
            }
            FlowButton {
                label: L.t("Скопировать всё")
                enabled: editor.text.trim().length > 0
                onClicked: root.copy(editor.text)
            }
        }
        FlowButton {
            anchors { right: parent.right; rightMargin: 16
                      verticalCenter: parent.verticalCenter }
            label: L.t("Удалить")
            kind: "danger"
            enabled: root.current !== ""
            onClicked: root.remove(root.current)
        }
    }
}
