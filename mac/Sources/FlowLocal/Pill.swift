import AppKit
import SwiftUI

// Плашка поверх окон: у нижнего края экрана. Компактная - 280 px и одна
// строка: прошлая, на 360, выглядела громоздко. Не забирает фокус
// (nonactivatingPanel + canBecomeKey=false) и не ловит мышь: ⌘V после неё
// должен уйти в то окно, где человек печатал.
final class PillPanel: NSPanel {
    static let width: CGFloat = 280

    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }

    init(state: AppState) {
        super.init(contentRect: NSRect(x: 0, y: 0, width: PillPanel.width, height: 40),
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
        let mouse = NSEvent.mouseLocation
        let screen = NSScreen.screens.first { NSMouseInRect(mouse, $0.frame, false) } ?? NSScreen.main
        if let vf = screen?.visibleFrame {
            setFrameOrigin(NSPoint(x: vf.midX - frame.width / 2, y: vf.minY + Space.s3))
        }
        orderFrontRegardless()
    }

    func dismiss() {
        orderOut(nil)
    }
}

// Строка плашки: моно-метка состояния и моно-текст. Акцент - только у записи:
// кромка и дорожка уровня.
struct PillView: View {
    @EnvironmentObject var state: AppState
    @ObservedObject private var meter = LevelStore.shared

    var body: some View {
        let p = state.palette
        HStack(spacing: 10) {
            content(p)
        }
        .padding(.horizontal, Space.s3)
        .frame(width: PillPanel.width, height: 34, alignment: .leading)
        // Стеклянная НUD-подложка вместо сплошной заливки - та же техника,
        // что у системных плашек громкости/Now Playing: размывает то, что
        // под ней, вместо непрозрачного прямоугольника. Убирает ощущение
        // "тяжёлого окна" поверх рабочего стола.
        .background(HUDMaterial())
        .overlay(Rectangle().strokeBorder(edge(p), lineWidth: Space.hairline))
        .overlay(alignment: .bottom) {
            // Во время записи - тонкая акцентная дорожка по низу, а не толстая рамка.
            if isRecording { Rectangle().fill(p.accent).frame(height: Space.strong) }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .environment(\.colorScheme, state.theme.colorScheme)
        .animation(Motion.base, value: state.phase)
    }

    private var isRecording: Bool {
        if case .recording = state.phase { return true }
        return false
    }

    private struct HUDMaterial: NSViewRepresentable {
        func makeNSView(context: Context) -> NSVisualEffectView {
            let v = NSVisualEffectView()
            v.material = .hudWindow
            v.blendingMode = .behindWindow
            v.state = .active
            return v
        }
        func updateNSView(_ nsView: NSVisualEffectView, context: Context) {}
    }

    private func edge(_ p: Palette) -> Color {
        switch state.phase {
        case .recording: return p.accent
        case .failed: return p.danger
        default: return p.borderStrong
        }
    }

    @ViewBuilder
    private func content(_ p: Palette) -> some View {
        switch state.phase {
        case .idle:
            EmptyView()
        case .loading:
            Text("Внимание").monoLabel(p.warning)
            Text("Загружаю модель").monoLabel(p.text).lineLimit(1)
        case let .recording(since, locked):
            VKBlink(color: p.danger, width: 6, height: 6)
            VKLevelBars(levels: meter.levels, color: p.accent, count: 14, spacing: 2, height: 14, floor: 0.16)
            TimelineView(.periodic(from: since, by: 0.25)) { ctx in
                let t = ctx.date.timeIntervalSince(since)
                HStack(spacing: Space.s2) {
                    Text(MainView.clock(t))
                        .font(Fonts.mono(FontSize.mono))
                        .tracking(FontSize.mono * 0.12)
                        .monospacedDigit()
                        .foregroundStyle(p.text)
                    if t > 1.5 && meter.peak < 0.05 {
                        Text("Нет сигнала").monoLabel(p.warning)
                    } else {
                        Text(locked ? "Нажать" : wordsLabel(state.liveWords)).monoLabel(p.textMuted)
                    }
                }
                .fixedSize()
            }
        case .processing:
            VKPulseBlocks(color: p.accent, width: 5, height: 10)
            Text("Распознаю").monoLabel(p.text)
        case let .done(msg):
            Text("Ок").monoLabel(p.success)
            Text(msg).monoLabel(p.text).lineLimit(1)
        case let .copied(msg):
            Text("Буфер").monoLabel(p.warning)
            Text(msg).monoLabel(p.text).lineLimit(1)
        case let .failed(msg):
            Text("Ошибка").monoLabel(p.danger)
            Text(msg).monoLabel(p.text).lineLimit(1)
        }
    }
}
