import CryptoKit
import Foundation

// Окружение распознавания при первом запуске - для версии из .dmg.
//
// Бэкенд (server.py) работает на Python с onnxruntime. Собранный из
// репозитория FlowLocal окружение получает от build.sh; скачанному .dmg его
// взять неоткуда. Поэтому приложение заводит его само, один раз:
//
//   1. качает готовый Python (python-build-standalone, ~25 МБ) под свой
//      процессор и сверяет контрольную сумму;
//   2. распаковывает в ~/Library/Application Support/FlowLocal/Python -
//      туда же, куда кладёт окружение build.sh (Paths.python);
//   3. ставит в него библиотеки из requirements.txt внутри приложения;
//   4. пишет метку - тот же файл, что пишет build.sh: окружение годно,
//      пока метка совпадает с requirements.txt.
//
// Дальше бэкенд стартует как обычно и сам докачивает модели.
enum PythonSetup {
    enum Step: Equatable {
        case downloading(Double?)     // доля скачанного
        case unpacking
        case installing
    }

    private static let release = "20261003"
    private static let version = "3.13.16"

    private static var asset: (name: String, sha256: String) {
        #if arch(arm64)
        return ("cpython-\(version)+\(release)-aarch64-apple-darwin-install_only.tar.gz",
                "d8975d7df4f08f7b1c7aafcdfacbddcec3d366415f2c1a72b2466b6850815933")
        #else
        return ("cpython-\(version)+\(release)-x86_64-apple-darwin-install_only.tar.gz",
                "8e9cb087305bfb8969f68a905f79f41469d4aa5220c1aa71ada7fc9953bdba0f")
        #endif
    }

    private static var stamp: URL { Paths.support.appendingPathComponent("Python/.flowlocal-requirements") }
    private static var requirements: URL? { Paths.backend?.appendingPathComponent("requirements.txt") }

    /// Нужно ли заводить окружение: нет python или метка не совпадает с
    /// requirements.txt этого приложения (обновили - зависимости поменялись).
    static var needed: Bool {
        guard FileManager.default.isExecutableFile(atPath: Paths.python.path) else { return true }
        guard let req = requirements, let want = try? Data(contentsOf: req) else { return false }
        return (try? Data(contentsOf: stamp)) != want
    }

    /// Всё по шагам, в фоне. progress и done - на главном потоке.
    static func run(progress: @escaping (Step) -> Void, done: @escaping (Error?) -> Void) {
        DispatchQueue.global(qos: .userInitiated).async {
            let report: (Step) -> Void = { s in DispatchQueue.main.async { progress(s) } }
            do {
                try install(report)
                DispatchQueue.main.async { done(nil) }
            } catch {
                Log.write("окружение распознавания: \(error.localizedDescription)")
                DispatchQueue.main.async { done(error) }
            }
        }
    }

    private static func fail(_ msg: String) -> NSError {
        NSError(domain: "FlowLocal", code: 3, userInfo: [NSLocalizedDescriptionKey: msg])
    }

