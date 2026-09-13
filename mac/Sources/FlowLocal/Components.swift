import AppKit
import SwiftUI

// Примитивы Verkstad (css/actions, data, feedback, forms, navigation,
// surfaces), перенесённые в SwiftUI: радиус 0, рамки 1/2 px, без теней,
// движение - одна кривая Motion. Состав - по набору элементов макета
// «Flow Local - главный экран» (артборд 1g).

// MARK: - кнопка

enum VKButtonKind { case primary, secondary, ghost, danger }
enum VKButtonSize { case sm, md }

struct VKButtonStyle: ButtonStyle {
    let palette: Palette
    var kind: VKButtonKind = .secondary
    var size: VKButtonSize = .md
    var fill = false

    func makeBody(configuration: Configuration) -> some View {
        VKButtonBody(configuration: configuration, p: palette, kind: kind, size: size, fill: fill)
    }
}

private struct VKButtonBody: View {
    let configuration: ButtonStyle.Configuration
    let p: Palette
    let kind: VKButtonKind
    let size: VKButtonSize
    let fill: Bool
    @State private var hover = false
    @Environment(\.isEnabled) private var enabled

    var body: some View {
        let fs = size == .sm ? FontSize.fs1 : FontSize.fs2
        configuration.label
            .font(Fonts.text(fs, .bold))
            .tracking(fs * 0.04)
            .textCase(.uppercase)
            .lineLimit(1)
            .padding(.horizontal, kind == .ghost || size == .sm ? Space.s3 : Space.s5)
            .frame(maxWidth: fill ? .infinity : nil)
            .frame(height: size == .sm ? Space.controlSm : Space.controlMd)
            .foregroundStyle(foreground)
            .background(
                // «Шторка»: заливка поднимается снизу вверх, подпись инвертируется.
                Rectangle().fill(shutter)
                    .scaleEffect(x: 1, y: hover && enabled ? 1 : 0, anchor: .bottom)
            )
            .background(base)
            .overlay(Rectangle().strokeBorder(edge, lineWidth: size == .sm ? Space.hairline : Space.strong))
            .contentShape(Rectangle())
            .scaleEffect(x: 1, y: configuration.isPressed && enabled ? 0.96 : 1)
            .animation(Motion.instant, value: configuration.isPressed)
            .animation(Motion.base, value: hover)
            .onHover { hover = $0 }
    }

    private var base: Color {
        guard kind == .primary else { return .clear }
        return enabled ? p.accent : p.surface2
    }

    private var shutter: Color {
        switch kind {
        case .primary: return p.text
        case .danger: return p.danger
        case .secondary, .ghost: return p.accent
        }
    }

    private var foreground: Color {
        guard enabled else { return p.textMuted }
        switch kind {
        case .primary: return hover ? p.textInverse : p.accentText
        case .secondary, .ghost: return hover ? p.accentText : p.text
        case .danger: return hover ? p.accentText : p.danger
        }
    }

    private var edge: Color {
        guard enabled else { return kind == .primary ? p.surface2 : (kind == .ghost ? .clear : p.border) }
        switch kind {
        case .primary: return hover ? p.text : p.accent
        case .secondary: return hover ? p.accent : p.borderStrong
        case .ghost: return .clear
        case .danger: return p.danger
        }
    }
}

// MARK: - вкладки (vk-tab: моно 12, активная - линия 2 px растёт слева)

struct VKTabBar: View {
    @Binding var selection: Tab
    let palette: Palette
    var compact = false

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Tab.allCases) { tab in
                VKTabButton(title: tab.title, active: tab == selection, palette: palette, compact: compact) {
                    selection = tab
                }
            }
        }
    }
}

private struct VKTabButton: View {
    let title: String
    let active: Bool
    let palette: Palette
    let compact: Bool
    let action: () -> Void
    @State private var hover = false

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(Fonts.mono(FontSize.monoLg))
                .tracking(FontSize.monoLg * 0.12)
                .textCase(.uppercase)
                .lineLimit(1)
                .foregroundStyle(active || hover ? palette.text : palette.textMuted)
                .padding(.horizontal, compact ? Space.s3 : Space.s4)
                .frame(maxHeight: .infinity)
                .overlay(alignment: .bottom) {
                    Rectangle()
                        .fill(palette.accent)
                        .frame(height: Space.strong)
                        .scaleEffect(x: active ? 1 : 0, y: 1, anchor: .leading)
                }
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { hover = $0 }
        .animation(Motion.base, value: active)
        .animation(Motion.base, value: hover)
    }
}

