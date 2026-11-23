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


def header(name, frame=1, offset=(0.0, 0.0, 0.0)):
    return gt.EntityHeader(frame=frame, name=name, kind="vehicle",
                           declared=gt.DeclaredBox((0.0, 0.0, 0.0), (4.0, 2.0, 1.5)),
                           origin_offset=gt.OriginOffset(*offset), sim_id=1, asset="x",
                           asset_box=None)


def trace(walker_y, cmd_frames, ego_offset=(0.0, 0.0, 0.0), ego_header_frame=1):
    st = lambda x, y, vx=0.0: gt.EntityState(          # noqa: E731
        ssv2=gt.Pose6(x, y, 0, 0, 0, 0), sim_pose=gt.Pose6(x, y, 0, 0, 0, 0),
        velocity=(vx, 0.0, 0.0), angular_velocity=(0.0, 0.0, 0.0),
        velocity_source="measured")
    t = gt.Trace(episode=gt.Episode(schema=3, episode=1, start_unix=0.0, npc_motion="tracked",
                                    map="Town01", step_time=0.05))
    t.headers = [header("ego", ego_header_frame, ego_offset), header("walker")]
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


    def test_the_ego_is_read_as_its_entity_as_the_runner_reads_it(self):
        """Issue 130: the truth carries the body; the replay takes the origin_offset back off
        through the runner's own conversion (seats.entity_pose, entity_velocity)."""
        from scensim.behaviour import seats
        t = trace([0.0] * 3, [0, 101, 102], ego_offset=(1.387, 0.0, 0.0))
        body = t.frames[1].entities["ego"]
        e = rp.ego_inputs(t, "ego")[1][3]
        x, y, _ = seats.entity_pose(body.sim_pose.x, body.sim_pose.y, body.sim_pose.yaw,
                                    (1.387, 0.0, 0.0))
        self.assertEqual((e[0], e[1]), (x, y))
        self.assertAlmostEqual(e[0], -1.387, places=12)   # body at 0 facing +x: origin behind
        self.assertEqual((e[2], e[3]), (8.0, 0.0))          # no yaw rate: the body's velocity

    def test_the_origin_velocity_takes_off_the_yaw_rate_times_the_offset(self):
        t = trace([0.0] * 2, [0, 101], ego_offset=(1.387, 0.0, 0.0))
        f = t.frames[1]
        ego = f.entities["ego"]
        f.entities["ego"] = gt.EntityState(**{**ego.__dict__, "angular_velocity": (0.0, 0.0, 0.5)})
        x, y, yaw, vx, vy = rp.entity_states(t, "ego")[f.frame]
        self.assertAlmostEqual(vx, 8.0, places=12)
        self.assertAlmostEqual(vy, -0.5 * 1.387, places=12)   # v - w x r, r = +1.387 x

    def test_a_frame_before_the_entitys_header_is_skipped_as_the_runner_skips_it(self):
        t = trace([0.0, 0.05, 0.10], [0, 101, 102], ego_header_frame=2)
        self.assertIsNone(rp.ego_inputs(t, "ego")[0][3])
        self.assertIsNotNone(rp.ego_inputs(t, "ego")[1][3])


if __name__ == "__main__":
    unittest.main()
