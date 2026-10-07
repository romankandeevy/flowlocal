import AppKit
import SwiftUI

// Тема FlowLocal (2026-10): почти белый фон и нейтральный графит, контрастный
// текст, яркий зелёный акцент, шрифт Onest. Имена токенов прежние (NL), поэтому
// экраны и компоненты меняются вместе. В коде экранов - только эти имена,
// никаких «сырых» цветов и размеров шрифта.

// MARK: - цвет

private func dynamic(_ light: NSColor, _ dark: NSColor) -> Color {
    Color(nsColor: NSColor(name: nil) { appearance in
        (appearance.bestMatch(from: [.aqua, .darkAqua]) ?? .aqua) == .darkAqua ? dark : light
    })
}

private func hex(_ value: UInt32, _ alpha: CGFloat = 1) -> NSColor {
    NSColor(srgbRed: CGFloat((value >> 16) & 0xFF) / 255,
            green: CGFloat((value >> 8) & 0xFF) / 255,
            blue: CGFloat(value & 0xFF) / 255,
            alpha: alpha)
}

private func black(_ a: CGFloat) -> NSColor { NSColor(srgbRed: 0, green: 0, blue: 0, alpha: a) }
private func white(_ a: CGFloat) -> NSColor { NSColor(srgbRed: 1, green: 1, blue: 1, alpha: a) }

private func ink(_ a: CGFloat) -> NSColor { NSColor(srgbRed: 0, green: 0, blue: 0, alpha: a) }
private func glow(_ a: CGFloat) -> NSColor { NSColor(srgbRed: 1, green: 1, blue: 1, alpha: a) }

/// Семантические цвета. Светлая тема - почти белая, без желтизны; тёмная -
/// нейтральный графит. Акцент - яркий зелёный.
enum NL {
    // Фоны: canvas - страница, surface - карточки, sidebar - левая колонка
    static let canvas = dynamic(hex(0xF6F6F4), hex(0x111113))
    static let surface = dynamic(hex(0xFFFFFF), hex(0x1C1C1F))
    static let sidebar = dynamic(hex(0xEEEEEC), hex(0x0C0C0E))
    static let subtle = dynamic(hex(0xEEEEEC), hex(0x26262A))
    static let hover = dynamic(ink(0.05), glow(0.06))
    static let active = dynamic(ink(0.09), glow(0.10))
    static let rowHover = dynamic(hex(0xFAFAF9), hex(0x222225))
    static let selected = dynamic(hex(0xE3F6EA), hex(0x12281C))
    static let disabled = dynamic(hex(0xEEEEEC), hex(0x26262A))
    static let popover = dynamic(hex(0xFFFFFF), hex(0x26262A))
    static let chartBar = dynamic(hex(0xE2E3E0), hex(0x2D2D31))
    static let chartBarHover = dynamic(hex(0xCBCDC9), hex(0x424247))

    static let accent = dynamic(hex(0x0FA84F), hex(0x3DEB8C))
    static let accentHover = dynamic(hex(0x12B957), hex(0x5FF0A1))
    static let accentActive = dynamic(hex(0x0C9045), hex(0x2FD27A))
    static let accentSubtle = dynamic(hex(0xE3F6EA), hex(0x12281C))

    static let success = accent
    static let successSubtle = accentSubtle
    static let warning = dynamic(hex(0xD18A16), hex(0xEBB55A))
    static let warningSubtle = dynamic(hex(0xFBF1DF), hex(0x2A2216))
    static let danger = dynamic(hex(0xC2410C), hex(0xF59A6B))
    static let dangerSubtle = dynamic(hex(0xFCEBE3), hex(0x2C1C15))
    static let dangerHover = dynamic(hex(0xAD3A0B), hex(0xF8AE87))
    static let dangerActive = dynamic(hex(0x96320A), hex(0xE88A5C))
    static let infoSubtle = accentSubtle

    // Текст
    static let textPrimary = dynamic(hex(0x16161A), hex(0xF4F4F5))
    static let textSecondary = dynamic(hex(0x54555B), hex(0xB8B8BE))
    static let textTertiary = dynamic(hex(0x727379), hex(0x8E8E95))
    static let textQuaternary = dynamic(hex(0x8C8D92), hex(0x76767D))
    static let textDisabled = dynamic(hex(0xB9BABD), hex(0x55555B))
    static let textPlaceholder = textQuaternary
    static let textOnAccent = dynamic(hex(0xFFFFFF), hex(0x021409))
    /// Зелёный текстом - на белом чуть темнее заливки, чтобы читался.
    static let textAccent = dynamic(hex(0x0B8E42), hex(0x3DEB8C))
    static let textSuccess = textAccent
    static let textWarning = dynamic(hex(0x9A5B0B), hex(0xEBB55A))
    static let textDanger = danger
    static let textInfo = textAccent

