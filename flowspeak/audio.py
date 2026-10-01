"""Microphone capture via sounddevice.

Records mono float32 audio while the hotkey is held, reports a smoothed RMS
level for the overlay waveform, and resamples to the 16 kHz that Whisper
expects. `sounddevice` is imported lazily so the pure-logic modules (and their
tests) import fine on machines without PortAudio.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

import numpy as np

from .logs import get_logger

log = get_logger()
TARGET_SR = 16000


def _sd():
    import sounddevice as sd  # lazy: needs PortAudio at runtime
    return sd


def list_input_devices() -> list[tuple[int, str]]:
    """(index, name) for every input-capable device, for the settings UI."""
    try:
        sd = _sd()
        out = []
        for i, dev in enumerate(sd.query_devices()):
            if dev.get("max_input_channels", 0) > 0:
                out.append((i, dev.get("name", f"Device {i}")))
        return out
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not list input devices: %s", exc)
        return []


def resample_to_16k(samples: np.ndarray, sr: int) -> np.ndarray:
    """Linear resample a mono float32 signal to 16 kHz."""
    samples = np.asarray(samples, dtype=np.float32).flatten()
    if sr == TARGET_SR or samples.size == 0:
        return samples
    duration = samples.size / float(sr)
    n_out = int(round(duration * TARGET_SR))
    if n_out <= 0:
        return np.zeros(0, dtype=np.float32)
    x_old = np.linspace(0.0, duration, num=samples.size, endpoint=False)
    x_new = np.linspace(0.0, duration, num=n_out, endpoint=False)
    return np.interp(x_new, x_old, samples).astype(np.float32)


class Recorder:
    """Start/stop microphone capture. Thread-safe for start()/stop() from the
    hotkey thread while the audio callback runs on PortAudio's own thread."""

    def __init__(self, device: Optional[int] = None,
                 on_level: Optional[Callable[[float], None]] = None):
        self.device = device
        self.on_level = on_level
        self._stream = None
        self._frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self.samplerate = TARGET_SR

    def _callback(self, indata, frames, time_info, status):  # noqa: ARG002
        if status:
            log.debug("audio status: %s", status)
        with self._lock:
            self._frames.append(indata.copy())
        if self.on_level is not None:
            try:
                rms = float(np.sqrt(np.mean(np.square(indata, dtype=np.float64))))
                self.on_level(rms)
            except Exception:  # noqa: BLE001
                pass

    def start(self) -> bool:
        sd = _sd()
        with self._lock:
            self._frames = []
        try:
            sr = TARGET_SR
            try:
                info = sd.query_devices(self.device if self.device is not None else None, "input")
                sr = int(info.get("default_samplerate") or TARGET_SR)
            except Exception:  # noqa: BLE001
                sr = TARGET_SR
            self.samplerate = sr
            self._stream = sd.InputStream(
                samplerate=sr, channels=1, dtype="float32",
                device=self.device if self.device is not None else None,
                callback=self._callback, blocksize=0,
            )
            self._stream.start()
            return True
        except Exception as exc:  # noqa: BLE001
            log.error("Could not start microphone: %s", exc)
            self._stream = None
            return False

    def stop(self) -> np.ndarray:
        """Stop and return the captured audio resampled to 16 kHz mono."""
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception as exc:  # noqa: BLE001
                log.debug("stream close: %s", exc)
        with self._lock:
            frames = self._frames
            self._frames = []
        if not frames:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(frames, axis=0).flatten().astype(np.float32)
        return resample_to_16k(audio, self.samplerate)
