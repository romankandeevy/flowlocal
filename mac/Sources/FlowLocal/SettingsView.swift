import AppKit
import Carbon.HIToolbox
import SwiftUI

// «Настройки» - последний раздел окна (⌘,). Четыре вкладки: Основные
// (клавиши, язык, вставка, микрофон), Капсула, Текст (чистка и замены),
// Система (тема, запуск, история, разрешения). Всё сохраняется сразу: каждое
// поле пишет прямо в AppState, а тот - в UserDefaults. Hub Settings
// по-прежнему может менять те же ключи (HubSync).
struct SettingsView: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions
    @AppStorage("settingsPane") private var paneRaw = SettingsPane.main.rawValue

    private var pane: SettingsPane { SettingsPane(rawValue: paneRaw) ?? .main }

    var body: some View {
        PageScroll {
            VStack(alignment: .leading, spacing: Space.s2) {
                PageTitle("Настройки")
                Text("Клавиши, вставка, капсула записи и чистка текста. Всё сохраняется сразу.")
                    .font(NLFont.ui(14.5))
                    .lineSpacing(3)
                    .foregroundStyle(NL.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            SegmentedChoice(
                options: SettingsPane.allCases.map { ($0, $0.title) },
                selection: Binding(get: { pane }, set: { paneRaw = $0.rawValue }),
                large: true)
            Group {
                switch pane {
                case .main: MainPane(actions: actions)
                case .capsule: CapsulePane()
                case .text: TextPane()
                case .system: SystemPane(actions: actions)
                }
            }
            // Смена вкладки без перехода: прежняя уходит сразу, иначе две
            // вкладки на миг лежат друг на друге.
            .id(pane)
            .transaction(value: pane) { $0.animation = nil }
        }
    }
}

enum SettingsPane: String, CaseIterable, Identifiable {
    case main, capsule, text, system

    var id: String { rawValue }
    var title: String {
        switch self {
        case .main: return "Основные"
        case .capsule: return "Капсула"
        case .text: return "Текст"
        case .system: return "Система"
        }
    }
}

// MARK: - общие кирпичики

/// Выбор из нескольких вариантов: подложка, выбранный вариант - карточкой,
/// которая переезжает под новый.
struct SegmentedChoice<T: Hashable>: View {
    let options: [(T, String)]
    @Binding var selection: T
    var large = false
    @Namespace private var thumb

    var body: some View {
        HStack(spacing: 1) {
            ForEach(options.indices, id: \.self) { i in
                let (value, title) = options[i]
                let selected = selection == value
                Button {
                    withMotion(Motion.base) { selection = value }
                } label: {
                    Text(title)
                        .font(NLFont.ui(large ? 13.5 : 13, selected ? .semibold : .medium))
                        .foregroundStyle(selected ? NL.textPrimary : NL.textSecondary)
                        .padding(.horizontal, large ? 16 : 12)
                        .frame(height: large ? 32 : 28)
                        .background {
                            if selected {
                                RoundedRectangle(cornerRadius: large ? 8 : 7, style: .continuous)
                                    .fill(NL.surface)
                                    .shadow(color: .black.opacity(0.06), radius: 1, y: 1)
                                    .overlay {
                                        RoundedRectangle(cornerRadius: large ? 8 : 7, style: .continuous)
                                            .strokeBorder(NL.border, lineWidth: 1)
                                    }
                                    .matchedGeometryEffect(id: "thumb", in: thumb)
                            }
                        }
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(selected ? .isSelected : [])
            }
        }
        .padding(large ? 3 : 2)
        .background(NL.subtle, in: RoundedRectangle(cornerRadius: large ? 11 : 9, style: .continuous))
        .fixedSize()
    }
}

/// Строка настройки: название и пояснение слева, управление справа.
struct SettingRow<Control: View>: View {
    let title: String
    var detail: String?
    @ViewBuilder var control: () -> Control

    var body: some View {
        HStack(alignment: .center, spacing: Space.s4) {
            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(NLFont.ui(14.5, .semibold))
                    .foregroundStyle(NL.textPrimary)
                if let detail {
                    Text(detail)
                        .font(NLFont.ui(12.5))
                        .foregroundStyle(NL.textTertiary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: Space.s4)
            control()
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 14)
        .frame(minHeight: 62)
    }
}

struct RowDivider: View {
    var body: some View { NL.borderSubtle.frame(height: 1) }
}

/// Группа: заголовок, карточка со строками и пояснение под ней.
private struct SettingsGroup<Content: View>: View {
    let title: String
    var footer: String?
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeading(title)
            VStack(spacing: 0, content: content)
                .nlCard(padding: 0)
            if let footer { FormFooter(footer) }
        }
    }
}

/// Однострочное поле в стиле приложения: в фокусе - кольцо акцента.
struct NLTextField: View {
    let prompt: String
    @Binding var text: String
    @FocusState private var focused: Bool

    var body: some View {
        TextField("", text: $text, prompt: Text(prompt).foregroundColor(NL.textPlaceholder))
            .textFieldStyle(.plain)
            .font(NLFont.ui(13.5))
            .foregroundStyle(NL.textPrimary)
            .focused($focused)
            .padding(.horizontal, 11)
            .frame(height: 32)
            .background(NL.surface, in: RoundedRectangle(cornerRadius: 9, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 9, style: .continuous)
                    .strokeBorder(focused ? NL.borderFocus : NL.borderStrong, lineWidth: 1)
            }
            .background {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(NL.ringFocus)
                    .padding(-3)
                    .opacity(focused ? 1 : 0)
            }
            .animation(Motion.base, value: focused)
    }
}

// MARK: - основные

private struct MainPane: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    var body: some View {
        HotkeysGroup(actions: actions)

        SettingsGroup(title: "Распознавание") {
            SettingRow(title: "Язык", detail: "«Авто» различает русский и английский по ходу речи.") {
                SegmentedChoice(options: LangMode.allCases.map { ($0, $0.title) }, selection: $state.langMode)
            }
        }

        SettingsGroup(title: "Вставка") {
            ToggleRow(title: "Вставлять текст в активное окно",
                      detail: "Иначе текст остаётся только в ленте.",
                      isOn: $state.insertAutomatically)
            if state.insertAutomatically {
                RowDivider()
                ToggleRow(title: "Пробел после текста",
                          detail: "Следующая диктовка не прилипнет к предыдущей.",
                          isOn: $state.addSpace)
                    .transition(.opacity)
                RowDivider()
                ToggleRow(title: "Оставлять текст в буфере обмена",
                          detail: "Иначе вернётся то, что было в буфере до диктовки.",
                          isOn: $state.keepInClipboard)
                    .transition(.opacity)
            }
        }
        .motion(Motion.moderate, value: state.insertAutomatically)

        SettingsGroup(title: "Микрофон") {
            SettingRow(title: "Источник", detail: "Микрофон слушает, только пока идёт запись.") {
                MicPicker()
            }
            RowDivider()
            ToggleRow(title: "Звук в начале и в конце записи",
                      detail: "Тихий сигнал, что запись пошла и закончилась.",
                      isOn: $state.sounds)
        }
    }
}

