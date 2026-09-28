import AppKit
import Combine
import ServiceManagement
import SwiftUI

// Жизнь приложения за пределами окон: диктовка (Controller), значок в строке
// меню, разрешения. Окна - сцены SwiftUI в FlowLocalApp.
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    let state = AppState()
    private lazy var controller = Controller(state: state)
    private(set) lazy var actions = makeActions()
    private var statusItem: NSStatusItem?
    private var statusVisibility: NSKeyValueObservation?
    private var bag = Set<AnyCancellable>()
    private var permissionTimer: Timer?

    override init() {
        super.init()
        // Упавший бэкенд закрывает свой конец трубы; без этого запись в неё
        // убила бы приложение сигналом вместо ошибки, которую мы ловим.
        signal(SIGPIPE, SIG_IGN)
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        state.launchAtLogin = SMAppService.mainApp.status == .enabled
        // Звук удалённых диктовок держали до перезапуска ради «Отменить».
        if state.historyLoaded {
            AudioStore.purge(keeping: Set(state.history.compactMap(\.audio)))
        }
        state.pruneHistory()
        applyAppearance()
        setupStatusItem()
        controller.start()
        HubSync.start(state) { [weak self] on in self?.setLaunchAtLogin(on) }

        if Recorder.permission == .notDetermined {
            Recorder.requestPermission { [weak self] _ in self?.state.refreshPermissions() }
        }
        if !Inserter.trusted {
            Inserter.requestTrust()
        }
        // Права - опросом (уведомлений об их смене нет), и только пока
        // какого-то не хватает: выдали оба - опрашивать нечего. Отозвать
        // можно, но это видно при следующей вставке и при активации окна.
        // Микрофоны - по уведомлению CoreAudio, а не опросом раз в 2 с.
        permissionTimer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let state = self?.state, !(state.micGranted && state.axTrusted) else { return }
                state.refreshPermissions()
            }
        }
        permissionTimer?.tolerance = 0.5
        NotificationCenter.default.addObserver(forName: NSApplication.didBecomeActiveNotification,
                                               object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.state.refreshPermissions() }
        }
        AudioDevices.onChange { [weak self] in
            MainActor.assumeIsolated { self?.state.refreshDevices() }
        }

        state.$phase.sink { [weak self] p in self?.updateStatusIcon(p) }.store(in: &bag)
        state.$appearance.dropFirst().sink { [weak self] _ in
            DispatchQueue.main.async { self?.applyAppearance() }
        }.store(in: &bag)
        state.$showMenuBarIcon.dropFirst().sink { [weak self] on in
            DispatchQueue.main.async { self?.statusItem?.isVisible = on }
        }.store(in: &bag)
        state.$showInDock.dropFirst().sink { [weak self] _ in
            DispatchQueue.main.async { self?.applyDockPolicy() }
        }.store(in: &bag)
        // Сочетания меняют в Hub Settings - перерегистрируем.
        state.$hotkey.dropFirst().map { _ in () }.merge(with: state.$toggleHotkey.dropFirst().map { _ in () })
            .sink { [weak self] in
                DispatchQueue.main.async { self?.controller.bindHotkeys() }
            }.store(in: &bag)
        Log.write("FlowLocal запущен, «Универсальный доступ»: \(Inserter.trusted ? "есть" : "нет")")
    }

    // Щелчок по значку в Доке, когда окон не видно, - открыть главное окно.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { SceneBridge.showMain() }
        return true
    }

    // Закрыли последнее окно - приложение остаётся: диктовка работает из
    // любого приложения, завершает только ⌘Q.
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    func applicationWillTerminate(_ notification: Notification) {
        AppState.flushHistory()
        controller.backend.stop()
    }

    private func makeActions() -> AppActions {
        AppActions(
            toggleDictation: { [weak self] in self?.controller.toggleDictation() },
            cancelDictation: { [weak self] in self?.controller.cancelDictation() },
            paste: { [weak self] entry in self?.controller.paste(entry) },
            rerecognize: { [weak self] entry in self?.controller.rerecognize(entry) },
            play: { [weak self] entry in self?.controller.play(entry) },
            openLog: { NSWorkspace.shared.open(Log.fileURL) },
            openRecordings: { NSWorkspace.shared.open(AudioStore.dir) },
            openSettings: { HubSync.openSettings() },
            showMain: { SceneBridge.showMain() },
            find: { [weak self] in
                self?.state.tab = .dictations
                SceneBridge.showMain()
                self?.state.searchFocusRequest += 1
            })
    }

    private func applyAppearance() {
        NSApp.appearance = state.appearance.nsAppearance
    }

    /// Без значка в Доке приложение живёт в строке меню. Оба сразу спрятать
    /// нельзя - иначе до окна не добраться: это правило держит HubSync.
    private func applyDockPolicy() {
        NSApp.setActivationPolicy(state.showInDock ? .regular : .accessory)
        if !state.showInDock {
            DispatchQueue.main.async { SceneBridge.showMain() }
        }
    }

    private func setLaunchAtLogin(_ on: Bool) {
        do {
            if on {
                try SMAppService.mainApp.register()
            } else {
                try SMAppService.mainApp.unregister()
            }
        } catch {
            Log.write("запуск при входе: \(error.localizedDescription)")
        }
        state.launchAtLogin = SMAppService.mainApp.status == .enabled
        UserDefaults.standard.set(state.launchAtLogin, forKey: "launchAtLogin")
        if state.launchAtLogin != on { HubSync.announce() }
    }

    // MARK: - значок в строке меню

    private func setupStatusItem() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        // Значок можно убрать ⌘-перетаскиванием из строки меню - и он не
        // вернётся: снятие пишется в настройку «Значок в строке меню».
        item.autosaveName = "FlowLocalStatusItem"
        item.behavior = .removalAllowed
        let menu = NSMenu()
        menu.autoenablesItems = false
        menu.delegate = self
        item.menu = menu
        statusItem = item
        item.isVisible = state.showMenuBarIcon
        updateStatusIcon(.idle)
        statusVisibility = item.observe(\.isVisible, options: [.new]) { [weak self] _, change in
            guard let visible = change.newValue else { return }
            DispatchQueue.main.async {
                guard let self, visible != self.state.showMenuBarIcon else { return }
                self.state.showMenuBarIcon = visible
                HubSync.announce()
            }
        }
        if !state.showInDock { NSApp.setActivationPolicy(.accessory) }
    }

    // Меню собирается при каждом открытии: первая строка - состояние сейчас.
    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        let status = NSMenuItem(title: state.statusText, action: nil, keyEquivalent: "")
        status.isEnabled = false
        menu.addItem(status)
        menu.addItem(.separator())
        let dictation = item(state.isRecording ? "Закончить диктовку" : "Начать диктовку", #selector(toggleDictation))
        dictation.isEnabled = state.isRecording || state.canDictate
        menu.addItem(dictation)
        menu.addItem(.separator())
        menu.addItem(item("Открыть Flow Local", #selector(openMain)))
        menu.addItem(item("Настройки…", #selector(openSettings), key: ","))
        menu.addItem(.separator())
        let quit = NSMenuItem(title: "Завершить Flow Local", action: #selector(NSApplication.terminate(_:)),
                              keyEquivalent: "q")
        menu.addItem(quit)
    }

    private func item(_ title: String, _ action: Selector, key: String = "") -> NSMenuItem {
        let item = NSMenuItem(title: title, action: action, keyEquivalent: key)
        item.target = self
        return item
    }

    @objc private func toggleDictation() { controller.toggleDictation() }
    @objc private func openMain() { SceneBridge.showMain() }
    @objc private func openSettings() { HubSync.openSettings() }

    private func updateStatusIcon(_ phase: Phase) {
        let name: String
        switch phase {
        case .recording: name = "mic.fill"
        case .processing: name = "ellipsis.circle"
        default: name = "waveform"
        }
        let image = NSImage(systemSymbolName: name, accessibilityDescription: "Flow Local")
        image?.isTemplate = true
        statusItem?.button?.image = image
    }
}
