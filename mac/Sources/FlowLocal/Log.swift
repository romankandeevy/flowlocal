import Foundation

// Журнал ~/Library/Logs/FlowLocal.log. Пишет только безопасными API:
// seekToEndOfFile()/write(_:) бросают исключение Objective-C на ошибке ввода-
// вывода (полный диск) и роняют приложение, а seekToEnd()/write(contentsOf:)
// бросают обычную ошибку. Больше 2 МБ - уезжает в .1, как flow.log в old/.
enum Log {
    private static let dir = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Logs")
    private static let url = dir.appendingPathComponent("FlowLocal.log")
    static var fileURL: URL { url }
    private static let previous = dir.appendingPathComponent("FlowLocal.log.1")
    private static let queue = DispatchQueue(label: "flowlocal.log")
    private static let limit = 2_000_000
    private static let stamp: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return f
    }()

    static func write(_ msg: String) {
        queue.async {
            let data = Data("\(stamp.string(from: Date())) \(msg)\n".utf8)
            let fm = FileManager.default
            try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
            if let size = try? fm.attributesOfItem(atPath: url.path)[.size] as? Int, size > limit {
                try? fm.removeItem(at: previous)
                try? fm.moveItem(at: url, to: previous)
            }
            guard let h = try? FileHandle(forWritingTo: url) else {
                try? data.write(to: url)
                return
            }
            defer { try? h.close() }
            _ = try? h.seekToEnd()
            try? h.write(contentsOf: data)
        }
    }
}

/// Режет поток байт на строки. Кусок из трубы может оборваться посреди
/// кириллической буквы: декодировать можно только целую строку, иначе
/// String(data:encoding:) вернёт nil и выбросит весь кусок.
struct LineSplitter {
    private var buffer = Data()

    mutating func feed(_ data: Data) -> [Data] {
        buffer.append(data)
        var lines: [Data] = []
        while let nl = buffer.firstIndex(of: 0x0A) {
            lines.append(Data(buffer[buffer.startIndex..<nl]))
            buffer.removeSubrange(buffer.startIndex...nl)
        }
        return lines
    }

    mutating func reset() {
        buffer.removeAll()
    }
}