private struct MicPicker: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        Picker("", selection: $state.micUID) {
            Text("Как в системе").tag(String?.none)
            ForEach(state.micDevices) { d in
                Text(d.name).tag(Optional(d.uid))
            }
            if let uid = state.micUID, !state.micDevices.contains(where: { $0.uid == uid }) {
                Text("Микрофон не подключён").tag(Optional(uid))
            }
        }
        .pickerStyle(.menu)
        .labelsHidden()
        .fixedSize()
        .accessibilityLabel("Микрофон")
    }
}

// MARK: - сочетания клавиш

private struct HotkeysGroup: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions
    @State private var recording: HotkeyRole?
    @State private var monitor: Any?

    private static let off = HotkeyPreset(id: "off", keyCode: UInt32(kVK_Space), modifiers: 0, keys: [])

    var body: some View {
        SettingsGroup(title: "Сочетания клавиш",
               footer: "Работают в любом приложении. Esc во время записи — отмена. Нажмите на сочетание и введите новое; Esc отменяет ввод.") {
            row(.hold, detail: "Держите и говорите, отпустите — текст на месте.")
            RowDivider()
            row(.toggle, detail: "Нажмите, чтобы начать, и ещё раз, чтобы вставить.")
        }
        .motion(Motion.moderate, value: state.hotkeyIssues.count)
        .onDisappear { stopRecording() }
    }

    private func preset(_ role: HotkeyRole) -> HotkeyPreset { role == .hold ? state.hotkey : state.toggleHotkey }

    private func row(_ role: HotkeyRole, detail: String) -> some View {
        let current = preset(role)
        let other = preset(role == .hold ? .toggle : .hold)
        let isRecording = recording == role
        return VStack(alignment: .leading, spacing: 8) {
            SettingRow(title: role.title, detail: detail) {
                HStack(spacing: 6) {
                    Button { isRecording ? stopRecording() : startRecording(role) } label: {
                        Group {
                            if isRecording {
                                Text("Нажмите сочетание…")
                                    .font(NLFont.ui(13, .medium))
                                    .foregroundStyle(NL.textAccent)
                            } else if current.isEnabled {
                                TutorialKeys(keys: current.keys)
                            } else {
                                Text("Не задано")
                                    .font(NLFont.ui(13))
                                    .foregroundStyle(NL.textTertiary)
                            }
                        }
                        .padding(.horizontal, 8)
                        .frame(minHeight: 34)
                        .background(NL.surface, in: RoundedRectangle(cornerRadius: 9, style: .continuous))
                        .overlay {
                            RoundedRectangle(cornerRadius: 9, style: .continuous)
                                .strokeBorder(isRecording ? NL.borderFocus : NL.borderStrong, lineWidth: 1)
                        }
                        .background {
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
                                .fill(NL.ringFocus).padding(-3).opacity(isRecording ? 1 : 0)
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .animation(Motion.base, value: isRecording)
                    .accessibilityLabel("Сочетание «\(role.title)»")
                    .accessibilityHint("Нажмите, чтобы ввести новое")
                    // Убрать можно, пока второй способ остаётся: иначе диктовку
                    // не запустить с клавиатуры.
                    Button {
                        set(role, Self.off)
                    } label: {
                        Image(systemName: "xmark")
                    }
                    .nlIconButton()
                    .help("Убрать сочетание")
                    .accessibilityLabel("Убрать сочетание")
                    .opacity(current.isEnabled && other.isEnabled && !isRecording ? 1 : 0)
                    .allowsHitTesting(current.isEnabled && other.isEnabled && !isRecording)
                }
            }
            if let issue = state.hotkeyIssues[role] {
                Text(issue)
                    .font(NLFont.ui(12.5, .medium))
                    .foregroundStyle(NL.textWarning)
                    .padding(.horizontal, 18)
                    .padding(.bottom, 12)
                    .transition(.opacity)
            }
        }
    }

    private func set(_ role: HotkeyRole, _ preset: HotkeyPreset) {
        if role == .hold { state.hotkey = preset } else { state.toggleHotkey = preset }
        HubSync.announce()
    }

    /// Следующее нажатие с модификатором (или F-клавиша без него) - и есть новое сочетание.
    /// Пока ждём, свои сочетания не слушаем: иначе они бы и сработали.
    private func startRecording(_ role: HotkeyRole) {
        stopRecording()
        recording = role
        actions.unbindHotkeys()
        monitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
            if event.keyCode == UInt16(kVK_Escape) { stopRecording(); return nil }
            var names: [String] = []
            let f = event.modifierFlags
            if f.contains(.control) { names.append("control") }
            if f.contains(.option) { names.append("option") }
            if f.contains(.shift) { names.append("shift") }
            if f.contains(.command) { names.append("command") }
            let code = Int(event.keyCode)
            let name = HotkeyPreset.keyName(code)
            let isFunctionKey = name.hasPrefix("F") && Int(name.dropFirst()) != nil
            guard !names.isEmpty || isFunctionKey else { NSSound.beep(); return nil }
            let preset = HotkeyPreset(keyCode: code, modifierNames: names.isEmpty ? ["none"] : names)
            if HotkeyPreset.isSystemCombo(keyCode: code, mods: preset.modifiers) { NSSound.beep(); return nil }
            stopRecording()
            set(role, preset)
            return nil
        }
    }

    private func stopRecording() {
        if let monitor { NSEvent.removeMonitor(monitor) }
        monitor = nil
        if recording != nil { actions.bindHotkeys() }
        recording = nil
    }
}

