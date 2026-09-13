import AppKit
import SwiftUI

// Примитивы Apple System Dark. Где у macOS есть свой контрол - берём его
// (переключатель, флажок, всплывающее меню, индикатор): он и выглядит, и
// ведёт себя как в System Settings. Своё рисуем только там, где системного
// нет: кнопки нужной высоты, сегменты, клавиши, волна, островок.

private let P = Palette.dark

// MARK: - кнопки

enum FLButtonKind { case primary, secondary, plain, destructive }
enum FLButtonSize { case small, regular }

/// Кнопка 22 / 28 pt, радиус 6, SF Pro 600. Наведение - ровный шаг
/// заливки, нажатие - заливка плотнее и кнопка на 3 % меньше.
struct FLButtonStyle: ButtonStyle {
    var kind: FLButtonKind = .secondary
    var size: FLButtonSize = .regular
    var fill = false

    func makeBody(configuration: Configuration) -> some View {
        FLButtonBody(configuration: configuration, kind: kind, size: size, fill: fill)
    }
}

private struct FLButtonBody: View {
    let configuration: ButtonStyle.Configuration
    let kind: FLButtonKind
    let size: FLButtonSize
    let fill: Bool
    @State private var hover = false
    @Environment(\.isEnabled) private var enabled

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: Radius.control, style: .continuous)
        configuration.label
            .labelStyle(FLLabelStyle())
            .font(.system(size: size == .small ? 12 : 13, weight: .semibold))
            .lineLimit(1)
            .padding(.horizontal, size == .small ? 10 : 14)
            .frame(maxWidth: fill ? .infinity : nil)
            .frame(height: size == .small ? Metric.buttonSmall : Metric.button)
            .foregroundStyle(foreground)
            .background {
                ZStack {
                    shape.fill(base)
                    shape.fill(Color.white.opacity(highlight))
                }
                .brightness(pressed && kind == .primary ? -0.08 : 0)
            }
            .contentShape(shape)
            .scaleEffect(pressed ? 0.97 : 1)
            .animation(Motion.press, value: configuration.isPressed)
            .animation(Motion.hover, value: hover)
            .onHover { hover = $0 }
    }

    private var pressed: Bool { configuration.isPressed && enabled }
    private var lit: Bool { hover && enabled }

    private var base: Color {
        guard enabled else { return kind == .plain ? .clear : P.fill4 }
        switch kind {
        case .primary: return P.accent
        case .secondary: return pressed ? P.fill1 : P.fill2
        case .plain: return pressed ? P.fill3 : (lit ? P.fill4 : .clear)
        case .destructive: return P.danger.opacity(pressed ? 0.28 : 0.18)
        }
    }

    private var highlight: Double {
        guard lit, !pressed else { return 0 }
        switch kind {
        case .primary: return 0.1
        case .secondary, .destructive: return 0.05
        case .plain: return 0
        }
    }

    private var foreground: Color {
        guard enabled else { return P.textTertiary }
        switch kind {
        case .primary: return .white
        case .secondary: return P.text
        case .plain: return lit ? P.text : P.textMuted
        case .destructive: return P.danger
        }
    }
}

/// Глиф и подпись в кнопке: глиф на шаг мельче текста, отступ 6.
struct FLLabelStyle: LabelStyle {
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 6) {
            configuration.icon.font(.system(size: 11, weight: .semibold))
            configuration.title
        }
    }
}

/// Кнопка-глиф для действий в строке: покой - secondaryLabel, наведение -
/// label и подложка; у удаления при наведении красный.
struct FLIconButton: View {
    let symbol: String
    let help: String
    var destructive = false
    let action: () -> Void
    @State private var hover = false
    @Environment(\.isEnabled) private var enabled

    var body: some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 12, weight: .medium))
                .contentTransition(.symbolEffect(.replace))
                .foregroundStyle(color)
                .frame(width: 26, height: Metric.buttonSmall)
                .background(RoundedRectangle(cornerRadius: Radius.control, style: .continuous)
                    .fill(hover && enabled ? P.fill4 : .clear))
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .help(help)
        .accessibilityLabel(help)
        .onHover { hover = $0 }
        .animation(Motion.hover, value: hover)
    }

    private var color: Color {
        guard enabled else { return P.textQuaternary }
        guard hover else { return P.textMuted }
        return destructive ? P.danger : P.text
    }
}

// MARK: - сегменты

/// Сегменты как у macOS: утопленная дорожка fill/3, выбранный сегмент -
/// поднятая плашка systemGray2, которая переезжает, а не перекрашивается.
struct FLSegmented<T: Hashable>: View {
    let options: [(T, String)]
    @Binding var selection: T
    @Namespace private var thumb

