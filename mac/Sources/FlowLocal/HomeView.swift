import AppKit
import SwiftUI

// «Главная» - пять состояний: покой, запись, распознавание, нет микрофона,
// загрузка моделей. Одна колонка: «Недавние» - группой в покое, а не второй
// боковой панелью рядом с сайдбаром.
struct HomeView: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    private enum Mode { case idle, recording, processing, micError, loading }

    private var mode: Mode {
        if !state.micGranted { return .micError }
        switch state.phase {
        case .recording: return .recording
        case .processing: return .processing
        default: return state.backend == .starting ? .loading : .idle
        }
    }

    var body: some View {
        stage
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .transition(.opacity)
            .animation(Motion.page, value: mode)
    }

    @ViewBuilder
    private var stage: some View {
        switch mode {
        case .idle: IdleStage(actions: actions)
        case .recording: RecordingStage()
        case .processing: ProcessingStage(actions: actions)
        case .micError: MicErrorStage()
        case .loading: LoadingStage(actions: actions)
        }
    }
}

/// Микрофоны для выбора: системный - первым, с именем того, что сейчас стоит.
func micOptions(_ state: AppState) -> [(String?, String)] {
    [(nil, "Системный · \(AudioDevices.defaultInput()?.name ?? "по умолчанию")")]
        + state.micDevices.map { ($0.uid, $0.name) }
}

/// Нет доступа: спросить, если macOS ещё не спрашивала, иначе - открыть настройки.
func openMicrophoneAccess(_ state: AppState) {
    if Recorder.permission == .notDetermined {
        Recorder.requestPermission { _ in state.refreshPermissions() }
    } else if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone") {
        NSWorkspace.shared.open(url)
    }
}

// MARK: - покой

private struct IdleStage: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    var body: some View {
        PageScroll(maxWidth: 640) {
            HeroCard()
                .padding(.top, Space.s2)
            if !state.axTrusted {
                FLNotice(symbol: "exclamationmark.triangle.fill", title: "Вставка отключена",
                         text: "Без права «Универсальный доступ» текст ложится в буфер обмена, и вставлять его нужно самому, ⌘V. Если Flow Local уже есть в списке, удалите его и добавьте снова.") {
                    Button {
                        Inserter.requestTrust()
                        Inserter.openAccessibilitySettings()
                    } label: {
                        Label("Открыть настройки", systemImage: "arrow.up.forward.app")
                    }
                    .buttonStyle(FLButtonStyle(kind: .primary, size: .small))
                }
            }
            VStack(alignment: .leading, spacing: Space.s2) {
                SectionTitle("Сегодня")
                StatTiles()
            }
            RecentSection(actions: actions)
        }
    }
}

/// Главное на «Главной» - как начать: основное сочетание крупными клавишами
/// MacBook и одна фраза, что будет; второй способ - строкой ниже. Менять
/// сочетания - в настройках: здесь только то, что нужно, чтобы начать.
private struct HeroCard: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        let p = state.palette
        VStack(spacing: 0) {
            VStack(spacing: Space.s4) {
                Image(systemName: "waveform")
                    .font(.system(size: 20, weight: .medium))
                    .foregroundStyle(p.accent)
                    .frame(width: 44, height: 44)
                    .background(Circle().fill(p.wash(p.accent)))
                VStack(spacing: 6) {
                    Text("Удерживайте и говорите").textStyle(.title2, p.text, weight: .semibold)
                    Text("Отпустите клавиши — текст встанет туда, где стоит курсор: в письмо, чат или документ.")
                        .textStyle(.body, p.textMuted)
                        .multilineTextAlignment(.center)
                        .frame(maxWidth: 380)
                        .fixedSize(horizontal: false, vertical: true)
                }
                KeyCapRow(keys: state.hotkey.keys)
                    .padding(.top, Space.s1)
            }
            .padding(.top, Space.s6)
            .padding(.bottom, Space.s5)
            .padding(.horizontal, Space.s5)
            FLSeparator()
            HStack(spacing: Space.s2) {
                Text("Долгая диктовка").textStyle(.subheadline, p.textMuted).lineLimit(1)
                KeyCapRow(keys: state.toggleHotkey.keys, size: .small)
                Text("— начать, ещё раз — вставить").textStyle(.subheadline, p.textMuted).lineLimit(1)
                Spacer(minLength: Space.s2)
                Button("Изменить…") { state.tab = .settings }
                    .buttonStyle(FLButtonStyle(kind: .plain, size: .small))
                    .help("Сочетания клавиш — в настройках")
            }
            .padding(.leading, Space.s4)
            .padding(.trailing, Space.s2)
            .frame(height: 44)
        }
        .frame(maxWidth: .infinity)
        .card()
    }
}

