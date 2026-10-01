# FlowSpeak 🎙️

**Local-first voice dictation for Windows.** Hold a key, talk, and your words are
cleaned up and typed into whatever app you're using — email, chat, your editor,
anywhere. Speech is transcribed **on your own machine**; nothing is uploaded.

Think of it as a lightweight, open, Wispr-Flow-style dictation tool you fully
control.

---

## ✨ Features

- **Push-to-talk** — hold **Right Ctrl**, speak, release. The text appears at your cursor.
- **Hands-free mode** — double-tap the hotkey to lock recording on; tap once to stop.
- **100% offline speech** — powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper). The model downloads once (~150 MB) and then runs with no internet.
- **Smart cleanup** — removes "um/uh", collapses stutters, turns *"new line"* / *"period"* into real formatting, applies your personal word fixes. Conservative by default, so it never changes what you actually said.
- **Optional AI polish** — plug in any OpenAI-compatible API key for stronger cleanup (off by default).
- **System tray app** — a settings window, usage stats, and dictation history, all tucked away in the tray.
- **Private by design** — config, stats, and models live in `%APPDATA%\FlowSpeak`. Your dictation never leaves the machine unless *you* turn on the cloud option.
- **Fully configurable** — change the hotkey, mic, model size, cleanup level, and more.

---

## 🚀 Install (3 steps)