    private static func install(_ report: @escaping (Step) -> Void) throws {
        let fm = FileManager.default
        guard let req = requirements, fm.fileExists(atPath: req.path) else {
            throw fail("В приложении нет requirements.txt - скачайте FlowLocal заново")
        }
        try fm.createDirectory(at: Paths.support, withIntermediateDirectories: true)
        let target = Paths.support.appendingPathComponent("Python", isDirectory: true)
        let work = Paths.support.appendingPathComponent("Python.setup", isDirectory: true)
        try? fm.removeItem(at: work)
        try fm.createDirectory(at: work, withIntermediateDirectories: true)
        defer { try? fm.removeItem(at: work) }

        // 1. Python.
        let (name, sum) = asset
        let encoded = name.replacingOccurrences(of: "+", with: "%2B")
        let url = URL(string: "https://github.com/astral-sh/python-build-standalone/releases/download/\(release)/\(encoded)")!
        Log.write("окружение распознавания: качаю \(name)")
        report(.downloading(nil))
        let archive = work.appendingPathComponent("python.tar.gz")
        try download(url, to: archive) { report(.downloading($0)) }
        let digest = SHA256.hash(data: try Data(contentsOf: archive, options: .mappedIfSafe))
            .map { String(format: "%02x", $0) }.joined()
        guard digest == sum else { throw fail("Скачанный Python повреждён (контрольная сумма не сошлась). Попробуйте ещё раз") }

        // 2. Распаковка: в архиве папка python/ с bin/python3 внутри.
        report(.unpacking)
        try runTool("/usr/bin/tar", ["-xzf", archive.path, "-C", work.path])
        let unpacked = work.appendingPathComponent("python", isDirectory: true)
        guard fm.isExecutableFile(atPath: unpacked.appendingPathComponent("bin/python3").path) else {
            throw fail("В архиве Python нет bin/python3")
        }

        // 3. Библиотеки - прямо в этот Python: он только наш.
        report(.installing)
        Log.write("окружение распознавания: ставлю библиотеки")
        try runTool(unpacked.appendingPathComponent("bin/python3").path,
                    ["-m", "pip", "install", "--disable-pip-version-check", "--no-warn-script-location",
                     "-q", "-r", req.path],
                    env: ["PYTHONNOUSERSITE": "1", "PIP_NO_INPUT": "1"])
        try runTool(unpacked.appendingPathComponent("bin/python3").path,
                    ["-c", "import onnxruntime, onnx_asr, numpy"])

        // 4. На место - только целиком готовое: оборванная установка не
        // оставит полуокружение, на котором бэкенд падал бы.
        try? fm.removeItem(at: target)
        try fm.moveItem(at: unpacked, to: target)
        try fm.copyItem(at: req, to: stamp)
        Log.write("окружение распознавания готово: Python \(version)")
    }

    // MARK: - мелочи

    private static func download(_ url: URL, to dest: URL, progress: @escaping (Double) -> Void) throws {
        let sem = DispatchSemaphore(value: 0)
        var failure: Error?
        let delegate = DownloadDelegate(dest: dest, progress: progress) { error in
            failure = error
            sem.signal()
        }
        let session = URLSession(configuration: .default, delegate: delegate, delegateQueue: nil)
        session.downloadTask(with: url).resume()
        sem.wait()
        session.finishTasksAndInvalidate()
        if let failure { throw failure }
    }

    private final class DownloadDelegate: NSObject, URLSessionDownloadDelegate {
        let dest: URL
        let progress: (Double) -> Void
        let done: (Error?) -> Void
        private var finished = false

        init(dest: URL, progress: @escaping (Double) -> Void, done: @escaping (Error?) -> Void) {
            self.dest = dest
            self.progress = progress
            self.done = done
        }

        func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask, didWriteData _: Int64,
                        totalBytesWritten written: Int64, totalBytesExpectedToWrite total: Int64) {
            if total > 0 { progress(Double(written) / Double(total)) }
        }

        func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask, didFinishDownloadingTo location: URL) {
            let code = (downloadTask.response as? HTTPURLResponse)?.statusCode ?? 0
            var error: Error?
            if code != 200 {
                error = PythonSetup.fail("Python не скачался (ответ сервера \(code))")
            } else {
                do {
                    try? FileManager.default.removeItem(at: dest)
                    try FileManager.default.moveItem(at: location, to: dest)
                } catch let e { error = e }
            }
            finish(error)
        }

        func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
            if let error { finish(PythonSetup.fail("Нет интернета или GitHub недоступен: \(error.localizedDescription)")) }
        }

        private func finish(_ error: Error?) {
            guard !finished else { return }
            finished = true
            done(error)
        }
    }

    /// Запуск утилиты; вывод ошибки - в журнал и в текст ошибки.
    private static func runTool(_ path: String, _ args: [String], env extra: [String: String] = [:]) throws {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: path)
        p.arguments = args
        var env = ProcessInfo.processInfo.environment
        for (k, v) in extra { env[k] = v }
        p.environment = env
        let err = Pipe()
        p.standardError = err
        p.standardOutput = FileHandle.nullDevice
        try p.run()
        let data = err.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        guard p.terminationStatus == 0 else {
            let tail = String(decoding: data, as: UTF8.self).split(separator: "\n").suffix(3).joined(separator: " ")
            Log.write("\(URL(fileURLWithPath: path).lastPathComponent) \(args.prefix(3).joined(separator: " ")): \(tail)")
            throw fail(tail.isEmpty ? "Не удалось подготовить распознавание (код \(p.terminationStatus))" : tail)
        }
    }
}