// MARK: - капсула

private struct CapsulePane: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeading("Так она выглядит")
            CapsulePreview()
        }

        SettingsGroup(title: "Капсула записи",
               footer: "Чёрная плашка с временем записи и бегущими полосками. Выключите — во время записи на экране ничего не появится, а о записи скажут значок в строке меню и звук.") {
            ToggleRow(title: "Показывать капсулу",
                      detail: "Поверх всех окон, пока идёт запись.",
                      isOn: $state.showPill)
            RowDivider()
            SettingRow(title: "Место на экране") {
                SegmentedChoice(options: PillPosition.allCases.map { ($0, $0.title) }, selection: $state.pillPosition)
            }
            .disabled(!state.showPill)
            .opacity(state.showPill ? 1 : 0.4)
        }
    }
}

/// Мини-экран: на нём капсула там, где её покажут.
private struct CapsulePreview: View {
    @EnvironmentObject var state: AppState
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        let top = state.pillPosition == .top
        ZStack {
            VStack(alignment: .leading, spacing: 9) {
                Text("Текстовый редактор")
                    .font(NLFont.ui(13))
                    .foregroundStyle(NL.textQuaternary)
                    .padding(.bottom, 4)
                ForEach([0.82, 0.64, 0.74], id: \.self) { w in
                    GeometryReader { geo in
                        Capsule().fill(NL.borderSubtle).frame(width: geo.size.width * w, height: 8)
                    }
                    .frame(height: 8)
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 26)
            .padding(.top, 40)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)

            if state.showPill {
                PillCapsule {
                    HStack(spacing: 10) {
                        Text("0:07")
                            .font(.system(size: 13, weight: .semibold).monospacedDigit())
                            .foregroundStyle(Pill.text)
                        DemoBars(animated: !reduceMotion)
                    }
                }
                .padding(.vertical, top ? 30 : 16)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: top ? .top : .bottom)
                .transition(.opacity.combined(with: .scale(scale: 0.9)))
            } else {
                Text("Капсула выключена")
                    .font(NLFont.ui(13))
                    .foregroundStyle(NL.textTertiary)
                    .transition(.opacity)
            }
        }
        .frame(height: 200)
        .frame(maxWidth: .infinity)
        .background(NL.subtle, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(alignment: .top) {
            NL.borderSubtle.frame(height: 22).clipShape(UnevenRoundedRectangle(topLeadingRadius: 14, topTrailingRadius: 14))
        }
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay { RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(NL.border, lineWidth: 1) }
        .motion(Motion.pop, value: state.showPill)
        .motion(Motion.moderate, value: state.pillPosition)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(state.showPill ? "Предпросмотр: капсула \(state.pillPosition == .top ? "вверху" : "внизу") экрана" : "Предпросмотр: капсула выключена")
    }
}

