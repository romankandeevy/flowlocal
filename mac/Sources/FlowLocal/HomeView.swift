import AppKit
import SwiftUI

// Вкладка «Главная» - пять состояний макета: 1a покой, 1b запись,
// 1c распознавание, 1d нет микрофона, 1e загрузка моделей. Размеры сбавлены
// против макета: на 37-40 px и 44 px клавиш окно выглядело громоздким.
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
        let p = state.palette
        Group {
            switch mode {
            case .recording: recording(p)
            case .processing: processing(p)
            case .micError: scroll { micError(p) }
            case .loading: scroll { loading(p) }
            case .idle: scroll { idle(p) }
            }
        }
        .padding(Space.s5)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }

    private func scroll<C: View>(@ViewBuilder _ content: () -> C) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Space.s5) { content() }
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .scrollIndicators(.never)
    }

    // MARK: - 1a покой

    @ViewBuilder
    private func idle(_ p: Palette) -> some View {
        statusLine(p)
        VStack(alignment: .leading, spacing: Space.s3) {
            Text("Говорите — текст на месте")
                .displayTitle(p.text, size: FontSize.fs5, weight: .bold)
                .fixedSize(horizontal: false, vertical: true)
            Text("Работает в любом окне: письмо, чат, документ. Голос не покидает этот компьютер.")
                .font(Fonts.text(FontSize.fs2))
                .foregroundStyle(p.textMuted)
                .lineSpacing(3)
                .fixedSize(horizontal: false, vertical: true)
        }
        VStack(alignment: .leading, spacing: Space.s3) {
            ForEach(HotkeyRole.allCases) { role in
                HStack(alignment: .center, spacing: Space.s4) {
                    Text(role.title).monoLabel(p.textMuted).frame(width: 64, alignment: .leading)
                    HotkeyRow(role: role, actions: actions, height: 36)
                }
            }
        }
        if !state.axTrusted {
            VKAlert(mark: "Внимание", title: "Вставка отключена",
                    text: "Нет права «Универсальный доступ»: текст ложится в буфер, вставка — ⌘V вручную. Если Flow Local уже в списке, удалите его и добавьте снова.",
                    palette: p) {
                Button("Открыть настройки") {
                    Inserter.requestTrust()
                    Inserter.openAccessibilitySettings()
                }
                .buttonStyle(VKButtonStyle(palette: p, kind: .primary, size: .sm))
            }
        }
        VKDivider(palette: p)
        StatTiles()
        MicRow()
    }

    private func statusLine(_ p: Palette) -> some View {
        HStack(spacing: Space.s3) {
            switch state.backend {
            case .ready:
                Rectangle().fill(p.success).frame(width: 8, height: 8)
                Text("Готов").monoLabel(p.text)
                Text("/ \(state.langMode.title) / " + (state.englishReady ? "GigaAM v3 · Parakeet" : "GigaAM v3"))
                    .monoLabel(p.textMuted).lineLimit(1)
            case .starting:
                Rectangle().fill(p.warning).frame(width: 8, height: 8)
                Text("Загрузка").monoLabel(p.text)
            case let .failed(msg):
                Rectangle().fill(p.danger).frame(width: 8, height: 8)
                Text("Ошибка").monoLabel(p.text)
                Text("/ \(msg)").monoLabel(p.textMuted).lineLimit(2)
            }
        }
    }

    // MARK: - 1b запись

    private func recording(_ p: Palette) -> some View {
        let since: Date
        let locked: Bool
        if case let .recording(s, l) = state.phase { since = s; locked = l } else { since = Date(); locked = false }
        let expanded = state.transcriptExpanded
        return VStack(alignment: .leading, spacing: Space.s4) {
            TimelineView(.periodic(from: since, by: 0.25)) { ctx in
                let t = ctx.date.timeIntervalSince(since)
                let wpm = t > 3 ? Int(Double(state.liveWords) / (t / 60)) : 0
                HStack(alignment: .firstTextBaseline, spacing: Space.s4) {
                    Text(MainView.clock(t))
                        .displayTitle(p.text, size: expanded ? FontSize.fs4 : 48, weight: .bold)
                        .monospacedDigit()
                    Text("\(wordsLabel(state.liveWords)) / \(wpm) сл/мин").monoLabel(p.textMuted)
                    Spacer()
                    VKBadge(text: locked ? "Нажать" : "Зажать", tone: .outline, palette: p)
                }
            }
            if !expanded {
                LiveLevels(color: p.accent, count: 44, spacing: 3, height: 64, floor: 0.08)
                    .padding(Space.s4)
                    .background(p.surface)
                    .overlay(Rectangle().strokeBorder(p.border, lineWidth: Space.hairline))
            }
            LiveTranscript(title: "Расшифровка в ходе речи", caret: true)
            HStack(spacing: Space.s4) {
                VKKeycap(text: locked ? state.toggleHotkey.label : state.hotkey.label,
                         palette: p, height: 32, accent: true)
                Text(locked ? "Нажмите ещё раз — текст встанет в активное окно" : "Отпустите — текст встанет в активное окно")
                    .font(Fonts.text(FontSize.fs2))
                    .foregroundStyle(p.textMuted)
                    .lineLimit(2)
            }
        }
        .animation(Motion.base, value: expanded)
    }

    // MARK: - 1c распознавание

    private func processing(_ p: Palette) -> some View {
        VStack(alignment: .leading, spacing: Space.s4) {
            VStack(alignment: .leading, spacing: Space.s2) {
                Text("Собираю текст").displayTitle(p.text, size: FontSize.fs5, weight: .bold)
                Text("Запись \(MainView.clock(state.recordSeconds)) · \(wordsLabel(state.liveWords)) на ходу. Остался хвост — меньше секунды.")
                    .font(Fonts.text(FontSize.fs2))
                    .foregroundStyle(p.textMuted)
            }
            VKProgress(value: nil, palette: p, height: 4)
            LiveTranscript(title: "Предварительный текст", caret: false, skeleton: true)
            HStack(spacing: Space.s3) {
                Button("Отменить", action: actions.cancelProcessing)
                    .buttonStyle(VKButtonStyle(palette: p, kind: .secondary, size: .sm))
                Text(state.insertAutomatically ? "Текст вставится сам и останется в истории" : "Текст останется в истории")
                    .font(Fonts.text(FontSize.fs2))
                    .foregroundStyle(p.textMuted)
            }
        }
    }

    // MARK: - 1d нет доступа к микрофону

    @ViewBuilder
    private func micError(_ p: Palette) -> some View {
        VKAlert(mark: "Ошибка", title: "Доступ к микрофону не выдан",
                text: "macOS не разрешает Flow Local слушать вход. Откройте «Конфиденциальность и безопасность» → «Микрофон» и включите Flow Local, затем вернитесь сюда.",
                tone: .danger, palette: p) { EmptyView() }
        VStack(alignment: .leading, spacing: Space.s3) {
            Text("Диктовка выключена").displayTitle(p.text, size: FontSize.fs5, weight: .bold)
            Text("Горячие клавиши не сработают, пока нет доступа. История и настройки остаются на месте.")
                .font(Fonts.text(FontSize.fs2))
                .foregroundStyle(p.textMuted)
                .fixedSize(horizontal: false, vertical: true)
        }
        HStack(spacing: Space.s3) {
            Button("Открыть настройки macOS") {
                if Recorder.permission == .notDetermined {
                    Recorder.requestPermission { _ in state.refreshPermissions() }
                } else if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone") {
                    NSWorkspace.shared.open(url)
                }
            }
            .buttonStyle(VKButtonStyle(palette: p, kind: .primary))
            Button("Проверить снова") { state.refreshPermissions() }
                .buttonStyle(VKButtonStyle(palette: p, kind: .secondary))
        }
        VStack(spacing: 0) {
            HStack {
                Text("Устройство ввода").monoLabel(p.textMuted)
                Spacer()
                VKBadge(text: "Нет сигнала", tone: .danger, palette: p)
            }
            .padding(.horizontal, Space.s4)
            .padding(.vertical, Space.s3)
            VKDivider(palette: p)
            HStack(spacing: Space.s4) {
                Text(state.micName).font(Fonts.text(FontSize.fs2)).foregroundStyle(p.text).lineLimit(1)
                Spacer()
                Button("Выбрать другой") { pickMic() }
                    .buttonStyle(VKButtonStyle(palette: p, kind: .ghost, size: .sm))
            }
            .padding(.horizontal, Space.s4)
            .padding(.vertical, Space.s3)
        }
        .background(p.surface)
        .overlay(Rectangle().strokeBorder(p.border, lineWidth: Space.hairline))
    }

    private func pickMic() {
        state.refreshDevices()
        let options: [(String?, String)] = [(nil, "Системный по умолчанию")] + state.micDevices.map { ($0.uid, $0.name) }
        MenuPresenter.show(options.map { ($0.1, $0.0 == state.micUID) }) { i in
            actions.selectMic(options[i].0)
        }
    }

    // MARK: - 1e загрузка моделей

    @ViewBuilder
    private func loading(_ p: Palette) -> some View {
        VStack(alignment: .leading, spacing: Space.s3) {
            Text("Загружаю модели распознавания")
                .displayTitle(p.text, size: FontSize.fs5, weight: .bold)
                .fixedSize(horizontal: false, vertical: true)
            Text("Несколько секунд при каждом запуске. Дальше приложение работает без сети: аудио и текст не уходят с компьютера.")
                .font(Fonts.text(FontSize.fs2))
                .foregroundStyle(p.textMuted)
                .fixedSize(horizontal: false, vertical: true)
        }
        VStack(alignment: .leading, spacing: Space.s2) {
            Text("RU · GigaAM v3  /  EN · Parakeet").monoLabel(p.textMuted)
            VKProgress(value: nil, palette: p, height: 4)
        }
        VStack(spacing: 0) {
            step(p, mark: state.micGranted ? "Ок" : "Сейчас", markColor: state.micGranted ? p.success : p.accentInk,
                 text: state.micGranted ? "Доступ к микрофону выдан" : "Доступ к микрофону", active: !state.micGranted)
            VKDivider(palette: p)
            step(p, mark: "Сейчас", markColor: p.accentInk, text: "Загрузка моделей", active: true)
            VKDivider(palette: p)
            step(p, mark: "Далее", markColor: p.textMuted, text: "Первая диктовка: \(state.hotkey.label)", active: false)
        }
        .background(p.surface)
        .overlay(Rectangle().strokeBorder(p.border, lineWidth: Space.hairline))
        VStack(alignment: .leading, spacing: Space.s3) {
            VKCheck(isOn: Binding(get: { state.launchAtLogin }, set: { actions.setLaunchAtLogin($0) }),
                    label: "Запускать при входе в систему", palette: p)
            VKCheck(isOn: $state.showPill, label: "Показывать плашку поверх окон", palette: p)
        }
    }

    private func step(_ p: Palette, mark: String, markColor: Color, text: String, active: Bool) -> some View {
        HStack(spacing: Space.s4) {
            Text(mark).monoLabel(markColor).frame(width: 60, alignment: .leading)
            Text(text).font(Fonts.text(FontSize.fs2)).foregroundStyle(active ? p.text : p.textMuted)
            Spacer()
        }
        .padding(.horizontal, Space.s4)
        .padding(.vertical, Space.s3)
        .background(active ? p.surface2 : Color.clear)
    }
}

