"""Speech-to-text.

Two paths, chosen by settings:
  * local  — faster-whisper (CTranslate2) running fully offline on the CPU.
             The model (e.g. base.en, ~150 MB) is downloaded once on first use
             into %APPDATA%\\FlowSpeak\\models and cached there forever after.
  * openai — POST the 16 kHz WAV to an OpenAI-compatible /audio/transcriptions
             endpoint (Whisper API). Only used if explicitly configured.

The heavy `faster_whisper` import and the model load are both lazy, so importing
this module (and running the logic tests) is cheap and dependency-free.
"""
from __future__ import annotations

import io
import json
import threading
import wave

import numpy as np

from . import config as cfg
from .logs import get_logger
from .paths import models_dir

log = get_logger()


def to_wav_bytes(samples: np.ndarray, sample_rate: int = 16000) -> bytes:
    """Encode mono float32 [-1, 1] samples as 16-bit PCM WAV bytes."""
    samples = np.asarray(samples, dtype=np.float32).flatten()
    clipped = np.clip(samples, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm16.tobytes())
    return buf.getvalue()


class Transcriber:
    """Lazily holds a loaded Whisper model and transcribes float32 audio."""

    def __init__(self, settings: "cfg.Settings"):
        self.settings = settings
        self._model = None
        self._model_key: tuple | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ local
    def _ensure_model(self):
        """Load (and on first run, download) the faster-whisper model."""
        key = (self.settings.whisper_model, self.settings.compute_type)
        if self._model is not None and self._model_key == key:
            return self._model
        from faster_whisper import WhisperModel  # lazy heavy import
        log.info("Loading Whisper model %s (%s)…", *key)
        model = WhisperModel(
            self.settings.whisper_model,
            device="cpu",
            compute_type=self.settings.compute_type,
            download_root=str(models_dir()),
        )
        self._model = model
        self._model_key = key
        log.info("Whisper model ready.")
        return model

    def warm_up(self) -> bool:
        """Pre-load the model (used on startup so the first dictation is fast).
        Returns True on success; never raises."""
        try:
            with self._lock:
                self._ensure_model()
            return True
        except Exception as exc:  # noqa: BLE001
            log.error("Model warm-up failed: %s", exc)
            return False

    def _transcribe_local(self, samples: np.ndarray) -> str:
        with self._lock:
            model = self._ensure_model()
        lang = (self.settings.language or "en").strip() or None
        segments, _info = model.transcribe(
            samples,
            language=lang,
            vad_filter=True,
            beam_size=1,
            condition_on_previous_text=False,
        )
        return "".join(seg.text for seg in segments).strip()

    # ------------------------------------------------------------------ openai
    def _transcribe_openai(self, samples: np.ndarray, sample_rate: int) -> str:
        import urllib.request

        base = (self.settings.openai_base_url.strip() or "https://api.openai.com/v1").rstrip("/")
        url = base + "/audio/transcriptions"
        wav = to_wav_bytes(samples, sample_rate)
        boundary = "----FlowSpeakBoundary7MA4YWxkTrZu0gW"
        parts: list[bytes] = []

        def field(name: str, value: str):
            parts.append((f"--{boundary}\r\nContent-Disposition: form-data; "
                          f'name="{name}"\r\n\r\n{value}\r\n').encode("utf-8"))

        field("model", self.settings.openai_model or "whisper-1")
        if (self.settings.language or "").strip():
            field("language", self.settings.language.strip())
        field("response_format", "json")
        parts.append((f"--{boundary}\r\nContent-Disposition: form-data; "
                      'name="file"; filename="audio.wav"\r\n'
                      "Content-Type: audio/wav\r\n\r\n").encode("utf-8"))
        parts.append(wav)
        parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(parts)

        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Authorization": f"Bearer {self.settings.openai_api_key.strip()}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return (data.get("text") or "").strip()

    # ------------------------------------------------------------------ entry
    def transcribe(self, samples: np.ndarray, sample_rate: int = 16000) -> str:
        """Turn captured audio into text. Returns "" on failure (never raises)."""
        samples = np.asarray(samples, dtype=np.float32).flatten()
        if samples.size < sample_rate // 10:  # < ~100 ms of audio
            return ""
        use_api = self.settings.stt_api_ready()
        try:
            if use_api:
                return self._transcribe_openai(samples, sample_rate)
            return self._transcribe_local(samples)
        except Exception as exc:  # noqa: BLE001
            log.error("Transcription failed: %s", exc)
            if use_api:  # one offline retry so a network blip still produces text
                try:
                    return self._transcribe_local(samples)
                except Exception as exc2:  # noqa: BLE001
                    log.error("Local fallback also failed: %s", exc2)
            return ""
