import AppKit
import Carbon.HIToolbox

/// Два сочетания, как hotkey_hold / hotkey_toggle в old/.
enum HotkeyRole: String, CaseIterable, Identifiable {
    case hold, toggle

    var id: String { rawValue }
    var title: String { self == .hold ? "Зажать" : "Нажать" }
    var hint: String {
        self == .hold ? "Держите и говорите, отпустили — текст на месте"
                      : "Нажали — говорите, нажали ещё раз — текст на месте"
    }
}

// Глобальные хоткеи через Carbon RegisterEventHotKey. Не требует ни
// Accessibility, ни Input Monitoring - в отличие от CGEventTap и pynput, где
// без разрешения хоткей просто молчит (docs/macos-port-audit.md, B1). И
// отдаёт отдельно нажатие и отпускание - ровно то, что нужно «зажал-сказал-
// отпустил».
struct HotkeyPreset: Identifiable, Equatable, Codable {
    let id: String
    let keyCode: UInt32
    let modifiers: UInt32
    let keys: [String]      // подписи клавиш словами, как в макете: CTRL, SHIFT, SPACE

    var label: String { keys.joined(separator: " + ") }

    // Первый - как в old/config.example.json (ctrl+shift+space).
    static let all: [HotkeyPreset] = [
        HotkeyPreset(id: "ctrl-shift-space", keyCode: UInt32(kVK_Space),
                     modifiers: UInt32(controlKey | shiftKey), keys: ["CTRL", "SHIFT", "SPACE"]),
        HotkeyPreset(id: "opt-space", keyCode: UInt32(kVK_Space),
                     modifiers: UInt32(optionKey), keys: ["OPTION", "SPACE"]),
        HotkeyPreset(id: "cmd-shift-space", keyCode: UInt32(kVK_Space),
                     modifiers: UInt32(cmdKey | shiftKey), keys: ["CMD", "SHIFT", "SPACE"]),
    ]

    /// «Нажать» по умолчанию: одна рука, без Ctrl.
    static let toggleDefault = HotkeyPreset(id: "opt-space", keyCode: UInt32(kVK_Space),
                                            modifiers: UInt32(optionKey), keys: ["OPTION", "SPACE"])

    static func defaultPreset(_ role: HotkeyRole) -> HotkeyPreset {
        role == .hold ? all[0] : toggleDefault
    }

    private static func storeKey(_ role: HotkeyRole) -> String {
        role == .hold ? "hotkeyPreset" : "hotkeyToggle"
    }

    /// Сохранённое сочетание, иначе - по умолчанию (для «Зажать» - как в old/).
    static func load(_ role: HotkeyRole) -> HotkeyPreset {
        if let data = UserDefaults.standard.data(forKey: storeKey(role)),
           let saved = try? JSONDecoder().decode(HotkeyPreset.self, from: data) {
            return saved
        }
        return defaultPreset(role)
    }

    func save(_ role: HotkeyRole) {
        if let data = try? JSONEncoder().encode(self) {
            UserDefaults.standard.set(data, forKey: Self.storeKey(role))
        }
    }

    func same(as other: HotkeyPreset) -> Bool {
        keyCode == other.keyCode && modifiers == other.modifiers
    }

    /// Своё сочетание из захвата «Нажмите клавиши». Без модификатора не
    /// принимаем: голая клавиша перехватывалась бы во всех программах.
    static func captured(keyCode: UInt16, flags: NSEvent.ModifierFlags, characters: String?) -> HotkeyPreset? {
        var mods: UInt32 = 0
        var names: [String] = []
        if flags.contains(.control) { mods |= UInt32(controlKey); names.append("CTRL") }
        if flags.contains(.option) { mods |= UInt32(optionKey); names.append("OPTION") }
        if flags.contains(.shift) { mods |= UInt32(shiftKey); names.append("SHIFT") }
        if flags.contains(.command) { mods |= UInt32(cmdKey); names.append("CMD") }
        guard mods != 0, let key = keyName(Int(keyCode), characters) else { return nil }
        return HotkeyPreset(id: "custom", keyCode: UInt32(keyCode), modifiers: mods, keys: names + [key])
    }

    private static func keyName(_ code: Int, _ chars: String?) -> String? {
        let named: [Int: String] = [
            kVK_Space: "SPACE", kVK_Return: "RETURN", kVK_Tab: "TAB", kVK_Delete: "DELETE",
            kVK_ForwardDelete: "DEL", kVK_Home: "HOME", kVK_End: "END", kVK_PageUp: "PGUP",
            kVK_PageDown: "PGDN", kVK_LeftArrow: "←", kVK_RightArrow: "→", kVK_UpArrow: "↑",
            kVK_DownArrow: "↓", kVK_F1: "F1", kVK_F2: "F2", kVK_F3: "F3", kVK_F4: "F4",
            kVK_F5: "F5", kVK_F6: "F6", kVK_F7: "F7", kVK_F8: "F8", kVK_F9: "F9",
            kVK_F10: "F10", kVK_F11: "F11", kVK_F12: "F12",
        ]
        // Esc - это «отмена» во время записи, отдавать его под хоткей нельзя.
        if code == kVK_Escape { return nil }
        if let name = named[code] { return name }
        guard let c = chars?.trimmingCharacters(in: .whitespaces), !c.isEmpty else { return nil }
        return c.uppercased()
    }
}

final class HotkeyCenter {
    static let shared = HotkeyCenter()

    private struct Handlers {
        let pressed: () -> Void
        let released: () -> Void
    }

    private var handlerRef: EventHandlerRef?
    private var refs: [UInt32: EventHotKeyRef] = [:]
    private var handlers: [UInt32: Handlers] = [:]

    private init() {
        var types = [
            EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed)),
            EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyReleased)),
        ]
        InstallEventHandler(GetApplicationEventTarget(), { _, event, _ -> OSStatus in
            guard let event else { return OSStatus(eventNotHandledErr) }
            var hk = EventHotKeyID()
            let st = GetEventParameter(event, EventParamName(kEventParamDirectObject),
                                       EventParamType(typeEventHotKeyID), nil,
                                       MemoryLayout<EventHotKeyID>.size, nil, &hk)
            guard st == noErr else { return st }
            let pressed = GetEventKind(event) == UInt32(kEventHotKeyPressed)
            HotkeyCenter.shared.dispatch(id: hk.id, pressed: pressed)
            return noErr
        }, types.count, &types, nil, &handlerRef)
    }

    private func dispatch(id: UInt32, pressed: Bool) {
        guard let h = handlers[id] else { return }
        pressed ? h.pressed() : h.released()
    }

    @discardableResult
    func register(id: UInt32, keyCode: UInt32, modifiers: UInt32,
                  pressed: @escaping () -> Void, released: @escaping () -> Void = {}) -> Bool {
        unregister(id: id)
        var ref: EventHotKeyRef?
        let hkID = EventHotKeyID(signature: OSType(0x464C_4F57), id: id)   // 'FLOW'
        let st = RegisterEventHotKey(keyCode, modifiers, hkID, GetApplicationEventTarget(), 0, &ref)
        guard st == noErr, let ref else { return false }
        refs[id] = ref
        handlers[id] = Handlers(pressed: pressed, released: released)
        return true
    }

    func unregister(id: UInt32) {
        if let ref = refs.removeValue(forKey: id) {
            UnregisterEventHotKey(ref)
        }
        handlers[id] = nil
    }
}
