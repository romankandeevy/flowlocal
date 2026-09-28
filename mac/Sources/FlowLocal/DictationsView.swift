import AppKit
import SwiftUI

// «Диктовки» - главный экран. Слева лента: сверху пульт записи, поиск,
// под ними диктовки по дням. Справа - выбранная диктовка крупно, для чтения, с
// действиями внизу. Запись не уводит на другой экран: пульт раскрывается
// в живую расшифровку, а готовая диктовка въезжает в ленту первой и сразу
// открывается справа. Пока диктовок нет, справа - первые шаги.
struct DictationsView: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    var body: some View {
        HStack(spacing: 0) {
            FeedColumn(actions: actions)
                .frame(width: 330)
            NL.border.frame(width: 1)
            ReaderPane(actions: actions)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(NL.surface)
        }
    }
}

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

// MARK: - лента

private struct FeedColumn: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions
    @Environment(\.undoManager) private var undo
    @FocusState private var focused: Bool
    /// Опора для ⇧-щелчка и стрелок.
    @State private var anchor: UUID?

    var body: some View {
        let items = filtered
        VStack(spacing: 0) {
            DictationDock(actions: actions)
                .padding([.horizontal, .top], Space.s3)
            if !state.history.isEmpty {
                SearchField(text: $state.historyQuery, focusRequest: state.searchFocusRequest)
                    .padding(.horizontal, Space.s3)
                    .padding(.top, Space.s3)
            }
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 2, pinnedViews: [.sectionHeaders]) {
                        ForEach(HistoryFormat.days(items)) { day in
                            Section {
                                ForEach(day.entries) { entry in
                                    FeedRow(entry: entry,
                                            selected: state.historySelection.contains(entry.id),
                                            playing: state.playing == entry.id) {
                                        click(entry, in: items)
                                    }
                                    .id(entry.id)
                                    .contextMenu {
                                        EntryCommands(state: state, entries: contextEntries(entry),
                                                      actions: actions, undo: undo)
                                    }
                                    .transition(.asymmetric(
                                        insertion: .opacity.combined(with: .offset(y: -8)),
                                        removal: .opacity))
                                }
                            } header: {
                                DayHeader(title: HistoryFormat.sectionTitle(day.date), day: day)
                            }
                        }
                    }
                    .padding(.horizontal, Space.s2)
                    .padding(.bottom, Space.s4)
                    // Анимируем только появление и удаление диктовок. При поиске
                    // список меняется на каждую букву, и анимация сотен строк
                    // заметно тормозит ввод.
                    .motion(Motion.moderate, value: query.isEmpty ? items.map(\.id) : [])
                }
                .focusable()
                .focusEffectDisabled()
                .focused($focused)
                .onMoveCommand { move($0, in: items, proxy: proxy) }
                .onCommand(#selector(NSResponder.selectAll(_:))) {
                    state.historySelection = Set(items.map(\.id))
                }
                .onCopyCommand { providers }
                // ↩ - вставить выбранную диктовку туда, где был курсор; пробел -
                // прослушать, как в Finder. Только когда фокус в ленте.
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
                .overlay { emptyFeed(items) }
            }
        }
        .background(NL.canvas)
        .onAppear {
            focused = true
            if state.historySelection.isEmpty, let first = state.history.first {
                state.historySelection = [first.id]
                anchor = first.id
            }
        }
        // Новая диктовка - первой в ленте и сразу открыта справа.
        .onChange(of: state.history.count) { old, new in
            guard new > old, let first = state.history.first,
                  Date().timeIntervalSince(first.date) < 30 else { return }
            state.historyQuery = ""
            withMotion { state.historySelection = [first.id] }
            anchor = first.id
        }
        // Поиск спрятал выделенную диктовку - она уходит и из выделения.
        .onChange(of: state.historyQuery) { _, _ in
            state.historySelection.formIntersection(Set(filtered.map(\.id)))
        }
    }

    private var query: String { state.historyQuery.trimmingCharacters(in: .whitespaces) }

    /// Выбрана ровно одна диктовка.
    private var single: Entry? {
        let selected = state.entries(state.historySelection)
        return selected.count == 1 ? selected.first : nil
    }

    private var filtered: [Entry] {
        let q = query
        return q.isEmpty ? state.history : state.history.filter { $0.text.localizedCaseInsensitiveContains(q) }
    }

    @ViewBuilder
    private func emptyFeed(_ items: [Entry]) -> some View {
        if state.history.isEmpty {
            Text("Здесь будут ваши диктовки")
                .nlType(.bodySm)
                .foregroundStyle(NL.textTertiary)
        } else if items.isEmpty {
            NLEmptyState(symbol: "magnifyingglass", title: "Ничего не найдено",
                         message: "Нет диктовок со словами «\(query)».") {
                Button("Сбросить поиск") { state.historyQuery = "" }
                    .nlButton(.secondary, .sm)
            }
        }
    }

    /// Правый щелчок по невыделенной строке действует на неё одну.
    private func contextEntries(_ entry: Entry) -> [Entry] {
        state.historySelection.contains(entry.id) ? state.entries(state.historySelection) : [entry]
    }

    private func click(_ entry: Entry, in items: [Entry]) {
        focused = true
        let flags = NSApp.currentEvent?.modifierFlags ?? []
        if flags.contains(.command) {
            if state.historySelection.contains(entry.id) {
                state.historySelection.remove(entry.id)
            } else {
                state.historySelection.insert(entry.id)
            }
            anchor = entry.id
        } else if flags.contains(.shift), let anchor,
                  let a = items.firstIndex(where: { $0.id == anchor }),
                  let b = items.firstIndex(where: { $0.id == entry.id }) {
            state.historySelection = Set(items[min(a, b)...max(a, b)].map(\.id))
        } else {
            state.historySelection = [entry.id]
            anchor = entry.id
        }
    }

    private func move(_ direction: MoveCommandDirection, in items: [Entry], proxy: ScrollViewProxy) {
        guard !items.isEmpty, direction == .up || direction == .down else { return }
        let current = anchor.flatMap { id in items.firstIndex { $0.id == id } }
        let next: Int
        if let current {
            next = direction == .down ? min(items.count - 1, current + 1) : max(0, current - 1)
        } else {
            next = direction == .down ? 0 : items.count - 1
        }
        let id = items[next].id
        state.historySelection = [id]
        anchor = id
        withMotion(Motion.base) { proxy.scrollTo(id) }
    }

    /// ⌘C и «Правка > Скопировать» - текст выделенных диктовок.
    private var providers: [NSItemProvider] {
        let text = state.entries(state.historySelection).filter { !$0.failed }.map(\.text).joined(separator: "\n\n")
        return text.isEmpty ? [] : [NSItemProvider(object: text as NSString)]
    }
}