// MARK: - сегменты (vk-btngroup: общая рамка, без зазоров)

struct VKSegmented<T: Hashable>: View {
    let options: [(T, String)]
    @Binding var selection: T
    let palette: Palette

    var body: some View {
        HStack(spacing: -Space.hairline) {
            ForEach(Array(options.enumerated()), id: \.offset) { _, option in
                Button(option.1) { selection = option.0 }
                    .buttonStyle(VKSegmentStyle(p: palette, on: option.0 == selection))
                    .zIndex(option.0 == selection ? 1 : 0)
            }
        }
        .fixedSize()
    }
}

private struct VKSegmentStyle: ButtonStyle {
    let p: Palette
    let on: Bool

    func makeBody(configuration: Configuration) -> some View {
        VKSegmentBody(configuration: configuration, p: p, on: on)
    }
}

private struct VKSegmentBody: View {
    let configuration: ButtonStyle.Configuration
    let p: Palette
    let on: Bool
    @State private var hover = false

    var body: some View {
        configuration.label
            .font(Fonts.mono(FontSize.mono, .medium))
            .tracking(FontSize.mono * 0.12)
            .textCase(.uppercase)
            .lineLimit(1)
            .padding(.horizontal, Space.s3)
            .frame(height: Space.controlSm)
            // Выбранный сегмент - инверсия текста, а не акцент: акцент на
            // экране один, и он отдан действию.
            .foregroundStyle(on ? p.textInverse : (hover ? p.text : p.textMuted))
            .background(on ? p.text : (hover ? p.surface2 : Color.clear))
            .overlay(Rectangle().strokeBorder(on ? p.text : p.borderStrong, lineWidth: Space.hairline))
            .contentShape(Rectangle())
            .scaleEffect(x: 1, y: configuration.isPressed ? 0.96 : 1)
            .animation(Motion.instant, value: configuration.isPressed)
            .animation(Motion.base, value: hover)
            .animation(Motion.base, value: on)
            .onHover { hover = $0 }
    }
}

// MARK: - переключатель (vk-switch: прямоугольная дорожка 44x20, жёсткий щелчок)

struct VKSwitch: View {
    @Binding var isOn: Bool
    let palette: Palette

    var body: some View {
        Button { isOn.toggle() } label: {
            ZStack(alignment: .leading) {
                Rectangle()
                    .fill(isOn ? palette.accent : palette.surface2)
                    .overlay(Rectangle().strokeBorder(isOn ? palette.accent : palette.borderStrong,
                                                      lineWidth: Space.hairline))
                Rectangle()
                    .fill(isOn ? palette.accentText : palette.textMuted)
                    .frame(width: 16, height: 14)
                    .offset(x: isOn ? 25 : 3)
            }
            .frame(width: 44, height: 20)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .animation(Motion.instant, value: isOn)
    }
}

// MARK: - флажок (vk-check: квадрат 18 px, заливка акцентом)

struct VKCheck: View {
    @Binding var isOn: Bool
    let label: String
    let palette: Palette

