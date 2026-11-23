"""scripts/pose_stalls.py (issue 127's detector): a stall-then-double-step is found where it is,
and nothing else is."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import gap_trace as gt  # noqa: E402
import pose_stalls as ps  # noqa: E402


def header(name, offset=(0.0, 0.0, 0.0)):
    return gt.EntityHeader(frame=1, name=name, kind="vehicle",
                           declared=gt.DeclaredBox((0.0, 0.0, 0.0), (4.0, 2.0, 1.5)),
                           origin_offset=gt.OriginOffset(*offset), sim_id=1, asset="x",
                           asset_box=None)


def trace(world_x, ssv2_x=None, flags=None, frames=None, offset=(0.0, 0.0, 0.0)):
    """One NPC moving along x: its world (body) and SSv2 x per frame; an ego that never moves."""
    ssv2_x = ssv2_x or [0.5 * k for k in range(len(world_x))]
    t = gt.Trace(episode=gt.Episode(schema=3, episode=1, start_unix=0.0,
                                    npc_motion="kinematic", map="Town01", step_time=0.05))
    t.headers = [header("npc", offset), header("ego")]
    pose = lambda x: gt.Pose6(x, 0.0, 0.0, 0.0, 0.0, 0.0)   # noqa: E731
    for k, (w, s) in enumerate(zip(world_x, ssv2_x)):
        st = gt.EntityState(ssv2=pose(s), sim_pose=None if w is None else pose(w),
                            velocity=None if w is None else (0.0, 0.0, 0.0),
                            flags=tuple((flags or {}).get(k, ())))
        t.frames.append(gt.Frame(frame=(frames or list(range(1, len(world_x) + 1)))[k],
                                 sim_time=0.05 * k,
                                 entities={"npc": st, "ego": gt.EntityState(
                                     ssv2=pose(0.0), sim_pose=pose(0.0),
                                     velocity=(0.0, 0.0, 0.0))}))
    return t


class Stalls(unittest.TestCase):
    def test_a_stall_then_a_double_step_is_found_at_its_frame(self):
        # SSv2 0.5 m a frame; the world holds at frame 3 and doubles to frame 4
        s = ps.stalls(trace([0.0, 0.5, 1.0, 1.0, 2.0, 2.5]), skip=("ego",))
        self.assertEqual([(x["entity"], x["frame"]) for x in s], [("npc", 4)])
        self.assertAlmostEqual(s[0]["world_step_out"], 1.0)

    def test_a_body_that_follows_ssv2_has_none(self):
        t = trace([0.5 * k for k in range(8)])
        self.assertEqual(ps.stalls(t, skip=("ego",)), [])
        self.assertEqual(ps.tracking(t, skip=("ego",))["max"], 0.0)

    def test_a_stop_ssv2_made_is_not_a_stall(self):
        # SSv2 itself stopped a frame: its step under MOVING_M
        x = [0.0, 0.5, 1.0, 1.0, 1.5, 2.0]
        self.assertEqual(ps.stalls(trace(x, ssv2_x=list(x)), skip=("ego",)), [])

    def test_a_stall_the_world_never_caught_up_on_is_not_counted(self):
        # held, then one ordinary step: a lag of its own, not issue 127's shape
        self.assertEqual(ps.stalls(trace([0.0, 0.5, 1.0, 1.0, 1.5, 2.0]), skip=("ego",)), [])

    def test_missing_frames_poses_and_spawns_are_skipped(self):
        x = [0.0, 0.5, 1.0, 1.0, 2.0, 2.5]
        self.assertEqual(ps.stalls(trace(x, frames=[1, 2, 3, 5, 6, 7]), skip=("ego",)), [])
        self.assertEqual(ps.stalls(trace([0.0, 0.5, None, 1.0, 2.0, 2.5]), skip=("ego",)), [])
        self.assertEqual(ps.stalls(trace(x, flags={3: ("spawn",)}), skip=("ego",)), [])

    def test_the_tracking_error_is_world_against_ssv2(self):
        tr = ps.tracking(trace([0.0, 0.6, 1.0, 1.9]), skip=("ego",))
        self.assertEqual(tr["entity_frames"], 4)
        self.assertAlmostEqual(tr["max"], 0.4)

    def test_the_world_pose_is_the_entitys_not_the_bodys(self):
        # a body 1.387 m ahead of its entity, following SSv2 exactly: no error (issue 130)
        x = [0.5 * k for k in range(4)]
        t = trace([v + 1.387 for v in x], ssv2_x=x, offset=(1.387, 0.0, 0.0))
        self.assertLess(ps.tracking(t, skip=("ego",))["max"], 1e-9)
        self.assertEqual(ps.stalls(t, skip=("ego",)), [])

    def test_an_entity_before_its_header_has_no_world_pose(self):
        t = trace([0.0, 0.5])
        t.headers = [header("ego")]
        self.assertEqual([r[1] for r in ps.series(t, skip=("ego",))["npc"]], [None, None])

    def test_the_ego_is_left_out(self):
        self.assertNotIn("ego", ps.series(trace([0.0, 0.5]), skip=("ego",)))


if __name__ == "__main__":
    unittest.main()
