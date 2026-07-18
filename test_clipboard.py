"""Вставка через буфер обмена: гонка и уборка за собой.

Настоящих нажатий не шлёт и настоящий буфер не трогает - подменяет и то и
другое, поэтому годится для CI. Живую вставку проверяет test_insert.py.

Проверяем ровно то, что легко сломать обратно:

  - длинному тексту даём больше времени, чем короткому (иначе он молча не
    вставляется), но не бесконечно (иначе своя же диктовка перебивает то, что
    человек скопировал до неё);
  - прежний буфер возвращаем, только если наша диктовка всё ещё в буфере;
  - если вставка провалилась, текст остаётся в буфере, а не пропадает.

Запуск: python test_clipboard.py
"""

import sys

import inserter

ok = True


def check(cond: bool, text: str) -> None:
    global ok
    ok = ok and bool(cond)
    print(("  ок   " if cond else "ПРОВАЛ ") + text)


class FakeClipboard:
    """Буфер обмена и хроника того, что с ним делали."""

    def __init__(self, start=None):
        self.text = start
        self.log: list[str] = []
        self.set_fails = False
        self.on_paste = None      # что случится «одновременно» с Ctrl+V
        self.after_set = None     # что случится сразу после нашей записи

    def get(self):
        return self.text

    def set(self, t):
        if self.set_fails:
            self.log.append("set-провал")
            return False
        self.text = t
        self.log.append(f"set:{t[:20]}")
        if self.after_set is not None:
            hook, self.after_set = self.after_set, None
            hook(self)
        return True

    def ctrl_v(self):
        self.log.append(f"вставили:{(self.text or '')[:20]}")
        if self.on_paste is not None:
            hook, self.on_paste = self.on_paste, None
            hook(self)


def run(text, clip, mode="paste", restore=True, typing_ok=True):
    """Прогнать insert() на поддельном буфере. Возвращает (итог, напечатали)."""
    typed: list[str] = []

    def fake_type(t):
        typed.append(t)
        return typing_ok

    saved = (inserter._get_clipboard_text, inserter._set_clipboard_text,
             inserter._send_ctrl_v, inserter._wait_modifiers_released,
             inserter._type_unicode, inserter.time.sleep)
    inserter._get_clipboard_text = clip.get
    inserter._set_clipboard_text = clip.set
    inserter._send_ctrl_v = clip.ctrl_v
    inserter._wait_modifiers_released = lambda *a, **k: None
    inserter._type_unicode = fake_type
    inserter.time.sleep = lambda _s: None     # ждать по-настоящему незачем
    try:
        return inserter.insert(text, mode=mode, restore=restore), typed
    finally:
        (inserter._get_clipboard_text, inserter._set_clipboard_text,
         inserter._send_ctrl_v, inserter._wait_modifiers_released,
         inserter._type_unicode, inserter.time.sleep) = saved


def main() -> int:
    # --- сколько ждём перед уборкой ---
    w = inserter._restore_wait
    check(abs(w(120) - 0.3) < 0.06,
          "обычной фразе - прежние 300 мс с точностью до мелочи: там, где и "
          "раньше всё работало, поведение не меняем")
    check(w(500) > w(50), "длинному тексту времени больше, чем короткому")
    check(w(100_000) == inserter._RESTORE_MAX,
          "ожидание упирается в потолок, а не растёт бесконечно")
    check(w(0) == 0.3 and w(-5) == 0.3, "нулевая и отрицательная длина не ломают счёт")
    check(inserter._RESTORE_MAX <= 1.5,
          "потолок ниже полутора секунд: дольше - и своя диктовка перебьёт "
          "то, что человек скопировал до неё")

    # --- обычная вставка ---
    clip = FakeClipboard("ссылка-которую-скопировали")
    res, typed = run("Здравствуйте, отправляю письмо.", clip)
    check(res is True, "обычная вставка удалась")
    check(any(x.startswith("вставили:Здравствуйте") for x in clip.log),
          "вставили именно диктовку")
    check(clip.get() == "ссылка-которую-скопировали", "прежний буфер вернули на место")
    check(not typed, "печатать посимвольно не понадобилось")

    # --- ЛОВУШКА: человек скопировал своё, пока мы ждали ---
    clip = FakeClipboard("старое")
    clip.on_paste = lambda c: setattr(c, "text", "человек скопировал это сам")
    run("диктовка", clip)
    check(clip.get() == "человек скопировал это сам",
          "свежую копию человека не затираем своей уборкой")

    # --- ЛОВУШКА: менеджер буфера перебил нас до Ctrl+V ---
    clip = FakeClipboard("старое")
    clip.after_set = lambda c: setattr(c, "text", "подмена от менеджера буфера")
    run("диктовка", clip)
    check("вставили:диктовка" in clip.log,
          "буфер перед Ctrl+V перезаписан нашим текстом, а не чужой подменой")

    # --- буфер занят намертво ---
    clip = FakeClipboard("старое")
    clip.set_fails = True
    res, typed = run("не влезло в буфер", clip)
    check(res is True and typed == ["не влезло в буфер"],
          "буфер недоступен - печатаем посимвольно")
    check(clip.get() == "старое", "и прежний буфер при этом не трогаем")

    # --- посимвольный ввод провалился: текст не теряем ---
    clip = FakeClipboard("старое")
    res, typed = run("важный текст", clip, mode="type", typing_ok=False)
    check(res is False, "провал посимвольного ввода честно возвращает False")
    check(clip.get() == "важный текст",
          "текст остался в буфере - его спасёт Ctrl+V, не открывая программу")

    # --- restore=False ---
    clip = FakeClipboard("старое")
    run("диктовка", clip, restore=False)
    check(clip.get() == "диктовка",
          "restore=False оставляет диктовку в буфере, как и просили")

    # --- пустой текст ---
    clip = FakeClipboard("старое")
    res, typed = run("", clip)
    check(res is True and not clip.log and not typed,
          "пустой текст не делает вообще ничего")

    print("\nИТОГ:", "всё сходится" if ok else "ЕСТЬ ПРОВАЛЫ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
