import AppKit
import Carbon.HIToolbox
import SwiftUI

// Обучение - отдельное окно при первом запуске: десять шагов слева, шаг
// справа, «Назад / Далее» внизу. Не только рассказывает, но и настраивает:
// разрешения, клавиши, язык, стиль приложений, словарь, тему, автозапуск -
// чтобы потом не искать это в настройках. Python и модели качаются с первого
// экрана в фоне (Controller.startBackend), по шагам можно идти не дожидаясь.
// Любой шаг можно пропустить; открыть снова - меню FlowLocal → «Обучение».
// Макет: https://claude.ai/artifact/RjJrhC5BqTAPxMoNJzKmtB

/// Что обучению нужно от приложения помимо AppState.
struct TutorialHooks {
    var bindHotkeys: () -> Void = {}
    var unbindHotkeys: () -> Void = {}
    var cancelDictation: () -> Void = {}
    var setLaunchAtLogin: (Bool) -> Void = { _ in }
    var finished: () -> Void = {}
}

@MainActor
enum TutorialWindow {
    private static var window: NSWindow?
    private static var closeObserver: NSObjectProtocol?
    static let doneKey = "tutorialDone"

    /// Показывать само при запуске: ещё не проходили и диктовок нет (у тех,
    /// кто обновился с прошлой версии, история есть - им не нужно).
    static func shouldShowOnLaunch(_ state: AppState) -> Bool {
        !UserDefaults.standard.bool(forKey: doneKey) && state.history.isEmpty
    }

    static func show(state: AppState, hooks: TutorialHooks) {
        if let window {
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
            return
        }
        var hooks = hooks
        let userFinished = hooks.finished
        hooks.finished = {
            UserDefaults.standard.set(true, forKey: doneKey)
            window?.close()
            userFinished()
        }
        let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1000, height: 660),
                         styleMask: [.titled, .closable, .fullSizeContentView],
                         backing: .buffered, defer: false)
        w.titlebarAppearsTransparent = true
        w.titleVisibility = .hidden
        w.title = "Обучение Flow Local"
        w.isMovableByWindowBackground = true
        w.isReleasedWhenClosed = false
        w.contentView = NSHostingView(rootView: TutorialView(hooks: hooks).environmentObject(state))
        w.center()
        window = w
        // Закрыли крестиком - тоже «пройдено»: открыть снова можно из меню,
        // а навязываться при каждом запуске не стоит.
        closeObserver = NotificationCenter.default.addObserver(forName: NSWindow.willCloseNotification,
                                                               object: w, queue: .main) { _ in
            MainActor.assumeIsolated {
                UserDefaults.standard.set(true, forKey: doneKey)
                state.tutorialPractice = false
                if let o = closeObserver { NotificationCenter.default.removeObserver(o) }
                closeObserver = nil
                window = nil
            }
        }
        w.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}

// MARK: - шаги

private enum TStep: Int, CaseIterable, Identifiable {
    case hello, permissions, keys, recognition, practice, styles, code, dictionary, tips, done
    var id: Int { rawValue }
    var title: String {
        switch self {
        case .hello: return "Привет"
        case .permissions: return "Разрешения"
        case .keys: return "Клавиши"
        case .recognition: return "Распознавание"
        case .practice: return "Первая диктовка"
        case .styles: return "Стиль под приложения"
        case .code: return "Код голосом"
        case .dictionary: return "Словарь и правки"
        case .tips: return "Ещё полезное"
        case .done: return "Готово"
        }
    }
}

struct TutorialView: View {
    @EnvironmentObject var state: AppState
    let hooks: TutorialHooks
    @State private var step: TStep = .hello
    @StateObject private var models = ModelProgress()