// MARK: - запись

private struct RecordingStage: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        let p = state.palette
        let info = recording
        let expanded = state.transcriptExpanded
        VStack(alignment: .leading, spacing: Space.s4) {
            TimelineView(.periodic(from: info.since, by: 0.25)) { ctx in
                let t = ctx.date.timeIntervalSince(info.since)
                let wpm = t > 3 ? Int(Double(state.liveWords) / (t / 60)) : 0
                HStack(alignment: .firstTextBaseline, spacing: Space.s3) {
                    Text(MainView.clock(t))
                        .font(.system(size: expanded ? 22 : 44, weight: .light))
                        .monospacedDigit()
                        .foregroundStyle(p.text)
                    Text("\(wordsLabel(state.liveWords)) · \(wpm) сл/мин")
                        .textStyle(.body, p.textMuted)
                        .monospacedDigit()
                    Spacer()
                    FLTag(text: info.locked ? "По нажатию" : "Удерживая")
                }
            }
            if !expanded {
                LiveWaveform(count: 64, height: 72)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Space.s5)
                    .card()
                    .transition(.opacity)
            }
            LiveTranscript(title: "Расшифровка", caret: true)
            HStack(spacing: Space.s3) {
                KeyCapRow(keys: (info.locked ? state.toggleHotkey : state.hotkey).keys, size: .small, active: true)
                Text(info.locked ? "Нажмите ещё раз — текст встанет в активное окно"
                                 : "Отпустите — текст встанет в активное окно")
                    .textStyle(.body, p.textMuted)
                    .lineLimit(1)
                Spacer(minLength: Space.s3)
                Text("Esc — отмена").textStyle(.subheadline, p.textMuted)
            }
        }
        .frame(maxWidth: 760, maxHeight: .infinity, alignment: .top)
        .padding(.horizontal, Space.s5)
        .padding(.top, Space.s1)
        .padding(.bottom, Space.s5)
        .frame(maxWidth: .infinity)
        .animation(Motion.page, value: expanded)
    }

    private var recording: (since: Date, locked: Bool) {
        if case let .recording(since, locked) = state.phase { return (since, locked) }
        return (Date(), false)
    }
}

// MARK: - распознавание

private struct ProcessingStage: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    var body: some View {
        let p = state.palette
        VStack(alignment: .leading, spacing: Space.s4) {
            VStack(alignment: .leading, spacing: 6) {
                Text("Собираю текст").textStyle(.largeTitle, p.text)
                Text("Запись \(MainView.clock(state.recordSeconds)) · \(wordsLabel(state.liveWords)) на ходу. Остался хвост — меньше секунды.")
                    .textStyle(.body, p.textMuted)
            }
            ProgressView()
                .progressViewStyle(.linear)
                .tint(p.accent)
            LiveTranscript(title: "Предварительный текст", caret: false, skeleton: true)
            HStack(spacing: Space.s3) {
                Button(action: actions.cancelProcessing) { Label("Отменить", systemImage: "xmark") }
                    .buttonStyle(FLButtonStyle(kind: .secondary))
                Text(state.insertAutomatically ? "Текст вставится сам и останется в истории"
                                               : "Текст останется в истории")
                    .textStyle(.body, p.textMuted)
            }
        }
        .frame(maxWidth: 760, maxHeight: .infinity, alignment: .top)
        .padding(.horizontal, Space.s5)
        .padding(.top, Space.s1)
        .padding(.bottom, Space.s5)
        .frame(maxWidth: .infinity)
    }
}

// MARK: - нет доступа к микрофону

