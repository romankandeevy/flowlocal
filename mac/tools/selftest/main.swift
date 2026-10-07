import Foundation

// Самопроверка логики без окна: словарь, обучение на правках, стили,
// режим шёпота. Запуск: tools/selftest.sh

var failures = 0
func check(_ ok: Bool, _ name: String, _ detail: @autoclosure () -> String = "") {
    if ok { print("  ✓ \(name)") } else { failures += 1; print("  ✗ \(name) \(detail())") }
}
func eq(_ a: String, _ b: String, _ name: String) { check(a == b, name, "\n      получили: «\(a)»\n      ждали:    «\(b)»") }

print("Словарь")
eq(Vocabulary.apply("Залей на гитхаб сегодня.", terms: ["GitHub"]), "Залей на GitHub сегодня.", "гитхаб → GitHub")
eq(Vocabulary.apply("Залей на гит хаб сегодня.", terms: ["GitHub"]), "Залей на GitHub сегодня.", "гит хаб → GitHub")
eq(Vocabulary.apply("Спроси у клода.", terms: ["Claude"]), "Спроси у Claude.", "клода → Claude")
eq(Vocabulary.apply("Позвони Кондееву завтра.", terms: ["Кандееву"]), "Позвони Кандееву завтра.", "Кондееву → Кандееву")
eq(Vocabulary.apply("Маша пришла.", terms: ["Саша"]), "Маша пришла.", "Маша не становится Сашей")
eq(Vocabulary.apply("И это всё.", terms: ["Ио"]), "И это всё.", "короткие слова не трогаем")
eq(Vocabulary.apply("Открой фигму, пожалуйста.", terms: ["Figma"]), "Открой Figma, пожалуйста.", "фигму → Figma")
eq(Vocabulary.apply("Visual Studio Code открыт.", terms: ["Visual Studio Code"]), "Visual Studio Code открыт.", "точное совпадение не меняется")
eq(Vocabulary.apply("Текст без терминов.", terms: []), "Текст без терминов.", "пустой словарь")

print("Обучение на правках")
func pairs(_ a: String, _ b: String) -> String { Vocabulary.learn(original: a, edited: b).map { "\($0.from)→\($0.to)" }.joined(separator: ", ") }
eq(pairs("Залей на гитхап сегодня", "Залей на GitHub сегодня"), "гитхап→GitHub", "одно слово")
eq(pairs("Встреча с Олегом Кондеевым в пять", "Встреча с Олегом Кандеевым в пять"), "Кондеевым→Кандеевым", "фамилия")
eq(pairs("открой github", "открой GitHub"), "github→GitHub", "смена регистра внутри слова")
eq(pairs("Скинь ссылку вечером", "Скинь ссылку вечером, и ещё фото с прогулки"), "", "дописанный хвост - не правка")
eq(pairs("Скинь ссылку вечером", "Совсем другой текст про погоду на завтра"), "", "переписанное - не правка")
eq(pairs("Пойдём в кино", "Пойдём в кино"), "", "без изменений")
let merged = Vocabulary.merge([("гитхап", "GitHub")], into: Vocabulary.merge([("гитхап", "GitHub")], into: []))
check(merged.count == 1 && merged[0].count == 2, "повтор правки увеличивает счёт")

print("Правка в поле")
let region = Vocabulary.editedRegion(now: "Привет. Скинь ссылку на GitHub вечером. Пока!", before: "Привет.",
                                     after: "Пока!", inserted: "Скинь ссылку на гитхаб вечером.")
eq(region ?? "nil", " Скинь ссылку на GitHub вечером. ", "нашли вставленный кусок между соседями")
eq(pairs("Скинь ссылку на гитхаб вечером.", (region ?? "").trimmingCharacters(in: .whitespaces)), "гитхаб→GitHub", "и выучили из него")
check(Vocabulary.editedRegion(now: "совсем другое", before: "Привет.", after: "", inserted: "x") == nil, "нет опоры - не учимся")

print("Стиль по приложению")
let base = CleanupOptions()
func styled(_ raw: String, _ style: TextStyle) -> String { style.finish(Vocabulary.apply(TextCleaner.clean(raw, style.adjust(base)), terms: ["GitHub"])) }
eq(styled("Скину ссылку вечером.", .chat), "скину ссылку вечером", "переписка: маленькая буква, без точки")
eq(styled("Я приду вечером.", .chat), "Я приду вечером", "переписка: «Я» остаётся")
eq(styled("гитхаб упал.", .chat), "GitHub упал", "переписка: термин с заглавной")
eq(styled("скину ссылку вечером", .formal), "Скину ссылку вечером.", "письмо: заглавная и точка")
eq(styled("Ну, короче, скину ссылку", .formal), "Скину ссылку.", "письмо: строгая чистка")
eq(styled("Скину ссылку вечером.", .standard), "Скину ссылку вечером.", "обычный: как в настройках")
check(!TextStyle.code.addsSpace && TextStyle.chat.addsSpace, "код - без пробела после вставки")
check(AppStyleRule.style(for: "ru.keepcoder.Telegram", in: AppStyleRule.suggestions) == .chat, "Telegram - переписка")
check(AppStyleRule.style(for: "com.unknown", in: AppStyleRule.suggestions) == .standard, "неизвестное - обычный")

print("Режим шёпота")
func rms(_ x: ArraySlice<Float>) -> Float { sqrt(x.reduce(0) { $0 + $1 * $1 } / Float(max(1, x.count))) }
func tone(_ amp: Float, seconds: Double) -> [Float] {
    (0..<Int(16000 * seconds)).map { amp * sin(2 * .pi * 220 * Float($0) / 16000) }
}
var g = WhisperGain()
var whisper = tone(0.004, seconds: 2)
let before = rms(whisper[16000...])
for i in stride(from: 0, to: whisper.count, by: 1600) {
    var chunk = Array(whisper[i..<min(i + 1600, whisper.count)])
    g.process(&chunk)
    whisper.replaceSubrange(i..<i + chunk.count, with: chunk)
}
let after = rms(whisper[16000...])
check(after > before * 8, "шёпот усилен", String(format: "%.4f → %.4f", before, after))
check(after < 0.12, "но не громче обычной речи", String(format: "%.4f", after))
var g2 = WhisperGain()
var loud = tone(0.5, seconds: 1)
g2.process(&loud)
check(loud.allSatisfy { abs($0) <= 1 }, "громкое не срезается за 1.0")
check(rms(loud[8000...]) < 0.4, "громкое не раздувается", String(format: "%.3f", rms(loud[8000...])))
var g3 = WhisperGain()
var hiss: [Float] = (0..<32000).map { _ in Float.random(in: -0.0008...0.0008) }
g3.process(&hiss)
check(rms(hiss[16000...]) < 0.004, "тишина не превращается в шум", String(format: "%.4f", rms(hiss[16000...])))

print(failures == 0 ? "\nВсё прошло." : "\nНе прошло: \(failures)")
exit(failures == 0 ? 0 : 1)
