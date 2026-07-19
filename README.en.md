# FlowLocal

**Hold a key. Speak. Release. Your words land in the window you were already typing in.**

A free, local, open-source alternative to [Wispr Flow](https://wisprflow.ai) for
Windows. Audio and text never leave your machine: no account, no cloud, no
subscription.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="tools/demo_dark.gif">
    <img src="tools/demo.gif" width="820" alt="Holding the shortcut, a live waveform on the pill, then the sentence lands in the email: «Стратегическая сессия начинается в пятницу в 10:00 утра.»">
  </picture>
</p>

<p align="center">
  <sub>Real pill, real waveform, real transcription: 5 seconds of speech in
  0.22 s on a CPU, punctuation and <code>10:00</code> included. The audio comes
  from <code>test.wav</code> rather than a microphone so that
  <a href="tools/demo_gif.py"><code>tools/demo_gif.py</code></a> gives the same
  result on any machine; the mail window is a mock, because a real one cannot
  be filmed without filming someone else's correspondence.</sub>
</p>

*Russian version - [README.md](README.md).*

## Why not another Whisper dictation app

Because every local dictation tool runs Whisper, and Whisper only got good at
*some* languages.

FlowLocal transcribes with **[GigaAM](https://huggingface.co/ai-sage/GigaAM)**
(MIT, by SberDevices) - a model trained on 700,000 hours of Russian speech. Per
its model card it makes **three times fewer errors than Whisper on Russian**
(8.4% against 25.1% across domains), weighs 236 MB instead of 1.6 GB, and
**cannot hallucinate on silence**: it has no generator that needs to say
something during a pause. No "Thanks for watching!" in the middle of a thought.

No GPU required. On a CPU, 8 seconds of speech becomes text in about 0.7 s, and
with transcribing while you speak there is almost no wait at all - see below.

> **Honest caveat.** The figures above are the model card's, not ours, and we
> are not going to pretend we measured them ourselves. Our own harness
> (`tools/bench_asr.py`) measures accuracy, latency, RAM and disk, but it was
> never given live recordings: the GigaAM decision is made and confirmed by
> daily use. Believe the direction, not the decimal.

**Two models in the list, not nine.** *Standard* and *Careful* are both GigaAM,
both Russian; they differ in how carefully they handle word endings and rare
words. Nine options are a shop window, not a choice: the person the program was
installed for cannot tell CTC from RNN-T, and should not have to. The removed
models can be recovered from the repository history.

## Install

[**Download the installer**](https://github.com/romankandeevy/flowlocal/releases/latest)
- 70 MB, no administrator rights, no UAC prompt. Windows 10 or 11.

It is not code-signed, so SmartScreen will show its blue card once: *More info*
→ *Run anyway*. From source:

```powershell
git clone https://github.com/romankandeevy/flowlocal
cd flowlocal
pip install -r requirements.txt
python app.py           # first run downloads GigaAM (236 MB) into models/
```

Python 3.14 or 3.13, Windows 10/11. First launch opens an eight-screen setup:
welcome, appearance, model, microphone with a live waveform, your shortcut, a
paste check, a trial dictation (we show the text and insert it nowhere), and
finally the offer to install text editing. There is no skip button, on purpose:
a dictation app whose gesture you don't know is a dictation app that doesn't
work.

<p align="center">
  <img src="tools/preview_onboarding.png" width="620" alt="All eight setup screens: welcome, appearance, model, microphone, shortcut, paste check, trial dictation, text editing">
</p>

In the background, without a console - `pythonw app.py`. Start with Windows - a
checkbox in Settings or `python app.py --autostart on`.

## How to use it

Hold **Ctrl+Shift+Space**, talk, let go. The pill at the bottom of the screen
shows a live waveform and a timer while you speak, then `распознаю`, then the
word count - and the text is already in place.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="tools/preview_overlay_qt.png">
    <img src="tools/preview_overlay_qt_light.png" width="300" alt="Every state of the pill: loading, recording with a live waveform, transcribing, done, the mode hint, «microphone is silent», and an error">
  </picture>
</p>

Two shortcuts, and it is not a mode switch - keep both and pick per situation:

- **Hold and talk** - press, speak, release, it's inserted.
- **Press and talk** - press, talk with your hands free, press again to stop.
  **Esc** throws the recording away.

Either one can be a mouse button, modifiers included (`Ctrl+Mouse 4`). Left and
right buttons are refused on purpose: dictation on LMB would make the mouse
unusable, and you'd have nothing left to undo the setting with.

## What's in it

| | |
|---|---|
| **Transcribing while you speak** | The program starts working while you are still talking. There is almost nothing to wait for after the key, even after fifteen minutes of dictation. |
| **Filler removal** | «Ну вот, короче, я думаю, типа, надо сделать» → «Я думаю, надо сделать». No model, no download, no latency - how exactly, below. |
| **Punctuation** | Commas by the rules in hundredths of a millisecond, or by the meaning of the sentence - with a trained 30 MB model, if you download it with the button. |
| **Hears questions** | «Ты придёшь» and «Ты придёшь?» are the same words, the difference is only in the voice. We have the voice: the recording is still there. |
| **Your words** | Surnames, names, terms. Fixed by Levenshtein distance with a threshold ladder; your inflections are left alone. |
| **Replacements** | Say a phrase, get a block of text. Whole words, case-insensitive. |
| **Replacements that find themselves** | The program notices what you repeat and offers to give it a short phrase. You supply the name: a machine can find the repetition, but only you know whether that is «мой адрес» or «рабочий». |
| **Technical terms** | «джейсон» becomes JSON, «гитхаб» becomes GitHub, «пул реквест» becomes pull request. A hundred terms behind one switch. |
| **Voice commands** | «с новой строки», «нажми энтер» - line breaks and Enter, spoken. |
| **Text transforms** | Select, press, pick from the list: shorter, stricter, as a list, a task for AI, a spec. Your own are written in Settings. *Needs Ollama.* |
| **Edit selection by voice** | Select, hold, say «сделай короче» - the selection is replaced. *Needs Ollama.* |
| **Notes** | A separate window for dictating at length without aiming at someone else's field. It saves itself, is searchable by words, and tidies up with one button. |
| **Undo** | Its own shortcut. Erases exactly what was inserted - and only if you haven't typed since. |
| **Repeat** | The last recording stays in memory: if something went wrong, transcribe it again from the tray. |
| **History and stats** | Every dictation, click to copy. Plus a per-day chart and how much time it saved. |
| **How you speak** | Favourite word, catch phrase, peak hours, where you dictate the most. Counted right here, from your own history; while there is little data the program stays quiet instead of making things up. |
| **Pause music** | While you dictate. If nothing was playing, nothing starts playing: we resume only what we stopped ourselves. |
| **Mic failover** | Chosen microphone dies - we record from the system default and say so on the pill. |
| **Send message** | List the programs where a dictation ends in Enter (`telegram.exe`). Saying «нажми энтер» still works everywhere. |
| **Continuing a thought** | Dictate a second sentence right after the first and it joins properly: a space, and no capital letter mid-sentence. Not after a full stop, not in another window, not half an hour later. |
| **Backup** | Your words, replacements, tone and shortcuts - to a file and back on another machine. Loading **adds**, it never overwrites. |
| **Forgetting** | History can be kept forever, or for a year, six months, or a month. |
| **Tone per app** | `outlook.exe` - formal, chat - loose. *Needs Ollama.* |
| **Understanding corrections** | «в пятницу, нет, в субботу» → «в субботу». *Needs Ollama, and installing it is one button: the program downloads it, installs it, fetches the model and switches it on.* |
| **English interface** | Switches on the fly, the window redraws itself. Recognition stays Russian: English is there so you can hand the program to someone who doesn't read Russian. |
| **Updates** | The program sees a new release itself and installs it; the list of changes is in *About*, with no internet. |

### Filler removal without a model

A filler isn't given away by the word - it's given away by the **commas around
it**. You can't just delete «вот»: *«вот дом»* is an ordinary sentence. But a
comma is placed wherever the speaker hesitated, which means the hesitations are
**already marked up in the text**. Read the punctuation instead of guessing the
meaning, and *«И вот, короче, я»* gives itself away while *«Вот дом»* stays
untouched.

This costs zero megabytes, zero milliseconds, and - crucially - **cannot lose
your words**: nothing is generated, only marked-up fragments are struck out.

We tried the obvious thing first and it failed. Qwen3-0.6B int4 (1 GB, in the
box) turned *«Вот дом, в котором я живу»* into **«дом»**. Qwen3-1.7B with
reasoning spent 53 seconds and turned *«Выручка выросла на 15% за квартал»* into
*«Выручка выросла за квартал»* - it deleted the number the sentence existed for.
A generator can return anything by construction; a deleter cannot. But
self-corrections and tone genuinely can't be done without a model, and that is
exactly what Ollama is for.

### Transcribing while you speak

What you said a minute ago is not going to change - so there is no reason to
wait for the end of the sentence before starting work. The program transcribes
while you speak, and by the time you release the key a couple of seconds are
left. The wait stops depending on length: fifteen minutes are ready in about the
same time as half a minute.

The side effect turned out to matter more than the speed itself: **the model can
now be chosen for accuracy rather than speed** - while you are still talking,
any of them keeps up.

Turned off in *Dictation* → *Transcribe while you speak*.

### Your transforms

Ten come ready, and they cover almost everything: shorter, stricter, simpler, as
a list, as a letter, step by step, a spec, mistakes only, a task for AI, into
English. The ones you don't need are hidden with a switch, so you don't have to
look for yours among someone else's.

Your own are written in *Words* → *Your transforms*: the name on the left, what
to do with the text on the right - **in plain words, the way you would explain
it to a person**. The instruction goes to the model as it is; we are not going
to rewrite your wording into a format of our own.

## Settings

Six doors, both themes, everything applies as you change it. There is no *Apply*
button, on purpose - an extra step that is easy to forget.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="tools/preview_settings_qt_dark.png">
    <img src="tools/preview_settings_qt_light.png" alt="All six settings pages: home, dictation, words, history, stats, about">
  </picture>
</p>

| Page | What's there |
|---|---|
| **Home** | How to dictate, findings, how much you saved, recent dictations |
| **History** | Everything you dictated, click to copy; whether to keep it and what to forget |
| **Stats** | Totals, *how you speak*, where you dictate, a per-day chart |
| **Dictation** | Shortcuts, microphone, cleanup, insertion, recognition, appearance, system |
| **Words** | Your words, replacements, tone per app, transforms |
| **About** | Backup, unsaved recordings, release history, diagnostics |

**A setting you can only see in `config.json` does not exist for a person.**
That is a rule, not a wish: everything the program can do has a place in the
window. Internal thresholds are the exception - they live in the comments of
`config.py`, because there is no reason to turn them.

The look is a design system called **Korti**: two inks (paper and ink,
everything else is ink over paper at some opacity), hairlines instead of fills,
blue accent reserved for the genuinely special, green and red for status only,
motion at 120/180/280 ms on one curve and no springs. Tokens live in `theme.py`
as a single source of truth and are bridged into QML, so switching themes
repaints the window live instead of rebuilding it.

Two deliberate departures from the system, both forced:

- **The interface font is Onest, not Hanken Grotesk.** The brand font has no
  Cyrillic (checked against the cmap table), and the whole Russian interface
  turned into rows of ▯▯▯. Onest repeats the geometry and the x-height, but
  knows Cyrillic.
- **The recording dot is green, not red.** In Korti red means "error", and
  blinking it during ordinary dictation would be a lie.

## How it works

| File | Job |
|---|---|
| `app.py` | The glue: hotkey, threads, tray, the record → text → insert pipeline |
| `recorder.py` | Microphone, ring pre-buffer, levels for the waveform |
| `streaming.py` | Transcribing while the person is still speaking |
| `transcriber.py` | onnx-asr: model loading, CPU or GPU, warm-up |
| `models.py` | Model catalogue: sizes, languages, licences |
| `cleaner.py` | Your words, filler removal, tone and editing via Ollama |
| `punct_rules.py`, `punct_model.py` | Punctuation: by rules and by model |
| `intonation.py` | The question mark, from the voice |
| `transforms.py` | Text transforms: the ready-made ones and your own |
| `insights.py` | Analysis of your own speech for *Stats* |
| `inserter.py` | Insertion into the active window (clipboard + Ctrl+V, or character by character) |
| `overlay_qt.py`, `qml/Overlay.qml` | The pill |
| `settings_qt.py`, `qml/Settings.qml` | Settings: data in Python, layout in QML |
| `notes_qt.py`, `notes.py` | The notes window |
| `i18n.py` | English interface; the translation key is the Russian string itself |
| `theme.py`, `theme_qt.py` | Korti tokens - one source of truth, bridged into QML |

The pill must never steal focus: if it did, your Ctrl+V would go to the wrong
window. Qt gives us that with `WindowDoesNotAcceptFocus`, which becomes
`WS_EX_NOACTIVATE` on Windows. Waveform data travels as a C++ signal inside the
process - no IPC, no serialisation, so 60 fps costs nothing.

## Limitations

- **Windows only.** macOS is on the roadmap and is a genuine 10-15 weeks, not a weekend.
- Inserting via the clipboard overwrites its non-text contents (files, images) -
  only text is restored.
- Insertion fails into programs running as administrator if FlowLocal itself
  runs without those rights (a Windows limitation, UIPI).
- The pill isn't visible over exclusive-fullscreen games.
- Undo won't fire if you managed to type something after inserting. That's a
  guard, not a gap: otherwise Backspace would eat your text.

## Tests

Sixteen fast tests run on every push
([`.github/workflows/tests.yml`](.github/workflows/tests.yml)). They touch
nothing: no microphone, no keyboard, no network, no model.

```powershell
$env:PYTHONIOENCODING="utf-8"   # or Cyrillic in the console is mojibake
python test_clean.py        # cleanup and your words: half the cases are traps
python test_stream.py       # transcribing while you speak
python test_transforms.py   # transforms: the list, your own, the hidden ones
python test_suggest.py      # findings from history: 8 traps out of 12
python test_join.py         # joining dictations and auto-submit: 9 of 16 are traps
python test_insights.py     # analysis of your own speech: quiet while data is thin
python test_backup.py       # save, load, and that loading never overwrites
```

These send real keystrokes and move the mouse, so they stay out of CI and off a
machine you are working on:

```powershell
python test_insert.py both  # insertion into a real EDIT control
python test_hotkey.py       # binding, rebinding, capture, rollback of a broken one
```

Better to close a running instance of the program for the duration of the run -
it will take the test's shortcuts away from it.

## Roadmap

Done: the move to onnx-asr and GigaAM, cleanup without a model, transcribing
while you speak, punctuation, transforms, notes, the installer, in-app updates,
one-button Ollama, findings from your own history, backup, auto-submit, phrase
joining, pausing music, the English interface.

Shipping our own LLM in the box was **tried twice and rejected twice** - the
second time on the full 20-case harness, where Qwen3-1.7B scored 10/20 against
Ollama's 18/20 and *lost words in two cases*. The measurement is the reason, not
the taste.

What is left: **macOS**. The honest cost is 10-15 weeks, and before spending it,
three evenings of probes on a real Mac will decide whether it is possible at
all. The $99/year Apple fee turns out **not** to be required: it buys
distribution by download, and this project is not distributed that way.

This is a tool its author uses every day, not a product chasing stars. Features
land when they are worth the day they cost.

## Licence

[MIT](LICENSE). Fonts under the OFL, in `assets/fonts/`. PySide6 is LGPLv3:
builds ship as a folder with Qt in them as replaceable libraries, licence texts
included in `licenses/`. The GigaAM model is MIT from SberDevices, downloaded on
first run and never committed to the repository.

Interface fonts are Onest and JetBrains Mono, handed to Windows for this process
only (`AddFontResourceEx` + `FR_PRIVATE`): nothing is installed into your
system, and a desktop app has no business calling a CDN to draw itself.

"A Wispr Flow alternative" here is a comparison for clarity, nothing more: the
project is not affiliated with Wispr AI and borrows nothing from them.
