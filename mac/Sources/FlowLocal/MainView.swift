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
    /// Ещё раз завести окружение распознавания (не скачалось - нет сети).
    var retrySetup: () -> Void = {}
    var openRecordings: () -> Void = {}
    /// Настройки - в Hub Settings.
    var openSettings: () -> Void = {}
    var showMain: () -> Void = {}
    var showTutorial: () -> Void = {}
    var find: () -> Void = {}
}

enum AppInfo {
    static var version: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "dev"
    }

    static let helpURL = URL(string: "https://github.com/romankandeevy/flowlocal/tree/main/mac#readme")!
}

// Главное окно - одно на всё: слева сайдбар с разделами, неделей и
// состоянием, справа раздел. Заголовка у окна нет - «светофоры» лежат на
// сайдбаре, а за верхнюю полосу и пустое место сайдбара окно можно тянуть.
// Смена раздела - новый проступает со сдвигом, прежний уходит сразу.
struct MainView: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    var body: some View {
        HStack(spacing: 0) {
            Sidebar(actions: actions)
            NL.sidebarBorder.frame(width: 1)
            VStack(spacing: 0) {
                WindowDragArea()
                    .frame(height: Space.s8 + Space.s1)
                // Смена раздела без общей анимации: прежний раздел уходит
                // сразу, новый проступает сам (PageAppear). С переходом в
                // ZStack уходящий держался поверх нового, пока шла пружина.
                Group {
                    switch state.tab {
                    case .home: HomeView(actions: actions)
                    case .history: HistoryView(actions: actions)
                    case .stats: StatsView()
                    case .style: StyleView()
                    case .dictionary: DictionaryView()
                    }
                }
                .id(state.tab)
                .modifier(PageAppear())
                .transaction(value: state.tab) { $0.animation = nil }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .background(NL.canvas)
        }
        .ignoresSafeArea(.container, edges: .top)
        .frame(minWidth: 820, minHeight: 540)
        .background(NL.canvas)
        .tint(NL.accent)
        .sheet(item: $state.editing) { entry in
            EditEntrySheet(entry: entry)
        }
        .modifier(SceneBridgeCapture())
    }

    static func clock(_ t: TimeInterval) -> String {
        let s = max(0, Int(t))
        return String(format: "%d:%02d", s / 60, s % 60)
    }
}

/// Новый раздел проступает со сдвигом на 6pt - своей анимацией, не
/// общей со сменой раздела.
private struct PageAppear: ViewModifier {
    @State private var shown = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func body(content: Content) -> some View {
        content
            .opacity(shown ? 1 : 0)
            .offset(y: shown || reduceMotion ? 0 : 6)
            .onAppear {
                if reduceMotion { shown = true } else { withAnimation(Motion.moderate) { shown = true } }
            }
    }
}

/// Страница раздела: колонка до 760pt по центру, поля 40pt.
struct PageScroll<Content: View>: View {
    @ViewBuilder var content: () -> Content

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28, content: content)
                .frame(maxWidth: Space.contentMax, alignment: .leading)
                .padding(.horizontal, Space.page)
                .padding(.top, Space.s3)
                .padding(.bottom, Space.s12)
                .frame(maxWidth: .infinity)
        }
        .scrollIndicators(.automatic)
    }
}

// MARK: - сайдбар

private struct Sidebar: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions
    @Namespace private var thumb

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            // Место «светофоров».
            Color.clear.frame(height: 50)
            ForEach(Tab.allCases) { tab in
                NavItem(tab: tab, selected: state.tab == tab, namespace: thumb) {
                    withMotion(Motion.position) { state.tab = tab }
                }
            }
            Spacer(minLength: Space.s4)
            if !state.history.isEmpty {
                WeekCard()
                    .transition(.opacity)
            }
            WhisperSwitch()
                .padding(.top, Space.s3)
            StatusLine(actions: actions)
                .padding(.top, Space.s2)
        }
        .padding(.horizontal, Space.s3)
        .padding(.bottom, Space.s3 + 2)
        .frame(width: Size.sidebar)
        .frame(maxHeight: .infinity, alignment: .top)
        .background { WindowDragArea() }
        .background(NL.sidebar)
        .motion(Motion.moderate, value: state.history.isEmpty)
    }
}

