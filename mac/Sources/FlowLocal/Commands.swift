import AppKit
import SwiftUI

// Строка меню. Всё, что умеет приложение, есть командой здесь: кнопки в окне
// и контекстное меню - только короткий путь к тем же командам. Меню
// приложения («О программе», «Настройки…» ⌘,, «Скрыть», «Завершить»),
// «Правка» и «Окно» - системные.
struct AppCommands: Commands {
    @ObservedObject var state: AppState
    let actions: AppActions

    var body: some Commands {

        // Приложение не документное: «Новое» в «Файле» ни к чему.
        CommandGroup(replacing: .newItem) {}

        // «Настройки…» ⌘, - модуль Flow в Hub Settings.
        CommandGroup(replacing: .appSettings) {
            Button("Настройки…", action: actions.openSettings)
                .keyboardShortcut(",")
        }

        CommandGroup(replacing: .textEditing) {
            Button("Найти…", action: actions.find)
                .keyboardShortcut("f")
        }

        CommandGroup(before: .toolbar) {
            ForEach(Tab.allCases) { tab in
                Button(tab.title) {
                    state.tab = tab
                    actions.showMain()
                }
                .keyboardShortcut(tab.shortcut)
            }
            Divider()
        }

        CommandMenu("Диктовка") {
            Button(state.isRecording ? "Закончить диктовку" : "Начать диктовку", action: actions.toggleDictation)
                .disabled(!state.isRecording && !state.canDictate)
            Button("Отменить диктовку", action: actions.cancelDictation)
                .disabled(!state.isBusy)
            Toggle("Режим шёпота", isOn: $state.whisperMode)
                .keyboardShortcut("w", modifiers: [.command, .option])
            Divider()
            EntryCommands(state: state, entries: state.entries(state.historySelection), actions: actions,
                          editing: false)
            Divider()
            Button("Очистить историю") {
                state.clearHistory(undo: (NSApp.keyWindow ?? NSApp.mainWindow)?.undoManager)
            }
            .disabled(state.history.isEmpty)
            Divider()
            Button("Показать записи в Finder", action: actions.openRecordings)
            Button("Показать журнал", action: actions.openLog)
        }

        CommandGroup(replacing: .help) {
            Button("Справка Flow Local") { NSWorkspace.shared.open(AppInfo.helpURL) }
        }
    }
}
