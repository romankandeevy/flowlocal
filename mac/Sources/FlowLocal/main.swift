import AppKit

// Упавший бэкенд закрывает свой конец трубы; без этого запись в неё убила бы
// приложение сигналом вместо ошибки, которую мы ловим.
signal(SIGPIPE, SIG_IGN)

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