    var body: some View {
        HStack(spacing: 0) {
            rail
            VStack(spacing: 0) {
                ScrollView {
                    content
                        .padding(.horizontal, 56)
                        .padding(.top, 44)
                        .padding(.bottom, 24)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .id(step)
                // Прежний шаг уходит сразу, новый проступает: без наложения.
                .transition(.asymmetric(insertion: .opacity, removal: .identity))
                footer
                    .transaction { $0.animation = nil }
            }
            .background(NL.canvas)
        }
        .frame(width: 1000, height: 660)
        .onAppear { models.start() }
        .onDisappear { models.stop(); state.tutorialPractice = false }
        .onChange(of: step) { _, new in state.tutorialPractice = new == .practice }
    }

    // MARK: рельс слева

    private var rail: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("ОБУЧЕНИЕ")
                .font(NLFont.ui(11, .semibold))
                .tracking(0.9)
                .foregroundStyle(NL.textTertiary)
                .padding(.horizontal, 10)
                .padding(.top, 44)
                .padding(.bottom, 10)
            ForEach(TStep.allCases) { s in
                Button { go(s) } label: {
                    HStack(spacing: 10) {
                        ZStack {
                            if s == step {
                                Circle().fill(NL.accent)
                                Text("\(s.rawValue + 1)").foregroundStyle(NL.textOnAccent)
                            } else if s.rawValue < step.rawValue {
                                Circle().fill(NL.accentSubtle)
                                Image(systemName: "checkmark").font(.system(size: 9, weight: .bold)).foregroundStyle(NL.textAccent)
                            } else {
                                Circle().strokeBorder(NL.borderStrong, lineWidth: 1.5)
                                Text("\(s.rawValue + 1)").foregroundStyle(NL.textSecondary)
                            }
                        }
                        .font(NLFont.ui(10.5, .semibold))
                        .frame(width: 20, height: 20)
                        Text(s.title)
                            .font(NLFont.ui(13.5, s == step ? .semibold : .regular))
                            .lineLimit(1)
                            .minimumScaleFactor(0.85)
                            .foregroundStyle(s == step ? NL.textAccent : s.rawValue < step.rawValue ? NL.textPrimary : NL.textSecondary)
                        Spacer(minLength: 0)
                    }
                    .padding(.horizontal, 10)
                    .frame(height: 32)
                    .background(s == step ? NL.accentSubtle : .clear, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
            Spacer()
            if step != .recognition, let note = preparingNote {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Готовлю распознавание").font(NLFont.ui(12, .semibold)).foregroundStyle(NL.textPrimary)
                    Text(note.text).font(NLFont.ui(12)).foregroundStyle(NL.textSecondary).fixedSize(horizontal: false, vertical: true)
                    ProgressBar(value: note.fraction)
                }
                .padding(10)
                .nlCard(padding: 0, radius: 10)
                .padding(.top, 8)
            }
        }
        .padding(.horizontal, 14)
        .padding(.bottom, 18)
        .frame(width: 232)
        .frame(maxHeight: .infinity, alignment: .top)
        .background(NL.sidebar)
        .overlay(alignment: .trailing) { NL.sidebarBorder.frame(width: 1) }
    }

    /// Что сейчас готовится - для карточки внизу рельса. nil - всё готово.
    private var preparingNote: (text: String, fraction: Double?)? {
        if let s = state.setupStep {
            switch s {
            case .downloading(let f): return ("Скачиваю Python\(f.map { " — \(Int($0 * 100))%" } ?? "")", f)
            case .unpacking: return ("Распаковываю Python", nil)
            case .installing: return ("Ставлю библиотеки", nil)
            }
        }
        if case .failed = state.backend { return ("Не получилось — подробности на шаге 4", nil) }
        if state.backend != .ready { return ("Модель для русского — \(Int(models.ru * 100))%", models.ru) }
        if !state.englishReady { return ("Модель для английского — \(Int(models.en * 100))%", models.en) }
        return nil
    }

    // MARK: низ

    private var footer: some View {
        HStack(spacing: 10) {
            Text("Шаг \(step.rawValue + 1) из \(TStep.allCases.count)")
                .font(NLFont.ui(12.5))
                .foregroundStyle(NL.textTertiary)
            Spacer()
            if step == .hello {
                Button("Пропустить обучение") { go(.done) }.buttonStyle(.plain)
                    .font(NLFont.ui(14, .medium)).foregroundStyle(NL.textSecondary).padding(.horizontal, 12)
            } else {
                Button("Назад") { go(TStep(rawValue: step.rawValue - 1) ?? .hello) }.buttonStyle(.plain)
                    .font(NLFont.ui(14, .medium)).foregroundStyle(NL.textSecondary).padding(.horizontal, 12)
                    .keyboardShortcut(.leftArrow, modifiers: [.command])
            }
            Button(step == .hello ? "Начать" : step == .done ? "Начать диктовать" : "Далее") {
                if step == .done { hooks.finished() } else { go(TStep(rawValue: step.rawValue + 1) ?? .done) }
            }
            .buttonStyle(AccentButtonStyle())
            .keyboardShortcut(.defaultAction)
        }
        .padding(.leading, 56)
        .padding(.trailing, 28)
        .frame(height: 68)
        .overlay(alignment: .top) { NL.sidebarBorder.frame(height: 1) }
    }

    private func go(_ s: TStep) {
        withMotion(Motion.base) { step = s }
    }

    // MARK: шаг

    @ViewBuilder
    private var content: some View {
        switch step {
        case .hello: HelloStep()
        case .permissions: PermissionsStep()
        case .keys: KeysStep(hooks: hooks)
        case .recognition: RecognitionStep(models: models)
        case .practice: PracticeStep(models: models)
        case .styles: StylesStep()
        case .code: CodeStep()
        case .dictionary: DictionaryStep()
        case .tips: TipsStep()
        case .done: DoneStep(hooks: hooks)
        }
    }
}

// MARK: - общие кусочки

private struct StepTitle: View {
    let title: String
    var subtitle: String?
    var kicker: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let kicker {
                Text(kicker).font(NLFont.ui(13, .semibold)).foregroundStyle(NL.textAccent)
            }
            Text(title)
                .font(NLFont.ui(30, .heavy))
                .tracking(-0.6)
                .foregroundStyle(NL.textPrimary)
                .fixedSize(horizontal: false, vertical: true)
            if let subtitle {
                Text(.init(subtitle))
                    .font(NLFont.ui(15))
                    .lineSpacing(3)
                    .foregroundStyle(NL.textSecondary)
                    .frame(maxWidth: 620, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.bottom, 6)
    }
}

/// Клавиши сочетания капсулами: ⌃ ⇧ Пробел.
struct TutorialKeys: View {
    let keys: [String]
    var lit = false

    var body: some View {
        HStack(spacing: 4) {
            ForEach(Array(keys.enumerated()), id: \.offset) { _, k in
                Text(KeyGlyph.short(k))
                    .font(NLFont.ui(12.5, .semibold))
                    .foregroundStyle(lit ? NL.textOnAccent : NL.textPrimary)
                    .padding(.horizontal, 7)
                    .frame(minWidth: 26, minHeight: 26)
                    .background(lit ? NL.accent : NL.surface, in: RoundedRectangle(cornerRadius: 7, style: .continuous))
                    .overlay { RoundedRectangle(cornerRadius: 7, style: .continuous).strokeBorder(lit ? .clear : NL.borderStrong) }
            }
        }
    }
}

private struct ProgressBar: View {
    let value: Double?

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(NL.chartBar)
                if let value {
                    Capsule().fill(NL.accent).frame(width: max(4, geo.size.width * min(1, max(0, value))))
                } else {
                    Capsule().fill(NL.accent.opacity(0.5)).frame(width: geo.size.width * 0.3)
                }
            }
        }
        .frame(height: 4)
        .animation(Motion.moderate, value: value)
    }
}