/// Волна для предпросмотра: те же полоски, что в капсуле, но без микрофона.
private struct DemoBars: View {
    var animated: Bool
    private let count = 14

    var body: some View {
        TimelineView(.animation(minimumInterval: animated ? 1.0 / 30 : 3600)) { context in
            let t = animated ? context.date.timeIntervalSinceReferenceDate : 0
            Canvas { ctx, size in
                let bar: CGFloat = 2.5, gap: CGFloat = 2.5
                for i in 0..<count {
                    let wave = (sin(t * 5 - Double(i) * 0.55) + 1) / 2
                    let body = (sin(Double(i) * 0.9) + 1) / 2
                    let v = 0.14 + 0.86 * (0.35 * wave + 0.65 * body * (0.5 + 0.5 * wave))
                    let h = max(bar, size.height * CGFloat(v))
                    let rect = CGRect(x: CGFloat(i) * (bar + gap), y: (size.height - h) / 2, width: bar, height: h)
                    ctx.fill(Path(roundedRect: rect, cornerRadius: bar / 2), with: .color(Pill.text))
                }
            }
        }
        .frame(width: CGFloat(count) * 2.5 + CGFloat(count - 1) * 2.5, height: 18)
        .mask {
            LinearGradient(stops: [.init(color: .clear, location: 0), .init(color: .black, location: 0.3)],
                           startPoint: .leading, endPoint: .trailing)
        }
    }
}

