// Заметки - отдельное окно. Теперь двухступенчатое: сначала СПИСОК заметок,
// из него - в редактор.
//
// Почему отдельное окно, а не страница в главном: диктуют В него, а не рядом с
// ним. Главное окно при этом остаётся открытым - человек не должен выбирать
// между «вижу свои настройки» и «пишу заметку».
//
// ---- Почему список и редактор - в ОДНОМ окне, а не двумя ----
//
// Владелец: «нажал Заметки - открылся список всех заметок, можно почитать,
// поправить, удалить. А "Создать новую" - тогда уже редактор». Раньше окно
// открывалось сразу в редактор (список жил узкой колонкой слева, и его не
// замечали). Теперь два ПОЛНЫХ вида, переключаемых свойством `view`:
//
//   list   - список заметок: заголовок, дата, превью первой строки, у каждой
//            «Открыть» и «Удалить». Сверху «Новая» и поиск.
//   editor - тот же редактор, что был: диктуют В него, автосейв, «Привести в
//            порядок», «Скопировать всё», «Удалить». Сверху «Назад» к списку.
//
// Одним окном, а не отдельным NotesList.qml, - сознательно. Редактор никуда не
// выброшен, к нему добавлен экран перед ним; вся обвязка (autosave, improve,
// copy, remove, search) уже связана с этим корнем, и второе окно означало бы
// два QQuickView, две их жизни и синхронизацию списка между ними - там, где
// хватает одного свойства `view`. Что показать при открытии, решает Python по
// настройке «notes_open» (notes_qt.open): по умолчанию - список.
//
// Диктовка в редактор работает сама: текст вставляется в активное окно через
// Ctrl+V, а активным будет это окно с полем в фокусе. Поэтому при переходе в
// редактор поле берём под фокус (onViewChanged) - чтобы надиктованному было
// куда лечь с первой секунды.