private struct AccentButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(NLFont.ui(14, .semibold))
            .foregroundStyle(NL.textOnAccent)
            .padding(.horizontal, 20)
            .frame(height: 38)
            .background(configuration.isPressed ? NL.accentActive : NL.accent,
                        in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            .contentShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }
}

/// Строка карточки: значок/номер слева, текст, действие справа.
private struct CardRow<Leading: View, Trailing: View>: View {
    let title: String
    let detail: String
    @ViewBuilder var leading: () -> Leading
    @ViewBuilder var trailing: () -> Trailing

    var body: some View {
        HStack(spacing: 16) {
            leading()
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(NLFont.ui(15.5, .semibold)).foregroundStyle(NL.textPrimary)
                Text(detail).font(NLFont.ui(13.5)).foregroundStyle(NL.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 12)
            trailing()
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
    }
}

private struct DoneMark: View {
    let done: Bool
    let number: Int
    var size: CGFloat = 34

    var body: some View {
        ZStack {
            if done {
                Circle().fill(NL.accent)
                Image(systemName: "checkmark").font(.system(size: size * 0.38, weight: .bold)).foregroundStyle(NL.textOnAccent)
            } else {
                Circle().strokeBorder(NL.borderStrong, lineWidth: 1.5)
                Text("\(number)").font(NLFont.ui(size * 0.4, .semibold)).foregroundStyle(NL.textSecondary)
            }
        }
        .frame(width: size, height: size)
        .animation(Motion.base, value: done)
    }
}

private struct Tip: View {
    let title: String
    let text: String
    var key: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(title).font(NLFont.ui(15, .semibold)).foregroundStyle(NL.textPrimary)
                Spacer()
                if let key {
                    Text(key).font(NLFont.ui(12.5, .semibold)).foregroundStyle(NL.textPrimary)
                        .padding(.horizontal, 7).padding(.vertical, 3)
                        .background(NL.subtle, in: RoundedRectangle(cornerRadius: 6, style: .continuous))
                }
            }
            Text(text).font(NLFont.ui(13.5)).lineSpacing(2).foregroundStyle(NL.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .nlCard(padding: 0)
    }
}

// MARK: - 1. Привет

private struct HelloStep: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            StepTitle(title: "Зажали. Сказали. Отпустили.",
                      subtitle: "FlowLocal превращает голос в текст в любом окне — в мессенджере, почте, редакторе кода. Распознавание работает прямо на этом Маке: без интернета, аккаунта и облака.",
                      kicker: "Добро пожаловать")
            HStack(alignment: .top, spacing: 12) {
                Tip(title: "1. Зажали клавиши", text: "В любом поле, где стоит курсор.")
                Tip(title: "2. Сказали", text: "Внизу экрана — чёрная капсула: идёт запись, рядом время.")
                Tip(title: "3. Отпустили", text: "Через 0,1 с текст уже в поле — со знаками и без «ну».")
            }
            .frame(height: 104)
            HStack(spacing: 12) {
                TutorialKeys(keys: state.hotkey.keys, lit: true)
                Text("— ваше сочетание. Поменять можно на шаге 3.").font(NLFont.ui(13.5)).foregroundStyle(NL.textSecondary)
            }
            Text("Дальше — 9 коротких шагов: разрешения, клавиши, первая диктовка и всё, что умеет FlowLocal. Около трёх минут. Любой шаг можно пропустить.")
                .font(NLFont.ui(13.5)).foregroundStyle(NL.textTertiary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

// MARK: - 2. Разрешения

private struct PermissionsStep: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            StepTitle(title: "Два разрешения — и больше вопросов не будет",
                      subtitle: "macOS спрашивает про них один раз. Нажмите «Разрешить» — откроются настройки, включите там FlowLocal и вернитесь сюда: галочка появится сама.")
            VStack(spacing: 0) {
                CardRow(title: "Микрофон", detail: "Слушает, только пока вы держите клавиши. Звук никуда не уходит.") {
                    DoneMark(done: state.micGranted, number: 1)
                } trailing: {
                    if state.micGranted { Text("Готово").font(NLFont.ui(13.5, .semibold)).foregroundStyle(NL.textAccent) }
                    else { Button("Разрешить") { openMicrophoneAccess(state) }.buttonStyle(InkButtonStyle()) }
                }
                NL.borderSubtle.frame(height: 1)
                CardRow(title: "Универсальный доступ", detail: "Чтобы текст сам вставлялся туда, где курсор. Без него диктовка ляжет в буфер обмена — ⌘V руками.") {
                    DoneMark(done: state.axTrusted, number: 2)
                } trailing: {
                    if state.axTrusted { Text("Готово").font(NLFont.ui(13.5, .semibold)).foregroundStyle(NL.textAccent) }
                    else { Button("Разрешить", action: openAccessibilityAccess).buttonStyle(InkButtonStyle()) }
                }
            }
            .nlCard(padding: 0)
            if !state.axTrusted {
                HStack(alignment: .top, spacing: 12) {
                    Image(systemName: "exclamationmark.circle.fill").foregroundStyle(NL.warning)
                    Text("Тумблер включён, а галочки нет? Нажмите «Разрешить» ещё раз — FlowLocal уберёт старую запись (после обновлений она перестаёт работать), и macOS заведёт новую.")
                        .font(NLFont.ui(13.5)).foregroundStyle(NL.textWarning)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(NL.warningSubtle, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                Text("Системные настройки → Конфиденциальность и безопасность → Универсальный доступ → FlowLocal")
                    .font(NLFont.ui(12.5)).foregroundStyle(NL.textTertiary)
            }
        }
    }
}

// MARK: - 3. Клавиши

private struct KeysStep: View {
    @EnvironmentObject var state: AppState
    let hooks: TutorialHooks
    @State private var recording: HotkeyRole?
    @State private var monitor: Any?
    @State private var heard: HotkeyRole?

