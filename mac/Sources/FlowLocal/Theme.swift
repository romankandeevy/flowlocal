import AppKit
import CoreText
import SwiftUI

// Дизайн-система Verkstad (prog/_materials): швейцарский индустриальный
// брутализм. Правила, которые здесь закреплены токенами:
//   - радиус 0 везде, теней нет - глубина рамкой и шагом фона bg -> surface -> surface-2;
//   - рамки только 1 и 2 px;
//   - один акцентный элемент в зоне видимости; акцент-текст - accentInk, заливка - accent;
//   - приглушённый текст - токен, не opacity;
//   - верхний регистр только в моно-лейблах, бейджах и кнопках.
enum ThemeKind: String, CaseIterable, Identifiable {
    case dark, light

    var id: String { rawValue }
    var title: String { self == .light ? "Светлая" : "Тёмная" }
    var appearance: NSAppearance? { NSAppearance(named: self == .light ? .aqua : .darkAqua) }
    var toggled: ThemeKind { self == .light ? .dark : .light }
    var colorScheme: ColorScheme { self == .light ? .light : .dark }

    static var system: ThemeKind {
        NSApp.effectiveAppearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua ? .dark : .light
    }
}

// tokens/colors.css
struct Palette {
    let bg: Color
    let surface: Color
    let surface2: Color
    let border: Color
    let borderStrong: Color
    let text: Color
    let textMuted: Color
    let textInverse: Color
    let accent: Color
    let accentHover: Color
    let accentText: Color
    let accentInk: Color
    let accentTextMuted: Color
    let success: Color
    let warning: Color
    let danger: Color
    let successBg: Color
    let warningBg: Color
    let dangerBg: Color
    let gridLine: Color

    static let dark = Palette(
        bg: hex(0x0A0A0A), surface: hex(0x141414), surface2: hex(0x1C1C1C),
        border: hex(0x2E2E2E), borderStrong: hex(0x4A4A4A),
        text: hex(0xF2F2F2), textMuted: hex(0x8C8C8C), textInverse: hex(0x0A0A0A),
        accent: hex(0x3A3AFF), accentHover: hex(0x2B2BE6), accentText: hex(0xFFFFFF),
        accentInk: hex(0x7070FF), accentTextMuted: hex(0xC9C9FF),
        success: hex(0x62A280), warning: hex(0xA89F52), danger: hex(0xCC6E6E),
        successBg: hex(0x12201A), warningBg: hex(0x1E1C10), dangerBg: hex(0x231313),
        gridLine: hex(0x1F1F1F))

    static let light = Palette(
        bg: hex(0xFAFAF8), surface: hex(0xFFFFFF), surface2: hex(0xF0F0EE),
        border: hex(0xBFBFB8), borderStrong: hex(0x0A0A0A),
        text: hex(0x0A0A0A), textMuted: hex(0x6B6B6B), textInverse: hex(0xFAFAF8),
        accent: hex(0x1B1BFF), accentHover: hex(0x1414CC), accentText: hex(0xFFFFFF),
        accentInk: hex(0x1B1BFF), accentTextMuted: hex(0xD6D6FF),
        success: hex(0x2F6B4E), warning: hex(0x6E6420), danger: hex(0x9B3B3B),
        successBg: hex(0xEDF2EF), warningBg: hex(0xF2F1E8), dangerBg: hex(0xF4EDED),
        gridLine: hex(0xE4E4E0))

    static func of(_ kind: ThemeKind) -> Palette { kind == .light ? .light : .dark }

    private static func hex(_ v: UInt32) -> Color {
        Color(.sRGB, red: Double((v >> 16) & 0xFF) / 255, green: Double((v >> 8) & 0xFF) / 255,
              blue: Double(v & 0xFF) / 255, opacity: 1)
    }
}

// tokens/spacing.css + borders.css: база 8, две толщины рамки.
enum Space {
    static let s1: CGFloat = 4
    static let s2: CGFloat = 8
    static let s3: CGFloat = 12
    static let s4: CGFloat = 16
    static let s5: CGFloat = 24
    static let s6: CGFloat = 32
    static let s7: CGFloat = 48

    static let controlSm: CGFloat = 32
    static let controlMd: CGFloat = 40

    static let hairline: CGFloat = 1
    static let strong: CGFloat = 2
}

// tokens/typography.css: шкала 1.333 от 14.
enum FontSize {
    static let fs1: CGFloat = 12
    static let fs2: CGFloat = 14
    static let fs3: CGFloat = 16
    static let fs4: CGFloat = 21
    static let fs5: CGFloat = 28
    static let fs6: CGFloat = 37
    static let mono: CGFloat = 11
    static let monoLg: CGFloat = 12
}

// tokens/motion.css: одна кривая, механическая и резкая.
enum Motion {
    static let instant = Animation.timingCurve(0.7, 0, 0.2, 1, duration: 0.09)
    static let base = Animation.timingCurve(0.7, 0, 0.2, 1, duration: 0.18)
    static let shutter = Animation.timingCurve(0.7, 0, 0.2, 1, duration: 0.4)
}

// Unbounded - только H1/H2 и крупные цифры; Inter - весь текст и кнопки;
// JetBrains Mono - лейблы, метки, числа. Имя семейства берём из самого файла:
// угаданное имя SwiftUI молча подменил бы системным шрифтом. Файла нет -
// останется запасное имя и системный шрифт, приложение от этого не падает.
enum Fonts {
    // nil - файла нет, берём системный шрифт того же веса (SF близок к Inter).
    private(set) static var displayFamily: String?
    private(set) static var textFamily: String?
    private(set) static var monoFamily: String?

    static func register() {
        displayFamily = register("Unbounded-Variable")
        textFamily = register("Inter-Variable")
        monoFamily = register("JetBrainsMono-Variable")
    }

    private static func register(_ file: String) -> String? {
        guard let url = Bundle.main.url(forResource: file, withExtension: "ttf", subdirectory: "Fonts") else {
            return nil
        }
        CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
        guard let descriptors = CTFontManagerCreateFontDescriptorsFromURL(url as CFURL) as? [CTFontDescriptor],
              let first = descriptors.first else { return nil }
        return CTFontDescriptorCopyAttribute(first, kCTFontFamilyNameAttribute) as? String
    }

    static func display(_ size: CGFloat, _ weight: Font.Weight = .black) -> Font {
        displayFamily.map { .custom($0, size: size).weight(weight) } ?? .system(size: size, weight: weight)
    }

    static func text(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        textFamily.map { .custom($0, size: size).weight(weight) } ?? .system(size: size, weight: weight)
    }

    static func mono(_ size: CGFloat, _ weight: Font.Weight = .medium) -> Font {
        monoFamily.map { .custom($0, size: size).weight(weight) }
            ?? .system(size: size, weight: weight, design: .monospaced)
    }
}

extension View {
    /// Моно-лейбл Verkstad: 11 px, верхний регистр, трекинг 0.12em.
    func monoLabel(_ color: Color, size: CGFloat = FontSize.mono) -> some View {
        font(Fonts.mono(size))
            .tracking(size * 0.12)
            .textCase(.uppercase)
            .foregroundStyle(color)
    }

    /// Заголовок display: Unbounded, трекинг -0.03em.
    func displayTitle(_ color: Color, size: CGFloat, weight: Font.Weight = .black) -> some View {
        font(Fonts.display(size, weight))
            .tracking(size * -0.03)
            .foregroundStyle(color)
    }
}
