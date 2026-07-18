# FlowLocal

**Hold a key. Speak. Release. Your words land in the window you were already typing in.**

A free, local, open-source alternative to [Wispr Flow](https://wisprflow.ai) for Windows.
Audio and text never leave your machine — no account, no cloud, no subscription.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="tools/demo_dark.gif">
    <img src="tools/demo.gif" width="820" alt="Holding the hotkey, a live waveform on the pill, then the sentence lands in the message: 'Стратегическая сессия начинается в пятницу в 10:00 утра.'">
  </picture>
</p>

<p align="center">
  <sub>Real pill, real waveform, real model — 5 seconds of speech transcribed in
  0.22 s on a CPU, punctuation and <code>10:00</code> included. The audio comes
  from <code>test.wav</code> rather than a microphone so that
  <a href="tools/demo_gif.py"><code>tools/demo_gif.py</code></a> gives the same
  result on any machine; the mail window is a mock, because a real one cannot be
  filmed without filming someone's mail.</sub>
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

> **Honest caveat:** the WER figures above are the model card's, not ours, and
> we are not going to pretend otherwise. Our own harness (`tools/bench_asr.py`)
> measures WER, latency, RAM and disk across the catalogue, and on the one
> synthetic phrase we have it puts GigaAM at 0.0% against Whisper-turbo's 9.1%
> — a sample of one, quoted as such. Believe the direction, not the decimal.

## Install

[**Download the installer**](https://github.com/romankandeevy/flowlocal/releases/latest)
— 70 MB, no administrator rights, no UAC prompt. Windows 10/11.

It is not code-signed, so SmartScreen will show its blue card once: *More info*
→ *Run anyway*. From source instead:

```powershell
git clone https://github.com/romankandeevy/flowlocal
cd flowlocal
pip install -r requirements.txt
python app.py           # first run downloads GigaAM (226 MB) into models/
```

Python 3.14 or 3.13, Windows 10/11. First launch opens a seven-screen setup:
language and model, microphone with a live waveform, your hotkey, a paste
check, a "say something" trial that shows the text without inserting it, and
finally the offer to install text polishing. There is no skip button — a
dictation app you don't know the gesture for is a dictation app that doesn't
work.

<p align="center">
  <img src="tools/preview_onboarding.png" width="620" alt="All seven setup screens: welcome, language and model, microphone, hotkey, paste check, trial, text polishing">
</p>

Run it in the background with `pythonw app.py`. Start with Windows: a checkbox
in Settings, or `python app.py --autostart on`.

## Settings

Six doors, both themes, everything applies as you change it. The model
catalogue is deliberately not one of them — it opens from *Dictation*, because
a person writing letters has no business meeting a zoo of ASR models.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="tools/preview_settings_qt_dark.png">
    <img src="tools/preview_settings_qt_light.png" alt="All six settings pages: home, dictation, words, history, stats, about">
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

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="tools/preview_overlay_qt.png">
    <img src="tools/preview_overlay_qt_light.png" width="300" alt="Every state of the pill: loading, recording with a live waveform, transcribing, done, the toggle-mode hint, 'microphone is silent', and an error">
  </picture>
</p>

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
| **Filler removal** | "Ну вот, короче, я думаю, типа, надо сделать" → "Я думаю, надо сделать." No model, no download, no latency — see below. |
| **Snippets that write themselves** | It watches what you repeat and offers to give it a short phrase. You supply the name — a machine can find the repetition, but only you know whether that address is "my email" or "the billing one". |
| **Auto-submit** | List the apps where a dictation ends in Enter (`telegram.exe`). Saying "нажми энтер" still works everywhere. |
| **Continuing a thought** | Dictate a second sentence right after the first and it joins properly — a space, and no capital letter mid-sentence. Not after a full stop, not in another window, not half an hour later. |
| **Backup** | Save your dictionary, snippets, tone rules and hotkeys to a file, and load them back on another machine. Loading **adds** — it never overwrites what you already have. |
| **Forgetting** | History can be kept forever, or for a year, six months, or a month. |
| **Tone per app** | `outlook.exe` → formal, chat → loose. *Needs Ollama.* |
| **LLM polish** | Applies self-corrections ("Friday — no, Saturday" → "Saturday"). *Needs Ollama — and installing it is one button now: FlowLocal downloads it, installs it, fetches the model and switches polish on.* |

### Filler removal without a model

A filler isn't given away by the word — it's given away by the **commas around
it**. You can't just delete "вот": *"вот дом"* is an ordinary sentence. But
GigaAM puts a comma wherever the speaker hesitated, which means the hesitations
are **already marked up in the text**. Read the punctuation instead of guessing
the meaning, and *"И вот, короче, я"* gives itself away while *"Вот дом"* stays
untouched.

This costs zero megabytes, zero milliseconds, and — crucially — **cannot lose
your words**: nothing is generated, only marked-up tokens are struck out.

We tried the obvious thing first and it failed. Qwen3-0.6B int4 (1 GB, in-app,
via onnxruntime-genai) turned *"Вот дом, в котором я живу"* into **"дом"**.
Qwen3-1.7B with reasoning spent 53 seconds and turned *"Выручка выросла на 15%
за квартал"* into *"Выручка выросла за квартал"* — it deleted the number the
sentence existed for. A generator can return anything by construction; a
deleter cannot. Self-corrections and tone genuinely do need a model, and that's
what Ollama is for.

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

Eight fast tests run on every push (`.github/workflows/tests.yml`). They touch
nothing: no microphone, no keyboard, no network, no model.

```powershell
$env:PYTHONIOENCODING="utf-8"   # or Cyrillic in the console is mojibake
python test_clean.py        # filler removal and the dictionary — half the cases are traps
python test_suggest.py      # snippets found in history — 8 of 12 cases are traps
python test_join.py         # joining dictations and auto-submit — 9 of 16 are traps
python test_backup.py       # backup, restore, and that restoring never overwrites
python test_inputspec.py    # hotkey parsing — the deterministic half of test_hotkey
```

These two send real keystrokes and move the mouse, so they stay out of CI and
off a machine you are using:

```powershell
python test_insert.py both  # insertion into a real EDIT control
python test_hotkey.py       # binding, rebinding, capture, rollback of a broken one
```

Tests send real keystrokes and move the mouse — don't touch the keyboard while
they run, and close a running instance first or it will eat the test's hotkeys.

## Roadmap

Done: the move to onnx-asr and GigaAM, filler removal without a model, command
mode, the installer, in-app updates, one-button Ollama, snippets found in your
own history, backup and restore, auto-submit, smart joining.

Shipping a small LLM in the box was **tried and rejected twice** — the second
time on the full 20-case harness, where Qwen3-1.7B scored 10/20 against
Ollama's 18/20 and *lost words in two cases*. The measurement is the reason,
not the taste.

What is left:

1. Pausing music while you dictate.
2. macOS. The honest cost is 10–15 weeks; before spending it, three evenings of
   probes on a real Mac decide whether it is possible at all. The $99/year
   Apple fee turns out **not** to be required — it buys distribution by
   download, which this project does not do.

This is a tool its author uses every day, not a product chasing stars. Features
land when they are worth the day they cost.

## Licence

[MIT](LICENSE). Fonts under the OFL, in `assets/fonts/`. PySide6 is LGPLv3 —
builds ship as onedir with Qt as replaceable libraries, licence texts included.
Parakeet is CC-BY-4.0 and requires attribution if you use it.

Interface fonts are Onest and JetBrains Mono, loaded per-process with
`AddFontResourceEx(FR_PRIVATE)` — nothing is installed into your system, and a
desktop app has no business calling a CDN to draw itself.

---

Русская версия — [README.ru.md](README.ru.md).