/// Заголовок дня прилипает к верху ленты: день слева, слова за день справа.
private struct DayHeader: View {
    let title: String
    let day: HistoryDay

    var body: some View {
        HStack {
            Text(title)
                .nlType(.labelSm)
                .foregroundStyle(NL.textSecondary)
            Spacer()
            Text(wordsLabel(day.entries.reduce(0) { $0 + $1.words }))
                .nlType(.caption)
                .monospacedDigit()
                .foregroundStyle(NL.textTertiary)
        }
        .padding(.horizontal, Space.s2)
        .padding(.top, Space.s4)
        .padding(.bottom, Space.s1_5)
        .background(NL.canvas)
    }
}

/// Строка ленты: две строки текста и время. Без рамок и разделителей -
/// строки отделяет воздух, выделение - мягкой подложкой.
private struct FeedRow: View {
    let entry: Entry
    let selected: Bool
    let playing: Bool
    let tap: () -> Void
    @State private var hover = false

    var body: some View {
        VStack(alignment: .leading, spacing: Space.s1) {
            EntryText(entry: entry, lines: 2)
                .nlType(.bodySm)
                .frame(maxWidth: .infinity, alignment: .leading)
            HStack(spacing: Space.s1_5) {
                Text(EntryFormat.meta(entry, showDay: false))
                    .nlType(.caption)
                    .monospacedDigit()
                    .foregroundStyle(NL.textTertiary)
                    .lineLimit(1)
                if playing {
                    Image(systemName: "speaker.wave.2")
                        .font(.system(size: 10))
                        .foregroundStyle(NL.iconAccent)
                        .symbolEffect(.variableColor.iterative, isActive: true)
                }
            }
        }
        .padding(.horizontal, Space.s3)
        .padding(.vertical, Space.s2 + 1)
        .background {
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(selected ? NL.accent.opacity(0.16) : hover ? NL.hover.opacity(0.6) : .clear)
        }
        .contentShape(Rectangle())
        .onTapGesture(perform: tap)
        .onHover { hover = $0 }
        .animation(Motion.fast, value: hover)
        .animation(Motion.fast, value: selected)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(selected ? [.isSelected, .isButton] : .isButton)
    }
}