// MARK: - сочетание с захватом

/// Клавиши сочетания и «Изменить». Захват - как в наборе 1g: клавиша
/// становится акцентной, надпись меняется на приглашение.
struct HotkeyRow: View {
    @EnvironmentObject var state: AppState
    let role: HotkeyRole
    let actions: AppActions
    var height: CGFloat = 36

    var body: some View {
        let p = state.palette
        let preset = state.hotkey(for: role)
        VStack(alignment: .leading, spacing: Space.s2) {
            HStack(spacing: Space.s2) {
                if state.capturing == role {
                    VKKeycap(text: "Нажмите клавиши", palette: p, height: height, accent: true)
                    Button("Отмена", action: actions.cancelCapture)
                        .buttonStyle(VKButtonStyle(palette: p, kind: .ghost, size: .sm))
                } else {
                    VKCombo(keys: preset.keys, palette: p, height: height)
                    Button("Изменить") { actions.beginCapture(role) }
                        .buttonStyle(VKButtonStyle(palette: p, kind: .ghost, size: .sm))
                        .padding(.leading, Space.s2)
                    if !preset.same(as: HotkeyPreset.defaultPreset(role)) {
                        Button("Сбросить") { actions.resetHotkey(role) }
                            .buttonStyle(VKButtonStyle(palette: p, kind: .ghost, size: .sm))
                    }
                }
            }
            if state.capturing == role {
                Text("Сочетание с Ctrl, Option, Shift или Cmd. Esc — отмена.")
                    .font(Fonts.text(FontSize.fs1)).foregroundStyle(p.textMuted)
            } else if let err = state.hotkeyError[role] {
                Text(err).font(Fonts.text(FontSize.fs1)).foregroundStyle(p.danger)
            }
        }
    }
}

