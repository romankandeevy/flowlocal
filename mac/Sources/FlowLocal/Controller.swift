import AppKit
import Carbon.HIToolbox

// Диктовка целиком: хоткеи -> микрофон -> бэкенд -> вставка -> окно и плашка.
//
// Два сочетания, как в old/ (hotkey_hold / hotkey_toggle):
//   «Зажать» - пишем, пока держат; отпустили - текст на месте;
//   «Нажать» - нажали - говорим, нажали ещё раз - текст на месте.
// Esc во время записи - отмена.
//
// Звук уходит в бэкенд порциями прямо во время речи и разбирается по паузам
// (server.py); после отпускания остаётся только хвост. Уже разобранное
// приходит событиями partial - это живая расшифровка в окне.
final class Controller {
    let state: AppState
    let backend = Backend()
    private let recorder = Recorder()
    private let player = Player()
    private lazy var pill = PillPanel(state: state)

    // Номер текущей диктовки. Ответ с чужим номером - устаревший: пришёл,
    // когда человек уже начал новую запись или отменил эту.
    private var session = 0
    private var pressedAt: Date?
    private var hideWork: DispatchWorkItem?
    private var tick: Timer?
    private var releasedTicks = 0
    private var restarts = 0
    private var lastBackendError: String?
    private var trustPromptShown = false
    // Запись, которую не успели распознать: бэкенд упал посреди работы. Не
    // выбрасываем - распознаем, когда он поднимется.
    private var orphan: (samples: [Float], entry: Entry)?
    // Последнее окончательное из разбора на ходу и оно же почищенное.
    private var liveFinal = (raw: "", clean: "")

    private let holdID: UInt32 = 1
    private let escapeID: UInt32 = 2
    private let toggleID: UInt32 = 3
    private let minRecordSec = 0.3      // old/config.example.json: min_record_sec
    // Предел длины записи. Было 5 минут - и живая диктовка на 780 слов
    // оборвалась ровно на нём. Разбор на ходу держит ожидание в секунде при
    // любой длине, память - 64 КБ на секунду в каждом процессе.
    private let maxRecordSec = 1800.0

    init(state: AppState) {
        self.state = state
    }

    func start() {
        recorder.onLevel = { rms in
            DispatchQueue.main.async { LevelStore.shared.push(rms: rms) }
        }
        recorder.onFailure = { [weak self] error in
            Log.write("микрофон пропал посреди записи: \(error.localizedDescription)")
            self?.finish()
        }
        player.onEnd = { [weak self] in self?.state.playing = nil }
        backend.onEvent = { [weak self] in self?.handle($0) }
        backend.start()
        bindHotkeys()
    }

    /// Сочетания задаются в Hub Settings. Занятое, системное или совпадающее с другим сочетание не
    /// регистрируется - причина пишется в журнал.
    func bindHotkeys() {
        HotkeyCenter.shared.unregister(id: holdID)
        HotkeyCenter.shared.unregister(id: toggleID)
        let hold = state.hotkey
        if usable(hold, .hold),
           !HotkeyCenter.shared.register(id: holdID, keyCode: hold.keyCode, modifiers: hold.modifiers,
                                         pressed: { [weak self] in self?.holdPressed() },
                                         released: { [weak self] in self?.holdReleased() }) {
            Log.write("сочетание «\(HotkeyRole.hold.title)» \(hold.label) занято другим приложением")
        }
        let toggle = state.toggleHotkey
        if hold.isEnabled, toggle.same(as: hold) {
            Log.write("сочетание «\(HotkeyRole.toggle.title)» совпадает с «\(HotkeyRole.hold.title)» - не регистрирую")
        } else if usable(toggle, .toggle),
                  !HotkeyCenter.shared.register(id: toggleID, keyCode: toggle.keyCode, modifiers: toggle.modifiers,
                                                pressed: { [weak self] in self?.togglePressed() }) {
            Log.write("сочетание «\(HotkeyRole.toggle.title)» \(toggle.label) занято другим приложением")
        }
    }

    private func usable(_ preset: HotkeyPreset, _ role: HotkeyRole) -> Bool {
        guard preset.isEnabled else { return false }
        if HotkeyPreset.isSystemCombo(keyCode: Int(preset.keyCode), mods: preset.modifiers) {
            Log.write("сочетание «\(role.title)» \(preset.label) - системное, его перехват сломал бы macOS")
            return false
        }
        return true
    }

