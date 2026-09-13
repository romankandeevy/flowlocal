import Foundation

// Мост к backend/server.py: тот же конвейер распознавания, что в old/ (GigaAM
// + Parakeet через onnx-asr), отдельным процессом. Протокол - в шапке server.py:
// во время диктовки звук уходит порциями (begin/audio/finish), целиком - только
// запасной путь (transcribe).
//
// Процесс и трубы трогает только своя очередь queue: главный поток ставит туда
// задачи и получает ответы на себя же.
final class Backend {
    enum Event {
        case ready(String)      // "ru" | "en"
        case failed(String)
        case exited(Int32)
        case partial(id: Int, text: String, words: Int)   // разобрано на ходу
    }

    struct Result {
        let text: String
        let lang: String
        let wait: Double         // секунды от «отпустил» до текста
        let audioSec: Double
        let streamedSec: Double  // разобрано на ходу
        let tailSec: Double      // осталось на после отпускания
        let specHit: Bool        // хвост разобран заранее, пока человек молчал
    }

    typealias Completion = (Swift.Result<Result, Error>) -> Void

    var onEvent: ((Event) -> Void)?

    private let queue = DispatchQueue(label: "flowlocal.backend")
    // Только на queue.
    private var process: Process?
    private var input: FileHandle?
    private var outLines = LineSplitter()
    private var errLines = LineSplitter()
    private var pending: [Int: Completion] = [:]
    // Только главный поток.
    private var nextID = 1
    // Для stop() с любого потока: на выходе очередь может быть занята записью
    // в трубу, и ждать её синхронно значило бы заморозить «Выйти».
    private let procLock = NSLock()
    private var live: Process?

    /// Папку бэкенда вписывает build.sh в Info.plist (FLBackendDir).
    static var directory: URL? {
        guard let path = Bundle.main.object(forInfoDictionaryKey: "FLBackendDir") as? String else { return nil }
        return URL(fileURLWithPath: path)
    }

    func start() {
        queue.async { self.launch() }
    }

    func stop() {
        procLock.lock()
        let p = live
        procLock.unlock()
        queue.async { try? self.input?.write(contentsOf: Data("{\"cmd\":\"quit\"}\n".utf8)) }
        p?.terminate()
    }

    func newID() -> Int {
        defer { nextID += 1 }
        return nextID
    }

    // MARK: - команды

    func begin(_ id: Int, lang: String = "auto") {
        send(Self.header(["cmd": "begin", "id": id, "lang": lang]))
    }

    func audio(_ id: Int, _ samples: [Float]) {
        guard !samples.isEmpty else { return }
        send(Self.packet(["cmd": "audio", "id": id], samples))
    }

    func finish(_ id: Int, timeout: Double, completion: @escaping Completion) {
        request(id, Self.header(["cmd": "finish", "id": id]), timeout: timeout, completion: completion)
    }

    func cancel(_ id: Int) {
        queue.async { self.pending[id] = nil }
        send(Self.header(["cmd": "cancel", "id": id]))
    }

    func transcribe(_ id: Int, _ samples: [Float], lang: String = "auto", timeout: Double,
                    completion: @escaping Completion) {
        request(id, Self.packet(["cmd": "transcribe", "id": id, "lang": lang], samples),
                timeout: timeout, completion: completion)
    }

    private static func header(_ obj: [String: Any]) -> Data {
        var d = (try? JSONSerialization.data(withJSONObject: obj)) ?? Data()
        d.append(0x0A)
        return d
    }

    private static func packet(_ obj: [String: Any], _ samples: [Float]) -> Data {
        var o = obj
        o["samples"] = samples.count
        var d = header(o)
        samples.withUnsafeBufferPointer { d.append(Data(buffer: $0)) }
        return d
    }

    private func send(_ data: Data) {
        queue.async { self.write(data, id: nil) }
    }

    private func request(_ id: Int, _ data: Data, timeout: Double, completion: @escaping Completion) {
        queue.async {
            self.pending[id] = completion
            self.write(data, id: id)
            // Своя граница ожидания на каждый запрос: зависни бэкенд - пилюля
            // иначе показывала бы «Распознавание» вечно.
            self.queue.asyncAfter(deadline: .now() + timeout) {
                self.fail(id, "Распознавание не ответило за \(Int(timeout)) с")
            }
        }
    }

    // Только на queue.
    private func write(_ data: Data, id: Int?) {
        guard let input, process?.isRunning == true else {
            fail(id, "Распознавание не запущено")
            return
        }
        do {
            try input.write(contentsOf: data)
        } catch {
            fail(id, error.localizedDescription)
        }
    }

    private func fail(_ id: Int?, _ msg: String) {
        guard let id, let cb = pending.removeValue(forKey: id) else { return }
        let err = NSError(domain: "FlowLocal", code: 2, userInfo: [NSLocalizedDescriptionKey: msg])
        DispatchQueue.main.async { cb(.failure(err)) }
    }

