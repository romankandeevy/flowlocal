import SwiftUI

// Календарь диктовок, как на GitHub: год квадратиками, неделя - столбик,
// чем больше слов надиктовано за день, тем зеленее. Щелчок по дню - в
// истории остаются только его диктовки; щелчок ещё раз - снова все.
// Годы листаются стрелками: история хранится вся, без лимита.
struct ActivityCalendar: View {
    let history: [Entry]
    @Binding var selected: Date?

    /// Конец показанного года: сегодня или 31 декабря прошлых лет.
    @State private var yearEnd: Date = Calendar.current.startOfDay(for: Date())
    @State private var hovered: Date?

    private static let cell: CGFloat = 11
    private static let gap: CGFloat = 3
    private static let weeks = 53

    private var cal: Calendar {
        var c = Calendar(identifier: .gregorian)
        c.locale = Locale(identifier: "ru_RU")
        c.firstWeekday = 2   // неделя с понедельника
        return c
    }

    var body: some View {
        let stats = Self.daily(history, cal)
        let top = Self.levels(stats)
        VStack(alignment: .leading, spacing: 10) {
            header(stats)
            // Недель - сколько влезает по ширине (до 53): прокрутка вбок мышью неудобна.
            HStack(alignment: .top, spacing: 6) {
                weekdayLabels
                GeometryReader { geo in
                    let fit = max(8, Int((geo.size.width + Self.gap) / (Self.cell + Self.gap)))
                    let grid = Array(columns.suffix(fit))
                    VStack(alignment: .leading, spacing: 4) {
                        monthLabels(grid)
                        HStack(alignment: .top, spacing: Self.gap) {
                            ForEach(grid.indices, id: \.self) { w in
                                VStack(spacing: Self.gap) {
                                    ForEach(0..<7, id: \.self) { d in
                                        cell(grid[w][d], stats, top)
                                    }
                                }
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .trailing)
                }
                .frame(height: 13 + 4 + 7 * Self.cell + 6 * Self.gap)
            }
            footer(stats)
        }
        .padding(16)
        .nlCard(padding: 0, radius: 12)
    }

    // MARK: - части

    private func header(_ stats: [Date: DayStat]) -> some View {
        let range = shownRange
        let inYear = stats.filter { range.contains($0.key) }
        let words = inYear.values.reduce(0) { $0 + $1.words }
        let days = inYear.count
        return HStack(alignment: .firstTextBaseline, spacing: 8) {
            Text(words > 0
                 ? "\(wordsLabel(words)) за \(isCurrentYear ? "последний год" : yearTitle) · \(grouped(days)) \(plural(days, "день", "дня", "дней"))"
                 : "За \(isCurrentYear ? "последний год" : yearTitle) диктовок нет")
                .font(NLFont.ui(13, .semibold))
                .monospacedDigit()
                .foregroundStyle(NL.textPrimary)
            Spacer()
            if canGoBack(stats) || !isCurrentYear {
                HStack(spacing: 2) {
                    arrow("chevron.left", enabled: canGoBack(stats)) { shift(-1) }
                    Text(isCurrentYear ? "Год" : yearTitle)
                        .font(NLFont.ui(12.5, .medium))
                        .monospacedDigit()
                        .foregroundStyle(NL.textSecondary)
                        .frame(minWidth: 38)
                    arrow("chevron.right", enabled: !isCurrentYear) { shift(1) }
                }
            }
        }
    }

    private func arrow(_ symbol: String, enabled: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 11, weight: .semibold))
                .frame(width: 22, height: 22)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .foregroundStyle(enabled ? NL.textSecondary : NL.textDisabled)
        .disabled(!enabled)
        .accessibilityLabel(symbol == "chevron.left" ? "Предыдущий год" : "Следующий год")
    }

    private var weekdayLabels: some View {
        VStack(alignment: .trailing, spacing: Self.gap) {
            Color.clear.frame(width: 1, height: 13)   // под подписями месяцев
            ForEach(0..<7, id: \.self) { d in
                Text(d == 0 ? "Пн" : d == 2 ? "Ср" : d == 4 ? "Пт" : "")
                    .font(NLFont.ui(9.5))
                    .foregroundStyle(NL.textTertiary)
                    .frame(height: Self.cell)
            }
        }
        .frame(width: 18, alignment: .trailing)
    }

    private func monthLabels(_ grid: [[Date?]]) -> some View {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ru_RU")
        f.dateFormat = "LLL"
        return HStack(spacing: Self.gap) {
            ForEach(grid.indices, id: \.self) { w in
                // Подпись - над неделей, где начинается месяц.
                let first = grid[w].compactMap { $0 }.first { cal.component(.day, from: $0) == 1 }
                // Подпись в overlay: длинное «февр» не раздвигает столбики.
                Color.clear
                    .frame(width: Self.cell, height: 13)
                    .overlay(alignment: .leading) {
                        if let first, w < grid.count - 2 {
                            Text(f.string(from: first).replacingOccurrences(of: ".", with: ""))
                                .font(NLFont.ui(9.5))
                                .foregroundStyle(NL.textTertiary)
                                .fixedSize()
                        }
                    }
            }
        }
    }

