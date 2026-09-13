import AppKit
import SwiftUI

/// Что окно умеет попросить у приложения. Замыкания подключает AppDelegate,
/// вью про контроллер не знают.
struct AppActions {
    var beginCapture: (HotkeyRole) -> Void = { _ in }
    var cancelCapture: () -> Void = {}
    var resetHotkey: (HotkeyRole) -> Void = { _ in }
    var cancelProcessing: () -> Void = {}
    var paste: (Entry) -> Void = { _ in }
    var rerecognize: (Entry) -> Void = { _ in }
    var play: (Entry) -> Void = { _ in }
    var setLaunchAtLogin: (Bool) -> Void = { _ in }
    var openLog: () -> Void = {}
    var openRecordings: () -> Void = {}
    var selectMic: (String?) -> Void = { _ in }
}

// Корень окна - как у приложений Apple на Mac: сайдбар на системном
// материале во всю высоту, под «светофорами», справа чёрная сцена со строкой
// заголовка на месте панели инструментов. Узкое окно - сайдбар сжимается до
// значков; широкое - на «Главной» справа появляются «Недавние».
struct MainView: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    static let sidebarWidth: CGFloat = 212
    static let railWidth: CGFloat = 80          // шире «светофоров» - они стоят над сайдбаром
    static let railBelow: CGFloat = 820         // уже - сайдбар из значков
    static let panelFrom: CGFloat = 860         // ширина сцены под «Недавние»

    var body: some View {
        GeometryReader { geo in
            let rail = geo.size.width < Self.railBelow
            let side = rail ? Self.railWidth : Self.sidebarWidth
            HStack(spacing: 0) {
                Sidebar(rail: rail)
                    .frame(width: side)
                VStack(spacing: 0) {
                    PageHeader()
                        .zIndex(1)
                    // clipped: прокрутка не должна заезжать под строку заголовка.
                    page(wide: geo.size.width - side >= Self.panelFrom)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .clipped()
                }
                .background(state.palette.bg)
            }
        }
        .ignoresSafeArea()
        .environment(\.colorScheme, .dark)
        .animation(Motion.page, value: state.tab)
    }

    @ViewBuilder
    private func page(wide: Bool) -> some View {
        switch state.tab {
        case .home: HomeView(actions: actions, wide: wide)
        case .history: HistoryView(actions: actions)
        case .stats: StatsView()
        case .settings: SettingsView(actions: actions)
        }
    }

    static func clock(_ t: TimeInterval) -> String {
        let s = max(0, Int(t))
        return String(format: "%d:%02d", s / 60, s % 60)
    }
}

enum AppInfo {
    static var version: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "dev"
    }
}

// MARK: - сайдбар

struct Sidebar: View {
    @EnvironmentObject var state: AppState
    let rail: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            // Место под «светофоры» окна.
            Color.clear.frame(height: Metric.toolbar)
            ForEach(Array(Tab.allCases.enumerated()), id: \.element) { i, tab in
                SidebarRow(tab: tab, index: i + 1, rail: rail)
            }
            Spacer(minLength: Space.s4)
            SidebarStatus(rail: rail)
        }
        .padding(.horizontal, 10)
        .padding(.bottom, Space.s3)
        .frame(maxHeight: .infinity, alignment: .top)
        .background {
            // Материал сам по себе пропускает цвет обоев (зелень, небо) - рядом с
            // чёрной сценой это читалось чужим цветом. Спецификация сайдбара:
            // «blur 40 · black 60 %» - затемняем поверх материала.
            ZStack {
                VisualEffect(material: .sidebar)
                Color.black.opacity(0.6)
            }
        }
        .overlay(alignment: .trailing) { FLSeparator(vertical: true, color: .black.opacity(0.6)) }
    }
}

/// Ряд сайдбара 28 pt: глиф в покое secondaryLabel, при наведении label,
/// у выбранного - systemBlue на подложке fill/2. ⌘1…⌘4 - переход.
struct SidebarRow: View {
    @EnvironmentObject var state: AppState
    let tab: Tab
    let index: Int
    let rail: Bool
    @State private var hover = false

    var body: some View {
        let p = state.palette
        let on = state.tab == tab
        Button { state.tab = tab } label: {
            HStack(spacing: Space.s2) {
                Image(systemName: tab.symbol)
                    .font(.system(size: 14))
                    .foregroundStyle(on ? p.accent : (hover ? p.text : p.textMuted))
                    .frame(width: 20)
                if !rail {
                    Text(tab.title).textStyle(.body, p.text).lineLimit(1)
                    Spacer(minLength: 0)
                    if tab == .history && !state.history.isEmpty {
                        Text("\(state.history.count)")
                            .textStyle(.subheadline, p.textMuted)
                            .monospacedDigit()
                    }
                }
            }
            .padding(.horizontal, rail ? 0 : Space.s2)
            .frame(maxWidth: .infinity, alignment: rail ? .center : .leading)
            .frame(height: rail ? 36 : Metric.row)
            .background(RoundedRectangle(cornerRadius: Radius.control, style: .continuous)
                .fill(on ? p.fill2 : (hover ? p.fill4 : .clear)))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .keyboardShortcut(KeyEquivalent(Character(String(index))), modifiers: .command)
        .help("\(tab.title) · ⌘\(index)")
        .onHover { hover = $0 }
        .animation(Motion.hover, value: hover)
    }
}

/// Спокойное состояние внизу сайдбара. Важное (нет микрофона, ошибка) ещё и
/// на самой «Главной» - низ сайдбара HIG не считает местом для критичного.
struct SidebarStatus: View {
    @EnvironmentObject var state: AppState
    let rail: Bool

