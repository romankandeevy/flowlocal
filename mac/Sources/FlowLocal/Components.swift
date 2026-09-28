import AppKit
import SwiftUI

// Примитивы Northline для SwiftUI: кнопки, переключатель, выпадающий
// выбор, алерт, бейдж, пустое состояние, заголовок страницы, строки
// «ключ - значение», полоса показателей. Плюс своё для диктовки: волна,
// сочетания клавиш, действия над диктовками.

// MARK: - кнопки

/// .btn: primary - одно главное действие на экран, secondary - остальное,
/// ghost - второстепенное и иконки, danger - разрушительное. Состояния
/// меняют только фон и границу.
struct NLButtonStyle: ButtonStyle {
    enum Kind { case primary, secondary, ghost, danger }
    enum Scale { case sm, md }

    var kind: Kind = .secondary
    var scale: Scale = .md
    var iconOnly = false

    func makeBody(configuration: Configuration) -> some View {
        NLButtonBody(configuration: configuration, kind: kind, scale: scale, iconOnly: iconOnly)
    }
}

private struct NLButtonBody: View {
    let configuration: ButtonStyleConfiguration
    let kind: NLButtonStyle.Kind
    let scale: NLButtonStyle.Scale
    let iconOnly: Bool
    @Environment(\.isEnabled) private var enabled
    @State private var hover = false

    var body: some View {
        let height = scale == .sm ? Size.controlSm : Size.controlMd
        let radius = scale == .sm ? Radius.sm : Radius.md
        let shape = RoundedRectangle(cornerRadius: radius, style: .continuous)
        configuration.label
            .labelStyle(NLButtonLabelStyle(iconOnly: iconOnly))
            .nlType(scale == .sm ? .labelSm : .label)
            .lineLimit(1)
            .foregroundStyle(foreground)
            .padding(.horizontal, iconOnly ? 0 : (scale == .sm ? Space.s2 : Space.s3))
            .frame(minWidth: iconOnly ? height : nil)
            .frame(height: height)
            .background(background, in: shape)
            .overlay { shape.strokeBorder(border, lineWidth: 1) }
            .shadow(color: kind == .secondary && enabled ? .black.opacity(0.04) : .clear, radius: 1, y: 1)
            .contentShape(shape)
            .onHover { hover = $0 && enabled }
            .animation(Motion.fast, value: hover)
            .animation(Motion.fast, value: configuration.isPressed)
    }

    private var pressed: Bool { configuration.isPressed && enabled }

    private var background: Color {
        guard enabled else { return kind == .ghost ? .clear : NL.disabled }
        switch kind {
        case .primary: return pressed ? NL.accentActive : hover ? NL.accentHover : NL.accent
        case .danger: return pressed ? NL.dangerActive : hover ? NL.dangerHover : NL.danger
        case .secondary: return pressed ? NL.active : hover ? NL.hover : NL.surface
        case .ghost: return pressed ? NL.active : hover ? NL.hover : .clear
        }
    }

    private var foreground: Color {
        guard enabled else { return NL.textDisabled }
        switch kind {
        case .primary, .danger: return NL.textOnAccent
        case .secondary: return NL.textPrimary
        case .ghost: return iconOnly ? NL.iconSecondary : NL.textPrimary
        }
    }

    private var border: Color {
        guard kind == .secondary else { return .clear }
        if !enabled { return NL.borderSubtle }
        return hover ? NL.borderHover : NL.border
    }
}

/// Иконка 16pt и подпись через 6pt; у кнопки-иконки подпись уходит в
/// доступность.
private struct NLButtonLabelStyle: LabelStyle {
    let iconOnly: Bool

    func makeBody(configuration: Configuration) -> some View {
        if iconOnly {
            configuration.icon
                .font(.system(size: 13, weight: .regular))
                .frame(width: Size.iconSm, height: Size.iconSm)
        } else {
            HStack(spacing: Space.s1_5) {
                configuration.icon.font(.system(size: 12, weight: .regular))
                configuration.title
            }
        }
    }
}

extension View {
    func nlButton(_ kind: NLButtonStyle.Kind = .secondary, _ scale: NLButtonStyle.Scale = .md) -> some View {
        buttonStyle(NLButtonStyle(kind: kind, scale: scale))
    }

    func nlIconButton(_ scale: NLButtonStyle.Scale = .sm) -> some View {
        buttonStyle(NLButtonStyle(kind: .ghost, scale: scale, iconOnly: true))
    }
}

