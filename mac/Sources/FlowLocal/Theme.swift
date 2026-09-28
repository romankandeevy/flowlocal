import AppKit
import SwiftUI

// Дизайн-система Northline (v2), перенесённая в SwiftUI. Источник правды -
// tokens.json из _materials/northline-design-system-v2: цвета, шрифтовая
// шкала, отступы, радиусы, тени и движение здесь - те же значения, под
// теми же семантическими именами. В коде экранов - только эти имена,
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

/// Семантические цвета Northline. Светлая тема - значения `:root`, тёмная -
/// `[data-theme="dark"]` из tokens.css.
enum NL {
    // Фоны
    static let canvas = dynamic(hex(0xFDFDFE), hex(0x0D0D0E))
    static let surface = dynamic(hex(0xF8F8F9), hex(0x131415))
    static let subtle = dynamic(hex(0xF1F2F3), hex(0x1C1D1E))
    static let hover = dynamic(black(0.08), white(0.10))
    static let active = dynamic(black(0.12), white(0.15))
    static let selected = dynamic(hex(0xEAF2FE), hex(0x161D28))
    static let disabled = dynamic(hex(0xF1F2F3), hex(0x1C1D1E))

    static let accent = dynamic(hex(0x2D69C0), hex(0x2368C9))
    static let accentHover = dynamic(hex(0x3268B5), hex(0x4F8CE5))
    static let accentActive = dynamic(hex(0x1755AA), hex(0x0853B2))
    static let accentSubtle = dynamic(hex(0xEAF2FE), hex(0x161D28))

    static let success = dynamic(hex(0x007A51), hex(0x007A4D))
    static let successSubtle = dynamic(hex(0xE9F5EF), hex(0x14201B))
    static let warning = dynamic(hex(0xCC8700), hex(0xCF8500))
    static let warningSubtle = dynamic(hex(0xF9F0E5), hex(0x231B11))
    static let danger = dynamic(hex(0xBF3D27), hex(0xC13A24))
    static let dangerSubtle = dynamic(hex(0xFFEDE9), hex(0x271916))
    static let dangerHover = dynamic(hex(0xB03D2A), hex(0xDB614B))
    static let dangerActive = dynamic(hex(0xA8250E), hex(0xA92008))
    static let infoSubtle = dynamic(hex(0xE9F4FA), hex(0x141F24))

    // Текст
    static let textPrimary = dynamic(hex(0x202224), hex(0xE5E8EC))
    static let textSecondary = dynamic(hex(0x4A4D52), hex(0xA6ABB2))
    static let textTertiary = dynamic(hex(0x646970), hex(0x858D97))
    static let textDisabled = dynamic(hex(0xAAAEB4), hex(0x5E646C))
    static let textPlaceholder = dynamic(hex(0x757B83), hex(0x737B86))
    static let textOnAccent = Color.white
    static let textAccent = dynamic(hex(0x2B4D7F), hex(0x85ADE7))
    static let textSuccess = dynamic(hex(0x125B42), hex(0x76BC9E))
    static let textWarning = dynamic(hex(0x6A4400), hex(0xCDA366))
    static let textDanger = dynamic(hex(0x7C3326), hex(0xE39382))
    static let textInfo = dynamic(hex(0x15546E), hex(0x78B4D1))

    // Иконки - те же ступени, что у текста
    static let iconPrimary = textPrimary
    static let iconSecondary = textSecondary
    static let iconTertiary = textTertiary
    static let iconAccent = textAccent

    // Границы: всегда 1pt, полупрозрачные - кроме фокуса и ошибки
    static let border = dynamic(black(0.10), white(0.12))
    static let borderSubtle = dynamic(black(0.06), white(0.06))
    static let borderStrong = dynamic(black(0.18), white(0.18))
    static let borderHover = dynamic(black(0.15), white(0.15))
    static let borderFocus = dynamic(hex(0x2D69C0), hex(0x4F8CE5))
    static let borderDanger = dynamic(hex(0xBF3D27), hex(0xC13A24))
    static let ringFocus = dynamic(hex(0x2D69C0, 0.35), hex(0x4F8CE5, 0.45))

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
            : .system(size: size, weight: weight)
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
    static let page: CGFloat = 24
    static let contentMax: CGFloat = 720
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
    static let sidebar: CGFloat = 220
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
    /// Карточка/регион: surface + граница 1pt, radius-lg, без тени.
    func nlCard(padding: CGFloat? = Space.insetLg) -> some View {
        self.padding(padding ?? 0)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(NL.surface, in: RoundedRectangle(cornerRadius: Radius.lg, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: Radius.lg, style: .continuous)
                    .strokeBorder(NL.border, lineWidth: 1)
            }
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
