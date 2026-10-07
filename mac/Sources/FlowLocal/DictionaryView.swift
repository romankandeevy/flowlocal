import SwiftUI

// «Словарь» - как писать имена и термины, и что выучено из правок. Термины
// - капсулами: пишется похоже - ставится как в словаре (Vocabulary).
// Исправления - парами «было → стало»; учатся сами из правок в истории и в
// поле, куда легла диктовка.
struct DictionaryView: View {
    @EnvironmentObject var state: AppState
    @State private var draft = ""
    @FocusState private var fieldFocused: Bool

    var body: some View {
        PageScroll {
            VStack(alignment: .leading, spacing: Space.s2) {
                PageTitle("Словарь")
                Text("Имена, названия и термины, которые модель пишет неправильно. Похожее на слух слово заменится на то, как оно записано здесь: «гитхаб» → GitHub, «клод» → Claude.")
                    .font(NLFont.ui(14.5))
                    .lineSpacing(3)
                    .foregroundStyle(NL.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            terms
            learned
        }
    }

    private var terms: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 8) {
                TextField("", text: $draft, prompt: Text("Добавить слово или название").foregroundColor(NL.textPlaceholder))
                    .textFieldStyle(.plain)
                    .font(NLFont.ui(14))
                    .foregroundStyle(NL.textPrimary)
                    .focused($fieldFocused)
                    .onSubmit(add)
                    .padding(.horizontal, 14)
                    .frame(height: 40)
                    .background(NL.surface, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                    .overlay {
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .strokeBorder(fieldFocused ? NL.borderFocus : NL.border, lineWidth: fieldFocused ? 1 : 0.5)
                    }
                    .animation(Motion.base, value: fieldFocused)
                Button("Добавить", action: add)
                    .buttonStyle(InkButtonStyle())
                    .disabled(draft.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            if state.vocabulary.isEmpty {
                Text("Пока пусто. Добавьте имена коллег, названия проектов и сервисов — всё, что модель пишет по-своему.")
                    .font(NLFont.ui(13))
                    .foregroundStyle(NL.textTertiary)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                WordFlow(spacing: 6, lineSpacing: 6) {
                    ForEach(state.vocabulary, id: \.self) { term in
                        TermChip(term: term) {
                            withMotion(Motion.moderate) { state.vocabulary.removeAll { $0 == term } }
                        }
                        .transition(.scale(scale: 0.9).combined(with: .opacity))
                    }
                }
                .motion(Motion.moderate, value: state.vocabulary)
            }
        }
    }

    private var learned: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeading("Исправления")
            VStack(spacing: 0) {
                ToggleRow(title: "Учиться на исправлениях",
                          detail: "Поправили слово в истории («Исправить…») или прямо в поле после вставки — в следующий раз оно напишется правильно.",
                          isOn: $state.learnFromEdits)
                ForEach(state.corrections) { item in
                    CorrectionRow(item: item) {
                        withMotion(Motion.moderate) { state.corrections.removeAll { $0.id == item.id } }
                    }
                    .overlay(alignment: .top) { NL.borderSubtle.frame(height: 1) }
                    .transition(.opacity)
                }
                if state.corrections.isEmpty {
                    Text("Выученных исправлений пока нет.")
                        .font(NLFont.ui(13))
                        .foregroundStyle(NL.textTertiary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 18)
                        .frame(height: 48)
                        .overlay(alignment: .top) { NL.borderSubtle.frame(height: 1) }
                }
            }
            .nlCard(padding: 0)
            .motion(Motion.moderate, value: state.corrections.map(\.id))
        }
    }

    private func add() {
        let parts = draft.split(whereSeparator: { $0 == "," || $0 == "\n" })
        withMotion(Motion.moderate) {
            for p in parts { state.addTerm(String(p)) }
        }
        draft = ""
    }
}

/// Термин капсулой; × при наведении.
private struct TermChip: View {
    let term: String
    let remove: () -> Void
    @State private var hover = false

    var body: some View {
        HStack(spacing: 6) {
            Text(term)
                .font(NLFont.ui(13.5, .medium))
                .foregroundStyle(NL.textPrimary)
            Button(action: remove) {
                Image(systemName: "xmark")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(hover ? NL.textPrimary : NL.textQuaternary)
            }
            .buttonStyle(.plain)
            .help("Убрать из словаря")
            .accessibilityLabel("Убрать \(term)")
        }
        .padding(.leading, 12)
        .padding(.trailing, 10)
        .frame(height: 30)
        .background(NL.surface, in: Capsule())
        .overlay { Capsule().strokeBorder(hover ? NL.borderStrong : NL.border, lineWidth: 1) }
        .onHover { hover = $0 }
        .animation(Motion.fast, value: hover)
    }
}

/// «было → стало» и сколько раз так поправили.
private struct CorrectionRow: View {
    let item: Vocabulary.Correction
    let remove: () -> Void
    @State private var hover = false

    var body: some View {
        HStack(spacing: 10) {
            Text(item.from)
                .font(NLFont.ui(14))
                .strikethrough(color: NL.textQuaternary)
                .foregroundStyle(NL.textTertiary)
            Image(systemName: "arrow.right")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(NL.textQuaternary)
            Text(item.to)
                .font(NLFont.ui(14, .semibold))
                .foregroundStyle(NL.textPrimary)
            Spacer()
            if item.count > 1 {
                Text("×\(item.count)")
                    .font(NLFont.ui(12, .medium))
                    .monospacedDigit()
                    .foregroundStyle(NL.textQuaternary)
            }
            Button(action: remove) {
                Image(systemName: "xmark")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(NL.textTertiary)
                    .frame(width: 26, height: 26)
                    .background(Circle().fill(hover ? NL.hover : .clear))
                    .contentShape(Circle())
            }
            .buttonStyle(.plain)
            .opacity(hover ? 1 : 0)
            .help("Забыть это исправление")
            .accessibilityLabel("Забыть \(item.from)")
        }
        .padding(.horizontal, 18)
        .frame(height: 48)
        .background(hover ? NL.rowHover : .clear)
        .onHover { hover = $0 }
        .animation(Motion.fast, value: hover)
    }
}
