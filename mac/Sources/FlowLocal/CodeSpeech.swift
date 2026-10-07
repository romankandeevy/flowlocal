import Foundation

// Стиль «Код»: продиктованное - в код. Работает по тексту, который уже
// распознан (в коде его собирают две модели, см. backend/server.py,
// merge_code): русские слова там от GigaAM, английские - от Parakeet.
//
//   «let greeting равно кавычки привет кавычки»  → let greeting = "привет"
//   «func load profile скобки открыть фигурную»   → func loadProfile() {
//   «snake case user id равно 42»                 → user_id = 42
//   «комментарий проверить, что профиль загружен» → // проверить, что профиль загружен
//
// Правила:
// - знаки препинания, которые модель ставит сама, убираются: в коде знаки
//   говорят словами («точка», «запятая», «dot», «comma»);
// - подряд идущие английские слова склеиваются в одно имя - camelCase по
//   умолчанию, другой регистр задаёт команда перед именем («снейк кейс»,
//   «паскаль кейс», «кебаб кейс», «капс», «слитно»); ключевые слова языков
//   («let», «return», «func», «def»…) остаются отдельными;
// - русские слова не склеиваются - это строки и комментарии;
// - фраза, начатая словом «комментарий» / «comment», - обычный текст после //.
enum CodeSpeech {
    enum Casing { case camel, pascal, snake, kebab, screaming, flat }

    // MARK: - словарь

    /// Знак и как он стоит: пробел до / после. nil - как у слова.
    private struct Sym {
        let text: String
        let before: Bool?
        let after: Bool?
    }

    private static func op(_ t: String) -> Sym { Sym(text: t, before: true, after: true) }
    private static func glued(_ t: String) -> Sym { Sym(text: t, before: false, after: false) }

