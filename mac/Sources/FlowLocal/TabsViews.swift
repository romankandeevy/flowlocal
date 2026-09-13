import AppKit
import SwiftUI

// Вкладки «История», «Статистика», «Настройки». В макете их не было, собраны
// из его набора элементов (1g): строки настроек, числа, пустота, история.

// MARK: - История

struct HistoryView: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions
    @State private var query = ""
    @State private var confirmClear = false

    var body: some View {
        let p = state.palette
        let items = filtered
        VStack(spacing: 0) {
            HStack(spacing: Space.s3) {
                VKSearchField(text: $query, palette: p)
                Text("\(items.count) из \(state.history.count)").monoLabel(p.textMuted).fixedSize()
                if !state.history.isEmpty {
                    Button(confirmClear ? "Удалить все?" : "Очистить") {
                        if confirmClear {
                            state.clearHistory()
                            confirmClear = false
                        } else {
                            confirmClear = true
                            DispatchQueue.main.asyncAfter(deadline: .now() + 3) { confirmClear = false }
                        }
                    }
                    .buttonStyle(VKButtonStyle(palette: p, kind: .danger, size: .sm))
                }
            }
            .padding(Space.s4)
            VKDivider(palette: p)
            if state.history.isEmpty {
                VKEmpty(title: "Диктовок ещё нет",
                        text: "Зажмите \(state.hotkey.label) и скажите первую фразу.", palette: p)
                    .padding(Space.s5)
                Spacer()
            } else if items.isEmpty {
                VKEmpty(code: "Поиск", title: "Ничего не найдено", text: "Измените запрос.", palette: p)
                    .padding(Space.s5)
                Spacer()
            } else {
                ScrollView {
                    LazyVStack(spacing: 0) {
                        ForEach(items) { e in
                            HistoryRow(entry: e, actions: actions)
                            VKDivider(palette: p)
                        }
                    }
                }
            }
        }
    }

    private var filtered: [Entry] {
        let q = query.trimmingCharacters(in: .whitespaces)
        return q.isEmpty ? state.history : state.history.filter { $0.text.localizedCaseInsensitiveContains(q) }
    }
}

struct HistoryRow: View {
    @EnvironmentObject var state: AppState
    let entry: Entry
    let actions: AppActions
    @State private var open = false
    @State private var copied = false

    private static let stamp: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "dd.MM.yyyy · HH:mm"
        return f
    }()

    var body: some View {
        let p = state.palette
        let long = entry.words > 60
        VStack(alignment: .leading, spacing: Space.s3) {
            HStack(spacing: Space.s3) {
                Text(Self.stamp.string(from: entry.date)).monoLabel(p.textMuted)
                Text(wordsLabel(entry.words)).monoLabel(p.textMuted)
                Text(MainView.clock(entry.seconds)).monoLabel(p.textMuted)
                VKBadge(text: entry.lang, tone: .outline, palette: p)
                if entry.failed { VKBadge(text: "Не распознано", tone: .warning, palette: p) }
            }
            if entry.failed {
                Text("Речь не распознана. Запись сохранена — попробуйте перераспознать, например другим языком.")
                    .font(Fonts.text(FontSize.fs2))
                    .foregroundStyle(p.textMuted)
            } else if open || !long {
                Text(entry.text)
                    .font(Fonts.text(FontSize.fs3))
                    .foregroundStyle(p.text)
                    .lineSpacing(4)
                    .textSelection(.enabled)
                    .frame(maxWidth: 760, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                Text(entry.text)
                    .font(Fonts.text(FontSize.fs3))
                    .foregroundStyle(p.text)
                    .lineSpacing(4)
                    .lineLimit(4)
                    .frame(maxWidth: 760, alignment: .leading)
            }
            HStack(spacing: Space.s2) {
                Button(copied ? "Скопировано" : "Копировать") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(entry.text, forType: .string)
                    copied = true
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) { copied = false }
                }
                .buttonStyle(VKButtonStyle(palette: p, kind: .secondary, size: .sm))
                .disabled(entry.failed)
                Button("Вставить") { actions.paste(entry) }
                    .buttonStyle(VKButtonStyle(palette: p, kind: .ghost, size: .sm))
                    .disabled(entry.failed)
                if long {
                    Button(open ? "Свернуть" : "Показать всё") { withAnimation(Motion.base) { open.toggle() } }
                        .buttonStyle(VKButtonStyle(palette: p, kind: .ghost, size: .sm))
                }
                if AudioStore.exists(entry.audio) {
                    Button(state.playing == entry.id ? "Стоп" : "Прослушать") { actions.play(entry) }
                        .buttonStyle(VKButtonStyle(palette: p, kind: .ghost, size: .sm))
                    Button(state.rerecognizing.contains(entry.id) ? "Распознаю…" : "Перераспознать") {
                        actions.rerecognize(entry)
                    }
                    .buttonStyle(VKButtonStyle(palette: p, kind: .ghost, size: .sm))
                    .disabled(state.rerecognizing.contains(entry.id))
                }
                Spacer()
                Button("Удалить") { state.remove(entry) }
                    .buttonStyle(VKButtonStyle(palette: p, kind: .ghost, size: .sm))
            }
        }
        .padding(.horizontal, Space.s5)
        .padding(.vertical, Space.s4)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Статистика

