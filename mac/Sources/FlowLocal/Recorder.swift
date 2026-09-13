import AVFoundation

// Микрофон -> 16 кГц моно float32, как ждёт модель (old/recorder.py,
// SAMPLE_RATE). Микрофон открыт только пока идёт запись: постоянно открытый
// пре-буфер из old/ на Маке держал бы оранжевую точку в строке меню всё время.
//
// Звук забирают двумя путями: drain() - порциями во время записи (разбор на
// ходу), stop() - всё целиком и неотданный остаток.
final class Recorder {
    static let sampleRate: Double = 16_000

    private let target = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: Recorder.sampleRate,
                                       channels: 1, interleaved: false)!
    private let lock = NSLock()
    // Под lock: пишет аудиопоток, читает главный.
    private var converter: AVAudioConverter?
    private var samples: [Float] = []
    private var sent = 0
    // Только главный поток.
    private var engine: AVAudioEngine?
    private var observer: NSObjectProtocol?
    private(set) var running = false
    /// UID выбранного микрофона. nil или пропал - системный по умолчанию.
    var deviceUID: String?

    /// RMS каждого куска, зовётся с аудиопотока.
    var onLevel: ((Float) -> Void)?
    /// Микрофон пропал посреди записи и не поднялся. Главный поток.
    var onFailure: ((Error) -> Void)?

    static var permission: AVAuthorizationStatus {
        AVCaptureDevice.authorizationStatus(for: .audio)
    }

    static func requestPermission(_ done: @escaping (Bool) -> Void) {
        AVCaptureDevice.requestAccess(for: .audio) { ok in
            DispatchQueue.main.async { done(ok) }
        }
    }

    func start() throws {
        guard !running else { return }
        lock.lock()
        samples.removeAll(keepingCapacity: true)
        sent = 0
        lock.unlock()
        try startEngine()
        running = true
    }

    // Движок - свой на каждую запись. Один на всё время жил бы с форматом
    // прежнего устройства: подключили AirPods между диктовками - и installTap
    // с устаревшим форматом бросает исключение Objective-C, то есть падение.
    private func startEngine() throws {
        let engine = AVAudioEngine()
        let input = engine.inputNode
        // Выбранный микрофон - свойством аудиоюнита входа, до чтения формата:
        // формат у каждого устройства свой.
        if let uid = deviceUID, let device = AudioDevices.device(uid: uid), let unit = input.audioUnit {
            var id = device.id
            let st = AudioUnitSetProperty(unit, kAudioOutputUnitProperty_CurrentDevice, kAudioUnitScope_Global,
                                          0, &id, UInt32(MemoryLayout<AudioDeviceID>.size))
            if st != noErr { Log.write("микрофон \(device.name) не выбрался (\(st)) - беру системный") }
        }
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0, format.channelCount > 0 else {
            throw Recorder.error("Микрофон не найден")
        }
        guard let conv = AVAudioConverter(from: format, to: target) else {
            throw Recorder.error("Формат микрофона не поддерживается")
        }
        lock.lock()
        converter = conv
        lock.unlock()
        input.installTap(onBus: 0, bufferSize: 2048, format: format) { [weak self] buf, _ in
            self?.consume(buf)
        }
        engine.prepare()
        do {
            try engine.start()
        } catch {
            input.removeTap(onBus: 0)
            lock.lock()
            converter = nil
            lock.unlock()
            throw error
        }
        observer = NotificationCenter.default.addObserver(
            forName: .AVAudioEngineConfigurationChange, object: engine, queue: .main
        ) { [weak self] _ in self?.configurationChanged() }
        self.engine = engine
    }

    private func teardown() {
        if let observer { NotificationCenter.default.removeObserver(observer) }
        observer = nil
        engine?.inputNode.removeTap(onBus: 0)
        engine?.stop()
        engine = nil
        lock.lock()
        converter = nil
        lock.unlock()
    }

    // Подключили наушники посреди фразы - движок останавливается сам и молча.
    // Поднимаем его на новом устройстве; записанное остаётся.
    private func configurationChanged() {
        guard running else { return }
        Log.write("микрофон: сменилась конфигурация - перезапускаю движок")
        teardown()
        do {
            try startEngine()
        } catch {
            Log.write("микрофон не перезапустился: \(error.localizedDescription)")
            onFailure?(error)
        }
    }

    // Аудиопоток. Конвертер берём под тем же замком, под которым его обнуляет
    // teardown(), - иначе остановка посреди куска читала бы освобождённый объект.
    private func consume(_ buf: AVAudioPCMBuffer) {
        lock.lock()
        guard let converter else {
            lock.unlock()
            return
        }
        let ratio = target.sampleRate / buf.format.sampleRate
        let capacity = AVAudioFrameCount(Double(buf.frameLength) * ratio + 64)
        guard let out = AVAudioPCMBuffer(pcmFormat: target, frameCapacity: capacity) else {
            lock.unlock()
            return
        }
        // Один входной буфер на вызов, дальше .noDataNow: так ресемплер держит
        // состояние между кусками, а .endOfStream сбрасывал бы его и щёлкал
        // на стыках.
        var fed = false
        var error: NSError?
        converter.convert(to: out, error: &error) { _, status in
            if fed {
                status.pointee = .noDataNow
                return nil
            }
            fed = true
            status.pointee = .haveData
            return buf
        }
        guard error == nil, let ch = out.floatChannelData?[0], out.frameLength > 0 else {
            lock.unlock()
            return
        }
        let chunk = UnsafeBufferPointer(start: ch, count: Int(out.frameLength))
        samples.append(contentsOf: chunk)
        var sum: Float = 0
        for v in chunk { sum += v * v }
        let rms = sqrt(sum / Float(chunk.count))
        lock.unlock()
        onLevel?(rms)
    }

    /// Новое с прошлого вызова - для разбора на ходу.
    func drain() -> [Float] {
        lock.lock()
        defer { lock.unlock() }
        guard sent < samples.count else { return [] }
        let out = Array(samples[sent...])
        sent = samples.count
        return out
    }

    /// Остановить: вся запись и то, что ещё не отдали через drain().
    func stop() -> (all: [Float], rest: [Float]) {
        guard running else { return ([], []) }
        teardown()
        running = false
        lock.lock()
        defer { lock.unlock() }
        let all = samples
        let rest = sent < samples.count ? Array(samples[sent...]) : []
        samples.removeAll()
        sent = 0
        return (all, rest)
    }

    private static func error(_ msg: String) -> NSError {
        NSError(domain: "FlowLocal", code: 1, userInfo: [NSLocalizedDescriptionKey: msg])
    }
}
