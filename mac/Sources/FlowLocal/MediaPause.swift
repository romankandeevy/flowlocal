import Foundation

// Музыка и видео на паузу, пока идёт диктовка: Музыка, Spotify, YouTube и
// сериалы в браузере - всё, что управляется клавишей ⏯. Через MediaRemote -
// тот же канал, что у клавиш на клавиатуре. Играло до записи - после неё
// продолжится; не играло - ничего не трогаем, иначе ⏯ запустил бы плеер сам.
enum MediaPause {
    private typealias SendCommand = @convention(c) (UInt32, CFDictionary?) -> Bool
    private typealias IsPlaying = @convention(c) (DispatchQueue, @escaping (Bool) -> Void) -> Void

    private static let handle = dlopen("/System/Library/PrivateFrameworks/MediaRemote.framework/MediaRemote", RTLD_LAZY)
    private static let send: SendCommand? = sym("MRMediaRemoteSendCommand")
    private static let isPlaying: IsPlaying? = sym("MRMediaRemoteGetNowPlayingApplicationIsPlaying")

    private static let play: UInt32 = 0
    private static let pause: UInt32 = 1

    /// Мы ли поставили на паузу - только тогда возобновляем.
    private static var paused = false
    /// Номер записи: пауза, ответ на которую пришёл после конца записи, не нужна.
    private static var generation = 0

    private static func sym<T>(_ name: String) -> T? {
        guard let handle, let p = dlsym(handle, name) else { return nil }
        return unsafeBitCast(p, to: T.self)
    }

    /// Начало записи. Главный поток.
    static func begin() {
        generation += 1
        let g = generation
        guard let isPlaying, let send else { return }
        isPlaying(.main) { playing in
            guard playing, g == generation, !paused else { return }
            if send(pause, nil) {
                paused = true
                Log.write("медиа на паузе на время диктовки")
            }
        }
    }

    /// Запись кончилась (текст вставлен или отменено). Главный поток.
    static func end() {
        generation += 1
        guard paused else { return }
        paused = false
        // Небольшая задержка: ⌘V должен уйти в окно раньше, чем проснётся звук.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            _ = send?(play, nil)
        }
    }
}
