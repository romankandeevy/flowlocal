import Foundation

// Все пути приложения - в одном месте и ни одного абсолютного. Сборка
// переносима: .app можно положить куда угодно, репозиторий - тоже.
//
//   FlowLocal.app/Contents/Resources/backend/   server.py и langdetect.py (кладёт build.sh)
//   ~/Library/Application Support/FlowLocal/
//       Python/        окружение бэкенда, своё на каждом Маке (заводит build.sh)
//       Models/        модели распознавания, докачиваются при первом старте
//       Recordings/    звук диктовок
//       history.json   история диктовок - весь текст, без лимита
//   ~/Library/Logs/FlowLocal.log
//
// FLOWLOCAL_BACKEND_DIR в окружении - взять server.py прямо из репозитория,
// чтобы правка бэкенда не требовала пересборки.
enum Paths {
    static let support: URL = {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        return base.appendingPathComponent("FlowLocal", isDirectory: true)
    }()

    static var python: URL { support.appendingPathComponent("Python/bin/python3") }
    static var models: URL { support.appendingPathComponent("Models", isDirectory: true) }
    static var recordings: URL { support.appendingPathComponent("Recordings", isDirectory: true) }
    static var history: URL { support.appendingPathComponent("history.json") }

    static var backend: URL? {
        if let dev = ProcessInfo.processInfo.environment["FLOWLOCAL_BACKEND_DIR"], !dev.isEmpty {
            return URL(fileURLWithPath: dev, isDirectory: true)
        }
        return Bundle.main.resourceURL?.appendingPathComponent("backend", isDirectory: true)
    }
}
