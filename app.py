"""FlowLocal - приватный локальный аналог Wispr Flow для Windows.

Зажал хоткей - говоришь, отпустил - текст вставился в активное окно.
Всё локально: faster-whisper на GPU/CPU, никакого облака.

Запуск:            pythonw app.py        (без консоли)
Отладка:           python app.py
Автозапуск:        python app.py --autostart on | off

Архитектура потоков:
  main            - tkinter (оверлей) + очередь UI-команд
  keyboard hook   - press/release хоткея (поток библиотеки keyboard)
  worker          - транскрипция + вставка (по одному на фразу,
                    сериализованы через _work_lock)
  pystray         - трей-иконка (свой поток)
"""

import ctypes
import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk

APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)

import keyboard  # noqa: E402

from cleaner import clean  # noqa: E402
from inserter import insert  # noqa: E402
from overlay import Overlay  # noqa: E402
from recorder import Recorder  # noqa: E402
from transcriber import Transcriber  # noqa: E402

CONFIG_PATH = os.path.join(APP_DIR, "config.json")
LOG_PATH = os.path.join(APP_DIR, "flow.log")
HISTORY_PATH = os.path.join(APP_DIR, "history.jsonl")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "FlowLocal"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass
    print(line, end="")


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def beep(freq: int, dur: int, enabled: bool) -> None:
    if not enabled:
        return
    import winsound

    threading.Thread(target=winsound.Beep, args=(freq, dur), daemon=True).start()