    // MARK: - процесс

    private func launch() {
        guard process == nil else { return }
        guard let dir = Backend.directory else {
            emit(.failed("Не найдена папка распознавания (FLBackendDir в Info.plist)"))
            return
        }
        let python = dir.appendingPathComponent(".venv/bin/python")
        guard FileManager.default.isExecutableFile(atPath: python.path) else {
            emit(.failed("Нет \(python.path). Запустите mac/build.sh"))
            return
        }
        let p = Process()
        p.executableURL = python
        p.arguments = [dir.appendingPathComponent("server.py").path]
        p.currentDirectoryURL = dir
        var env = ProcessInfo.processInfo.environment
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        p.environment = env

        let inPipe = Pipe(), outPipe = Pipe(), errPipe = Pipe()
        p.standardInput = inPipe
        p.standardOutput = outPipe
        p.standardError = errPipe
        // Пустое чтение - конец трубы, и обработчик надо снять: иначе после
        // выхода процесса он зовётся без конца и съедает целое ядро.
        outPipe.fileHandleForReading.readabilityHandler = { [weak self] h in
            let data = h.availableData
            guard !data.isEmpty else {
                h.readabilityHandler = nil
                return
            }
            self?.queue.async { self?.consume(data) }
        }
        errPipe.fileHandleForReading.readabilityHandler = { [weak self] h in
            let data = h.availableData
            guard !data.isEmpty else {
                h.readabilityHandler = nil
                return
            }
            self?.queue.async { self?.logStderr(data) }
        }
        p.terminationHandler = { [weak self] proc in
            // Последние строки stdout могут ещё идти в очередь - даём им дойти,
            // прежде чем объявить ожидающим, что ответа не будет.
            self?.queue.asyncAfter(deadline: .now() + 0.2) { self?.reap(proc) }
        }
        do {
            try p.run()
        } catch {
            emit(.failed("Не запустился python: \(error.localizedDescription)"))
            return
        }
        process = p
        input = inPipe.fileHandleForWriting
        procLock.lock()
        live = p
        procLock.unlock()
        Log.write("распознавание запущено, pid \(p.processIdentifier)")
    }

    private func reap(_ proc: Process) {
        guard proc === process else { return }
        process = nil
        input = nil
        outLines.reset()
        errLines.reset()
        procLock.lock()
        live = nil
        procLock.unlock()
        let waiting = pending
        pending.removeAll()
        let err = NSError(domain: "FlowLocal", code: 2,
                          userInfo: [NSLocalizedDescriptionKey: "Распознавание перезапускается"])
        for cb in waiting.values {
            DispatchQueue.main.async { cb(.failure(err)) }
        }
        emit(.exited(proc.terminationStatus))
    }

    private func logStderr(_ data: Data) {
        for line in errLines.feed(data) {
            let s = String(decoding: line, as: UTF8.self)
            // onnxruntime сыплет предупреждениями - журналу они не нужны.
            if s.isEmpty || s.contains("[W:onnxruntime") { continue }
            Log.write(s)
        }
    }

    private func consume(_ data: Data) {
        for line in outLines.feed(data) {
            guard let obj = try? JSONSerialization.jsonObject(with: line) as? [String: Any] else { continue }
            if let event = obj["event"] as? String {
                switch event {
                case "ready": emit(.ready(obj["model"] as? String ?? "?"))
                case "error": emit(.failed(obj["message"] as? String ?? "Ошибка распознавания"))
                case "partial":
                    emit(.partial(id: obj["id"] as? Int ?? -1, text: obj["text"] as? String ?? "",
                                  words: obj["words"] as? Int ?? 0))
                default: break
                }
                continue
            }
            guard let id = obj["id"] as? Int, let cb = pending.removeValue(forKey: id) else { continue }
            let result: Swift.Result<Result, Error>
            if let msg = obj["error"] as? String {
                result = .failure(NSError(domain: "FlowLocal", code: 4,
                                          userInfo: [NSLocalizedDescriptionKey: msg]))
            } else {
                result = .success(Result(
                    text: obj["text"] as? String ?? "",
                    lang: obj["lang"] as? String ?? "ru",
                    wait: obj["sec"] as? Double ?? 0,
                    audioSec: obj["audio_sec"] as? Double ?? 0,
                    streamedSec: obj["streamed_sec"] as? Double ?? 0,
                    tailSec: obj["tail_sec"] as? Double ?? 0,
                    specHit: obj["spec_hit"] as? Bool ?? false))
            }
            DispatchQueue.main.async { cb(result) }
        }
    }

    private func emit(_ e: Event) {
        DispatchQueue.main.async { self.onEvent?(e) }
    }
}