    var body: some View {
        HStack(spacing: 2) {
            ForEach(Array(options.enumerated()), id: \.offset) { _, option in
                let on = option.0 == selection
                Button {
                    withAnimation(Motion.page) { selection = option.0 }
                } label: {
                    Text(option.1)
                        .font(.system(size: 12, weight: on ? .semibold : .regular))
                        .foregroundStyle(on ? P.text : P.textMuted)
                        .padding(.horizontal, 12)
                        .frame(height: 22)
                        .background {
                            if on {
                                RoundedRectangle(cornerRadius: Radius.menu, style: .continuous)
                                    .fill(P.gray2)
                                    .matchedGeometryEffect(id: "thumb", in: thumb)
                            }
                        }
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
        }
        .padding(2)
        .background(RoundedRectangle(cornerRadius: Radius.control, style: .continuous).fill(P.fill3))
        .fixedSize()
    }
}

// MARK: - системные контролы

/// Настоящий переключатель macOS, малый размер, акцент systemBlue.
struct FLSwitch: View {
    @Binding var isOn: Bool

    var body: some View {
        Toggle("", isOn: $isOn)
            .toggleStyle(.switch)
            .labelsHidden()
            .controlSize(.small)
            .tint(P.accent)
    }
}

/// Настоящий флажок macOS с подписью.
struct FLCheck: View {
    @Binding var isOn: Bool
    let label: String

    var body: some View {
        Toggle(isOn: $isOn) {
            Text(label).textStyle(.body, P.text)
        }
        .toggleStyle(.checkbox)
    }
}

/// Всплывающее меню macOS (NSPopUpButton): список - системный.
struct FLPopup<T: Hashable>: View {
    let options: [(T, String)]
    @Binding var selection: T

    var body: some View {
        Picker("", selection: $selection) {
            ForEach(Array(options.enumerated()), id: \.offset) { _, option in
                Text(option.1).tag(option.0)
            }
        }
        .pickerStyle(.menu)
        .labelsHidden()
    }
}

// MARK: - поиск

/// Поле поиска: лупа, fill/3, радиус 6; в фокусе - кольцо 3 pt
/// systemBlue 50 %, как у системного поля.
struct FLSearchField: View {
    @Binding var text: String
    var placeholder = "Поиск"
    @FocusState private var focused: Bool

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(P.textMuted)
            TextField(placeholder, text: $text)
                .textFieldStyle(.plain)
                .font(TextStyle.body.font())
                .foregroundStyle(P.text)
                .focused($focused)
            if !text.isEmpty {
                Button { text = "" } label: {
                    Image(systemName: "xmark.circle.fill").font(.system(size: 12))
                        .foregroundStyle(P.textTertiary)
                }
                .buttonStyle(.plain)
                .help("Очистить")
            }
        }
        .padding(.horizontal, 8)
        .frame(height: Metric.button)
        .background(RoundedRectangle(cornerRadius: Radius.control, style: .continuous).fill(P.fill3))
        .overlay(
            RoundedRectangle(cornerRadius: Radius.control + 3, style: .continuous)
                .strokeBorder(P.accent.opacity(focused ? 0.5 : 0), lineWidth: 3)
                .padding(-3)
        )
        .animation(Motion.hover, value: focused)
    }
}

// MARK: - тег, точка, линия

enum FLTone { case neutral, accent, success, warning, danger }

/// Тег-капсула 11/600: цвет состояния текстом и прозрачной подложкой.
struct FLTag: View {
    let text: String
    var tone: FLTone = .neutral
    var dot = false
    var symbol: String?

    var body: some View {
        HStack(spacing: 5) {
            if dot { Circle().fill(color).frame(width: 6, height: 6) }
            if let symbol { Image(systemName: symbol).font(.system(size: 9, weight: .semibold)) }
            Text(text).font(.system(size: 11, weight: .semibold))
        }
        .foregroundStyle(color)
        .padding(.horizontal, 8)
        .frame(height: 20)
        .background(Capsule().fill(background))
        .fixedSize()
    }

    private var color: Color {
        switch tone {
        case .neutral: return P.textMuted
        case .accent: return P.accent
        case .success: return P.success
        case .warning: return P.warning
        case .danger: return P.danger
        }
    }

    private var background: Color { tone == .neutral ? P.fill3 : P.wash(color) }
}

/// Точка состояния. pulse - тихое расходящееся кольцо (идёт запись).
struct StatusDot: View {
    let color: Color
    var pulse = false
    @State private var on = false