    // MARK: - бэкенд

    private func handle(_ event: Backend.Event) {
        switch event {
        case let .ready(model):
            if model == "ru" {
                state.backend = .ready
                recoverOrphan()
            } else {
                state.englishReady = true
            }
        case let .failed(msg):
            Log.write("распознавание: \(msg)")
            lastBackendError = msg
            if state.backend != .ready { state.backend = .failed(msg) }
        case let .exited(code):
            Log.write("распознавание завершилось с кодом \(code)")
            state.englishReady = false
            guard restarts < 3 else {
                state.backend = .failed(lastBackendError
                    ?? "Распознавание падает при запуске. Журнал: ~/Library/Logs/FlowLocal.log")
                return
            }
            restarts += 1
            state.backend = .starting
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { [weak self] in self?.backend.start() }
        case let .partial(id, text, interim, words):
            guard id == session else { return }
            switch state.phase {
            case .recording, .processing:
                // Окончательное только дописывается, черновик хвоста
                // перерисовывается целиком - так слова видны сразу.
                LiveWords.shared.setCount(words)
                pushLive(final: text, interim: interim)
            default:
                break
            }
        }
    }

    // MARK: - хоткеи

    private func holdPressed() {
        switch state.phase {
        case .recording(_, true): finish()
        // Автоповтор зажатой клавиши. И пока идёт распознавание, новое нажатие
        // запись не начинает: иначе ответ прошлой диктовки перебил бы новую.
        case .recording, .processing: break
        default: begin(locked: false)
        }
    }

    private func holdReleased() {
        guard case .recording(_, false) = state.phase else { return }
        finish()
    }

    private func togglePressed() {
        switch state.phase {
        case .recording: finish()
        case .processing: break
        default: begin(locked: true)
        }
    }

    // MARK: - запись

    private func begin(locked: Bool) {
        guard Recorder.permission == .authorized else {
            Recorder.requestPermission { [weak self] ok in
                self?.state.refreshPermissions()
                if !ok { self?.flash(.failed("Нет доступа к микрофону")) }
            }
            return
        }
        switch state.backend {
        case .starting:
            flash(.loading, hideAfter: 1.5)
            return
        case .failed:
            flash(.failed("Распознавание не запустилось"), hideAfter: 3)
            return
        case .ready:
            break
        }
        hideWork?.cancel()
        // Сначала - что запись идёт: капсула показывается сразу по нажатию,
        // а не после того, как поднимется микрофон (на Bluetooth это заметно).
        session = backend.newID()
        let id = session
        pressedAt = Date()
        releasedTicks = 0
        liveFinal = ("", "")
        LiveWords.shared.reset()
        LevelStore.shared.reset()
        state.phase = .recording(since: Date(), locked: locked)
        if state.showPill { pill.present() }
        HotkeyCenter.shared.register(id: escapeID, keyCode: UInt32(kVK_Escape), modifiers: 0,
                                     pressed: { [weak self] in self?.cancel() })
        // Микрофон - следующим оборотом цикла, чтобы капсула успела
        // нарисоваться. Отпустили или отменили раньше - открывать уже нечего.
        DispatchQueue.main.async { [weak self] in
            guard let self, id == self.session, case .recording = self.state.phase else { return }
            self.openMicrophone(id)
        }
        // .common, а не .default: в режиме по умолчанию таймер стоит, пока
        // открыто любое меню, и звук перестал бы уходить на разбор.
        let t = Timer(timeInterval: 0.25, repeats: true) { [weak self] _ in self?.onTick() }
        t.tolerance = 0.03
        RunLoop.main.add(t, forMode: .common)
        tick = t
    }

    private func openMicrophone(_ id: Int) {
        recorder.deviceUID = state.micUID
        let t0 = Date()
        do {
            try recorder.start()
        } catch {
            HotkeyCenter.shared.unregister(id: escapeID)
            tick?.invalidate()
            tick = nil
            state.phase = .idle
            pill.dismiss()
            flash(.failed("Не удалось открыть микрофон"))
            Log.write("микрофон не открылся: \(error.localizedDescription)")
            return
        }
        let ms = Int(Date().timeIntervalSince(t0) * 1000)
        if ms > 150 { Log.write("микрофон открывался \(ms) мс") }
        if state.sounds { Sounds.start?.play() }
        backend.begin(id, lang: state.langMode.rawValue)
    }

