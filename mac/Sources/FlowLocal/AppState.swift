import AppKit
import SwiftUI

enum Phase: Equatable {
    case idle
    case loading                              // хоткей нажат, а модель ещё грузится
    case recording(since: Date, locked: Bool) // locked - запись по нажатию, до следующего нажатия
    case processing
    case done(String)
    case copied(String)                       // не вставилось - текст ждёт в буфере
    case failed(String)
}

enum BackendState: Equatable {
    case starting
    case ready
    case failed(String)
}

/// Разделы главного окна - пункты сайдбара. Настроек в окне нет: они в
/// Hub Settings, ⌘, открывает его.
enum Tab: String, CaseIterable, Identifiable {
    case home, history, stats, style, dictionary

    var id: String { rawValue }
    var title: String {
        switch self {
        case .home: return "Главная"
        case .history: return "История"
        case .stats: return "Обзор"
        case .style: return "Стиль"
        case .dictionary: return "Словарь"
        }
    }

    var symbol: String {
        switch self {
        case .home: return "house"
        case .history: return "list.bullet"
        case .stats: return "chart.bar"
        case .style: return "textformat"
        case .dictionary: return "character.book.closed"
        }
    }

    /// ⌘1, ⌘2 - в меню «Вид».
    var shortcut: KeyEquivalent {
        KeyEquivalent(Character(String((Tab.allCases.firstIndex(of: self) ?? 0) + 1)))
    }
}

/// Оформление окна и индикатора.
enum AppAppearance: String, CaseIterable, Identifiable {
    case system, light, dark

    var id: String { rawValue }
    var title: String {
        switch self {
        case .system: return "Как в системе"
        case .light: return "Светлое"
        case .dark: return "Тёмное"
        }
    }

    var nsAppearance: NSAppearance? {
        switch self {
        case .system: return nil
        case .light: return NSAppearance(named: .aqua)
        case .dark: return NSAppearance(named: .darkAqua)
        }
    }
}

/// Где индикатор записи.
enum PillPosition: String, CaseIterable, Identifiable {
    case bottom, top

    var id: String { rawValue }
    var title: String { self == .bottom ? "Внизу" : "Вверху" }
}

/// Размер капсулы записи.
enum PillSize: String, CaseIterable, Identifiable {
    case compact, regular, large

    var id: String { rawValue }
    var title: String {
        switch self {
        case .compact: return "Мелкая"
        case .regular: return "Обычная"
        case .large: return "Крупная"
        }
    }
    var scale: CGFloat {
        switch self {
        case .compact: return 0.85
        case .regular: return 1
        case .large: return 1.2
        }
    }
}

/// Ширина бегущей строки в капсуле.
enum PillTextWidth: String, CaseIterable, Identifiable {
    case narrow, medium, wide

    var id: String { rawValue }
    var title: String {
        switch self {
        case .narrow: return "Узкая"
        case .medium: return "Средняя"
        case .wide: return "Широкая"
        }
    }
    var points: CGFloat {
        switch self {
        case .narrow: return 180
        case .medium: return 300
        case .wide: return 440
        }
    }
}

/// Замена в тексте: «флоу локал» → «Flow Local».
struct Replacement: Identifiable, Codable, Equatable {
    var id = UUID()
    var from: String
    var to: String

    static func pairs(_ list: [Replacement]) -> [[String]] {
        list.map { [$0.from, $0.to] }
    }

    /// Из UserDefaults: парами строк (Hub Settings) или JSON-ом прошлых версий.
    static func load(_ raw: Any?) -> [Replacement]? {
        if let pairs = raw as? [[String]] {
            return pairs.filter { $0.count == 2 }.map { Replacement(from: $0[0], to: $0[1]) }
        }
        if let data = raw as? Data {
            return try? JSONDecoder().decode([Replacement].self, from: data)
        }
        return nil
    }
}

/// Язык распознавания: авто - GigaAM и переспрос Parakeet по кускам.
enum LangMode: String, CaseIterable, Identifiable {
    case auto, ru, en