    private static let togglePresets: [HotkeyPreset] = [
        HotkeyPreset.toggleDefault,
        HotkeyPreset(id: "ctrl-opt-space", keyCode: UInt32(kVK_Space), modifiers: UInt32(controlKey | optionKey),
                     keys: ["CTRL", "OPTION", "SPACE"]),
    ]
    private static let off = HotkeyPreset(id: "off", keyCode: UInt32(kVK_Space), modifiers: 0, keys: [])

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            StepTitle(title: "Выберите клавиши для диктовки",
                      subtitle: "Два способа, можно пользоваться обоими. Нажмите сочетание прямо сейчас — оно загорится, значит работает.")
            roleCard(.hold, title: "Удерживать и говорить", hint: "для коротких фраз: держите — говорите — отпустите",
                     presets: HotkeyPreset.all, current: state.hotkey)
            roleCard(.toggle, title: "Нажать один раз", hint: "для длинной речи: нажали — говорите сколько угодно — нажали ещё раз",
                     presets: Self.togglePresets, current: state.toggleHotkey, allowOff: true)
            (Text("Esc").font(NLFont.ui(13, .semibold)).foregroundStyle(NL.textPrimary)
             + Text(" — отменить запись в любой момент. Сменить клавиши потом можно в настройках (⌘,).").font(NLFont.ui(13)).foregroundStyle(NL.textTertiary))
        }
        // Нажали сочетание - запись началась: показываем «работает» и сразу
        // отменяем, вставлять тут нечего.
        .onChange(of: state.phase) { _, phase in
            guard case let .recording(_, locked) = phase else { return }
            heard = locked ? .toggle : .hold
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { hooks.cancelDictation() }
        }
        .onDisappear { stopRecording() }
    }

    private func roleCard(_ role: HotkeyRole, title: String, hint: String, presets: [HotkeyPreset],
                          current: HotkeyPreset, allowOff: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(title).font(NLFont.ui(16, .semibold)).foregroundStyle(NL.textPrimary)
                Text(hint).font(NLFont.ui(13)).foregroundStyle(NL.textTertiary)
            }
            HStack(spacing: 8) {
                ForEach(presets) { p in
                    chip(selected: current.same(as: p) && current.isEnabled) { TutorialKeys(keys: p.keys) } action: { set(role, p) }
                }
                let custom = current.isEnabled && !presets.contains { $0.same(as: current) }
                chip(selected: custom || recording == role, dashed: !custom) {
                    if recording == role {
                        Text("Нажмите сочетание…").font(NLFont.ui(13.5, .medium)).foregroundStyle(NL.textAccent)
                    } else if custom {
                        TutorialKeys(keys: current.keys)
                    } else {
                        Text("Своё сочетание…").font(NLFont.ui(13.5)).foregroundStyle(NL.textSecondary)
                    }
                } action: { startRecording(role) }
                if allowOff {
                    chip(selected: !current.isEnabled) {
                        Text("Не нужно").font(NLFont.ui(13.5)).foregroundStyle(NL.textSecondary)
                    } action: { set(role, Self.off) }
                }
            }
            if heard == role {
                HStack(spacing: 8) {
                    Circle().fill(NL.accent).frame(width: 8, height: 8)
                    Text("Работает — вы нажали \(current.label)").font(NLFont.ui(13.5, .medium)).foregroundStyle(NL.textAccent)
                }
                .padding(.horizontal, 12).padding(.vertical, 9)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(NL.accentSubtle, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                .transition(.opacity)
            }
        }
        .padding(18)
        .nlCard(padding: 0)
        .animation(Motion.base, value: heard)
    }

    private func chip<L: View>(selected: Bool, dashed: Bool = false, @ViewBuilder label: () -> L,
                               action: @escaping () -> Void) -> some View {
        Button(action: action) {
            label()
                .padding(.horizontal, 10)
                .frame(height: 38)
                .background(selected ? NL.accentSubtle : .clear, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                .overlay {
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .strokeBorder(selected ? NL.accent : NL.border, style: StrokeStyle(lineWidth: selected ? 2 : 1, dash: dashed && !selected ? [4, 3] : []))
                }
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private func set(_ role: HotkeyRole, _ preset: HotkeyPreset) {
        heard = nil
        if role == .hold { state.hotkey = preset } else { state.toggleHotkey = preset }
        HubSync.announce()
    }

    /// «Своё сочетание»: следующее нажатие с модификатором - и есть оно.
    /// Пока ждём, свои сочетания не слушаем: иначе они бы и сработали.
    private func startRecording(_ role: HotkeyRole) {
        stopRecording()
        recording = role
        hooks.unbindHotkeys()
        monitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
            if event.keyCode == UInt16(kVK_Escape) { stopRecording(); return nil }
            var names: [String] = []
            let f = event.modifierFlags
            if f.contains(.control) { names.append("control") }
            if f.contains(.option) { names.append("option") }
            if f.contains(.shift) { names.append("shift") }
            if f.contains(.command) { names.append("command") }
            guard !names.isEmpty else { NSSound.beep(); return nil }
            let preset = HotkeyPreset(keyCode: Int(event.keyCode), modifierNames: names)
            if HotkeyPreset.isSystemCombo(keyCode: Int(event.keyCode), mods: preset.modifiers) { NSSound.beep(); return nil }
            stopRecording()
            set(role, preset)
            return nil
        }
    }

    private func stopRecording() {
        if let monitor { NSEvent.removeMonitor(monitor) }
        monitor = nil
        if recording != nil { hooks.bindHotkeys() }
        recording = nil
    }
}

// MARK: - 4. Распознавание

private struct RecognitionStep: View {
    @EnvironmentObject var state: AppState
    @ObservedObject var models: ModelProgress

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            StepTitle(title: "Распознавание — прямо на этом Маке",
                      subtitle: "Скачивается один раз, около 1 ГБ. Дальше всё работает без интернета: звук и текст никуда не уходят. Можно идти дальше — скачивание продолжится в фоне.")
            VStack(spacing: 0) {
                part("Python и библиотеки", "130 МБ", done: state.setupStep == nil && !PythonSetup.needed,
                     active: state.setupStep != nil, note: state.setupStep.map { _ in state.startingNote }, fraction: pythonFraction)
                NL.borderSubtle.frame(height: 1)
                part("GigaAM v3 — русский", "ставит знаки, пишет числа цифрами", done: state.backend == .ready,
                     active: state.setupStep == nil && state.backend == .starting,
                     note: "\(Int(models.ruMB)) из \(Int(ModelProgress.ruTotal / 1_000_000)) МБ", fraction: models.ru)
                NL.borderSubtle.frame(height: 1)
                part("Parakeet — английский", "и английские слова в коде", done: state.englishReady,
                     active: state.backend == .ready && !state.englishReady,
                     note: "\(Int(models.enMB)) из \(Int(ModelProgress.enTotal / 1_000_000)) МБ", fraction: models.en)
            }
            .nlCard(padding: 0)
            if case let .failed(message) = state.backend {
                NLAlert(kind: .danger, title: "Распознавание не подготовилось", message: message)
            }
            VStack(alignment: .leading, spacing: 10) {
                Text("На каком языке вы будете говорить?").font(NLFont.ui(15, .semibold)).foregroundStyle(NL.textPrimary)
                Picker("", selection: $state.langMode) {
                    Text("Сам определит").tag(LangMode.auto)
                    Text("Только русский").tag(LangMode.ru)
                    Text("Только английский").tag(LangMode.en)
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .fixedSize()
                Text("«Сам определит» понимает и смешанную речь — по кусочкам.").font(NLFont.ui(13)).foregroundStyle(NL.textTertiary)
            }
            .padding(16)
            .nlCard(padding: 0)
        }
        .onChange(of: state.langMode) { _, _ in HubSync.announce() }
    }

    private var pythonFraction: Double? {
        if case let .downloading(f) = state.setupStep { return f.map { $0 * 0.5 } }
        if state.setupStep == .unpacking { return 0.55 }
        if state.setupStep == .installing { return 0.75 }
        return nil
    }

    private func part(_ title: String, _ detail: String, done: Bool, active: Bool, note: String?, fraction: Double?) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 14) {
                ZStack {
                    if done {
                        Circle().fill(NL.accent)
                        Image(systemName: "checkmark").font(.system(size: 11, weight: .bold)).foregroundStyle(NL.textOnAccent)
                    } else {
                        Circle().strokeBorder(active ? NL.accent : NL.borderStrong, lineWidth: active ? 2 : 1.5)
                    }
                }
                .frame(width: 26, height: 26)
                (Text(title).font(NLFont.ui(15, .semibold)).foregroundStyle(NL.textPrimary)
                 + Text("  · \(detail)").font(NLFont.ui(13)).foregroundStyle(NL.textTertiary))
                Spacer()
                if done { Text("Готово").font(NLFont.ui(13, .semibold)).foregroundStyle(NL.textAccent) }
                else if active, let note { Text(note).font(NLFont.ui(13).monospacedDigit()).foregroundStyle(NL.textSecondary) }
                else { Text("следующим").font(NLFont.ui(13)).foregroundStyle(NL.textTertiary) }
            }
            if active && !done {
                ProgressBar(value: fraction).padding(.leading, 40)
            }
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 14)
    }
}

