import AppKit
import SwiftUI

/// Что окна умеют попросить у приложения. Замыкания подключает AppDelegate,
/// вью про контроллер не знают.
struct AppActions {
    var toggleDictation: () -> Void = {}
    var cancelDictation: () -> Void = {}
    var paste: (Entry) -> Void = { _ in }
    var rerecognize: (Entry) -> Void = { _ in }
    var play: (Entry) -> Void = { _ in }
    var openLog: () -> Void = {}
    var openRecordings: () -> Void = {}
    /// Настройки - в Hub Settings.
    var openSettings: () -> Void = {}
    var showMain: () -> Void = {}
    var find: () -> Void = {}
}

enum AppInfo {
    static var version: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "dev"
    }

    static let helpURL = URL(string: "https://github.com/romankandeevy/flowlocal/tree/main/mac#readme")!
}

// Главное окно - одно на всё. В тулбаре: состояние слева, разделы
// переключателем по центру. Под ним раздел; смена раздела -
// новый раздел проступает со сдвигом на 6pt, прежний уходит сразу.
struct MainView: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    var body: some View {
        ZStack {
            switch state.tab {
            case .dictations:
                DictationsView(actions: actions)
                    .transition(.sectionSwap)
            case .stats:
                StatsView()
                    .transition(.sectionSwap)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .motion(Motion.moderate, value: state.tab)
        .overlay(alignment: .top) { NL.border.frame(height: 1) }
        .frame(minWidth: 780, minHeight: 500)
        .background(NL.canvas)
        // Верхняя панель - тулбар окна со своими видами: высота, место
        // «светофоров» и перетаскивание окна остаются системными.
        .toolbar {
            ToolbarItem(placement: .navigation) {
                EngineStatus().padding(.horizontal, Space.s2)
            }
            .plainToolbarBackground()
            ToolbarItem(placement: .principal) {
                SectionSwitcher(selection: $state.tab)
            }
            .plainToolbarBackground()
        }
        .toolbarBackground(NL.canvas, for: .windowToolbar)
        .toolbarBackground(.visible, for: .windowToolbar)
        .navigationTitle("")
        .tint(NL.accent)
        .modifier(SceneBridgeCapture())
    }

    static func clock(_ t: TimeInterval) -> String {
        let s = max(0, Int(t))
        return String(format: "%d:%02d", s / 60, s % 60)
    }
}

extension ToolbarContent {
    /// macOS 26 кладёт каждый элемент тулбара на своё «стекло». У нас и статус,
    /// и переключатель разделов со своей подложкой - второе стекло вокруг
    /// выглядит двойной рамкой и обрезает текст статуса. На старых SDK и
    /// системах модификатора нет - там и стекла нет.
    @ToolbarContentBuilder
    func plainToolbarBackground() -> some ToolbarContent {
        #if compiler(>=6.2)
        if #available(macOS 26, *) {
            sharedBackgroundVisibility(.hidden)
        } else {
            self
        }
        #else
        self
        #endif
    }
}

extension AnyTransition {
    /// Смена раздела: растворение и сдвиг на 4pt, без масштаба.
    static var sectionSwap: AnyTransition {
        // Уходящий раздел исчезает сразу: при растворении обоих они на миг
        // просвечивали друг сквозь друга.
        .asymmetric(insertion: .opacity.combined(with: .offset(y: 6)).combined(with: .scale(scale: 0.99)),
                    removal: .identity)
    }
}

// MARK: - верхняя панель

/// Разделы - сегменты в подложке subtle; выбранный - surface с тенью xs,
/// переезжает под новый раздел (ease-in-out, чистая смена положения).
private struct SectionSwitcher: View {
    @Binding var selection: Tab
    @Namespace private var thumb

    var body: some View {
        HStack(spacing: Space.s0_5) {
            ForEach(Tab.allCases) { tab in
                Segment(title: tab.title, selected: selection == tab, namespace: thumb) {
                    withMotion(Motion.position) { selection = tab }
                }
            }
        }
        .padding(Space.s0_5)
        .background(NL.subtle, in: RoundedRectangle(cornerRadius: Radius.md, style: .continuous))
    }

