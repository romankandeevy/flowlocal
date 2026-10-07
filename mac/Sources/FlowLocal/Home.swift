import SwiftUI

// «Главная» - ради одного: открыть окно, взять недавнюю диктовку и уйти.
// Сверху приветствие и сочетание, под ним то, что требует внимания, и
// живая запись, если идёт. Дальше - четыре числа за день и диктовки
// сегодня: щелчок по строке копирует. Пока диктовок нет - первые шаги.
struct HomeView: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    var body: some View {
        ZStack {
            if state.history.isEmpty && !state.isBusy {
                OnboardingView(actions: actions)
                    .transition(.opacity)
            } else {
                PageScroll {
                    header
                    AttentionBanner(actions: actions)
                    if state.isBusy {
                        LivePanel(actions: actions)
                            .padding(Space.insetLg)
                            .nlCard(padding: 0)
                            .transition(.opacity.combined(with: .offset(y: -6)))
                    }
                    stats
                    recent
                }
                .entryKeys(recentItems, actions: actions)
                .transition(.opacity)
            }
        }
        .motion(Motion.moderate, value: state.history.isEmpty)
        .motion(Motion.slow, value: state.isBusy)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: Space.s2) {
            Text(greeting)
                .font(NLFont.ui(30, .bold))
                .tracking(-0.75)
                .foregroundStyle(NL.textPrimary)
            HStack(spacing: 6) {
                Text("Удерживайте")
                KeyCaps(preset: state.hotkey)
                Text("в любом окне и говорите — текст появится там, где курсор.")
                    .lineLimit(1)
                    .minimumScaleFactor(0.9)
            }
            .font(NLFont.ui(14.5))
            .foregroundStyle(NL.textSecondary)
        }
    }

    private var greeting: String {
        switch Calendar.current.component(.hour, from: Date()) {
        case 5..<12: return "Доброе утро"
        case 12..<18: return "Добрый день"
        case 18..<23: return "Добрый вечер"
        default: return "Доброй ночи"
        }
    }

    private var stats: some View {
        HStack(spacing: 10) {
            StatTile(value: grouped(state.wordsToday), label: plural(state.wordsToday, "слово", "слова", "слов") + " сегодня")
            StatTile(value: grouped(state.dictationsToday),
                     label: plural(state.dictationsToday, "диктовка", "диктовки", "диктовок"))
            StatTile(value: state.speedWPM > 0 ? grouped(state.speedWPM) : "—", label: "слов в минуту")
            StatTile(value: ratio, label: "быстрее клавиатуры")
        }
    }

    private var ratio: String {
        guard state.speedWPM > 0 else { return "—" }
        return state.voiceRatio.formatted(.number.precision(.fractionLength(1))) + "×"
    }

    private var today: [Entry] { state.history.filter { Calendar.current.isDateInToday($0.date) } }

    /// Сегодняшние диктовки; сегодня пусто - пять последних.
    private var recentItems: [Entry] {
        let today = today
        return today.isEmpty ? Array(state.history.prefix(5)) : Array(today.prefix(12))
    }

    private var recent: some View {
        let today = today
        let items = recentItems
        return VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(today.isEmpty ? "Недавние" : "Сегодня")
                    .font(NLFont.ui(15, .bold))
                    .foregroundStyle(NL.textPrimary)
                Spacer()
                Button {
                    withMotion(Motion.position) { state.tab = .history }
                } label: {
                    Text("Вся история →")
                        .font(NLFont.ui(13, .medium))
                        .foregroundStyle(NL.textAccent)
                }
                .buttonStyle(.plain)
            }
            EntryList(entries: items, actions: actions, showDay: today.isEmpty)
                .motion(Motion.moderate, value: items.map(\.id))
        }
    }
}

/// Число и подпись в карточке.
struct StatTile: View {
    let value: String
    let label: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value)
                .font(NLFont.ui(22, .bold))
                .tracking(-0.4)
                .monospacedDigit()
                .foregroundStyle(NL.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .contentTransition(.numericText())
            Text(label)
                .nlType(.caption)
                .foregroundStyle(NL.textTertiary)
                .lineLimit(1)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .nlCard(padding: 0, radius: 12)
        .motion(Motion.slow, value: value)
        .accessibilityElement(children: .combine)
    }
}

/// Что мешает диктовать - одной плашкой, самое важное первым.
private struct AttentionBanner: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    var body: some View {
        Group {
            if case let .failed(message) = state.backend {
                // Не завелось окружение (первый запуск из .dmg, нет сети) -
                // проще всего попробовать ещё раз; иначе - журнал.
                if PythonSetup.needed {
                    NLAlert(kind: .danger, title: "Распознавание не подготовилось", message: message,
                            actionTitle: "Ещё раз", action: actions.retrySetup)
                } else {
                    NLAlert(kind: .danger, title: "Распознавание не запустилось", message: message,
                            actionTitle: "Журнал", action: actions.openLog)
                }
            } else if !state.micGranted {
                NLAlert(kind: .warning, title: "Нет доступа к микрофону", message: "Без него диктовка не начнётся.",
                        actionTitle: "Разрешить", action: { openMicrophoneAccess(state) })
            } else if state.backend == .starting {
                NLAlert(kind: .info, title: state.setupStep == nil ? "Загружаю распознавание" : "Готовлю распознавание",
                        message: state.startingNote)
            } else if !state.axTrusted {
                NLAlert(kind: .warning, title: "Текст не вставится сам",
                        message: "Без универсального доступа диктовка попадёт только в буфер обмена.",
                        actionTitle: "Разрешить", action: openAccessibilityAccess)
            }
        }
        .transition(.opacity)
        .motion(Motion.moderate, value: state.statusText)
    }
}