private struct MicErrorStage: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        let p = state.palette
        VStack(spacing: Space.s3) {
            Image(systemName: "mic.slash.fill")
                .font(.system(size: 32))
                .foregroundStyle(p.danger)
                .padding(.bottom, Space.s1)
            Text("Нет доступа к микрофону").textStyle(.title2, p.text, weight: .semibold)
            Text("macOS не разрешает Flow Local слушать вход. Откройте «Конфиденциальность и безопасность» → «Микрофон», включите Flow Local и вернитесь сюда.")
                .textStyle(.body, p.textMuted)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 380)
                .fixedSize(horizontal: false, vertical: true)
            HStack(spacing: Space.s2) {
                Button { openMicrophoneAccess(state) } label: {
                    Label("Открыть настройки macOS", systemImage: "arrow.up.forward.app")
                }
                .buttonStyle(FLButtonStyle(kind: .primary))
                Button { state.refreshPermissions() } label: {
                    Label("Проверить снова", systemImage: "arrow.clockwise")
                }
                .buttonStyle(FLButtonStyle(kind: .secondary))
            }
            .padding(.top, Space.s2)
            Text("Пока доступа нет, горячие клавиши молчат. История и настройки на месте.")
                .textStyle(.subheadline, p.textMuted)
                .padding(.top, Space.s1)
        }
        .padding(Space.s6)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - загрузка моделей

private struct LoadingStage: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    var body: some View {
        let p = state.palette
        PageScroll {
            VStack(alignment: .leading, spacing: Space.s2) {
                Text("Загружаю модели").textStyle(.largeTitle, p.text)
                Text("Несколько секунд при каждом запуске. Дальше всё работает без сети: звук и текст не уходят с этого Mac.")
                    .textStyle(.body, p.textMuted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(.top, Space.s2)
            VStack(spacing: 0) {
                step(p, state: .done, title: "Доступ к микрофону выдан", detail: nil)
                FLSeparator(inset: 48)
                step(p, state: .active, title: "Модели распознавания", detail: "RU · GigaAM v3    EN · Parakeet TDT")
                FLSeparator(inset: 48)
                step(p, state: .next, title: "Первая диктовка", detail: "Зажмите \(state.hotkey.label) и говорите")
            }
            .card()
            VStack(alignment: .leading, spacing: Space.s2) {
                FLCheck(isOn: Binding(get: { state.launchAtLogin }, set: { actions.setLaunchAtLogin($0) }),
                        label: "Запускать при входе в систему")
                FLCheck(isOn: $state.showPill, label: "Показывать островок во время диктовки")
            }
        }
    }

    private enum StepState { case done, active, next }

    private func step(_ p: Palette, state s: StepState, title: String, detail: String?) -> some View {
        HStack(spacing: Space.s3) {
            ZStack {
                switch s {
                case .done: Image(systemName: "checkmark.circle.fill").foregroundStyle(p.success)
                case .active: ProgressView().controlSize(.small)
                case .next: Image(systemName: "circle").foregroundStyle(p.textTertiary)
                }
            }
            .font(.system(size: 16))
            .frame(width: 20, height: 20)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).textStyle(.body, s == .next ? p.textMuted : p.text)
                if let detail { Text(detail).textStyle(.subheadline, p.textMuted) }
            }
            Spacer()
        }
        .padding(.horizontal, Space.s4)
        .padding(.vertical, Space.s3)
    }
}

// MARK: - сочетание с захватом

enum HotkeyRowStyle { case hero, row }

/// Сочетание и «Изменить». hero - большие клавиши MacBook на «Главной»,
/// row - маленькие в настройках. Места мало - клавиши уходят под текст.
struct HotkeyRow: View {
    @EnvironmentObject var state: AppState
    let role: HotkeyRole
    let actions: AppActions
    var style: HotkeyRowStyle = .row

    var body: some View {
        let p = state.palette
        VStack(alignment: .leading, spacing: Space.s2) {
            ViewThatFits(in: .horizontal) {
                HStack(spacing: Space.s4) {
                    texts(p)
                    Spacer(minLength: Space.s4)
                    keys(p)
                    buttons
                }
                VStack(alignment: .leading, spacing: Space.s3) {
                    texts(p)
                    HStack(spacing: Space.s3) {
                        keys(p)
                        buttons
                    }
                }
            }
            // Иначе выбранный вариант встаёт по центру карточки и строки
            // «Зажать» и «Нажать» начинаются с разных отступов.
            .frame(maxWidth: .infinity, alignment: .leading)
            note(p)
        }
        .padding(.horizontal, Space.s4)
        .padding(.vertical, style == .hero ? Space.s4 : 10)
        .animation(Motion.page, value: state.capturing)
    }

