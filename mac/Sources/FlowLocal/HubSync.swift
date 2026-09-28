import AppKit

// Настройки Flow живут в Hub Settings (apps/hub-settings): своего окна настроек у Flow нет. Хаб меняет
// их прямо в UserDefaults Flow и присылает распределённое уведомление "com.roman.suite.flow.settings".
// Здесь Flow перечитывает их на лету, без перезапуска: свойства AppState меняются со всеми реакциями.
// Если Flow поправил настройку сам (вход в систему не включился), он отвечает
// уведомлением "….changed", и хаб показывает то, что есть на самом деле.
@MainActor
enum HubSync {
    static let notification = Notification.Name("com.roman.suite.flow.settings")
    private static let changed = Notification.Name("com.roman.suite.flow.settings.changed")
    private static let hubBundleID = "com.roman.hub-settings"
    private static var observer: NSObjectProtocol?
    private static weak var state: AppState?
    private static var setLaunchAtLogin: (Bool) -> Void = { _ in }

    static func start(_ state: AppState, setLaunchAtLogin: @escaping (Bool) -> Void) {
        self.state = state
        self.setLaunchAtLogin = setLaunchAtLogin
        // Хаб видит, включён ли вход в систему на самом деле.
        UserDefaults.standard.set(state.launchAtLogin, forKey: "launchAtLogin")
        // Состояние берём из статического свойства, а не из замыкания: AppState не Sendable.
        observer = DistributedNotificationCenter.default().addObserver(
            forName: notification, object: nil, queue: .main
        ) { _ in
            MainActor.assumeIsolated { HubSync.reload() }
        }
    }

    private static func reload() {
        guard let state else { return }
        let corrected = state.reloadHubSettings()
        if let wanted = UserDefaults.standard.object(forKey: "launchAtLogin") as? Bool, wanted != state.launchAtLogin {
            setLaunchAtLogin(wanted)
        }
        if corrected { announce() }
    }

    /// Flow поменял настройку сам - хаб перечитает её.
    static func announce() {
        UserDefaults.standard.synchronize()
        DistributedNotificationCenter.default().postNotificationName(changed, object: nil, userInfo: nil,
                                                                     deliverImmediately: true)
    }

    /// ⌘, и «Настройки…»: открыть Hub Settings сразу на модуле Flow.
    static func openSettings() {
        guard let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: hubBundleID) else {
            let alert = NSAlert()
            alert.messageText = "Hub Settings не установлен"
            alert.informativeText = "Настройки Flow Local теперь в приложении Hub Settings. Установите его: apps/hub-settings, ./build.sh install."
            alert.runModal()
            return
        }
        // Не запущен - откроется на последнем модуле из своих настроек; запущен - переключится по уведомлению.
        let domain = hubBundleID as CFString
        CFPreferencesSetAppValue("selection" as CFString, "flow" as CFString, domain)
        CFPreferencesAppSynchronize(domain)
        DistributedNotificationCenter.default().postNotificationName(
            Notification.Name("com.roman.suite.hub.show"), object: "flow", userInfo: nil, deliverImmediately: true)
        NSWorkspace.shared.openApplication(at: url, configuration: NSWorkspace.OpenConfiguration())
    }
}

extension AppState {
    /// Все настройки из UserDefaults. Меняются только те, что правда отличаются: иначе лишний раз
    /// сработали бы реакции (тема, значок в Доке, хоткеи). true - Flow поправил что-то сам.
    func reloadHubSettings() -> Bool {
        let d = UserDefaults.standard
        d.synchronize()
        func bool(_ key: String) -> Bool? { d.object(forKey: key) as? Bool }
        func text(_ key: String) -> String? { d.string(forKey: key) }

        if let v = bool("insertAutomatically"), v != insertAutomatically { insertAutomatically = v }
        if let v = bool("addSpace"), v != addSpace { addSpace = v }
        if let v = bool("keepInClipboard"), v != keepInClipboard { keepInClipboard = v }
        if let v = bool("sounds"), v != sounds { sounds = v }
        if let v = bool("saveAudio"), v != saveAudio { saveAudio = v }
        if let v = bool("showPill"), v != showPill { showPill = v }
        if let v = bool("pillShowDot"), v != pillShowDot { pillShowDot = v }
        if let v = bool("pillShowTimer"), v != pillShowTimer { pillShowTimer = v }
        if let v = bool("pillShowWave"), v != pillShowWave { pillShowWave = v }
        if let v = bool("pillLiveText"), v != pillLiveText { pillLiveText = v }
        if let v = bool("pillShowStatus"), v != pillShowStatus { pillShowStatus = v }
        if let v = bool("removeRepeats"), v != removeRepeats { removeRepeats = v }
        if let v = bool("capitalize"), v != capitalize { capitalize = v }
        if let v = bool("trailingPeriod"), v != trailingPeriod { trailingPeriod = v }
        if let v = bool("showMenuBarIcon"), v != showMenuBarIcon { showMenuBarIcon = v }
        if let v = bool("showInDock"), v != showInDock { showInDock = v }
        if let v = text("langMode").flatMap(LangMode.init(rawValue:)), v != langMode { langMode = v }
        if let v = text("appearance").flatMap(AppAppearance.init(rawValue:)), v != appearance { appearance = v }
        if let v = text("pillPosition").flatMap(PillPosition.init(rawValue:)), v != pillPosition { pillPosition = v }
        if let v = text("pillSize").flatMap(PillSize.init(rawValue:)), v != pillSize { pillSize = v }
        if let v = text("pillTextWidth").flatMap(PillTextWidth.init(rawValue:)), v != pillTextWidth { pillTextWidth = v }
        if let v = text("cleanupLevel").flatMap(CleanupLevel.init(rawValue:)), v != cleanupLevel { cleanupLevel = v }
        if let v = text("customFillers"), v != customFillers { customFillers = v }
        if let v = Self.days(d.object(forKey: "historyDays")), v != historyDays { historyDays = v }
        let mic = text("micUID").flatMap { $0.isEmpty ? nil : $0 }
        if mic != micUID { micUID = mic }
        if let v = Replacement.load(d.object(forKey: "replacements")),
           Replacement.pairs(v) != Replacement.pairs(replacements) { replacements = v }
        let hold = HotkeyPreset.load(.hold)
        if !hold.same(as: hotkey) { hotkey = hold }
        let toggle = HotkeyPreset.load(.toggle)
        if !toggle.same(as: toggleHotkey) { toggleHotkey = toggle }

        // Оба значка можно спрятать: окно открывается повторным запуском Flow
        // из Spotlight или «Программ» (applicationShouldHandleReopen), а
        // диктовка работает по сочетаниям. Раньше здесь значок в строке меню
        // возвращался насильно - и убрать его было нельзя.
        return false
    }
}