    @ViewBuilder
    private func cell(_ day: Date?, _ stats: [Date: DayStat], _ top: Int) -> some View {
        if let day, day <= today {
            let s = stats[day]
            let isSel = selected.map { cal.isDate($0, inSameDayAs: day) } ?? false
            RoundedRectangle(cornerRadius: 2.5, style: .continuous)
                .fill(Self.color(s?.words ?? 0, top))
                .frame(width: Self.cell, height: Self.cell)
                .overlay {
                    RoundedRectangle(cornerRadius: 2.5, style: .continuous)
                        .strokeBorder(isSel ? NL.textPrimary : hovered == day ? NL.borderStrong : .clear,
                                      lineWidth: isSel ? 1.5 : 1)
                }
                .contentShape(Rectangle())
                .onHover { inside in
                    if inside { hovered = day } else if hovered == day { hovered = nil }
                }
                .onTapGesture {
                    guard s != nil else { return }
                    withMotion(Motion.base) { selected = isSel ? nil : day }
                }
                .help(Self.tooltip(day, s))
                .accessibilityElement()
                .accessibilityLabel(Self.tooltip(day, s))
                .accessibilityAddTraits(s != nil ? .isButton : [])
        } else {
            Color.clear.frame(width: Self.cell, height: Self.cell)
        }
    }

    private func footer(_ stats: [Date: DayStat]) -> some View {
        HStack(spacing: 6) {
            if let day = hovered ?? selected {
                Text(Self.tooltip(day, stats[day]))
                    .font(NLFont.ui(11.5))
                    .monospacedDigit()
                    .foregroundStyle(NL.textSecondary)
                    .lineLimit(1)
            } else {
                Text("Нажмите на день — останутся его диктовки")
                    .font(NLFont.ui(11.5))
                    .foregroundStyle(NL.textTertiary)
            }
            Spacer()
            Text("Меньше").font(NLFont.ui(10.5)).foregroundStyle(NL.textTertiary)
            ForEach(0..<5, id: \.self) { i in
                RoundedRectangle(cornerRadius: 2.5, style: .continuous)
                    .fill(Self.shade(i))
                    .frame(width: 10, height: 10)
            }
            Text("Больше").font(NLFont.ui(10.5)).foregroundStyle(NL.textTertiary)
        }
    }

    // MARK: - даты

    private var today: Date { cal.startOfDay(for: Date()) }
    private var isCurrentYear: Bool { yearEnd >= today }
    private var yearTitle: String { String(cal.component(.year, from: yearEnd)) }

    /// Видимые дни: текущий год - последние 53 недели, прошлые - с 1 января по 31 декабря.
    private var shownRange: ClosedRange<Date> {
        if isCurrentYear {
            let start = cal.date(byAdding: .day, value: -(Self.weeks * 7 - 1), to: today)!
            return start...today
        }
        let y = cal.component(.year, from: yearEnd)
        let start = cal.date(from: DateComponents(year: y, month: 1, day: 1))!
        return start...yearEnd
    }

    /// Столбики-недели по 7 дней (пн…вс); дни вне диапазона - nil.
    private var columns: [[Date?]] {
        let range = shownRange
        let weekday = (cal.component(.weekday, from: range.lowerBound) + 5) % 7   // пн = 0
        var day = cal.date(byAdding: .day, value: -weekday, to: range.lowerBound)!
        var out: [[Date?]] = []
        while day <= range.upperBound {
            var week: [Date?] = []
            for _ in 0..<7 {
                week.append(range.contains(day) ? day : nil)
                day = cal.date(byAdding: .day, value: 1, to: day)!
            }
            out.append(week)
        }
        return out
    }

    private func canGoBack(_ stats: [Date: DayStat]) -> Bool {
        guard let oldest = stats.keys.min() else { return false }
        return oldest < shownRange.lowerBound
    }

    private func shift(_ years: Int) {
        let y = cal.component(.year, from: isCurrentYear ? today : yearEnd) + years
        withMotion(Motion.base) {
            if y >= cal.component(.year, from: today) {
                yearEnd = today
            } else {
                yearEnd = cal.date(from: DateComponents(year: y, month: 12, day: 31))!
            }
        }
    }

    // MARK: - данные

    struct DayStat {
        var count = 0
        var words = 0
    }

    static func daily(_ history: [Entry], _ cal: Calendar) -> [Date: DayStat] {
        var out: [Date: DayStat] = [:]
        for e in history where !e.failed {
            let d = cal.startOfDay(for: e.date)
            out[d, default: DayStat()].count += 1
            out[d, default: DayStat()].words += e.words
        }
        return out
    }

    /// Самый «громкий» день - по нему ступени цвета (как у GitHub - от максимума).
    static func levels(_ stats: [Date: DayStat]) -> Int {
        max(1, stats.values.map(\.words).max() ?? 1)
    }

    static func color(_ words: Int, _ top: Int) -> Color {
        guard words > 0 else { return shade(0) }
        let r = Double(words) / Double(top)
        return shade(r > 0.75 ? 4 : r > 0.4 ? 3 : r > 0.15 ? 2 : 1)
    }

    static func shade(_ level: Int) -> Color {
        switch level {
        case 0: return NL.chartBar
        case 1: return NL.accent.opacity(0.28)
        case 2: return NL.accent.opacity(0.5)
        case 3: return NL.accent.opacity(0.75)
        default: return NL.accent
        }
    }

    static func tooltip(_ day: Date, _ s: DayStat?) -> String {
        let date = HistoryFormat.dayYear.string(from: day)
        guard let s, s.count > 0 else { return "\(date) — диктовок нет" }
        return "\(date) — \(s.count) \(plural(s.count, "диктовка", "диктовки", "диктовок")), \(wordsLabel(s.words))"
    }
}