// MARK: - плитки

struct StatTiles: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        let p = state.palette
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: Space.hairline), count: 3),
                  spacing: Space.hairline) {
            VKStatTile(label: "Слов сегодня", value: grouped(state.wordsToday), palette: p, size: FontSize.fs5)
            VKStatTile(label: "Скорость", value: "\(state.speedWPM)", unit: "сл/мин", palette: p, size: FontSize.fs5)
            VKStatTile(label: "Сэкономлено", value: "\(state.savedMinutes)", unit: "мин", palette: p, size: FontSize.fs5)
        }
        .background(p.border)
        .overlay(Rectangle().strokeBorder(p.border, lineWidth: Space.hairline))
    }
}

// MARK: - микрофон

struct MicRow: View {
    @EnvironmentObject var state: AppState
    @ObservedObject private var meter = LevelStore.shared

    var body: some View {
        let p = state.palette
        let options: [(String?, String)] = [(nil, "Системный · \(AudioDevices.defaultInput()?.name ?? "по умолчанию")")]
            + state.micDevices.map { ($0.uid, $0.name) }
        VStack(alignment: .leading, spacing: Space.s2) {
            Text("Микрофон").monoLabel(p.textMuted)
            HStack(spacing: Space.s4) {
                VKSelect(options: options, selection: $state.micUID, palette: p, small: true)
                VKLevelBars(levels: meter.levels, color: p.textMuted, count: 5, spacing: 3, barWidth: 3, height: 20)
                Text(meter.peak > 0.1 ? "Сигнал" : "Тишина").monoLabel(p.textMuted).frame(width: 60, alignment: .leading)
            }
        }
    }
}