    /// Фразы → знаки. Русские - в тех формах, в каких их пишет GigaAM.
    private static let symbols: [([String], Sym)] = {
        var list: [(String, Sym)] = []
        func add(_ s: Sym, _ phrases: String...) { for p in phrases { list.append((p, s)) } }

        add(op("=="), "равно равно", "двойное равно", "double equals", "equals equals", "equal equal")
        add(op("!="), "не равно", "not equal", "not equals", "not equal to")
        add(op(">="), "больше или равно", "greater or equal", "greater than or equal", "greater than or equal to")
        add(op("<="), "меньше или равно", "less or equal", "less than or equal", "less than or equal to")
        add(op("+="), "плюс равно", "plus equals")
        add(op("-="), "минус равно", "minus equals")
        add(op("="), "равно", "равняется", "присвоить", "equals", "equal", "equal sign")
        add(op("+"), "плюс", "plus")
        add(op("-"), "минус", "minus")
        add(op("*"), "умножить на", "умножить", "times", "multiplied by")
        add(op("/"), "разделить на", "делить на", "разделить", "divided by")
        add(op("%"), "остаток от деления", "modulo")
        add(op(">"), "больше чем", "больше", "greater than")
        add(op("<"), "меньше чем", "меньше", "less than")
        add(op("=>"), "жирная стрелка", "fat arrow")
        add(op("->"), "стрелка", "стрелочка", "arrow")
        add(op("&&"), "и и", "логическое и", "and and", "double and")
        add(op("||"), "или или", "логическое или", "or or", "double or")

        add(Sym(text: "()", before: false, after: nil), "пустые скобки", "скобки", "empty parens", "parens", "parentheses", "open close parent", "empty parents")
        add(Sym(text: "(", before: false, after: false),
            "открыть круглую скобку", "открыть скобку", "открыть скобки", "открывающая скобка", "скобка открывается",
            "open paren", "open parenthesis", "left paren", "open parentheses", "open parent", "open parents")
        add(Sym(text: ")", before: false, after: nil),
            "закрыть круглую скобку", "закрыть скобку", "закрыть скобки", "закрывающая скобка", "скобка закрывается",
            "close paren", "close parenthesis", "right paren", "close parentheses", "close parent", "close parents")
        add(Sym(text: "[", before: false, after: false),
            "открыть квадратную скобку", "квадратная скобка открывается", "open square bracket", "open bracket", "left bracket")
        add(Sym(text: "]", before: false, after: nil),
            "закрыть квадратную скобку", "квадратная скобка закрывается", "close square bracket", "close bracket", "right bracket")
        add(Sym(text: "{", before: true, after: nil),
            "открыть фигурную скобку", "открыть фигурную", "фигурная скобка открывается", "open curly brace", "open curly", "open brace")
        add(Sym(text: "}", before: nil, after: nil),
            "закрыть фигурную скобку", "закрыть фигурную", "фигурная скобка закрывается", "close curly brace", "close curly", "close brace")

        add(Sym(text: ";", before: false, after: true), "точка с запятой", "semicolon")
        add(glued("."), "точка", "точку", "dot")
        add(Sym(text: ",", before: false, after: true), "запятая", "запятую", "comma")
        add(Sym(text: ":", before: false, after: true), "двоеточие", "colon")
        add(Sym(text: "?", before: false, after: nil), "вопросительный знак", "знак вопроса", "question mark")
        add(Sym(text: "!", before: nil, after: false), "восклицательный знак", "восклицательный", "bang", "exclamation mark")
        add(glued("_"), "нижнее подчёркивание", "нижнее подчеркивание", "подчёркивание", "подчеркивание", "underscore")
        add(glued("\\"), "обратный слэш", "обратный слеш", "бэкслэш", "бэкслеш", "backslash")
        add(glued("/"), "слэш", "слеш", "slash")
        add(glued("-"), "дефис", "тире", "dash", "hyphen")
        add(glued("\n"), "новая строка", "с новой строки", "новую строку", "new line", "newline")
        add(Sym(text: "@", before: nil, after: false), "собака", "собачка", "at sign")
        add(Sym(text: "#", before: nil, after: false), "решётка", "решетка", "hash sign", "hashtag", "pound sign")
        add(Sym(text: "$", before: nil, after: false), "доллар", "dollar sign", "dollar")
        add(op("&"), "амперсанд", "ampersand")
        add(op("|"), "вертикальная черта", "pipe")
        add(glued("~"), "тильда", "tilde")
        add(glued("`"), "обратная кавычка", "backtick")
        add(glued(" "), "пробел", "space")

        // Длинные фразы раньше коротких: «равно равно» раньше «равно».
        return list.map { ($0.0.split(separator: " ").map(String.init), $0.1) }
            .sorted { $0.0.count > $1.0.count }
    }()

    /// Кавычки - отдельно: открывающая и закрывающая стоят по-разному.
    private static let doubleQuote: Set<String> = ["кавычка", "кавычки", "кавычку", "кавычек", "quote", "quotes"]
    private static let singleQuote: [[String]] = [["одинарная", "кавычка"], ["одинарные", "кавычки"], ["одинарную", "кавычку"],
                                                  ["апостроф"], ["single", "quote"], ["apostrophe"]]

    /// Команды регистра: первое слово × второе - так ловим и кривые
    /// варианты распознавания («Camel Keys», «Camil Kays», «кэмел кейс»).
    private static let caseWord: Set<String> = ["case", "keys", "kays", "cases", "kase", "кейс", "кейз", "кэйс", "кейсом"]
    private static let casingHeads: [(Set<String>, Casing)] = [
        (["camel", "camil", "camal", "кэмел", "кемел", "камел", "кэмэл", "кэмл", "кемэл"], .camel),
        (["pascal", "паскаль", "паскал"], .pascal),
        (["snake", "snak", "снейк", "снэйк", "снек", "снэк"], .snake),
        (["kebab", "кебаб", "кебап"], .kebab),
    ]
    private static let casingSingle: [String: Casing] = [
        "капс": .screaming, "капсом": .screaming, "константа": .screaming, "constant": .screaming,
        "слитно": .flat, "одним": .flat,
    ]
    private static let casingPairs: [[String]: Casing] = [
        ["all", "caps"]: .screaming, ["upper", "case"]: .screaming, ["одним", "словом"]: .flat, ["one", "word"]: .flat,
    ]