    var body: some View {
        Circle().fill(color).frame(width: 8, height: 8)
            .background {
                if pulse {
                    Circle().fill(color.opacity(0.4))
                        .scaleEffect(on ? 2.4 : 1)
                        .opacity(on ? 0 : 1)
                        .animation(.easeOut(duration: 1.2).repeatForever(autoreverses: false), value: on)
                }
            }
            .onAppear { on = pulse }
            .onChange(of: pulse) { _, value in on = value }
    }
}

/// Глиф строки настроек в плашке 24 pt - как в System Settings, но
/// монохромный: цвет на экране один, и он отдан действию.
struct SettingIcon: View {
    let symbol: String

    var body: some View {
        Image(systemName: symbol)
            .font(.system(size: 12, weight: .medium))
            .foregroundStyle(P.text)
            .frame(width: 24, height: 24)
            .background(RoundedRectangle(cornerRadius: Radius.control, style: .continuous).fill(P.surface3))
    }
}

/// Разделитель толщиной в один физический пиксель, как у системных списков.
struct FLSeparator: View {
    var vertical = false
    var inset: CGFloat = 0
    var color: Color = Palette.dark.separator
    @Environment(\.displayScale) private var scale

    var body: some View {
        let w = 1 / max(scale, 1)
        Rectangle()
            .fill(color)
            .frame(width: vertical ? w : nil, height: vertical ? nil : w)
            .frame(maxWidth: vertical ? nil : .infinity, maxHeight: vertical ? .infinity : nil)
            .padding(vertical ? .top : .leading, inset)
    }
}

extension View {
    /// Карточка: уровень elevated/1 на чёрном, радиус 12, без рамки и тени.
    func card() -> some View {
        background(RoundedRectangle(cornerRadius: Radius.card, style: .continuous).fill(P.surface))
    }
}

/// Заголовок группы над карточкой - headline 13/600, как в System Settings.
struct SectionTitle: View {
    let text: String
    init(_ text: String) { self.text = text }

    var body: some View {
        Text(text).textStyle(.headline, P.text)
    }
}

/// Прокручиваемая страница: колонка ограниченной ширины по центру сцены,
/// поля по сетке - на широком окне справа не остаётся пустого хвоста.
struct PageScroll<Content: View>: View {
    var maxWidth: CGFloat = 720
    @ViewBuilder let content: () -> Content

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Space.s5) { content() }
                .frame(maxWidth: maxWidth, alignment: .leading)
                .padding(.horizontal, Space.s5)
                .padding(.top, Space.s1)
                .padding(.bottom, Space.s6)
                .frame(maxWidth: .infinity)
        }
    }
}

// MARK: - сообщение

/// Сообщение в потоке страницы: цветной глиф и белый текст на карточке -
/// без полосы у края и без жёлтой заливки.
struct FLNotice<Actions: View>: View {
    let symbol: String
    let title: String
    let text: String
    var tone: FLTone = .warning
    @ViewBuilder let actions: () -> Actions

    var body: some View {
        HStack(alignment: .top, spacing: Space.s3) {
            Image(systemName: symbol)
                .font(.system(size: 18))
                .foregroundStyle(color)
                .frame(width: 24)
            VStack(alignment: .leading, spacing: Space.s1) {
                Text(title).textStyle(.headline, P.text)
                Text(text)
                    .textStyle(.body, P.textMuted)
                    .fixedSize(horizontal: false, vertical: true)
                actions().padding(.top, Space.s2)
            }
            Spacer(minLength: 0)
        }
        .padding(Space.s4)
        .card()
    }

    private var color: Color {
        switch tone {
        case .success: return P.success
        case .danger: return P.danger
        case .warning: return P.warning
        case .neutral, .accent: return P.accent
        }
    }
}

// MARK: - пусто, ожидание

/// Пустое состояние: глиф 32 pt, заголовок и одна строка пояснения по центру.
struct EmptyState: View {
    let symbol: String
    let title: String
    let text: String

    var body: some View {
        VStack(spacing: Space.s2) {
            Image(systemName: symbol)
                .font(.system(size: 32, weight: .light))
                .foregroundStyle(P.textTertiary)
                .padding(.bottom, Space.s1)
            Text(title).textStyle(.title3, P.text, weight: .semibold)
            Text(text)
                .textStyle(.body, P.textMuted)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 300)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(Space.s5)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// Строка-заглушка, пока текст готовится: мягко дышит, не бегает.
struct FLSkeleton: View {
    var width: CGFloat?
    @State private var dim = false

    var body: some View {
        RoundedRectangle(cornerRadius: Radius.menu, style: .continuous)
            .fill(P.fill3)
            .frame(width: width, height: 12)
            .frame(maxWidth: width == nil ? .infinity : nil, alignment: .leading)
            .opacity(dim ? 0.45 : 1)
            .onAppear {
                withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) { dim = true }
            }
    }
}

// MARK: - волна

/// Волна уровня, как в «Диктофоне»: капсулы от центра вверх и вниз, свежий
/// звук справа, старый гаснет к левому краю.
struct Waveform: View {
    let levels: [Float]
    var color: Color = Palette.dark.accent
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
        .animation(.linear(duration: 0.1), value: values)
        .accessibilityHidden(true)
    }
}