/// Пункт сайдбара: значок и название. Выбранный - карточкой, которая
/// переезжает под новый пункт.
private struct NavItem: View {
    let tab: Tab
    let selected: Bool
    let namespace: Namespace.ID
    let action: () -> Void
    @State private var hover = false

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                Image(systemName: tab.symbol)
                    .font(.system(size: 13, weight: .medium))
                    .frame(width: 18)
                Text(tab.title)
                    .font(NLFont.ui(13.5, selected ? .semibold : .medium))
                Spacer(minLength: 0)
            }
            .foregroundStyle(selected || hover ? NL.textPrimary : NL.textSecondary)
            .padding(.horizontal, 10)
            .frame(height: 34)
            .background {
                if selected {
                    RoundedRectangle(cornerRadius: 9, style: .continuous)
                        .fill(NL.surface)
                        .shadow(color: .black.opacity(0.06), radius: 1, y: 1)
                        .overlay {
                            RoundedRectangle(cornerRadius: 9, style: .continuous)
                                .strokeBorder(NL.border, lineWidth: 1)
                        }
                        .matchedGeometryEffect(id: "thumb", in: namespace)
                } else if hover {
                    RoundedRectangle(cornerRadius: 9, style: .continuous)
                        .fill(NL.hover)
                }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { hover = $0 }
        .animation(Motion.fast, value: hover)
        .help("\(tab.title) (⌘\(String(tab.shortcut.character)))")
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}

/// Неделя в сайдбаре: слова и сэкономленное время.
private struct WeekCard: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("На этой неделе")
                .nlType(.caption)
                .foregroundStyle(NL.textTertiary)
            Text(wordsLabel(state.wordsWeek))
                .font(NLFont.ui(22, .bold))
                .tracking(-0.4)
                .monospacedDigit()
                .foregroundStyle(NL.textPrimary)
                .contentTransition(.numericText())
            Text(saved)
                .nlType(.caption)
                .foregroundStyle(NL.textTertiary)
        }
        .padding(14)
        .nlCard(padding: 0, radius: 12)
        .motion(Motion.slow, value: state.wordsWeek)
    }

    private var saved: String {
        let m = state.savedMinutes(days: 7)
        return m > 0 ? "≈ \(grouped(m)) мин сэкономлено" : "Говорите — время начнёт копиться"
    }
}

