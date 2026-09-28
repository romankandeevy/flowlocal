import AppKit
import SwiftUI

// Живая расшифровка по словам. Бэкенд присылает текст порциями (раз в
// 0,5-1,5 с, по нескольку слов) - если показывать как есть, текст скачет
// пачками. Здесь пришедшее выводится по одному слову ровным темпом:
// ~70 мс на слово, быстрее, если накопился запас, - и всегда догоняет.
// Черновик хвоста может уточниться: общее начало остаётся на месте, дальше
// слова меняются и допечатываются заново. Обновляется только этот объект,
// а не всё состояние приложения.
final class LiveWords: ObservableObject {
    static let shared = LiveWords()

    struct Word: Identifiable, Equatable {
        let id: Int          // позиция: новое слово - новая позиция, анимация появления
        let text: String
        let final: Bool      // окончательное - основным цветом, черновик - вторичным
    }

    @Published private(set) var words: [Word] = []
    /// Слов разобрано по счёту бэкенда - для заголовка пульта.
    @Published private(set) var count = 0

    private var target: [String] = []
    private var finalCount = 0
    private var timer: Timer?

    /// Новое состояние расшифровки: окончательное и черновик хвоста, оба уже почищены.
    func update(final: String, interim: String) {
        let f = final.split(whereSeparator: \.isWhitespace).map(String.init)
        let i = interim.split(whereSeparator: \.isWhitespace).map(String.init)
        target = f + i
        finalCount = f.count
        // Общее начало с уже показанным - остаётся; расходящееся - убираем
        // сразу, дальше допечатаем.
        // Сравниваем без регистра и знаков в конце: «работает» и «работает.»
        // - то же слово, оно меняется на месте, без повторного появления.
        var keep = 0
        while keep < words.count, keep < target.count,
              Self.norm(words[keep].text) == Self.norm(target[keep]) { keep += 1 }
        var shown = Array(words.prefix(keep))
        for k in shown.indices where shown[k].text != target[k] || (k < finalCount) != shown[k].final {
            shown[k] = Word(id: k, text: target[k], final: k < finalCount)
        }
        if shown != words { words = shown }
        schedule()
    }

    private static func norm(_ w: String) -> String {
        w.lowercased().trimmingCharacters(in: CharacterSet(charactersIn: ".,!?…:;»\"'"))
    }

    func reset() {
        timer?.invalidate()
        timer = nil
        target = []
        finalCount = 0
        if !words.isEmpty { words = [] }
        if count != 0 { count = 0 }
    }

    func setCount(_ n: Int) {
        if n != count { count = n }
    }

    private func schedule() {
        guard timer == nil, words.count < target.count else { return }
        let t = Timer(timeInterval: 0.07, repeats: true) { [weak self] _ in self?.step() }
        RunLoop.main.add(t, forMode: .common)
        timer = t
    }

    private func step() {
        let backlog = target.count - words.count
        guard backlog > 0 else {
            timer?.invalidate()
            timer = nil
            return
        }
        // Больше 6 слов в запасе - по нескольку за шаг, чтобы не отставать от речи.
        let n = backlog > 6 ? Int((Double(backlog) / 4).rounded(.up)) : 1
        var next = words
        for k in words.count..<min(target.count, words.count + n) {
            next.append(Word(id: k, text: target[k], final: k < finalCount))
        }
        words = next
    }
}

// MARK: - раскладка по строкам

/// Слова строками, как текст: переносит по ширине, промежуток - пробел.
struct WordFlow: Layout {
    var spacing: CGFloat = 4
    var lineSpacing: CGFloat = 4

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, line: CGFloat = 0, maxX: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > 0, x + s.width > width {
                y += line + lineSpacing
                x = 0
                line = 0
            }
            x += s.width + spacing
            maxX = max(maxX, x - spacing)
            line = max(line, s.height)
        }
        return CGSize(width: proposal.width ?? maxX, height: y + line)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, line: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > bounds.minX, x + s.width > bounds.maxX {
                y += line + lineSpacing
                x = bounds.minX
                line = 0
            }
            v.place(at: CGPoint(x: x, y: y), proposal: .unspecified)
            x += s.width + spacing
            line = max(line, s.height)
        }
    }
}

