import Foundation

// Записи диктовок - WAV 16 кГц 16 бит моно в ~/Library/Application Support/
// FlowLocal/Recordings, по файлу на запись в истории. Нужны, чтобы
// перераспознать: не расслышал, упал бэкенд, хочется другим языком. Как
// recordings.py в old/ - там это «нераспознанные записи».
enum AudioStore {
    static let dir: URL = {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let d = base.appendingPathComponent("FlowLocal/Recordings", isDirectory: true)
        try? FileManager.default.createDirectory(at: d, withIntermediateDirectories: true)
        return d
    }()

    static func url(_ name: String) -> URL {
        dir.appendingPathComponent(name)
    }

    /// Сохранить и вернуть имя файла. nil - не вышло (записано в журнал).
    static func save(_ samples: [Float], id: UUID, rate: Int = 16_000) -> String? {
        let name = "\(id.uuidString).wav"
        var data = Data(capacity: 44 + samples.count * 2)
        func put<T: FixedWidthInteger>(_ v: T) {
            withUnsafeBytes(of: v.littleEndian) { data.append(contentsOf: $0) }
        }
        let bytes = UInt32(samples.count * 2)
        data.append(contentsOf: Array("RIFF".utf8)); put(UInt32(36) + bytes)
        data.append(contentsOf: Array("WAVE".utf8))
        data.append(contentsOf: Array("fmt ".utf8)); put(UInt32(16)); put(UInt16(1)); put(UInt16(1))
        put(UInt32(rate)); put(UInt32(rate * 2)); put(UInt16(2)); put(UInt16(16))
        data.append(contentsOf: Array("data".utf8)); put(bytes)
        // Одним куском: по сэмплу через Data.append две с половиной минуты
        // звука писались 9 секунд. Int16 на x86 и arm уже little-endian.
        var pcm = [Int16](repeating: 0, count: samples.count)
        for i in pcm.indices {
            pcm[i] = Int16(max(-1, min(1, samples[i])) * 32767)
        }
        pcm.withUnsafeBytes { data.append(contentsOf: $0) }
        do {
            try data.write(to: url(name), options: .atomic)
            return name
        } catch {
            Log.write("запись не сохранилась: \(error.localizedDescription)")
            return nil
        }
    }

    /// Прочитать свой же WAV обратно в float32. Заголовок - наш, 44 байта.
    static func load(_ name: String) -> [Float]? {
        guard let data = try? Data(contentsOf: url(name)), data.count > 44 else { return nil }
        let pcm = data.dropFirst(44)
        var out = [Float](repeating: 0, count: pcm.count / 2)
        pcm.withUnsafeBytes { raw in
            for i in 0..<out.count {
                let v = Int16(littleEndian: raw.loadUnaligned(fromByteOffset: i * 2, as: Int16.self))
                out[i] = Float(v) / 32768
            }
        }
        return out
    }

    static func exists(_ name: String?) -> Bool {
        guard let name else { return false }
        return FileManager.default.fileExists(atPath: url(name).path)
    }

    static func delete(_ name: String?) {
        guard let name else { return }
        try? FileManager.default.removeItem(at: url(name))
    }
}
