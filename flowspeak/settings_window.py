"""Settings & history window (Tkinter / ttk).

A single tabbed window — General, Speech, Cleanup, History — styled to match
the dark "Deep-Slate / Aqua" look. It edits a *copy* of the settings and only
calls ``on_save`` when the user clicks Save, so cancelling changes nothing.

Created lazily on the Tk main thread by the app; a second "open" just lifts the
existing window. Tkinter is imported defensively so the module imports headless.
"""
from __future__ import annotations

from typing import Callable, Optional

from . import ACCENT, __app_name__
from . import config as cfg
from .logs import get_logger

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except Exception:  # noqa: BLE001 - headless
    tk = None
    ttk = None
    messagebox = None

log = get_logger()

# palette
_BG = "#15181D"
_CARD = "#1C2026"
_FG = "#E6E9EF"
_MUTED = "#8A94A6"
_FIELD = "#0E1013"


def _format_history(stats) -> str:
    if stats is None:
        return "No history yet."
    s = stats.summary()
    lines = [
        f"Total words dictated: {s['total_words']:,}",
        f"Words today: {s['words_today']:,}    "
        f"Streak: {s['streak_days']} day(s)    Sessions: {s['sessions']}",
        f"Average speed: {s['wpm']} wpm    "
        f"Est. time saved vs typing: {s['time_saved_minutes']} min",
        "",
        "Recent dictations:",
    ]
    items = stats.history(limit=15)
    if not items:
        lines.append("  (nothing yet — hold your hotkey and speak)")
    else:
        import time as _t
        for it in items:
            when = _t.strftime("%b %d %H:%M", _t.localtime(it.get("ts", 0)))
            text = (it.get("text") or "").replace("\n", " ")
            if len(text) > 70:
                text = text[:67] + "…"
            lines.append(f"  [{when}] {text}")
    return "\n".join(lines)