    /// Ключевые слова популярных языков - не склеиваются с именем рядом.
    static let keywords: Set<String> = [
        "let", "var", "func", "return", "if", "else", "for", "in", "while", "do", "switch", "case", "default",
        "break", "continue", "class", "struct", "enum", "protocol", "extension", "import", "guard", "self",
        "true", "false", "nil", "null", "none", "def", "const", "function", "async", "await", "try", "catch",
        "throw", "throws", "public", "private", "static", "final", "void", "new", "this", "super", "from", "as",
        "is", "not", "and", "or", "with", "yield", "lambda", "pass", "raise", "except", "elif", "val", "fun",
        "package", "interface", "implements", "extends", "export", "fn", "mut", "pub", "impl", "use", "match",
        "where", "type", "of", "to", "at", "on", "by", "go", "defer", "select", "inout", "some", "any",
        "override", "init", "deinit", "lazy", "weak", "get", "set", "where", "echo", "sudo", "git", "npm",
        "cd", "ls", "rm", "mkdir", "the", "a", "an",
    ]

    private static let commentHeads: Set<String> = ["комментарий", "коммент", "комментарии", "comment"]

    // MARK: - разбор

    private enum Piece {
        case word(String)       // английское слово - кандидат в имя
        case text(String)       // русское слово, число, всё прочее - как есть
        case sym(Sym)
        case quote(single: Bool)
        case casing(Casing)
    }

    static func render(_ input: String) -> String {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return trimmed }

        // «Комментарий …» - обычный текст после //, знаки модели остаются.
        let firstWord = trimmed.prefix { $0.isLetter }.lowercased()
        if commentHeads.contains(firstWord) {
            var rest = trimmed.dropFirst(firstWord.count).drop { !$0.isLetter && !$0.isNumber }
            if rest.hasSuffix("."), !rest.hasSuffix("..") { rest = rest.dropLast() }
            return rest.isEmpty ? "//" : "// " + rest
        }

