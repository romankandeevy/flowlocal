import AppKit
import SwiftUI

// Диктовка в окне: строка диктовки (Главная и История), живая запись,
// доступы и форматы дат.

/// Нет доступа: спросить, если macOS ещё не спрашивала, иначе - открыть настройки.
func openMicrophoneAccess(_ state: AppState) {
    if Recorder.permission == .notDetermined {
        Recorder.requestPermission { _ in state.refreshPermissions() }
    } else if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone") {
        NSWorkspace.shared.open(url)
    }
}

func openAccessibilityAccess() {
    Inserter.requestTrust()
    Inserter.openAccessibilitySettings()
}

// MARK: - строка диктовки

/// Диктовки одной карточкой: строки через тонкий разделитель. Новые
/// въезжают сверху, удалённые растворяются.
struct EntryList: View {
    let entries: [Entry]
    let actions: AppActions
    var showDay = false

    var body: some View {
        VStack(spacing: 0) {
            ForEach(Array(entries.enumerated()), id: \.element.id) { index, entry in
                EntryRow(entry: entry, actions: actions, showDay: showDay)
                    .id(entry.id)
                    .overlay(alignment: .top) {
                        if index > 0 { NL.borderSubtle.frame(height: 1) }
                    }
                    .transition(.asymmetric(insertion: .opacity.combined(with: .offset(y: -8)),
                                            removal: .opacity))
            }
        }
        .nlCard(padding: 0)
    }
}

/// Строка диктовки: время, две строки текста и сведения. Щелчок копирует -
/// на месте подсказки проступает «Скопировано»; нераспознанная по щелчку
/// распознаётся заново. «⋯» и правый щелчок - остальные действия.
struct EntryRow: View {
    @EnvironmentObject var state: AppState
    let entry: Entry
    let actions: AppActions
    var showDay = false
    @Environment(\.undoManager) private var undo
    @State private var hover = false
    @State private var copied = false
    @State private var reset: DispatchWorkItem?

    var body: some View {
        HStack(alignment: .top, spacing: Space.s4) {
            Text(HistoryFormat.time.string(from: entry.date))
                .font(NLFont.ui(13))
                .monospacedDigit()
                .foregroundStyle(NL.textQuaternary)
                .frame(width: 40, alignment: .leading)
                .padding(.top, 2)
            VStack(alignment: .leading, spacing: 4) {
                Group {
                    if entry.failed {
                        Text("Речь не распознана")
                            .foregroundStyle(NL.textTertiary)
                    } else {
                        Text(entry.text)
                            .foregroundStyle(NL.textPrimary)
                            .lineLimit(2)
                    }
                }
                .font(NLFont.ui(14.5))
                .lineSpacing(4)
                .frame(maxWidth: .infinity, alignment: .leading)
                HStack(spacing: 6) {
                    Text(meta)
                        .font(NLFont.ui(12))
                        .monospacedDigit()
                        .foregroundStyle(entry.failed ? NL.textDanger : NL.textQuaternary)
                        .lineLimit(1)
                    if state.playing == entry.id {
                        Image(systemName: "speaker.wave.2")
                            .font(.system(size: 10))
                            .foregroundStyle(NL.iconAccent)
                            .symbolEffect(.variableColor.iterative, isActive: true)
                    }
                }
            }
            trailing
                .frame(width: 150, alignment: .trailing)
        }
        .padding(.vertical, 14)
        .padding(.leading, 18)
        .padding(.trailing, 10)
        .background(selected ? NL.selected : hover ? NL.rowHover : .clear)
        .contentShape(Rectangle())
        .onTapGesture(perform: primary)
        .onHover { hover = $0 }
        .animation(Motion.fast, value: hover)
        .contextMenu {
            EntryCommands(state: state, entries: [entry], actions: actions, undo: undo)
        }
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
        .accessibilityHint(entry.failed ? "Распознать заново" : "Скопировать")
    }

    private var selected: Bool { state.historySelection == [entry.id] }

    private var meta: String {
        if entry.failed { return "Не распознано · " + MainView.clock(entry.seconds) }
        var parts = [wordsLabel(entry.words), MainView.clock(entry.seconds)]
        if showDay { parts.insert(HistoryFormat.sectionTitle(Calendar.current.startOfDay(for: entry.date)), at: 0) }
        if entry.lang.lowercased() == "en" { parts.append("English") }
        if let app = entry.appName { parts.append(app) }
        return parts.joined(separator: " · ")
    }

