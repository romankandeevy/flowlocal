import AppKit
import Carbon.HIToolbox

/// Два сочетания, как hotkey_hold / hotkey_toggle в old/.
enum HotkeyRole: String, CaseIterable, Identifiable {
    case hold, toggle

    var id: String { rawValue }
    var title: String { self == .hold ? "Удерживая клавиши" : "По нажатию" }
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
    let keys: [String]      // имена клавиш: CTRL, SHIFT, SPACE - подписи строит KeyGlyph

    /// Как macOS пишет сочетание в тексте и меню: ⌃⇧Space.
    var label: String { keys.map(KeyGlyph.short).joined() }

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

    /// Где лежит сочетание: код клавиши и модификаторы словами - так их пишет Hub Settings.
    private static func storeKeys(_ role: HotkeyRole) -> (code: String, modifiers: String) {
        role == .hold ? ("holdKeyCode", "holdModifiers") : ("toggleKeyCode", "toggleModifiers")
    }

    /// Сохранённое сочетание (его задают в Hub Settings), иначе - по умолчанию (для «Зажать» - как в old/).
    static func load(_ role: HotkeyRole) -> HotkeyPreset {
        let d = UserDefaults.standard
        let keys = storeKeys(role)
        if let code = d.object(forKey: keys.code) as? Int, let names = d.stringArray(forKey: keys.modifiers) {
            return HotkeyPreset(keyCode: code, modifierNames: names)
        }
        // Прошлые версии хранили сочетание JSON-ом под другим ключом - переносим.
        let legacy = role == .hold ? "hotkeyPreset" : "hotkeyToggle"
        if let data = d.data(forKey: legacy), let saved = try? JSONDecoder().decode(HotkeyPreset.self, from: data) {
            saved.save(role)
            d.removeObject(forKey: legacy)
            return saved
        }
        return defaultPreset(role)
    }

    func save(_ role: HotkeyRole) {
        let keys = Self.storeKeys(role)
        UserDefaults.standard.set(Int(keyCode), forKey: keys.code)
        UserDefaults.standard.set(modifierNames, forKey: keys.modifiers)
    }

    func same(as other: HotkeyPreset) -> Bool {
        keyCode == other.keyCode && modifiers == other.modifiers
    }

    /// Сочетание убрали в Hub Settings (крестик в поле) - хоткея нет.
    var isEnabled: Bool { modifiers != 0 }

    private static let modifierTable: [(name: String, carbon: Int, key: String)] = [
        ("control", controlKey, "CTRL"), ("option", optionKey, "OPTION"),
        ("shift", shiftKey, "SHIFT"), ("command", cmdKey, "CMD"),
    ]

    /// Модификаторы словами, как их хранит Hub Settings: control, option, shift, command.
    var modifierNames: [String] {
        Self.modifierTable.filter { modifiers & UInt32($0.carbon) != 0 }.map(\.name)
    }

    /// Комбо, которые ломают систему, если их перехватить глобально.
    static func isSystemCombo(keyCode: Int, mods: UInt32) -> Bool {
        let cmd = mods & UInt32(cmdKey) != 0
        guard cmd else { return false }
        // Пробел системный только с ⌘ (Spotlight) и ⌘⌥ (поиск Finder); ⌘⇧Пробел -
        // свободен, его и предлагаем.
        if keyCode == kVK_Space {
            return mods == UInt32(cmdKey) || mods == UInt32(cmdKey | optionKey)
        }
        switch keyCode {
        case kVK_ANSI_Q, kVK_ANSI_W, kVK_ANSI_H, kVK_ANSI_M, kVK_Tab,
             kVK_ANSI_F, kVK_Delete:
            return true
        default:
            return false
        }
    }

