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
    /// Когда пришёл последний кусок звука - для сторожа мёртвого микрофона.
    private var lastBuffer = Date()
    // Только главный поток.
    private var engine: AVAudioEngine?
    private var observer: NSObjectProtocol?
    private var format: AVAudioFormat?
    private var restartPending = false
    private var restarts = 0
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
        lastBuffer = Date()
        lock.unlock()
        restarts = 0
        do {
            try startEngine()
        } catch where deviceUID != nil {
            // Выбранный микрофон не запускается (встроенный при подключённых
            // наушниках даёт -10868) - запись важнее выбора: берём системный.
            Log.write("выбранный микрофон не открылся (\(error.localizedDescription)) - беру системный")
            teardown()
            deviceUID = nil
            try startEngine()
        }
        // Отсчёт сторожа - от поднятого движка: на Bluetooth открытие идёт
        // до нескольких секунд, и это не тишина.
        lock.lock()
        lastBuffer = Date()
        lock.unlock()
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
        // Формат отвода - nil, то есть «какой есть у узла сейчас». Явный
        // формат после смены устройства бывает устаревшим, и installTap
        // бросает исключение Objective-C - падение всего приложения (так и
        // было со встроенным микрофоном при подключённых наушниках).
        // Конвертер подстраивается под формат пришедшего куска в consume().
        input.installTap(onBus: 0, bufferSize: 2048, format: nil) { [weak self] buf, _ in
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
        self.format = format
    }

    private func teardown() {
        if let observer { NotificationCenter.default.removeObserver(observer) }
        observer = nil
        engine?.inputNode.removeTap(onBus: 0)
        engine?.stop()
        engine = nil
        format = nil
        lock.lock()
        converter = nil
        lock.unlock()
    }

    // Подключили наушники посреди фразы - движок останавливается сам и молча.
    // Поднимаем его на новом устройстве; записанное остаётся.
    //
    // Уведомление приходит и без смены устройства - например, от выбора
    // микрофона в startEngine() или от Bluetooth-гарнитуры, переключающей
    // профиль. Перезапуск на каждое такое вызывал новое уведомление, движок
    // крутился в цикле по несколько раз в секунду и запись выходила пустой.
    // Поэтому: пачку уведомлений склеиваем в одно, живой движок с прежним
    // форматом не трогаем, а перезапусков на одну запись - не больше трёх.
    private func configurationChanged() {
        guard running, !restartPending else { return }
        restartPending = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { [weak self] in
            guard let self else { return }
            self.restartPending = false
            self.restartIfNeeded()
        }
    }

    private func restartIfNeeded() {
        guard running, let engine else { return }
        let now = engine.inputNode.outputFormat(forBus: 0)
        if engine.isRunning, let format,
           now.sampleRate == format.sampleRate, now.channelCount == format.channelCount {
            return
        }
        guard restarts < 3 else {
            Log.write("микрофон: слишком много перезапусков подряд - останавливаю запись")
            onFailure?(Recorder.error("Микрофон постоянно переключается"))
            return
        }
        restarts += 1
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
        guard var converter else {
            lock.unlock()
            return
        }
        if converter.inputFormat != buf.format {
            guard let fresh = AVAudioConverter(from: buf.format, to: target) else {
                lock.unlock()
                return
            }
            self.converter = fresh
            converter = fresh
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
        lastBuffer = Date()
        var sum: Float = 0
        for v in chunk { sum += v * v }
        let rms = sqrt(sum / Float(chunk.count))
        lock.unlock()
        onLevel?(rms)
    }

    /// Сторож: движок «работает», а звук не идёт. Так бывает, когда
    /// Bluetooth-наушники переключают профиль (пауза музыки, звонок):
    /// уведомления о смене конфигурации нет, формат прежний, а отвод молчит.
    /// Звали раз в 0,25 с; тишина дольше секунды - поднимаем движок заново.
    func checkAlive() {
        guard running, !restartPending else { return }
        lock.lock()
        let silent = Date().timeIntervalSince(lastBuffer)
        lock.unlock()
        guard silent > 1.0 else { return }
        guard restarts < 3 else {
            Log.write("микрофон молчит и не поднимается - останавливаю запись")
            running = false
            onFailure?(Recorder.error("Микрофон не отдаёт звук"))
            return
        }
        restarts += 1
        // Выбранный микрофон молчит - обычно он не системный вход (скажем,
        // встроенный при подключённых наушниках), и такой движок звука не
        // отдаёт. До конца записи берём системный.
        if deviceUID != nil {
            Log.write("выбранный микрофон молчит - переключаюсь на системный")
            deviceUID = nil
        }
        Log.write(String(format: "микрофон молчит %.1f с - перезапускаю движок", silent))
        teardown()
        lock.lock()
        lastBuffer = Date()
        lock.unlock()
        do {
            try startEngine()
        } catch {
            Log.write("микрофон не перезапустился: \(error.localizedDescription)")
            onFailure?(error)
        }
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
