"""scripts/k12_walker_replay.py (092 K12's exit check 2): the pairing by cmd_frame and the xy
error, on a synthetic schema 3 trace and a stub model."""
import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
try:
    import numpy as np
    import torch  # noqa: F401
    sys.path.insert(0, str(HERE.parents[1] / "scensim_launch" / "scripts"))
    import gap_trace as gt
    _spec = importlib.util.spec_from_file_location(
        "k12_walker_replay", HERE.parent / "scripts" / "k12_walker_replay.py")
    rp = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(rp)
except ImportError:
    np = None


class Stub:
    """Walks north at 1 m/s, its limit high enough to reach it in one step; `go` at step 2."""

    def __init__(self):
        self.k = 0

    def step(self, obs, dt):
        self.k += 1
        return ({"speed": np.array([1.0]), "heading": np.array([np.pi / 2]),
                 "accel_limit": np.array([100.0])}, np.array([1 if self.k == 2 else 0]))


def trace(walker_y, cmd_frames):
    st = lambda x, y, vx=0.0: gt.EntityState(          # noqa: E731
        ssv2=gt.Pose6(x, y, 0, 0, 0, 0), sim_pose=gt.Pose6(x, y, 0, 0, 0, 0),
        velocity=(vx, 0.0, 0.0), angular_velocity=(0.0, 0.0, 0.0),
        velocity_source="measured")
    t = gt.Trace(episode=gt.Episode(schema=3, episode=1, start_unix=0.0, npc_motion="tracked",
                                    map="Town01", step_time=0.05))
    for n, (wy, cf) in enumerate(zip(walker_y, cmd_frames), start=1):
        w = st(10.0, wy)
        w = gt.EntityState(**{**w.__dict__, "cmd_frame": cf})
        t.frames.append(gt.Frame(frame=n, sim_time=0.05 * n, sim_frame=100 + n,
                                 sim_time_ns=10**12 + 5 * 10**7 * n,
                                 entities={"ego": st(0.0, 0.0, 8.0), "walker": w}))
    return t


@unittest.skipIf(np is None, "numpy, torch or the trace reader is not importable here")
class Replay(unittest.TestCase):
    def test_lag_one_truth_matches_the_replay_and_events_pair_by_frame(self):
        # the replay moves 0.05 m a step; the world moved the walker at k+1 by k's command
        ys = [0.0, 0.05, 0.10, 0.15, 0.20]
        r = rp.replay(trace(ys, [0, 101, 102, 103, 104]), Stub(), "walker", "ego", 10.0, 0.0,
                      events={2: "go"})
        self.assertLess(r["max_xy_error_m"], 1e-12)
        self.assertEqual(r["frames_compared"], 4)
        self.assertTrue(r["events_match"])
        self.assertEqual(r["events_replay"], {"2": "go"})

    def test_a_frame_moved_by_the_wrong_command_shows(self):
        ys = [0.0, 0.05, 0.10, 0.10, 0.20]       # frame 4 lags: moved by frame 2's state
        r = rp.replay(trace(ys, [0, 101, 102, 103, 104]), Stub(), "walker", "ego", 10.0, 0.0,
                      events={3: "go"})
        self.assertAlmostEqual(r["max_xy_error_m"], 0.05, places=9)
        self.assertEqual(r["at_frame"], 4)
        self.assertFalse(r["events_match"])


if __name__ == "__main__":
    unittest.main()