// MARK: - расшифровка

/// Уже разобранный текст. Куски приходят окончательными: текст только
/// дописывается и не мигает. Сам прокручивается к новому; последний кусок -
/// цветом текста, прежнее - приглушённым. «Развернуть» отдаёт ему всё окно.
struct LiveTranscript: View {
    @EnvironmentObject var state: AppState
    let title: String
    var caret = false
    var skeleton = false

    var body: some View {
        let p = state.palette
        VStack(alignment: .leading, spacing: Space.s3) {
            HStack(spacing: Space.s3) {
                Text(title).monoLabel(p.textMuted)
                Text(wordsLabel(state.liveWords)).monoLabel(p.textMuted)
                Spacer()
                if caret {
                    Button(state.transcriptExpanded ? "Свернуть" : "Развернуть") {
                        state.transcriptExpanded.toggle()
                    }
                    .buttonStyle(VKButtonStyle(palette: p, kind: .ghost, size: .sm))
                }
            }
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: Space.s3) {
                        TimelineView(.periodic(from: .now, by: 0.5)) { ctx in
                            let on = Int(ctx.date.timeIntervalSinceReferenceDate * 2) % 2 == 0
                            transcript(p, caretOn: on)
                                .font(Fonts.text(FontSize.fs3 + 2))
                                .lineSpacing(6)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .fixedSize(horizontal: false, vertical: true)
                                // Новый кусок раньше влетал разом - дёргано. Кросс-фейд
                                // делает появление слов плавным, без прыжков верстки.
                                .contentTransition(.opacity)
                                .animation(Motion.base, value: state.liveText)
                        }
                        if skeleton {
                            VKSkeleton(palette: p, height: 12)
                            VKSkeleton(palette: p, height: 12, delay: 0.15).frame(maxWidth: 240)
                        }
                        Color.clear.frame(height: 1).id("end")
                    }
                }
                .scrollIndicators(.never)
                .onChange(of: state.liveText) { _, _ in
                    withAnimation(Motion.base) { proxy.scrollTo("end", anchor: .bottom) }
                }
                .onAppear { proxy.scrollTo("end", anchor: .bottom) }
            }
        }
        .padding(Space.s4)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(p.surface)
        .overlay(Rectangle().strokeBorder(p.border, lineWidth: Space.hairline))
        .overlay(alignment: .leading) { Rectangle().fill(p.accent).frame(width: Space.strong) }
    }

    private func transcript(_ p: Palette, caretOn: Bool) -> Text {
        if state.liveText.isEmpty {
            let hint = Text(skeleton ? "" : "Говорите — текст появится здесь по мере разбора.")
                .foregroundColor(p.textMuted)
            return caret ? hint + Text(" ▌").foregroundColor(caretOn ? p.accent : .clear) : hint
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
        return caret ? text + Text(" ▌").foregroundColor(caretOn ? p.accent : .clear) : text
    }
}