    var body: some View {
        Button { isOn.toggle() } label: {
            HStack(alignment: .top, spacing: Space.s3) {
                ZStack {
                    Rectangle()
                        .fill(isOn ? palette.accent : palette.surface)
                        .overlay(Rectangle().strokeBorder(isOn ? palette.accent : palette.borderStrong,
                                                          lineWidth: Space.hairline))
                    if isOn {
                        CheckMark().stroke(palette.accentText, style: StrokeStyle(lineWidth: Space.strong))
                            .frame(width: 10, height: 8)
                    }
                }
                .frame(width: 18, height: 18)
                .padding(.top, 1)
                Text(label)
                    .font(Fonts.text(FontSize.fs2))
                    .foregroundStyle(isOn ? palette.text : palette.textMuted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .animation(Motion.instant, value: isOn)
    }
}

private struct CheckMark: Shape {
    func path(in r: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: r.minX, y: r.minY + r.height * 0.55))
        p.addLine(to: CGPoint(x: r.minX + r.width * 0.38, y: r.maxY))
        p.addLine(to: CGPoint(x: r.maxX, y: r.minY))
        return p
    }
}

// MARK: - выбор (vk-select). Поле - своё, список - системное меню: у SwiftUI
// Menu на macOS своя рамка не рисуется, а список - это список.

struct VKSelect<T: Hashable>: View {
    let options: [(T, String)]
    @Binding var selection: T
    let palette: Palette
    var small = false
    @State private var hover = false

    var body: some View {
        let current = options.first { $0.0 == selection }?.1 ?? "—"
        Button {
            MenuPresenter.show(options.map { ($0.1, $0.0 == selection) }) { i in
                selection = options[i].0
            }
        } label: {
            HStack(spacing: Space.s2) {
                Text(current)
                    .font(Fonts.text(small ? FontSize.fs1 : FontSize.fs2))
                    .foregroundStyle(palette.text)
                    .lineLimit(1)
                Spacer(minLength: Space.s2)
                Chevron()
                    .stroke(palette.text, style: StrokeStyle(lineWidth: Space.strong))
                    .frame(width: 8, height: 5)
            }
            .padding(.horizontal, Space.s3)
            .frame(height: small ? Space.controlSm : Space.controlMd)
            .background(palette.surface)
            .overlay(Rectangle().strokeBorder(hover ? palette.borderStrong : palette.border,
                                              lineWidth: Space.hairline))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { hover = $0 }
        .animation(Motion.base, value: hover)
    }
}

private struct Chevron: Shape {
    func path(in r: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: r.minX, y: r.minY))
        p.addLine(to: CGPoint(x: r.midX, y: r.maxY))
        p.addLine(to: CGPoint(x: r.maxX, y: r.minY))
        return p
    }
}

enum MenuPresenter {
    static func show(_ items: [(String, Bool)], _ pick: @escaping (Int) -> Void) {
        let menu = NSMenu()
        let target = MenuTarget(pick)
        for (i, item) in items.enumerated() {
            let mi = NSMenuItem(title: item.0, action: #selector(MenuTarget.picked(_:)), keyEquivalent: "")
            mi.target = target
            mi.tag = i
            mi.state = item.1 ? .on : .off
            menu.addItem(mi)
        }
        // popUp модальный: target живёт на стеке, пока меню открыто.
        menu.popUp(positioning: nil, at: NSEvent.mouseLocation, in: nil)
        _ = target
    }
}

private final class MenuTarget: NSObject {
    let pick: (Int) -> Void
    init(_ pick: @escaping (Int) -> Void) { self.pick = pick }
    @objc func picked(_ sender: NSMenuItem) { pick(sender.tag) }
}

// MARK: - поиск (vk-search: моно-метка вместо значка)

struct VKSearchField: View {
    @Binding var text: String
    let palette: Palette
    var placeholder = "Текст диктовки"
    @FocusState private var focused: Bool

    var body: some View {
        HStack(spacing: 0) {
            Text("Поиск")
                .monoLabel(palette.textMuted)
                .padding(.horizontal, Space.s3)
                .frame(maxHeight: .infinity)
                .overlay(alignment: .trailing) { Rectangle().fill(palette.border).frame(width: Space.hairline) }
            TextField(placeholder, text: $text)
                .textFieldStyle(.plain)
                .font(Fonts.text(FontSize.fs2))
                .foregroundStyle(palette.text)
                .focused($focused)
                .padding(.horizontal, Space.s3)
        }
        .frame(height: Space.controlMd)
        .background(palette.surface)
        .overlay(Rectangle().strokeBorder(focused ? palette.accent : palette.border,
                                          lineWidth: focused ? Space.strong : Space.hairline))
    }
}

// MARK: - бейдж (vk-badge)

enum VKTone { case neutral, accent, outline, success, warning, danger }

struct VKBadge: View {
    let text: String
    var tone: VKTone = .neutral
    var dot = false
    let palette: Palette