class App:
    def __init__(self) -> None:
        self.cfg = load_config()
        self.root = tk.Tk()
        self.root.withdraw()
        self.overlay = Overlay(self.root)
        self.ui_queue: queue.Queue = queue.Queue()
        try:
            self.recorder = Recorder(
                pre_buffer_sec=float(self.cfg.get("pre_buffer_sec", 0.5)),
                keep_open=bool(self.cfg.get("keep_mic_open", True)),
            )
        except Exception as e:  # noqa: BLE001 - без микрофона стартуем, откроем при нажатии
            log(f"mic not available at start: {e}")
            self.recorder = Recorder(
                pre_buffer_sec=float(self.cfg.get("pre_buffer_sec", 0.5)),
                keep_open=False,
            )
        self.transcriber = Transcriber(self.cfg, log)
        self.tray = None
        self._recording = False
        self._rec_started_at = 0.0
        self._key_down = False
        self._work_lock = threading.Lock()
        self._ready = False

    # ---------- UI-очередь: все обращения к tkinter только отсюда ----------

    def ui(self, fn, *args) -> None:
        self.ui_queue.put((fn, args))

    def _poll_ui(self) -> None:
        try:
            while True:
                fn, args = self.ui_queue.get_nowait()
                try:
                    fn(*args)
                except Exception as e:  # noqa: BLE001
                    log(f"ui error: {e}")
        except queue.Empty:
            pass
        self.root.after(40, self._poll_ui)

    # ---------- хоткей ----------

    def _on_press(self, _e) -> None:
        if self._key_down:  # автоповтор зажатой клавиши
            return
        self._key_down = True
        if not self._ready or self._recording:
            return
        self._recording = True
        self._rec_started_at = time.time()
        try:
            self.recorder.start()
        except Exception as e:  # noqa: BLE001
            log(f"mic error: {e}")
            self._recording = False
            return
        beep(880, 60, self.cfg.get("sounds", True))
        self.ui(self.overlay.show_recording)
        self._set_tray_state("rec")

    def _on_release(self, _e) -> None:
        self._key_down = False
        if not self._recording:
            return
        self._recording = False
        audio = self.recorder.stop()
        dur = time.time() - self._rec_started_at
        beep(660, 60, self.cfg.get("sounds", True))
        if dur < float(self.cfg.get("min_record_sec", 0.3)) or audio.size == 0:
            self.ui(self.overlay.hide)
            self._set_tray_state("idle")
            return
        self.ui(self.overlay.show_processing)
        self._set_tray_state("proc")
        threading.Thread(target=self._process, args=(audio, dur), daemon=True).start()

    def _process(self, audio, dur: float) -> None:
        try:
            with self._work_lock:  # модель - по одной фразе за раз
                t0 = time.time()
                text = self.transcriber.transcribe(audio)
            text = clean(text, self.cfg, log)
            elapsed = time.time() - t0
            if text:
                out = text + (" " if self.cfg.get("append_space", True) else "")
                insert(
                    out,
                    mode=self.cfg.get("insert_mode", "paste"),
                    restore=self.cfg.get("restore_clipboard", True),
                )
                self._history(text, dur)
                log(f"ok: {dur:.1f}s audio -> {len(text)} chars in {elapsed:.2f}s")
            else:
                log(f"empty result ({dur:.1f}s audio)")
        except Exception as e:  # noqa: BLE001
            log(f"process error: {e}")
        finally:
            self.ui(self.overlay.hide)
            self._set_tray_state("idle")

    def _history(self, text: str, dur: float) -> None:
        if not self.cfg.get("history", True):
            return
        try:
            with open(HISTORY_PATH, "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "sec": round(dur, 1),
                            "text": text,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except OSError:
            pass

    # ---------- трей ----------

    def _tray_image(self, state: str):
        from PIL import Image, ImageDraw

        color = {"idle": "#8a8a8e", "rec": "#e05a4e", "proc": "#c9a24b", "load": "#5a7de0"}[state]
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([22, 8, 42, 40], radius=10, fill=color)   # капсула микрофона
        d.arc([14, 22, 50, 52], 0, 180, fill=color, width=5)          # дуга
        d.line([32, 52, 32, 60], fill=color, width=5)                 # ножка
        return img

    def _set_tray_state(self, state: str) -> None:
        if self.tray is not None:
            try:
                self.tray.icon = self._tray_image(state)
            except Exception:  # noqa: BLE001
                pass

    def _start_tray(self) -> None:
        import pystray

        def open_path(path):
            return lambda: subprocess.Popen(["explorer", path])

        def reload_cfg():
            try:
                self.cfg.update(load_config())
                log("config reloaded")
            except Exception as e:  # noqa: BLE001
                log(f"config reload error: {e}")

        def quit_app():
            self.tray.stop()
            self.ui(self.root.quit)

        menu = pystray.Menu(
            pystray.MenuItem(lambda _i: f"FlowLocal - {self._status()}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Открыть config.json", open_path(CONFIG_PATH)),
            pystray.MenuItem("История диктовок", open_path(HISTORY_PATH)),
            pystray.MenuItem("Лог", open_path(LOG_PATH)),
            pystray.MenuItem("Перечитать конфиг", reload_cfg),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", quit_app),
        )
        self.tray = pystray.Icon("FlowLocal", self._tray_image("load"), "FlowLocal", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

    def _status(self) -> str:
        if not self._ready:
            return "загрузка модели…"
        return f"{self.cfg.get('model')} @ {self.transcriber.device}/{self.transcriber.compute_type}"

    # ---------- запуск ----------

    def _load_model_bg(self) -> None:
        try:
            self.transcriber.load()
            self._ready = True
            self._set_tray_state("idle")
            log(f"ready, hotkey: {self.cfg.get('hotkey')}")
            beep(1040, 90, self.cfg.get("sounds", True))
        except Exception as e:  # noqa: BLE001
            log(f"FATAL: {e}")
            self.ui(self.root.quit)

    def run(self) -> None:
        hk = self.cfg.get("hotkey", "right ctrl")
        keyboard.on_press_key(hk, self._on_press, suppress=False)
        keyboard.on_release_key(hk, self._on_release, suppress=False)
        self._start_tray()
        threading.Thread(target=self._load_model_bg, daemon=True).start()
        self.root.after(40, self._poll_ui)
        log("started")
        try:
            self.root.mainloop()
        finally:
            keyboard.unhook_all()
            self.recorder.close()
            if self.tray is not None:
                try:
                    self.tray.stop()
                except Exception:  # noqa: BLE001
                    pass


def autostart(mode: str) -> None:
    import winreg

    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    cmd = f'"{pythonw}" "{os.path.join(APP_DIR, "app.py")}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if mode == "on":
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, cmd)
            print(f"автозапуск включён: {cmd}")
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass
            print("автозапуск выключен")


def single_instance() -> bool:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW(None, False, "FlowLocal_single_instance")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "--autostart":
        autostart(sys.argv[2])
        return
    if not single_instance():
        print("FlowLocal уже запущен")
        return
    App().run()


if __name__ == "__main__":
    main()
