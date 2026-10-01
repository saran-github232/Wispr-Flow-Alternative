"""Push-to-talk state machine behaviour."""
import unittest

from flowspeak.statemachine import (CANCEL, CAP, DISCARD, LOCK, START, STOP,
                                    PushToTalk, State)


class TestPushToTalk(unittest.TestCase):
    def test_hold_then_release_transcribes(self):
        sm = PushToTalk(min_hold_ms=250)
        self.assertEqual(sm.key_down(0), [START])
        self.assertTrue(sm.recording)
        self.assertEqual(sm.key_up(500), [STOP])
        self.assertFalse(sm.recording)

    def test_short_tap_is_discarded(self):
        sm = PushToTalk(min_hold_ms=250)
        sm.key_down(0)
        self.assertEqual(sm.key_up(100), [DISCARD])

    def test_autorepeat_down_ignored_while_recording(self):
        sm = PushToTalk()
        sm.key_down(0)
        self.assertEqual(sm.key_down(10), [])   # key auto-repeat
        self.assertEqual(sm.key_down(20), [])

    def test_double_tap_locks_handsfree(self):
        sm = PushToTalk(min_hold_ms=250, double_tap_lock=True)
        sm.key_down(0)
        self.assertEqual(sm.key_up(100), [DISCARD])   # first short tap
        self.assertEqual(sm.key_down(300), [LOCK])    # second tap within window
        self.assertEqual(sm.state, State.LOCKED)
        # a single tap while locked ends + transcribes
        self.assertEqual(sm.key_down(5000), [STOP])
        self.assertEqual(sm.state, State.IDLE)

    def test_double_tap_window_expired_starts_normally(self):
        sm = PushToTalk(min_hold_ms=250, double_tap_lock=True)
        sm.key_down(0)
        sm.key_up(100)
        self.assertEqual(sm.key_down(1000), [START])  # too late to be a double-tap

    def test_double_tap_disabled(self):
        sm = PushToTalk(min_hold_ms=250, double_tap_lock=False)
        sm.key_down(0)
        sm.key_up(100)
        self.assertEqual(sm.key_down(200), [START])

    def test_esc_cancels_active_take(self):
        sm = PushToTalk()
        sm.key_down(0)
        self.assertEqual(sm.cancel(), [CANCEL])
        self.assertFalse(sm.recording)
        self.assertEqual(sm.cancel(), [])             # nothing to cancel now

    def test_session_cap_autostops(self):
        sm = PushToTalk(session_cap_minutes=1)
        sm.key_down(0)
        self.assertEqual(sm.tick(30_000), [])         # under the cap
        self.assertEqual(sm.tick(60_000), [CAP])      # at the cap
        self.assertFalse(sm.recording)

    def test_release_without_record_is_noop(self):
        sm = PushToTalk()
        self.assertEqual(sm.key_up(100), [])


if __name__ == "__main__":
    unittest.main()
