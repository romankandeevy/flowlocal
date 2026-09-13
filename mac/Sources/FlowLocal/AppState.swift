import AppKit
import SwiftUI

enum Phase: Equatable {
    case idle
    case loading                              // хоткей нажат, а модель ещё грузится
    case recording(since: Date, locked: Bool) // locked - запись по «Нажать», до следующего нажатия
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

enum Tab: String, CaseIterable, Identifiable {
    case home, history, stats, settings

    var id: String { rawValue }
    var title: String {
        switch self {
        case .home: return "Главная"
        case .history: return "История"
        case .stats: return "Статистика"
        case .settings: return "Настройки"
        }
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
    var failed: Bool            // речь не распознана - можно перераспознать

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
    }
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

/// Разряды - неразрывным пробелом, как требует Verkstad: «1 284».
func grouped(_ n: Int) -> String {
    let f = NumberFormatter()
    f.numberStyle = .decimal
    f.groupingSeparator = "\u{00A0}"
    return f.string(from: NSNumber(value: n)) ?? "\(n)"
}

final class AppState: ObservableObject {
    @Published var theme: ThemeKind {
        didSet {
            UserDefaults.standard.set(theme.rawValue, forKey: "theme")
            NSApp.appearance = theme.appearance
        }
    }
    /// «Зажать»: пишем, пока держат.
    @Published var hotkey: HotkeyPreset {
        didSet { hotkey.save(.hold) }
    }
    /// «Нажать»: нажал - говоришь, нажал ещё раз - текст на месте.
    @Published var toggleHotkey: HotkeyPreset {
        didSet { toggleHotkey.save(.toggle) }
    }
    @Published var tab: Tab = .home
    @Published var backend: BackendState = .starting
    @Published var englishReady = false
    @Published var phase: Phase = .idle
    @Published var history: [Entry] = []
    @Published var micGranted = false
    @Published var axTrusted = false
    @Published var hotkeyError: [HotkeyRole: String] = [:]
    @Published var capturing: HotkeyRole?

    // Разбор на ходу: уже разобранный текст и слова - для окна и плашки.
    @Published var liveText = ""
    @Published var liveLatest = ""                // последний разобранный кусок - его подсвечиваем
    @Published var liveWords = 0
    @Published var recordSeconds: Double = 0
    @Published var transcriptExpanded = false

    // Что сейчас играет и что перераспознаётся - для кнопок в истории.
    @Published var playing: UUID?
    @Published var rerecognizing: Set<UUID> = []

    // Настройки.
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

    var palette: Palette { .of(theme) }

    init() {
        let d = UserDefaults.standard
        theme = ThemeKind(rawValue: d.string(forKey: "theme") ?? "") ?? .system
        hotkey = HotkeyPreset.load(.hold)
        toggleHotkey = HotkeyPreset.load(.toggle)
        insertAutomatically = d.object(forKey: "insertAutomatically") as? Bool ?? true
        showPill = d.object(forKey: "showPill") as? Bool ?? true
        saveAudio = d.object(forKey: "saveAudio") as? Bool ?? true
        sounds = d.object(forKey: "sounds") as? Bool ?? false
        langMode = LangMode(rawValue: d.string(forKey: "langMode") ?? "") ?? .auto
        micUID = d.string(forKey: "micUID")
        if let data = d.data(forKey: "history"),
           let saved = try? JSONDecoder().decode([Entry].self, from: data) {
            history = saved
        }
        refreshPermissions()
        refreshDevices()
    }

    func refreshPermissions() {
        let mic = Recorder.permission == .authorized
        let ax = Inserter.trusted
        if mic != micGranted { micGranted = mic }
        if ax != axTrusted { axTrusted = ax }
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

    func hotkey(for role: HotkeyRole) -> HotkeyPreset {
        role == .hold ? hotkey : toggleHotkey
    }

    func setHotkey(_ preset: HotkeyPreset, for role: HotkeyRole) {
        if role == .hold { hotkey = preset } else { toggleHotkey = preset }
    }

    // MARK: - история

    func add(_ entry: Entry) {
        history.insert(entry, at: 0)
        if history.count > 500 {
            for old in history[500...] { AudioStore.delete(old.audio) }
            history.removeLast(history.count - 500)
        }
        saveHistory()
    }

    func update(_ entry: Entry) {
        guard let i = history.firstIndex(where: { $0.id == entry.id }) else { return }
        history[i] = entry
        saveHistory()
    }

    func remove(_ entry: Entry) {
        AudioStore.delete(entry.audio)
        history.removeAll { $0.id == entry.id }
        saveHistory()
    }

    func clearHistory() {
        for e in history { AudioStore.delete(e.audio) }
        history.removeAll()
        UserDefaults.standard.removeObject(forKey: "history")
    }

    private func saveHistory() {
        if let data = try? JSONEncoder().encode(history) {
            UserDefaults.standard.set(data, forKey: "history")
        }
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

    /// Слова по дням за последние 7 дней, сегодня - последний.
    var lastDays: [(date: Date, words: Int)] {
        let cal = Calendar.current
        let today = cal.startOfDay(for: Date())
        return (0..<7).reversed().map { back in
            let day = cal.date(byAdding: .day, value: -back, to: today)!
            let words = history.filter { cal.isDate($0.date, inSameDayAs: day) }.reduce(0) { $0 + $1.words }
            return (day, words)
        }
    }
}