/// .btn--link: текст-ссылка акцентного цвета.
struct NLLinkButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        LinkBody(configuration: configuration)
    }

    private struct LinkBody: View {
        let configuration: ButtonStyleConfiguration
        @State private var hover = false
        var body: some View {
            configuration.label
                .nlType(.label)
                .foregroundStyle(NL.textAccent)
                .underline(hover)
                .contentShape(Rectangle())
                .onHover { hover = $0 }
        }
    }
}

// MARK: - текст и структура

/// .page-header: заголовок 20/600, описание 13 вторичным, справа действия,
/// под шапкой - линия. Одна шапка на экран, без надзаголовков.
struct PageHeader<Actions: View>: View {
    let title: String
    let description: String
    @ViewBuilder var actions: () -> Actions

    var body: some View {
        HStack(alignment: .top, spacing: Space.s4) {
            VStack(alignment: .leading, spacing: Space.s1) {
                Text(title)
                    .nlType(.heading)
                    .foregroundStyle(NL.textPrimary)
                Text(description)
                    .nlType(.bodySm)
                    .foregroundStyle(NL.textSecondary)
                    .frame(maxWidth: Space.contentMax, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
            HStack(spacing: Space.s2) { actions() }
        }
        .padding(.bottom, Space.s4)
        .overlay(alignment: .bottom) { NL.border.frame(height: 1) }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

extension PageHeader where Actions == EmptyView {
    init(title: String, description: String) {
        self.init(title: title, description: description) { EmptyView() }
    }
}

/// Заголовок группы над карточкой или списком - heading-sm, справа - одно
/// тихое действие.
struct SectionTitle<Trailing: View>: View {
    let title: String
    @ViewBuilder var trailing: () -> Trailing

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(title)
                .nlType(.headingSm)
                .foregroundStyle(NL.textPrimary)
            Spacer(minLength: Space.s2)
            trailing()
        }
    }
}

extension SectionTitle where Trailing == EmptyView {
    init(_ title: String) { self.init(title: title) { EmptyView() } }
}

/// .kv-row: ключ третичным, значение - основным, цифры моноширинные.
struct KVRow: View {
    let key: String
    let value: String
    var last = false

    var body: some View {
        HStack {
            Text(key)
                .nlType(.bodySm)
                .foregroundStyle(NL.textTertiary)
            Spacer(minLength: Space.s4)
            Text(value)
                .nlType(.bodySm)
                .monospacedDigit()
                .foregroundStyle(NL.textPrimary)
                .multilineTextAlignment(.trailing)
        }
        .padding(.vertical, Space.s2)
        .overlay(alignment: .bottom) {
            if !last { NL.borderSubtle.frame(height: 1) }
        }
    }
}

/// Пояснение под карточкой: caption третичным, от одного левого края.
struct FormFooter: View {
    let text: String
    init(_ text: String) { self.text = text }

    var body: some View {
        Text(text)
            .nlType(.caption)
            .foregroundStyle(NL.textTertiary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .fixedSize(horizontal: false, vertical: true)
    }
}

// MARK: - алерт, бейдж, пустое состояние

/// .alert: подложка -subtle, иконка и заголовок цветом состояния, текст
/// вторичным. На экране - не больше одного тонированного блока.
struct NLAlert: View {
    enum Kind { case info, warning, danger }

    let kind: Kind
    let title: String
    let message: String
    var actionTitle: String?
    var action: (() -> Void)?

    var body: some View {
        HStack(alignment: .top, spacing: Space.s2) {
            Image(systemName: icon)
                .font(.system(size: 13))
                .foregroundStyle(tone)
                .frame(width: Size.iconSm, height: 19.5)
            VStack(alignment: .leading, spacing: Space.s0_5) {
                Text(title)
                    .nlType(.label)
                    .foregroundStyle(tone)
                    .padding(.top, 2)
                Text(message)
                    .nlType(.bodySm)
                    .foregroundStyle(NL.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: Space.s3)
            if let actionTitle, let action {
                Button(actionTitle, action: action)
                    .nlButton(.secondary, .sm)
            }
        }
        .padding(.vertical, Space.s3)
        .padding(.horizontal, Space.s4)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(fill, in: RoundedRectangle(cornerRadius: Radius.lg, style: .continuous))
        .overlay {
            if kind == .info {
                RoundedRectangle(cornerRadius: Radius.lg, style: .continuous)
                    .strokeBorder(NL.borderSubtle, lineWidth: 1)
            }
        }
    }

    private var icon: String {
        switch kind {
        case .info: return "info.circle"
        case .warning: return "exclamationmark.triangle"
        case .danger: return "exclamationmark.octagon"
        }
    }

    private var tone: Color {
        switch kind {
        case .info: return NL.textInfo
        case .warning: return NL.textWarning
        case .danger: return NL.textDanger
        }
    }

    private var fill: Color {
        switch kind {
        case .info: return NL.infoSubtle
        case .warning: return NL.warningSubtle
        case .danger: return NL.dangerSubtle
        }
    }
}

/// .badge: капсула 20pt, label-sm. Только для исключительного состояния.
struct NLBadge: View {
    enum Kind { case neutral, success, warning, danger }
    let title: String
    var kind: Kind = .neutral

    var body: some View {
        HStack(spacing: Space.s1) {
            Circle().fill(foreground).frame(width: 6, height: 6)
            Text(title)
        }
        .nlType(.labelSm)
        .foregroundStyle(foreground)
        .padding(.horizontal, Space.s2)
        .frame(height: Size.control2xs)
        .background(background, in: Capsule())
    }

    private var foreground: Color {
        switch kind {
        case .neutral: return NL.textSecondary
        case .success: return NL.textSuccess
        case .warning: return NL.textWarning
        case .danger: return NL.textDanger
        }
    }

    private var background: Color {
        switch kind {
        case .neutral: return NL.subtle
        case .success: return NL.successSubtle
        case .warning: return NL.warningSubtle
        case .danger: return NL.dangerSubtle
        }
    }
}

/// .empty-state: иконка 32 третичным, заголовок 16/600, одно предложение и
/// одно действие. По центру - единственное место, где текст центрируется.
struct NLEmptyState<Action: View>: View {
    let symbol: String
    let title: String
    let message: String
    @ViewBuilder var action: () -> Action

    var body: some View {
        VStack(spacing: Space.s2) {
            Image(systemName: symbol)
                .font(.system(size: 26, weight: .light))
                .foregroundStyle(NL.iconTertiary)
                .frame(width: Size.iconXl, height: Size.iconXl)
                .padding(.bottom, Space.s2)
            Text(title)
                .nlType(.headingSm)
                .foregroundStyle(NL.textPrimary)
            Text(message)
                .nlType(.bodySm)
                .foregroundStyle(NL.textSecondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 320)
                .fixedSize(horizontal: false, vertical: true)
            action().padding(.top, Space.s2)
        }
        .padding(.vertical, Space.s12)
        .padding(.horizontal, Space.s6)
        .frame(maxWidth: .infinity)
    }
}

extension NLEmptyState where Action == EmptyView {
    init(symbol: String, title: String, message: String) {
        self.init(symbol: symbol, title: title, message: message) { EmptyView() }
    }
}

// MARK: - показатели

/// Показатели одной полосой: один регион с границей, внутри - деление
/// линиями, а не карточка на каждое число.
struct StatStrip: View {
    struct Item: Identifiable {
        let label: String
        let value: String
        var id: String { label }
    }

    let items: [Item]

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(items.enumerated()), id: \.element.id) { index, item in
                VStack(alignment: .leading, spacing: Space.s1) {
                    Text(item.label)
                        .nlType(.caption)
                        .foregroundStyle(NL.textTertiary)
                    Text(item.value)
                        .nlType(.headingLg)
                        .monospacedDigit()
                        .foregroundStyle(NL.textPrimary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, Space.insetLg)
                .padding(.vertical, Space.insetMd)
                .overlay(alignment: .leading) {
                    if index > 0 { NL.borderSubtle.frame(width: 1) }
                }
                .accessibilityElement(children: .combine)
            }
        }
        .nlCard(padding: 0)
    }
}

// MARK: - волна

/// Волна уровня: капсулы от центра, свежий звук справа, старый гаснет к
/// левому краю. Цвет - нейтральный: волна - данные, а не украшение.
struct Waveform: View {
    let levels: [Float]
    var color: Color = NL.iconSecondary
    var count = 48
    var barWidth: CGFloat = 3
    var spacing: CGFloat = 3
    var height: CGFloat = 64
    var floor: CGFloat = 0.06
    var fade = true

    var body: some View {
        let tail = Array(levels.suffix(count))
        let values = Array(repeating: Float(0), count: max(0, count - tail.count)) + tail
        HStack(alignment: .center, spacing: spacing) {
            ForEach(values.indices, id: \.self) { i in
                Capsule()
                    .fill(color)
                    .frame(width: barWidth, height: max(barWidth, height * max(floor, CGFloat(values[i]))))
            }
        }
        .frame(height: height)
        .mask {
            if fade {
                LinearGradient(stops: [.init(color: .clear, location: 0), .init(color: .black, location: 0.25)],
                               startPoint: .leading, endPoint: .trailing)
            } else {
                Color.black
            }
        }
        // Без анимации высоты: волна - бегущая лента, каждый кадр столбики
        // сдвигаются на место соседа. Анимация тянула каждый от чужой высоты
        // к новой - и волна прыгала вверх-вниз вразнобой вместо того, чтобы течь.
        .accessibilityHidden(true)
    }
}

/// Волна, которая сама слушает уровень микрофона: перерисовывается только
/// она, а не всё окно.
struct LiveWaveform: View {
    @ObservedObject private var meter = LevelStore.shared
    var color: Color = NL.iconSecondary
    var count = 48
    var barWidth: CGFloat = 3
    var spacing: CGFloat = 3
    var height: CGFloat = 64

    var body: some View {
        Waveform(levels: meter.levels, color: color, count: count, barWidth: barWidth,
                 spacing: spacing, height: height)
    }
}

// MARK: - сочетания клавиш

/// Сочетание знаками macOS: ⌃⇧Пробел.
struct ShortcutText: View {
    let preset: HotkeyPreset

    var body: some View {
        Text(preset.label)
            .accessibilityLabel(preset.keys.map(KeyGlyph.word).joined(separator: " "))
    }
}

/// Сочетание моноширинным в тихой подложке - как значение, а не кнопка.
struct ShortcutValue: View {
    let preset: HotkeyPreset

    var body: some View {
        ShortcutText(preset: preset)
            .font(.system(size: 12, weight: .medium, design: .monospaced))
            .foregroundStyle(NL.textPrimary)
            .padding(.horizontal, Space.s2)
            .frame(height: 22)
            .background(NL.subtle, in: RoundedRectangle(cornerRadius: Radius.xs, style: .continuous))
    }
}

// MARK: - состояние

/// Состояние словом и знаком: цвет не единственный носитель смысла.
struct StatusLabel: View {
    enum Kind { case ready, busy, caution, failure }

    let title: String
    let kind: Kind

    var body: some View {
        switch kind {
        case .ready: NLBadge(title: title, kind: .success)
        case .caution: NLBadge(title: title, kind: .warning)
        case .failure: NLBadge(title: title, kind: .danger)
        case .busy:
            HStack(spacing: Space.s1_5) {
                ProgressView().controlSize(.mini)
                Text(title)
            }
            .nlType(.labelSm)
            .foregroundStyle(NL.textSecondary)
        }
    }
}

// MARK: - диктовки

/// Текст диктовки; нераспознанная - предупреждением.
struct EntryText: View {
    let entry: Entry
    var lines: Int?

    var body: some View {
        if entry.failed {
            HStack(spacing: Space.s1_5) {
                Image(systemName: "exclamationmark.triangle")
                    .foregroundStyle(NL.textWarning)
                Text("Речь не распознана").foregroundStyle(NL.textSecondary)
            }
        } else {
            Text(entry.text)
                .foregroundStyle(NL.textPrimary)
                .lineLimit(lines)
        }
    }
}

/// Действия над диктовками - одни и те же в контекстном меню и в меню
/// «Диктовка». В строке меню «Скопировать» и «Удалить» живут в «Правке»
/// (⌘C, ⌫), поэтому там их второй раз нет.
struct EntryCommands: View {
    @ObservedObject var state: AppState
    let entries: [Entry]
    let actions: AppActions
    var undo: UndoManager?
    var editing = true

    var body: some View {
        let one = entries.count == 1 ? entries.first : nil
        let playable = one.map { AudioStore.exists($0.audio) } ?? false
        let recorded = entries.filter { AudioStore.exists($0.audio) }
        Button("Вставить в активное окно") { if let one { actions.paste(one) } }
            .disabled(one == nil || one?.failed == true)
        if editing {
            Button("Скопировать") { Clipboard.copy(entries) }
                .disabled(!entries.contains { !$0.failed })
        }
        Divider()
        Button(one != nil && state.playing == one?.id ? "Остановить воспроизведение" : "Прослушать") {
            if let one { actions.play(one) }
        }
        .disabled(!playable)
        Button("Распознать заново") { recorded.forEach(actions.rerecognize) }
            .disabled(recorded.isEmpty)
        if editing {
            Divider()
            Button("Удалить") { state.delete(Set(entries.map(\.id)), undo: undo) }
                .disabled(entries.isEmpty)
        }
    }
}

enum Clipboard {
    /// Текст диктовок в буфер обмена; несколько - через пустую строку.
    static func copy(_ entries: [Entry]) {
        let text = entries.filter { !$0.failed }.map(\.text).joined(separator: "\n\n")
        guard !text.isEmpty else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
    }
}