> **Requirements:** Windows 10 or 11, and **Python 3.10, 3.11, 3.12, or 3.13**
> ([3.12 recommended](https://www.python.org/downloads/release/python-3127/)).
> When installing Python, tick **"Add python.exe to PATH"**.
>
> ⚠️ **Python 3.14 is not supported yet.** The offline speech engine
> (faster-whisper → ctranslate2 / onnxruntime) and NumPy don't publish Windows
> packages for 3.14 at the time of writing, so the install would fail. If 3.14 is
> all you have, install 3.12 alongside it — `install.bat` will automatically use
> the compatible one, and you can keep 3.14 for everything else.

1. **Download** this project and unzip it anywhere (e.g. your Desktop).
2. **Double-click `install.bat`.** It finds a compatible Python (3.10–3.13),
   creates a self-contained `.venv` folder, and installs everything. This takes a
   few minutes the first time. If it can't find a supported Python, it tells you
   exactly which version to install.
3. **Double-click `run.bat`.** FlowSpeak starts and lives in your system tray.

That's it. The first time you dictate, the speech model downloads automatically;
after that FlowSpeak works offline.

> 💡 Want it on your Desktop / Start Menu? Right-click **`create_shortcut.ps1`** →
> **Run with PowerShell**.

---

## 🎧 How to use it

| Action | What to do |
| --- | --- |
| **Dictate** | Hold **Right Ctrl**, speak, then release. Text is inserted at your cursor. |
| **Hands-free** | **Double-tap** Right Ctrl to lock recording on. Tap once more to stop. |
| **Cancel** | Press **Esc** while recording to throw the take away. |
| **Settings / history** | Click the FlowSpeak icon in the system tray. |
| **Pause** | Tray menu → *Pause dictation* (toggles the hotkey off). |
| **Quit** | Tray menu → *Quit*. |

A small pill appears at the bottom of your screen while recording and shows a
live waveform, then a "thinking" shimmer while it transcribes.

Spoken formatting that just works: say **"period"**, **"comma"**, **"question
mark"**, **"new line"**, or **"new paragraph"** and FlowSpeak inserts the real
glyph instead of the word.

---

## ⚙️ Settings

Open the tray icon to reach the settings window:

- **General** — hotkey (click *Record* and press any key), double-tap lock, insert
  mode (paste vs. type), start-up sound, and *launch at sign-in*.
- **Speech** — engine (local/offline or cloud API), model size (`tiny.en` →
  `large-v3`), compute type, language, and which microphone to use.
- **Cleanup** — how much tidying to apply, plus the optional API settings.
- **History** — your totals (words dictated, streak, time saved vs. typing) and a
  list of recent dictations.

### Cleanup engines

| Engine | What it does | Internet |
| --- | --- | --- |
| **Raw** | Pastes exactly what was heard (only your dictionary is applied). | No |
| **Local** *(default)* | Offline tidy-up: fillers, stutters, spoken punctuation, spacing, capitalization. | No |
| **OpenAI** | Sends the transcript to an OpenAI-compatible chat API for stronger cleanup. Falls back to local on any error. | Yes |

The default is **Local / Light** on purpose — it's conservative and won't rewrite
your wording.

### Optional: cloud cleanup or cloud speech

In **Settings → Cleanup**, paste an API key and (optionally) a custom base URL —
e.g. `https://openrouter.ai/api/v1` — to use any OpenAI-compatible provider. The
same key can power cloud speech-to-text (**Settings → Speech → Engine → openai**)
if you'd rather not run Whisper locally. Both are **off by default**; FlowSpeak is
fully offline out of the box.

---

## 🔒 Privacy & your data

Everything is stored locally under `%APPDATA%\FlowSpeak`:

- `config.json` — your settings
- `stats.json` — usage stats & recent dictation history
- `models/` — the downloaded speech model(s)
- `flowspeak.log` — a local log file

Audio is processed in memory and is **not** saved to disk. Nothing is sent over
the network unless you explicitly enable a cloud engine.

---

## 🛠️ Troubleshooting

**`No module named 'numpy'` (or the app won't start after install).** This almost
always means the dependencies didn't install because your default Python is too
new (3.14+). Install **Python 3.12** from python.org (tick *"Add python.exe to
PATH"*), then double-click **`install.bat`** again — it will detect 3.12, rebuild
the environment, and install everything. You don't need to uninstall 3.14.

**The hotkey does nothing.** The global keyboard hook sometimes needs elevated
rights. Right-click `run.bat` → *Run as administrator*. (If you dictate into apps
that themselves run as admin, FlowSpeak must be elevated too.)

**"No microphone" / silence.** Check Windows **Settings → Privacy & security →
Microphone** and make sure desktop apps are allowed. Pick the right input device
in **Settings → Speech**.

**Antivirus flags it.** The `keyboard` library listens for global key presses
(that's how push-to-talk works), which some antivirus tools treat as suspicious.
It's a well-known open-source package; allow it if prompted.

**First dictation is slow.** That's the one-time model download (~150 MB) plus
loading it into memory. Later dictations are fast. A smaller model (`tiny.en`) is
quicker; a larger one (`small.en`, `medium.en`) is more accurate.

**I need to see what went wrong.** Run **`run-debug.bat`** — it keeps a console
window open and prints logs (also saved to `%APPDATA%\FlowSpeak\flowspeak.log`).

---

## 📦 Optional: build a standalone `.exe`

If you'd like a single executable that runs without a separate Python install:

```
build-exe.bat
```

This produces `dist\FlowSpeak.exe` (via PyInstaller). The first dictation still
downloads the speech model.

---

## 👩‍💻 For developers

```bash
# from the project folder, with the venv active
python -m flowspeak           # run the app
python -m unittest discover -s tests   # run the test suite
```

Project layout:

```
flowspeak/
  config.py        settings (load/save/normalize)
  statemachine.py  pure push-to-talk reducer
  cleanup.py       transcript cleanup (local + optional API)
  stats.py         local usage stats & history
  audio.py         microphone capture (sounddevice)
  transcribe.py    speech-to-text (faster-whisper / API)
  paste.py         insert text at the cursor
  hotkey.py        global hotkey listener (keyboard)
  overlay.py       the floating pill (Tkinter)
  tray.py          system-tray icon & menu (pystray)
  settings_window.py  settings & history UI (Tkinter)
  app.py           orchestrator that wires it all together
tests/             unit tests for the pure logic
legacy-rust-tauri/ the original Rust/Tauri version, archived for reference
```

The pure-logic modules (`config`, `cleanup`, `stats`, `statemachine`) have no
hardware or GUI dependencies and are covered by unit tests. A headless
integration smoke test (`tests/test_integration_smoke.py`) drives the full
hotkey → record → transcribe → clean → paste → stats pipeline with the mic,
GUI, and speech model replaced by in-process fakes, so the whole app can be
verified on any machine (no microphone, display, or model download required).

---

## 📝 About the previous version

This project began as a Rust + Tauri desktop app (now kept under
`legacy-rust-tauri/`). That stack required a full C++/LLVM/CMake toolchain to
build, which made it hard to install. This version is a from-scratch **pure-Python
rewrite** with the same idea but a one-double-click install.

---

## ⚖️ License

Released under the [MIT License](LICENSE) — free to use, modify, and distribute,
including commercially, with attribution. See [`LICENSE`](LICENSE) for the full text.