    private var canRetry: Bool { AudioStore.exists(entry.audio) }

    @ViewBuilder
    private var trailing: some View {
        HStack(spacing: 2) {
            ZStack(alignment: .trailing) {
                if state.rerecognizing.contains(entry.id) {
                    ProgressView().controlSize(.small)
                        .transition(.opacity)
                } else if copied {
                    HStack(spacing: 5) {
                        Image(systemName: "checkmark")
                            .font(.system(size: 10, weight: .bold))
                        Text("Скопировано")
                    }
                    .font(NLFont.ui(12, .semibold))
                    .foregroundStyle(NL.textOnAccent)
                    .padding(.horizontal, 9)
                    .frame(height: 22)
                    .background(NL.accent, in: Capsule())
                    .transition(.scale(scale: 0.85).combined(with: .opacity))
                } else if entry.failed {
                    if canRetry {
                        Text("Распознать заново")
                            .font(NLFont.ui(12, .semibold))
                            .foregroundStyle(NL.textDanger)
                            .transition(.opacity)
                    }
                } else {
                    Text("Скопировать")
                        .font(NLFont.ui(12, .medium))
                        .foregroundStyle(NL.textTertiary)
                        .opacity(hover ? 1 : 0)
                        .offset(x: hover ? 0 : 4)
                        .transition(.opacity)
                }
            }
            .frame(height: 24)
            Menu {
                EntryCommands(state: state, entries: [entry], actions: actions, undo: undo)
            } label: {
                Image(systemName: "ellipsis")
                    .font(.system(size: 13, weight: .medium))
            }
            .menuStyle(.borderlessButton)
            .menuIndicator(.hidden)
            .fixedSize()
            .frame(width: 30, height: 24)
            .opacity(hover ? 1 : 0)
            .help("Действия")
            .accessibilityLabel("Действия")
        }
        .animation(Motion.pop, value: copied)
    }

    private func primary() {
        state.historySelection = [entry.id]
        if entry.failed {
            if canRetry && !state.rerecognizing.contains(entry.id) { actions.rerecognize(entry) }
            return
        }
        Clipboard.copy([entry])
        reset?.cancel()
        copied = true
        let work = DispatchWorkItem { copied = false }
        reset = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5, execute: work)
    }
}

/// Клавиатура в списке диктовок: ↑↓ - выбор, ↩ - вставить, пробел -
/// прослушать, ⌘C - скопировать, ⌫ - удалить (⌘Z вернёт).
struct EntryKeys: ViewModifier {
    @EnvironmentObject var state: AppState
    let items: [Entry]
    let actions: AppActions
    @Environment(\.undoManager) private var undo
    @FocusState private var focused: Bool

    func body(content: Content) -> some View {
        ScrollViewReader { proxy in
            content
                .focusable()
                .focusEffectDisabled()
                .focused($focused)
                .onMoveCommand { move($0, proxy: proxy) }
                .onCopyCommand {
                    let text = state.entries(state.historySelection).filter { !$0.failed }
                        .map(\.text).joined(separator: "\n\n")
                    return text.isEmpty ? [] : [NSItemProvider(object: text as NSString)]
                }
                .onKeyPress(.return) {
                    guard let entry = single, !entry.failed else { return .ignored }
                    actions.paste(entry)
                    return .handled
                }
                .onKeyPress(.space) {
                    guard let entry = single, AudioStore.exists(entry.audio) else { return .ignored }
                    actions.play(entry)
                    return .handled
                }
                .onDeleteCommand { state.delete(state.historySelection, undo: undo) }
                .onTapGesture { focused = true }
        }
    }

    private var single: Entry? {
        let selected = state.entries(state.historySelection)
        return selected.count == 1 ? selected.first : nil
    }

    private func move(_ direction: MoveCommandDirection, proxy: ScrollViewProxy) {
        guard !items.isEmpty, direction == .up || direction == .down else { return }
        let current = state.historySelection.count == 1
            ? items.firstIndex { state.historySelection.contains($0.id) } : nil
        let next: Int
        if let current {
            next = direction == .down ? min(items.count - 1, current + 1) : max(0, current - 1)
        } else {
            next = direction == .down ? 0 : items.count - 1
        }
        let id = items[next].id
        withMotion(Motion.fast) { state.historySelection = [id] }
        withMotion(Motion.base) { proxy.scrollTo(id) }
    }
}

