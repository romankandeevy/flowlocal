import AppKit
import SwiftUI
import UniformTypeIdentifiers

// «Стиль» - как писать текст в каждом приложении и как слушать голос.
// Сверху - четыре стиля с примером; под ними - приложения со своим стилем;
// остальные пишутся по общим настройкам. Ниже - режим шёпота.
struct StyleView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        PageScroll {
            VStack(alignment: .leading, spacing: Space.s2) {
                PageTitle("Стиль")
                Text("Как писать текст там, куда вы диктуете. Приложение узнаётся по тому, какое было впереди в начале записи.")
                    .font(NLFont.ui(14.5))
                    .lineSpacing(3)
                    .foregroundStyle(NL.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            styles
            apps
            voice
        }
    }

    private var styles: some View {
        HStack(spacing: 10) {
            ForEach(TextStyle.allCases) { style in
                VStack(alignment: .leading, spacing: 8) {
                    Text(style.title)
                        .font(NLFont.ui(13.5, .semibold))
                        .foregroundStyle(NL.textPrimary)
                    Text(style.sample)
                        .font(NLFont.ui(13, .medium))
                        .foregroundStyle(NL.textPrimary)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 7)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(NL.canvas, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                    Text(style.detail)
                        .font(NLFont.ui(12))
                        .foregroundStyle(NL.textTertiary)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                }
                .padding(14)
                .frame(maxHeight: .infinity, alignment: .top)
                .nlCard(padding: 0, radius: 12)
            }
        }
        .fixedSize(horizontal: false, vertical: true)
    }

    private var apps: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                SectionHeading("Приложения")
                Spacer()
                AddAppMenu()
            }
            VStack(spacing: 0) {
                ForEach(Array(state.appStyles.enumerated()), id: \.element.id) { index, rule in
                    AppRuleRow(rule: rule)
                        .overlay(alignment: .top) {
                            if index > 0 { NL.borderSubtle.frame(height: 1) }
                        }
                        .transition(.opacity)
                }
                HStack(spacing: 12) {
                    Image(systemName: "square.grid.2x2")
                        .font(.system(size: 15))
                        .foregroundStyle(NL.iconTertiary)
                        .frame(width: 28, height: 28)
                    Text("Все остальные")
                        .font(NLFont.ui(14))
                        .foregroundStyle(NL.textSecondary)
                    Spacer()
                    Text("Обычный")
                        .font(NLFont.ui(13, .medium))
                        .foregroundStyle(NL.textTertiary)
                        .padding(.trailing, 6)
                }
                .padding(.horizontal, 16)
                .frame(height: 54)
                .overlay(alignment: .top) {
                    if !state.appStyles.isEmpty { NL.borderSubtle.frame(height: 1) }
                }
            }
            .nlCard(padding: 0)
            .motion(Motion.moderate, value: state.appStyles.map(\.id))
        }
    }

    private var voice: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeading("Голос")
            VStack(spacing: 0) {
                ToggleRow(title: "Режим шёпота",
                          detail: "Тихая речь усиливается до обычной: можно диктовать вполголоса — в офисе или ночью. Включается и в сайдбаре, и в меню «Диктовка» (⌥⌘W).",
                          isOn: $state.whisperMode)
            }
            .nlCard(padding: 0)
        }
    }
}

/// Приложение и его стиль.
private struct AppRuleRow: View {
    @EnvironmentObject var state: AppState
    let rule: AppStyleRule
    @State private var hover = false

    var body: some View {
        HStack(spacing: 12) {
            AppIcon(bundleID: rule.bundleID)
                .frame(width: 28, height: 28)
            Text(rule.name)
                .font(NLFont.ui(14, .medium))
                .foregroundStyle(NL.textPrimary)
            Spacer()
            Picker("", selection: binding) {
                ForEach(TextStyle.allCases) { Text($0.title).tag($0) }
            }
            .labelsHidden()
            .pickerStyle(.menu)
            .fixedSize()
            Button {
                withMotion(Motion.moderate) { state.appStyles.removeAll { $0.id == rule.id } }
            } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(NL.textTertiary)
                    .frame(width: 26, height: 26)
                    .background(Circle().fill(hover ? NL.hover : .clear))
                    .contentShape(Circle())
            }
            .buttonStyle(.plain)
            .opacity(hover ? 1 : 0)
            .help("Убрать — будет «Обычный»")
            .accessibilityLabel("Убрать \(rule.name)")
        }
        .padding(.horizontal, 16)
        .frame(height: 54)
        .background(hover ? NL.rowHover : .clear)
        .onHover { hover = $0 }
        .animation(Motion.fast, value: hover)
    }

    private var binding: Binding<TextStyle> {
        Binding {
            state.appStyles.first { $0.id == rule.id }?.style ?? .standard
        } set: { value in
            if let i = state.appStyles.firstIndex(where: { $0.id == rule.id }) { state.appStyles[i].style = value }
        }
    }
}

