import AppKit
import ApplicationServices
import Carbon.HIToolbox

enum InsertOutcome {
    case pasted
    case copied     // нет права Accessibility - текст ждёт в буфере, Cmd+V руками
}

// Вставка в чужое окно: буфер + Cmd+V через CGEvent (docs/macos-port-audit.md,
// B2). Логика ожиданий и восстановления - из old/inserter.py.
enum Inserter {
    static var trusted: Bool { AXIsProcessTrusted() }

    static func requestTrust() {
        let key = kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String
        _ = AXIsProcessTrustedWithOptions([key: true] as CFDictionary)
    }

    /// Стереть свои записи «Универсального доступа». macOS привязывает право
    /// к подписи приложения: после обновления в настройках остаётся старая
    /// запись FlowLocal - тумблер включён, а к этой сборке он не относится, и
    /// сколько его ни щёлкай, доступа нет. Без старой записи macOS заводит
    /// свежую под эту подпись - и тумблер срабатывает с первого раза.
    /// tccutil трогает только записи этого приложения и прав админа не просит.
    static func resetTrust() {
        guard let id = Bundle.main.bundleIdentifier else { return }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/tccutil")
        p.arguments = ["reset", "Accessibility", id]
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        do {
            try p.run()
            p.waitUntilExit()
            Log.write("универсальный доступ: старые записи стёрты (tccutil, код \(p.terminationStatus))")
        } catch {
            Log.write("универсальный доступ: tccutil не запустился - \(error.localizedDescription)")
        }
    }

    static func openAccessibilitySettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") {
            NSWorkspace.shared.open(url)
        }
    }

    // Сколько ждать перед возвратом прежнего буфера. Фиксированные 300 мс в
    // old/ теряли длинный текст (приложение читает буфер позже, чем мы его
    // возвращаем), а долгое ожидание даёт вставить диктовку дважды. Поэтому по
    // длине: 300 мс + 450 мс на тысячу знаков, не больше 1.2 с.
    static func restoreWait(_ chars: Int) -> Double {
        min(1.2, 0.3 + 0.45 / 1000 * Double(max(0, chars)))
    }

    // Буфер человека, который ждёт возврата, и сам возврат. Одни на все вставки:
    // вторая диктовка, пришедшая раньше возврата после первой, иначе сняла бы
    // снимком первую диктовку вместо буфера человека, а возврат первой
    // пропустился бы по changeCount - и исходный буфер пропал бы насовсем.
    private static var saved: [NSPasteboardItem]?
    private static var ownsClipboard = false
    private static var pendingRestore: DispatchWorkItem?

    /// keep: вставленный текст остаётся в буфере, прежний не возвращаем.
    static func insert(_ text: String, keep: Bool = false, completion: @escaping (InsertOutcome) -> Void) {
        let pb = NSPasteboard.general
        guard trusted else {
            // Без разрешения CGEventPost молчит. Диктовку не теряем: она в
            // буфере, пилюля скажет «Cmd+V». Прежний буфер не возвращаем:
            // раньше возврат через 0.3 с затирал диктовку, и ⌘V руками
            // вставлял старое.
            pendingRestore?.cancel()
            pendingRestore = nil
            ownsClipboard = false
            saved = nil
            pb.clearContents()
            pb.setString(text, forType: .string)
            completion(.copied)
            return
        }
        pendingRestore?.cancel()
        pendingRestore = nil
        // Снимок нужен только для возврата; оставляем текст в буфере - не
        // тратим время на копию чужого буфера (картинки, Office).
        if keep {
            saved = nil
            ownsClipboard = false
        } else if !ownsClipboard {
            saved = snapshot(pb)
        }
        waitModifiersReleased {
            ownsClipboard = true
            pb.clearContents()
            pb.setString(text, forType: .string)
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                // Менеджер буфера мог переписать его сразу после нас - тогда
                // Cmd+V вставил бы его версию.
                if pb.string(forType: .string) != text {
                    pb.clearContents()
                    pb.setString(text, forType: .string)
                }
                let ours = pb.changeCount
                postCmdV()
                completion(.pasted)
                if keep {
                    ownsClipboard = false
                    saved = nil
                    return
                }
                let work = DispatchWorkItem {
                    pendingRestore = nil
                    ownsClipboard = false
                    defer { saved = nil }
                    // Человек успел скопировать своё - его копия важнее нашей уборки.
                    guard pb.changeCount == ours, let items = saved else { return }
                    pb.clearContents()
                    if !items.isEmpty { pb.writeObjects(items) }
                }
                pendingRestore = work
                DispatchQueue.main.asyncAfter(deadline: .now() + restoreWait(text.count), execute: work)
            }
        }
    }

    // Снимок буфера. Синтетические dyn.* - это пересчёт системой уже
    // имеющихся типов, а отложенные (promised) заставили бы исходное
    // приложение сейчас же отдать файл: и то и другое при восстановлении не
    // нужно и тормозит на Office и больших картинках. Больше 50 МБ - не
    // восстанавливаем вовсе (nil), чем держать такое в памяти.
    private static func snapshot(_ pb: NSPasteboard) -> [NSPasteboardItem]? {
        var total = 0
        var out: [NSPasteboardItem] = []
        for item in pb.pasteboardItems ?? [] {
            let copy = NSPasteboardItem()
            for type in item.types where !type.rawValue.hasPrefix("dyn.")
                && !type.rawValue.contains("promised") {
                guard let data = item.data(forType: type) else { continue }
                total += data.count
                if total > 50_000_000 { return nil }
                copy.setData(data, forType: type)
            }
            out.append(copy)
        }
        return out
    }

    // Зажатые модификаторы хоткея склеились бы с нашим Cmd+V (Shift+Cmd+V -
    // «вставить без форматирования»). Ждём отпускания, не дольше секунды.
    private static func waitModifiersReleased(until deadline: Date = Date().addingTimeInterval(1),
                                              _ then: @escaping () -> Void) {
        let held: CGEventFlags = [.maskCommand, .maskControl, .maskAlternate, .maskShift]
        if CGEventSource.flagsState(.combinedSessionState).intersection(held).isEmpty || Date() > deadline {
            then()
            return
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.02) {
            waitModifiersReleased(until: deadline, then)
        }
    }

    private static func postCmdV() {
        let src = CGEventSource(stateID: .combinedSessionState)
        let key = CGKeyCode(kVK_ANSI_V)
        let down = CGEvent(keyboardEventSource: src, virtualKey: key, keyDown: true)
        let up = CGEvent(keyboardEventSource: src, virtualKey: key, keyDown: false)
        down?.flags = .maskCommand
        up?.flags = .maskCommand
        down?.post(tap: .cghidEventTap)
        up?.post(tap: .cghidEventTap)
    }
}
