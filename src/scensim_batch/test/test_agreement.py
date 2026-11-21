"""K2.4's comparison (scensim_batch.agreement) on records made here: frame pairing by S, the
command hold by time, the storyboard log's steps, the errors and trigger offsets."""
import json
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from scensim_batch import agreement as A   # noqa: E402


@dataclass
class P6:
    x: float
    y: float
    yaw: float


@dataclass
class St:
    ssv2: object
    sim_pose: object


@dataclass
class Fr:
    frame: int
    sim_time_ns: int
    entities: dict


@dataclass
class Tr:
    frames: list


def trace(first=10, n=8, S=3, dt_ns=50_000_000):
    """Frames first..first+n-1; the ego at x = k (k scenario steps), the npc at 10 + 2k in SSv2
    and its body 0.1 m off; before S both still."""
    fr = []
    for i in range(n):
        k = max(i - S, 0)
        fr.append(Fr(first + i, 1_000_000_000_000 + (i + 1) * dt_ns,
                     {"ego": St(P6(-9, 0, 0), P6(k, 0, 0)),
                      "npc": St(P6(10 + 2 * k, 0, 0), P6(10.1 + 2 * k, 0, 0))}))
    return Tr(fr)


class AgreementTest(unittest.TestCase):
    def test_frames_pair_on_scenario_time(self):
        t = trace()
        s = A.seats_poses(t, 3, 4, ["ego", "npc"], pose={"ego": "sim", "npc": "ssv2"})
        self.assertEqual([p[0] for p in s["ego"]], [0, 1, 2, 3])
        self.assertEqual([p[0] for p in s["npc"]], [10, 12, 14, 16])
        self.assertEqual(A.seats_poses(t, 6, 3, ["ego"], "sim")["ego"][2], None)  # past the end

    def test_hold_is_paired_by_time(self):
        t = trace(first=10, S=3)
        cmd0 = {"k": 0, "frame": 77, "clock_ns": t.frames[5].sim_time_ns}   # world frame unrelated
        self.assertEqual(A.hold_steps(t, 3, cmd0), 2)
        self.assertIsNone(A.hold_steps(t, 3, {"clock_ns": 1}))

    def test_replay_log_after_its_last_reset(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.jsonl"
            p.write_text("\n".join(json.dumps(o) for o in [
                {"frame": 1, "k": 0, "clock_ns": 1}, {"reset": True},
                {"frame": 5, "k": None, "clock_ns": 5}, {"frame": 6, "k": 0, "clock_ns": 6}]))
            rows = A.replay_log(p)
            self.assertEqual(len(rows), 2)
            self.assertEqual(A.first_command(rows)["frame"], 6)

    def test_context_steps(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.jsonl"
            p.write_text("\n".join(json.dumps(o) for o in [
                {"ev": "state", "sim": None, "element": "s/a", "from": None, "to": "standbyState"},
                {"ev": "state", "sim": 0.05, "element": "s/a", "from": "standbyState",
                 "to": "runningState"},
                {"ev": "state", "sim": 1.0, "element": "s/a", "from": "runningState",
                 "to": "completeState"},
                {"ev": "state", "sim": 2.0, "element": "s/a", "from": "completeState",
                 "to": "runningState"}]))
            self.assertEqual(A.context_steps(p, 0.05),
                             {"s/a": {"runningState": 1, "completeState": 20}})

    def test_compare(self):
        seats = {"poses": {"ego": [(0, 0, 0), (1, 0, 0), None], "npc": [(10, 0, 0)]},
                 "steps": {"s/a": {"runningState": 1, "completeState": 20}}, "outcome": "success"}
        batch = {"poses": {"ego": [(0, 0, 0), (1, 0.3, 0.1), (2, 0, 0)], "npc": [(10, 0.4, 0)]},
                 "steps": {"s/a": {"runningState": 1, "completeState": 21}, "s/b": {}},
                 "outcome": "success"}
        t = A.compare(seats, batch)
        self.assertTrue(t["outcome"]["agree"])
        ego = t["trajectory"]["ego"]
        self.assertEqual((ego["frames"], ego["missing"]), (2, 1))
        self.assertAlmostEqual(ego["max_m"], 0.3)
        self.assertAlmostEqual(ego["max_yaw_rad"], 0.1)
        self.assertEqual(t["triggers"]["s/a"]["completeState"], (20, 21, 1))
        self.assertEqual(t["triggers"]["s/b"]["runningState"], (None, None, None))
        self.assertEqual(t["trigger_offsets"], [0, 1])


if __name__ == "__main__":
    unittest.main()