    private static let named: [Int: String] = [
        kVK_Space: "SPACE", kVK_Return: "RETURN", kVK_Tab: "TAB", kVK_Delete: "DELETE",
        kVK_ForwardDelete: "DEL", kVK_Home: "HOME", kVK_End: "END", kVK_PageUp: "PGUP",
        kVK_PageDown: "PGDN", kVK_LeftArrow: "←", kVK_RightArrow: "→", kVK_UpArrow: "↑",
        kVK_DownArrow: "↓", kVK_F1: "F1", kVK_F2: "F2", kVK_F3: "F3", kVK_F4: "F4",
        kVK_F5: "F5", kVK_F6: "F6", kVK_F7: "F7", kVK_F8: "F8", kVK_F9: "F9",
        kVK_F10: "F10", kVK_F11: "F11", kVK_F12: "F12",
    ]

    /// Имя клавиши по коду: буквы - по латинской раскладке, какая бы ни была включена.
    static func keyName(_ code: Int) -> String {
        if let name = named[code] { return name }
        guard let source = TISCopyCurrentASCIICapableKeyboardLayoutInputSource()?.takeRetainedValue(),
              let pointer = TISGetInputSourceProperty(source, kTISPropertyUnicodeKeyLayoutData)
        else { return "#\(code)" }
        let data = Unmanaged<CFData>.fromOpaque(pointer).takeUnretainedValue() as Data
        var deadKeys: UInt32 = 0
        var length = 0
        var chars = [UniChar](repeating: 0, count: 4)
        let status = data.withUnsafeBytes { raw in
            UCKeyTranslate(raw.bindMemory(to: UCKeyboardLayout.self).baseAddress, UInt16(code),
                           UInt16(kUCKeyActionDisplay), 0, UInt32(LMGetKbdType()),
                           OptionBits(kUCKeyTranslateNoDeadKeysBit), &deadKeys, chars.count, &length, &chars)
        }
        guard status == noErr, length > 0 else { return "#\(code)" }
        return String(utf16CodeUnits: chars, count: length).uppercased()
    }
}

extension HotkeyPreset {
    /// Сочетание из Hub Settings: код клавиши и модификаторы словами. Без модификаторов - сочетания нет.
    init(keyCode: Int, modifierNames names: [String]) {
        let used = Self.modifierTable.filter { names.contains($0.name) }
        let mods = used.reduce(UInt32(0)) { $0 | UInt32($1.carbon) }
        self.init(id: "custom", keyCode: UInt32(keyCode), modifiers: mods,
                  keys: mods == 0 ? [] : used.map(\.key) + [Self.keyName(keyCode)])
    }
}

/// Подписи клавиш так, как их пишет macOS в меню и Системных настройках:
/// модификаторы - знаками ⌃ ⌥ ⇧ ⌘, остальное - знаком или словом.
enum KeyGlyph {
    static func symbol(_ key: String) -> String? {
        switch key {
        case "CTRL": return "⌃"
        case "OPTION": return "⌥"
        case "SHIFT": return "⇧"
        case "CMD": return "⌘"
        default: return nil
        }
    }

    /// Слово для VoiceOver: control, option, пробел, return.
    static func word(_ key: String) -> String {
        switch key {
        case "CTRL": return "control"
        case "OPTION": return "option"
        case "SHIFT": return "shift"
        case "CMD": return "command"
        case "SPACE": return "пробел"
        case "RETURN", "TAB", "DELETE", "HOME", "END": return key.lowercased()
        case "DEL": return "⌦"
        case "PGUP": return "page up"
        case "PGDN": return "page down"
        default: return key
        }
    }

    /// Короткая подпись, как в русской macOS: ⌃, ⇧, Пробел, ↩, A.
    static func short(_ key: String) -> String {
        if let glyph = symbol(key) { return glyph }
        switch key {
        case "SPACE": return "Пробел"
        case "RETURN": return "↩"
        case "TAB": return "⇥"
        case "DELETE": return "⌫"
        case "DEL": return "⌦"
        case "HOME": return "↖"
        case "END": return "↘"
        case "PGUP": return "⇞"
        case "PGDN": return "⇟"
        default: return key
        }
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