    var body: some View {
        HStack(spacing: Space.s2) {
            if dot {
                Rectangle().fill(colors.fg).frame(width: 6, height: 6)
            }
            Text(text).monoLabel(colors.fg)
        }
        .padding(.horizontal, Space.s2)
        .frame(height: 20)
        .background(colors.bg)
        .overlay(Rectangle().strokeBorder(colors.edge, lineWidth: Space.hairline))
        .fixedSize()
    }

    private var colors: (bg: Color, fg: Color, edge: Color) {
        let p = palette
        switch tone {
        case .neutral: return (p.surface2, p.text, p.border)
        case .accent: return (p.accent, p.accentText, p.accent)
        case .outline: return (.clear, p.text, p.borderStrong)
        case .success: return (p.successBg, p.success, p.success)
        case .warning: return (p.warningBg, p.warning, p.warning)
        case .danger: return (p.dangerBg, p.danger, p.danger)
        }
    }
}

// MARK: - линия

/// Хейрлайн на всю ширину: секции делятся линией, а не пустотой.
struct VKDivider: View {
    let palette: Palette
    var strong = false
    var vertical = false

    var body: some View {
        let w = strong ? Space.strong : Space.hairline
        Rectangle()
            .fill(strong ? palette.borderStrong : palette.border)
            .frame(width: vertical ? w : nil, height: vertical ? nil : w)
            .frame(maxWidth: vertical ? nil : .infinity, maxHeight: vertical ? .infinity : nil)
    }
}

// MARK: - алерт (vk-alert: кромка 2 px цветом состояния)

struct VKAlert<Actions: View>: View {
    let mark: String
    let title: String
    let text: String
    var tone: VKTone = .warning
    let palette: Palette
    @ViewBuilder let actions: () -> Actions

    var body: some View {
        let p = palette
        HStack(alignment: .top, spacing: Space.s4) {
            Text(mark).monoLabel(edge).padding(.top, 2)
            VStack(alignment: .leading, spacing: Space.s2) {
                Text(title).font(Fonts.text(FontSize.fs2, .bold)).foregroundStyle(p.text)
                Text(text)
                    .font(Fonts.text(FontSize.fs2))
                    .foregroundStyle(p.textMuted)
                    .lineSpacing(3)
                    .fixedSize(horizontal: false, vertical: true)
                actions().padding(.top, Space.s1)
            }
            Spacer(minLength: 0)
        }
        .padding(Space.s4)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(background)
        .overlay(Rectangle().strokeBorder(p.border, lineWidth: Space.hairline))
        .overlay(alignment: .leading) { Rectangle().fill(edge).frame(width: Space.strong) }
    }

    private var edge: Color {
        switch tone {
        case .success: return palette.success
        case .danger: return palette.danger
        case .warning: return palette.warning
        default: return palette.accentInk
        }
    }

    private var background: Color {
        switch tone {
        case .success: return palette.successBg
        case .danger: return palette.dangerBg
        case .warning: return palette.warningBg
        default: return palette.surface
        }
    }
}

// MARK: - ожидание: блоки, мигание, прогресс, скелетон

/// Три прямоугольных блока шагами (vk-spinner), никогда не круг.
struct VKSpinner: View {
    let color: Color
    var height: CGFloat = 16

    var body: some View {
        TimelineView(.animation) { ctx in
            let t = ctx.date.timeIntervalSinceReferenceDate
            HStack(alignment: .bottom, spacing: 3) {
                ForEach(0..<3, id: \.self) { i in
                    let phase = (t - Double(i) * 0.12).truncatingRemainder(dividingBy: 0.72)
                    Rectangle()
                        .fill(color)
                        .frame(width: height / 4, height: height)
                        .scaleEffect(x: 1, y: phase < 0.36 ? 0.35 : 1, anchor: .bottom)
                }
            }
            .frame(height: height)
        }
    }
}

/// «РАСПОЗНАЮ» из макета: три блока мигают по очереди, шагами.
struct VKPulseBlocks: View {
    let color: Color
    var width: CGFloat = 6
    var height: CGFloat = 12