    var id: String { rawValue }
    var title: String {
        switch self {
        case .auto: return "Авто"
        case .ru: return "Русский"
        case .en: return "English"
        }
    }
}

struct Entry: Identifiable, Codable, Equatable {
    let id: UUID
    var text: String
    var lang: String
    let date: Date
    let seconds: Double
    // Слова считаются один раз, а не на каждой перерисовке: статистика
    // пробегает всю историю, и пересчёт при каждом кадре тормозил окно.
    var words: Int
    var audio: String?          // имя WAV в AudioStore
    var failed: Bool            // речь не распознана - можно распознать заново
    /// Текст до чистки - если чистка что-то убрала.
    var raw: String?
    /// Куда диктовали: приложение впереди в начале записи.
    var appID: String?
    var appName: String?
    /// Перераспознали - в записи тишина: распознавать нечего.
    var silent: Bool?

    init(id: UUID = UUID(), text: String, lang: String, date: Date = Date(), seconds: Double,
         audio: String? = nil, failed: Bool = false) {
        self.id = id
        self.text = text
        self.lang = lang
        self.date = date
        self.seconds = seconds
        self.words = Entry.count(text)
        self.audio = audio
        self.failed = failed
    }

    static func count(_ text: String) -> Int {
        text.split(whereSeparator: { $0.isWhitespace }).count
    }

    // История прошлых версий - без words/audio/failed.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        text = try c.decode(String.self, forKey: .text)
        lang = try c.decode(String.self, forKey: .lang)
        date = try c.decode(Date.self, forKey: .date)
        seconds = try c.decode(Double.self, forKey: .seconds)
        words = try c.decodeIfPresent(Int.self, forKey: .words) ?? Entry.count(text)
        audio = try c.decodeIfPresent(String.self, forKey: .audio)
        failed = try c.decodeIfPresent(Bool.self, forKey: .failed) ?? false
        raw = try c.decodeIfPresent(String.self, forKey: .raw)
        appID = try c.decodeIfPresent(String.self, forKey: .appID)
        appName = try c.decodeIfPresent(String.self, forKey: .appName)
        silent = try c.decodeIfPresent(Bool.self, forKey: .silent)
    }
}

/// Слова за день - столбик недельного графика.
struct DayWords: Identifiable {
    let date: Date
    let words: Int
    var id: Date { date }
}

/// «1 слово», «2 слова», «5 слов».
func plural(_ n: Int, _ one: String, _ few: String, _ many: String) -> String {
    let m10 = n % 10, m100 = n % 100
    if m10 == 1 && m100 != 11 { return one }
    if (2...4).contains(m10) && !(12...14).contains(m100) { return few }
    return many
}

func wordsLabel(_ n: Int) -> String {
    "\(n) \(plural(n, "слово", "слова", "слов"))"
}

/// «1 284 слова» - с разрядами.
func groupedWords(_ n: Int) -> String {
    "\(grouped(n)) \(plural(n, "слово", "слова", "слов"))"
}

/// «130 слов в минуту».
func perMinute(_ n: Int) -> String {
    "\(grouped(n)) \(plural(n, "слово", "слова", "слов")) в минуту"
}

/// Разряды - неразрывным пробелом: «1 284».
func grouped(_ n: Int) -> String {
    let f = NumberFormatter()
    f.numberStyle = .decimal
    f.groupingSeparator = "\u{00A0}"
    return f.string(from: NSNumber(value: n)) ?? "\(n)"
}

final class AppState: ObservableObject {
    /// «Удерживая клавиши»: пишем, пока держат.
    @Published var hotkey: HotkeyPreset {
        didSet { hotkey.save(.hold) }
    }
    /// «По нажатию»: нажал - говоришь, нажал ещё раз - текст на месте.
    @Published var toggleHotkey: HotkeyPreset {
        didSet { toggleHotkey.save(.toggle) }
    }
    // Раздел окна переживает перезапуск, как у приложений Apple; поиск - нет.
    @Published var tab: Tab {
        didSet { UserDefaults.standard.set(tab.rawValue, forKey: "section") }
    }
    @Published var historyQuery = ""
    /// День, выбранный в календаре истории или на графике «Обзора».
    @Published var historyDay: Date?
    /// ⌘F: растёт - поле поиска забирает фокус.
    @Published var searchFocusRequest = 0
    @Published var historySelection: Set<UUID> = []
    @Published var backend: BackendState = .starting
    /// Первый запуск из .dmg: приложение заводит себе Python (PythonSetup).
    @Published var setupStep: PythonSetup.Step?
    /// Открыт шаг «Первая диктовка» в обучении: диктовка не вставляется.
    @Published var tutorialPractice = false