/// Сколько моделей уже скачано: по размеру их папок (onnx-asr пишет файлы
/// прямо туда, недокачанное - тоже). Опрос раз в секунду, пока окно открыто.
@MainActor
final class ModelProgress: ObservableObject {
    static let ruTotal: Double = 226_000_000
    static let enTotal: Double = 662_000_000
    @Published var ruMB: Double = 0
    @Published var enMB: Double = 0
    private var timer: Timer?

    var ru: Double { min(1, ruMB * 1_000_000 / Self.ruTotal) }
    var en: Double { min(1, enMB * 1_000_000 / Self.enTotal) }

    func start() {
        guard timer == nil else { return }
        poll()
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.poll() }
        }
    }

    func stop() {
        timer?.invalidate()
        timer = nil
    }

    private func poll() {
        DispatchQueue.global(qos: .utility).async {
            let ru = Self.size("gigaam-v3-e2e-rnnt-int8"), en = Self.size("nemo-parakeet-tdt-0.6b-v2-int8")
            DispatchQueue.main.async { [weak self] in
                self?.ruMB = ru / 1_000_000
                self?.enMB = en / 1_000_000
            }
        }
    }

    nonisolated private static func size(_ folder: String) -> Double {
        let dir = Paths.models.appendingPathComponent(folder)
        guard let e = FileManager.default.enumerator(at: dir, includingPropertiesForKeys: [.fileSizeKey]) else { return 0 }
        var total = 0
        for case let url as URL in e {
            total += (try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
        }
        return Double(total)
    }
}

// MARK: - 5. Первая диктовка

private struct PracticeStep: View {
    @EnvironmentObject var state: AppState
    @ObservedObject var models: ModelProgress
    @State private var since = Date()