// MARK: - пульт записи

/// Пульт над лентой. В покое - одна кнопка и сочетание; пока идёт запись -
/// раскрывается: время, волна, живой текст, «Готово» и «Отменить». Высота
/// меняется плавно, содержимое - растворением.
private struct DictationDock: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    private enum Mode: Equatable { case noMic, loading, failed, idle, live }

    private var mode: Mode {
        if state.isBusy { return .live }
        if !state.micGranted { return .noMic }
        switch state.backend {
        case .starting: return .loading
        case .failed: return .failed
        case .ready: return .idle
        }
    }

    var body: some View {
        Group {
            switch mode {
            case .live:
                LivePanel(actions: actions)
                    .transition(.opacity)
            case .idle:
                IdleDock(actions: actions)
                    .transition(.opacity)
            case .loading:
                DockMessage(symbol: nil, title: "Загружаю распознавание",
                            message: "Первый раз после запуска — около 20 секунд.")
                    .transition(.opacity)
            case .noMic:
                DockMessage(symbol: "mic.slash", title: "Нет доступа к микрофону",
                            message: "Без него диктовка не начнётся.") {
                    Button("Разрешить") { openMicrophoneAccess(state) }
                        .nlButton(.secondary, .sm)
                }
                .transition(.opacity)
            case .failed:
                DockMessage(symbol: "exclamationmark.octagon", title: "Распознавание не запустилось",
                            message: failure, tone: NL.textDanger) {
                    Button("Журнал", action: actions.openLog)
                        .nlButton(.secondary, .sm)
                }
                .transition(.opacity)
            }
        }
        .padding(mode == .idle ? Space.s1 : Space.s3)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(mode == .idle ? Color.clear : NL.surface,
                    in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .motion(Motion.slow, value: mode)
    }

    private var failure: String {
        if case let .failed(message) = state.backend { return message }
        return ""
    }
}

private struct IdleDock: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    var body: some View {
        VStack(alignment: .leading, spacing: Space.s2) {
            Button(action: actions.toggleDictation) {
                HStack(spacing: Space.s3) {
                    MicOrb()
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Диктовать")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(NL.textPrimary)
                        HStack(spacing: 4) {
                            Text("или удерживайте")
                            Text(state.hotkey.label)
                                .font(.system(size: 11, weight: .medium, design: .rounded))
                        }
                        .font(.system(size: 11))
                        .foregroundStyle(NL.textTertiary)
                    }
                    Spacer(minLength: 0)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .disabled(!state.canDictate)
            .accessibilityLabel("Диктовать")
            if !state.axTrusted {
                HStack(spacing: Space.s1_5) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.system(size: 10))
                        .foregroundStyle(NL.textWarning)
                    Text("Текст не вставится сам — только в буфер.")
                        .nlType(.caption)
                        .foregroundStyle(NL.textSecondary)
                    Spacer(minLength: Space.s1)
                    Button("Разрешить", action: openAccessibilityAccess)
                        .buttonStyle(NLLinkButtonStyle())
                }
            }
        }
    }
}

