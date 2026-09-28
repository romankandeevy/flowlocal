import Charts
import SwiftUI

// «Обзор» - одна колонка для чтения сверху вниз: главное число недели
// крупно, под ним - сколько это сэкономило; полоса показателей; неделя
// графиком (наведение показывает день); итог за всё время. Числа меняются
// перекатом цифр, столбики при входе вырастают от нуля.
struct StatsView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Space.s8) {
                hero
                StatStrip(items: [
                    .init(label: "Слов сегодня", value: grouped(state.wordsToday)),
                    .init(label: "Диктовок сегодня", value: grouped(state.dictationsToday)),
                    .init(label: "Скорость речи", value: state.speedWPM > 0 ? "\(state.speedWPM) сл/мин" : "—"),
                    .init(label: "Быстрее клавиатуры", value: ratio),
                ])
                chartSection
                allTimeSection
            }
            .frame(maxWidth: Space.contentMax, alignment: .leading)
            .padding(.horizontal, Space.s8)
            .padding(.vertical, Space.s8)
            .frame(maxWidth: .infinity)
        }
        .background(NL.canvas)
    }

    private var hero: some View {
        VStack(alignment: .leading, spacing: Space.s1) {
            Text("За последние 7 дней")
                .nlType(.label)
                .foregroundStyle(NL.textSecondary)
            HStack(alignment: .firstTextBaseline, spacing: Space.s2) {
                Text(grouped(state.wordsWeek))
                    .nlType(.display)
                    .monospacedDigit()
                    .foregroundStyle(NL.textPrimary)
                    .contentTransition(.numericText())
                Text(plural(state.wordsWeek, "слово", "слова", "слов"))
                    .nlType(.headingSm)
                    .foregroundStyle(NL.textSecondary)
            }
            .motion(Motion.slow, value: state.wordsWeek)
            Text(savedLine)
                .nlType(.bodySm)
                .foregroundStyle(NL.textSecondary)
        }
    }

    private var savedLine: String {
        let minutes = weekSavedMinutes
        guard minutes > 0 else { return "Надиктуйте больше — и здесь появится сэкономленное время." }
        return "Примерно \(minutes) мин сэкономлено по сравнению с набором на клавиатуре."
    }

    /// Экономия недели - так же, как за всё время: печать минус речь.
    private var weekSavedMinutes: Int {
        let since = Calendar.current.date(byAdding: .day, value: -6, to: Calendar.current.startOfDay(for: Date()))!
        let saved = state.history.filter { $0.date >= since }
            .reduce(0.0) { $0 + max(0, Double($1.words) / AppState.typingWPM - $1.seconds / 60) }
        return Int(saved.rounded())
    }

    private var chartSection: some View {
        VStack(alignment: .leading, spacing: Space.stackSm) {
            SectionTitle("По дням")
            Group {
                if state.lastDays.allSatisfy({ $0.words == 0 }) {
                    NLEmptyState(symbol: "chart.bar", title: "Пока пусто",
                                 message: "Диктуйте — и здесь появятся слова по дням.")
                } else {
                    WeekChart(days: state.lastDays)
                        .padding(Space.insetLg)
                }
            }
            .nlCard(padding: 0)
        }
    }

    private var allTimeSection: some View {
        let ok = state.history.filter { !$0.failed }
        let words = ok.reduce(0) { $0 + $1.words }
        let seconds = ok.reduce(0.0) { $0 + $1.seconds }
        return VStack(alignment: .leading, spacing: Space.stackSm) {
            SectionTitle("За всё время")
            VStack(spacing: 0) {
                KVRow(key: "Диктовок", value: grouped(state.history.count))
                KVRow(key: "Слов", value: grouped(words))
                KVRow(key: "Говорили", value: "\(grouped(Int((seconds / 60).rounded()))) мин")
                KVRow(key: "Сэкономлено", value: "\(grouped(state.savedMinutes)) мин")
                KVRow(key: "Убрано слов-паразитов", value: grouped(state.removedWords), last: true)
            }
            .padding(.horizontal, Space.insetMd)
            .padding(.vertical, Space.s1)
            .nlCard(padding: 0)
            FormFooter("Сравнение — со скоростью набора 40 слов в минуту.")
        }
    }

    private var ratio: String {
        guard state.speedWPM > 0 else { return "—" }
        return state.voiceRatio.formatted(.number.precision(.fractionLength(1))) + "×"
    }
}

/// Слова по дням. Сегодня - акцентом, прочие - нейтральной ступенью;
/// наведённый день подсвечивается, над ним - число. Столбики вырастают
/// при появлении (ease-out 300 мс).
private struct WeekChart: View {
    let days: [DayWords]
    @State private var hovered: Date?
    @State private var grown = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        Chart(days) { day in
            let isToday = Calendar.current.isDateInToday(day.date)
            let isHovered = hovered.map { Calendar.current.isDate($0, inSameDayAs: day.date) } ?? false
            BarMark(x: .value("День", day.date, unit: .day),
                    y: .value("Слова", grown ? day.words : 0),
                    width: .ratio(0.55))
                .foregroundStyle(isToday ? NL.accent : isHovered ? NL.textTertiary : NL.borderStrong)
                .clipShape(UnevenRoundedRectangle(topLeadingRadius: Radius.xs, topTrailingRadius: Radius.xs,
                                                  style: .continuous))
                .annotation(position: .top, spacing: 4) {
                    if isHovered || (hovered == nil && isToday && day.words > 0) {
                        Text(grouped(day.words))
                            .nlType(.labelSm)
                            .monospacedDigit()
                            .foregroundStyle(NL.textPrimary)
                    }
                }
        }
        .chartXSelection(value: $hovered)
        .chartXAxis {
            AxisMarks(values: .stride(by: .day)) { _ in
                AxisValueLabel(format: .dateTime.weekday(.abbreviated), centered: true)
                    .font(NLType.caption.font)
                    .foregroundStyle(NL.textTertiary)
            }
        }
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) { _ in
                AxisGridLine(stroke: StrokeStyle(lineWidth: 1))
                    .foregroundStyle(NL.borderSubtle)
                AxisValueLabel()
                    .font(NLType.caption.font.monospacedDigit())
                    .foregroundStyle(NL.textTertiary)
            }
        }
        .frame(height: 180)
        .animation(Motion.fast, value: hovered)
        .onAppear {
            if reduceMotion { grown = true } else { withAnimation(Motion.slow) { grown = true } }
        }
    }
}