    private var attempt: Entry? { state.history.first { $0.date >= since } }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            StepTitle(title: "Попробуйте — прямо здесь",
                      subtitle: "Зажмите **\(state.hotkey.label)**, скажите фразу и отпустите. Например: *«Привет, это моя первая диктовка, встречаемся завтра в десять»*.")
            field
            if let e = attempt, !e.failed {
                HStack(spacing: 12) {
                    Image(systemName: "checkmark.circle.fill").font(.system(size: 20)).foregroundStyle(NL.accent)
                    Text(resultLine(e)).font(NLFont.ui(14, .medium)).foregroundStyle(NL.textAccent)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(.horizontal, 16).padding(.vertical, 12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(NL.accentSubtle, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                .transition(.opacity)
            }
            HStack(alignment: .top, spacing: 10) {
                Tip(title: "Говорите как обычно", text: "Запятые и точки поставятся сами — диктовать их не нужно.")
                Tip(title: "Капсула внизу экрана", text: "Чёрная, с полосками и временем — значит, слушает.")
                Tip(title: "Передумали", text: "Esc — запись отменится, ничего не вставится.")
            }
            .frame(height: 108)
        }
        .animation(Motion.moderate, value: attempt?.id)
        .onAppear { since = Date() }
    }

    @ViewBuilder
    private var field: some View {
        let shape = RoundedRectangle(cornerRadius: 14, style: .continuous)
        VStack(alignment: .leading) {
            if let e = attempt {
                Text(e.failed ? "Не расслышал — попробуйте ещё раз, чуть ближе к микрофону." : e.text)
                    .font(NLFont.ui(18))
                    .foregroundStyle(e.failed ? NL.textTertiary : NL.textPrimary)
                    .textSelection(.enabled)
            } else if state.isBusy {
                Text("Слушаю…").font(NLFont.ui(18)).foregroundStyle(NL.textTertiary)
            } else if state.backend != .ready {
                Text("Распознавание ещё готовится — \(Int(models.ru * 100))%. Как только будет готово, можно пробовать.")
                    .font(NLFont.ui(16)).foregroundStyle(NL.textTertiary)
            } else {
                Text("Здесь появится то, что вы скажете").font(NLFont.ui(18)).foregroundStyle(NL.textQuaternary)
            }
        }
        .padding(.horizontal, 20).padding(.vertical, 18)
        .frame(maxWidth: .infinity, minHeight: 120, alignment: .topLeading)
        .background(NL.surface, in: shape)
        .overlay { shape.strokeBorder(state.isBusy ? NL.accent : NL.border, lineWidth: state.isBusy ? 2 : 1) }
        .animation(Motion.fast, value: state.isBusy)
    }

    private func resultLine(_ e: Entry) -> String {
        var s = "Получилось! \(wordsLabel(e.words))."
        if let raw = e.raw {
            let removed = max(0, Entry.count(raw) - e.words)
            if removed > 0 { s += " Убрано лишних слов: \(removed)." }
        }
        if !state.axTrusted { s += " В другом окне текст ляжет в буфер обмена — дайте универсальный доступ на шаге 2." }
        return s
    }
}

// MARK: - 6. Стиль под приложения

private struct StylesStep: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            StepTitle(title: "В каждом приложении — свой стиль",
                      subtitle: "FlowLocal видит, куда вы диктуете, и пишет по-разному. Вот приложения, которые нашлись у вас, — проверьте стиль или оставьте как есть.")
            VStack(spacing: 0) {
                ForEach(state.appStyles) { rule in
                    HStack(spacing: 14) {
                        AppIcon(bundleID: rule.bundleID).frame(width: 30, height: 30)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(rule.name).font(NLFont.ui(14.5, .semibold)).foregroundStyle(NL.textPrimary)
                            Text(rule.style.sample).font(NLFont.ui(12.5)).foregroundStyle(NL.textTertiary)
                        }
                        Spacer()
                        Picker("", selection: binding(rule)) {
                            ForEach(TextStyle.allCases) { Text($0.title).tag($0) }
                        }
                        .labelsHidden().pickerStyle(.menu).fixedSize()
                    }
                    .padding(.horizontal, 18).padding(.vertical, 10)
                    NL.borderSubtle.frame(height: 1)
                }
                HStack(spacing: 14) {
                    RoundedRectangle(cornerRadius: 8, style: .continuous).fill(NL.subtle).frame(width: 30, height: 30)
                        .overlay { Image(systemName: "ellipsis").foregroundStyle(NL.iconTertiary) }
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Все остальные").font(NLFont.ui(14.5, .semibold)).foregroundStyle(NL.textPrimary)
                        Text(TextStyle.standard.sample).font(NLFont.ui(12.5)).foregroundStyle(NL.textTertiary)
                    }
                    Spacer()
                    Text("Обычный").font(NLFont.ui(13, .medium)).foregroundStyle(NL.textSecondary)
                }
                .padding(.horizontal, 18).padding(.vertical, 10)
            }
            .nlCard(padding: 0)
            HStack(spacing: 8) {
                ForEach(TextStyle.allCases) { s in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(s.title).font(NLFont.ui(12.5, .semibold)).foregroundStyle(NL.textPrimary)
                        Text(short(s)).font(NLFont.ui(12)).foregroundStyle(NL.textSecondary)
                    }
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(NL.subtle, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                }
            }
            Text("Добавить приложение или поменять стиль потом — вкладка «Стиль» в окне FlowLocal.")
                .font(NLFont.ui(13)).foregroundStyle(NL.textTertiary)
        }
    }

    private func short(_ s: TextStyle) -> String {
        switch s {
        case .standard: return "Как сказали, со знаками."
        case .chat: return "С маленькой, без точки."
        case .formal: return "Строго, с заглавной и точкой."
        case .code: return "Знаки словами, имена слитно."
        }
    }

    private func binding(_ rule: AppStyleRule) -> Binding<TextStyle> {
        Binding {
            state.appStyles.first { $0.id == rule.id }?.style ?? .standard
        } set: { value in
            if let i = state.appStyles.firstIndex(where: { $0.id == rule.id }) { state.appStyles[i].style = value }
            HubSync.announce()
        }
    }
}

// MARK: - 7. Код голосом