/// Круглая кнопка микрофона: акцентный круг с мягким свечением; при
/// наведении чуть подрастает, при нажатии - проседает.
private struct MicOrb: View {
    @State private var hover = false

    var body: some View {
        Image(systemName: "mic.fill")
            .font(.system(size: 15, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: 40, height: 40)
            .background {
                Circle().fill(LinearGradient(colors: [NL.accentHover, NL.accent],
                                             startPoint: .top, endPoint: .bottom))
            }
            .overlay { Circle().strokeBorder(.white.opacity(0.18), lineWidth: 1) }
            .shadow(color: NL.accent.opacity(hover ? 0.55 : 0.3), radius: hover ? 10 : 6, y: 2)
            .scaleEffect(hover ? 1.06 : 1)
            .onHover { hover = $0 }
            .animation(Motion.base, value: hover)
    }
}

private struct DockMessage<Action: View>: View {
    let symbol: String?
    let title: String
    let message: String
    var tone: Color = NL.textPrimary
    @ViewBuilder var action: () -> Action

    var body: some View {
        HStack(alignment: .top, spacing: Space.s2) {
            Group {
                if let symbol {
                    Image(systemName: symbol).font(.system(size: 13)).foregroundStyle(tone)
                } else {
                    ProgressView().controlSize(.mini)
                }
            }
            .frame(width: Size.iconSm, height: 19)
            VStack(alignment: .leading, spacing: Space.s0_5) {
                Text(title)
                    .nlType(.label)
                    .foregroundStyle(tone)
                    .padding(.top, 2)
                Text(message)
                    .nlType(.caption)
                    .foregroundStyle(NL.textSecondary)
                    .lineLimit(3)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: Space.s2)
            action()
        }
    }
}

extension DockMessage where Action == EmptyView {
    init(symbol: String?, title: String, message: String, tone: Color = NL.textPrimary) {
        self.init(symbol: symbol, title: title, message: message, tone: tone) { EmptyView() }
    }
}

/// Раскрытый пульт: время крупно (единственное крупное на экране), волна
/// во всю ширину, живой текст - свежий кусок основным, прежнее вторичным.
private struct LivePanel: View {
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

// MARK: - чтение

private struct ReaderPane: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    var body: some View {
        let selected = state.entries(state.historySelection)
        ZStack {
            if state.history.isEmpty {
                FirstSteps(actions: actions)
                    .transition(.opacity)
            } else if selected.count == 1, let entry = selected.first {
                EntryReader(entry: entry, actions: actions)
                    .id(entry.id)
                    .transition(.asymmetric(insertion: .opacity.combined(with: .offset(y: 4)),
                                            removal: .opacity))
            } else if selected.isEmpty {
                NLEmptyState(symbol: "text.alignleft", title: "Выберите диктовку",
                             message: "Она откроется здесь целиком — с действиями и записью.")
                    .transition(.opacity)
            } else {
                MultiSelection(entries: selected, actions: actions)
                    .transition(.opacity)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .motion(Motion.base, value: state.historySelection)
    }
}

/// Одна диктовка: сведения мелко сверху, текст крупно - как страница, а
/// не как карточка. Действия - полосой внизу, всегда на одном месте.
private struct EntryReader: View {
    @EnvironmentObject var state: AppState
    let entry: Entry
    let actions: AppActions
    @Environment(\.undoManager) private var undo
    @State private var copied = false
    @State private var showRaw = false

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: Space.s4) {
                    HStack(alignment: .firstTextBaseline, spacing: Space.s3) {
                        Text(EntryFormat.headline(entry))
                            .nlType(.caption)
                            .monospacedDigit()
                            .foregroundStyle(NL.textTertiary)
                        Spacer(minLength: 0)
                        if let raw = entry.raw {
                            let removed = max(0, Entry.count(raw) - entry.words)
                            Button(showRaw ? "Показать очищенный" : "Исходный текст · −\(removed)") {
                                withMotion(Motion.base) { showRaw.toggle() }
                            }
                            .buttonStyle(NLLinkButtonStyle())
                            .help("Чистка убрала \(wordsLabel(removed))")
                        }
                    }
                    if entry.failed {
                        let canRetry = AudioStore.exists(entry.audio) && !state.rerecognizing.contains(entry.id)
                        NLAlert(kind: .warning, title: "Речь не распознана",
                                message: AudioStore.exists(entry.audio)
                                    ? "Запись сохранилась — распознайте её заново, при необходимости сменив язык в настройках."
                                    : "Запись не сохранилась, распознать её заново не получится.",
                                actionTitle: canRetry ? "Распознать заново" : nil,
                                action: canRetry ? { actions.rerecognize(entry) } : nil)
                    } else {
                        Text(showRaw ? (entry.raw ?? entry.text) : entry.text)
                            .font(.system(size: 18))
                            .lineSpacing(7)
                            .foregroundStyle(showRaw ? NL.textSecondary : NL.textPrimary)
                            .contentTransition(.opacity)
                            .textSelection(.enabled)
                            .frame(maxWidth: 620, alignment: .leading)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, Space.s8 + Space.s2)
                .padding(.top, Space.s8)
                .padding(.bottom, 88)
            }
        }
        .overlay(alignment: .bottom) {
            actionBar.padding(.bottom, Space.s5)
        }
    }

