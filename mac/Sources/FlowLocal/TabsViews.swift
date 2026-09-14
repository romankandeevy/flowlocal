import AppKit
import SwiftUI

// «История», «Статистика», «Настройки» - из тех же примитивов, что и
// «Главная»: карточки elevated/1 на чёрном, группы с заголовком над ними.

// MARK: - История

/// Список по дням: заголовок дня и карточка его диктовок. Строки ленивые -
/// карточка собрана из скруглённых первой и последней строк, а не обёрткой,
/// иначе день на сотню диктовок строился бы целиком.
struct HistoryView: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    var body: some View {
        let items = filtered
        Group {
            if state.history.isEmpty {
                EmptyState(symbol: "clock", title: "Диктовок ещё нет",
                           text: "Зажмите \(state.hotkey.label) и скажите первую фразу — она появится здесь.")
            } else if items.isEmpty {
                EmptyState(symbol: "magnifyingglass", title: "Ничего не найдено",
                           text: "Нет диктовок со словами «\(query)».")
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        ForEach(Self.rows(items)) { row in
                            rowView(row)
                        }
                    }
                    .frame(maxWidth: 820, alignment: .leading)
                    .padding(.horizontal, Space.s5)
                    .padding(.top, Space.s1)
                    .padding(.bottom, Space.s6)
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .animation(Motion.page, value: items.map(\.id))
        // Ушли со вкладки - поиск сбрасывается, как в Finder: вернулись к полному списку.
        .onDisappear { state.historyQuery = "" }
    }

    private var query: String { state.historyQuery.trimmingCharacters(in: .whitespaces) }

    private var filtered: [Entry] {
        let q = query
        return q.isEmpty ? state.history : state.history.filter { $0.text.localizedCaseInsensitiveContains(q) }
    }

    @ViewBuilder
    private func rowView(_ row: HistoryListRow) -> some View {
        switch row.kind {
        case let .header(day, first):
            SectionTitle(HistoryFormat.sectionTitle(day))
                .padding(.top, first ? 0 : Space.s5)
                .padding(.bottom, Space.s2)
        case let .entry(entry, first, last):
            let r = Radius.card
            let shape = UnevenRoundedRectangle(topLeadingRadius: first ? r : 0, bottomLeadingRadius: last ? r : 0,
                                               bottomTrailingRadius: last ? r : 0, topTrailingRadius: first ? r : 0,
                                               style: .continuous)
            HistoryRow(entry: entry, actions: actions, divider: !first)
                .background(shape.fill(state.palette.surface))
                .clipShape(shape)
        }
    }

    static func rows(_ items: [Entry]) -> [HistoryListRow] {
        let cal = Calendar.current
        var out: [HistoryListRow] = []
        var i = 0
        while i < items.count {
            let day = cal.startOfDay(for: items[i].date)
            var j = i
            while j < items.count && cal.isDate(items[j].date, inSameDayAs: day) { j += 1 }
            out.append(HistoryListRow(id: "day-\(Int(day.timeIntervalSince1970))", kind: .header(day, first: out.isEmpty)))
            for k in i..<j {
                out.append(HistoryListRow(id: items[k].id.uuidString,
                                          kind: .entry(items[k], first: k == i, last: k == j - 1)))
            }
            i = j
        }
        return out
    }
}

struct HistoryListRow: Identifiable {
    enum Kind {
        case header(Date, first: Bool)
        case entry(Entry, first: Bool, last: Bool)
    }

    let id: String
    let kind: Kind
}

/// Строка диктовки: время и сведения, текст в три строки. Действия - глифы
/// справа, видны при наведении и в раскрытой строке: в покое список чистый.
struct HistoryRow: View {
    @EnvironmentObject var state: AppState
    let entry: Entry
    let actions: AppActions
    var divider = false
    var showDay = false          // вне «Истории» дня-заголовка нет - день в строке
    @State private var open = false
    @State private var hover = false
    @State private var copied = false