// Контролы лежат в соседней папке, поэтому импорт каталога: соседства,
// на котором QML находит типы сам, между windows/ и controls/ уже нет.
// Почему каталог, а не qmldir, - разобрано в windows/Settings.qml.
import QtQuick
import "../controls"

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
    // Короткая жалоба внизу редактора. Пусто - жаловаться не на что.
    property string note: ""
    // Какой экран показан: "list" (список заметок) или "editor" (одна заметка).
    // Ставит Python при открытии (notes_qt.open) по настройке «notes_open»,
    // переключают кнопки «Новая»/«Открыть» (в редактор) и «Назад» (к списку).
    property string view: "list"

    signal pick(string id)
    signal create()
    signal remove(string id)
    signal store(string id, string text)
    signal improve(string id, string text)
    signal copy(string text)
    signal search(string query)

    // Иконки нужны пустому списку. Свой инстанс, а не общий: у этого окна нет
    // ни `B`, ни чужих синглтонов - оно живёт само по себе.
    Icons { id: ic }

    function setText(t) {
        if (editor.text !== t)
            editor.text = t;
    }

    // Поле под фокус, как только показали редактор: диктовка вставляется в
    // активное поле, и без фокуса надиктованному некуда лечь. Оба вида всегда
    // собраны в дереве (переключается лишь видимость), так что editor к этому
    // моменту существует.
    onViewChanged: if (view === "editor") editor.forceActiveFocus()

    // Сохраняем не на каждую букву, а через паузу после последней: заметку
    // пишут диктовкой, то есть кусками по десятку слов, и писать файл на
    // каждое нажатие незачем.
    Timer {
        id: autosave
        interval: 700
        onTriggered: root.store(root.current, editor.text)
    }

    // Сохранить немедленно и уйти к списку. Явное сохранение перед уходом:
    // автосейв ждёт паузу в 700 мс, а «Назад» можно нажать раньше - и тогда
    // последние слова не попали бы ни в превью списка, ни на диск.
    function backToList() {
        if (root.current)
            root.store(root.current, editor.text);
        root.view = "list";
    }

    // ======================= СПИСОК =======================
    Item {
        anchors.fill: parent
        visible: root.view === "list"

        Text {
            id: listTitle
            anchors { left: parent.left; top: parent.top
                      leftMargin: 20; topMargin: 16 }
            text: L.t("Заметки")
            font.family: T.sans; font.pixelSize: T.tXl
            font.weight: Font.DemiBold
            color: T.text
        }

        // «Новая» и поиск одной строкой, как строка поиска в app-shell.
        Row {
            id: listBar
            anchors { left: parent.left; right: parent.right; top: listTitle.bottom
                      leftMargin: 16; rightMargin: 16; topMargin: 12 }
            spacing: 8
            FlowButton {
                id: newBtn
                label: L.t("Новая")
                kind: "primary"
                // «Новая» заводит чистую заметку и уводит в редактор - ровно то
                // окно, что раньше открывалось сразу.
                onClicked: { root.create(); root.view = "editor" }
            }
            FlowInput {
                id: findFld
                width: listBar.width - newBtn.width - listBar.spacing
                placeholder: L.t("Найти…")
                onTextChanged: root.search(text)
            }
        }

        ListView {
            id: list
            anchors { left: parent.left; right: parent.right; top: listBar.bottom
                      bottom: parent.bottom; leftMargin: 16; rightMargin: 16
                      topMargin: 12; bottomMargin: 16 }
            clip: true
            spacing: 10
            model: root.items

            // Каждая заметка - карточкой: заголовок, превью первой строки, дата,
            // и явные «Открыть»/«Удалить». Тень выключена по той же причине, что
            // у карточек «Истории»: список с клипом обрезал бы её по краю.
            delegate: Card {
                width: list.width
                shadow: false
                Item {
                    width: parent.width
                    implicitHeight: Math.max(noteInfo.implicitHeight,
                                             noteActions.implicitHeight) + 28
                    Column {
                        id: noteInfo
                        anchors { left: parent.left; right: noteActions.left
                                  top: parent.top; leftMargin: 20
                                  rightMargin: 12; topMargin: 14 }
                        spacing: 6
                        Text {
                            width: parent.width
                            text: modelData.title
                            elide: Text.ElideRight
                            font.family: T.sans; font.pixelSize: T.tMd
                            font.weight: Font.DemiBold
                            color: T.text
                        }
                        Text {
                            width: parent.width
                            // Прячем, когда превью повторяет заголовок слово в
                            // слово: у короткой однострочной заметки первая
                            // строка и есть заголовок, и дублировать её незачем.
                            // У длинной заголовок обрезан до 60, а превью до 120
                            // - там оно показывает продолжение и остаётся.
                            visible: text !== "" && text !== modelData.title
                            text: modelData.preview
                            elide: Text.ElideRight
                            maximumLineCount: 1
                            font.family: T.sans; font.pixelSize: T.tSm
                            color: T.textMuted
                        }
                        Text {
                            visible: text !== ""
                            text: modelData.when
                            font.family: T.mono; font.pixelSize: T.t2xs
                            color: T.textMuted
                        }
                    }
                    Row {
                        id: noteActions
                        anchors { right: parent.right; rightMargin: 20
                                  verticalCenter: parent.verticalCenter }
                        spacing: 8
                        FlowButton {
                            label: L.t("Открыть")
                            kind: "primary"
                            onClicked: { root.pick(modelData.id); root.view = "editor" }
                        }
                        FlowButton {
                            label: L.t("Удалить")
                            kind: "danger"
                            onClicked: root.remove(modelData.id)
                        }
                    }
                }
            }

            // Пусто - зовём попробовать, а не показываем пустоту. Вид тот же,
            // что у пустых «Истории» и «Статистики» в главном окне: одно
            // устройство пустоты на всю программу. Внутри ListView можно: список
            // пуст, ездить нечему.
            EmptyState {
                anchors.centerIn: parent
                visible: root.items.length === 0
                icon: ic.notes
                title: L.t("Заметок пока нет")
                hint: L.t("Нажмите «Новая» и диктуйте прямо сюда.")
            }
        }
    }

    // ======================= РЕДАКТОР =======================
    Item {
        anchors.fill: parent
        visible: root.view === "editor"

        // Шапка редактора: «Назад» к списку.
        Item {
            id: edBar
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 56
            FlowButton {
                anchors { left: parent.left; leftMargin: 16
                          verticalCenter: parent.verticalCenter }
                label: L.t("Назад")
                onClicked: root.backToList()
            }
            Rectangle {
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                height: 1; color: T.border
            }
        }

        // Само поле заметки.
        Item {
            anchors { left: parent.left; right: parent.right; top: edBar.bottom
                      bottom: bottomBar.top; margins: 16 }

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
                    font.pixelSize: T.tMd
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
                    font.pixelSize: T.tMd
                    color: T.textFaint
                }
            }
        }

        // Низ: действия.
        Rectangle {
            id: bottomBar
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
                    label: root.busy ? L.t("Причёсываю…") : L.t("Привести в порядок")
                    enabled: !root.busy && editor.text.trim().length > 0
                    onClicked: { root.busy = true; root.improve(root.current, editor.text) }
                }
                FlowButton {
                    label: L.t("Скопировать всё")
                    enabled: editor.text.trim().length > 0
                    onClicked: root.copy(editor.text)
                }

                // «Привести в порядок» умеет не сработать - она ходит в правку
                // текста, а та бывает не установлена или молчит. Раньше в этом
                // случае кнопка просто переставала «причёсывать», и человек
                // оставался с ощущением, что нажатие потерялось. Причину говорим
                // словами; текст исключения при этом остаётся в журнале.
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.note !== ""
                    text: root.note
                    font.family: T.sans; font.pixelSize: T.tSm
                    color: T.danger
                }
            }
            FlowButton {
                anchors { right: parent.right; rightMargin: 16
                          verticalCenter: parent.verticalCenter }
                label: L.t("Удалить")
                kind: "danger"
                enabled: root.current !== ""
                // Удалили из редактора - возвращаемся к списку: показывать пустой
                // редактор удалённой заметки незачем.
                onClicked: { root.remove(root.current); root.view = "list" }
            }
        }
    }
}
