import AppKit

// Музыка и видео на паузу, пока идёт диктовка: Яндекс Музыка, Музыка,
// Spotify, YouTube и сериалы в браузере - всё, что слушается клавиши ⏯.
//
// С macOS 15.4 MediaRemote не отвечает сторонним приложениям: «играет ли»
// - всегда «нет», а команды паузы молча игнорируются. Поэтому:
//   - играет ли - спрашиваем через osascript: он системный, и ему отвечают;
//   - пауза и продолжение - системной клавишей ⏯, как с клавиатуры
//     (нужен «Универсальный доступ», он у приложения есть для вставки).
// ⏯ - переключатель, поэтому жмём его, только когда точно играло, и
// возвращаем, только если после записи по-прежнему тихо.
enum MediaPause {
    /// Мы ли поставили на паузу - только тогда возобновляем.
    private static var paused = false
    /// Номер записи: ответ osascript, пришедший после её конца, уже не нужен.
    private static var generation = 0
    private static let queue = DispatchQueue(label: "flowlocal.media", qos: .userInitiated)

    private static let script = """
    ObjC.import('Foundation');
    $.NSBundle.bundleWithPath('/System/Library/PrivateFrameworks/MediaRemote.framework/').load;
    const R = $.NSClassFromString('MRNowPlayingRequest');
    R.isNil() ? 'unknown' : (R.localIsPlaying ? 'playing' : 'idle')
    """

    /// Начало записи. Главный поток.
    static func begin() {
        generation += 1
        let g = generation
        queue.async {
            let playing = isPlaying()
            DispatchQueue.main.async {
                guard playing == true, g == generation, !paused else { return }
                paused = true
                postPlayPause()
                Log.write("медиа на паузе на время диктовки")
            }
        }
    }

    /// Запись кончилась (текст вставлен или отменено). Главный поток.
    static func end() {
        generation += 1
        guard paused else { return }
        paused = false
        queue.async {
            // Человек мог сам включить что-то за время записи - тогда ⏯
            // поставил бы это на паузу.
            guard isPlaying() == false else { return }
            // ⌘V должен уйти в окно раньше, чем проснётся звук.
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { postPlayPause() }
        }
    }

    /// nil - узнать не вышло.
    private static func isPlaying() -> Bool? {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
        p.arguments = ["-l", "JavaScript", "-e", script]
        let out = Pipe()
        p.standardOutput = out
        p.standardError = FileHandle.nullDevice
        do { try p.run() } catch { return nil }
        p.waitUntilExit()
        let s = String(decoding: out.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        switch s {
        case "playing": return true
        case "idle": return false
        default: return nil
        }
    }

    /// Клавиша ⏯ (NX_KEYTYPE_PLAY = 16): нажатие и отпускание.
    private static func postPlayPause() {
        for down in [true, false] {
            let flags: Int = down ? 0xA00 : 0xB00
            let event = NSEvent.otherEvent(with: .systemDefined, location: .zero,
                                           modifierFlags: NSEvent.ModifierFlags(rawValue: UInt(flags)),
                                           timestamp: 0, windowNumber: 0, context: nil, subtype: 8,
                                           data1: (16 << 16) | (down ? 0xA00 : 0xB00), data2: -1)
            event?.cgEvent?.post(tap: .cghidEventTap)
        }
    }
}