    var body: some View {
        let p = state.palette
        let long = entry.words > 50
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: Space.s2) {
                Text(meta).textStyle(.subheadline, p.textMuted).monospacedDigit().lineLimit(1)
                if entry.lang.lowercased() == "en" { FLTag(text: "English") }
                if entry.failed { FLTag(text: "Не распознано", tone: .warning) }
                Spacer(minLength: Space.s2)
                rowActions
                    .opacity(hover || open ? 1 : 0)
                    .allowsHitTesting(hover || open)
            }
            if entry.failed {
                Text("Речь не распознана. Запись сохранена — перераспознайте её, например другим языком.")
                    .textStyle(.body, p.textMuted)
            } else if open || !long {
                // Выделяемый текст на macOS игнорирует lineLimit - поэтому
                // выделение только у показанного целиком.
                Text(entry.text)
                    .textStyle(.body, p.text)
                    .lineSpacing(4)
                    .textSelection(.enabled)
                    .frame(maxWidth: 720, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                Text(entry.text)
                    .textStyle(.body, p.text)
                    .lineSpacing(4)
                    .lineLimit(3)
                    .frame(maxWidth: 720, alignment: .leading)
            }
            if long && !entry.failed {
                Button { withAnimation(Motion.page) { open.toggle() } } label: {
                    Label(open ? "Свернуть" : "Показать полностью", systemImage: open ? "chevron.up" : "chevron.down")
                }
                .buttonStyle(FLButtonStyle(kind: .plain, size: .small))
                // Подпись кнопки - на одной линии с текстом записи.
                .padding(.leading, -10)
            }
        }
        .padding(.horizontal, Space.s4)
        .padding(.vertical, Space.s3)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(hover ? p.fill4.opacity(0.5) : Color.clear)
        .overlay(alignment: .top) { if divider { FLSeparator(inset: Space.s4) } }
        .onHover { hover = $0 }
        .animation(Motion.hover, value: hover)
    }

    private var meta: String {
        var when = HistoryFormat.time.string(from: entry.date)
        if showDay && !Calendar.current.isDateInToday(entry.date) {
            when = "\(HistoryFormat.sectionTitle(entry.date)), \(when)"
        }
        return "\(when) · \(wordsLabel(entry.words)) · \(MainView.clock(entry.seconds))"
    }

    private var rowActions: some View {
        HStack(spacing: 2) {
            FLIconButton(symbol: copied ? "checkmark" : "doc.on.doc", help: copied ? "Скопировано" : "Копировать") {
                NSPasteboard.general.clearContents()
                NSPasteboard.general.setString(entry.text, forType: .string)
                withAnimation(Motion.press) { copied = true }
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) { copied = false }
            }
            .disabled(entry.failed)
            FLIconButton(symbol: "arrow.turn.down.left", help: "Вставить в активное окно") { actions.paste(entry) }
                .disabled(entry.failed)
            if AudioStore.exists(entry.audio) {
                let playing = state.playing == entry.id
                FLIconButton(symbol: playing ? "stop.fill" : "play.fill", help: playing ? "Остановить" : "Прослушать") {
                    actions.play(entry)
                }
                if state.rerecognizing.contains(entry.id) {
                    ProgressView().controlSize(.mini).frame(width: 26, height: 24)
                } else {
                    FLIconButton(symbol: "arrow.triangle.2.circlepath", help: "Перераспознать") {
                        actions.rerecognize(entry)
                    }
                }
            }
            FLIconButton(symbol: "trash", help: "Удалить", destructive: true) {
                withAnimation(Motion.page) { state.remove(entry) }
            }
        }
    }
}

// MARK: - Статистика

struct StatsView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        let p = state.palette
        PageScroll(maxWidth: 820) {
            Text("Считается по истории на этом Mac. Печать для сравнения — \(Int(AppState.typingWPM)) слов в минуту.")
                .textStyle(.body, p.textMuted)
                .fixedSize(horizontal: false, vertical: true)
            TodayCard()
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 170), spacing: Space.s2)], spacing: Space.s2) {
                StatTile(symbol: "speedometer", label: "Скорость речи", value: "\(state.speedWPM)", unit: "сл/мин")
                StatTile(symbol: "hourglass", label: "Сэкономлено", value: "\(state.savedMinutes)", unit: "мин")
                StatTile(symbol: "keyboard", label: "Голос против клавиатуры", value: ratio)
                StatTile(symbol: "calendar", label: "Слов за неделю", value: grouped(state.wordsWeek))
            }
        }
    }

    private var ratio: String {
        guard state.speedWPM > 0 else { return "—" }
        return String(format: "%.1f×", state.voiceRatio).replacingOccurrences(of: ".", with: ",")
    }
}

/// Главная карточка статистики: слов сегодня крупно и неделя столбиками.
struct TodayCard: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .bottom, spacing: Space.s6) {
                summary
                WeekChart().frame(minWidth: 320)
            }
            VStack(alignment: .leading, spacing: Space.s5) {
                summary
                WeekChart()
            }
        }
        .padding(Space.s5)
        .card()
    }

    private var summary: some View {
        let p = state.palette
        let n = state.dictationsToday
        return VStack(alignment: .leading, spacing: 6) {
            Text("Слов сегодня").textStyle(.subheadline, p.textMuted)
            Text(grouped(state.wordsToday))
                .font(.system(size: 44, weight: .light))
                .monospacedDigit()
                .foregroundStyle(p.text)
                .contentTransition(.numericText())
            Text("\(n) \(plural(n, "диктовка", "диктовки", "диктовок")) · за 7 дней \(grouped(state.wordsWeek))")
                .textStyle(.subheadline, p.textMuted)
        }
        .fixedSize()
    }
}

