import Foundation

// Стиль текста под приложение: в переписке - без точки в конце и с
// маленькой буквы, в письме - строго и полными предложениями, в коде - как
// сказано, без заглавной и точки. Приложение узнаём по тому, какое было
// впереди, когда начали диктовку. Остальные - по общим настройкам чистки.

enum TextStyle: String, Codable, CaseIterable, Identifiable {
    case standard, chat, formal, code

    var id: String { rawValue }

    var title: String {
        switch self {
        case .standard: return "Обычный"
        case .chat: return "Переписка"
        case .formal: return "Письмо"
        case .code: return "Код"
        }
    }

    var detail: String {
        switch self {
        case .standard: return "Как в общих настройках чистки."
        case .chat: return "С маленькой буквы, без точки в конце — как пишут в мессенджерах."
        case .formal: return "С заглавной и точкой, строгая чистка паразитов и оборотов."
        case .code: return "Диктовка кода: «равно», «точка», «скобки» — знаками, английские слова — в имя camelCase. «Комментарий …» — строка после //."
        }
    }

    /// Пример - чтобы выбрать, не читая описаний.
    var sample: String {
        switch self {
        case .standard: return "Скину ссылку вечером."
        case .chat: return "скину ссылку вечером"
        case .formal: return "Скину ссылку вечером."
        case .code: return "let userName = \"Роман\""
        }
    }

    /// Общие настройки чистки - под этот стиль.
    func adjust(_ base: CleanupOptions) -> CleanupOptions {
        var o = base
        switch self {
        case .standard:
            break
        case .chat:
            o.capitalize = false
            o.trailingPeriod = false
        case .formal:
            o.capitalize = true
            o.trailingPeriod = true
            o.removeRepeats = true
            o.level = .strict
        case .code:
            o.capitalize = false
            o.trailingPeriod = false
            // «равно равно» - это ==, а не повтор.
            o.removeRepeats = false
        }
        return o
    }

    /// Пробел после вставки - в коде мешает.
    var addsSpace: Bool { self != .code }

    /// Убрать точку с конца и заглавную с начала уже готового текста -
    /// GigaAM ставит точку сам, чистка её только не дописывает.
    func finish(_ text: String) -> String {
        if self == .code { return CodeSpeech.render(text) }
        guard self == .chat else { return text }
        var s = text
        if s.hasSuffix("."), !s.hasSuffix("..") { s.removeLast() }
        if let first = s.first, first.isUppercase {
            // Аббревиатуры и имена не трогаем: «iOS», «GitHub», «Саша».
            let word = s.prefix { $0.isLetter }
            let isPlainWord = word.count > 1 && word.dropFirst().allSatisfy { $0.isLowercase }
            if isPlainWord && !Self.keepsCapital(String(word)) {
                s = first.lowercased() + s.dropFirst()
            }
        }
        return s
    }

    /// Начало фразы с заглавной по смыслу: «Я» - так и пишут.
    private static func keepsCapital(_ word: String) -> Bool {
        word == "Я"
    }
}

/// Правило: приложение и его стиль.
struct AppStyleRule: Codable, Equatable, Identifiable {
    var bundleID: String
    var name: String
    var style: TextStyle
    var id: String { bundleID }

    /// Что предложить на первом запуске - если такое приложение есть.
    static let suggestions: [AppStyleRule] = [
        AppStyleRule(bundleID: "ru.keepcoder.Telegram", name: "Telegram", style: .chat),
        AppStyleRule(bundleID: "com.apple.MobileSMS", name: "Сообщения", style: .chat),
        AppStyleRule(bundleID: "net.whatsapp.WhatsApp", name: "WhatsApp", style: .chat),
        AppStyleRule(bundleID: "com.tinyspeck.slackmacgap", name: "Slack", style: .chat),
        AppStyleRule(bundleID: "com.apple.mail", name: "Почта", style: .formal),
        AppStyleRule(bundleID: "com.apple.dt.Xcode", name: "Xcode", style: .code),
        AppStyleRule(bundleID: "com.microsoft.VSCode", name: "Visual Studio Code", style: .code),
        AppStyleRule(bundleID: "com.apple.Terminal", name: "Терминал", style: .code),
        AppStyleRule(bundleID: "com.googlecode.iterm2", name: "iTerm", style: .code),
    ]

    static func style(for bundleID: String?, in rules: [AppStyleRule]) -> TextStyle {
        guard let bundleID else { return .standard }
        return rules.first { $0.bundleID == bundleID }?.style ?? .standard
    }
}