private struct CodeStep: View {
    private let examples: [(String, String)] = [
        ("let greeting равно кавычки привет кавычки", "let greeting = \"привет\""),
        ("func load profile скобки открыть фигурную", "func loadProfile() {"),
        ("snake case user id равно 42", "user_id = 42"),
        ("комментарий проверить загрузку", "// проверить загрузку"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            StepTitle(title: "Код — тоже голосом",
                      subtitle: "В приложениях со стилем «Код» говорите вперемешку, как привыкли. Знаки — словами, английские слова склеиваются в одно имя. Не программируете — смело листайте дальше.")
            VStack(spacing: 0) {
                HStack {
                    Text("ГОВОРИТЕ").frame(maxWidth: .infinity, alignment: .leading)
                    Text("ПОЛУЧАЕТСЯ").frame(maxWidth: .infinity, alignment: .leading)
                }
                .font(NLFont.ui(11.5, .semibold)).tracking(0.7).foregroundStyle(NL.textTertiary)
                .padding(.horizontal, 18).padding(.vertical, 10)
                .background(NL.canvas)
                ForEach(examples, id: \.0) { said, got in
                    NL.borderSubtle.frame(height: 1)
                    HStack {
                        Text(said).font(NLFont.ui(14)).foregroundStyle(NL.textPrimary).frame(maxWidth: .infinity, alignment: .leading)
                        Text(got).font(.system(size: 13.5, design: .monospaced)).foregroundStyle(NL.textAccent).frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .padding(.horizontal, 18).padding(.vertical, 11)
                }
            }
            .nlCard(padding: 0)
            HStack(alignment: .top, spacing: 10) {
                Tip(title: "Знаки словами", text: "равно, точка, запятая, скобки, открыть / закрыть скобку, квадратную, фигурную, кавычки, стрелка, плюс, минус, больше, меньше, новая строка")
                Tip(title: "Как писать имя", text: "по умолчанию camelCase. Перед именем: «снейк кейс», «паскаль кейс», «кебаб кейс», «капс», «слитно»")
            }
            .frame(height: 118)
        }
    }
}

// MARK: - 8. Словарь и правки

private struct DictionaryStep: View {
    @EnvironmentObject var state: AppState
    @State private var term = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            StepTitle(title: "Научите FlowLocal своим словам",
                      subtitle: "Имена коллег, названия проектов, сервисы — всё, что модель может написать по-своему. Добавьте их сейчас или потом во вкладке «Словарь».")
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 8) {
                    TextField("Имя, название или термин", text: $term)
                        .textFieldStyle(.roundedBorder)
                        .font(NLFont.ui(14))
                        .onSubmit(add)
                    Button("Добавить", action: add).buttonStyle(InkButtonStyle())
                        .disabled(term.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                if !state.vocabulary.isEmpty {
                    FlowRow(items: state.vocabulary) { word in
                        Button {
                            withMotion(Motion.base) { state.vocabulary.removeAll { $0 == word } }
                        } label: {
                            HStack(spacing: 6) {
                                Text(word).font(NLFont.ui(13.5, .medium)).foregroundStyle(NL.textPrimary)
                                Image(systemName: "xmark").font(.system(size: 9, weight: .bold)).foregroundStyle(NL.textTertiary)
                            }
                            .padding(.horizontal, 12).padding(.vertical, 6)
                            .background(NL.subtle, in: Capsule())
                        }
                        .buttonStyle(.plain)
                    }
                }
                Text("Похожее на слух слово заменится: «гитхаб» → GitHub, «кондеев» → Кандеев.")
                    .font(NLFont.ui(13)).foregroundStyle(NL.textTertiary)
            }
            .padding(16)
            .nlCard(padding: 0)
            ToggleRow(title: "Учиться на ваших правках",
                      detail: "Поправили слово прямо в поле после вставки или в истории — в следующий раз оно напишется верно. Например: «флоу локал» → FlowLocal.",
                      isOn: $state.learnFromEdits)
                .nlCard(padding: 0)
        }
        .onChange(of: state.learnFromEdits) { _, _ in HubSync.announce() }
    }

    private func add() {
        let t = term.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty else { return }
        if !state.vocabulary.contains(where: { $0.caseInsensitiveCompare(t) == .orderedSame }) {
            withMotion(Motion.base) { state.vocabulary.append(t) }
        }
        term = ""
    }
}

/// Капсулы в строку с переносом.
private struct FlowRow<Content: View>: View {
    let items: [String]
    @ViewBuilder var content: (String) -> Content

    var body: some View {
        FlowLayout(spacing: 8) {
            ForEach(items, id: \.self) { content($0) }
        }
    }
}

private struct FlowLayout: Layout {
    var spacing: CGFloat

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, row: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > 0 && x + s.width > width { x = 0; y += row + spacing; row = 0 }
            x += s.width + spacing
            row = max(row, s.height)
        }
        return CGSize(width: width == .infinity ? x : width, height: y + row)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, row: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > bounds.minX && x + s.width > bounds.maxX { x = bounds.minX; y += row + spacing; row = 0 }
            v.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(s))
            x += s.width + spacing
            row = max(row, s.height)
        }
    }
}

// MARK: - 9. Ещё полезное