    // Иконки - те же ступени, что у текста
    static let iconPrimary = textPrimary
    static let iconSecondary = textSecondary
    static let iconTertiary = textTertiary
    static let iconAccent = textAccent

    // Границы: полупрозрачные нейтральные - кроме фокуса и ошибки
    static let border = dynamic(ink(0.10), glow(0.10))
    static let borderSubtle = dynamic(hex(0xEDEDEB), hex(0x27272B))
    static let borderStrong = dynamic(ink(0.18), glow(0.18))
    static let borderHover = dynamic(ink(0.15), glow(0.15))
    static let borderFocus = accent
    static let borderDanger = danger
    static let ringFocus = dynamic(hex(0x0FA84F, 0.28), hex(0x3DEB8C, 0.32))
    static let sidebarBorder = dynamic(hex(0xE2E2DF), hex(0x232326))

    /// Тонкий верхний блик поднятых поверхностей - только в тёмной теме.
    static let raisedHighlight = dynamic(white(0), white(0.04))
}

// MARK: - шрифт

/// Шкала Northline: размер / межстрочный / трекинг / насыщенность. Один
/// шрифт на всё - системный; моно - только для цифр и сочетаний клавиш.
enum NLType {
    case display, headingLg, heading, headingSm, headingXs
    case bodyLg, body, bodySm, label, labelSm, caption, labelXs, overline, numeric

    var size: CGFloat {
        switch self {
        case .display: return 40
        case .headingLg: return 24
        case .heading: return 20
        case .headingSm, .bodyLg: return 16
        case .headingXs, .body, .numeric: return 14
        case .bodySm, .label: return 13
        case .labelSm, .caption: return 12
        case .labelXs, .overline: return 11
        }
    }

    var lineHeight: CGFloat {
        switch self {
        case .display: return 44
        case .headingLg: return 28.8
        case .heading: return 25
        case .headingSm: return 22.4
        case .bodyLg: return 24.8
        case .headingXs: return 19.6
        case .body, .numeric: return 21.7
        case .bodySm: return 19.5
        case .label: return 15.6
        case .labelSm: return 14.4
        case .caption: return 16.8
        case .labelXs, .overline: return 13.2
        }
    }

    /// Трекинг в em, как в tokens.json.
    var trackingEm: CGFloat {
        switch self {
        case .display: return -0.02
        case .headingLg: return -0.015
        case .heading: return -0.01
        case .headingSm, .headingXs: return -0.005
        case .labelSm: return 0.005
        case .labelXs: return 0.01
        case .overline: return 0.04
        default: return 0
        }
    }

    var weight: Font.Weight {
        switch self {
        case .display, .headingLg, .heading, .headingSm, .headingXs: return .semibold
        case .label, .labelSm, .labelXs, .overline: return .medium
        default: return .regular
        }
    }

    var font: Font {
        self == .numeric
            ? .system(size: size, weight: weight, design: .monospaced)
            : NLFont.ui(size, weight)
    }
}

/// Onest лежит в Resources/Fonts и регистрируется при запуске; нет файла -
/// системный шрифт, вид тот же по размерам.
enum NLFont {
    static let family = "Onest"
    private static var registered = false

    static func register() {
        guard !registered, let url = Bundle.main.url(forResource: "Onest", withExtension: "ttf",
                                                    subdirectory: "Fonts") else { return }
        registered = CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
            || NSFont(name: family, size: 12) != nil
    }

    static func ui(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        registered ? .custom(family, size: size).weight(weight) : .system(size: size, weight: weight)
    }
}

extension View {
    /// Стиль текста из шкалы: шрифт, трекинг и межстрочный разом.
    func nlType(_ style: NLType) -> some View {
        font(style.font)
            .tracking(style.size * style.trackingEm)
            .lineSpacing(max(0, style.lineHeight - style.size * 1.2))
            .textCase(style == .overline ? .uppercase : nil)
    }
}

// MARK: - отступы, радиусы, размеры

/// Шаг 4pt. На экран - два ритма: плотный внутри группы (stackSm) и
/// свободный между группами (stackLg).
enum Space {
    static let s0_5: CGFloat = 2
    static let s1: CGFloat = 4
    static let s1_5: CGFloat = 6
    static let s2: CGFloat = 8
    static let s3: CGFloat = 12
    static let s4: CGFloat = 16
    static let s5: CGFloat = 20
    static let s6: CGFloat = 24
    static let s8: CGFloat = 32
    static let s12: CGFloat = 48

