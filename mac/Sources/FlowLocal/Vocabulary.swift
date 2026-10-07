import Foundation

// Словарь и исправления - без нейросетей, только Foundation (проверяется
// tools/selftest.sh).
//
// Словарь - слова, которые модель пишет неправильно: имена, термины,
// названия. После чистки каждое слово (и пары-тройки слов) сравниваются с
// терминами по «звучанию»: кириллица переводится в латиницу, английское
// упрощается (c→k, au→o, немая e на конце), дубли букв схлопываются.
// Совпало или почти совпало - на место ставится термин как он записан:
// «гитхаб» → GitHub, «клод» → Claude.
//
// Исправления - пары «было → стало», выученные из правок человека: в
// окне истории или прямо в поле, куда легла диктовка. Учатся только точечные
// замены одного-трёх слов, похожих на исходные; переписанный абзац -
// не исправление, а новый текст.

enum Vocabulary {
    // MARK: - звучание

    private static let cyrillic: [Character: String] = [
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
        "и": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
        "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh",
        "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "u", "я": "a",
    ]

    /// Ключ звучания: латиница, без знаков и пробелов, упрощённая.
    static func key(_ text: String) -> String {
        var s = ""
        for ch in text.lowercased() {
            if let t = cyrillic[ch] {
                s += t
            } else if ch.isLetter || ch.isNumber {
                s.append(ch)
            }
        }
        // Упрощаем одинаково обе записи: «гитхаб» и «GitHub» сходятся в одну.
        do {
            for (a, b) in [("ph", "f"), ("th", "t"), ("ck", "k"), ("ch", "ch"), ("sh", "sh"), ("qu", "kv"),
                           ("au", "o"), ("ou", "u"), ("oo", "u"), ("ee", "i"), ("ea", "i"), ("ai", "ei"),
                           ("x", "ks"), ("q", "k"), ("w", "v"), ("y", "i"), ("j", "dzh")] {
                s = s.replacingOccurrences(of: a, with: b)
            }
            // c перед e/i - «с», иначе «к».
            var out = ""
            let chars = Array(s)
            for (i, c) in chars.enumerated() {
                if c == "c" {
                    let next = i + 1 < chars.count ? chars[i + 1] : " "
                    if next == "h" { out.append("c"); continue }
                    out.append(next == "e" || next == "i" ? "s" : "k")
                } else {
                    out.append(c)
                }
            }
            s = out
            if s.count > 3 && s.hasSuffix("e") { s.removeLast() }
        }
        // Дубли букв: «Гугл» и «Google» - одно.
        var collapsed = ""
        for c in s where collapsed.last != c { collapsed.append(c) }
        return collapsed
    }