/// Готовность распознавания - точкой и словом; справа - настройки.
private struct StatusLine: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions
    @State private var hover = false

    var body: some View {
        HStack(spacing: 7) {
            Circle().fill(tone).frame(width: 6, height: 6)
            Text(state.statusText)
                .nlType(.caption)
                .foregroundStyle(NL.textTertiary)
                .lineLimit(1)
                .contentTransition(.opacity)
            Spacer(minLength: 0)
            Button(action: actions.openSettings) {
                Image(systemName: "gearshape")
                    .font(.system(size: 13))
                    .foregroundStyle(hover ? NL.textPrimary : NL.textTertiary)
                    .frame(width: 26, height: 26)
                    .background(Circle().fill(hover ? NL.hover : .clear))
                    .contentShape(Circle())
            }
            .buttonStyle(.plain)
            .onHover { hover = $0 }
            .animation(Motion.fast, value: hover)
            .help("Настройки (⌘,)")
            .accessibilityLabel("Настройки")
        }
        .padding(.leading, 6)
        .motion(Motion.base, value: state.statusText)
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

/// Режим шёпота одним щелчком: капсула-переключатель над состоянием.
private struct WhisperSwitch: View {
    @EnvironmentObject var state: AppState
    @State private var hover = false

    var body: some View {
        Button {
            withMotion(Motion.base) { state.whisperMode.toggle() }
        } label: {
            HStack(spacing: 8) {
                Image(systemName: state.whisperMode ? "waveform.badge.mic" : "waveform")
                    .font(.system(size: 12, weight: .medium))
                    .contentTransition(.symbolEffect(.replace))
                    .frame(width: 18)
                Text("Шёпот")
                    .font(NLFont.ui(13, .medium))
                Spacer(minLength: 0)
                Capsule()
                    .fill(state.whisperMode ? NL.accent : NL.borderStrong)
                    .frame(width: 26, height: 15)
                    .overlay(alignment: state.whisperMode ? .trailing : .leading) {
                        Circle().fill(.white).frame(width: 11, height: 11).padding(2)
                            .shadow(color: .black.opacity(0.15), radius: 1, y: 0.5)
                    }
            }
            .foregroundStyle(state.whisperMode ? NL.textPrimary : NL.textSecondary)
            .padding(.horizontal, 10)
            .frame(height: 32)
            .background(RoundedRectangle(cornerRadius: 9, style: .continuous).fill(hover ? NL.hover : .clear))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { hover = $0 }
        .animation(Motion.fast, value: hover)
        .help("Режим шёпота: тихая речь усиливается (⌥⌘W)")
        .accessibilityLabel("Режим шёпота")
        .accessibilityValue(state.whisperMode ? "включён" : "выключен")
    }
}

/// «Исправить…»: текст диктовки целиком; сохранили - поправки учатся.
private struct EditEntrySheet: View {
    @EnvironmentObject var state: AppState
    @Environment(\.dismiss) private var dismiss
    let entry: Entry
    @State private var text = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Исправить диктовку")
                    .font(NLFont.ui(18, .semibold))
                    .foregroundStyle(NL.textPrimary)
                Text(state.learnFromEdits
                     ? "Поправьте слова, которые модель написала неправильно, — в следующий раз они напишутся верно."
                     : "Обучение на исправлениях выключено в «Словаре».")
                    .font(NLFont.ui(13))
                    .foregroundStyle(NL.textTertiary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            TextEditor(text: $text)
                .font(NLFont.ui(15))
                .lineSpacing(4)
                .scrollContentBackground(.hidden)
                .padding(10)
                .frame(minHeight: 160)
                .background(NL.surface, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                .overlay {
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .strokeBorder(NL.border, lineWidth: 1)
                }
            HStack {
                Spacer()
                Button("Отменить") { dismiss() }
                    .keyboardShortcut(.cancelAction)
                    .nlButton(.ghost)
                Button("Сохранить") {
                    state.saveEdit(entry, text: text)
                    dismiss()
                }
                .keyboardShortcut(.defaultAction)
                .buttonStyle(InkButtonStyle())
            }
        }
        .padding(24)
        .frame(width: 520)
        .background(NL.canvas)
        .onAppear { text = entry.text }
    }
}

// MARK: - перетаскивание окна

/// Пустое место, за которое тянут окно: у окна без заголовка иначе
/// перетаскивать не за что - SwiftUI забирает щелчки себе.
struct WindowDragArea: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView { DragView() }
    func updateNSView(_ nsView: NSView, context: Context) {}

    private final class DragView: NSView {
        override var mouseDownCanMoveWindow: Bool { true }

        override func mouseDown(with event: NSEvent) {
            if event.clickCount == 2 {
                window?.performZoom(nil)
            } else {
                window?.performDrag(with: event)
            }
        }
    }
}

// MARK: - поиск

/// Поле поиска: карточка 40pt, лупа, ⌘F справа; в фокусе - кольцо
/// акцента. ⌘F забирает фокус, Esc очищает.
struct SearchField: View {
    @Binding var text: String
    var focusRequest: Int
    @FocusState private var focused: Bool

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 14))
                .foregroundStyle(NL.iconTertiary)
            TextField("", text: $text, prompt: Text("Найти по словам").foregroundColor(NL.textPlaceholder))
                .textFieldStyle(.plain)
                .font(NLFont.ui(14))
                .foregroundStyle(NL.textPrimary)
                .focused($focused)
                .onExitCommand { text = ""; focused = false }
            if !text.isEmpty {
                Button { text = "" } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 13))
                        .foregroundStyle(NL.iconTertiary)
                }
                .buttonStyle(.plain)
                .help("Очистить поиск")
                .transition(.opacity)
            } else {
                Text("⌘F")
                    .font(NLFont.ui(11.5, .semibold))
                    .foregroundStyle(NL.textTertiary)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 1)
                    .overlay {
                        RoundedRectangle(cornerRadius: 5, style: .continuous)
                            .strokeBorder(NL.border, lineWidth: 1)
                    }
                    .transition(.opacity)
            }
        }
        .padding(.horizontal, 14)
        .frame(height: 40)
        .background(NL.surface, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .strokeBorder(focused ? NL.borderFocus : NL.border, lineWidth: focused ? 1 : 0.5)
        }
        .background {
            RoundedRectangle(cornerRadius: 15, style: .continuous)
                .fill(NL.ringFocus)
                .padding(-3)
                .opacity(focused ? 1 : 0)
        }
        .animation(Motion.base, value: focused)
        .animation(Motion.fast, value: text.isEmpty)
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