    private func texts(_ p: Palette) -> some View {
        HStack(spacing: Space.s3) {
            if style == .row { SettingIcon(symbol: role.symbol) }
            VStack(alignment: .leading, spacing: 2) {
                Text(role.title).textStyle(.body, p.text)
                Text(role.hint).textStyle(.subheadline, p.textMuted)
            }
        }
    }

    @ViewBuilder
    private func keys(_ p: Palette) -> some View {
        if state.capturing == role {
            Text("Нажмите сочетание…")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(.white)
                .padding(.horizontal, Space.s3)
                .frame(height: style == .hero ? 40 : Metric.buttonSmall)
                .background(RoundedRectangle(cornerRadius: Radius.control, style: .continuous).fill(p.accent))
        } else {
            KeyCapRow(keys: state.hotkey(for: role).keys, size: style == .hero ? .large : .small)
        }
    }

    @ViewBuilder
    private var buttons: some View {
        HStack(spacing: Space.s1) {
            if state.capturing == role {
                Button("Отмена", action: actions.cancelCapture)
                    .buttonStyle(FLButtonStyle(kind: .plain, size: .small))
            } else {
                Button("Изменить") { actions.beginCapture(role) }
                    .buttonStyle(FLButtonStyle(kind: .secondary, size: .small))
                if !state.hotkey(for: role).same(as: HotkeyPreset.defaultPreset(role)) {
                    FLIconButton(symbol: "arrow.uturn.backward", help: "Вернуть по умолчанию") {
                        actions.resetHotkey(role)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func note(_ p: Palette) -> some View {
        if state.capturing == role {
            Text("Сочетание с ⌃, ⌥, ⇧ или ⌘. Esc — отмена.").textStyle(.subheadline, p.textMuted)
        } else if let err = state.hotkeyError[role] {
            Text(err).textStyle(.subheadline, p.danger)
        }
    }
}

// MARK: - плитки

struct StatTiles: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        HStack(spacing: Space.s2) {
            StatTile(symbol: "text.alignleft", label: "Слов сегодня", value: grouped(state.wordsToday))
            StatTile(symbol: "speedometer", label: "Скорость", value: "\(state.speedWPM)", unit: "сл/мин")
            StatTile(symbol: "hourglass", label: "Сэкономлено", value: "\(state.savedMinutes)", unit: "мин")
        }
    }
}

// MARK: - расшифровка

/// Уже разобранный текст. Куски приходят окончательными: текст только
/// дописывается и не мигает. Сам прокручивается к новому; последний кусок -
/// label, прежнее - secondaryLabel. «Развернуть» отдаёт ему всю сцену.
struct LiveTranscript: View {
    @EnvironmentObject var state: AppState
    let title: String
    var caret = false
    var skeleton = false

    var body: some View {
        let p = state.palette
        VStack(alignment: .leading, spacing: Space.s3) {
            HStack(spacing: Space.s2) {
                Text(title).textStyle(.headline, p.text)
                Text(wordsLabel(state.liveWords)).textStyle(.subheadline, p.textMuted).monospacedDigit()
                Spacer()
                if caret {
                    FLIconButton(symbol: state.transcriptExpanded ? "arrow.down.right.and.arrow.up.left"
                                                                  : "arrow.up.left.and.arrow.down.right",
                                 help: state.transcriptExpanded ? "Свернуть" : "Развернуть") {
                        withAnimation(Motion.page) { state.transcriptExpanded.toggle() }
                    }
                }
            }
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: Space.s3) {
                        if caret {
                            TimelineView(.periodic(from: .now, by: 0.5)) { ctx in
                                transcriptText(p, caretOn: Int(ctx.date.timeIntervalSinceReferenceDate * 2) % 2 == 0)
                            }
                        } else {
                            transcriptText(p, caretOn: false)
                        }
                        if skeleton {
                            FLSkeleton()
                            FLSkeleton(width: 240)
                        }
                        Color.clear.frame(height: 1).id("end")
                    }
                }
                .scrollIndicators(.never)
                .onChange(of: state.liveText) { _, _ in
                    withAnimation(Motion.page) { proxy.scrollTo("end", anchor: .bottom) }
                }
                .onAppear { proxy.scrollTo("end", anchor: .bottom) }
            }
        }
        .padding(Space.s4)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .card()
    }