/// Волна, которая сама слушает уровень микрофона: перерисовывается только
/// она, а не всё окно.
struct LiveWaveform: View {
    @ObservedObject private var meter = LevelStore.shared
    var color: Color = Palette.dark.accent
    var count = 48
    var barWidth: CGFloat = 3
    var spacing: CGFloat = 3
    var height: CGFloat = 64

    var body: some View {
        Waveform(levels: meter.levels, color: color, count: count, barWidth: barWidth,
                 spacing: spacing, height: height)
    }
}

// MARK: - числа

/// Плитка числа: глиф и подпись 11 pt secondaryLabel, число 26/400
/// табличными цифрами, единица - body secondaryLabel.
struct StatTile: View {
    var symbol: String?
    let label: String
    let value: String
    var unit: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Space.s2) {
            HStack(spacing: 6) {
                if let symbol {
                    Image(systemName: symbol).font(.system(size: 11, weight: .medium))
                }
                Text(label).font(TextStyle.subheadline.font()).lineLimit(1)
            }
            .foregroundStyle(P.textMuted)
            HStack(alignment: .firstTextBaseline, spacing: Space.s1) {
                Text(value)
                    .font(TextStyle.largeTitle.font())
                    .monospacedDigit()
                    .foregroundStyle(P.text)
                    .contentTransition(.numericText())
                    .lineLimit(1)
                if let unit {
                    Text(unit).textStyle(.body, P.textMuted)
                }
            }
        }
        .padding(Space.s4)
        .frame(maxWidth: .infinity, alignment: .leading)
        .card()
    }
}

// MARK: - клавиши

enum KeyCapSize { case large, small }

/// Клавиша, как на клавиатуре MacBook: у модификатора знак сверху справа и
/// слово снизу слева, у остальных - слово по центру. small - маленькая
/// клавиша со знаком для строк настроек.
struct KeyCap: View {
    let key: String
    var size: KeyCapSize = .large
    var active = false

    var body: some View {
        face
            .foregroundStyle(active ? Color.white : P.text)
            .background(RoundedRectangle(cornerRadius: Radius.control, style: .continuous)
                .fill(active ? P.accent : P.surface2))
            .fixedSize()
    }

    @ViewBuilder
    private var face: some View {
        if size == .small {
            Text(KeyGlyph.short(key))
                .font(.system(size: 12, weight: .medium))
                .padding(.horizontal, 6)
                .frame(minWidth: 22, minHeight: 22)
        } else if let glyph = KeyGlyph.symbol(key) {
            VStack(alignment: .leading, spacing: 0) {
                Text(glyph)
                    .font(.system(size: 12))
                    .frame(maxWidth: .infinity, alignment: .trailing)
                Spacer(minLength: 0)
                Text(KeyGlyph.word(key)).font(.system(size: 10, weight: .medium))
            }
            .padding(.horizontal, 7)
            .padding(.vertical, 5)
            .frame(width: KeyGlyph.width(key), height: 40)
        } else {
            Text(KeyGlyph.word(key))
                .font(.system(size: 11, weight: .medium))
                .frame(width: KeyGlyph.width(key), height: 40)
        }
    }
}

/// Сочетание целиком - клавиши вплотную, без «+», как в меню macOS.
struct KeyCapRow: View {
    let keys: [String]
    var size: KeyCapSize = .large
    var active = false

    var body: some View {
        HStack(spacing: size == .large ? 6 : 3) {
            ForEach(Array(keys.enumerated()), id: \.offset) { _, key in
                KeyCap(key: key, size: size, active: active)
            }
        }
        .fixedSize()
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(keys.map(KeyGlyph.word).joined(separator: " "))
    }
}

// MARK: - материал

/// Системный материал AppKit: .sidebar размывает то, что за окном, - так же,
/// как сайдбар Finder и System Settings.
struct VisualEffect: NSViewRepresentable {
    var material: NSVisualEffectView.Material = .sidebar
    var blending: NSVisualEffectView.BlendingMode = .behindWindow

    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.material = material
        view.blendingMode = blending
        view.state = .followsWindowActiveState
        return view
    }

    func updateNSView(_ view: NSVisualEffectView, context: Context) {
        view.material = material
        view.blendingMode = blending
    }
}