/// Столбики по дням. Сегодня - systemBlue, остальные - fill/1: один акцент.
struct WeekChart: View {
    @EnvironmentObject var state: AppState
    var height: CGFloat = 120

    var body: some View {
        let p = state.palette
        let days = state.lastDays
        let top = max(1, days.map(\.words).max() ?? 1)
        HStack(alignment: .bottom, spacing: Space.s2) {
            ForEach(days.indices, id: \.self) { i in
                let today = i == days.count - 1
                let words = days[i].words
                VStack(spacing: 6) {
                    Text(words > 0 ? grouped(words) : " ")
                        .textStyle(.subheadline, today ? p.text : p.textMuted)
                        .monospacedDigit()
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                    UnevenRoundedRectangle(topLeadingRadius: Radius.menu, bottomLeadingRadius: 2,
                                           bottomTrailingRadius: 2, topTrailingRadius: Radius.menu, style: .continuous)
                        .fill(today ? p.accent : p.surface3)
                        .frame(height: max(4, height * CGFloat(words) / CGFloat(top)))
                    Text(HistoryFormat.weekday.string(from: days[i].date))
                        .textStyle(.subheadline, today ? p.text : p.textMuted, weight: today ? .semibold : .regular)
                }
                .frame(maxWidth: .infinity)
            }
        }
        .frame(height: height + 44, alignment: .bottom)
    }
}

// MARK: - Настройки

// Как System Settings: группы с заголовком над карточкой, строки 44 pt с
// разделителем от текста, контрол справа; колонка 640 по центру сцены.
struct SettingsView: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions
    @State private var recordings = (count: 0, bytes: Int64(0))

    var body: some View {
        let p = state.palette
        ScrollView {
            VStack(alignment: .leading, spacing: Space.s5) {
                SettingsSection("Сочетания клавиш", footer: "Работают в любом приложении. Esc во время записи — отмена.") {
                    HotkeyRow(role: .hold, actions: actions)
                    FLSeparator(inset: Metric.rowTextInset)
                    HotkeyRow(role: .toggle, actions: actions)
                }
                SettingsSection("Диктовка") {
                    SettingRow(symbol: "arrow.turn.down.left", title: "Вставлять текст сразу",
                               subtitle: "Иначе текст остаётся только в истории") {
                        FLSwitch(isOn: $state.insertAutomatically)
                    }
                    FLSeparator(inset: Metric.rowTextInset)
                    SettingRow(symbol: "globe", title: "Язык", subtitle: "Авто — русский и английский по кускам речи") {
                        FLSegmented(options: LangMode.allCases.map { ($0, $0.title) }, selection: $state.langMode)
                    }
                    FLSeparator(inset: Metric.rowTextInset)
                    SettingRow(symbol: "capsule", title: "Островок во время записи",
                               subtitle: "Уровень и время записи у нижнего края экрана") {
                        FLSwitch(isOn: $state.showPill)
                    }
                    FLSeparator(inset: Metric.rowTextInset)
                    SettingRow(symbol: "speaker.wave.2", title: "Звук начала и конца",
                               subtitle: "Короткий щелчок, когда запись началась и закончилась") {
                        FLSwitch(isOn: $state.sounds)
                    }
                }
                SettingsSection("Микрофон", footer: "Микрофон слушает только пока идёт запись.") {
                    SettingRow(symbol: "mic", title: "Устройство", subtitle: state.micName) {
                        // По ширине названия: имя микрофона не обрезается.
                        FLPopup(options: micOptions(state), selection: $state.micUID)
                            .fixedSize()
                    }
                }
                SettingsSection("Записи", footer: "Аудио каждой диктовки хранится, чтобы её можно было прослушать и перераспознать.") {
                    SettingRow(symbol: "waveform", title: "Сохранять аудио", subtitle: "WAV 16 кГц, около 2 МБ на минуту") {
                        FLSwitch(isOn: $state.saveAudio)
                    }
                    FLSeparator(inset: Metric.rowTextInset)
                    SettingRow(symbol: "folder", title: "Папка записей",
                               subtitle: "\(recordings.count) \(plural(recordings.count, "файл", "файла", "файлов")) · \(megabytes)") {
                        Button(action: actions.openRecordings) { Label("Открыть", systemImage: "arrow.up.forward.app") }
                            .buttonStyle(FLButtonStyle(kind: .secondary, size: .small))
                    }
                }
                SettingsSection("Разрешения", footer: "macOS спрашивает их один раз. Без микрофона диктовка выключена, без универсального доступа текст ложится в буфер.") {
                    SettingRow(symbol: "hand.raised", title: "Микрофон",
                               subtitle: state.micGranted ? "Доступ выдан" : "Не выдан — диктовка выключена") {
                        permission(state.micGranted) { openMicrophoneAccess(state) }
                    }
                    FLSeparator(inset: Metric.rowTextInset)
                    SettingRow(symbol: "accessibility", title: "Универсальный доступ",
                               subtitle: state.axTrusted ? "Выдан — вставка в любое окно" : "Не выдан — вставлять ⌘V вручную") {
                        permission(state.axTrusted) {
                            Inserter.requestTrust()
                            Inserter.openAccessibilitySettings()
                        }
                    }
                }
                SettingsSection("Система") {
                    SettingRow(symbol: "power", title: "Запускать при входе в систему",
                               subtitle: "Flow Local стартует вместе с macOS") {
                        FLSwitch(isOn: Binding(get: { state.launchAtLogin }, set: { actions.setLaunchAtLogin($0) }))
                    }
                }
                SettingsSection("Распознавание", footer: "Модели работают на процессоре этого Mac — без сети и аккаунта.") {
                    SettingRow(symbol: "textformat", title: "Русский", subtitle: "GigaAM v3 e2e · int8") {
                        model(state.backend == .ready)
                    }
                    FLSeparator(inset: Metric.rowTextInset)
                    SettingRow(symbol: "textformat.abc", title: "Английский", subtitle: "Parakeet TDT 0.6b v2 · int8") {
                        model(state.englishReady)
                    }
                    FLSeparator(inset: Metric.rowTextInset)
                    SettingRow(symbol: "doc.text", title: "Журнал", subtitle: "~/Library/Logs/FlowLocal.log") {
                        Button(action: actions.openLog) { Label("Открыть", systemImage: "arrow.up.forward.app") }
                            .buttonStyle(FLButtonStyle(kind: .secondary, size: .small))
                    }
                }
                Text("Flow Local \(AppInfo.version)")
                    .textStyle(.subheadline, p.textMuted)
                    .frame(maxWidth: .infinity)
            }
            .frame(maxWidth: 640)
            .padding(.horizontal, Space.s5)
            .padding(.top, Space.s1)
            .padding(.bottom, Space.s6)
            .frame(maxWidth: .infinity)
        }
        .onAppear(perform: countRecordings)
    }

    private var megabytes: String {
        String(format: "%.1f МБ", Double(recordings.bytes) / 1_048_576).replacingOccurrences(of: ".", with: ",")
    }

    private func countRecordings() {
        let files = (try? FileManager.default.contentsOfDirectory(at: AudioStore.dir,
                                                                 includingPropertiesForKeys: [.fileSizeKey])) ?? []
        let bytes = files.reduce(Int64(0)) { sum, url in
            sum + Int64((try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0)
        }
        recordings = (files.count, bytes)
    }

    @ViewBuilder
    private func permission(_ ok: Bool, open: @escaping () -> Void) -> some View {
        if ok {
            FLTag(text: "Выдан", tone: .success, symbol: "checkmark")
        } else {
            HStack(spacing: Space.s2) {
                FLTag(text: "Нет", tone: .danger)
                Button("Открыть", action: open)
                    .buttonStyle(FLButtonStyle(kind: .secondary, size: .small))
            }
        }
    }

    private func model(_ ready: Bool) -> some View {
        FLTag(text: ready ? "Готов" : "Загрузка", tone: ready ? .success : .warning, dot: true)
    }
}