    private func transcriptText(_ p: Palette, caretOn: Bool) -> some View {
        transcript(p, caretOn: caretOn)
            .font(TextStyle.title3.font())
            .lineSpacing(6)
            .frame(maxWidth: .infinity, alignment: .leading)
            .fixedSize(horizontal: false, vertical: true)
            // Короткий кросс-фейд: длинный читался как задержка распознавания.
            .contentTransition(.opacity)
            .animation(Motion.press, value: state.liveText)
    }

    private func transcript(_ p: Palette, caretOn: Bool) -> Text {
        let mark = Text(" ▍").foregroundColor(caretOn ? p.accent : .clear)
        if state.liveText.isEmpty {
            let hint = Text(skeleton ? "" : "Говорите — текст появится здесь по мере разбора.")
                .foregroundColor(p.textMuted)
            return caret ? hint + mark : hint
        }
        // Сравниваем обрезанное: хвостовой пробел ломал hasSuffix, и тогда
        // весь текст уходил в приглушённый цвет вместе со свежим куском.
        let full = state.liveText.trimmingCharacters(in: .whitespacesAndNewlines)
        let latest = state.liveLatest.trimmingCharacters(in: .whitespacesAndNewlines)
        let split = !latest.isEmpty && full.hasSuffix(latest) && full.count > latest.count
        let older = split ? String(full.dropLast(latest.count)) : full
        var text = Text(older).foregroundColor(split ? p.textMuted : p.text)
        if split {
            text = text + Text(latest).foregroundColor(p.text)
        }
        return caret ? text + mark : text
    }
}

// MARK: - «Недавние»

/// Последние диктовки группой на «Главной»: те же строки и действия при
/// наведении, что в «Истории», в одной карточке. Остальное - по ссылке.
struct RecentSection: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions
    static let limit = 5

    var body: some View {
        let p = state.palette
        let items = Array(state.history.prefix(Self.limit))
        VStack(alignment: .leading, spacing: Space.s2) {
            HStack {
                SectionTitle("Недавние")
                Spacer()
                if !items.isEmpty {
                    Button { state.tab = .history } label: {
                        HStack(spacing: 4) {
                            Text("Вся история")
                            Image(systemName: "chevron.right").font(.system(size: 10, weight: .semibold))
                        }
                    }
                    .buttonStyle(FLButtonStyle(kind: .plain, size: .small))
                    .help("История · ⌘2")
                    // Подпись - вровень с правым краем карточки, ряд - высотой заголовка.
                    .padding(.trailing, -10)
                    .padding(.vertical, -3)
                }
            }
            if items.isEmpty {
                HStack(spacing: Space.s3) {
                    Image(systemName: "waveform")
                        .font(.system(size: 14))
                        .foregroundStyle(p.textTertiary)
                    Text("Диктовок ещё нет — первая появится здесь.").textStyle(.body, p.textMuted)
                    Spacer(minLength: 0)
                }
                .padding(.horizontal, Space.s4)
                .frame(minHeight: 44)
                .card()
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(items.enumerated()), id: \.element.id) { i, entry in
                        HistoryRow(entry: entry, actions: actions, divider: i > 0, showDay: true)
                    }
                }
                .card()
                .clipShape(RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
            }
        }
        .animation(Motion.page, value: items.map(\.id))
    }
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

    static let weekday: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ru_RU")
        f.dateFormat = "EE"
        return f
    }()

    static func sectionTitle(_ day: Date) -> String {
        let cal = Calendar.current
        if cal.isDateInToday(day) { return "Сегодня" }
        if cal.isDateInYesterday(day) { return "Вчера" }
        if cal.isDate(day, equalTo: Date(), toGranularity: .year) { return Self.day.string(from: day) }
        return dayYear.string(from: day)
    }
}