extension View {
    func entryKeys(_ items: [Entry], actions: AppActions) -> some View {
        modifier(EntryKeys(items: items, actions: actions))
    }
}

/// Сочетание клавиш - отдельными клавишами: ⌃ ⇧ Space.
struct KeyCaps: View {
    let preset: HotkeyPreset
    var size: CGFloat = 12.5

    var body: some View {
        HStack(spacing: size > 13 ? 6 : 3) {
            ForEach(Array(preset.keys.enumerated()), id: \.offset) { _, key in
                Text(KeyGlyph.short(key))
                    .font(NLFont.ui(size, .semibold))
                    .foregroundStyle(NL.textPrimary)
                    .padding(.horizontal, size > 13 ? 10 : 6)
                    .frame(minWidth: size > 13 ? 34 : 22, minHeight: size > 13 ? 34 : 22)
                    .background(NL.surface, in: RoundedRectangle(cornerRadius: size > 13 ? 8 : 6, style: .continuous))
                    .overlay {
                        RoundedRectangle(cornerRadius: size > 13 ? 8 : 6, style: .continuous)
                            .strokeBorder(NL.borderStrong, lineWidth: 0.5)
                    }
                    .shadow(color: .black.opacity(0.08), radius: 0, y: 1)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(preset.keys.map(KeyGlyph.word).joined(separator: " "))
    }
}
// MARK: - живая запись

/// Раскрытый пульт: время крупно (единственное крупное на экране), волна
/// во всю ширину, живой текст - свежий кусок основным, прежнее вторичным.
struct LivePanel: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    var body: some View {
        VStack(alignment: .leading, spacing: Space.s3) {
            header
            if state.isRecording {
                GeometryReader { geo in
                    LiveWaveform(count: max(8, Int(geo.size.width / 6)), barWidth: 3, spacing: 3, height: 32)
                        .frame(width: geo.size.width, alignment: .leading)
                }
                .frame(height: 32)
                .transition(.opacity)
            } else {
                IndeterminateBar()
                    .frame(height: 3)
                    .padding(.vertical, 14)
                    .transition(.opacity)
            }
            LiveText()
            HStack(spacing: Space.s2) {
                if state.isRecording {
                    Button(action: actions.toggleDictation) {
                        Label("Готово", systemImage: "checkmark")
                    }
                    .nlButton(.primary, .sm)
                }
                Button("Отменить", action: actions.cancelDictation)
                    .keyboardShortcut(.cancelAction)
                    .nlButton(.ghost, .sm)
                Spacer(minLength: 0)
                Text(hint)
                    .nlType(.caption)
                    .foregroundStyle(NL.textTertiary)
                    .lineLimit(1)
            }
        }
        .motion(Motion.moderate, value: state.isRecording)
    }

    @ViewBuilder
    private var header: some View {
        if case let .recording(since, _) = state.phase {
            TimelineView(.periodic(from: since, by: 0.5)) { context in
                let t = context.date.timeIntervalSince(since)
                HStack(alignment: .center, spacing: Space.s2) {
                    RecordingDot()
                    Text(MainView.clock(t))
                        .nlType(.headingLg)
                        .monospacedDigit()
                        .foregroundStyle(NL.textPrimary)
                        .contentTransition(.numericText())
                    Spacer(minLength: 0)
                    LiveWordCount()
                        .nlType(.caption)
                        .monospacedDigit()
                        .foregroundStyle(NL.textTertiary)
                        .contentTransition(.numericText())
                }
                .animation(Motion.base, value: Int(t))
            }
        } else {
            HStack(alignment: .firstTextBaseline, spacing: Space.s2) {
                Text("Распознаю")
                    .nlType(.headingLg)
                    .foregroundStyle(NL.textPrimary)
                Spacer(minLength: 0)
                LiveWordCount(prefix: "\(MainView.clock(state.recordSeconds)) · ")
                    .nlType(.caption)
                    .monospacedDigit()
                    .foregroundStyle(NL.textTertiary)
            }
        }
    }

    private var hint: String {
        switch state.phase {
        case .recording(_, true): return "или \(state.toggleHotkey.label) ещё раз"
        case .recording: return "отпустите \(state.hotkey.label)"
        default: return state.insertAutomatically ? "текст вставится в активное окно" : "текст останется в ленте"
        }
    }
}

/// Красная точка записи мягко «дышит» прозрачностью; при «Уменьшить
/// движение» - просто горит.
private struct RecordingDot: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var dim = false