    var body: some View {
        TimelineView(.animation) { ctx in
            let t = ctx.date.timeIntervalSinceReferenceDate
            HStack(spacing: 3) {
                ForEach(0..<3, id: \.self) { i in
                    let phase = (t - Double(i) * 0.2).truncatingRemainder(dividingBy: 0.6)
                    Rectangle()
                        .fill(color)
                        .frame(width: width, height: height)
                        .opacity(phase < 0.3 ? 1 : 0.35)
                }
            }
        }
    }
}

/// Мигающий квадрат (идёт запись) и курсор расшифровки - шагами, без плавности.
struct VKBlink: View {
    let color: Color
    var width: CGFloat = 8
    var height: CGFloat = 8
    var period: Double = 1.2

    var body: some View {
        TimelineView(.periodic(from: .now, by: period / 2)) { ctx in
            let on = Int(ctx.date.timeIntervalSinceReferenceDate / (period / 2)) % 2 == 0
            Rectangle().fill(color).frame(width: width, height: height).opacity(on ? 1 : 0.35)
        }
    }
}

struct VKProgress: View {
    var value: Double?          // nil - неизвестно сколько: бегущая полоса
    let palette: Palette
    var height: CGFloat = 8

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Rectangle().fill(palette.surface2)
                if let v = value {
                    Rectangle().fill(palette.accent).frame(width: geo.size.width * max(0, min(1, v)))
                } else {
                    TimelineView(.animation) { ctx in
                        let w = geo.size.width * 0.32
                        let x = -w + (geo.size.width + w) * Self.eased(ctx.date, period: 1.2)
                        Rectangle().fill(palette.accent).frame(width: w).offset(x: x)
                    }
                }
            }
            .clipped()
        }
        .frame(height: height)
        .overlay(Rectangle().strokeBorder(palette.border, lineWidth: Space.hairline))
    }

    /// Та же кривая, что у всей системы: механически разгоняется и тормозит.
    static func eased(_ date: Date, period: Double) -> Double {
        let t = date.timeIntervalSinceReferenceDate.truncatingRemainder(dividingBy: period) / period
        return t < 0.5 ? 4 * t * t * t : 1 - pow(-2 * t + 2, 3) / 2
    }
}

/// Скелетон: плоский блок и жёсткая протирка панелью, не мягкая пульсация.
struct VKSkeleton: View {
    let palette: Palette
    var height: CGFloat = 16
    var delay: Double = 0

    var body: some View {
        GeometryReader { geo in
            TimelineView(.animation) { ctx in
                let w = geo.size.width * 0.25
                let phase = VKProgress.eased(ctx.date.addingTimeInterval(-delay), period: 1.1)
                Rectangle().fill(palette.borderStrong).frame(width: w).offset(x: -w + (geo.size.width + w * 4) * phase)
            }
        }
        .frame(height: height)
        .background(palette.surface)
        .clipped()
        .overlay(Rectangle().strokeBorder(palette.border, lineWidth: Space.hairline))
    }
}

// MARK: - уровень микрофона

/// Столбики уровня, прижаты книзу. Берём последние count значений.
struct VKLevelBars: View {
    let levels: [Float]
    let color: Color
    var count = 20
    var spacing: CGFloat = 4
    var barWidth: CGFloat?
    var height: CGFloat = 80
    var floor: CGFloat = 0.12

    var body: some View {
        let tail = Array(levels.suffix(count))
        let values = Array(repeating: Float(0), count: max(0, count - tail.count)) + tail
        HStack(alignment: .bottom, spacing: spacing) {
            ForEach(values.indices, id: \.self) { i in
                Rectangle()
                    .fill(color)
                    .frame(width: barWidth)
                    .frame(maxWidth: barWidth == nil ? .infinity : nil)
                    .frame(height: height * max(floor, CGFloat(values[i])))
            }
        }
        .frame(height: height, alignment: .bottom)
        .animation(.linear(duration: 0.08), value: values)
    }
}