/// «Добавить приложение»: запущенные - списком, остальные - через Finder.
private struct AddAppMenu: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        Menu {
            let running = runningApps
            if !running.isEmpty {
                Section("Открытые") {
                    ForEach(running, id: \.bundleID) { app in
                        Button(app.name) { add(app.bundleID, app.name) }
                    }
                }
            }
            Button("Выбрать в «Программах»…", action: pick)
        } label: {
            Label("Добавить приложение", systemImage: "plus")
                .font(NLFont.ui(13, .medium))
        }
        .menuStyle(.borderlessButton)
        .menuIndicator(.hidden)
        .fixedSize()
        .foregroundStyle(NL.textAccent)
    }

    private var runningApps: [(bundleID: String, name: String)] {
        let taken = Set(state.appStyles.map(\.bundleID))
        return NSWorkspace.shared.runningApplications
            .filter { $0.activationPolicy == .regular }
            .compactMap { app in
                guard let id = app.bundleIdentifier, id != Bundle.main.bundleIdentifier, !taken.contains(id) else { return nil }
                return (id, app.localizedName ?? id)
            }
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    private func add(_ id: String, _ name: String) {
        guard !state.appStyles.contains(where: { $0.bundleID == id }) else { return }
        withMotion(Motion.moderate) { state.appStyles.append(AppStyleRule(bundleID: id, name: name, style: .chat)) }
    }

    private func pick() {
        let panel = NSOpenPanel()
        panel.directoryURL = URL(fileURLWithPath: "/Applications")
        panel.allowedContentTypes = [.application]
        panel.allowsMultipleSelection = false
        panel.prompt = "Добавить"
        guard panel.runModal() == .OK, let url = panel.url, let bundle = Bundle(url: url),
              let id = bundle.bundleIdentifier else { return }
        let name = FileManager.default.displayName(atPath: url.path).replacingOccurrences(of: ".app", with: "")
        add(id, name)
    }
}

/// Значок приложения по идентификатору.
struct AppIcon: View {
    let bundleID: String

    var body: some View {
        if let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: bundleID) {
            Image(nsImage: NSWorkspace.shared.icon(forFile: url.path))
                .resizable()
                .interpolation(.high)
        } else {
            RoundedRectangle(cornerRadius: 7, style: .continuous)
                .fill(NL.subtle)
                .overlay {
                    Image(systemName: "app.dashed").foregroundStyle(NL.iconTertiary)
                }
        }
    }
}

/// Строка с переключателем: название, пояснение, тумблер справа.
struct ToggleRow: View {
    let title: String
    let detail: String
    @Binding var isOn: Bool

    var body: some View {
        HStack(alignment: .center, spacing: Space.s4) {
            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(NLFont.ui(14.5, .semibold))
                    .foregroundStyle(NL.textPrimary)
                Text(detail)
                    .font(NLFont.ui(12.5))
                    .foregroundStyle(NL.textTertiary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: Space.s4)
            Toggle("", isOn: $isOn.animation(Motion.base))
                .labelsHidden()
                .toggleStyle(.switch)
                .tint(NL.accent)
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 14)
    }
}

/// Заголовок страницы - 30pt, как на всех разделах.
struct PageTitle: View {
    let text: String
    init(_ text: String) { self.text = text }

    var body: some View {
        Text(text)
            .font(NLFont.ui(30, .bold))
            .tracking(-0.75)
            .foregroundStyle(NL.textPrimary)
    }
}

/// Заголовок группы над карточкой.
struct SectionHeading: View {
    let text: String
    init(_ text: String) { self.text = text }

    var body: some View {
        Text(text)
            .font(NLFont.ui(15, .bold))
            .foregroundStyle(NL.textPrimary)
    }
}
