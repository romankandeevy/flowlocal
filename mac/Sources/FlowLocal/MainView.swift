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

// Корень окна по макету «Flow Local - главный экран»: шапка на месте
// заголовка окна, вкладки, содержимое, строка состояния. Окно тянется:
// уже 880 px панель истории уходит, уже 760 px сжимается шапка.
struct MainView: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    static let wideWidth: CGFloat = 880
    static let compactWidth: CGFloat = 760

    var body: some View {
        let p = state.palette
        GeometryReader { geo in
            let w = geo.size.width
            VStack(spacing: 0) {
                header(p, width: w)
                VKDivider(palette: p)
                content(p, wide: w >= Self.wideWidth)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                VKDivider(palette: p)
                footer(p, width: w)
            }
            .background(p.bg)
            .overlay(frame(p))
        }
        .environment(\.colorScheme, state.theme.colorScheme)
        .animation(Motion.base, value: state.theme)
        .animation(Motion.base, value: state.tab)
    }

    // MARK: - шапка

    // Уже 860 px уходят версия и спокойный статус, уже 700 px - знак. Вкладки
    // остаются целыми всегда: обрезанное «СТАТИС…» хуже, чем отсутствие знака.
    private func header(_ p: Palette, width: CGFloat) -> some View {
        let roomy = width >= 860
        let brand = width >= 700
        return HStack(spacing: Space.s4) {
            if brand {
                Text("Flow Local")
                    .textCase(.uppercase)
                    .displayTitle(p.text, size: FontSize.fs3)
                    .lineLimit(1)
                    .fixedSize()
                if roomy {
                    Text(AppInfo.version).monoLabel(p.textMuted)
                }
                VKDivider(palette: p, vertical: true).frame(height: 20)
            }
            VKTabBar(selection: $state.tab, palette: p, compact: !roomy)
                .fixedSize(horizontal: true, vertical: false)
            Spacer(minLength: Space.s3)
            status(p, compact: !roomy)
        }
        // Слева - место под системные «светофоры» окна.
        .padding(.leading, 84)
        .padding(.trailing, Space.s4)
        .frame(height: 52)
        .background(p.surface)
    }

    @ViewBuilder
    private func status(_ p: Palette, compact: Bool) -> some View {
        // В тесной шапке важное (запись, распознавание, ошибка) остаётся
        // значком, спокойное «ЛОКАЛЬНО» уходит совсем.
        HStack(spacing: 10) {
            switch state.phase {
            case .recording:
                VKBlink(color: p.danger)
                if !compact { Text("Запись").monoLabel(p.text) }
            case .processing:
                VKPulseBlocks(color: p.accent)
                if !compact { Text("Распознаю").monoLabel(p.text) }
            default:
                if !state.micGranted {
                    Rectangle().fill(p.danger).frame(width: 8, height: 8)
                    if !compact { Text("Микрофон недоступен").monoLabel(p.text) }
                } else if state.backend == .starting {
                    if compact {
                        Rectangle().fill(p.warning).frame(width: 8, height: 8)
                    } else {
                        VKBadge(text: "Загрузка", tone: .warning, palette: p)
                    }
                } else if case .failed = state.backend {
                    if compact {
                        Rectangle().fill(p.danger).frame(width: 8, height: 8)
                    } else {
                        VKBadge(text: "Ошибка", tone: .danger, palette: p)
                    }
                } else if !compact {
                    VKBadge(text: "Локально", tone: .outline, palette: p)
                }
            }
        }
        .fixedSize()
    }

    // MARK: - содержимое

    @ViewBuilder
    private func content(_ p: Palette, wide: Bool) -> some View {
        switch state.tab {
        case .home:
            HStack(spacing: 0) {
                HomeView(actions: actions)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                if wide {
                    VKDivider(palette: p, vertical: true)
                    HistoryPanel(actions: actions)
                        .frame(width: 320)
                }
            }
        case .history:
            HistoryView(actions: actions)
        case .stats:
            StatsView()
        case .settings:
            SettingsView(actions: actions)
        }
    }

    // MARK: - строка состояния

    private func footer(_ p: Palette, width: CGFloat) -> some View {
        HStack(spacing: Space.s5) {
            footerLeft(p, compact: width < Self.compactWidth)
            Spacer(minLength: Space.s3)
            Text("Без сети · без аккаунта").monoLabel(p.textMuted).lineLimit(1)
        }
        .padding(.horizontal, Space.s4)
        .frame(height: 36)
        .background(p.surface)
    }

    @ViewBuilder
    private func footerLeft(_ p: Palette, compact: Bool) -> some View {
        switch state.phase {
        case let .recording(since, locked):
            TimelineView(.periodic(from: since, by: 0.5)) { ctx in
                Text("Запись \(Self.clock(ctx.date.timeIntervalSince(since)))").monoLabel(p.text)
            }
            if !compact {
                Text(locked ? "/ \(state.toggleHotkey.label) ещё раз — вставить · Esc — отменить" : "/ Esc — отменить")
                    .monoLabel(p.textMuted).lineLimit(1)
            }
        case .processing:
            Text("Распознавание").monoLabel(p.textMuted)
        default:
            if !state.micGranted {
                Text("Диктовка недоступна").monoLabel(p.textMuted)
            } else if state.backend == .starting {
                Text("Загрузка моделей").monoLabel(p.textMuted)
            } else {
                Text("Зажать \(state.hotkey.label)").monoLabel(p.textMuted).lineLimit(1)
                if !compact {
                    Text("/ Нажать \(state.toggleHotkey.label)").monoLabel(p.textMuted).lineLimit(1)
                }
            }
        }
    }

    // Во время записи всё окно обведено акцентом - как на макете 1b.
    @ViewBuilder
    private func frame(_ p: Palette) -> some View {
        if case .recording = state.phase {
            Rectangle().strokeBorder(p.accent, lineWidth: Space.strong).allowsHitTesting(false)
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