class SettingsWindow:
    def __init__(self, root: "tk.Tk", settings: "cfg.Settings",
                 on_save: Callable[["cfg.Settings"], None],
                 stats=None):
        self.root = root
        self.settings = settings
        self.on_save = on_save
        self.stats = stats
        self.win: Optional["tk.Toplevel"] = None
        self._vars: dict = {}
        self._capturing = False

    # ------------------------------------------------------------------ open
    def show(self) -> None:
        if self.win is not None and tk is not None:
            try:
                self.win.deiconify()
                self.win.lift()
                self.win.focus_force()
                self._refresh_history()
                return
            except Exception:  # noqa: BLE001
                self.win = None
        self._build()

    def _init_style(self) -> None:
        style = ttk.Style(self.win)
        try:
            style.theme_use("clam")
        except Exception:  # noqa: BLE001
            pass
        style.configure(".", background=_BG, foreground=_FG,
                        fieldbackground=_FIELD, bordercolor=_CARD)
        style.configure("TFrame", background=_BG)
        style.configure("Card.TFrame", background=_CARD)
        style.configure("TLabel", background=_BG, foreground=_FG)
        style.configure("Muted.TLabel", background=_BG, foreground=_MUTED)
        style.configure("Head.TLabel", background=_BG, foreground=_FG,
                        font=("Segoe UI", 11, "bold"))
        style.configure("TCheckbutton", background=_BG, foreground=_FG)
        style.map("TCheckbutton", background=[("active", _BG)])
        style.configure("TButton", background=_CARD, foreground=_FG,
                        bordercolor=_CARD, focuscolor=_CARD, padding=6)
        style.map("TButton", background=[("active", "#2A2F37")])
        style.configure("Accent.TButton", background=ACCENT, foreground="#06201E",
                        font=("Segoe UI", 10, "bold"), padding=7)
        style.map("Accent.TButton", background=[("active", "#1BA99D")])
        style.configure("TNotebook", background=_BG, bordercolor=_BG)
        style.configure("TNotebook.Tab", background=_BG, foreground=_MUTED,
                        padding=(14, 7))
        style.map("TNotebook.Tab",
                  background=[("selected", _CARD)],
                  foreground=[("selected", _FG)])
        style.configure("TEntry", fieldbackground=_FIELD, foreground=_FG,
                        insertcolor=_FG)
        style.configure("TCombobox", fieldbackground=_FIELD, foreground=_FG,
                        background=_CARD, arrowcolor=_FG)
        style.configure("TSpinbox", fieldbackground=_FIELD, foreground=_FG,
                        arrowcolor=_FG)

    def _build(self) -> None:
        if tk is None:
            log.error("Tkinter unavailable; cannot open settings window.")
            return
        self.win = tk.Toplevel(self.root)
        self.win.title(f"{__app_name__} — Settings")
        self.win.configure(bg=_BG)
        self.win.geometry("560x600")
        self.win.minsize(520, 520)
        try:
            from .paths import asset_path
            ico = asset_path("flowspeak.ico")
            if ico and ico.exists():
                self.win.iconbitmap(str(ico))
        except Exception:  # noqa: BLE001
            pass
        self._init_style()
        self.win.protocol("WM_DELETE_WINDOW", self._close)

        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=12, pady=(12, 0))
        self._tab_general = ttk.Frame(nb)
        self._tab_speech = ttk.Frame(nb)
        self._tab_cleanup = ttk.Frame(nb)
        self._tab_history = ttk.Frame(nb)
        nb.add(self._tab_general, text="General")
        nb.add(self._tab_speech, text="Speech")
        nb.add(self._tab_cleanup, text="Cleanup")
        nb.add(self._tab_history, text="History")
        self._build_general(self._tab_general)
        self._build_speech(self._tab_speech)
        self._build_cleanup(self._tab_cleanup)
        self._build_history(self._tab_history)

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=12)
        ttk.Button(bar, text="Save", style="Accent.TButton",
                   command=self._save).pack(side="right")
        ttk.Button(bar, text="Cancel", command=self._close).pack(side="right", padx=8)

    def _close(self) -> None:
        if self.win is not None:
            try:
                self.win.withdraw()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _pad(frame):
        inner = ttk.Frame(frame)
        inner.pack(fill="both", expand=True, padx=16, pady=14)
        inner.columnconfigure(1, weight=1)
        return inner

    def _label(self, parent, text, row, muted=False):
        ttk.Label(parent, text=text,
                  style="Muted.TLabel" if muted else "TLabel").grid(
            row=row, column=0, sticky="w", pady=6, padx=(0, 12))

    def _hint(self, parent, text, row):
        ttk.Label(parent, text=text, style="Muted.TLabel",
                  wraplength=360, justify="left").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))

    # ------------------------------------------------------------------ General
    def _build_general(self, tab):
        p = self._pad(tab)
        v = self._vars
        r = 0
        ttk.Label(p, text="Push-to-talk", style="Head.TLabel").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(0, 6)); r += 1

        self._label(p, "Hotkey", r)
        hk_frame = ttk.Frame(p)
        hk_frame.grid(row=r, column=1, sticky="ew", pady=6)
        v["hotkey"] = tk.StringVar(value=self.settings.hotkey)
        self._hk_entry = ttk.Entry(hk_frame, textvariable=v["hotkey"])
        self._hk_entry.pack(side="left", fill="x", expand=True)
        self._hk_btn = ttk.Button(hk_frame, text="Record", width=8,
                                  command=self._capture_hotkey)
        self._hk_btn.pack(side="left", padx=(8, 0)); r += 1
        self._hint(p, "Hold this key to dictate; release to insert the text. "
                      "Right Ctrl is recommended so it won't clash with Ctrl+C/V.", r); r += 1

        v["double_tap_lock"] = tk.BooleanVar(value=self.settings.double_tap_lock)
        ttk.Checkbutton(p, text="Double-tap to lock hands-free (tap again to stop)",
                        variable=v["double_tap_lock"]).grid(
            row=r, column=0, columnspan=2, sticky="w", pady=4); r += 1

        self._label(p, "Min hold (ms)", r)
        v["min_hold_ms"] = tk.IntVar(value=self.settings.min_hold_ms)
        ttk.Spinbox(p, from_=0, to=2000, increment=50, width=8,
                    textvariable=v["min_hold_ms"]).grid(row=r, column=1, sticky="w", pady=6); r += 1

        self._label(p, "Session cap (min)", r)
        v["session_cap_minutes"] = tk.IntVar(value=self.settings.session_cap_minutes)
        ttk.Spinbox(p, from_=1, to=120, increment=1, width=8,
                    textvariable=v["session_cap_minutes"]).grid(row=r, column=1, sticky="w", pady=6); r += 1

        ttk.Label(p, text="Behaviour", style="Head.TLabel").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(14, 6)); r += 1

        self._label(p, "Insert mode", r)
        v["paste_mode"] = tk.StringVar(value=self.settings.paste_mode)
        ttk.Combobox(p, textvariable=v["paste_mode"], state="readonly",
                     values=["paste", "type"], width=12).grid(
            row=r, column=1, sticky="w", pady=6); r += 1

        v["play_sounds"] = tk.BooleanVar(value=self.settings.play_sounds)
        ttk.Checkbutton(p, text="Play start/stop sounds",
                        variable=v["play_sounds"]).grid(
            row=r, column=0, columnspan=2, sticky="w", pady=4); r += 1

        v["launch_on_startup"] = tk.BooleanVar(value=self.settings.launch_on_startup)
        ttk.Checkbutton(p, text="Launch FlowSpeak when I sign in to Windows",
                        variable=v["launch_on_startup"]).grid(
            row=r, column=0, columnspan=2, sticky="w", pady=4); r += 1

    # ------------------------------------------------------------------ Speech
    def _build_speech(self, tab):
        p = self._pad(tab)
        v = self._vars
        r = 0
        ttk.Label(p, text="Speech-to-text", style="Head.TLabel").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(0, 6)); r += 1

        self._label(p, "Engine", r)
        v["stt_engine"] = tk.StringVar(value=self.settings.stt_engine)
        ttk.Combobox(p, textvariable=v["stt_engine"], state="readonly",
                     values=[cfg.STT_LOCAL, cfg.STT_OPENAI], width=16).grid(
            row=r, column=1, sticky="w", pady=6); r += 1
        self._hint(p, "Local runs fully offline on your CPU (recommended). "
                      "OpenAI sends audio to the API key set on the Cleanup tab.", r); r += 1

        self._label(p, "Model", r)
        v["whisper_model"] = tk.StringVar(value=self.settings.whisper_model)
        ttk.Combobox(p, textvariable=v["whisper_model"], state="readonly",
                     values=["tiny.en", "base.en", "small.en", "medium.en",
                             "large-v3"], width=16).grid(
            row=r, column=1, sticky="w", pady=6); r += 1
        self._hint(p, "Bigger = more accurate but slower and larger download. "
                      "base.en (~150 MB) is a good default.", r); r += 1

        self._label(p, "Compute type", r)
        v["compute_type"] = tk.StringVar(value=self.settings.compute_type)
        ttk.Combobox(p, textvariable=v["compute_type"], state="readonly",
                     values=["int8", "int8_float16", "float16", "float32"],
                     width=16).grid(row=r, column=1, sticky="w", pady=6); r += 1

        self._label(p, "Language", r)
        v["language"] = tk.StringVar(value=self.settings.language)
        ttk.Entry(p, textvariable=v["language"], width=10).grid(
            row=r, column=1, sticky="w", pady=6); r += 1

        self._label(p, "Microphone", r)
        v["input_device"] = tk.StringVar()
        self._mic_map = {"System default": ""}
        choices = ["System default"]
        try:
            from .audio import list_input_devices
            for idx, name in list_input_devices():
                label = f"{idx}: {name}"
                self._mic_map[label] = str(idx)
                choices.append(label)
        except Exception as exc:  # noqa: BLE001
            log.debug("mic list: %s", exc)
        current = "System default"
        for label, val in self._mic_map.items():
            if val == str(self.settings.input_device):
                current = label
                break
        v["input_device"].set(current)
        ttk.Combobox(p, textvariable=v["input_device"], state="readonly",
                     values=choices, width=34).grid(
            row=r, column=1, sticky="w", pady=6); r += 1

    # ------------------------------------------------------------------ Cleanup
    def _build_cleanup(self, tab):
        p = self._pad(tab)
        v = self._vars
        r = 0
        ttk.Label(p, text="Transcript cleanup", style="Head.TLabel").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(0, 6)); r += 1

        self._label(p, "Engine", r)
        v["cleanup_engine"] = tk.StringVar(value=self.settings.cleanup_engine)
        ttk.Combobox(p, textvariable=v["cleanup_engine"], state="readonly",
                     values=[cfg.CLEANUP_RAW, cfg.CLEANUP_LOCAL, cfg.CLEANUP_OPENAI],
                     width=16).grid(row=r, column=1, sticky="w", pady=6); r += 1
        self._hint(p, "raw = paste exactly what was heard · local = offline tidy-up "
                      "(fillers, stutters, punctuation) · openai = polish via API.", r); r += 1

        self._label(p, "Aggressiveness", r)
        v["cleanup_level"] = tk.StringVar(value=self.settings.cleanup_level)
        ttk.Combobox(p, textvariable=v["cleanup_level"], state="readonly",
                     values=[cfg.LEVEL_NONE, cfg.LEVEL_LIGHT, cfg.LEVEL_MEDIUM,
                             cfg.LEVEL_HIGH], width=16).grid(
            row=r, column=1, sticky="w", pady=6); r += 1

        ttk.Label(p, text="OpenAI-compatible API (optional)",
                  style="Head.TLabel").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(14, 6)); r += 1

        self._label(p, "API key", r)
        v["openai_api_key"] = tk.StringVar(value=self.settings.openai_api_key)
        ttk.Entry(p, textvariable=v["openai_api_key"], show="•").grid(
            row=r, column=1, sticky="ew", pady=6); r += 1

        self._label(p, "Base URL", r)
        v["openai_base_url"] = tk.StringVar(value=self.settings.openai_base_url)
        ttk.Entry(p, textvariable=v["openai_base_url"]).grid(
            row=r, column=1, sticky="ew", pady=6); r += 1
        self._hint(p, "Leave blank for OpenAI. For others, e.g. "
                      "https://openrouter.ai/api/v1", r); r += 1

        self._label(p, "Model", r)
        v["openai_model"] = tk.StringVar(value=self.settings.openai_model)
        ttk.Entry(p, textvariable=v["openai_model"]).grid(
            row=r, column=1, sticky="ew", pady=6); r += 1

        self._label(p, "Custom style", r)
        v["custom_style"] = tk.StringVar(value=self.settings.custom_style)
        ttk.Entry(p, textvariable=v["custom_style"]).grid(
            row=r, column=1, sticky="ew", pady=6); r += 1
        self._hint(p, "Optional instruction for the API engine, "
                      'e.g. "Prefer British spelling; keep it formal."', r); r += 1

    # ------------------------------------------------------------------ History
    def _build_history(self, tab):
        p = ttk.Frame(tab)
        p.pack(fill="both", expand=True, padx=16, pady=14)
        self._hist_text = tk.Text(p, bg=_FIELD, fg=_FG, bd=0,
                                  font=("Consolas", 9), wrap="none",
                                  padx=10, pady=10, insertbackground=_FG)
        self._hist_text.pack(fill="both", expand=True)
        self._refresh_history()
        self._hist_text.configure(state="disabled")

    def _refresh_history(self) -> None:
        if getattr(self, "_hist_text", None) is None:
            return
        try:
            self._hist_text.configure(state="normal")
            self._hist_text.delete("1.0", "end")
            self._hist_text.insert("1.0", _format_history(self.stats))
            self._hist_text.configure(state="disabled")
        except Exception as exc:  # noqa: BLE001
            log.debug("history refresh: %s", exc)

    # ------------------------------------------------------------------ hotkey
    def _capture_hotkey(self) -> None:
        if self._capturing:
            return
        self._capturing = True
        self._hk_btn.configure(text="Press…")

        def worker():
            name = None
            try:
                import keyboard
                while True:
                    ev = keyboard.read_event(suppress=False)
                    if getattr(ev, "event_type", None) == "down" and ev.name:
                        name = ev.name
                        break
            except Exception as exc:  # noqa: BLE001
                log.warning("hotkey capture failed: %s", exc)
            self.root.after(0, lambda: self._finish_capture(name))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _finish_capture(self, name: Optional[str]) -> None:
        self._capturing = False
        try:
            self._hk_btn.configure(text="Record")
            if name:
                self._vars["hotkey"].set(name.strip().lower())
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ save
    def _collect(self) -> "cfg.Settings":
        import copy
        s = copy.deepcopy(self.settings)
        v = self._vars
        s.hotkey = v["hotkey"].get()
        s.double_tap_lock = bool(v["double_tap_lock"].get())
        s.min_hold_ms = int(v["min_hold_ms"].get())
        s.session_cap_minutes = int(v["session_cap_minutes"].get())
        s.paste_mode = v["paste_mode"].get()
        s.play_sounds = bool(v["play_sounds"].get())
        s.launch_on_startup = bool(v["launch_on_startup"].get())
        s.stt_engine = v["stt_engine"].get()
        s.whisper_model = v["whisper_model"].get()
        s.compute_type = v["compute_type"].get()
        s.language = v["language"].get().strip()
        s.input_device = self._mic_map.get(v["input_device"].get(), "")
        s.cleanup_engine = v["cleanup_engine"].get()
        s.cleanup_level = v["cleanup_level"].get()
        s.openai_api_key = v["openai_api_key"].get().strip()
        s.openai_base_url = v["openai_base_url"].get().strip()
        s.openai_model = v["openai_model"].get().strip() or "gpt-4o-mini"
        s.custom_style = v["custom_style"].get()
        s.normalize()
        return s

    def _save(self) -> None:
        try:
            new = self._collect()
        except Exception as exc:  # noqa: BLE001
            if messagebox:
                messagebox.showerror(__app_name__, f"Could not read settings:\n{exc}")
            return
        try:
            self.on_save(new)
            self.settings = new
        except Exception as exc:  # noqa: BLE001
            log.error("on_save failed: %s", exc)
            if messagebox:
                messagebox.showerror(__app_name__, f"Could not apply settings:\n{exc}")
            return
        self._close()
