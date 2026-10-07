import SwiftUI

// Первый запуск, пока диктовок нет: три шага карточкой и проба. Пройденный
// шаг получает зелёную галочку, проба проступает, когда готово всё.
struct OnboardingView: View {
    @EnvironmentObject var state: AppState
    let actions: AppActions

    private var modelsReady: Bool { state.backend == .ready }
    private var allDone: Bool { state.micGranted && state.axTrusted && modelsReady }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                VStack(alignment: .leading, spacing: Space.s2) {
                    Text("Три шага — и можно говорить")
                        .font(NLFont.ui(30, .bold))
                        .tracking(-0.75)
                        .foregroundStyle(NL.textPrimary)
                    Text("Диктуйте в любом приложении. Звук и текст не покидают этот Mac — без аккаунта и облака.")
                        .font(NLFont.ui(14.5))
                        .lineSpacing(3)
                        .foregroundStyle(NL.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }

                VStack(spacing: 0) {
                    Step(number: 1, title: "Микрофон", detail: "Слушает, только пока вы держите клавишу.",
                         done: state.micGranted) {
                        Button("Разрешить") { openMicrophoneAccess(state) }
                            .buttonStyle(InkButtonStyle())
                    }
                    Step(number: 2, title: "Универсальный доступ", detail: "Чтобы текст сам вставлялся туда, где курсор.",
                         done: state.axTrusted) {
                        Button("Разрешить", action: openAccessibilityAccess)
                            .buttonStyle(InkButtonStyle())
                    }
                    .overlay(alignment: .top) { NL.borderSubtle.frame(height: 1) }
                    modelsStep
                        .overlay(alignment: .top) { NL.borderSubtle.frame(height: 1) }
                }
                .padding(.horizontal, 18)
                .nlCard(padding: 0)

                VStack(alignment: .leading, spacing: 14) {
                    Text(allDone ? "Всё готово — попробуйте" : "Потом — первая диктовка")
                        .font(NLFont.ui(15, .bold))
                        .foregroundStyle(NL.textPrimary)
                        .contentTransition(.opacity)
                    HStack(spacing: 8) {
                        Text("Удерживайте")
                        KeyCaps(preset: state.hotkey, size: 14)
                        Text("и скажите пару фраз.")
                    }
                    .font(NLFont.ui(14))
                    .foregroundStyle(NL.textSecondary)
                    Text("Или нажмите \(state.toggleHotkey.label) один раз — и ещё раз, когда закончите.")
                        .nlType(.caption)
                        .foregroundStyle(NL.textTertiary)
                }
                .padding(22)
                .nlCard(padding: 0)
                .opacity(allDone ? 1 : 0.45)
                .offset(y: allDone ? 0 : 4)
            }
            .frame(maxWidth: 560, alignment: .leading)
            .padding(.horizontal, Space.page)
            .padding(.top, Space.s8)
            .padding(.bottom, Space.s12)
            .frame(maxWidth: .infinity)
        }
        .motion(Motion.slow, value: [state.micGranted, state.axTrusted, modelsReady])
    }

    private var modelsStep: some View {
        Step(number: 3, title: "Модели распознавания", detail: modelsDetail, done: modelsReady,
             failed: modelsFailed) {
            if modelsFailed {
                Button("Журнал", action: actions.openLog)
                    .buttonStyle(InkButtonStyle())
            } else {
                IndeterminateBar()
                    .frame(width: 96, height: 4)
            }
        }
    }

    private var modelsFailed: Bool {
        if case .failed = state.backend { return true }
        return false
    }

    private var modelsDetail: String {
        switch state.backend {
        case .ready: return "GigaAM для русского, Parakeet для английского."
        case .starting: return state.setupStep == nil ? "Загружаем GigaAM и Parakeet — в первый раз около 850 МБ." : state.startingNote
        case let .failed(message): return message
        }
    }
}

/// Шаг: номер в кружке (пройден - зелёная галочка), название и пояснение,
/// справа - действие или «Готово».
private struct Step<Action: View>: View {
    let number: Int
    let title: String
    let detail: String
    let done: Bool
    var failed = false
    @ViewBuilder var action: () -> Action

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                Circle()
                    .fill(done ? NL.accent : .clear)
                Circle()
                    .strokeBorder(NL.borderStrong, lineWidth: 1.5)
                    .opacity(done ? 0 : 1)
                if done {
                    Image(systemName: "checkmark")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(NL.textOnAccent)
                        .transition(.scale(scale: 0.5).combined(with: .opacity))
                } else {
                    Text("\(number)")
                        .font(NLFont.ui(12.5, .semibold))
                        .foregroundStyle(NL.textSecondary)
                        .transition(.opacity)
                }
            }
            .frame(width: 26, height: 26)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(NLFont.ui(14.5, .semibold))
                    .foregroundStyle(done ? NL.textSecondary : NL.textPrimary)
                Text(detail)
                    .font(NLFont.ui(12.5))
                    .foregroundStyle(failed ? NL.textDanger : NL.textTertiary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: Space.s3)
            if done {
                Text("Готово")
                    .font(NLFont.ui(12.5, .semibold))
                    .foregroundStyle(NL.textAccent)
                    .transition(.scale(scale: 0.85).combined(with: .opacity))
            } else {
                action()
                    .transition(.opacity)
            }
        }
        .frame(minHeight: 70)
        .padding(.vertical, 4)
    }
}

/// Плотная кнопка цвета чернил - главное действие шага.
struct InkButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        InkBody(configuration: configuration)
    }

    private struct InkBody: View {
        let configuration: ButtonStyleConfiguration
        @State private var hover = false

        var body: some View {
            configuration.label
                .font(NLFont.ui(13, .semibold))
                .foregroundStyle(NL.canvas)
                .padding(.horizontal, 14)
                .frame(height: 30)
                .background(NL.textPrimary.opacity(hover ? 0.88 : 1),
                            in: RoundedRectangle(cornerRadius: 9, style: .continuous))
                .scaleEffect(configuration.isPressed ? 0.97 : 1)
                .contentShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
                .onHover { hover = $0 }
                .animation(Motion.fast, value: hover)
                .animation(Motion.fast, value: configuration.isPressed)
        }
    }
}