    private func onTick() {
        guard case let .recording(since, locked) = state.phase else { return }
        backend.audio(session, recorder.drain())
        if Date().timeIntervalSince(since) > maxRecordSec {
            Log.write("запись упёрлась в предел \(Int(maxRecordSec)) с")
            finish()
            return
        }
        // Отпускание «Зажать» может потеряться (сменился фокус, защищённый
        // ввод пароля) - тогда запись шла бы вечно. Страховка: модификаторы
        // сочетания отпущены два тика подряд - значит, отпустили.
        guard !locked, let t = pressedAt, Date().timeIntervalSince(t) > 0.35 else { return }
        let need = requiredFlags(state.hotkey)
        if CGEventSource.flagsState(.combinedSessionState).intersection(need) != need {
            releasedTicks += 1
            if releasedTicks >= 2 {
                Log.write("отпускание хоткея потерялось - завершаю по модификаторам")
                finish()
            }
        } else {
            releasedTicks = 0
        }
    }

    private func requiredFlags(_ hk: HotkeyPreset) -> CGEventFlags {
        var f: CGEventFlags = []
        if hk.modifiers & UInt32(controlKey) != 0 { f.insert(.maskControl) }
        if hk.modifiers & UInt32(shiftKey) != 0 { f.insert(.maskShift) }
        if hk.modifiers & UInt32(optionKey) != 0 { f.insert(.maskAlternate) }
        if hk.modifiers & UInt32(cmdKey) != 0 { f.insert(.maskCommand) }
        return f
    }

    private func stopRecording() -> (all: [Float], rest: [Float]) {
        HotkeyCenter.shared.unregister(id: escapeID)
        tick?.invalidate()
        tick = nil
        return recorder.stop()
    }

    private func cancel() {
        guard case .recording = state.phase else { return }
        _ = stopRecording()
        backend.cancel(session)
        state.phase = .idle
        LiveWords.shared.reset()
        pill.dismiss()
    }

    /// «Отменить» на экране распознавания: ответ, если придёт, уже чужой.
    func cancelProcessing() {
        guard case .processing = state.phase else { return }
        backend.cancel(session)
        session = backend.newID()
        state.phase = .idle
        LiveWords.shared.reset()
        pill.dismiss()
        Log.write("распознавание отменено")
    }

    /// «Начать / Закончить диктовку» из меню - как сочетание «По нажатию».
    func toggleDictation() {
        togglePressed()
    }

    /// «Отменить» в окне и в меню: и запись, и распознавание.
    func cancelDictation() {
        switch state.phase {
        case .recording: cancel()
        case .processing: cancelProcessing()
        default: break
        }
    }

    private func finish() {
        guard case .recording = state.phase else { return }
        let (all, rest) = stopRecording()
        if state.sounds { Sounds.stop?.play() }
        let id = session
        backend.audio(id, rest)
        let seconds = Double(all.count) / Recorder.sampleRate
        guard seconds >= minRecordSec else {
            backend.cancel(id)
            Log.write(String(format: "запись короче %.1fс - отпустили сразу, без разбора", minRecordSec))
            state.phase = .idle
            pill.dismiss()
            flash(.failed("Слишком короткая запись"), hideAfter: 1.5)
            return
        }
        state.recordSeconds = seconds
        state.phase = .processing
        // Запись - на диск в фоне, чтобы окно не ждало: получаса звука - 57 МБ.
        let entryID = UUID()
        let audio = state.saveAudio ? "\(entryID.uuidString).wav" : nil
        if state.saveAudio {
            DispatchQueue.global(qos: .utility).async { _ = AudioStore.save(all, id: entryID) }
        }
        let draft = Entry(id: entryID, text: "", lang: state.langMode.rawValue, seconds: seconds, audio: audio)
        backend.finish(id, timeout: 15 + seconds * 0.3) { [weak self] result in
            guard let self, id == self.session else { return }
            switch result {
            case let .success(r):
                self.deliver(r, draft: draft)
            case let .failure(error):
                Log.write("разбор на ходу не удался: \(error.localizedDescription) - распознаю целиком")
                self.fallback(all, draft: draft)
            }
        }
    }