/// Группа настроек: заголовок, карточка строк, пояснение под ней.
struct SettingsSection<Rows: View>: View {
    let title: String
    let footer: String?
    let rows: () -> Rows

    init(_ title: String, footer: String? = nil, @ViewBuilder rows: @escaping () -> Rows) {
        self.title = title
        self.footer = footer
        self.rows = rows
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Space.s2) {
            SectionTitle(title)
            VStack(spacing: 0) { rows() }
                .card()
            if let footer {
                Text(footer)
                    .textStyle(.subheadline, Palette.dark.textMuted)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

/// Строка настроек: глиф в плашке, заголовок body, пояснение subheadline,
/// контрол справа. Разделитель между строками начинается от текста.
struct SettingRow<Control: View>: View {
    let symbol: String?
    let title: String
    let subtitle: String?
    let control: () -> Control

    init(symbol: String? = nil, title: String, subtitle: String? = nil,
         @ViewBuilder control: @escaping () -> Control) {
        self.symbol = symbol
        self.title = title
        self.subtitle = subtitle
        self.control = control
    }

    var body: some View {
        let p = Palette.dark
        HStack(spacing: Space.s3) {
            if let symbol { SettingIcon(symbol: symbol) }
            VStack(alignment: .leading, spacing: 2) {
                Text(title).textStyle(.body, p.text)
                if let subtitle {
                    Text(subtitle)
                        .textStyle(.subheadline, p.textMuted)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: Space.s4)
            control()
        }
        .padding(.horizontal, Space.s4)
        .padding(.vertical, 10)
        .frame(minHeight: 44)
    }
}