// MARK: - текст

private struct TextPane: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        SettingsGroup(title: "Чистка текста") {
            SettingRow(title: "Слова-паразиты") {
                SegmentedChoice(options: CleanupLevel.allCases.map { ($0, $0.title) }, selection: $state.cleanupLevel)
            }
            Text(state.cleanupLevel.detail)
                .font(NLFont.ui(12.5))
                .foregroundStyle(NL.textTertiary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 18)
                .padding(.bottom, 14)
                .fixedSize(horizontal: false, vertical: true)
                .contentTransition(.opacity)
                .motion(Motion.base, value: state.cleanupLevel)
            RowDivider()
            ToggleRow(title: "Убирать повторы", detail: "«я я хотел» → «я хотел»", isOn: $state.removeRepeats)
            RowDivider()
            ToggleRow(title: "Заглавная в начале фразы",
                      detail: "Первое слово диктовки пишется с большой буквы.",
                      isOn: $state.capitalize)
            RowDivider()
            ToggleRow(title: "Точка в конце",
                      detail: "Выключите для чатов: сообщения без точки.",
                      isOn: $state.trailingPeriod)
            RowDivider()
            VStack(alignment: .leading, spacing: 8) {
                Text("Свои слова-паразиты")
                    .font(NLFont.ui(14.5, .semibold))
                    .foregroundStyle(NL.textPrimary)
                Text("Через запятую. Убираются везде, где стоят отдельным словом.")
                    .font(NLFont.ui(12.5))
                    .foregroundStyle(NL.textTertiary)
                NLTextField(prompt: "слышь, прикинь, это самое", text: $state.customFillers)
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 14)
        }

        SettingsGroup(title: "Замены",
               footer: "По целым словам, без учёта регистра. Например, «флоу локал» → «Flow Local». Пустые пары не сохраняются.") {
            ReplacementsEditor()
                .padding(.horizontal, 18)
                .padding(.vertical, 14)
        }

        SettingsGroup(title: "Что получится") {
            CleanupSample()
                .padding(.horizontal, 18)
                .padding(.vertical, 14)
        }
    }
}