    private func fallback(_ audio: [Float], draft: Entry) {
        let id = backend.newID()
        session = id
        backend.transcribe(id, audio, lang: state.langMode.rawValue, timeout: 20 + draft.seconds * 0.5) { [weak self] result in
            guard let self, id == self.session else { return }
            switch result {
            case let .success(r):
                self.deliver(r, draft: draft)
            case let .failure(error):
                Log.write("распознавание не удалось: \(error.localizedDescription) - запись сохранена до перезапуска")
                self.orphan = (audio, draft)
                self.flash(.failed("Распознавание перезапускается"), hideAfter: 3)
            }
        }
    }

    private func recoverOrphan() {
        guard let (audio, draft) = orphan else { return }
        // Не трогаем буфер и историю посреди активной диктовки:
        // рестарт бэкенда мог совпасть с новой записью.
        guard case .idle = state.phase else { return }
        orphan = nil
        backend.transcribe(backend.newID(), audio, lang: state.langMode.rawValue,
                           timeout: 30 + draft.seconds) { [weak self] result in
            guard let self else { return }
            var entry = draft
            if case let .success(r) = result {
                self.apply(r.text, to: &entry)
                entry.lang = r.lang
            }
            entry.words = Entry.count(entry.text)
            entry.failed = entry.text.isEmpty
            self.state.add(entry)
            // Вставлять не будем: фокус за это время мог уйти куда угодно.
            guard !entry.failed else { return }
            NSPasteboard.general.clearContents()
            NSPasteboard.general.setString(entry.text, forType: .string)
            self.flash(.copied("Диктовка восстановлена. Нажмите ⌘V"), hideAfter: 3)
        }
    }

    private func deliver(_ r: Backend.Result, draft: Entry) {
        // Счётчик перезапусков - после настоящей работы, а не на «модель
        // загружена»: процесс, падающий позже загрузки, иначе крутился бы вечно.
        restarts = 0
        // Подписи по единицам, урок из TREE.md: «звук/на_ходу/хвост» - секунды
        // записи, «ожидание» - секунды работы после отпускания. Не путать.
        Log.write(String(format: "диктовка: звук=%.1fс на_ходу=%.1fс хвост=%.1fс заранее=%@ | ожидание=%.2fс язык=%@",
                         draft.seconds, r.streamedSec, r.tailSec, r.specHit ? "да" : "нет", r.wait, r.lang))
        var entry = draft
        apply(r.text, to: &entry)
        entry.lang = r.lang
        let text = entry.text
        LiveWords.shared.update(final: text, interim: "")
        if let raw = entry.raw {
            Log.write("чистка: \(Entry.count(raw)) → \(entry.words) слов")
        }
        guard !text.isEmpty else {
            // Не расслышали - запись всё равно в истории: её можно перераспознать.
            if entry.audio != nil { state.add(entry) }
            flash(.failed(entry.audio != nil ? "Речь не распознана. Запись в истории" : "Речь не распознана"))
            return
        }
        state.add(entry)
        guard state.insertAutomatically else {
            flash(.done("\(wordsLabel(entry.words)) в истории"), hideAfter: 1.5)
            return
        }
        insert(text, words: wordsLabel(entry.words))
    }

    /// «Вставить» из истории: прячем окно - фокус возвращается туда, где
    /// человек был, - и вставляем туда.
    func paste(_ entry: Entry) {
        NSApp.hide(nil)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { [weak self] in
            self?.insert(entry.text, words: wordsLabel(entry.words))
        }
    }