// MARK: - панель истории справа

struct HistoryPanel: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions
    @State private var copied = false

    var body: some View {
        let p = state.palette
        VStack(spacing: 0) {
            HStack {
                Text("История").monoLabel(p.text)
                Spacer()
                Text("\(state.history.count)").monoLabel(p.textMuted)
            }
            .padding(.horizontal, Space.s4)
            .padding(.vertical, Space.s3)
            VKDivider(palette: p)
            live(p)
            if state.history.isEmpty {
                VKEmpty(title: "Диктовок ещё нет",
                        text: "Зажмите \(state.hotkey.label) и скажите первую фразу.", palette: p)
                    .padding(Space.s4)
                Spacer(minLength: 0)
            } else {
                ScrollView {
                    LazyVStack(spacing: 0) {
                        ForEach(Array(state.history.prefix(60).enumerated()), id: \.element.id) { i, e in
                            PanelRow(entry: e, first: i == 0 && isIdle, actions: actions)
                            VKDivider(palette: p)
                        }
                    }
                }
                .scrollIndicators(.never)
            }
            VKDivider(palette: p)
            footer(p)
        }
        .background(p.surface)
    }

    private var isIdle: Bool {
        switch state.phase {
        case .recording, .processing: return false
        default: return true
        }
    }

    @ViewBuilder
    private func live(_ p: Palette) -> some View {
        switch state.phase {
        case .recording:
            VStack(alignment: .leading, spacing: Space.s2) {
                Text("Сейчас").monoLabel(p.accentInk)
                Text(state.liveText.isEmpty ? "…" : state.liveText)
                    .font(Fonts.text(FontSize.fs2)).foregroundStyle(p.text).lineLimit(3)
            }
            .padding(.horizontal, Space.s4)
            .padding(.vertical, Space.s3)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(p.surface2)
            .overlay(alignment: .leading) { Rectangle().fill(p.accent).frame(width: Space.strong) }
            VKDivider(palette: p)
        case .processing:
            VStack(alignment: .leading, spacing: Space.s2) {
                Text("Готовится").monoLabel(p.textMuted)
                VKSkeleton(palette: p, height: 12)
                VKSkeleton(palette: p, height: 12, delay: 0.15).frame(maxWidth: 180)
            }
            .padding(.horizontal, Space.s4)
            .padding(.vertical, Space.s3)
            VKDivider(palette: p)
        default:
            EmptyView()
        }
    }

    @ViewBuilder
    private func footer(_ p: Palette) -> some View {
        if case .recording = state.phase {
            HStack {
                Text(state.micName).monoLabel(p.textMuted).lineLimit(1)
                Spacer()
            }
            .padding(.horizontal, Space.s4)
            .frame(height: 48)
        } else {
            HStack(spacing: Space.s2) {
                Button(copied ? "Скопировано" : "Копировать") {
                    guard let last = state.history.first(where: { !$0.failed }) else { return }
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(last.text, forType: .string)
                    copied = true
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) { copied = false }
                }
                .buttonStyle(VKButtonStyle(palette: p, kind: .secondary, size: .sm, fill: true))
                .disabled(state.history.isEmpty)
                Button("Открыть все") { state.tab = .history }
                    .buttonStyle(VKButtonStyle(palette: p, kind: .ghost, size: .sm, fill: true))
            }
            .padding(.horizontal, Space.s4)
            .padding(.vertical, Space.s3)
        }
    }

    static let time: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "HH:mm"
        return f
    }()
}