/// Пары «было → стало». Правятся здесь целиком; в настройки уходят только
/// заполненные.
private struct ReplacementsEditor: View {
    @EnvironmentObject var state: AppState
    @State private var rows: [Replacement] = []

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach($rows) { $row in
                HStack(spacing: 8) {
                    NLTextField(prompt: "Было", text: $row.from)
                    Image(systemName: "arrow.right")
                        .font(.system(size: 11))
                        .foregroundStyle(NL.iconTertiary)
                    NLTextField(prompt: "Стало", text: $row.to)
                    Button { rows.removeAll { $0.id == row.id } } label: {
                        Image(systemName: "xmark")
                    }
                    .nlIconButton()
                    .help("Удалить замену")
                    .accessibilityLabel("Удалить замену")
                }
                .transition(.opacity)
            }
            if rows.isEmpty {
                Text("Замен пока нет.")
                    .font(NLFont.ui(13))
                    .foregroundStyle(NL.textTertiary)
            }
            Button {
                withMotion(Motion.base) { rows.append(Replacement(from: "", to: "")) }
            } label: {
                Label("Добавить замену", systemImage: "plus")
            }
            .nlButton()
            .padding(.top, 2)
        }
        .motion(Motion.moderate, value: rows.map(\.id))
        .onAppear { rows = state.replacements }
        .onChange(of: rows) { _, new in
            let filled = new.filter {
                !$0.from.trimmingCharacters(in: .whitespaces).isEmpty && !$0.to.isEmpty
            }
            if Replacement.pairs(filled) != Replacement.pairs(state.replacements) { state.replacements = filled }
        }
        .onChange(of: state.replacements) { _, new in
            // Заменили снаружи (Hub Settings) - показываем то, что сохранено.
            let filled = rows.filter {
                !$0.from.trimmingCharacters(in: .whitespaces).isEmpty && !$0.to.isEmpty
            }
            if Replacement.pairs(filled) != Replacement.pairs(new) { rows = new }
        }
    }
}

/// Пример на настоящей чистке: что сказано и что напишется при текущих настройках.
private struct CleanupSample: View {
    @EnvironmentObject var state: AppState
    private let raw = "ну я я хотел типа э-э показать код на гитхаб в принципе"

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            line("Сказано", raw, NL.textSecondary)
            line("Напишется", state.cleaned(raw), NL.textPrimary)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(NL.canvas, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
        .motion(Motion.base, value: state.cleaned(raw))
    }

    private func line(_ label: String, _ text: String, _ color: Color) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label)
                .nlType(.overline)
                .foregroundStyle(NL.textTertiary)
            Text(text.isEmpty ? "—" : text)
                .font(NLFont.ui(14, label == "Напишется" ? .medium : .regular))
                .lineSpacing(3)
                .foregroundStyle(color)
                .fixedSize(horizontal: false, vertical: true)
                .contentTransition(.opacity)
        }
    }
}

// MARK: - система