    /// Что сейчас делается до готовности распознавания - одной строкой.
    var startingNote: String {
        switch setupStep {
        case .downloading(let f?): return "Скачиваю Python для распознавания — \(Int(f * 100))%. Один раз."
        case .downloading(nil): return "Скачиваю Python для распознавания. Один раз."
        case .unpacking: return "Распаковываю Python…"
        case .installing: return "Ставлю библиотеки распознавания — минута-две, один раз."
        case nil: return "Первый раз после запуска — около 20 секунд, при самом первом — докачка моделей (~850 МБ)."
        }
    }
    @Published var englishReady = false
    @Published var phase: Phase = .idle {
        didSet { if phase != oldValue { SuiteBroadcast.phase(phase) } }
    }
    @Published var history: [Entry] = []
    @Published var micGranted = false
    @Published var axTrusted = false

    // Живая расшифровка и счёт слов - в LiveWords: каждый кусок разбора
    // перерисовывал бы отсюда всё окно вместе с лентой.
    @Published var recordSeconds: Double = 0

    // Что сейчас играет и что распознаётся заново - для кнопок в истории.
    @Published var playing: UUID?
    @Published var rerecognizing: Set<UUID> = []

    // Настройки. Меняют их в Hub Settings: он пишет эти же ключи UserDefaults
    // и зовёт HubSync, а тот ставит новые значения сюда.
    @Published var insertAutomatically: Bool {
        didSet { UserDefaults.standard.set(insertAutomatically, forKey: "insertAutomatically") }
    }
    @Published var showPill: Bool {
        didSet { UserDefaults.standard.set(showPill, forKey: "showPill") }
    }
    @Published var saveAudio: Bool {
        didSet { UserDefaults.standard.set(saveAudio, forKey: "saveAudio") }
    }
    @Published var sounds: Bool {
        didSet { UserDefaults.standard.set(sounds, forKey: "sounds") }
    }
    @Published var langMode: LangMode {
        didSet { UserDefaults.standard.set(langMode.rawValue, forKey: "langMode") }
    }
    @Published var micUID: String? {
        didSet { UserDefaults.standard.set(micUID, forKey: "micUID") }
    }
    @Published var micDevices: [AudioDevice] = []
    @Published var launchAtLogin = false

    @Published var appearance: AppAppearance {
        didSet { UserDefaults.standard.set(appearance.rawValue, forKey: "appearance") }
    }
    @Published var showMenuBarIcon: Bool {
        didSet { UserDefaults.standard.set(showMenuBarIcon, forKey: "showMenuBarIcon") }
    }
    @Published var showInDock: Bool {
        didSet { UserDefaults.standard.set(showInDock, forKey: "showInDock") }
    }
    @Published var addSpace: Bool {
        didSet { UserDefaults.standard.set(addSpace, forKey: "addSpace") }
    }
    @Published var keepInClipboard: Bool {
        didSet { UserDefaults.standard.set(keepInClipboard, forKey: "keepInClipboard") }
    }
    @Published var pillPosition: PillPosition {
        didSet { UserDefaults.standard.set(pillPosition.rawValue, forKey: "pillPosition") }
    }
    @Published var pillLiveText: Bool {
        didSet { UserDefaults.standard.set(pillLiveText, forKey: "pillLiveText") }
    }
    @Published var pillShowDot: Bool {
        didSet { UserDefaults.standard.set(pillShowDot, forKey: "pillShowDot") }
    }
    @Published var pillShowTimer: Bool {
        didSet { UserDefaults.standard.set(pillShowTimer, forKey: "pillShowTimer") }
    }
    @Published var pillShowWave: Bool {
        didSet { UserDefaults.standard.set(pillShowWave, forKey: "pillShowWave") }
    }
    @Published var pillShowStatus: Bool {
        didSet { UserDefaults.standard.set(pillShowStatus, forKey: "pillShowStatus") }
    }
    @Published var pillTextWidth: PillTextWidth {
        didSet { UserDefaults.standard.set(pillTextWidth.rawValue, forKey: "pillTextWidth") }
    }
    @Published var pillSize: PillSize {
        didSet { UserDefaults.standard.set(pillSize.rawValue, forKey: "pillSize") }
    }
    /// Сколько дней хранить историю; 0 - всегда. Хранится строкой: это вариант
    /// выбора в Hub Settings.
    @Published var historyDays: Int {
        didSet { UserDefaults.standard.set(String(historyDays), forKey: "historyDays"); pruneHistory() }
    }

