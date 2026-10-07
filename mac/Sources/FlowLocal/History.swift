import SwiftUI

// «История» - все диктовки по дням. Заголовок, поиск и фильтры стоят на
// месте, под ними прокручиваются дни карточками. Щелчок копирует, «⋯» и
// правый щелчок - остальное. ⌘F - в поиск.
struct HistoryView: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions
    @State private var filter: Filter = .all

    enum Filter: String, CaseIterable, Identifiable {
        case all, ru, en, failed
        var id: String { rawValue }
        var title: String {
            switch self {
            case .all: return "Все"
            case .ru: return "Русский"
            case .en: return "English"
            case .failed: return "Не распознаны"
            }
        }
    }

    var body: some View {
        let items = filtered
        VStack(alignment: .leading, spacing: 0) {
            controls
                .frame(maxWidth: Space.contentMax, alignment: .leading)
                .padding(.horizontal, Space.page)
                .padding(.top, Space.s3)
                .padding(.bottom, Space.s4)
                .frame(maxWidth: .infinity)
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 22) {
                    if !state.history.isEmpty {
                        ActivityCalendar(history: state.history, selected: $state.historyDay)
                    }
                    ForEach(HistoryFormat.days(items)) { day in
                        DaySection(day: day, actions: actions)
                    }
                }
                .frame(maxWidth: Space.contentMax, alignment: .leading)
                .padding(.horizontal, Space.page)
                .padding(.top, Space.s1)
                .padding(.bottom, Space.s12)
                .frame(maxWidth: .infinity)
                // Анимируем только появление и удаление диктовок: при поиске
                // список меняется на каждую букву, и анимация сотен строк
                // тормозила бы ввод.
                .motion(Motion.moderate, value: query.isEmpty && filter == .all && state.historyDay == nil ? items.map(\.id) : [])
            }
            .entryKeys(items, actions: actions)
            .overlay { empty(items) }
        }
    }

    private var controls: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                Text("История")
                    .font(NLFont.ui(30, .bold))
                    .tracking(-0.75)
                    .foregroundStyle(NL.textPrimary)
                Spacer()
                Text(summary)
                    .font(NLFont.ui(13))
                    .monospacedDigit()
                    .foregroundStyle(NL.textTertiary)
            }
            if !state.history.isEmpty {
                SearchField(text: $state.historyQuery, focusRequest: state.searchFocusRequest)
                HStack(spacing: 8) {
                    FilterChips(selection: $filter)
                    if let day = state.historyDay {
                        DayChip(title: HistoryFormat.sectionTitle(day)) {
                            withMotion(Motion.base) { state.historyDay = nil }
                        }
                        .transition(.opacity.combined(with: .scale(scale: 0.9)))
                    }
                }
            }
        }
    }

    private var summary: String {
        let words = state.history.reduce(0) { $0 + $1.words }
        let n = state.history.count
        return "\(grouped(n)) \(plural(n, "диктовка", "диктовки", "диктовок")) · \(wordsLabel(words))"
    }

    private var query: String { state.historyQuery.trimmingCharacters(in: .whitespaces) }

    private var filtered: [Entry] {
        let q = query
        return state.history.filter { entry in
            let lang = entry.lang.lowercased()
            let passes: Bool
            switch filter {
            case .all: passes = true
            case .ru: passes = !entry.failed && lang != "en"
            case .en: passes = !entry.failed && lang == "en"
            case .failed: passes = entry.failed
            }
            let inDay = state.historyDay.map { Calendar.current.isDate(entry.date, inSameDayAs: $0) } ?? true
            return passes && inDay && (q.isEmpty || entry.text.localizedCaseInsensitiveContains(q))
        }
    }

    @ViewBuilder
    private func empty(_ items: [Entry]) -> some View {
        if state.history.isEmpty {
            NLEmptyState(symbol: "text.alignleft", title: "Здесь будут ваши диктовки",
                         message: "Удерживайте \(state.hotkey.label) в любом окне и говорите.")
        } else if items.isEmpty {
            NLEmptyState(symbol: "magnifyingglass", title: "Ничего не нашлось",
                         message: query.isEmpty ? "В этом фильтре пока пусто." : "Нет диктовок со словами «\(query)».") {
                Button("Сбросить") {
                    state.historyQuery = ""
                    withMotion(Motion.base) { filter = .all; state.historyDay = nil }
                }
                .nlButton(.secondary, .sm)
            }
        }
    }
}

/// День: заголовок со счётом и диктовки карточкой.
private struct DaySection: View {
    let day: HistoryDay
    let actions: AppActions

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(HistoryFormat.sectionTitle(day.date))
                    .font(NLFont.ui(15, .bold))
                    .foregroundStyle(NL.textPrimary)
                Spacer()
                Text("\(day.entries.count) · \(wordsLabel(day.entries.reduce(0) { $0 + $1.words }))")
                    .font(NLFont.ui(12.5))
                    .monospacedDigit()
                    .foregroundStyle(NL.textTertiary)
            }
            EntryList(entries: day.entries, actions: actions)
        }
    }
}

/// Выбранный в календаре день - капсулой с крестиком.
private struct DayChip: View {
    let title: String
    let clear: () -> Void
    @State private var hover = false

    var body: some View {
        Button(action: clear) {
            HStack(spacing: 6) {
                Image(systemName: "calendar")
                    .font(.system(size: 11, weight: .medium))
                Text(title)
                    .font(NLFont.ui(12.5, .medium))
                Image(systemName: "xmark")
                    .font(.system(size: 9, weight: .bold))
                    .opacity(hover ? 1 : 0.6)
            }
            .foregroundStyle(NL.textAccent)
            .padding(.horizontal, 12)
            .frame(height: 28)
            .background(Capsule().fill(NL.accentSubtle))
            .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .onHover { hover = $0 }
        .help("Показать все дни")
        .accessibilityLabel("День \(title), показать все дни")
    }
}

/// Фильтры капсулами; выбранный - тёмной капсулой, она переезжает.
private struct FilterChips: View {
    @Binding var selection: HistoryView.Filter
    @Namespace private var thumb

    var body: some View {
        HStack(spacing: 4) {
            ForEach(HistoryView.Filter.allCases) { item in
                Chip(title: item.title, selected: selection == item, namespace: thumb) {
                    withMotion(Motion.position) { selection = item }
                }
            }
        }
    }

    private struct Chip: View {
        let title: String
        let selected: Bool
        let namespace: Namespace.ID
        let action: () -> Void
        @State private var hover = false

        var body: some View {
            Button(action: action) {
                Text(title)
                    .font(NLFont.ui(12.5, .medium))
                    .foregroundStyle(selected ? NL.canvas : hover ? NL.textPrimary : NL.textSecondary)
                    .padding(.horizontal, 12)
                    .frame(height: 28)
                    .background {
                        if selected {
                            Capsule().fill(NL.textPrimary)
                                .matchedGeometryEffect(id: "chip", in: namespace)
                        } else if hover {
                            Capsule().fill(NL.hover)
                        }
                    }
                    .contentShape(Capsule())
            }
            .buttonStyle(.plain)
            .onHover { hover = $0 }
            .animation(Motion.fast, value: hover)
            .accessibilityAddTraits(selected ? .isSelected : [])
        }
    }
}