    /// Действия - плавающей стеклянной панелью значков внизу по центру;
    /// подписи - во всплывающих подсказках.
    private var actionBar: some View {
        HStack(spacing: 2) {
            BarButton(symbol: "arrow.turn.down.left", help: "Вставить туда, где курсор (↩)") {
                actions.paste(entry)
            }
            .disabled(entry.failed)
            BarButton(symbol: copied ? "checkmark" : "doc.on.doc", help: "Скопировать") {
                Clipboard.copy([entry])
                withMotion(Motion.base) { copied = true }
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.4) {
                    withMotion(Motion.base) { copied = false }
                }
            }
            .disabled(entry.failed)
            if AudioStore.exists(entry.audio) {
                Divider().frame(height: 18).padding(.horizontal, 4)
                BarButton(symbol: state.playing == entry.id ? "stop.fill" : "play.fill",
                          help: state.playing == entry.id ? "Остановить" : "Прослушать (пробел)") {
                    actions.play(entry)
                }
                if state.rerecognizing.contains(entry.id) {
                    ProgressView().controlSize(.small).frame(width: 34, height: 34)
                } else {
                    BarButton(symbol: "arrow.clockwise", help: "Распознать заново") {
                        actions.rerecognize(entry)
                    }
                }
            }
            Divider().frame(height: 18).padding(.horizontal, 4)
            BarButton(symbol: "trash", help: "Удалить (⌘Z — вернуть)", tint: NL.textDanger) {
                state.delete([entry.id], undo: undo)
            }
        }
        .padding(5)
        .background(.regularMaterial, in: Capsule(style: .continuous))
        .overlay { Capsule(style: .continuous).strokeBorder(NL.border, lineWidth: 1) }
        .shadow(color: .black.opacity(0.18), radius: 16, y: 6)
    }
}

/// Кнопка-значок плавающей панели: круг подсветки при наведении.
private struct BarButton: View {
    let symbol: String
    let help: String
    var tint: Color = NL.textPrimary
    let action: () -> Void
    @State private var hover = false
    @Environment(\.isEnabled) private var enabled

    var body: some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 14, weight: .medium))
                .foregroundStyle(tint.opacity(enabled ? 1 : 0.35))
                .contentTransition(.symbolEffect(.replace))
                .frame(width: 34, height: 34)
                .background(Circle().fill(hover && enabled ? NL.hover : .clear))
                .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .help(help)
        .accessibilityLabel(help)
        .onHover { hover = $0 }
        .animation(Motion.fast, value: hover)
    }
}

private struct MultiSelection: View {
    @EnvironmentObject var state: AppState
    let entries: [Entry]
    let actions: AppActions
    @Environment(\.undoManager) private var undo