    // Чистка текста.
    @Published var cleanupLevel: CleanupLevel {
        didSet { UserDefaults.standard.set(cleanupLevel.rawValue, forKey: "cleanupLevel") }
    }
    @Published var removeRepeats: Bool {
        didSet { UserDefaults.standard.set(removeRepeats, forKey: "removeRepeats") }
    }
    @Published var capitalize: Bool {
        didSet { UserDefaults.standard.set(capitalize, forKey: "capitalize") }
    }
    @Published var trailingPeriod: Bool {
        didSet { UserDefaults.standard.set(trailingPeriod, forKey: "trailingPeriod") }
    }
    @Published var customFillers: String {
        didSet { UserDefaults.standard.set(customFillers, forKey: "customFillers") }
    }
    /// Хранятся парами строк [было, стало] - так их правит Hub Settings.
    @Published var replacements: [Replacement] {
        didSet { UserDefaults.standard.set(Replacement.pairs(replacements), forKey: "replacements") }
    }

    /// Режим шёпота: тихая речь усиливается до разбора.
    @Published var whisperMode: Bool {
        didSet { UserDefaults.standard.set(whisperMode, forKey: "whisperMode") }
    }
    /// Стиль текста по приложениям - настраивается в окне, во вкладке «Стиль».
    @Published var appStyles: [AppStyleRule] {
        didSet { Self.save(appStyles, "appStyles") }
    }
    /// Словарь: имена и термины, как их писать.
    @Published var vocabulary: [String] {
        didSet { UserDefaults.standard.set(vocabulary, forKey: "vocabulary") }
    }
    /// Выученные из правок замены.
    @Published var corrections: [Vocabulary.Correction] {
        didSet { Self.save(corrections, "learnedCorrections") }
    }
    @Published var learnFromEdits: Bool {
        didSet { UserDefaults.standard.set(learnFromEdits, forKey: "learnFromEdits") }
    }
    /// Диктовка, которую правят в окне («Исправить…»).
    @Published var editing: Entry?
    /// Короткие метки у строк истории: «Распознано заново», «В записи тишина».
    @Published var rowNotes: [UUID: String] = [:]

