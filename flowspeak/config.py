"""User settings — persisted as JSON at %APPDATA%\\FlowSpeak\\config.json.

A dataclass with sane defaults, forward-compatible loading (unknown keys are
ignored, missing keys fall back to defaults), and atomic saves. Mirrors the
original Rust `Settings` where it still makes sense.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Dict, List

from .paths import config_path

# Speech-to-text engines.
STT_LOCAL = "local"        # faster-whisper, fully offline (default)
STT_OPENAI = "openai"      # OpenAI-compatible /audio/transcriptions API

# Cleanup engines.
CLEANUP_RAW = "raw"        # paste exactly what was heard
CLEANUP_LOCAL = "local"    # built-in rule-based cleanup (no network)
CLEANUP_OPENAI = "openai"  # OpenAI-compatible chat API

# Cleanup aggressiveness (only meaningful for the API engine).
LEVEL_NONE = "none"
LEVEL_LIGHT = "light"      # default — conservative
LEVEL_MEDIUM = "medium"
LEVEL_HIGH = "high"

VALID_STT_ENGINES = {STT_LOCAL, STT_OPENAI}
VALID_ENGINES = {CLEANUP_RAW, CLEANUP_LOCAL, CLEANUP_OPENAI}
VALID_LEVELS = {LEVEL_NONE, LEVEL_LIGHT, LEVEL_MEDIUM, LEVEL_HIGH}


@dataclass
class Settings:
    # --- hotkey -------------------------------------------------------------
    hotkey: str = "right ctrl"       # any `keyboard`-library key name
    double_tap_lock: bool = True     # double-tap the hotkey to lock hands-free
    min_hold_ms: int = 250           # taps shorter than this are ignored

    # --- speech-to-text -----------------------------------------------------
    stt_engine: str = STT_LOCAL      # local (offline) or openai (cloud API)
    whisper_model: str = "base.en"   # tiny.en/base.en/small.en/medium.en/large-v3
    compute_type: str = "int8"       # int8 (CPU-friendly) / int8_float16 / float16
    language: str = "en"
    input_device: str = ""           # "" = system default microphone

    # --- cleanup ------------------------------------------------------------
    cleanup_engine: str = CLEANUP_LOCAL
    cleanup_level: str = LEVEL_LIGHT
    openai_api_key: str = ""         # stored here for a personal local app
    openai_base_url: str = ""        # e.g. https://openrouter.ai/api/v1 ("" = OpenAI)
    openai_model: str = "gpt-4o-mini"
    custom_style: str = ""           # free-text style instruction for the API engine
    dictionary: Dict[str, str] = field(default_factory=dict)  # misheard -> correct

    # --- behavior -----------------------------------------------------------
    play_sounds: bool = True
    paste_mode: str = "paste"        # "paste" (Ctrl+V) or "type" (char-by-char)
    launch_on_startup: bool = False
    session_cap_minutes: int = 20    # safety cap on a single hands-free session

    # ------------------------------------------------------------------------
    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or config_path()
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError, OSError):
            return cls()
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in raw.items() if k in known}
        s = cls(**clean)
        s.normalize()
        return s

    def normalize(self) -> None:
        """Clamp/repair values so a hand-edited config can't crash the app."""
        if self.stt_engine not in VALID_STT_ENGINES:
            self.stt_engine = STT_LOCAL
        if self.cleanup_engine not in VALID_ENGINES:
            self.cleanup_engine = CLEANUP_LOCAL
        if self.cleanup_level not in VALID_LEVELS:
            self.cleanup_level = LEVEL_LIGHT
        if self.paste_mode not in {"paste", "type"}:
            self.paste_mode = "paste"
        self.hotkey = (self.hotkey or "right ctrl").strip().lower()
        self.min_hold_ms = max(0, int(self.min_hold_ms))
        self.session_cap_minutes = max(1, int(self.session_cap_minutes))
        if not isinstance(self.dictionary, dict):
            self.dictionary = {}

    def save(self, path: Path | None = None) -> None:
        path = Path(path or config_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write so a crash mid-save never corrupts the file.
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(asdict(self), fh, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def has_api_key(self) -> bool:
        return bool(self.openai_api_key.strip())

    def api_ready(self) -> bool:
        return self.cleanup_engine == CLEANUP_OPENAI and self.has_api_key()

    def stt_api_ready(self) -> bool:
        return self.stt_engine == STT_OPENAI and self.has_api_key()
