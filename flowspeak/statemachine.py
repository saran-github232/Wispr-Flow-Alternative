"""Pure push-to-talk state machine (no I/O, fully unit-testable).

Feed it key/esc/tick events with millisecond timestamps; it returns a list of
actions for the app layer to carry out. This mirrors the behavior of the
original Rust reducer:

  * hold the hotkey to record, release to transcribe+paste
  * a very short tap (< min_hold_ms) is ignored (guards against accidents)
  * two short taps within the double-tap window lock hands-free mode
  * in hands-free mode, a single tap ends and transcribes
  * Esc cancels and discards the current take
  * a session longer than the cap auto-stops (safety)
"""
from __future__ import annotations

from enum import Enum

# Actions returned to the app layer.
START = "start_recording"        # begin capturing audio
STOP = "stop_and_transcribe"     # finish, transcribe + paste
DISCARD = "discard"              # stop capturing, throw audio away (too short)
LOCK = "lock_handsfree"          # begin capturing in hands-free (locked) mode
CANCEL = "cancel"                # user pressed Esc — discard
CAP = "session_cap"              # hit the safety time cap — stop + transcribe

DOUBLE_TAP_MS = 400              # max gap between taps to count as a double-tap


class State(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    LOCKED = "locked"


class PushToTalk:
    def __init__(self, min_hold_ms: int = 250, double_tap_lock: bool = True,
                 session_cap_minutes: int = 20):
        self.min_hold_ms = int(min_hold_ms)
        self.double_tap_lock = bool(double_tap_lock)
        self.session_cap_ms = int(session_cap_minutes) * 60_000
        self.state = State.IDLE
        self._press_ts = 0          # when the current take started
        self._last_tap_up_ts = None  # end of a prior short tap (double-tap tracking)

    @property
    def recording(self) -> bool:
        return self.state in (State.RECORDING, State.LOCKED)

    def key_down(self, ts: int) -> list[str]:
        if self.state == State.LOCKED:
            # A tap while hands-free ends the session.
            self.state = State.IDLE
            self._last_tap_up_ts = None
            return [STOP]
        if self.state == State.RECORDING:
            return []  # key auto-repeat while held — ignore
        # IDLE
        if (self.double_tap_lock and self._last_tap_up_ts is not None
                and ts - self._last_tap_up_ts <= DOUBLE_TAP_MS):
            self.state = State.LOCKED
            self._press_ts = ts
            self._last_tap_up_ts = None
            return [LOCK]
        self.state = State.RECORDING
        self._press_ts = ts
        return [START]

    def key_up(self, ts: int) -> list[str]:
        if self.state != State.RECORDING:
            return []  # releases in LOCKED/IDLE don't matter
        hold = ts - self._press_ts
        self.state = State.IDLE
        if hold >= self.min_hold_ms:
            self._last_tap_up_ts = None
            return [STOP]
        # Too short to be a real dictation — discard, but remember it in case a
        # second quick tap follows (double-tap -> lock).
        self._last_tap_up_ts = ts
        return [DISCARD]

    def cancel(self) -> list[str]:
        if self.recording:
            self.state = State.IDLE
            self._last_tap_up_ts = None
            return [CANCEL]
        return []

    def tick(self, ts: int) -> list[str]:
        if self.recording and ts - self._press_ts >= self.session_cap_ms:
            self.state = State.IDLE
            return [CAP]
        return []
