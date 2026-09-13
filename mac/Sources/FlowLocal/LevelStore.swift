import SwiftUI

// Уровень микрофона - отдельно от AppState. Раньше он жил там, и каждый кусок
// звука (~23 раза в секунду) перерисовывал всё окно: историю, плитки,
// статистику по всей истории. На слабом Маке это и было «лагучее». Теперь
// его видят только столбики, и публикуем не чаще 20 раз в секунду.
final class LevelStore: ObservableObject {
    static let shared = LevelStore()
    static let count = 64       // волна на «Главной» - 64 столбика

    @Published private(set) var levels: [Float] = Array(repeating: 0, count: LevelStore.count)
    private var pending: [Float] = []
    private var lastPublish = Date.distantPast

    /// RMS -> 0...1. Диапазон уже прежнего (-50...-12 дБ) и с подъёмом тихих:
    /// обычная речь заполняет столбики, а не шевелит их у самого низа.
    func push(rms: Float) {
        let db = 20 * log10(max(rms, 1e-6))
        let v = min(1, max(0, (db + 50) / 38))
        pending.append(pow(v, 0.8))
        let now = Date()
        guard now.timeIntervalSince(lastPublish) >= 0.05 else { return }
        lastPublish = now
        levels = Array((levels + pending).suffix(Self.count))
        pending.removeAll(keepingCapacity: true)
    }

    func reset() {
        pending.removeAll()
        levels = Array(repeating: 0, count: Self.count)
    }

    /// Для снимков и проверки без микрофона.
    func set(_ values: [Float]) {
        levels = Array(values.suffix(Self.count))
    }

    var peak: Float { levels.suffix(8).max() ?? 0 }
}
