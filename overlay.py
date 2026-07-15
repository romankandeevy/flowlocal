"""Пилюля-индикатор внизу экрана (как у Wispr Flow): запись / обработка.

Все вызовы show/hide должны приходить из потока tkinter (через очередь
в app.py) - сам класс потокобезопасность не обеспечивает.
"""

import tkinter as tk

BG = "#1b1b1f"
FG = "#e8e6e3"
REC = "#e05a4e"
PROC = "#c9a24b"


class Overlay:
    def __init__(self, root: tk.Tk):
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.93)
        self.win.configure(bg=BG)
        self.label = tk.Label(
            self.win, text="", bg=BG, fg=FG, font=("Segoe UI", 11), padx=18, pady=9
        )
        self.label.pack()
        self.win.withdraw()
        self._blink_job: str | None = None
        self._blink_on = True

    def _place(self) -> None:
        self.win.update_idletasks()
        w = self.win.winfo_reqwidth()
        h = self.win.winfo_reqheight()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"+{(sw - w) // 2}+{sh - h - 90}")

    def show_recording(self) -> None:
        self._stop_blink()
        self._blink()
        self._place()
        self.win.deiconify()
        self.win.attributes("-topmost", True)

    def show_processing(self) -> None:
        self._stop_blink()
        self.label.config(text="…распознаю", fg=PROC)
        self._place()
        self.win.deiconify()

    def hide(self) -> None:
        self._stop_blink()
        self.win.withdraw()

    def _blink(self) -> None:
        dot = "●" if self._blink_on else "○"
        self.label.config(text=f"{dot} запись", fg=REC)
        self._blink_on = not self._blink_on
        self._blink_job = self.win.after(450, self._blink)

    def _stop_blink(self) -> None:
        if self._blink_job is not None:
            self.win.after_cancel(self._blink_job)
            self._blink_job = None
        self._blink_on = True
