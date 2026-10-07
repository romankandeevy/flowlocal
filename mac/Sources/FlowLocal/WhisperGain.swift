import Foundation

// Режим шёпота: тихую речь поднимаем до обычной громкости до того, как она
// уйдёт на разбор. Срез низа (ниже ~100 Гц) - чтобы не раздувать гул стола
// и вентилятора; автоусиление по огибающей - до 12×, в паузах усиление не
// растёт (иначе в тишине вылез бы шум); мягкий ограничитель сверху -
// громкое слово не хрипит. Звук в истории сохраняется уже усиленным, и
// перераспознавание слышит то же самое.

struct WhisperGain {
    static let maxGain: Float = 12
    /// Куда тянем громкость речи (RMS).
    static let target: Float = 0.08
    /// Тише этого - пауза: усиление не поднимаем.
    static let floor: Float = 0.0025
    static let block = 160 // 10 мс при 16 кГц

    private(set) var gain: Float = 4
    private var env: Float = 0
    private var hpIn: Float = 0
    private var hpOut: Float = 0
    private var acc: Float = 0
    private var n = 0

    mutating func process(_ samples: inout [Float]) {
        for i in samples.indices {
            // Срез низа: однополюсный фильтр верхних частот.
            let hp = 0.961 * (hpOut + samples[i] - hpIn)
            hpIn = samples[i]
            hpOut = hp
            acc += hp * hp
            n += 1
            if n == Self.block {
                update(rms: sqrt(acc / Float(n)))
                acc = 0
                n = 0
            }
            samples[i] = Self.limit(hp * gain)
        }
    }

    private mutating func update(rms: Float) {
        // Огибающая: быстро вверх, медленно вниз.
        env = rms > env ? env * 0.5 + rms * 0.5 : env * 0.97 + rms * 0.03
        var desired = min(Self.maxGain, max(1, Self.target / max(env, 1e-5)))
        if env < Self.floor { desired = min(desired, gain) }
        // Громче нужного - сбрасываем сразу, тише - подтягиваем плавно.
        gain = desired < gain ? gain * 0.6 + desired * 0.4 : gain + (desired - gain) * 0.04
    }

    /// Выше 0.8 - мягкое насыщение вместо среза.
    static func limit(_ x: Float) -> Float {
        let a = abs(x)
        guard a > 0.8 else { return x }
        let y = 0.8 + 0.2 * tanh((a - 0.8) / 0.2)
        return x < 0 ? -y : y
    }
}
