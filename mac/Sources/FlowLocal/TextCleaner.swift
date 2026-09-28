import Foundation

// Чистка диктовки без нейросетей: правила по словам и знакам препинания.
// GigaAM v3 e2e ставит запятые и точки сам, и слово-паразит почти всегда
// отбито ими: «Ну, короче, я типа хотел…». Поэтому опасные слова («вот»,
// «ну», «значит», «это») убираем только там, где они стоят вставкой - между
// границами (начало фразы, запятая, точка), а слова со значением - в
// обычной речи - остаются: «вот этот файл», «значит, так» → «вот этот
// файл», «так». Безопасные («э-э», «типа», «как бы», «короче») - везде, кроме
// известных оборотов со значением («какого типа», «как бы не», «короче, чем»).

enum CleanupLevel: String, CaseIterable, Identifiable {
    case off, hesitations, fillers, strict

    var id: String { rawValue }
    var title: String {
        switch self {
        case .off: return "Выкл."
        case .hesitations: return "Заминки"
        case .fillers: return "Паразиты"
        case .strict: return "Строго"
        }
    }

    var detail: String {
        switch self {
        case .off: return "Текст остаётся как распознан."
        case .hesitations: return "Убираются «э-э», «эм», «ммм», растянутые «и-и-и» и повторы."
        case .fillers: return "Плюс «ну», «типа», «как бы», «короче», «вот», «значит», «в общем», «ты понял»."
        case .strict: return "Плюс мат-междометия и обороты: «в принципе», «на самом деле», «получается», «собственно»."
        }
    }
}

struct CleanupOptions: Equatable {
    var level: CleanupLevel = .fillers
    var removeRepeats = true
    var capitalize = true
    var trailingPeriod = true
    /// Свои слова и обороты: убираются везде, где отбиты границами.
    var customFillers: [String] = []
    /// Замены «было → стало», без учёта регистра, по целым словам.
    var replacements: [(from: String, to: String)] = []

    static func == (a: CleanupOptions, b: CleanupOptions) -> Bool {
        a.level == b.level && a.removeRepeats == b.removeRepeats && a.capitalize == b.capitalize
            && a.trailingPeriod == b.trailingPeriod && a.customFillers == b.customFillers
            && a.replacements.map(\.from) == b.replacements.map(\.from)
            && a.replacements.map(\.to) == b.replacements.map(\.to)
    }
}

enum TextCleaner {
    // MARK: - словари

    private enum Mode {
        /// Убираем везде.
        case always
        /// Только вставкой: слева начало/знак, справа знак/конец.
        case bounded
        /// В начале фразы - всегда, внутри - только вставкой.
        case leading
        /// Хвостом внутри фразы: «…, да, …», «…, да.» - но не «Да, конечно» и не «…, да?».
        case tag
    }

    private struct Rule {
        let words: [String]
        let mode: Mode
        let minLevel: CleanupLevel
        /// Слова, после которых правило не действует («какого типа»).
        var notAfter: Set<String> = []
        /// Слова, перед которыми правило не действует («как бы не»).
        var notBefore: Set<String> = []
    }

