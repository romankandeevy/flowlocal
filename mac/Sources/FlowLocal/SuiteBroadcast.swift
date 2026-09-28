import Foundation

// Сообщает другим приложениям набора (острову в чёлке), что идёт диктовка.
// Уходит только состояние и громкость для волны - сам текст никуда не отправляется.
// Канал - системные распределённые уведомления "com.roman.suite.flow.dictation" (см. Apps/SuiteKit/SuiteBus).
enum SuiteBroadcast {
    private static let name = Notification.Name("com.roman.suite.flow.dictation")
    private static var lastLevel = Date.distantPast

    static func phase(_ phase: Phase) {
        post(["state": state(of: phase)])
    }

    /// Громкость 0...1 для волны на острове, не чаще 10 раз в секунду.
    static func level(_ value: Float) {
        let now = Date()
        guard now.timeIntervalSince(lastLevel) >= 0.1 else { return }
        lastLevel = now
        post(["state": "recording", "level": String(format: "%.2f", value)])
    }

    private static func state(of phase: Phase) -> String {
        switch phase {
        case .idle: return "idle"
        case .loading: return "loading"
        case .recording: return "recording"
        case .processing: return "processing"
        case .done, .copied: return "done"
        case .failed: return "failed"
        }
    }

    private static func post(_ info: [String: String]) {
        DistributedNotificationCenter.default().postNotificationName(name, object: nil, userInfo: info, deliverImmediately: true)
    }
}