    private struct Segment: View {
        let title: String
        let selected: Bool
        let namespace: Namespace.ID
        let action: () -> Void
        @State private var hover = false

        var body: some View {
            Button(action: action) {
                Text(title)
                    .nlType(.label)
                    .foregroundStyle(selected || hover ? NL.textPrimary : NL.textSecondary)
                    .padding(.horizontal, Space.s4)
                    .frame(height: 26)
                    .background {
                        if selected {
                            RoundedRectangle(cornerRadius: Radius.sm, style: .continuous)
                                .fill(NL.surface)
                                .nlShadow(.xs)
                                .overlay {
                                    RoundedRectangle(cornerRadius: Radius.sm, style: .continuous)
                                        .strokeBorder(NL.borderSubtle, lineWidth: 1)
                                }
                                .matchedGeometryEffect(id: "thumb", in: namespace)
                        }
                    }
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .onHover { hover = $0 }
            .animation(Motion.fast, value: hover)
            .accessibilityAddTraits(selected ? .isSelected : [])
        }
    }
}

/// Готовность распознавания - точкой и словом.
private struct EngineStatus: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        HStack(spacing: Space.s1_5) {
            Circle().fill(tone).frame(width: 6, height: 6)
            Text(state.statusText)
                .nlType(.caption)
                .foregroundStyle(NL.textTertiary)
                .lineLimit(1)
                .contentTransition(.opacity)
        }
        .motion(Motion.base, value: state.statusText)
        .accessibilityElement(children: .combine)
    }

    private var tone: Color {
        if state.isRecording { return NL.danger }
        if !state.micGranted { return NL.warning }
        switch state.backend {
        case .ready: return NL.success
        case .failed: return NL.danger
        case .starting: return NL.warning
        }
    }
}

/// Поле поиска Northline: surface, граница, иконка третичным; в фокусе -
/// граница и кольцо акцента. ⌘F - забирает фокус, Esc - очищает.
struct SearchField: View {
    @Binding var text: String
    var focusRequest: Int
    @FocusState private var focused: Bool

    var body: some View {
        HStack(spacing: Space.s1_5) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 12))
                .foregroundStyle(NL.iconTertiary)
            TextField("", text: $text, prompt: Text("Поиск").foregroundColor(NL.textPlaceholder))
                .textFieldStyle(.plain)
                .nlType(.bodySm)
                .foregroundStyle(NL.textPrimary)
                .focused($focused)
                .onExitCommand { text = ""; focused = false }
            if !text.isEmpty {
                Button { text = "" } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 12))
                        .foregroundStyle(NL.iconTertiary)
                }
                .buttonStyle(.plain)
                .help("Очистить поиск")
            } else {
                Text("⌘F")
                    .nlType(.labelXs)
                    .foregroundStyle(NL.textTertiary)
            }
        }
        .padding(.horizontal, Space.s2)
        .frame(height: Size.controlSm)
        .background(NL.surface, in: RoundedRectangle(cornerRadius: Radius.sm, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: Radius.sm, style: .continuous)
                .strokeBorder(focused ? NL.borderFocus : NL.border, lineWidth: 1)
        }
        .background {
            RoundedRectangle(cornerRadius: Radius.sm + 3, style: .continuous)
                .fill(NL.ringFocus)
                .padding(-3)
                .opacity(focused ? 1 : 0)
        }
        .animation(Motion.base, value: focused)
        .onChange(of: focusRequest) { _, _ in focused = true }
    }
}

// MARK: - мост AppKit -> сцены

/// Главное окно открывается только действием из окружения SwiftUI, а
/// просят о нём и строка меню, и Док. Окно запоминает его при первом показе.
@MainActor
enum SceneBridge {
    static var openWindow: OpenWindowAction?

    static func showMain() {
        NSApp.activate()
        if let openWindow {
            openWindow(id: "main")
        } else {
            NSApp.windows.first { $0.canBecomeMain }?.makeKeyAndOrderFront(nil)
        }
    }
}

struct SceneBridgeCapture: ViewModifier {
    @Environment(\.openWindow) private var openWindow

    func body(content: Content) -> some View {
        content.onAppear { SceneBridge.openWindow = openWindow }
    }
}
