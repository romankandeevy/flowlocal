import AppKit
import Combine
import ServiceManagement
import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate {
    let state = AppState()
    private lazy var controller = Controller(state: state)
    private var window: NSWindow?
    private var statusItem: NSStatusItem?
    private var bag = Set<AnyCancellable>()
    private var permissionTimer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.appearance = NSAppearance(named: .darkAqua)
        NSApp.mainMenu = buildMainMenu()
        state.launchAtLogin = SMAppService.mainApp.status == .enabled
        setupStatusItem()
        controller.start()
        showWindow()

        if Recorder.permission == .notDetermined {
            Recorder.requestPermission { [weak self] _ in self?.state.refreshPermissions() }
        }
        if !Inserter.trusted {
            Inserter.requestTrust()
        }
        permissionTimer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            self?.state.refreshPermissions()
            self?.state.refreshDevices()
        }

        state.$phase.sink { [weak self] p in self?.updateStatusIcon(p) }.store(in: &bag)
        Log.write("FlowLocal запущен, «Универсальный доступ»: \(Inserter.trusted ? "есть" : "нет")")
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        showWindow()
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    func applicationWillTerminate(_ notification: Notification) {
        controller.backend.stop()
    }

    // MARK: - окно

    // Окно 1100x720, тянется. Заголовок прозрачный, а пустая унифицированная
    // панель инструментов делает его высотой 52 - ровно под строку заголовка
    // сцены; «светофоры» встают над сайдбаром, как в Finder и System Settings.
    @objc func showWindow() {
        if window == nil {
            let view = MainView(actions: makeActions()).environmentObject(state)
            let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1100, height: 720),
                             styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                             backing: .buffered, defer: false)
            w.title = "Flow Local"
            w.titleVisibility = .hidden
            w.titlebarAppearsTransparent = true
            let toolbar = NSToolbar(identifier: "FlowLocalMain")
            toolbar.showsBaselineSeparator = false
            w.toolbar = toolbar
            w.toolbarStyle = .unified
            w.isMovableByWindowBackground = true
            w.isReleasedWhenClosed = false
            w.minSize = NSSize(width: 680, height: 540)
            w.contentView = NSHostingView(rootView: view)
            w.center()
            // v3: раскладка с сайдбаром шире прежней - старый размер окна не берём.
            w.setFrameAutosaveName("FlowLocalMain.v3")
            window = w
            applyDarkAppearance()
        }
        NSApp.activate(ignoringOtherApps: true)
        window?.makeKeyAndOrderFront(nil)
    }

    @objc private func openSettings() {
        state.tab = .settings
        showWindow()
    }

    private func makeActions() -> AppActions {
        AppActions(
            beginCapture: { [weak self] role in self?.controller.beginHotkeyCapture(role) },
            cancelCapture: { [weak self] in self?.controller.endHotkeyCapture() },
            resetHotkey: { [weak self] role in self?.controller.resetHotkey(role) },
            cancelProcessing: { [weak self] in self?.controller.cancelProcessing() },
            paste: { [weak self] entry in self?.controller.paste(entry) },
            rerecognize: { [weak self] entry in self?.controller.rerecognize(entry) },
            play: { [weak self] entry in self?.controller.play(entry) },
            setLaunchAtLogin: { [weak self] on in self?.setLaunchAtLogin(on) },
            openLog: { NSWorkspace.shared.open(Log.fileURL) },
            openRecordings: { NSWorkspace.shared.open(AudioStore.dir) },
            selectMic: { [weak self] uid in self?.state.micUID = uid })
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
    }

    // Только тёмная тема (Apple System Dark) - переключателя нет. Фон окна -
    // #000000, как systemBackground в дизайн-системе.
    private func applyDarkAppearance() {
        let dark = NSAppearance(named: .darkAqua)
        NSApp.appearance = dark
        window?.appearance = dark
        window?.backgroundColor = .black
    }

    // MARK: - строка меню

    private func setupStatusItem() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        let menu = NSMenu()
        menu.addItem(withTitle: "Открыть Flow Local", action: #selector(showWindow), keyEquivalent: "").target = self
        menu.addItem(withTitle: "Настройки…", action: #selector(openSettings), keyEquivalent: ",").target = self
        menu.addItem(.separator())
        menu.addItem(withTitle: "Выйти", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        item.menu = menu
        statusItem = item
        updateStatusIcon(.idle)
        applyDarkAppearance()
    }

    private func updateStatusIcon(_ phase: Phase) {
        let name: String
        switch phase {
        case .recording: name = "mic.fill"
        case .processing: name = "ellipsis.circle"
        default: name = "waveform"
        }
        let img = NSImage(systemSymbolName: name, accessibilityDescription: "Flow Local")
        img?.isTemplate = true
        statusItem?.button?.image = img
    }

    // MARK: - главное меню (⌘, ⌘Q, ⌘W, ⌘C/V в полях)

    private func buildMainMenu() -> NSMenu {
        let main = NSMenu()

        let appItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "О программе Flow Local",
                        action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Настройки…", action: #selector(openSettings), keyEquivalent: ",").target = self
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Скрыть Flow Local", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Выйти из Flow Local", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        main.addItem(appItem)

        let editItem = NSMenuItem()
        let edit = NSMenu(title: "Правка")
        edit.addItem(withTitle: "Отменить", action: Selector(("undo:")), keyEquivalent: "z")
        edit.addItem(.separator())
        edit.addItem(withTitle: "Вырезать", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "Скопировать", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "Вставить", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "Выделить всё", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = edit
        main.addItem(editItem)

        let winItem = NSMenuItem()
        let win = NSMenu(title: "Окно")
        win.addItem(withTitle: "Закрыть", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        win.addItem(withTitle: "Свернуть", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        winItem.submenu = win
        main.addItem(winItem)
        return main
    }
}