    var body: some View {
        Circle()
            .fill(NL.danger)
            .frame(width: 10, height: 10)
            .opacity(dim ? 0.35 : 1)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) { dim = true }
            }
            .accessibilityLabel("Идёт запись")
    }
}

/// Неопределённый прогресс Northline: отрезок 40% ширины бежит слева
/// направо за 1,4 с. При «Уменьшить движение» - стоит на месте.
struct IndeterminateBar: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var run = false

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(NL.subtle)
                Capsule()
                    .fill(NL.accent)
                    .frame(width: geo.size.width * 0.4)
                    .offset(x: run ? geo.size.width : -geo.size.width * 0.4)
            }
            .clipShape(Capsule())
        }
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 1.4).repeatForever(autoreverses: false)) { run = true }
        }
        .accessibilityLabel("Распознавание")
    }
}

/// Счёт слов живой диктовки. Своим видом: меняется с каждым куском разбора и
/// перерисовывает только себя.
private struct LiveWordCount: View {
    @ObservedObject private var live = LiveWords.shared
    var prefix = ""

    var body: some View {
        Text(prefix + wordsLabel(live.count))
    }
}

/// Живая расшифровка в пульте - по словам (LiveWords).
private struct LiveText: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        LiveWordsFlow(placeholder: state.isRecording ? "Говорите — слова появятся здесь." : "Ещё мгновение…")
    }
}

// MARK: - даты

struct HistoryDay: Identifiable {
    let date: Date
    let entries: [Entry]
    var id: Date { date }
}

/// Даты для истории: время, день, заголовки групп.
enum HistoryFormat {
    static let time: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "HH:mm"
        return f
    }()

    static let day: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ru_RU")
        f.dateFormat = "d MMMM"
        return f
    }()

    static let dayYear: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ru_RU")
        f.dateFormat = "d MMMM yyyy"
        return f
    }()

    static func sectionTitle(_ day: Date) -> String {
        let cal = Calendar.current
        if cal.isDateInToday(day) { return "Сегодня" }
        if cal.isDateInYesterday(day) { return "Вчера" }
        if cal.isDate(day, equalTo: Date(), toGranularity: .year) { return Self.day.string(from: day) }
        return dayYear.string(from: day)
    }

    /// Подряд идущие диктовки одного дня; история уже от новых к старым.
    static func days(_ items: [Entry]) -> [HistoryDay] {
        let cal = Calendar.current
        var out: [HistoryDay] = []
        var i = 0
        while i < items.count {
            let day = cal.startOfDay(for: items[i].date)
            var j = i
            while j < items.count && cal.isDate(items[j].date, inSameDayAs: day) { j += 1 }
            out.append(HistoryDay(date: day, entries: Array(items[i..<j])))
            i = j
        }
        return out
    }
}

enum EntryFormat {
    /// «14:32 · 12 слов · 0:05» - вне «Истории» ещё и день.
    static func meta(_ entry: Entry, showDay: Bool) -> String {
        var when = HistoryFormat.time.string(from: entry.date)
        if showDay && !Calendar.current.isDateInToday(entry.date) {
            when = "\(HistoryFormat.sectionTitle(entry.date)), \(when)"
        }
        // Нераспознанная: «0 слов» ничего не говорит - строка и так помечена.
        if entry.failed { return [when, MainView.clock(entry.seconds)].joined(separator: " · ") }
        var parts = [when, wordsLabel(entry.words), MainView.clock(entry.seconds)]
        if entry.lang.lowercased() == "en" { parts.append("English") }
        return parts.joined(separator: " · ")
    }

    /// Шапка диктовки в чтении: «Сегодня, 14:32 · 0:05 · 12 слов · Русский».
    static func headline(_ entry: Entry) -> String {
        let day = HistoryFormat.sectionTitle(Calendar.current.startOfDay(for: entry.date))
        let time = HistoryFormat.time.string(from: entry.date)
        if entry.failed { return ["\(day), \(time)", MainView.clock(entry.seconds)].joined(separator: " · ") }
        return ["\(day), \(time)", MainView.clock(entry.seconds), wordsLabel(entry.words), language(entry.lang)]
            .joined(separator: " · ")
    }

    static func language(_ code: String) -> String {
        switch code.lowercased() {
        case "ru": return "Русский"
        case "en": return "English"
        default: return "—"
        }
    }
}