    private static let rules: [Rule] = {
        func r(_ phrase: String, _ mode: Mode, _ level: CleanupLevel,
               notAfter: Set<String> = [], notBefore: Set<String> = []) -> Rule {
            Rule(words: phrase.split(separator: " ").map { String($0) }, mode: mode, minLevel: level,
                 notAfter: notAfter, notBefore: notBefore)
        }
        let nounish: Set<String> = ["какого", "этого", "того", "такого", "нового", "другого", "одного",
                                    "любого", "всякого", "своего", "нашего", "вашего", "моего", "твоего",
                                    "разного", "определённого", "определенного", "данного", "старого"]
        return [
            // Заминки
            r("э", .always, .hesitations), r("ээ", .always, .hesitations), r("эм", .always, .hesitations),
            r("эмм", .always, .hesitations), r("мм", .always, .hesitations), r("хм", .always, .hesitations),
            r("гм", .always, .hesitations), r("кхм", .always, .hesitations),
            r("um", .always, .hesitations), r("uh", .always, .hesitations), r("uhm", .always, .hesitations),
            r("umm", .always, .hesitations), r("erm", .always, .hesitations), r("er", .bounded, .hesitations),
            r("hmm", .always, .hesitations), r("mm", .always, .hesitations),
            r("угу", .bounded, .hesitations), r("ага", .bounded, .hesitations),
            // Паразиты
            r("как бы", .always, .fillers, notBefore: ["не", "ни", "то", "там", "чего"]),
            r("типа", .always, .fillers, notAfter: nounish.union(["вроде"])),
            r("короче", .always, .fillers, notBefore: ["чем"]),
            r("короче говоря", .always, .fillers),
            r("ну", .leading, .fillers),
            // «вот» со смыслом - перед указанием: «вот этот», «вот так», «вот почему», «вот он».
            r("вот", .always, .fillers, notBefore: ["этот", "эта", "это", "эти", "этого", "этой", "этим", "этих",
                                                    "эту", "тот", "та", "те", "то", "того", "так", "такой", "такая",
                                                    "такие", "такое", "здесь", "тут", "там", "почему", "зачем",
                                                    "что", "как", "где", "когда", "и", "он", "она", "они", "оно",
                                                    "сюда", "туда", "откуда", "куда", "кто", "ещё", "еще", "уже",
                                                    "видишь", "смотри", "именно", "поэтому"]),
            r("да", .tag, .fillers),
            r("вот так вот", .bounded, .fillers),
            r("вот это вот", .bounded, .fillers),
            r("значит", .bounded, .fillers),
            r("это самое", .always, .fillers),
            r("это", .bounded, .fillers),
            r("так сказать", .always, .fillers),
            r("в общем", .bounded, .fillers),
            r("в общем-то", .always, .fillers),
            r("вообще", .bounded, .fillers),
            r("слушай", .bounded, .fillers), r("слушайте", .bounded, .fillers),
            r("ты понял", .bounded, .fillers), r("понимаешь", .bounded, .fillers),
            r("ты понимаешь", .bounded, .fillers), r("знаешь", .bounded, .fillers),
            r("ты знаешь", .bounded, .fillers),
            r("блин", .bounded, .fillers),
            r("you know", .bounded, .fillers), r("i mean", .bounded, .fillers), r("like", .bounded, .fillers),
            r("basically", .bounded, .fillers), r("well", .bounded, .fillers),
            r("блядь", .always, .fillers), r("бля", .always, .fillers), r("блять", .always, .fillers),
            // Строго
            r("сука", .bounded, .strict), r("нахрен", .bounded, .strict), r("нафиг", .bounded, .strict),
            r("в принципе", .bounded, .strict), r("на самом деле", .bounded, .strict),
            r("получается", .bounded, .strict), r("собственно", .always, .strict),
            r("собственно говоря", .always, .strict), r("по сути", .bounded, .strict),
            r("как говорится", .always, .strict), r("скажем так", .always, .strict),
            r("грубо говоря", .bounded, .strict), r("в целом", .bounded, .strict),
            r("literally", .bounded, .strict), r("actually", .bounded, .strict),
        ]
    }()

    // MARK: - токены

    private struct Token {
        var text: String
        var isWord: Bool
        var removed = false
        var lower: String { text.lowercased() }
    }

