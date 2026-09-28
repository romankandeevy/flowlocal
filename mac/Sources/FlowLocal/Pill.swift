import AppKit
import SwiftUI

// Индикатор записи поверх окон у нижнего края экрана. Не забирает фокус
// (nonactivatingPanel + canBecomeKey=false) и не ловит мышь: ⌘V после него
// должен уйти в то окно, где человек печатал. Панель шире самого индикатора и
// не меняет размер: капсула сама по ширине содержимого и всегда по центру
// панели, а панель - по центру экрана.
final class PillPanel: NSPanel {
    static let width: CGFloat = 820
    static let height: CGFloat = 96

    /// Каждое present/dismiss - новое поколение: гашение, начатое раньше,
    /// не уберёт индикатор, который успели показать снова.
    private var generation = 0

    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }

    private let state: AppState

    init(state: AppState) {
        self.state = state
        super.init(contentRect: NSRect(x: 0, y: 0, width: PillPanel.width, height: PillPanel.height),
                   styleMask: [.borderless, .nonactivatingPanel],
                   backing: .buffered, defer: false)
        isFloatingPanel = true
        level = .statusBar
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary, .ignoresCycle]
        backgroundColor = .clear
        isOpaque = false
        hasShadow = false
        ignoresMouseEvents = true
        hidesOnDeactivate = false
        isReleasedWhenClosed = false
        let host = NSHostingView(rootView: PillView().environmentObject(state))
        // Иначе NSHostingView подгоняет окно под ширину капсулы, окно растёт
        // от левого края - и капсула уезжает вбок.
        host.sizingOptions = []
        contentView = host
    }

    func present() {
        generation += 1
        if let screen = Self.activeScreen() {
            // По горизонтали - центр всего экрана, а не visibleFrame: Dock
            // сбоку сдвинул бы его. По вертикали - над Доком / под меню.
            let vf = screen.visibleFrame
            let y = state.pillPosition == .top ? vf.maxY - PillPanel.height : vf.minY
            setFrame(NSRect(x: (screen.frame.midX - PillPanel.width / 2).rounded(), y: y,
                            width: PillPanel.width, height: PillPanel.height), display: false)
        }
        if !isVisible {
            alphaValue = 0
            orderFrontRegardless()
        }
        NSAnimationContext.runAnimationGroup { ctx in
            ctx.duration = 0.18
            animator().alphaValue = 1
        }
    }

    /// Экран, где человек печатает: окно активного приложения, а не курсор.
    /// С двумя мониторами мышь часто на другом - и капсулу было не видно.
    private static func activeScreen() -> NSScreen? {
        let mouse = NSEvent.mouseLocation
        let byMouse = NSScreen.screens.first { NSMouseInRect(mouse, $0.frame, false) } ?? NSScreen.main
        guard NSScreen.screens.count > 1,
              let pid = NSWorkspace.shared.frontmostApplication?.processIdentifier,
              let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements],
                                                    kCGNullWindowID) as? [[String: Any]],
              let info = list.first(where: {
                  ($0[kCGWindowOwnerPID as String] as? pid_t) == pid && ($0[kCGWindowLayer as String] as? Int) == 0
              }),
              let dict = info[kCGWindowBounds as String] as? NSDictionary,
              let cg = CGRect(dictionaryRepresentation: dict),
              let primary = NSScreen.screens.first
        else { return byMouse }
        // Координаты окон - от верхнего левого угла главного экрана, у NSScreen - от нижнего.
        let center = NSPoint(x: cg.midX, y: primary.frame.maxY - cg.midY)
        return NSScreen.screens.first { NSMouseInRect(center, $0.frame, false) } ?? byMouse
    }

    func dismiss() {
        generation += 1
        let current = generation
        NSAnimationContext.runAnimationGroup({ ctx in
            ctx.duration = 0.22
            animator().alphaValue = 0
        }, completionHandler: { [weak self] in
            guard let self, self.generation == current else { return }
            self.orderOut(nil)
        })
    }
}