struct StatsView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        let p = state.palette
        ScrollView {
            VStack(alignment: .leading, spacing: Space.s5) {
                VStack(alignment: .leading, spacing: Space.s2) {
                    Text("Статистика").displayTitle(p.text, size: FontSize.fs5, weight: .bold)
                    Text("Считается по истории на этом компьютере. Печать для сравнения — \(Int(AppState.typingWPM)) слов в минуту.")
                        .font(Fonts.text(FontSize.fs2))
                        .foregroundStyle(p.textMuted)
                        .fixedSize(horizontal: false, vertical: true)
                }
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: Space.hairline), count: 3),
                          spacing: Space.hairline) {
                    VKStatTile(label: "Слов сегодня", value: grouped(state.wordsToday), palette: p, size: FontSize.fs5)
                    VKStatTile(label: "Слов за неделю", value: grouped(state.wordsWeek), palette: p, size: FontSize.fs5)
                    VKStatTile(label: "Скорость", value: "\(state.speedWPM)", unit: "сл/мин", palette: p, size: FontSize.fs5)
                    VKStatTile(label: "Сэкономлено", value: "\(state.savedMinutes)", unit: "мин", palette: p, size: FontSize.fs5)
                    VKStatTile(label: "Голос / клавиатура", value: ratio, palette: p, size: FontSize.fs5)
                    VKStatTile(label: "Диктовок сегодня", value: "\(state.dictationsToday)", palette: p, size: FontSize.fs5)
                }
                .background(p.border)
                .overlay(Rectangle().strokeBorder(p.border, lineWidth: Space.hairline))
                VKDivider(palette: p)
                VStack(alignment: .leading, spacing: Space.s4) {
                    Text("Последние 7 дней").monoLabel(p.textMuted)
                    WeekBars()
                }
            }
            .padding(Space.s5)
            .frame(maxWidth: 880, alignment: .leading)
        }
        .scrollIndicators(.never)
    }

    private var ratio: String {
        guard state.speedWPM > 0 else { return "—" }
        return String(format: "%.1f×", state.voiceRatio).replacingOccurrences(of: ".", with: ",")
    }
}

/// Столбики по дням. Сегодня - акцентом: один акцент на экране.
struct WeekBars: View {
    @EnvironmentObject var state: AppState

    private static let weekday: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ru_RU")
        f.dateFormat = "EE"
        return f
    }()

    var body: some View {
        let p = state.palette
        let days = state.lastDays
        let top = max(1, days.map(\.words).max() ?? 1)
        HStack(alignment: .bottom, spacing: Space.s2) {
            ForEach(days.indices, id: \.self) { i in
                let today = i == days.count - 1
                VStack(spacing: Space.s2) {
                    Text(grouped(days[i].words)).monoLabel(p.textMuted).lineLimit(1).minimumScaleFactor(0.6)
                    Rectangle()
                        .fill(today ? p.accent : p.borderStrong)
                        .frame(height: max(2, 120 * CGFloat(days[i].words) / CGFloat(top)))
                    Text(Self.weekday.string(from: days[i].date)).monoLabel(today ? p.text : p.textMuted)
                }
                .frame(maxWidth: .infinity)
            }
        }
        .frame(height: 170, alignment: .bottom)
    }
}

// MARK: - Настройки