    /// Перераспознать сохранённую запись - текущим языком из настроек.
    func rerecognize(_ entry: Entry) {
        guard let name = entry.audio, !state.rerecognizing.contains(entry.id) else { return }
        state.rerecognizing.insert(entry.id)
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let samples = AudioStore.load(name)
            DispatchQueue.main.async {
                guard let self else { return }
                guard let samples, !samples.isEmpty else {
                    self.state.rerecognizing.remove(entry.id)
                    Log.write("перераспознать: нет файла \(name)")
                    return
                }
                self.backend.transcribe(self.backend.newID(), samples, lang: self.state.langMode.rawValue,
                                        timeout: 30 + entry.seconds) { result in
                    self.state.rerecognizing.remove(entry.id)
                    guard case let .success(r) = result else { return }
                    var e = entry
                    self.apply(r.text, to: &e)
                    e.lang = r.lang
                    self.state.update(e)
                    Log.write("перераспознано: \(e.words) слов, \(r.lang)")
                }
            }
        }
    }

    /// Живая расшифровка по словам - уже почищенная. Точку в конце не
    /// дописываем: фраза ещё идёт.
    private func pushLive(final: String, interim: String) {
        var o = state.cleanup
        o.trailingPeriod = false
        // Окончательное меняется раз в несколько секунд, черновик - несколько
        // раз в секунду. Чистить весь растущий текст на каждый черновик -
        // лишняя работа главного потока на длинной диктовке.
        let f: String
        if final == liveFinal.raw {
            f = liveFinal.clean
        } else {
            f = final.isEmpty ? "" : TextCleaner.clean(final, o)
            liveFinal = (final, f)
        }
        var t = o
        let ended = f.isEmpty || f.hasSuffix(".") || f.hasSuffix("?") || f.hasSuffix("!")
        t.capitalize = o.capitalize && ended
        let i = interim.isEmpty ? "" : TextCleaner.clean(interim, t)
        LiveWords.shared.update(final: f, interim: i)
    }

    /// Распознанный текст - в диктовку: чистка по настройкам, исходный
    /// сохраняется, только если чистка что-то поменяла.
    private func apply(_ recognized: String, to entry: inout Entry) {
        let raw = recognized.trimmingCharacters(in: .whitespacesAndNewlines)
        let clean = state.cleaned(raw)
        entry.text = clean
        entry.raw = clean == raw ? nil : raw
        entry.words = Entry.count(clean)
        entry.failed = clean.isEmpty
    }

    func play(_ entry: Entry) {
        if state.playing == entry.id {
            player.stop()
            state.playing = nil
            return
        }
        guard let name = entry.audio, AudioStore.exists(name) else { return }
        state.playing = player.play(AudioStore.url(name)) ? entry.id : nil
    }

    private func insert(_ text: String, words: String) {
        // Пробел в конце - old/ append_space: следующая диктовка не прилипнет.
        Inserter.insert(state.addSpace ? text + " " : text, keep: state.keepInClipboard) { outcome in
            Log.write(outcome == .pasted ? "вставка: ⌘V" : "вставка: в буфер - нет права «Универсальный доступ»")
            self.state.refreshPermissions()
            switch outcome {
            case .pasted:
                self.flash(.done("\(words) вставлено"), hideAfter: 1.2)
            case .copied where !self.trustPromptShown:
                // Системный запрос при запуске легко закрыть не глядя. Здесь
                // человек как раз ждал вставку - самое время показать, где
                // включить. Один раз за сеанс.
                self.trustPromptShown = true
                Inserter.requestTrust()
                Inserter.openAccessibilitySettings()
                self.flash(.copied("Включите «Универсальный доступ»"), hideAfter: 5)
            case .copied:
                self.flash(.copied("Текст скопирован. Нажмите ⌘V"), hideAfter: 2.5)
            }
        }
    }

    // MARK: - плашка

    private func flash(_ phase: Phase, hideAfter: Double = 2) {
        // Идёт запись - её плашка важнее любого сообщения.
        if case .recording = state.phase { return }
        hideWork?.cancel()
        state.phase = phase
        if state.showPill { pill.present() }
        let work = DispatchWorkItem { [weak self] in
            guard let self else { return }
            if case .recording = self.state.phase { return }
            self.state.phase = .idle
            self.pill.dismiss()
        }
        hideWork = work
        DispatchQueue.main.asyncAfter(deadline: .now() + hideAfter, execute: work)
    }
}

/// Звуки начала и конца записи: загружаются один раз, а не на каждой диктовке.
private enum Sounds {
    static let start = NSSound(named: "Tink")
    static let stop = NSSound(named: "Pop")
}

/// Прослушать запись из истории. NSSound хватает: WAV свой, короткий путь.
final class Player: NSObject, NSSoundDelegate {
    private var sound: NSSound?
    var onEnd: (() -> Void)?

    func play(_ url: URL) -> Bool {
        stop()
        guard let s = NSSound(contentsOf: url, byReference: true) else { return false }
        s.delegate = self
        sound = s
        return s.play()
    }

    func stop() {
        sound?.stop()
        sound = nil
    }

    func sound(_ sound: NSSound, didFinishPlaying flag: Bool) {
        self.sound = nil
        DispatchQueue.main.async { self.onEnd?() }
    }
}
