import SwiftUI

// «Обзор» - одна колонка сверху вниз: слова за период крупно и сколько это
// сэкономило; переключатель «Неделя / Месяц»; график по дням (наведение
// показывает день, столбики вырастают при входе); три числа и итог за всё
// время. Числа меняются перекатом цифр.
struct StatsView: View {
    @EnvironmentObject var state: AppState
    @State private var period: Period = .week

    enum Period: Int, CaseIterable, Identifiable {
        case week = 7, month = 30
        var id: Int { rawValue }
        var title: String { self == .week ? "Неделя" : "Месяц" }
    }

    var body: some View {
        let days = state.lastDays(period.rawValue)
        let words = days.reduce(0) { $0 + $1.words }
        PageScroll {
            HStack(alignment: .top, spacing: Space.s4) {
                hero(words: words)
                Spacer(minLength: 0)
                PeriodSwitch(selection: $period)
            }
            BarChart(days: days)
                .padding(.horizontal, 24)
                .padding(.top, 22)
                .padding(.bottom, 14)
                .nlCard(padding: 0)
            HStack(spacing: 10) {
                StatTile(value: state.speedWPM > 0 ? "\(state.speedWPM) сл/мин" : "—", label: "скорость речи")
                StatTile(value: ratio, label: "быстрее клавиатуры")
                StatTile(value: averageLength, label: "средняя диктовка")
            }
            allTime
        }
    }

    private func hero(words: Int) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("За последние \(period.rawValue) \(plural(period.rawValue, "день", "дня", "дней"))")
                .font(NLFont.ui(13.5, .medium))
                .foregroundStyle(NL.textTertiary)
                .contentTransition(.opacity)
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(grouped(words))
                    .font(NLFont.ui(52, .bold))
                    .tracking(-1.8)
                    .monospacedDigit()
                    .foregroundStyle(NL.textPrimary)
                    .contentTransition(.numericText())
                Text(plural(words, "слово", "слова", "слов"))
                    .font(NLFont.ui(20, .medium))
                    .foregroundStyle(NL.textSecondary)
            }
            Text(savedLine)
                .font(NLFont.ui(14))
                .foregroundStyle(NL.textSecondary)
                .contentTransition(.opacity)
        }
        .motion(Motion.slow, value: words)
    }

    private var savedLine: String {
        let minutes = state.savedMinutes(days: period.rawValue)
        guard minutes > 0 else { return "Надиктуйте больше — и здесь появится сэкономленное время." }
        return "Примерно \(grouped(minutes)) мин сэкономлено по сравнению с клавиатурой."
    }

    private var ratio: String {
        guard state.speedWPM > 0 else { return "—" }
        return state.voiceRatio.formatted(.number.precision(.fractionLength(1))) + "×"
    }

    private var averageLength: String {
        let ok = state.history.filter { !$0.failed }
        guard !ok.isEmpty else { return "—" }
        return MainView.clock(ok.reduce(0) { $0 + $1.seconds } / Double(ok.count))
    }

    private var allTime: some View {
        let ok = state.history.filter { !$0.failed }
        let words = ok.reduce(0) { $0 + $1.words }
        let seconds = ok.reduce(0.0) { $0 + $1.seconds }
        let rows: [(String, String)] = [
            ("Диктовок", grouped(state.history.count)),
            ("Слов", grouped(words)),
            ("Говорили", "\(grouped(Int((seconds / 60).rounded()))) мин"),
            ("Сэкономлено", "\(grouped(state.savedMinutes)) мин"),
            ("Убрано слов-паразитов", grouped(state.removedWords)),
        ]
        return VStack(alignment: .leading, spacing: 10) {
            Text("За всё время")
                .font(NLFont.ui(15, .bold))
                .foregroundStyle(NL.textPrimary)
            VStack(spacing: 0) {
                ForEach(Array(rows.enumerated()), id: \.offset) { index, row in
                    HStack {
                        Text(row.0).foregroundStyle(NL.textSecondary)
                        Spacer(minLength: Space.s4)
                        Text(row.1)
                            .fontWeight(.semibold)
                            .monospacedDigit()
                            .foregroundStyle(NL.textPrimary)
                    }
                    .font(NLFont.ui(14))
                    .frame(height: 44)
                    .overlay(alignment: .top) {
                        if index > 0 { NL.borderSubtle.frame(height: 1) }
                    }
                }
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 4)
            .nlCard(padding: 0)
            Text("Сравнение — со скоростью набора 40 слов в минуту.")
                .nlType(.caption)
                .foregroundStyle(NL.textTertiary)
                .padding(.horizontal, 4)
        }
    }
}

