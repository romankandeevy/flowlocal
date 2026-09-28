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

// Капсула - тёмное стекло в форме таблетки, как «остров» у чёлки: одинаково
// читается на светлом и тёмном фоне. Появляется пружиной из чуть меньшего
// размера с размытием, гаснет обратно; ширина под содержимое меняется
// той же пружиной.
struct PillView: View {
    @EnvironmentObject var state: AppState
    @ObservedObject private var meter = LevelStore.shared
    @ObservedObject private var live = LiveWords.shared
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    /// Последнее видимое состояние: пока индикатор гаснет, он показывает
    /// его, а не схлопывается в пустую капсулу.
    @State private var shown: Phase = .idle

    var body: some View {
        PillCapsule { content }
            .environment(\.colorScheme, .dark)
            .opacity(visible ? 1 : 0)
            .scaleEffect(visible || reduceMotion ? 1 : 0.86, anchor: state.pillPosition == .top ? .top : .bottom)
            .blur(radius: visible || reduceMotion ? 0 : 6)
            .scaleEffect(state.pillSize.scale)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .animation(reduceMotion ? nil : Motion.pop, value: visible)
            .animation(reduceMotion ? nil : Motion.moderate, value: shown)
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
            PillSpinner()
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
            .transition(.opacity)
        case .processing:
            PillSpinner()
            Text("Распознаю…")
                .transition(.opacity)
        case let .done(message):
            PillIcon(symbol: "checkmark", tint: Pill.green)
            Text(message)
        case let .copied(message):
            PillIcon(symbol: "doc.on.clipboard.fill", tint: Pill.blue)
            Text(message)
        case let .failed(message):
            PillIcon(symbol: "exclamationmark", tint: Pill.red)
            Text(message)
        }
    }
}

/// Цвета капсулы - свои: она всегда тёмная, независимо от темы окна.
enum Pill {
    static let red = Color(red: 1.0, green: 0.27, blue: 0.23)
    static let green = Color(red: 0.2, green: 0.84, blue: 0.42)
    static let blue = Color(red: 0.25, green: 0.6, blue: 1.0)
    static let text = Color.white.opacity(0.95)
    static let secondary = Color.white.opacity(0.55)
}

/// Значок статуса - в цветном кружке, появляется пружиной.
private struct PillIcon: View {
    let symbol: String
    let tint: Color
    @State private var shown = false

    var body: some View {
        Image(systemName: symbol)
            .font(.system(size: 10, weight: .bold))
            .foregroundStyle(.white)
            .frame(width: 20, height: 20)
            .background(tint, in: Circle())
            .scaleEffect(shown ? 1 : 0.4)
            .opacity(shown ? 1 : 0)
            .onAppear { withMotion(Motion.pop) { shown = true } }
    }
}

/// Крутилка «Распознаю» - дуга, а не системный ProgressView: тот на тёмном
/// стекле серый и мелкий.
private struct PillSpinner: View {
    @State private var spin = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        Circle()
            .trim(from: 0.15, to: 0.85)
            .stroke(Pill.text, style: StrokeStyle(lineWidth: 2, lineCap: .round))
            .frame(width: 14, height: 14)
            .rotationEffect(.degrees(spin ? 360 : 0))
            .padding(3)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.linear(duration: 0.8).repeatForever(autoreverses: false)) { spin = true }
            }
    }
}

/// Сама капсула: тёмное стекло, тонкая светлая кромка, мягкая тень.
struct PillCapsule<Content: View>: View {
    @ViewBuilder var content: () -> Content

    var body: some View {
        HStack(spacing: 10) {
            content()
        }
        .font(.system(size: 13, weight: .medium))
        .foregroundStyle(Pill.text)
        .lineLimit(1)
        .padding(.leading, 12)
        .padding(.trailing, 16)
        .frame(height: 40)
        .fixedSize()
        .background {
            Capsule(style: .continuous)
                .fill(.ultraThinMaterial)
                .overlay(Capsule(style: .continuous).fill(Color.black.opacity(0.62)))
        }
        .overlay {
            Capsule(style: .continuous)
                .strokeBorder(LinearGradient(colors: [.white.opacity(0.18), .white.opacity(0.05)],
                                             startPoint: .top, endPoint: .bottom), lineWidth: 1)
        }
        .clipShape(Capsule(style: .continuous))
        .shadow(color: .black.opacity(0.28), radius: 14, y: 6)
    }
}

/// Красная точка записи - мягко дышит, пока идёт запись.
private struct RecordingDot: View {
    var silent = false
    @State private var breathe = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ZStack {
            Circle().fill(Pill.red.opacity(0.35))
                .frame(width: 16, height: 16)
                .scaleEffect(breathe ? 1 : 0.5)
                .opacity(breathe ? 0 : 1)
            Circle().fill(Pill.red)
                .frame(width: 8, height: 8)
        }
        .frame(width: 16, height: 16)
        .opacity(silent ? 0.5 : 1)
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.easeOut(duration: 1.4).repeatForever(autoreverses: false)) { breathe = true }
        }
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
        HStack(spacing: 10) {
            if showDot {
                RecordingDot(silent: silent)
            }
            if state.pillShowTimer {
                Text(MainView.clock(elapsed))
                    .font(.system(size: 13, weight: .medium).monospacedDigit())
                    .foregroundStyle(Pill.text)
                    .contentTransition(.numericText())
            }
            if state.pillShowWave {
                Waveform(levels: levels, color: Pill.text, count: 14, barWidth: 2.5,
                         spacing: 2, height: 18, floor: 0.12, fade: false)
                    .opacity(silent ? 0.35 : 0.9)
            }
            // Бегущая строка расшифровки: видно каждое слово, не глядя в окно.
            if showWords {
                if showDot || state.pillShowTimer || state.pillShowWave {
                    Color.white.opacity(0.14).frame(width: 1, height: 16)
                }
                words()
                    .transition(.opacity)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Идёт запись, \(MainView.clock(elapsed))")
    }
}