// Индикатор - тост Northline: surface + граница 1pt + shadow-lg, radius-lg,
// одна строка label. Запись - красная точка, нейтральная волна и время
// моноширинными цифрами; что из этого видно - секция «Капсула записи» в Hub Settings.
// Ничего не пружинит: смена - ease-out 200 мс.
struct PillView: View {
    @EnvironmentObject var state: AppState
    @ObservedObject private var meter = LevelStore.shared
    @ObservedObject private var live = LiveWords.shared
    /// Последнее видимое состояние: пока индикатор гаснет, он показывает
    /// его, а не схлопывается в пустую капсулу.
    @State private var shown: Phase = .idle

    var body: some View {
        PillCapsule { content }
            .opacity(visible ? 1 : 0)
            .scaleEffect(state.pillSize.scale)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .motion(Motion.moderate, value: state.phase)
            .onAppear { if state.phase != .idle { shown = state.phase } }
            .onChange(of: state.phase) { _, phase in
                if phase != .idle { shown = phase }
            }
    }

    /// «Распознаю…» и «Готово» можно спрятать; запись, ошибки и «скопировано,
    /// нажмите ⌘V» видны всегда.
    private var visible: Bool {
        switch state.phase {
        case .idle: return false
        case .processing, .done: return state.pillShowStatus
        default: return true
        }
    }

    @ViewBuilder
    private var content: some View {
        switch shown {
        case .idle:
            EmptyView()
        case .loading:
            ProgressView().controlSize(.mini)
            Text("Загрузка моделей…")
        case let .recording(since, _):
            TimelineView(.periodic(from: since, by: 0.25)) { context in
                let t = context.date.timeIntervalSince(since)
                PillRecordingRow(elapsed: t, levels: meter.levels,
                                 silent: t > 1.5 && meter.peak < 0.05,
                                 hasWords: !live.words.isEmpty) {
                    LiveWordsTicker(width: state.pillTextWidth.points)
                }
            }
        case .processing:
            ProgressView().controlSize(.mini)
            Text("Распознаю…")
        case let .done(message):
            Image(systemName: "checkmark").foregroundStyle(NL.textSuccess)
            Text(message)
        case let .copied(message):
            Image(systemName: "doc.on.clipboard")
                .foregroundStyle(NL.iconSecondary)
            Text(message)
        case let .failed(message):
            Image(systemName: "exclamationmark.octagon").foregroundStyle(NL.textDanger)
            Text(message)
        }
    }
}

/// Сама капсула: фон, граница, тень.
struct PillCapsule<Content: View>: View {
    @ViewBuilder var content: () -> Content

    var body: some View {
        HStack(spacing: Space.s2) {
            content()
        }
        .nlType(.label)
        .foregroundStyle(NL.textPrimary)
        .lineLimit(1)
        .padding(.horizontal, Space.s3)
        .frame(height: 36)
        .fixedSize()
        .nlRaised(.lg)
    }
}

/// Строка записи в капсуле. Какие части видны - настройки «Капсулы»;
/// выключено всё - остаётся красная точка, чтобы запись было видно.
struct PillRecordingRow<Words: View>: View {
    @EnvironmentObject var state: AppState
    let elapsed: TimeInterval
    let levels: [Float]
    var silent = false
    var hasWords = true
    @ViewBuilder var words: () -> Words

    var body: some View {
        let showWords = state.pillLiveText && hasWords
        let showDot = state.pillShowDot
            || !(state.pillShowTimer || state.pillShowWave || showWords)
        HStack(spacing: Space.s2) {
            if showDot {
                Circle().fill(NL.danger).frame(width: 8, height: 8)
            }
            if state.pillShowTimer {
                Text(MainView.clock(elapsed))
                    .font(.system(size: 12, weight: .medium, design: .monospaced))
                    .foregroundStyle(NL.textPrimary)
            }
            if state.pillShowWave {
                Waveform(levels: levels, color: NL.iconSecondary, count: 12, barWidth: 2,
                         spacing: 2, height: 14, floor: 0.15, fade: false)
                    .opacity(silent ? 0.4 : 1.0)
            }
            // Бегущая строка расшифровки: видно каждое слово, не глядя в окно.
            if showWords {
                if showDot || state.pillShowTimer || state.pillShowWave {
                    NL.border.frame(width: 1, height: 14)
                }
                words()
                    .transition(.opacity)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Идёт запись, \(MainView.clock(elapsed))")
    }
}