    /// Расстояние Левенштейна по символам.
    static func distance(_ a: String, _ b: String) -> Int {
        let a = Array(a), b = Array(b)
        if a.isEmpty { return b.count }
        if b.isEmpty { return a.count }
        var prev = Array(0...b.count)
        var cur = Array(repeating: 0, count: b.count + 1)
        for i in 1...a.count {
            cur[0] = i
            for j in 1...b.count {
                cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] == b[j - 1] ? 0 : 1))
            }
            swap(&prev, &cur)
        }
        return prev[b.count]
    }

    /// Похожесть 0...1 по ключам звучания.
    static func similarity(_ a: String, _ b: String) -> Double {
        let ka = key(a), kb = key(b)
        let longest = max(ka.count, kb.count)
        guard longest > 0 else { return 0 }
        return 1 - Double(distance(ka, kb)) / Double(longest)
    }

    /// Порог: короткое слово должно совпасть почти полностью, иначе
    /// «Саша» стал бы «Машей».
    static func threshold(_ keyLength: Int) -> Double {
        switch keyLength {
        case ..<4: return 1.0
        case 4...5: return 0.8
        case 6...8: return 0.78
        default: return 0.74
        }
    }

    // MARK: - словарь

    private struct Word {
        let range: Range<String.Index>
        let text: String
    }

    private static func words(_ s: String) -> [Word] {
        var out: [Word] = []
        var start: String.Index?
        var i = s.startIndex
        while i < s.endIndex {
            let ch = s[i]
            let inWord = ch.isLetter || ch.isNumber || ((ch == "-" || ch == "'" || ch == "+") && start != nil)
            if inWord {
                if start == nil { start = i }
            } else if let st = start {
                out.append(Word(range: st..<i, text: String(s[st..<i])))
                start = nil
            }
            i = s.index(after: i)
        }
        if let st = start { out.append(Word(range: st..<s.endIndex, text: String(s[st...]))) }
        return out
    }

    /// Термины словаря - на место похожих слов. Окно в одно-три слова: «гит
    /// хаб» тоже GitHub.
    static func apply(_ text: String, terms: [String]) -> String {
        let terms = terms.map { $0.trimmingCharacters(in: .whitespaces) }.filter { key($0).count >= 2 }
        guard !terms.isEmpty, !text.isEmpty else { return text }
        let ws = words(text)
        guard !ws.isEmpty else { return text }
        var replacements: [(Range<String.Index>, String)] = []
        var i = 0
        while i < ws.count {
            var best: (len: Int, term: String, score: Double)?
            for n in (1...3).reversed() where i + n <= ws.count {
                let window = ws[i..<(i + n)]
                // Окно - подряд идущие слова, без знаков между ними.
                let span = window.first!.range.lowerBound..<window.last!.range.upperBound
                let between = text[span].filter { !$0.isLetter && !$0.isNumber && $0 != " " && $0 != "-" }
                if n > 1 && !between.isEmpty { continue }
                let phrase = window.map(\.text).joined(separator: " ")
                let pk = key(phrase)
                for term in terms {
                    let tk = key(term)
                    let termWords = term.split(separator: " ").count
                    // Окно не длиннее термина больше чем на два слова и не короче.
                    guard n >= termWords, n <= termWords + 2 else { continue }
                    guard pk.count >= 2 else { continue }
                    if phrase == term { best = nil; break }
                    let longest = max(pk.count, tk.count)
                    let score = 1 - Double(distance(pk, tk)) / Double(longest)
                    // Короткое слово с другой первой буквой - другое слово: «Маша» не «Саша».
                    if min(pk.count, tk.count) < 7, pk.first != tk.first { continue }
                    if score >= threshold(min(pk.count, tk.count)), score > (best?.score ?? 0) {
                        best = (n, term, score)
                    }
                }
                if best != nil { break }
            }
            if let best {
                let span = ws[i].range.lowerBound..<ws[i + best.len - 1].range.upperBound
                if String(text[span]) != best.term { replacements.append((span, best.term)) }
                i += best.len
            } else {
                i += 1
            }
        }
        var out = text
        for (range, term) in replacements.reversed() {
            out.replaceSubrange(range, with: term)
        }
        return out
    }

    // MARK: - исправления

    /// Выученная замена: сколько раз человек так поправил.
    struct Correction: Codable, Equatable, Identifiable {
        var from: String
        var to: String
        var count: Int = 1
        var id: String { from.lowercased() }
    }

    /// Что человек поправил: точечные замены из сравнения по словам.
    static func learn(original: String, edited: String) -> [(from: String, to: String)] {
        let a = words(original).map(\.text)
        let b = words(edited).map(\.text)
        guard !a.isEmpty, !b.isEmpty, a != b else { return [] }
        // Почти всё переписано - это не исправление.
        let lcs = commonSubsequence(a.map { $0.lowercased() }, b.map { $0.lowercased() })
        guard lcs.count * 2 >= min(a.count, b.count) || (a.count <= 3 && b.count <= 3) else { return [] }
        var out: [(String, String)] = []
        var i = 0, j = 0, k = 0
        while i < a.count || j < b.count {
            if k < lcs.count, i < a.count, j < b.count,
               a[i].lowercased() == lcs[k], b[j].lowercased() == lcs[k] {
                // Смена регистра - тоже исправление: «github» → «GitHub».
                if a[i] != b[j], hasInnerCase(b[j]) { out.append((a[i], b[j])) }
                i += 1; j += 1; k += 1
                continue
            }
            var di = i, dj = j
            while di < a.count, k >= lcs.count || a[di].lowercased() != lcs[k] { di += 1 }
            while dj < b.count, k >= lcs.count || b[dj].lowercased() != lcs[k] { dj += 1 }
            let removed = Array(a[i..<di]), added = Array(b[j..<dj])
            // Хвост, дописанный после вставки, - не правка.
            let appended = di == a.count && dj == b.count && added.count > removed.count
            if !appended, (1...3).contains(removed.count), (1...3).contains(added.count) {
                let from = removed.joined(separator: " "), to = added.joined(separator: " ")
                if similarity(from, to) >= 0.4 || (removed.count == 1 && added.count == 1 && key(from).count <= 4) {
                    out.append((from, to))
                }
            }
            i = di; j = dj
        }
        return out
    }

    /// GitHub, iOS, McDonald - заглавная не только первой буквой.
    private static func hasInnerCase(_ w: String) -> Bool {
        w.dropFirst().contains { $0.isUppercase }
    }

    private static func commonSubsequence(_ a: [String], _ b: [String]) -> [String] {
        guard !a.isEmpty, !b.isEmpty else { return [] }
        var dp = Array(repeating: Array(repeating: 0, count: b.count + 1), count: a.count + 1)
        for i in stride(from: a.count - 1, through: 0, by: -1) {
            for j in stride(from: b.count - 1, through: 0, by: -1) {
                dp[i][j] = a[i] == b[j] ? dp[i + 1][j + 1] + 1 : max(dp[i + 1][j], dp[i][j + 1])
            }
        }
        var out: [String] = []
        var i = 0, j = 0
        while i < a.count, j < b.count {
            if a[i] == b[j] { out.append(a[i]); i += 1; j += 1 } else if dp[i + 1][j] >= dp[i][j + 1] { i += 1 } else { j += 1 }
        }
        return out
    }

    /// Добавить выученные пары к уже известным.
    static func merge(_ learned: [(from: String, to: String)], into list: [Correction]) -> [Correction] {
        var out = list
        for pair in learned {
            if let i = out.firstIndex(where: { $0.from.lowercased() == pair.from.lowercased() }) {
                if out[i].to == pair.to { out[i].count += 1 } else { out[i].to = pair.to; out[i].count = 1 }
            } else {
                out.append(Correction(from: pair.from, to: pair.to))
            }
        }
        return out
    }

    // MARK: - правка в поле

    /// Где в новом тексте поля лежит вставленный кусок: между тем, что было
    /// до вставки, и тем, что было после. Нет опоры - nil.
    static func editedRegion(now: String, before: String, after: String, inserted: String) -> String? {
        let ns = now as NSString
        var lo = 0
        if !before.isEmpty {
            let r = ns.range(of: before, options: .backwards)
            guard r.location != NSNotFound else { return nil }
            lo = r.location + r.length
        }
        var hi = ns.length
        if !after.isEmpty {
            let r = ns.range(of: after, options: [], range: NSRange(location: lo, length: ns.length - lo))
            guard r.location != NSNotFound else { return nil }
            hi = r.location
        }
        guard hi >= lo else { return nil }
        var region = ns.substring(with: NSRange(location: lo, length: hi - lo))
        // После вставки дописали ещё: берём не больше вставленного плюс запас.
        if after.isEmpty {
            let limit = Int(Double(inserted.count) * 1.5) + 12
            if region.count > limit {
                region = String(region.prefix(limit))
                if let space = region.lastIndex(where: { $0.isWhitespace }) { region = String(region[..<space]) }
            }
        }
        return region
    }
}