    var body: some View {
        let words = entries.reduce(0) { $0 + $1.words }
        NLEmptyState(symbol: "square.stack",
                     title: "Выбрано \(entries.count) \(plural(entries.count, "диктовка", "диктовки", "диктовок"))",
                     message: "Всего \(wordsLabel(words)). Скопируются одним текстом, через пустую строку.") {
            HStack(spacing: Space.s2) {
                Button("Скопировать все") { Clipboard.copy(entries) }
                    .nlButton(.secondary)
                Button("Удалить") { state.delete(Set(entries.map(\.id)), undo: undo) }
                    .nlButton(.ghost)
            }
        }
    }
}

/// Первые шаги, пока диктовок нет: три условия и проба. Каждый шаг -
/// строка с состоянием справа; выполненный гаснет до третичного.
private struct FirstSteps: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Space.s6) {
                VStack(alignment: .leading, spacing: Space.s1) {
                    Text("Первая диктовка")
                        .nlType(.heading)
                        .foregroundStyle(NL.textPrimary)
                    Text("Три условия — и можно говорить в любом приложении. Звук и текст не покидают этот Mac.")
                        .nlType(.bodySm)
                        .foregroundStyle(NL.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                VStack(spacing: 0) {
                    step(1, "Доступ к микрофону", "Микрофон слушает, только пока идёт запись.", done: state.micGranted) {
                        Button("Разрешить") { openMicrophoneAccess(state) }.nlButton(.secondary, .sm)
                    }
                    step(2, "Универсальный доступ", "Чтобы текст сам вставлялся туда, где курсор.", done: state.axTrusted) {
                        Button("Разрешить", action: openAccessibilityAccess).nlButton(.secondary, .sm)
                    }
                    step(3, "Модели распознавания", "GigaAM для русского, Parakeet для английского.",
                         done: state.backend == .ready, last: true) {
                        StatusLabel(title: "Загрузка…", kind: .busy)
                    }
                }
                .padding(.horizontal, Space.insetMd)
                .nlCard(padding: 0)
                VStack(alignment: .leading, spacing: Space.s2) {
                    Text("Попробуйте")
                        .nlType(.headingXs)
                        .foregroundStyle(NL.textPrimary)
                    HStack(spacing: Space.s2) {
                        Text("Удерживайте")
                        ShortcutValue(preset: state.hotkey)
                        Text("и скажите пару фраз, потом отпустите.")
                    }
                    .nlType(.bodySm)
                    .foregroundStyle(NL.textSecondary)
                }
            }
            .frame(maxWidth: 520, alignment: .leading)
            .padding(Space.s8)
            .frame(maxWidth: .infinity)
        }
        .motion(Motion.moderate, value: [state.micGranted, state.axTrusted, state.backend == .ready])
    }

    private func step<Action: View>(_ n: Int, _ title: String, _ detail: String, done: Bool, last: Bool = false,
                                    @ViewBuilder action: () -> Action) -> some View {
        HStack(alignment: .center, spacing: Space.s3) {
            Text("\(n)")
                .nlType(.labelSm)
                .monospacedDigit()
                .foregroundStyle(NL.textTertiary)
                .frame(width: 12)
            VStack(alignment: .leading, spacing: Space.s0_5) {
                Text(title)
                    .nlType(.label)
                    .foregroundStyle(done ? NL.textTertiary : NL.textPrimary)
                    .strikethrough(done, color: NL.textTertiary)
                Text(detail)
                    .nlType(.caption)
                    .foregroundStyle(NL.textTertiary)
            }
            Spacer(minLength: Space.s3)
            if done {
                StatusLabel(title: "Готово", kind: .ready)
                    .transition(.opacity)
            } else {
                action()
            }
        }
        .padding(.vertical, Space.s3)
        .frame(minHeight: Size.rowHeight + 8)
        .overlay(alignment: .bottom) {
            if !last { NL.borderSubtle.frame(height: 1) }
        }
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