        let words = tokenize(trimmed)
        let parts = pieces(words)
        // Ни английского, ни команд кода - это просьба словами (чат с ИИ в
        // редакторе, сообщение коммита): текст как сказан, со знаками.
        let isProse = !parts.contains { if case .text = $0 { return false } else { return true } }
        if isProse {
            var t = trimmed
            if t.hasSuffix("."), !t.hasSuffix("..") { t.removeLast() }
            if let first = t.first, first.isUppercase, t.dropFirst().prefix(1).allSatisfy({ $0.isLowercase }) {
                t = first.lowercased() + t.dropFirst()
            }
            return t
        }
        return join(parts)
    }

    /// Слова без знаков, которые поставила модель. Регистр - строчный, кроме
    /// аббревиатур (URL, JSON, iOS): у них заглавных больше одной.
    static func tokenize(_ s: String) -> [String] {
        let strip = CharacterSet(charactersIn: ".,!?;:…«»\"“”()")
        return s.split(whereSeparator: { $0.isWhitespace }).compactMap { raw in
            let w = raw.trimmingCharacters(in: strip)
            guard !w.isEmpty else { return nil }
            let upper = w.filter { $0.isUppercase }.count
            return upper >= 2 ? w : w.lowercased()
        }
    }

    private static func pieces(_ words: [String]) -> [Piece] {
        var out: [Piece] = []
        var i = 0
        func lower(_ k: Int) -> String { words[k].lowercased() }
        outer: while i < words.count {
            // Регистр: «camel case», «капс», «одним словом».
            if i + 1 < words.count {
                for (heads, casing) in casingHeads where heads.contains(lower(i)) && caseWord.contains(lower(i + 1)) {
                    out.append(.casing(casing)); i += 2; continue outer
                }
                if let c = casingPairs[[lower(i), lower(i + 1)]] { out.append(.casing(c)); i += 2; continue }
            }
            if let c = casingSingle[lower(i)] { out.append(.casing(c)); i += 1; continue }
            // Кавычки.
            for q in singleQuote where matches(q, words, at: i) {
                out.append(.quote(single: true)); i += q.count; continue outer
            }
            if matches(["double", "quote"], words, at: i) { out.append(.quote(single: false)); i += 2; continue }
            if doubleQuote.contains(lower(i)) { out.append(.quote(single: false)); i += 1; continue }
            // Знаки.
            for (phrase, sym) in symbols where matches(phrase, words, at: i) {
                out.append(.sym(sym)); i += phrase.count; continue outer
            }
            let w = words[i]
            out.append(isLatin(w) ? .word(w) : .text(w))
            i += 1
        }
        return out
    }

    private static func matches(_ phrase: [String], _ words: [String], at i: Int) -> Bool {
        guard i + phrase.count <= words.count else { return false }
        for (k, p) in phrase.enumerated() where words[i + k].lowercased() != p { return false }
        return true
    }

    private static func isLatin(_ w: String) -> Bool {
        w.unicodeScalars.contains { ("a"..."z").contains($0) || ("A"..."Z").contains($0) }
            && !w.unicodeScalars.contains { (0x0400...0x04FF).contains(Int($0.value)) }
    }

    // MARK: - сборка

    /// Кусок выхода и как он стыкуется с соседями.
    private struct Out {
        var text: String
        var before: Bool?
        var after: Bool?
    }

    private static func join(_ pieces: [Piece]) -> String {
        var outs: [Out] = []
        var pending: Casing?
        var name: [String] = []
        var inQuote: (Bool, Bool) = (false, false)   // внутри "…", внутри '…'

        func flushName() {
            guard !name.isEmpty else { return }
            outs.append(Out(text: apply(pending ?? .camel, name), before: nil, after: nil))
            name.removeAll()
            pending = nil
        }

        for p in pieces {
            switch p {
            case .casing(let c):
                flushName()
                pending = c
            case .word(let w):
                let quoted = inQuote.0 || inQuote.1
                if quoted {
                    // В строке слова - как сказаны, через пробел.
                    flushName()
                    outs.append(Out(text: w, before: nil, after: nil))
                } else if pending == nil && keywords.contains(w.lowercased()) {
                    flushName()
                    outs.append(Out(text: w, before: nil, after: nil))
                } else {
                    name.append(w)
                }
            case .text(let t):
                flushName()
                outs.append(Out(text: t, before: nil, after: nil))
            case .sym(let s):
                flushName()
                outs.append(Out(text: s.text, before: s.before, after: s.after))
            case .quote(let single):
                flushName()
                let ch = single ? "'" : "\""
                let open = single ? !inQuote.1 : !inQuote.0
                if single { inQuote.1.toggle() } else { inQuote.0.toggle() }
                outs.append(open ? Out(text: ch, before: nil, after: false) : Out(text: ch, before: false, after: nil))
            }
        }
        flushName()

        var s = ""
        for (k, o) in outs.enumerated() {
            if k > 0 {
                let prev = outs[k - 1]
                let space: Bool
                // Знак, приклеенный с любой стороны, побеждает: «a.b», «f(x)».
                space = !(prev.after == false || o.before == false)
                if space { s += " " }
            }
            s += o.text
        }
        return s
    }

    static func apply(_ casing: Casing, _ words: [String]) -> String {
        let parts = words.flatMap { $0.split(separator: "-").map(String.init) }.filter { !$0.isEmpty }
        func cap(_ w: String) -> String { w.prefix(1).uppercased() + w.dropFirst() }
        func low(_ w: String) -> String { w.filter { $0.isUppercase }.count >= 2 ? w : w.lowercased() }
        switch casing {
        case .camel:
            guard let first = parts.first else { return "" }
            return low(first) + parts.dropFirst().map { cap(low($0)) }.joined()
        case .pascal: return parts.map { cap(low($0)) }.joined()
        case .snake: return parts.map { $0.lowercased() }.joined(separator: "_")
        case .kebab: return parts.map { $0.lowercased() }.joined(separator: "-")
        case .screaming: return parts.map { $0.uppercased() }.joined(separator: "_")
        case .flat: return parts.map { $0.lowercased() }.joined()
        }
    }
}
