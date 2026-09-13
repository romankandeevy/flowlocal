import AppKit
import SwiftUI

// Островок поверх окон у нижнего края экрана. Не забирает фокус
// (nonactivatingPanel + canBecomeKey=false) и не ловит мышь: ⌘V после него
// должен уйти в то окно, где человек печатал. Панель шире самого островка -
// он сам по ширине содержимого и плавно меняет её между состояниями.
final class PillPanel: NSPanel {
    static let width: CGFloat = 400
    static let height: CGFloat = 48

    /// Каждое present/dismiss - новое поколение: гашение, начатое раньше,
    /// не уберёт островок, который успели показать снова.
    private var generation = 0

    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }

    init(state: AppState) {
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
        contentView = NSHostingView(rootView: PillView().environmentObject(state))
    }

    func present() {
        generation += 1
        let mouse = NSEvent.mouseLocation
        let screen = NSScreen.screens.first { NSMouseInRect(mouse, $0.frame, false) } ?? NSScreen.main
        if let vf = screen?.visibleFrame {
            setFrameOrigin(NSPoint(x: vf.midX - frame.width / 2, y: vf.minY + Space.s2))
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

// «01 · Островок» из дизайн-системы: сплошной #000000 без материала и блюра -
// у края экрана он должен читаться как рамка дисплея, а не как окно. Высота
// 32, радиус - половина высоты; рамка rgba(84,84,88,0.4) только по нижней
// половине. Глиф в плашке 18 pt, одна строка 13/600, один индикатор.
struct PillView: View {
    @EnvironmentObject var state: AppState
    @ObservedObject private var meter = LevelStore.shared
    /// Последнее видимое состояние: пока островок гаснет, он показывает его,
    /// а не схлопывается в пустую капсулу.
    @State private var shown: Phase = .idle

    var body: some View {
        let p = state.palette
        let visible = state.phase != .idle
        HStack(spacing: 10) {
            content(p)
        }
        .padding(.leading, 7)
        .padding(.trailing, 16)
        .frame(height: 32)
        .fixedSize()
        .background(Capsule().fill(Color.black))
        .overlay(
            Capsule()
                .strokeBorder(p.islandEdge, lineWidth: 1)
                .mask(VStack(spacing: 0) { Color.clear; Color.black })
        )
        .scaleEffect(visible ? 1 : 0.92)
        .opacity(visible ? 1 : 0)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .environment(\.colorScheme, .dark)
        .animation(Motion.island, value: state.phase)
        .onAppear { if state.phase != .idle { shown = state.phase } }
        .onChange(of: state.phase) { _, phase in
            if phase != .idle { shown = phase }
        }
    }

    @ViewBuilder
    private func content(_ p: Palette) -> some View {
        switch shown {
        case .idle:
            EmptyView()
        case .loading:
            glyph("hourglass", p.warning)
            line("Загружаю модель", p)
        case let .recording(since, _):
            TimelineView(.periodic(from: since, by: 0.25)) { ctx in
                let t = ctx.date.timeIntervalSince(since)
                let silent = t > 1.5 && meter.peak < 0.05
                HStack(spacing: 10) {
                    glyph(silent ? "mic.slash.fill" : "mic.fill", silent ? p.warning : p.accent)
                    line(silent ? "Нет сигнала" : "Слушаю", p)
                    Waveform(levels: meter.levels, color: p.accent, count: 6, barWidth: 2, spacing: 2,
                             height: 14, floor: 0.15, fade: false)
                    Rectangle().fill(p.separator).frame(width: 1, height: 14)
                    Text(MainView.clock(t))
                        .font(TextStyle.mono.font())
                        .monospacedDigit()
                        .foregroundStyle(p.textMuted)
                }
            }
        case .processing:
            ProgressView()
                .controlSize(.mini)
                .frame(width: 18, height: 18)
                .background(RoundedRectangle(cornerRadius: Radius.menu, style: .continuous).fill(p.fill3))
            line("Распознаю", p)
        case let .done(msg):
            glyph("checkmark", p.success)
            line(msg, p)
        case let .copied(msg):
            glyph("doc.on.clipboard", p.warning)
            line(msg, p)
        case let .failed(msg):
            glyph("xmark", p.danger)
            line(msg, p)
        }
    }

    private func glyph(_ symbol: String, _ color: Color) -> some View {
        Image(systemName: symbol)
            .font(.system(size: 10, weight: .semibold))
            .foregroundStyle(color)
            .contentTransition(.symbolEffect(.replace))
            .frame(width: 18, height: 18)
            .background(RoundedRectangle(cornerRadius: Radius.menu, style: .continuous).fill(Palette.dark.fill3))
    }

    private func line(_ text: String, _ p: Palette) -> some View {
        Text(text)
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(p.text)
            .lineLimit(1)
    }
}