    func note(_ id: UUID, _ text: String) {
        rowNotes[id] = text
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.4) { [weak self] in
            if self?.rowNotes[id] == text { self?.rowNotes[id] = nil }
        }
    }

    private static func save<T: Encodable>(_ value: T, _ key: String) {
        if let data = try? JSONEncoder().encode(value) { UserDefaults.standard.set(data, forKey: key) }
    }

    private static func load<T: Decodable>(_ type: T.Type, _ key: String) -> T? {
        UserDefaults.standard.data(forKey: key).flatMap { try? JSONDecoder().decode(T.self, from: $0) }
    }

    func style(for appID: String?) -> TextStyle {
        AppStyleRule.style(for: appID, in: appStyles)
    }

    /// Чистка под стиль приложения; выученные исправления - после своих замен.
    func cleanup(for style: TextStyle) -> CleanupOptions {
        var o = style.adjust(cleanup)
        o.replacements += corrections.map { ($0.from, $0.to) }
        return o
    }

    /// Распознанное - в текст диктовки: чистка, словарь, отделка стиля.
    func process(_ raw: String, style: TextStyle) -> String {
        let clean = TextCleaner.clean(raw, cleanup(for: style))
        return style.finish(Vocabulary.apply(clean, terms: vocabulary))
    }

    func addCorrections(_ pairs: [(from: String, to: String)]) {
        guard !pairs.isEmpty else { return }
        corrections = Vocabulary.merge(pairs, into: corrections)
        Log.write("выучено исправлений: \(pairs.count)")
    }

    /// Правка диктовки в окне: новый текст и, если включено, урок.
    func saveEdit(_ entry: Entry, text: String) {
        let edited = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard edited != entry.text else { return }
        if learnFromEdits, !entry.failed { addCorrections(Vocabulary.learn(original: entry.text, edited: edited)) }
        var e = entry
        e.text = edited
        e.words = Entry.count(edited)
        e.failed = edited.isEmpty
        update(e)
    }

    func addTerm(_ term: String) {
        let t = term.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty, !vocabulary.contains(where: { $0.caseInsensitiveCompare(t) == .orderedSame }) else { return }
        vocabulary.append(t)
    }

    var cleanup: CleanupOptions {
        CleanupOptions(level: cleanupLevel, removeRepeats: removeRepeats, capitalize: capitalize,
                       trailingPeriod: trailingPeriod,
                       customFillers: customFillers.split(whereSeparator: { $0 == "," || $0 == "\n" }).map(String.init),
                       replacements: replacements.map { ($0.from, $0.to) })
    }

    /// Текст диктовки после чистки и замен.
    func cleaned(_ text: String) -> String {
        TextCleaner.clean(text, cleanup)
    }

    /// История прочиталась целиком (или её ещё не было). Не прочиталась -
    /// записи на диске не чистим: иначе сбой разбора стёр бы и звук.
    private(set) var historyLoaded = true

    init() {
        let d = UserDefaults.standard
        hotkey = HotkeyPreset.load(.hold)
        toggleHotkey = HotkeyPreset.load(.toggle)
        tab = Tab(rawValue: d.string(forKey: "section") ?? "") ?? .home
        insertAutomatically = d.object(forKey: "insertAutomatically") as? Bool ?? true
        showPill = d.object(forKey: "showPill") as? Bool ?? true
        saveAudio = d.object(forKey: "saveAudio") as? Bool ?? true
        sounds = d.object(forKey: "sounds") as? Bool ?? false
        langMode = LangMode(rawValue: d.string(forKey: "langMode") ?? "") ?? .auto
        micUID = d.string(forKey: "micUID").flatMap { $0.isEmpty ? nil : $0 }
        appearance = AppAppearance(rawValue: d.string(forKey: "appearance") ?? "") ?? .system
        showMenuBarIcon = d.object(forKey: "showMenuBarIcon") as? Bool ?? true
        showInDock = d.object(forKey: "showInDock") as? Bool ?? true
        addSpace = d.object(forKey: "addSpace") as? Bool ?? true
        // Диктовка остаётся в буфере: её можно вставить ещё раз, в другое
        // место. Значение пишем явно - Hub Settings показывает то, что в
        // UserDefaults, а не наш умолчательный.
        keepInClipboard = d.object(forKey: "keepInClipboard") as? Bool ?? true
        if d.object(forKey: "keepInClipboard") == nil { d.set(true, forKey: "keepInClipboard") }
        pillPosition = PillPosition(rawValue: d.string(forKey: "pillPosition") ?? "") ?? .bottom
        pillLiveText = d.object(forKey: "pillLiveText") as? Bool ?? true
        pillShowDot = d.object(forKey: "pillShowDot") as? Bool ?? true
        pillShowTimer = d.object(forKey: "pillShowTimer") as? Bool ?? true
        pillShowWave = d.object(forKey: "pillShowWave") as? Bool ?? true
        pillShowStatus = d.object(forKey: "pillShowStatus") as? Bool ?? true
        pillTextWidth = PillTextWidth(rawValue: d.string(forKey: "pillTextWidth") ?? "") ?? .medium
        pillSize = PillSize(rawValue: d.string(forKey: "pillSize") ?? "") ?? .regular
        historyDays = Self.days(d.object(forKey: "historyDays")) ?? 0
        cleanupLevel = CleanupLevel(rawValue: d.string(forKey: "cleanupLevel") ?? "") ?? .fillers
        removeRepeats = d.object(forKey: "removeRepeats") as? Bool ?? true
        capitalize = d.object(forKey: "capitalize") as? Bool ?? true
        trailingPeriod = d.object(forKey: "trailingPeriod") as? Bool ?? true
        customFillers = d.string(forKey: "customFillers") ?? ""
        replacements = Replacement.load(d.object(forKey: "replacements")) ?? []
        whisperMode = d.bool(forKey: "whisperMode")
        vocabulary = d.stringArray(forKey: "vocabulary") ?? []
        corrections = Self.load([Vocabulary.Correction].self, "learnedCorrections") ?? []
        learnFromEdits = d.object(forKey: "learnFromEdits") as? Bool ?? true
        if let saved = Self.load([AppStyleRule].self, "appStyles") {
            appStyles = saved
        } else {
            // Первый запуск: стили для того, что установлено.
            appStyles = AppStyleRule.suggestions.filter {
                NSWorkspace.shared.urlForApplication(withBundleIdentifier: $0.bundleID) != nil
            }
        }
        // Прошлые версии хранили срок числом, а замены - JSON-ом: переводим в вид, который понимает хаб.
        if d.object(forKey: "historyDays") is NSNumber { d.set(String(historyDays), forKey: "historyDays") }
        if d.object(forKey: "replacements") is Data { d.set(Replacement.pairs(replacements), forKey: "replacements") }
        loadHistory(d)
        refreshPermissions()
        refreshDevices()
    }

    /// Первая проверка прав - при запуске: из неё окно вперёд не выводим.
    private var permissionsChecked = false

    func refreshPermissions() {
        let mic = Recorder.permission == .authorized
        let ax = Inserter.trusted
        let wasChecked = permissionsChecked
        permissionsChecked = true
        if mic != micGranted { micGranted = mic }
        if ax != axTrusted {
            axTrusted = ax
            // Только что выдали в настройках - возвращаем человека в окно:
            // видно галочку, и не надо искать, сработало ли.
            if ax && wasChecked {
                Log.write("универсальный доступ: выдан")
                NSApp.activate(ignoringOtherApps: true)
            }
        }
    }

    func refreshDevices() {
        let list = AudioDevices.inputs()
        if list != micDevices { micDevices = list }
    }

    /// Имя микрофона, который будет писать: выбранный, иначе системный.
    var micName: String {
        if let uid = micUID, let d = micDevices.first(where: { $0.uid == uid }) { return d.name }
        return AudioDevices.defaultInput()?.name ?? "Системный микрофон"
    }

    /// Срок хранения истории: строкой из Hub Settings или числом из прошлых версий.
    static func days(_ raw: Any?) -> Int? {
        (raw as? String).flatMap { Int($0) } ?? (raw as? Int)
    }

    // MARK: - состояние одной строкой

    var isRecording: Bool {
        if case .recording = phase { return true }
        return false
    }

    var isBusy: Bool {
        switch phase {
        case .recording, .processing: return true
        default: return false
        }
    }

    /// Можно начать диктовку: есть микрофон, модели готовы, прошлая разобрана.
    var canDictate: Bool {
        micGranted && backend == .ready && phase != .processing
    }

    /// Подзаголовок окна и первая строка меню в строке меню.
    var statusText: String {
        switch phase {
        case .recording: return "Идёт запись"
        case .processing: return "Распознавание…"
        default: break
        }
        if !micGranted { return "Нет доступа к микрофону" }
        switch backend {
        case .starting: return "Загрузка моделей…"
        case .failed: return "Распознавание не запустилось"
        case .ready: return "Готово к диктовке"
        }
    }

    // MARK: - история

    /// Старше срока хранения - прочь вместе со звуком.
    func pruneHistory() {
        guard historyDays > 0, historyLoaded else { return }
        let since = Calendar.current.date(byAdding: .day, value: -historyDays, to: Date())!
        let old = history.filter { $0.date < since }
        guard !old.isEmpty else { return }
        for e in old { AudioStore.delete(e.audio) }
        history.removeAll { $0.date < since }
        saveHistory()
    }

    /// Сколько лишних слов убрала чистка за всё время.
    var removedWords: Int {
        history.reduce(0) { sum, e in
            guard let raw = e.raw else { return sum }
            return sum + max(0, Entry.count(raw) - e.words)
        }
    }

    /// Сколько последних диктовок хранят звук. Текст хранится весь и всегда:
    /// история и статистика «за всё время» - по всем диктовкам. Звук тяжёлый,
    /// у старых записей он уходит, а текст остаётся.
    static let audioKept = 500

    func add(_ entry: Entry) {
        history.insert(entry, at: 0)
        var withAudio = 0
        for i in history.indices where history[i].audio != nil {
            withAudio += 1
            if withAudio > Self.audioKept {
                AudioStore.delete(history[i].audio)
                history[i].audio = nil
            }
        }
        saveHistory()
    }

    func update(_ entry: Entry) {
        guard let i = history.firstIndex(where: { $0.id == entry.id }) else { return }
        history[i] = entry
        saveHistory()
    }

    func entries(_ ids: Set<UUID>) -> [Entry] {
        ids.isEmpty ? [] : history.filter { ids.contains($0.id) }
    }

    /// Удалить с «Отменить» в меню «Правка». Звук удалённых остаётся на
    /// диске до следующего запуска (AudioStore.purge) - иначе отмена вернула
    /// бы текст без записи.
    func delete(_ ids: Set<UUID>, undo: UndoManager?, action: String? = nil) {
        let removed = history.filter { ids.contains($0.id) }
        guard !removed.isEmpty else { return }
        history.removeAll { ids.contains($0.id) }
        historySelection.subtract(ids)
        saveHistory()
        let name = action ?? (removed.count == 1 ? "удаление диктовки" : "удаление диктовок")
        undo?.registerUndo(withTarget: self) { state in state.restore(removed, undo: undo, action: name) }
        undo?.setActionName(name)
    }

    func restore(_ entries: [Entry], undo: UndoManager?, action: String) {
        history = (history + entries).sorted { $0.date > $1.date }
        saveHistory()
        undo?.registerUndo(withTarget: self) { state in
            state.delete(Set(entries.map(\.id)), undo: undo, action: action)
        }
        undo?.setActionName(action)
    }

    func clearHistory(undo: UndoManager?) {
        delete(Set(history.map(\.id)), undo: undo, action: "очистку истории")
    }

    /// История - в фоне: тысячи записей в JSON - заметная пауза главного потока
    /// ровно в момент вставки. Очередь последовательная - порядок сохранений
    /// не путается; массив копируется, данные не делятся между потоками.
    private static let saveQueue = DispatchQueue(label: "flowlocal.history", qos: .utility)

    private func saveHistory() {
        let snapshot = history
        Self.saveQueue.async {
            guard let data = try? JSONEncoder().encode(snapshot) else { return }
            try? FileManager.default.createDirectory(at: Paths.support, withIntermediateDirectories: true)
            try? data.write(to: Paths.history, options: .atomic)
        }
    }

    /// История - файлом в данных приложения. Раньше она жила в UserDefaults
    /// (и обрезалась до 500 записей): без лимита там ей тесно - весь plist
    /// читается в память при каждом запуске. Старую переносим один раз.
    private func loadHistory(_ d: UserDefaults) {
        let fm = FileManager.default
        if let data = try? Data(contentsOf: Paths.history) {
            if let saved = try? JSONDecoder().decode([Entry].self, from: data) {
                // Нераспознанные, в которых оказалась тишина, раньше оставались
                // в истории с пометкой - теперь их там нет.
                history = saved.filter { !($0.failed && $0.silent == true) }
            } else {
                // Битый файл откладываем в сторону, а не затираем новыми
                // диктовками; звук не чистим (historyLoaded) - разберёмся руками.
                historyLoaded = false
                let aside = Paths.support.appendingPathComponent("history-broken-\(Int(Date().timeIntervalSince1970)).json")
                try? fm.moveItem(at: Paths.history, to: aside)
                Log.write("история не прочиталась, отложена в \(aside.lastPathComponent)")
            }
            return
        }
        guard let data = d.data(forKey: "history") else { return }
        guard let saved = try? JSONDecoder().decode([Entry].self, from: data) else {
            historyLoaded = false
            return
        }
        history = saved
        do {
            try fm.createDirectory(at: Paths.support, withIntermediateDirectories: true)
            try data.write(to: Paths.history, options: .atomic)
            d.removeObject(forKey: "history")
        } catch {
            Log.write("история не перенеслась в файл: \(error.localizedDescription)")
        }
    }

    /// Дождаться начатых сохранений - перед выходом.
    static func flushHistory() {
        saveQueue.sync {}
    }

    // MARK: - статистика из истории

    /// Скорость печати, с которой сравниваем голос: средняя по клавиатуре -
    /// около 40 слов в минуту.
    static let typingWPM = 40.0

    var wordsToday: Int {
        let cal = Calendar.current
        return history.filter { cal.isDateInToday($0.date) }.reduce(0) { $0 + $1.words }
    }

    var wordsWeek: Int {
        let since = Calendar.current.date(byAdding: .day, value: -6, to: Calendar.current.startOfDay(for: Date()))!
        return history.filter { $0.date >= since }.reduce(0) { $0 + $1.words }
    }

    var dictationsToday: Int {
        history.filter { Calendar.current.isDateInToday($0.date) }.count
    }

    /// Слов в минуту речи - по всем распознанным диктовкам.
    var speedWPM: Int {
        let ok = history.filter { !$0.failed }
        let words = ok.reduce(0) { $0 + $1.words }
        let minutes = ok.reduce(0) { $0 + $1.seconds } / 60
        return minutes > 0.05 ? Int((Double(words) / minutes).rounded()) : 0
    }

    /// Минут сэкономлено против печати: сколько бы печатали минус сколько говорили.
    var savedMinutes: Int {
        let saved = history.reduce(0.0) { $0 + max(0, Double($1.words) / Self.typingWPM - $1.seconds / 60) }
        return Int(saved.rounded())
    }

    var voiceRatio: Double {
        Double(speedWPM) / Self.typingWPM
    }

    /// Диктовки за последние `days` дней, считая сегодня.
    func recent(days: Int) -> [Entry] {
        let cal = Calendar.current
        let since = cal.date(byAdding: .day, value: -(days - 1), to: cal.startOfDay(for: Date()))!
        return history.filter { $0.date >= since }
    }

    /// Минут сэкономлено за последние `days` дней - так же, как за всё время.
    func savedMinutes(days: Int) -> Int {
        let saved = recent(days: days)
            .reduce(0.0) { $0 + max(0, Double($1.words) / Self.typingWPM - $1.seconds / 60) }
        return Int(saved.rounded())
    }

    /// Слова за последние 7 дней, сегодня - последний.
    var lastDays: [DayWords] { lastDays(7) }

    /// Слова по дням за последние `count` дней, сегодня - последний.
    func lastDays(_ count: Int) -> [DayWords] {
        let cal = Calendar.current
        let today = cal.startOfDay(for: Date())
        var byDay: [Date: Int] = [:]
        for entry in recent(days: count) {
            byDay[cal.startOfDay(for: entry.date), default: 0] += entry.words
        }
        return (0..<count).reversed().map { back in
            let day = cal.date(byAdding: .day, value: -back, to: today)!
            return DayWords(date: day, words: byDay[day] ?? 0)
        }
    }
}
