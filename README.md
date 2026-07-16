# FlowLocal

**Hold a key. Speak. Release. Your words land in the window you were already typing in.**

A free, local, open-source alternative to [Wispr Flow](https://wisprflow.ai) for Windows.
Audio and text never leave your machine — no account, no cloud, no subscription.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="tools/preview_overlay_qt.png">
    <img src="tools/preview_overlay_qt_light.png" width="300" alt="The FlowLocal pill: loading, recording with a live waveform, transcribing, done">
  </picture>
</p>

## Why another dictation app

Because every local dictation tool runs Whisper, and Whisper only got good at
*some* languages.

FlowLocal defaults to **[GigaAM v3](https://huggingface.co/ai-sage/GigaAM-v3)**
(MIT, by SberDevices) — a 240M Conformer trained on 700,000 hours of Russian
speech. Per its model card it averages **8.4% WER across domains where Whisper
averages 25.1%**. It is 226 MB instead of 1.6 GB, it punctuates and normalises
numbers on its own, and — because RNN-T has no autoregressive decoder — it
**cannot hallucinate on silence**. No "Thanks for watching!" during your pauses.

It also runs faster on a CPU than Whisper-large-v3-turbo does on an RTX 4090.
No GPU required. On this machine, 8 seconds of speech becomes text in ~0.7 s.

Speak something else? The model catalogue also carries **Parakeet TDT** (25
European languages, auto-detect), **Whisper large-v3-turbo** and **base** (99+
languages), and **Vosk** — all through [onnx-asr](https://github.com/istupakov/onnx-asr),
all downloadable from inside the app, all swappable without a restart.

> **Honest caveat:** the WER figures above are the model card's, not ours. Our
> own benchmark harness is in `tools/bench_asr.py` and its verdict on real
> speech isn't in yet. Believe the direction, not the decimal.

## Install

No installer yet — that's next on the roadmap. From source:

```powershell
git clone https://github.com/romankandeevy/flowlocal
cd flowlocal
pip install -r requirements.txt
python app.py           # first run downloads GigaAM (226 MB) into models/
```

Python 3.14 or 3.13, Windows 10/11. First launch opens a six-screen setup:
language and model, microphone with a live waveform, your hotkey, a paste
check, and a "say something" trial that shows the text without inserting it.

<p align="center">
  <img src="tools/preview_onboarding.png" width="620" alt="The six setup screens">
</p>

Run it in the background with `pythonw app.py`. Start with Windows: a checkbox
in Settings, or `python app.py --autostart on`.

## Settings

Nine pages, both themes, everything applies as you change it.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="tools/preview_settings_qt_dark.png">
    <img src="tools/preview_settings_qt_light.png" alt="All nine settings pages: general, recognition, models, input, dictionary, replacements, history, stats, about">
  </picture>
</p>

The look is a design system called Korti, ported by hand rather than eyeballed:
two inks (paper and ink, everything else is ink over paper at some opacity),
hairlines instead of fills, blue accent reserved for the genuinely special,
green and red for status only, motion at 120/180/280 ms on one curve and no
springs. Tokens live in `theme.py` as a single source of truth and are bridged
into QML, so switching themes repaints the window live instead of rebuilding it.

## Use it

Hold **Ctrl+Shift+Space**, talk, let go. The pill at the bottom of the screen
shows a live waveform and a timer while you speak, then `распознаю`, then the
word count — and the text is in place.

Two independent bindings, not a mode switch — keep both and pick per situation:

- **Hold and talk** — press, speak, release, it's inserted.
- **Press and talk** — press once to start, again to stop. Hands free for long
  dictation; **Esc** throws the recording away.

Either binding can be a mouse button, modifiers included (`Ctrl+Mouse 4`).
Left and right buttons are refused on purpose: dictation on LMB would make the
mouse unusable, and you'd have nothing left to undo the setting with.

## What's in it

| | |
|---|---|
| **Dictionary** | Names and terms, fixed by Levenshtein distance with a threshold ladder. Won't touch your inflections. |
| **Snippets** | Say a phrase, get a block of text. Whole words, case-insensitive. |
| **Voice commands** | "с новой строки", "нажми энтер" — line breaks and Enter, spoken. |
| **Undo** | Its own hotkey. Backspaces exactly what was inserted — and only if you haven't typed since. |
| **Retry** | The last recording stays in memory; re-run it from the tray if something went wrong. |
| **History & stats** | Every dictation, click to copy, plus a per-day chart of how much you've saved. |
| **Mic failover** | Chosen microphone dies → record from the system default, with a note on the pill. |
| **Tone per app** | `outlook.exe` → formal, chat → loose. *Requires the LLM polish below.* |
| **LLM polish** | Removes filler, applies self-corrections ("Friday — no, Saturday" → "Saturday"). *Optional, off by default, needs [Ollama](https://ollama.com) running locally.* |

The last two are the honest weak spot: they're the features that separate
FlowLocal from a plain transcriber, and today they ask you to install a second
program first. Putting a small LLM in the box is the next thing being built.

## How it works

| File | Job |
|---|---|
| `app.py` | The glue: hotkey, threads, tray, the record → text → insert pipeline |
| `recorder.py` | Microphone, ring pre-buffer, levels for the waveform |
| `transcriber.py` | onnx-asr: model loading, CPU/GPU with fallback, warm-up |
| `models.py` | Catalogue: sizes, languages, licences, pick-by-language |
| `cleaner.py` | Dictionary, filler removal, optional Ollama polish and tone |
| `inserter.py` | Insertion: clipboard + Ctrl+V, or character by character |
| `overlay_qt.py`, `qml/Overlay.qml` | The pill |
| `settings_qt.py`, `qml/Settings.qml` | Settings: data in Python, layout in QML |
| `theme.py`, `theme_qt.py` | Design tokens — one source of truth, bridged into QML |

The pill must never steal focus: if it did, your Ctrl+V would go to the wrong
window. Qt gives us that with `WindowDoesNotAcceptFocus`, which becomes
`WS_EX_NOACTIVATE` on Windows. Waveform data travels as a C++ signal inside the
process — no IPC, no serialisation, so 60 fps costs nothing.

## Limitations

- **Windows only.** macOS is on the roadmap and is a genuine 10–15 weeks, not a weekend.
- `paste` mode overwrites non-text clipboard content (files, images); only text is restored.
- Insertion fails into apps running as administrator unless FlowLocal is too (Windows UIPI).
- The pill isn't visible over exclusive-fullscreen games.
- Undo won't fire if you typed after inserting — that's a guard, not a bug.

## Tests

```powershell
$env:PYTHONIOENCODING="utf-8"   # or Cyrillic in the console is mojibake
python test_e2e.py          # WAV → transcribe → clean (no microphone needed)
python test_insert.py both  # insertion into a real EDIT control
python test_hotkey.py       # binding, rebinding, capture, rollback of a broken one
```

Tests send real keystrokes and move the mouse — don't touch the keyboard while
they run, and close a running instance first or it will eat the test's hotkeys.

## Roadmap

1. Benchmark GigaAM against real speech, not one synthetic phrase.
2. Ship a small LLM in the box so polish and tone work on first launch.
3. Command mode — select text, say what to do with it.
4. Installer, code signing, a demo GIF.
5. `platform/` abstraction, then macOS.

## Licence

[MIT](LICENSE). Fonts under the OFL, in `assets/fonts/`. PySide6 is LGPLv3 —
builds ship as onedir with Qt as replaceable libraries, licence texts included.
Parakeet is CC-BY-4.0 and requires attribution if you use it.

Interface fonts are Onest and JetBrains Mono, loaded per-process with
`AddFontResourceEx(FR_PRIVATE)` — nothing is installed into your system, and a
desktop app has no business calling a CDN to draw itself.

---

Русская версия — [README.ru.md](README.ru.md).