// Разделы по шаблону страницы-формы Verkstad: подпись раздела слева, строки
// справа, разделы через хейрлайн. На узком окне подпись встаёт над строками.
struct SettingsView: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions
    @State private var recordings = (count: 0, bytes: Int64(0))

    var body: some View {
        let p = state.palette
        GeometryReader { geo in
            let wide = geo.size.width >= 760
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    VStack(alignment: .leading, spacing: Space.s2) {
                        Text("Настройки").displayTitle(p.text, size: FontSize.fs5, weight: .bold)
                        Text("Всё хранится на этом Mac. Аккаунта и сервера нет.")
                            .font(Fonts.text(FontSize.fs2))
                            .foregroundStyle(p.textMuted)
                    }
                    .padding(.bottom, Space.s5)

                    section("Горячие клавиши", "Два способа начать диктовку", wide: wide) {
                        ForEach(Array(HotkeyRole.allCases.enumerated()), id: \.offset) { i, role in
                            // Всегда под текстом: три клавиши и «Изменить» справа от
                            // заголовка не влезают и на широком окне.
                            SettingRow(title: role.title, subtitle: role.hint, last: i == 1, stacked: true) {
                                HotkeyRow(role: role, actions: actions, height: Space.controlSm)
                            }
                        }
                    }
                    section("Диктовка", "Что происходит с текстом", wide: wide) {
                        SettingRow(title: "Вставлять текст сразу", subtitle: "Иначе текст только в истории") {
                            VKSwitch(isOn: $state.insertAutomatically, palette: p)
                        }
                        SettingRow(title: "Язык", subtitle: "Авто — русский и английский по кускам речи") {
                            VKSegmented(options: LangMode.allCases.map { ($0, $0.title) },
                                        selection: $state.langMode, palette: p)
                        }
                        SettingRow(title: "Плашка поверх окон", subtitle: "Уровень, таймер и слова у нижнего края экрана") {
                            VKSwitch(isOn: $state.showPill, palette: p)
                        }
                        SettingRow(title: "Звук начала и конца", subtitle: "Короткий щелчок, когда запись началась и закончилась",
                                   last: true) {
                            VKSwitch(isOn: $state.sounds, palette: p)
                        }
                    }
                    section("Микрофон", "Слушает только пока идёт запись", wide: wide) {
                        SettingRow(title: "Устройство", subtitle: state.micName, last: true, stacked: !wide) {
                            VKSelect(options: micOptions, selection: $state.micUID, palette: p, small: true)
                                .frame(width: wide ? 260 : nil)
                        }
                    }
                    section("Записи", "Аудио каждой диктовки — чтобы перераспознать", wide: wide) {
                        SettingRow(title: "Сохранять аудио", subtitle: "WAV 16 кГц, около 2 МБ на минуту") {
                            VKSwitch(isOn: $state.saveAudio, palette: p)
                        }
                        SettingRow(title: "Папка записей",
                                   subtitle: "\(recordings.count) \(plural(recordings.count, "файл", "файла", "файлов")) · \(megabytes)",
                                   last: true) {
                            Button("Открыть", action: actions.openRecordings)
                                .buttonStyle(VKButtonStyle(palette: p, kind: .ghost, size: .sm))
                        }
                    }
                    section("Система", "Запуск, вид и разрешения", wide: wide) {
                        SettingRow(title: "Запускать при входе в систему", subtitle: "Flow Local стартует вместе с macOS") {
                            VKSwitch(isOn: Binding(get: { state.launchAtLogin }, set: { actions.setLaunchAtLogin($0) }),
                                     palette: p)
                        }
                        SettingRow(title: "Тема", subtitle: "Две равноправные темы") {
                            VKSegmented(options: ThemeKind.allCases.map { ($0, $0.title) }, selection: $state.theme, palette: p)
                        }
                        SettingRow(title: "Микрофон", subtitle: state.micGranted ? "Доступ выдан" : "Не выдан — диктовка выключена") {
                            permission(state.micGranted, p) {
                                if Recorder.permission == .notDetermined {
                                    Recorder.requestPermission { _ in state.refreshPermissions() }
                                } else if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone") {
                                    NSWorkspace.shared.open(url)
                                }
                            }
                        }
                        SettingRow(title: "Универсальный доступ",
                                   subtitle: state.axTrusted ? "Выдан — вставка в любое окно" : "Не выдан — текст ложится в буфер",
                                   last: true) {
                            permission(state.axTrusted, p) {
                                Inserter.requestTrust()
                                Inserter.openAccessibilitySettings()
                            }
                        }
                    }
                    section("Распознавание", "Локальные модели, процессор", wide: wide, last: true) {
                        SettingRow(title: "Русский", subtitle: "GigaAM v3 e2e · int8") {
                            VKBadge(text: state.backend == .ready ? "Готов" : "Загрузка",
                                    tone: state.backend == .ready ? .success : .warning, palette: p)
                        }
                        SettingRow(title: "Английский", subtitle: "Parakeet TDT 0.6b v2 · int8") {
                            VKBadge(text: state.englishReady ? "Готов" : "Загрузка",
                                    tone: state.englishReady ? .success : .warning, palette: p)
                        }
                        SettingRow(title: "Журнал", subtitle: "~/Library/Logs/FlowLocal.log", last: true) {
                            Button("Открыть", action: actions.openLog)
                                .buttonStyle(VKButtonStyle(palette: p, kind: .ghost, size: .sm))
                        }
                    }
                }
                .padding(Space.s5)
                .frame(maxWidth: 960, alignment: .leading)
            }
            .scrollIndicators(.never)
        }
        .onAppear(perform: countRecordings)
    }

    private var micOptions: [(String?, String)] {
        [(nil, "Системный · \(AudioDevices.defaultInput()?.name ?? "по умолчанию")")]
            + state.micDevices.map { ($0.uid, $0.name) }
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
    private func section<C: View>(_ title: String, _ note: String, wide: Bool, last: Bool = false,
                                  @ViewBuilder _ rows: () -> C) -> some View {
        let p = state.palette
        VStack(spacing: 0) {
            VKDivider(palette: p)
            Group {
                if wide {
                    HStack(alignment: .top, spacing: Space.s5) {
                        label(title, note, p).frame(width: 200, alignment: .leading)
                        box(p, rows)
                    }
                } else {
                    VStack(alignment: .leading, spacing: Space.s3) {
                        label(title, note, p)
                        box(p, rows)
                    }
                }
            }
            .padding(.vertical, Space.s5)
            if last { VKDivider(palette: p) }
        }
    }

    private func label(_ title: String, _ note: String, _ p: Palette) -> some View {
        VStack(alignment: .leading, spacing: Space.s1) {
            Text(title).monoLabel(p.text)
            Text(note)
                .font(Fonts.text(FontSize.fs1))
                .foregroundStyle(p.textMuted)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func box<C: View>(_ p: Palette, _ rows: () -> C) -> some View {
        VStack(spacing: 0) { rows() }
            .frame(maxWidth: .infinity)
            .background(p.surface)
            .overlay(Rectangle().strokeBorder(p.border, lineWidth: Space.hairline))
    }

    private func permission(_ ok: Bool, _ p: Palette, open: @escaping () -> Void) -> some View {
        HStack(spacing: Space.s3) {
            VKBadge(text: ok ? "Выдан" : "Нет", tone: ok ? .success : .danger, palette: p)
            if !ok {
                Button("Открыть", action: open)
                    .buttonStyle(VKButtonStyle(palette: p, kind: .ghost, size: .sm))
            }
        }
    }
}

/// Строка настроек из набора 1g: заголовок, пояснение, контрол справа.
struct SettingRow<Control: View>: View {
    @EnvironmentObject var state: AppState
    let title: String
    let subtitle: String
    var last = false
    /// Контрол под текстом, а не справа: для широких контролов и узкого окна.
    var stacked = false
    @ViewBuilder let control: () -> Control

    var body: some View {
        let p = state.palette
        VStack(spacing: 0) {
            Group {
                if stacked {
                    VStack(alignment: .leading, spacing: Space.s3) {
                        texts(p)
                        control()
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                } else {
                    HStack(spacing: Space.s4) {
                        texts(p)
                        Spacer(minLength: Space.s4)
                        control()
                    }
                }
            }
            .padding(.horizontal, Space.s4)
            .padding(.vertical, Space.s3)
            if !last {
                VKDivider(palette: p)
            }
        }
    }

    private func texts(_ p: Palette) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(Fonts.text(FontSize.fs2, .medium)).foregroundStyle(p.text)
            Text(subtitle)
                .font(Fonts.text(FontSize.fs1))
                .foregroundStyle(p.textMuted)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}