/// «Неделя / Месяц»: подложка и карточка выбранного, которая переезжает.
private struct PeriodSwitch: View {
    @Binding var selection: StatsView.Period
    @Namespace private var thumb

    var body: some View {
        HStack(spacing: 2) {
            ForEach(StatsView.Period.allCases) { item in
                let selected = selection == item
                Button {
                    withMotion(Motion.position) { selection = item }
                } label: {
                    Text(item.title)
                        .font(NLFont.ui(12.5, .medium))
                        .foregroundStyle(selected ? NL.textPrimary : NL.textSecondary)
                        .padding(.horizontal, 12)
                        .frame(height: 28)
                        .background {
                            if selected {
                                RoundedRectangle(cornerRadius: 8, style: .continuous)
                                    .fill(NL.surface)
                                    .shadow(color: .black.opacity(0.06), radius: 1, y: 1)
                                    .matchedGeometryEffect(id: "period", in: thumb)
                            }
                        }
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(selected ? .isSelected : [])
            }
        }
        .padding(3)
        .background(NL.hover, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
    }
}

/// Слова по дням столбиками. Сегодня - акцентом, остальные - тёплой
/// ступенью, наведённый темнеет; над ним - число. Столбики вырастают при
/// появлении один за другим.
private struct BarChart: View {
    let days: [DayWords]
    @State private var hovered: Date?
    @State private var grown = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private let plot: CGFloat = 172

    var body: some View {
        let peak = max(1, days.map(\.words).max() ?? 1)
        let dense = days.count > 7
        VStack(spacing: 0) {
            HStack(alignment: .bottom, spacing: dense ? 4 : 14) {
                ForEach(Array(days.enumerated()), id: \.element.id) { index, day in
                    let today = Calendar.current.isDateInToday(day.date)
                    let isHovered = hovered == day.date
                    let showValue = isHovered || (hovered == nil && today && day.words > 0)
                    let height = day.words == 0 ? 3 : max(4, CGFloat(day.words) / CGFloat(peak) * plot)
                    RoundedRectangle(cornerRadius: dense ? 3 : 7, style: .continuous)
                        .fill(today ? NL.accent : isHovered ? NL.chartBarHover : NL.chartBar)
                        .frame(maxWidth: 56)
                        .frame(height: grown ? height : 0)
                        .overlay(alignment: .top) {
                            Text(grouped(day.words))
                                .font(NLFont.ui(12, .semibold))
                                .monospacedDigit()
                                .foregroundStyle(NL.textPrimary)
                                .fixedSize()
                                .offset(y: -20)
                                .opacity(showValue ? 1 : 0)
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottom)
                        .contentShape(Rectangle())
                        .onHover { inside in
                            if inside { hovered = day.date } else if hovered == day.date { hovered = nil }
                        }
                        .animation(reduceMotion ? nil : Motion.slow.delay(Double(index) * (dense ? 0.01 : 0.04)),
                                   value: grown)
                        .accessibilityElement()
                        .accessibilityLabel("\(Self.label(day.date, today: today)): \(wordsLabel(day.words))")
                }
            }
            .frame(height: plot + 24)
            .animation(Motion.moderate, value: days.map(\.words))
            .animation(Motion.fast, value: hovered)
            NL.borderSubtle.frame(height: 1)
            HStack(spacing: dense ? 4 : 14) {
                ForEach(Array(days.enumerated()), id: \.element.id) { index, day in
                    let today = Calendar.current.isDateInToday(day.date)
                    Text(dense ? (index % 5 == 4 || today ? Self.dayNumber.string(from: day.date) : "")
                               : Self.label(day.date, today: today))
                        .font(NLFont.ui(12, today ? .semibold : .medium))
                        .foregroundStyle(today ? NL.textPrimary : NL.textTertiary)
                        .lineLimit(1)
                        .fixedSize()
                        .frame(maxWidth: .infinity)
                }
            }
            .padding(.top, 10)
        }
        .onAppear { grown = true }
    }

    private static let weekday: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ru_RU")
        f.dateFormat = "EE"
        return f
    }()

    private static let dayNumber: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ru_RU")
        f.dateFormat = "d"
        return f
    }()

    static func label(_ date: Date, today: Bool) -> String {
        today ? "Сегодня" : weekday.string(from: date).capitalized
    }
}
