import AppKit
import ApplicationServices

// Учимся на правках прямо в поле. После вставки запоминаем поле с фокусом
// и что стояло вокруг диктовки; пока человек в этом поле (до полутора
// минут), раз в 1,5 с перечитываем его текст. Ушёл из поля, началась новая
// диктовка или время вышло - сравниваем вставленное с тем, что стало между
// теми же соседями, и точечные замены отдаём в словарь исправлений.
//
// Работает там, где поле отдаёт текст через Универсальный доступ (Заметки,
// Почта, TextEdit, Safari, Xcode и большинство родных полей); в остальных
// молча ничего не делает. Пароли не читаем никогда. Текст поля дальше этой
// проверки не уходит и не сохраняется.
final class CorrectionWatcher {
    var onLearn: (([(from: String, to: String)]) -> Void)?

    private var element: AXUIElement?
    private var inserted = ""
    private var before = ""
    private var after = ""
    private var lastValue = ""
    private var started = Date()
    private var timer: Timer?
    private var pending: DispatchWorkItem?

    /// Длиннее - не следим: перечитывать большой документ раз в 1,5 с дорого.
    private let maxLength = 100_000

    func watch(inserted text: String) {
        finish()
        let work = DispatchWorkItem { [weak self] in self?.attach(text) }
        pending = work
        // Приложение вставляет ⌘V не мгновенно.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6, execute: work)
    }

    func finish() {
        pending?.cancel()
        pending = nil
        timer?.invalidate()
        timer = nil
        defer {
            element = nil
            inserted = ""
        }
        guard element != nil, !inserted.isEmpty,
              let region = Vocabulary.editedRegion(now: lastValue, before: before, after: after, inserted: inserted)
        else { return }
        let edited = region.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !edited.isEmpty, edited != inserted else { return }
        let pairs = Vocabulary.learn(original: inserted, edited: edited)
        if !pairs.isEmpty { onLearn?(pairs) }
    }

    private func attach(_ text: String) {
        guard AXIsProcessTrusted(), let el = Self.focused(), !Self.isSecure(el),
              let value = Self.value(el), value.count <= maxLength else { return }
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let ns = value as NSString
        let r = ns.range(of: trimmed, options: .backwards)
        guard !trimmed.isEmpty, r.location != NSNotFound else { return }
        let lo = max(0, r.location - 40)
        before = ns.substring(with: NSRange(location: lo, length: r.location - lo))
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let end = r.location + r.length
        after = ns.substring(with: NSRange(location: end, length: min(40, ns.length - end)))
            .trimmingCharacters(in: .whitespacesAndNewlines)
        inserted = trimmed
        element = el
        lastValue = value
        started = Date()
        let t = Timer(timeInterval: 1.5, repeats: true) { [weak self] _ in self?.tick() }
        t.tolerance = 0.3
        RunLoop.main.add(t, forMode: .common)
        timer = t
    }

    private func tick() {
        guard let element else { return finish() }
        if let v = Self.value(element), v.count <= maxLength { lastValue = v }
        let here = Self.focused().map { CFEqual($0, element) } ?? false
        if !here || Date().timeIntervalSince(started) > 90 { finish() }
    }

    private static func focused() -> AXUIElement? {
        var ref: CFTypeRef?
        guard AXUIElementCopyAttributeValue(AXUIElementCreateSystemWide(), kAXFocusedUIElementAttribute as CFString,
                                            &ref) == .success, let ref,
              CFGetTypeID(ref) == AXUIElementGetTypeID() else { return nil }
        return (ref as! AXUIElement)
    }

    private static func value(_ el: AXUIElement) -> String? {
        var ref: CFTypeRef?
        guard AXUIElementCopyAttributeValue(el, kAXValueAttribute as CFString, &ref) == .success else { return nil }
        return ref as? String
    }

    private static func isSecure(_ el: AXUIElement) -> Bool {
        var ref: CFTypeRef?
        AXUIElementCopyAttributeValue(el, kAXSubroleAttribute as CFString, &ref)
        return (ref as? String) == (kAXSecureTextFieldSubrole as String)
    }
}