    private static let tokenRegex = try! NSRegularExpression(
        pattern: #"[\p{L}\p{N}][\p{L}\p{N}'’\-]*|[^\s\p{L}\p{N}]"#)

    private static func tokenize(_ text: String) -> [Token] {
        let ns = text as NSString
        return tokenRegex.matches(in: text, range: NSRange(location: 0, length: ns.length)).map { m in
            let t = ns.substring(with: m.range)
            let first = t.unicodeScalars.first!
            return Token(text: t, isWord: CharacterSet.letters.union(.decimalDigits).contains(first))
        }
    }

    private static let sentenceEnd: Set<String> = [".", "!", "?", "…"]
    private static let noSpaceBefore: Set<String> = [",", ".", "!", "?", "…", ":", ";", ")", "»", "%"]
    private static let noSpaceAfter: Set<String> = ["(", "«"]

    /// Заминка растяжкой: «э-э-э», «и-и-и», «ааа», «мммм».
    private static func isStretch(_ word: String) -> Bool {
        let w = word.lowercased()
        let letters = w.filter { $0 != "-" }
        guard let first = letters.first, letters.count >= 2 else { return false }
        let hesitant: Set<Character> = ["а", "э", "и", "о", "у", "м", "ы", "e", "a", "u", "m"]
        return hesitant.contains(first) && letters.allSatisfy { $0 == first }
            && (w.contains("-") || letters.count >= 3 || "эмm".contains(first))
    }

    // MARK: - чистка

    static func clean(_ text: String, _ o: CleanupOptions) -> String {
        var s = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !s.isEmpty else { return s }
        s = applyReplacements(s, o.replacements)
        guard o.level != .off || o.removeRepeats || !o.customFillers.isEmpty
              || o.capitalize || !o.trailingPeriod else { return s }

        var tokens = tokenize(s)
        if o.level != .off {
            for i in tokens.indices where tokens[i].isWord && isStretch(tokens[i].text) {
                tokens[i].removed = true
            }
            var active = rules.filter { $0.minLevel.rank <= o.level.rank }
            active += o.customFillers
                .map { $0.trimmingCharacters(in: .whitespaces).lowercased() }
                .filter { !$0.isEmpty }
                .map { Rule(words: $0.split(separator: " ").map(String.init), mode: .bounded, minLevel: .hesitations) }
            // Длинные обороты раньше коротких: «вот так вот» раньше «вот».
            active.sort { $0.words.count > $1.words.count }
            run(active, on: &tokens)
        } else if !o.customFillers.isEmpty {
            let custom = o.customFillers.map { $0.trimmingCharacters(in: .whitespaces).lowercased() }
                .filter { !$0.isEmpty }
                .map { Rule(words: $0.split(separator: " ").map(String.init), mode: .bounded, minLevel: .off) }
            run(custom.sorted(by: { $0.words.count > $1.words.count }), on: &tokens)
        }
        if o.removeRepeats { removeRepeats(&tokens) }
        return render(tokens.filter { !$0.removed }, capitalize: o.capitalize, trailingPeriod: o.trailingPeriod)
    }

    /// Правила по кругу, пока что-то убирается: убранное «типа» делает
    /// соседнее «ну» вставкой. Запятые за убранным - в самом конце, чтобы
    /// до тех пор они служили границами.
    private static func run(_ rules: [Rule], on tokens: inout [Token]) {
        var commas = Set<Int>()
        for _ in 0..<4 {
            var changed = false
            for rule in rules where apply(rule, to: &tokens, commas: &commas) { changed = true }
            if !changed { break }
        }
        for c in commas { tokens[c].removed = true }
    }

    @discardableResult
    private static func apply(_ rule: Rule, to tokens: inout [Token], commas: inout Set<Int>) -> Bool {
        var changed = false
        let n = rule.words.count
        // Идём по ещё не убранным токенам: убранные не мешают границам, и
        // «Ну, короче, типа» чистится целиком.
        var live = tokens.indices.filter { !tokens[$0].removed }
        var pos = 0
        while pos + n <= live.count {
            let span = (0..<n).map { live[pos + $0] }
            let matches = span.enumerated().allSatisfy { k, idx in
                tokens[idx].isWord && tokens[idx].lower == rule.words[k]
            }
            guard matches else { pos += 1; continue }
            let prev = pos > 0 ? tokens[live[pos - 1]] : nil
            let nextIdx = pos + n < live.count ? live[pos + n] : nil
            let next = nextIdx.map { tokens[$0] }
            if let prev, prev.isWord, rule.notAfter.contains(prev.lower) { pos += 1; continue }
            // Следующее слово - и через запятую: «Короче, чем раньше».
            var nextWord = next
            if let n0 = next, !n0.isWord, n0.text == ",", pos + n + 1 < live.count {
                nextWord = tokens[live[pos + n + 1]]
            }
            if let w = nextWord, w.isWord, rule.notBefore.contains(w.lower) { pos += 1; continue }
            let leftBound = prev.map { !$0.isWord } ?? true
            let rightBound = next.map { !$0.isWord } ?? true
            let sentenceStart = prev.map { sentenceEnd.contains($0.text) } ?? true
            let ok: Bool
            switch rule.mode {
            case .always: ok = true
            case .bounded: ok = leftBound && rightBound
            case .leading: ok = sentenceStart || (leftBound && rightBound)
            case .tag: ok = leftBound && !sentenceStart && (next.map { $0.text == "," || $0.text == "." } ?? true)
            }
            guard ok else { pos += 1; continue }
            for idx in span { tokens[idx].removed = true }
            // Запятая сразу за вставкой - её же: «Ну, давай» → «Давай»,
            // «что вот, как бы, флоу» → «что флоу». Запятая перед вставкой
            // остаётся: «Я думаю, ну, что» → «Я думаю, что».
            if let nextIdx, tokens[nextIdx].text == "," {
                commas.insert(nextIdx)
            }
            changed = true
            live = tokens.indices.filter { !tokens[$0].removed }
            pos = max(0, pos - 1)
        }
        return changed
    }

    /// «я я хотел», «И, и, и вот» → одно слово. Кроме слов, где повтор - смысл.
    private static func removeRepeats(_ tokens: inout [Token]) {
        let keep: Set<String> = ["да", "нет", "очень", "так", "ха", "бла", "тук", "yes", "no", "very",
                                 "ho", "ha", "bye", "еле", "много", "долго", "далеко"]
        var lastWord: Int?
        var commas: [Int] = []
        for i in tokens.indices where !tokens[i].removed {
            let t = tokens[i]
            if !t.isWord {
                if t.text == "," { commas.append(i) } else { lastWord = nil; commas = [] }
                continue
            }
            if let l = lastWord, tokens[l].lower == t.lower, !keep.contains(t.lower) {
                tokens[i].removed = true
                for c in commas { tokens[c].removed = true }
                commas = []
                continue
            }
            lastWord = i
            commas = []
        }
    }

    private static func render(_ tokens: [Token], capitalize: Bool, trailingPeriod: Bool) -> String {
        // Схлопываем знаки: «, ,» → «,», «, .» → «.», запятая в начале фразы - прочь.
        var out: [Token] = []
        for t in tokens {
            if !t.isWord, t.text == "," || sentenceEnd.contains(t.text) || t.text == ";" || t.text == ":" {
                if out.isEmpty { continue }
                if let l = out.last, !l.isWord {
                    if sentenceEnd.contains(l.text) || l.text == "?" || l.text == "!" {
                        if t.text == "," || t.text == ";" || t.text == ":" { continue }
                        if l.text == t.text { continue }
                        // «.?» - оставляем сильнейший.
                        if l.text == "." { out.removeLast() }
                    } else if l.text == "," || l.text == ";" || l.text == ":" {
                        out.removeLast()
                    }
                }
            }
            out.append(t)
        }
        while let l = out.last, !l.isWord, l.text == "," || l.text == ";" || l.text == ":" { out.removeLast() }

        var result = ""
        var startSentence = true
        var prev: Token?
        for var t in out {
            if t.isWord && startSentence && capitalize {
                t.text = t.text.prefix(1).uppercased() + t.text.dropFirst()
            }
            if !result.isEmpty {
                let glue = (!t.isWord && noSpaceBefore.contains(t.text)) || (prev.map { !$0.isWord && noSpaceAfter.contains($0.text) } ?? false)
                    || (t.text == "-" && false)
                if !glue { result += " " }
            }
            result += t.text
            if t.isWord { startSentence = false } else if sentenceEnd.contains(t.text) { startSentence = true }
            prev = t
        }
        if trailingPeriod {
            if let l = out.last, l.isWord { result += "." }
        } else if result.hasSuffix("."), !result.hasSuffix("..") {
            result.removeLast()
        }
        return result
    }

    private static func applyReplacements(_ text: String, _ pairs: [(from: String, to: String)]) -> String {
        var s = text
        for p in pairs {
            let from = p.from.trimmingCharacters(in: .whitespaces)
            guard !from.isEmpty else { continue }
            let pattern = "(?<![\\p{L}\\p{N}])" + NSRegularExpression.escapedPattern(for: from) + "(?![\\p{L}\\p{N}])"
            guard let re = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]) else { continue }
            s = re.stringByReplacingMatches(in: s, range: NSRange(location: 0, length: (s as NSString).length),
                                            withTemplate: NSRegularExpression.escapedTemplate(for: p.to))
        }
        return s
    }
}

private extension CleanupLevel {
    var rank: Int {
        switch self {
        case .off: return 0
        case .hesitations: return 1
        case .fillers: return 2
        case .strict: return 3
        }
    }
}
