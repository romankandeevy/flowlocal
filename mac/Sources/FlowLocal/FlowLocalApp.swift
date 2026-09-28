import SwiftUI

// Точка входа: одно окно, заголовок спрятан - в тулбаре свои разделы и
// поиск. Своих настроек у Flow нет: они в Hub Settings, ⌘, открывает его
// на модуле Flow (HubSync).
@main
struct FlowLocalApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate

    var body: some Scene {
        Window("Flow Local", id: "main") {
            MainView(actions: delegate.actions)
                .environmentObject(delegate.state)
        }
        .windowToolbarStyle(.unified(showsTitle: false))
        .defaultSize(width: 1000, height: 660)
        .commands {
            AppCommands(state: delegate.state, actions: delegate.actions)
        }
    }
}
