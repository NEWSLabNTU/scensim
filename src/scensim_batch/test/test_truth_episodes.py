"""Issue 199: TruthRecorder gives a slot reopened by `begin` after its episode ended by outcome
its own episode number, so the export keeps both episodes."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "scensim_launch" / "scripts"))

try:
    import torch
    import gap_trace
    from scensim_batch.truth import TruthRecorder
except ImportError:
    torch = None


def _run(n):
    ents = [SimpleNamespace(name="ego", kind="vehicle", cx=1.4, cy=0.0, length=4.6, width=1.9,
                            height=1.5),
            SimpleNamespace(name="walker", kind="pedestrian", cx=0.0, cy=0.0, length=0.5,
                            width=0.5, height=1.8)]
    c = SimpleNamespace(n=n, entities=ents, records=[{"id": f"{k:064x}"} for k in range(n)],
                        seeds=list(range(n)), scenario="fake.xosc")
    return SimpleNamespace(c=c, ego=0, ctx=SimpleNamespace(t=torch.zeros(n, dtype=torch.float64)))


def _obs(n, wx, outcome):
    x = torch.tensor([[0.0, wx]] * n, dtype=torch.float64)
    z = torch.zeros_like(x)
    return {"x": x, "y": z, "yaw": z, "v": z,
            "ego": {"yaw_rate": torch.zeros(n, dtype=torch.float64)},
            "outcome": torch.tensor(outcome, dtype=torch.int8)}


@unittest.skipIf(torch is None, "no torch")
class Reopened(unittest.TestCase):
    def test_a_slot_ended_by_its_outcome_and_reopened_keeps_both_episodes(self):
        run = _run(2)
        rec = TruthRecorder(run, step_time=0.05, start_unix=0.0)
        rec.begin(_obs(2, 9.0, [0, 0]))
        for f, (wx, out) in enumerate([(8.0, [0, 0]), (7.0, [1, 0])], 1):   # slot 0 ends
            run.ctx.t = torch.full((2,), f * 0.05, dtype=torch.float64)
            rec.record(_obs(2, wx, out))
        rec.begin(_obs(2, 6.0, [0, 0]), [True, False])                       # slot 0 again
        for f, wx in enumerate([5.0, 4.0, 3.5], 3):
            run.ctx.t = torch.full((2,), f * 0.05, dtype=torch.float64)
            rec.record(_obs(2, wx, [0, 0]))
        with tempfile.TemporaryDirectory() as d:
            dirs = sorted(x.name for x in rec.write(d))
            self.assertEqual(dirs, ["slot_0_ep0", "slot_0_ep1", "slot_1_ep0"])
            frames = {}
            for name in dirs:
                tr = gap_trace.load_trace(Path(d, name, "truth.jsonl"))
                self.assertTrue(tr.end.complete, name)
                frames[name] = [f.entities["walker"].sim_pose.x for f in tr.frames]
        self.assertEqual(frames["slot_0_ep0"], [9.0, 8.0, 7.0])
        self.assertEqual(frames["slot_0_ep1"], [6.0, 5.0, 4.0, 3.5])
        self.assertEqual(frames["slot_1_ep0"], [9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.5])


if __name__ == "__main__":
    unittest.main()