    static let insetSm: CGFloat = 12
    static let insetMd: CGFloat = 16
    static let insetLg: CGFloat = 20
    static let stackXs: CGFloat = 4
    static let stackSm: CGFloat = 8
    static let stackMd: CGFloat = 16
    static let stackLg: CGFloat = 24
    static let inlineSm: CGFloat = 8
    static let inlineMd: CGFloat = 12
    /// Поля страницы в приложении.
    static let page: CGFloat = 40
    static let contentMax: CGFloat = 760
}

enum Radius {
    static let xs: CGFloat = 4
    static let sm: CGFloat = 6
    static let md: CGFloat = 8
    static let lg: CGFloat = 10
    static let xl: CGFloat = 12
}

enum Size {
    static let controlSm: CGFloat = 28
    static let controlMd: CGFloat = 32
    static let control2xs: CGFloat = 20
    static let iconSm: CGFloat = 16
    static let iconMd: CGFloat = 20
    static let iconXl: CGFloat = 32
    static let rowHeight: CGFloat = 44
    static let sidebar: CGFloat = 228
}

// MARK: - тени

/// Тени Northline: нейтральные, двуслойные, размытие не больше 24pt. У
/// карточки тени нет никогда - только у всплывающего.
enum NLShadow { case xs, md, lg, xl }

extension View {
    @ViewBuilder
    func nlShadow(_ level: NLShadow) -> some View {
        switch level {
        case .xs:
            shadow(color: .black.opacity(0.06), radius: 1, y: 1)
        case .md:
            shadow(color: .black.opacity(0.08), radius: 2, y: 2)
                .shadow(color: .black.opacity(0.10), radius: 4, y: 4)
        case .lg:
            shadow(color: .black.opacity(0.10), radius: 4, y: 4)
                .shadow(color: .black.opacity(0.16), radius: 8, y: 8)
        case .xl:
            shadow(color: .black.opacity(0.12), radius: 8, y: 8)
                .shadow(color: .black.opacity(0.18), radius: 12, y: 16)
        }
    }
}

// MARK: - поверхности

extension View {
    /// Карточка: surface, тонкая тёплая граница и едва заметная тень под
    /// формой (тень у фигуры, а не у содержимого - дёшево при прокрутке).
    func nlCard(padding: CGFloat? = Space.insetLg, radius: CGFloat = 14) -> some View {
        let shape = RoundedRectangle(cornerRadius: radius, style: .continuous)
        return self.padding(padding ?? 0)
            .frame(maxWidth: .infinity, alignment: .leading)
            .clipShape(shape)
            .background {
                shape.fill(NL.surface)
                    .shadow(color: .black.opacity(0.05), radius: 1.5, y: 1)
            }
            .overlay { shape.strokeBorder(NL.border, lineWidth: 1) }
    }

    /// Всплывающее: surface + граница + тень уровня и блик сверху в тёмной теме.
    func nlRaised(_ level: NLShadow, radius: CGFloat = Radius.lg) -> some View {
        background(NL.surface, in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .strokeBorder(NL.border, lineWidth: 1)
            }
            .overlay(alignment: .top) {
                NL.raisedHighlight.frame(height: 1).padding(.horizontal, radius)
            }
            .nlShadow(level)
    }
}

// MARK: - движение

/// Движение - пружины без отскока: быстро стартуют и мягко садятся, а
/// прерванная на середине анимация продолжается от текущей скорости, без рывка.
/// Наведение и нажатие - самые короткие, окна и разделы - длиннее.
enum Motion {
    static let fast = Animation.spring(response: 0.18, dampingFraction: 1)
    static let base = Animation.spring(response: 0.26, dampingFraction: 0.95)
    static let moderate = Animation.spring(response: 0.32, dampingFraction: 0.9)
    static let slow = Animation.spring(response: 0.45, dampingFraction: 0.9)
    /// Смена положения (индикатор вкладки) - с лёгкой живостью.
    static let position = Animation.spring(response: 0.3, dampingFraction: 0.82)
    /// Появление всплывающего (капсула записи).
    static let pop = Animation.spring(response: 0.34, dampingFraction: 0.72)
}

extension View {
    func motion<V: Equatable>(_ animation: Animation = Motion.moderate, value: V) -> some View {
        modifier(MotionModifier(animation: animation, value: value))
    }
}

private struct MotionModifier<V: Equatable>: ViewModifier {
    let animation: Animation
    let value: V
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func body(content: Content) -> some View {
        content.animation(reduceMotion ? nil : animation, value: value)
    }
}

/// withAnimation с оглядкой на «Уменьшить движение».
func withMotion<Result>(_ animation: Animation = Motion.moderate, _ body: () throws -> Result) rethrows -> Result {
    try withAnimation(NSWorkspace.shared.accessibilityDisplayShouldReduceMotion ? nil : animation, body)
}
