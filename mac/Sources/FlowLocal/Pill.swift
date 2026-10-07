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

// Капсула - чёрная плашка и белые полоски, и больше ничего: ни времени, ни
// точки, ни слов, ни надписей. Не настраивается. Пока идёт запись, полоски
// живут от голоса; пока распознаётся - по ним бежит мягкая волна; дальше
// капсула гаснет. Появляется пружиной из чуть меньшего размера, гаснет
// обратно.
struct PillView: View {
    @EnvironmentObject var state: AppState
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        PillCapsule {
            PillBars(thinking: state.phase == .processing)
        }
        .opacity(visible ? 1 : 0)
        .scaleEffect(visible || reduceMotion ? 1 : 0.86, anchor: state.pillPosition == .top ? .top : .bottom)
        .blur(radius: visible || reduceMotion ? 0 : 6)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .animation(reduceMotion ? nil : Motion.pop, value: visible)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(state.phase == .processing ? "Распознавание" : "Идёт запись")
    }

    /// Только запись и распознавание - остальное капсула не показывает.
    private var visible: Bool {
        switch state.phase {
        case .recording, .processing: return true
        default: return false
        }
    }
}

/// Цвета капсулы: чёрная плашка, белые полоски. Text/secondary - для
/// бегущей строки (LiveWordsTicker), в капсуле её больше нет.
enum Pill {
    static let text = Color.white
    static let secondary = Color.white.opacity(0.55)
}

/// Девять белых полосок. Запись - высота от уровня голоса, выше к центру;
/// распознавание - по ним бежит волна.
private struct PillBars: View {
    var thinking: Bool
    @ObservedObject private var meter = LevelStore.shared
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private let count = 9
    private let shape: [CGFloat] = [0.45, 0.6, 0.78, 0.92, 1.0, 0.92, 0.78, 0.6, 0.45]

    var body: some View {
        TimelineView(.animation(minimumInterval: reduceMotion ? 0.25 : 1.0 / 30)) { context in
            let t = context.date.timeIntervalSinceReferenceDate
            HStack(spacing: 3) {
                ForEach(0..<count, id: \.self) { i in
                    Capsule()
                        .fill(Color.white)
                        .frame(width: 3, height: 4 + 14 * height(i, t))
                }
            }
            .frame(height: 18)
            .animation(.easeOut(duration: 0.12), value: meter.levels.last ?? 0)
        }
    }

    private func height(_ i: Int, _ t: Double) -> CGFloat {
        if thinking {
            let phase = t * 6 - Double(i) * 0.7
            return 0.2 + 0.55 * CGFloat((sin(phase) + 1) / 2)
        }
        // Последние уровни - с разных моментов, чтобы полоски не прыгали разом.
        let levels = meter.levels
        let v = CGFloat(levels[max(0, levels.count - 1 - abs(i - count / 2))])
        let jitter = 0.85 + 0.15 * CGFloat(sin(t * 9 + Double(i) * 1.9))
        return max(0.12, min(1, v * shape[i] * jitter * 1.15))
    }
}

/// Сама капсула: чёрная плашка с едва заметной кромкой и мягкой тенью.
struct PillCapsule<Content: View>: View {
    @ViewBuilder var content: () -> Content

    var body: some View {
        content()
            .padding(.horizontal, 16)
            .frame(height: 36)
            .fixedSize()
            .background(Capsule(style: .continuous).fill(Color.black))
            .overlay {
                Capsule(style: .continuous).strokeBorder(Color.white.opacity(0.12), lineWidth: 0.5)
            }
            .shadow(color: .black.opacity(0.25), radius: 12, y: 5)
    }
}
