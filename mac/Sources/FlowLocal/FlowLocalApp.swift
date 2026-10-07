import SwiftUI

// Точка входа: одно окно без заголовка - «светофоры» лежат на сайдбаре.
// Своих настроек у Flow нет: они в Hub Settings, ⌘, открывает его на
// модуле Flow (HubSync).
@main
struct FlowLocalApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate

    init() { NLFont.register() }

    var body: some Scene {
        Window("Flow Local", id: "main") {
            MainView(actions: delegate.actions)
                .environmentObject(delegate.state)
        }
        .windowStyle(.hiddenTitleBar)
        .defaultSize(width: 1080, height: 720)
        .commands {
            AppCommands(state: delegate.state, actions: delegate.actions)
        }
    }
}