/// Запись в панели: свёрнута в три строки, клик - раскрыть. Текст не
/// выделяемый намеренно: выделяемый текст на macOS игнорирует lineLimit и
/// вылезал поверх соседних записей.
struct PanelRow: View {
    @EnvironmentObject var state: AppState
    let entry: Entry
    let first: Bool
    let actions: AppActions
    @State private var open = false
    @State private var hover = false

    var body: some View {
        let p = state.palette
        VStack(alignment: .leading, spacing: Space.s2) {
            HStack(spacing: Space.s2) {
                Text(HistoryPanel.time.string(from: entry.date)).monoLabel(p.textMuted)
                if entry.failed { VKBadge(text: "Не распознано", tone: .warning, palette: p) }
                Spacer()
                Text(wordsLabel(entry.words)).monoLabel(p.textMuted)
            }
            Text(entry.failed ? "Речь не распознана. Запись сохранена — её можно перераспознать." : entry.text)
                .font(Fonts.text(FontSize.fs2))
                .foregroundStyle(first || open ? p.text : p.textMuted)
                .lineSpacing(3)
                .lineLimit(open ? nil : 3)
                .frame(maxWidth: .infinity, alignment: .leading)
                .fixedSize(horizontal: false, vertical: true)
            if open {
                HStack(spacing: Space.s2) {
                    Button("Копировать") {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(entry.text, forType: .string)
                    }
                    .buttonStyle(VKButtonStyle(palette: p, kind: .secondary, size: .sm))
                    .disabled(entry.failed)
                    if entry.audio != nil {
                        Button(state.rerecognizing.contains(entry.id) ? "Распознаю…" : "Перераспознать") {
                            actions.rerecognize(entry)
                        }
                        .buttonStyle(VKButtonStyle(palette: p, kind: .ghost, size: .sm))
                        .disabled(state.rerecognizing.contains(entry.id))
                    }
                }
            } else if entry.words > 30 {
                Text("Ещё").monoLabel(hover ? p.accentInk : p.textMuted)
            }
        }
        .padding(.horizontal, Space.s4)
        .padding(.vertical, Space.s3)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(first ? p.surface2 : (hover ? p.surface2 : Color.clear))
        .overlay(alignment: .leading) {
            if first { Rectangle().fill(p.accent).frame(width: Space.strong) }
        }
        .clipped()
        .contentShape(Rectangle())
        .onTapGesture { withAnimation(Motion.base) { open.toggle() } }
        .onHover { hover = $0 }
        .animation(Motion.instant, value: hover)
    }
}