private struct SystemPane: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions
    @State private var recordings = ""
    @State private var pendingDays: Int?

    var body: some View {
        SettingsGroup(title: "Оформление") {
            SettingRow(title: "Тема", detail: "Окно FlowLocal. Капсула записи всегда чёрная.") {
                SegmentedChoice(options: AppAppearance.allCases.map { ($0, $0.title) }, selection: $state.appearance)
            }
        }

        SettingsGroup(title: "Запуск и значки",
               footer: "Хотя бы один значок остаётся: без обоих до окна FlowLocal не добраться. Окно открывается и повторным запуском из Spotlight.") {
            ToggleRow(title: "Открывать при входе в систему",
                      detail: "Чтобы диктовка работала сразу после включения Мака.",
                      isOn: Binding(get: { state.launchAtLogin }, set: { actions.setLaunchAtLogin($0) }))
            RowDivider()
            ToggleRow(title: "Значок в строке меню",
                      detail: "Состояние записи и быстрый старт диктовки.",
                      isOn: $state.showMenuBarIcon)
                .disabled(state.showMenuBarIcon && !state.showInDock)
            RowDivider()
            ToggleRow(title: "Значок в Доке",
                      detail: "Без него FlowLocal живёт только в строке меню.",
                      isOn: $state.showInDock)
                .disabled(state.showInDock && !state.showMenuBarIcon)
        }

        SettingsGroup(title: "История") {
            ToggleRow(title: "Сохранять звук диктовок",
                      detail: "Чтобы прослушать и распознать заново. Около 2 МБ в минуту.",
                      isOn: $state.saveAudio)
            RowDivider()
            SettingRow(title: "Хранить диктовки", detail: "Старые удаляются вместе со звуком.") {
                SegmentedChoice(
                    options: [(7, "Неделю"), (30, "Месяц"), (90, "3 месяца"), (0, "Всегда")],
                    selection: Binding(get: { state.historyDays }, set: chooseDays))
            }
            RowDivider()
            SettingRow(title: "Папка записей", detail: recordings) {
                Button(action: actions.openRecordings) {
                    Label("Показать в Finder", systemImage: "folder")
                }
                .nlButton()
            }
            RowDivider()
            SettingRow(title: "Журнал", detail: "~/Library/Logs/FlowLocal.log") {
                Button("Показать журнал", action: actions.openLog)
                    .nlButton()
            }
        }
        .onAppear { recordings = Self.recordingsSummary() }
        .confirmationDialog("Удалить старые диктовки?",
                            isPresented: Binding(get: { pendingDays != nil }, set: { if !$0 { pendingDays = nil } }),
                            titleVisibility: .visible) {
            if let days = pendingDays {
                Button("Удалить \(Self.count(oldEntries(days)))", role: .destructive) {
                    state.historyDays = days
                    pendingDays = nil
                }
            }
            Button("Отмена", role: .cancel) { pendingDays = nil }
        } message: {
            Text("Они пропадут из истории вместе со звуком. Вернуть их будет нельзя.")
        }

        SettingsGroup(title: "Разрешения",
               footer: "Если FlowLocal уже есть в списке, а доступ не работает, удалите его из списка и добавьте снова.") {
            SettingRow(title: "Микрофон", detail: "Без него диктовка выключена.") {
                HStack(spacing: 10) {
                    NLBadge(title: state.micGranted ? "Выдано" : "Не выдано", kind: state.micGranted ? .success : .warning)
                    Button(state.micGranted ? "Открыть" : "Разрешить") { openMicrophoneAccess(state) }
                        .nlButton()
                }
            }
            RowDivider()
            SettingRow(title: "Универсальный доступ", detail: "Без него текст остаётся в буфере обмена.") {
                HStack(spacing: 10) {
                    NLBadge(title: state.axTrusted ? "Выдано" : "Не выдано", kind: state.axTrusted ? .success : .warning)
                    Button(state.axTrusted ? "Открыть" : "Разрешить") {
                        state.axTrusted ? Inserter.openAccessibilitySettings() : openAccessibilityAccess()
                    }
                    .nlButton()
                }
            }
        }

        SettingsGroup(title: "О программе") {
            SettingRow(title: "FlowLocal \(AppInfo.version)",
                       detail: "Распознавание работает на этом Маке, без интернета.") {
                HStack(spacing: 8) {
                    Button("Пройти обучение заново", action: actions.showTutorial)
                        .nlButton()
                    Button("Справка") { NSWorkspace.shared.open(AppInfo.helpURL) }
                        .nlButton(.ghost)
                }
            }
        }
    }

    // MARK: история

    private func oldEntries(_ days: Int) -> Int {
        guard days > 0, let since = Calendar.current.date(byAdding: .day, value: -days, to: Date()) else { return 0 }
        return state.history.filter { $0.date < since }.count
    }

    /// Короче срок - сначала спросить, если что-то уйдёт; иначе применить сразу.
    private func chooseDays(_ days: Int) {
        if oldEntries(days) > 0 { pendingDays = days } else { state.historyDays = days }
    }

    private static func count(_ n: Int) -> String {
        let word = n % 10 == 1 && n % 100 != 11 ? "диктовку"
            : (2...4).contains(n % 10) && !(12...14).contains(n % 100) ? "диктовки" : "диктовок"
        return "\(n) \(word)"
    }

    /// «12 файлов · 24 МБ».
    private static func recordingsSummary() -> String {
        let files = (try? FileManager.default.contentsOfDirectory(at: Paths.recordings,
                                                                 includingPropertiesForKeys: [.fileSizeKey])) ?? []
        let wav = files.filter { $0.pathExtension == "wav" }
        let bytes = wav.reduce(Int64(0)) { sum, url in
            sum + Int64((try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0)
        }
        let n = wav.count
        let word = n % 10 == 1 && n % 100 != 11 ? "файл"
            : (2...4).contains(n % 10) && !(12...14).contains(n % 100) ? "файла" : "файлов"
        return "\(n) \(word) · \(ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file))"
    }
}
