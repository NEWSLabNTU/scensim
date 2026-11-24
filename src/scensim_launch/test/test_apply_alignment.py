"""scripts/apply_alignment.py (issue 135 step 2): each label where it belongs, by value within
float32's tolerance, drops leaving frames unclassified, raced calls counted apart."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import apply_alignment as aa  # noqa: E402

HEADER = "kind,mono_ns,f_obs,f_after,throttle,brake,steer,hand_brake,reverse,gear,call_us"


def tick(ns, frame):
    return f"tick,{ns},{frame},,,,,,,,"


def apply(ns, f_obs, f_after, throttle, steer=0.0):
    return f"apply,{ns},{f_obs},{f_after},{throttle},0.0,{steer},0,0,0,20.0"


def ctl(throttle, steer=0.0):
    return {"throttle": throttle, "brake": 0.0, "steer": steer, "hand_brake": False,
            "reverse": False, "gear": 0}


def run(lines, truth):
    rows, drops = aa.read_trace(["# comment", HEADER] + lines)
    return aa.classify(rows, drops, truth)


class Classify(unittest.TestCase):
    def test_held_in_its_tick_is_in_time_and_the_last_clean_send_counts(self):
        lines = [tick(0, 10), apply(1, 10, 10, 0.1), apply(2, 10, 10, 0.2), tick(3, 11)]
        labels, counts = run(lines, [(11, ctl(0.2))])
        self.assertEqual(labels, {11: "in_time"})
        self.assertEqual(counts["in_time"], 1)

    def test_the_previous_control_held_is_late(self):
        lines = [tick(0, 10), apply(1, 10, 10, 0.1), tick(2, 11), apply(3, 11, 11, 0.3),
                 tick(4, 12)]
        labels, _ = run(lines, [(11, ctl(0.1)), (12, ctl(0.1))])
        self.assertEqual(labels, {11: "in_time", 12: "late"})

    def test_a_repeated_value_is_ambiguous_and_an_unknown_one_other(self):
        lines = [tick(0, 10), apply(1, 10, 10, 0.1), tick(2, 11), apply(3, 11, 11, 0.1),
                 tick(4, 12), apply(5, 12, 12, 0.5), tick(6, 13)]
        labels, _ = run(lines, [(12, ctl(0.1)), (13, ctl(0.9))])
        self.assertEqual(labels, {12: "ambiguous", 13: "other"})

    def test_a_call_a_tick_finished_during_is_raced_not_a_clean_send(self):
        lines = [tick(0, 10), apply(1, 10, 11, 0.4), tick(2, 11)]
        labels, counts = run(lines, [(11, ctl(0.0))])
        self.assertEqual(labels, {11: "no_send"})
        self.assertEqual(counts["raced"], 1)

    def test_dropped_rows_leave_their_frames_unclassified(self):
        lines = [tick(0, 10), apply(1, 10, 10, 0.1), tick(2, 11),
                 "[acb_bridge log] 3 line(s) dropped: the log file blocked", tick(4, 12)]
        labels, counts = run(lines, [(11, ctl(0.1)), (12, ctl(0.1))])
        self.assertEqual(labels, {11: "in_time", 12: "unclassified"})
        self.assertEqual(counts["dropped_rows"], 3)

    def test_values_match_within_float32_not_beyond(self):
        f32 = 0.30000001192092896              # 0.3 as CARLA holds it
        lines = [tick(0, 10), apply(1, 10, 10, f32), tick(2, 11)]
        self.assertEqual(run(lines, [(11, ctl(0.3))])[0], {11: "in_time"})
        self.assertEqual(run(lines, [(11, ctl(0.3001))])[0], {11: "other"})

    def test_the_gear_carla_reports_is_not_matched(self):
        # automatic transmission: sent 0, CARLA holds the gear it is in
        lines = [tick(0, 10), apply(1, 10, 10, 0.1), tick(2, 11)]
        held = dict(ctl(0.1), gear=1)
        self.assertEqual(run(lines, [(11, held)])[0], {11: "in_time"})

    def test_velocity_rows_are_counted_not_matched(self):
        lines = [tick(0, 10), "velocity,1,10,10,,,,,,,5.0", tick(2, 11)]
        labels, counts = run(lines, [(11, ctl(0.0))])
        self.assertEqual(labels, {11: "no_send"})
        self.assertEqual(counts["velocity_rows"], 1)


def timed(lines, truth, ticks):
    rows, drops = aa.read_trace(["# comment", HEADER] + lines)
    labels, counts = aa.classify(rows, drops, truth)
    return aa.timed(rows, labels, ticks)


class Timed(unittest.TestCase):
    # step 3: the world server's tick start (CLOCK_MONOTONIC) splits `late`
    LATE = [tick(0, 10), apply(1, 10, 10, 0.1), tick(2, 11), apply(30, 11, 11, 0.3),
            tick(40, 12)]
    TRUTH = [(11, ctl(0.1)), (12, ctl(0.1))]

    def test_a_late_send_after_the_tick_began_is_after_tick(self):
        labels, offsets = timed(self.LATE, self.TRUTH, {11: (2, 3), 12: (25, 28)})
        self.assertEqual(labels, {11: "in_time", 12: "after_tick"})
        self.assertEqual(offsets["after_tick"], [5])

    def test_a_late_send_before_the_tick_began_stays_late(self):
        labels, offsets = timed(self.LATE, self.TRUTH, {11: (2, 3), 12: (31, 33)})
        self.assertEqual(labels, {11: "in_time", 12: "late"})
        self.assertEqual(offsets["late"], [-1])

    def test_a_held_send_after_the_stamp_is_counted_apart(self):
        # sent after the client's stamp, held anyway: the server began the tick later
        lines = [tick(0, 10), apply(5, 10, 10, 0.1), tick(9, 11)]
        labels, offsets = timed(lines, [(11, ctl(0.1))], {11: (4, 8)})
        self.assertEqual(labels, {11: "in_time"})
        self.assertEqual(offsets["in_time_after_stamp"], [1])

    def test_an_unstamped_frame_keeps_its_label(self):
        labels, _ = timed(self.LATE, self.TRUTH, {11: (2, 3)})
        self.assertEqual(labels[12], "late")

    def test_the_tick_windows_are_summarised(self):
        w = aa.tick_windows({1: (0, 1000), 2: (0, 2000), 3: (0, 3000), 4: (0, 0)})
        self.assertEqual(w["n"], 3)
        self.assertEqual((w["min_us"], w["max_us"]), (1.0, 3.0))
        self.assertEqual(w["p50_us"], 2.0)


class BootId(unittest.TestCase):
    def test_the_trace_names_its_boot(self):
        self.assertEqual(aa.trace_boot_id(["# boot_id abc-1", HEADER]), "abc-1")
        self.assertIsNone(aa.trace_boot_id(["# comment", HEADER]))

    def test_a_comparison_across_boots_is_refused_by_name(self):
        aa.check_same_boot("abc", "abc")
        for trace, world in (("abc", "def"), (None, "abc"), ("abc", None)):
            with self.assertRaisesRegex(SystemExit, "boot"):
                aa.check_same_boot(trace, world)


if __name__ == "__main__":
    unittest.main()