// MARK: - числа, пустота, клавиши

/// Плитка числа: моно-подпись, крупная цифра Unbounded, единица моно.
struct VKStatTile: View {
    let label: String
    let value: String
    var unit: String?
    let palette: Palette
    var size: CGFloat = 34

    var body: some View {
        VStack(alignment: .leading, spacing: Space.s2) {
            Text(label).monoLabel(palette.textMuted).lineLimit(1)
            HStack(alignment: .firstTextBaseline, spacing: Space.s2) {
                Text(value)
                    .displayTitle(palette.text, size: size, weight: .bold)
                    .monospacedDigit()
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                if let unit {
                    Text(unit).monoLabel(palette.textMuted, size: FontSize.monoLg)
                }
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, Space.s4)
        // Одна высота на всех: иначе плитка с единицей выше соседей, и сетка
        // центрует их по-разному - подписи в ряду разъезжаются.
        .frame(maxWidth: .infinity, minHeight: 96, alignment: .topLeading)
        .background(palette.surface)
    }
}

/// Пустое состояние: пунктирная рамка, моно-код, факт, потом действие.
struct VKEmpty: View {
    var code = "Пусто"
    let title: String
    let text: String
    let palette: Palette

    var body: some View {
        VStack(alignment: .leading, spacing: Space.s3) {
            Text(code).monoLabel(palette.textMuted)
            Text(title).font(Fonts.text(FontSize.fs4, .bold)).foregroundStyle(palette.text)
            Text(text)
                .font(Fonts.text(FontSize.fs2))
                .foregroundStyle(palette.textMuted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(Space.s5)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(palette.surface)
        .overlay(Rectangle().strokeBorder(palette.borderStrong,
                                          style: StrokeStyle(lineWidth: Space.hairline, dash: [4, 3])))
    }
}

/// Клавиша: 44 px, моно 12, трекинг 0.12em. SPACE - шире, как в макете.
struct VKKeycap: View {
    let text: String
    let palette: Palette
    var height: CGFloat = 44
    var accent = false

    var body: some View {
        let wide = text == "SPACE"
        Text(text)
            .font(Fonts.mono(height > 36 ? FontSize.monoLg : FontSize.mono))
            .tracking(FontSize.monoLg * 0.12)
            .textCase(.uppercase)
            .lineLimit(1)
            .foregroundStyle(accent ? palette.accentText : palette.text)
            .padding(.horizontal, wide ? (height > 36 ? Space.s6 : 20) : (height > 36 ? Space.s4 : Space.s3))
            .frame(height: height)
            .background(accent ? palette.accent : palette.surface2)
            .overlay(Rectangle().strokeBorder(accent ? palette.accent : palette.borderStrong,
                                              lineWidth: accent ? Space.strong : Space.hairline))
            .fixedSize()
    }
}

/// Сочетание целиком: клавиши через «+». Плюс - полноценный элемент строки
/// цветом текста: без него три клавиши читаются как три отдельные кнопки.
struct VKCombo: View {
    let keys: [String]
    let palette: Palette
    var height: CGFloat = 40

    var body: some View {
        HStack(spacing: Space.s2) {
            ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                if item == "+" {
                    Text("+")
                        .font(Fonts.mono(FontSize.fs3, .medium))
                        .foregroundStyle(palette.text)
                } else {
                    VKKeycap(text: item, palette: palette, height: height)
                }
            }
        }
        .fixedSize()
    }

    private var items: [String] {
        keys.enumerated().flatMap { i, key in i == 0 ? [key] : ["+", key] }
    }
}

/// Столбики, которые сами слушают уровень микрофона: перерисовываются только
/// они, а не всё окно.
struct LiveLevels: View {
    @ObservedObject private var meter = LevelStore.shared
    let color: Color
    var count = 20
    var spacing: CGFloat = 4
    var barWidth: CGFloat?
    var height: CGFloat = 80
    var floor: CGFloat = 0.12

    var body: some View {
        VKLevelBars(levels: meter.levels, color: color, count: count, spacing: spacing,
                    barWidth: barWidth, height: height, floor: floor)
    }
}