private struct TipsStep: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            StepTitle(title: "Ещё пара вещей, которые стоит знать")
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                Tip(title: "Шёпотом", text: "В опенспейсе или ночью: микрофон становится чувствительнее на время записи. Переключатель — внизу слева в окне.", key: "⌥⌘W")
                Tip(title: "История и календарь", text: "Все диктовки хранятся: найти, прослушать, распознать заново, вставить снова. Календарь показывает каждый день.", key: "⌘F")
                Tip(title: "Буфер обмена — на месте", text: "Текст вставляется через буфер, а то, что там было, возвращается. Музыка на время записи — на паузе.")
                Tip(title: "Значок в строке меню", text: "Окно можно закрыть — FlowLocal работает из строки меню. Оттуда же: окно, настройки и это обучение.")
            }
            VStack(alignment: .leading, spacing: 10) {
                Text("Не получилось?").font(NLFont.ui(15, .semibold)).foregroundStyle(NL.textPrimary)
                HStack(alignment: .top, spacing: 14) {
                    trouble("Текст не вставился", "нет универсального доступа: он в буфере, ⌘V.")
                    trouble("Не тот язык", "шаг 4: «Только русский».")
                    trouble("Неверное слово", "поправьте его — FlowLocal запомнит.")
                }
            }
            .padding(16)
            .nlCard(padding: 0)
        }
    }

    private func trouble(_ title: String, _ text: String) -> some View {
        (Text(title).font(NLFont.ui(13, .semibold)).foregroundStyle(NL.textPrimary)
         + Text(" — \(text)").font(NLFont.ui(13)).foregroundStyle(NL.textSecondary))
            .frame(maxWidth: .infinity, alignment: .leading)
            .fixedSize(horizontal: false, vertical: true)
    }
}

// MARK: - 10. Готово

private struct DoneStep: View {
    @EnvironmentObject var state: AppState
    let hooks: TutorialHooks

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 14) {
                ZStack {
                    Circle().fill(NL.accent)
                    Image(systemName: "checkmark").font(.system(size: 17, weight: .bold)).foregroundStyle(NL.textOnAccent)
                }
                .frame(width: 40, height: 40)
                Text("Всё готово — можно говорить").font(NLFont.ui(30, .heavy)).tracking(-0.6).foregroundStyle(NL.textPrimary)
            }
            Text(.init("Зажмите **\(state.hotkey.label)** в любом окне. Последние мелочи — и FlowLocal не будет задавать вопросов."))
                .font(NLFont.ui(15)).foregroundStyle(NL.textSecondary)
                .padding(.bottom, 4)

            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Оформление").font(NLFont.ui(15, .semibold)).foregroundStyle(NL.textPrimary)
                    Text("Окно FlowLocal. Капсула записи всегда чёрная.").font(NLFont.ui(13)).foregroundStyle(NL.textTertiary)
                }
                Spacer()
                ForEach(AppAppearance.allCases) { a in
                    Button {
                        withMotion(Motion.base) { state.appearance = a }
                        HubSync.announce()
                    } label: {
                        VStack(spacing: 5) {
                            ThemeSwatch(appearance: a, selected: state.appearance == a)
                            Text(a == .system ? "Как в системе" : a == .light ? "Светлая" : "Тёмная")
                                .font(NLFont.ui(12, state.appearance == a ? .semibold : .regular))
                                .foregroundStyle(state.appearance == a ? NL.textAccent : NL.textSecondary)
                        }
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 18).padding(.vertical, 14)
            .nlCard(padding: 0)

            VStack(spacing: 0) {
                ToggleRow(title: "Запускать при входе в систему",
                          detail: "Чтобы диктовка работала сразу после включения Мака.",
                          isOn: Binding(get: { state.launchAtLogin }, set: { hooks.setLaunchAtLogin($0) }))
                NL.borderSubtle.frame(height: 1)
                ToggleRow(title: "Звук начала и конца записи",
                          detail: "Тихий щелчок — слышно, что FlowLocal начал слушать.",
                          isOn: $state.sounds)
                NL.borderSubtle.frame(height: 1)
                HStack(spacing: 16) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Капсула записи").font(NLFont.ui(14.5, .semibold)).foregroundStyle(NL.textPrimary)
                        Text("Где показывать, пока идёт запись.").font(NLFont.ui(12.5)).foregroundStyle(NL.textTertiary)
                    }
                    Spacer()
                    Picker("", selection: $state.pillPosition) {
                        ForEach(PillPosition.allCases) { Text($0.title).tag($0) }
                    }
                    .pickerStyle(.segmented).labelsHidden().fixedSize()
                }
                .padding(.horizontal, 18).padding(.vertical, 14)
            }
            .nlCard(padding: 0)
            Text("Обучение можно открыть снова: значок FlowLocal в строке меню → «Обучение».")
                .font(NLFont.ui(13)).foregroundStyle(NL.textTertiary)
        }
        .onChange(of: state.sounds) { _, _ in HubSync.announce() }
        .onChange(of: state.pillPosition) { _, _ in HubSync.announce() }
    }
}

private struct ThemeSwatch: View {
    let appearance: AppAppearance
    let selected: Bool

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: 9, style: .continuous)
        Group {
            switch appearance {
            case .system:
                HStack(spacing: 0) {
                    Color(red: 0.965, green: 0.965, blue: 0.957)
                    Color(red: 0.067, green: 0.067, blue: 0.075)
                }
            case .light:
                HStack(spacing: 4) {
                    RoundedRectangle(cornerRadius: 3).fill(Color(red: 0.933, green: 0.933, blue: 0.925)).frame(width: 16)
                    RoundedRectangle(cornerRadius: 3).fill(.white)
                }
                .padding(6)
                .background(Color(red: 0.965, green: 0.965, blue: 0.957))
            case .dark:
                HStack(spacing: 4) {
                    RoundedRectangle(cornerRadius: 3).fill(Color(red: 0.047, green: 0.047, blue: 0.055)).frame(width: 16)
                    RoundedRectangle(cornerRadius: 3).fill(Color(red: 0.11, green: 0.11, blue: 0.12))
                }
                .padding(6)
                .background(Color(red: 0.067, green: 0.067, blue: 0.075))
            }
        }
        .frame(width: 76, height: 48)
        .clipShape(shape)
        .overlay { shape.strokeBorder(selected ? NL.accent : NL.borderStrong, lineWidth: selected ? 2 : 1) }
    }
}