    var body: some View {
        let p = state.palette
        let s = status(p)
        HStack(spacing: Space.s2) {
            StatusDot(color: s.color, pulse: s.pulse)
                .frame(width: 20)
            if !rail {
                VStack(alignment: .leading, spacing: 1) {
                    Text(s.title).textStyle(.headline, p.text).lineLimit(1)
                    Text(s.detail).textStyle(.subheadline, p.textMuted).lineLimit(1)
                }
                Spacer(minLength: 0)
            }
        }
        .padding(.horizontal, rail ? 0 : Space.s2)
        .padding(.vertical, Space.s2)
        .frame(maxWidth: .infinity, alignment: rail ? .center : .leading)
        .help("\(s.title) · \(s.detail)")
        .animation(Motion.page, value: s.title)
    }

    private func status(_ p: Palette) -> (color: Color, title: String, detail: String, pulse: Bool) {
        switch state.phase {
        case .recording: return (p.danger, "Идёт запись", "Esc — отменить", true)
        case .processing: return (p.accent, "Распознаю", "Меньше секунды", false)
        default: break
        }
        if !state.micGranted { return (p.danger, "Нет микрофона", "Нужен доступ в macOS", false) }
        switch state.backend {
        case .starting: return (p.warning, "Загрузка", "Модели распознавания", false)
        case .failed: return (p.danger, "Ошибка", "Распознавание не запустилось", false)
        case .ready: return (p.success, "Готов", state.englishReady ? "GigaAM v3 · Parakeet" : "GigaAM v3", false)
        }
    }
}

// MARK: - строка заголовка

/// Полоса 52 pt на месте панели инструментов: заголовок страницы 15/600
/// слева, её инструменты справа.
struct PageHeader: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        HStack(spacing: Space.s3) {
            Text(state.tab.title)
                .textStyle(.title3, state.palette.text, weight: .semibold)
                .id(state.tab)
                .transition(.opacity)
            Spacer(minLength: Space.s3)
            switch state.tab {
            case .home: HomeStatus()
            case .history: HistoryTools()
            default: EmptyView()
            }
        }
        .padding(.horizontal, Space.s5)
        .frame(height: Metric.toolbar)
        .background(state.palette.bg)
    }
}

/// Справа в заголовке «Главной»: идёт запись, распознавание или покой.
struct HomeStatus: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        let p = state.palette
        switch state.phase {
        case let .recording(since, _):
            TimelineView(.periodic(from: since, by: 1)) { ctx in
                HStack(spacing: Space.s2) {
                    StatusDot(color: p.danger, pulse: true)
                    Text("Запись · \(MainView.clock(ctx.date.timeIntervalSince(since)))")
                        .font(.system(size: 12, weight: .semibold))
                        .monospacedDigit()
                        .foregroundStyle(p.text)
                }
                .padding(.horizontal, 10)
                .frame(height: 24)
                .background(Capsule().fill(p.wash(p.danger)))
            }
        case .processing:
            HStack(spacing: Space.s2) {
                ProgressView().controlSize(.small)
                Text("Распознаю").font(.system(size: 12, weight: .semibold)).foregroundStyle(p.text)
            }
        default:
            HStack(spacing: 6) {
                Image(systemName: "lock.fill").font(.system(size: 10, weight: .semibold))
                Text("Всё остаётся на этом Mac").font(TextStyle.subheadline.font())
            }
            .foregroundStyle(p.textMuted)
        }
    }
}

/// Справа в заголовке «Истории»: поиск и очистка с подтверждением.
struct HistoryTools: View {
    @EnvironmentObject var state: AppState
    @State private var confirm = false

    var body: some View {
        HStack(spacing: Space.s2) {
            FLSearchField(text: $state.historyQuery, placeholder: "Поиск по диктовкам")
                .frame(width: 220)
            if !state.history.isEmpty {
                Button {
                    if confirm {
                        withAnimation(Motion.page) { state.clearHistory() }
                        confirm = false
                    } else {
                        withAnimation(Motion.press) { confirm = true }
                        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                            withAnimation(Motion.press) { confirm = false }
                        }
                    }
                } label: {
                    Label(confirm ? "Удалить все?" : "Очистить",
                          systemImage: confirm ? "exclamationmark.triangle.fill" : "trash")
                        .contentTransition(.symbolEffect(.replace))
                }
                .buttonStyle(FLButtonStyle(kind: confirm ? .destructive : .plain))
            }
        }
    }
}