/// Высота по содержимому, но не больше max; лишнее срезается сверху -
/// видны последние строки.
private struct CappedBottomLayout: Layout {
    let max: CGFloat

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        guard let v = subviews.first else { return .zero }
        let s = v.sizeThatFits(ProposedViewSize(width: proposal.width, height: nil))
        return CGSize(width: proposal.width ?? s.width, height: min(s.height, max))
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        guard let v = subviews.first else { return }
        let s = v.sizeThatFits(ProposedViewSize(width: bounds.width, height: nil))
        v.place(at: CGPoint(x: bounds.minX, y: bounds.maxY - s.height),
                proposal: ProposedViewSize(width: bounds.width, height: s.height))
    }
}

private struct CappedBottom: ViewModifier {
    let max: CGFloat
    func body(content: Content) -> some View {
        CappedBottomLayout(max: max) { content }.clipped()
    }
}

// MARK: - виды

/// Появление слова: проступает и чуть поднимается на 3pt, 180 мс ease-out.
private struct WordAppear: ViewModifier {
    let visible: Bool
    func body(content: Content) -> some View {
        content.opacity(visible ? 1 : 0).offset(y: visible ? 0 : 3)
    }
}

extension AnyTransition {
    static var wordIn: AnyTransition {
        .modifier(active: WordAppear(visible: false), identity: WordAppear(visible: true))
    }
}

/// Живой текст в пульте: слова строками, свежие проступают, область сама
/// плавно прокручивается к последней строке.
struct LiveWordsFlow: View {
    @ObservedObject private var live = LiveWords.shared
    var placeholder: String
    var maxHeight: CGFloat = 116
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        if live.words.isEmpty {
            Text(placeholder)
                .nlType(.bodySm)
                .foregroundStyle(NL.textTertiary)
                .frame(maxWidth: .infinity, alignment: .leading)
        } else {
            // Без прокрутки: блок прижат к низу и обрезан сверху - новые
            // строки плавно выталкивают старые вверх вместе с анимацией слов.
            WordFlow(spacing: 4, lineSpacing: 3) {
                ForEach(live.words) { w in
                    Text(w.text)
                        .nlType(.bodySm)
                        .foregroundStyle(w.final ? NL.textPrimary : NL.textSecondary)
                        .transition(.wordIn)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .modifier(CappedBottom(max: maxHeight))
            .mask {
                // Верхний край растворяется, когда текст уходит за него.
                if live.words.count > 30 {
                    LinearGradient(stops: [.init(color: .clear, location: 0), .init(color: .black, location: 0.18)],
                                   startPoint: .top, endPoint: .bottom)
                } else {
                    Color.black
                }
            }
            .animation(reduceMotion ? nil : .easeOut(duration: 0.2), value: live.words)
        }
    }
}

/// Бегущая строка в капсуле: последние слова одной строкой, прижаты вправо;
/// новое слово проступает справа, строка плавно уезжает влево, левый край
/// растворяется.
struct LiveWordsTicker: View {
    @ObservedObject private var live = LiveWords.shared
    var width: CGFloat = 300
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        let tail = Array(live.words.suffix(24))
        HStack(spacing: 4) {
            ForEach(tail) { w in
                Text(w.text)
                    .foregroundStyle(w.final ? NL.textPrimary : NL.textSecondary)
                    .fixedSize()
                    .transition(.wordIn)
            }
        }
        .frame(width: width, alignment: .trailing)
        .clipped()
        .mask {
            LinearGradient(stops: [.init(color: .clear, location: 0), .init(color: .black, location: 0.18)],
                           startPoint: .leading, endPoint: .trailing)
        }
        .animation(reduceMotion ? nil : .easeOut(duration: 0.2), value: tail)
        .accessibilityElement(children: .combine)
    }
}
