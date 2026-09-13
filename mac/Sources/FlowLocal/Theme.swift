import AppKit
import SwiftUI

// Дизайн-система Apple System Dark (prog/_materials/Apple Design system,
// «macOS utility hub · dark only»). Apple документирует цвета ролями, а не
// hex, но приложение всегда тёмное - поэтому роли тёмной темы измерены и
// зафиксированы здесь один раз. Правила, которые держат токены:
//   - глубина - уровнем фона (#000 -> #1C1C1E -> #2C2C2E -> #3A3A3C), а не
//     рамкой и не тенью: карточке на чёрном граница не нужна;
//   - один акцент на экран - systemBlue для интерактива; состояние -
//     green / orange / red; yellow и mint текстом не бывают;
//   - смысл несут label и secondaryLabel; tertiary - плейсхолдеры,
//     quaternary - выключенное; серого текста ниже 60 % нет;
//   - SF Pro: 400 для текста, 600 для заголовков и кнопок; без Bold, капса
//     и трекинга вразрядку; SF Mono - только таймеры, цифры табличные;
//   - радиусы по роли: 4 пункт меню, 6 кнопка и поле, 10 поповер, 12 карточка.
struct Palette {
    // Фоны и уровни
    let bg = Color(rgb: 0x000000)           // systemBackground
    let surface = Color(rgb: 0x1C1C1E)      // elevated/1 - карточка
    let surface2 = Color(rgb: 0x2C2C2E)     // elevated/2 - клавиша, поле
    let surface3 = Color(rgb: 0x3A3A3C)     // elevated/3 - наведение
    let gray2 = Color(rgb: 0x636366)        // systemGray2 - выбранный сегмент

    // Fills - подложки контролов поверх любого уровня
    let fill1 = Color(rgb: 0x787880, 0.36)
    let fill2 = Color(rgb: 0x787880, 0.32)
    let fill3 = Color(rgb: 0x787880, 0.24)
    let fill4 = Color(rgb: 0x787880, 0.18)

    // Разделители
    let separator = Color(rgb: 0x545458, 0.65)
    let separatorOpaque = Color(rgb: 0x38383A)   // на #2C2C2E и выше
    let islandEdge = Color(rgb: 0x545458, 0.4)

    // Текст
    let text = Color(rgb: 0xFFFFFF)
    let textMuted = Color(rgb: 0xEBEBF5, 0.6)
    let textTertiary = Color(rgb: 0xEBEBF5, 0.3)
    let textQuaternary = Color(rgb: 0xEBEBF5, 0.18)

    // Системные цвета, тёмные варианты
    let accent = Color(rgb: 0x0A84FF)
    let success = Color(rgb: 0x30D158)
    let warning = Color(rgb: 0xFF9F0A)
    let danger = Color(rgb: 0xFF453A)

    static let dark = Palette()

    /// Подложка под цвет состояния - для тегов и значков.
    func wash(_ color: Color) -> Color { color.opacity(0.18) }
}

private extension Color {
    init(rgb: UInt32, _ alpha: Double = 1) {
        self.init(.sRGB, red: Double((rgb >> 16) & 0xFF) / 255, green: Double((rgb >> 8) & 0xFF) / 255,
                  blue: Double(rgb & 0xFF) / 255, opacity: alpha)
    }
}

// «05 · Радиусы»: 4 - пункт меню, 6 - кнопка и поле, 10 - поповер и окно,
// 12 - лист и карточка; островок и тег - капсула.
enum Radius {
    static let menu: CGFloat = 4
    static let control: CGFloat = 6
    static let popover: CGFloat = 10
    static let card: CGFloat = 12
}

// Сетка 8 pt с шагом 4.
enum Space {
    static let s1: CGFloat = 4
    static let s2: CGFloat = 8
    static let s3: CGFloat = 12
    static let s4: CGFloat = 16
    static let s5: CGFloat = 24
    static let s6: CGFloat = 32
    static let s7: CGFloat = 48
}

// «05 · Метрика»: ряд списка 28, кнопка 22 / 28. Строка заголовка - 52,
// как у окна с унифицированной панелью инструментов.
enum Metric {
    static let toolbar: CGFloat = 52
    static let row: CGFloat = 28
    static let button: CGFloat = 28
    static let buttonSmall: CGFloat = 22
    /// Разделитель строк настроек начинается от текста: поле 16 + плашка 24 + зазор 12.
    static let rowTextInset: CGFloat = 52
}

// «03 · Типографика · SF Pro»: кегль/строка и вес. 13 pt - базовый размер
// интерфейса macOS, 10 pt - нижняя граница и только для служебных меток.
enum TextStyle {
    case largeTitle, title1, title2, title3, headline, body, subheadline, footnote, mono

    var size: CGFloat {
        switch self {
        case .largeTitle: return 26
        case .title1: return 22
        case .title2: return 17
        case .title3: return 15
        case .headline, .body: return 13
        case .subheadline: return 11
        case .footnote: return 10
        case .mono: return 12
        }
    }

    var weight: Font.Weight { self == .headline ? .semibold : .regular }

    /// Межстрочное из таблицы: 26/32, 22/26, 17/22, 15/20, 13/16, 11/14, 10/13.
    var leading: CGFloat {
        switch self {
        case .largeTitle: return 6
        case .title1: return 4
        case .title2, .title3: return 5
        case .headline, .body, .subheadline, .footnote, .mono: return 3
        }
    }

    func font(_ weight: Font.Weight? = nil) -> Font {
        .system(size: size, weight: weight ?? self.weight, design: self == .mono ? .monospaced : .default)
    }
}

extension View {
    /// Текст по шкале: кегль, вес, межстрочное и цвет роли одним вызовом.
    func textStyle(_ style: TextStyle, _ color: Color, weight: Font.Weight? = nil) -> some View {
        font(style.font(weight))
            .foregroundStyle(color)
            .lineSpacing(style.leading)
    }
}

// «05 · Движение»: hover 120 мс ease-out, поповер 250 мс (0.32, 0.72, 0, 1),
// островок - пружина 400 мс с затуханием 0.85.
enum Motion {
    static let hover = Animation.easeOut(duration: 0.12)
    static let press = Animation.spring(response: 0.2, dampingFraction: 0.9)
    static let page = Animation.timingCurve(0.32, 0.72, 0, 1, duration: 0.25)
    static let island = Animation.spring(response: 0.4, dampingFraction: 0.85)
}
