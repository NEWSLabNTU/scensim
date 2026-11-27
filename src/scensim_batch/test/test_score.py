"""092 K11f: the batch's score in the batch (scensim_batch.score). The signed distance against
gap_geometry's, the running minimum against closest() on the truth export of the same steps,
and search_run scoring without the export, its --truth audit and its fail-stop."""
import importlib.util
import json
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "scensim_sampler"))
sys.path.insert(0, str(HERE.parents[1] / "sim_vehicle_ecu"))
sys.path.insert(0, str(HERE.parents[1] / "scensim"))
sys.path.insert(0, str(HERE.parents[1] / "scensim_launch" / "scripts"))
sys.path.insert(0, str(HERE))

try:
    import torch
    import gap_geometry as gg
    from scensim import truth as T
    from scensim_batch.truth import TruthRecorder
    from test_core import DT, StraightWorld
except ImportError:
    torch = None
if torch is not None:   # not in the guard: a missing scensim_batch.score is a failure
    from scensim_batch import score as S

CASE = HERE.parents[1] / "scensim_sampler" / "examples" / "cases" / "cs1_walker_gap_acceptance.xosc"


def _search_run():
    spec = importlib.util.spec_from_file_location("search_run",
                                                  HERE.parent / "scripts" / "search_run.py")
    sr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sr)
    return sr


def _ref(b):
    cx, cy, yaw, hl, hw = b
    return gg.OrientedBox(cx, cy, yaw, hl, hw)


class FakeRun:
    """What TruthRecorder and ClosestGap read of a BatchRun: the compiled entities, records and
    seeds, the ego's index and the clock. Poses are set per step by the test."""

    def __init__(self, n, ents, ego=0):
        self.ego = ego
        self.c = SimpleNamespace(
            n=n, entities=[SimpleNamespace(name=name, kind=kind, cx=cx, cy=cy, length=ln,
                                           width=wd, height=1.5)
                           for name, kind, cx, cy, ln, wd in ents],
            records=[{"id": f"{k:064x}"} for k in range(n)], seeds=list(range(n)),
            scenario="fake.xosc")
        self.ctx = SimpleNamespace(t=torch.zeros(n, dtype=torch.float64))

    def obs(self, x, y, yaw, outcome=None):
        n = self.c.n
        ob = {"x": torch.as_tensor(x, dtype=torch.float64).reshape(n, -1),
              "y": torch.as_tensor(y, dtype=torch.float64).reshape(n, -1),
              "yaw": torch.as_tensor(yaw, dtype=torch.float64).reshape(n, -1),
              "ego": {"yaw_rate": torch.zeros(n, dtype=torch.float64)}}
        ob["v"] = torch.zeros_like(ob["x"])
        if outcome is not None:
            ob["outcome"] = torch.as_tensor(outcome, dtype=torch.int8)
        return ob


ENTS = [("ego", "vehicle", 1.4, 0.0, 4.6, 1.9), ("van", "vehicle", 1.0, 0.0, 5.0, 2.0),
        ("walker", "pedestrian", 0.0, 0.0, 0.5, 0.5)]


def _both(run, steps):
    """Drive TruthRecorder and ClosestGap through the same steps: ("begin", obs, mask) or
    ("record", obs, t). Returns (slot_outcomes on the export, ClosestGap's rows)."""
    rec = TruthRecorder(run, step_time=DT, start_unix=0.0)
    cg = S.ClosestGap(run)
    for kind, ob, extra in steps:
        if kind == "begin":
            rec.begin(ob, extra)
            cg.begin(ob, extra)
        else:
            run.ctx.t = torch.as_tensor(extra, dtype=torch.float64)
            rec.record(ob)
            cg.record(ob)
    with tempfile.TemporaryDirectory() as d:
        rec.write(d)
        want = T.slot_outcomes(d)
    return want, cg.rows()


@unittest.skipIf(torch is None, "no torch or no sim_vehicle_ecu")
class SignedDistance(unittest.TestCase):
    def _check(self, pairs, bar=1e-12):
        a = torch.tensor([p[0] for p in pairs], dtype=torch.float64)
        b = torch.tensor([p[1] for p in pairs], dtype=torch.float64)
        got = S.signed_distance(a, b)
        self.assertEqual(got.dtype, torch.float64)
        worst = 0.0
        for k, (pa, pb) in enumerate(pairs):
            want = gg.signed_distance(_ref(pa), _ref(pb))
            d = abs(float(got[k]) - want)
            worst = max(worst, d)
            self.assertLessEqual(d, bar, (pa, pb, float(got[k]), want))
        return worst

    def test_random_pairs_equal_gap_geometry(self):
        rng = random.Random(20261127)
        pairs = []
        for _ in range(10_000):
            a = (rng.uniform(-6, 6), rng.uniform(-6, 6), rng.uniform(-math.pi, math.pi),
                 rng.uniform(0.2, 3.0), rng.uniform(0.2, 1.5))
            b = (rng.uniform(-6, 6), rng.uniform(-6, 6), rng.uniform(-math.pi, math.pi),
                 rng.uniform(0.2, 3.0), rng.uniform(0.2, 1.5))
            pairs.append((a, b))
        self._check(pairs)
        kinds = [gg.signed_distance(_ref(a), _ref(b)) for a, b in pairs]
        self.assertGreater(sum(1 for d in kinds if d > 0), 1000)      # both branches exercised
        self.assertGreater(sum(1 for d in kinds if d < 0), 1000)

    def test_touching_corner_to_corner_and_the_tolerance(self):
        q = math.pi / 4
        r2 = math.sqrt(2.0)
        pairs = [
            ((0, 0, 0, 2, 1), (4, 0, 0, 2, 1)),               # edge to edge, touching: 0
            ((0, 0, 0, 2, 1), (4, 2, 0, 2, 1)),               # corner to corner, touching
            ((0, 0, 0, 2, 1), (5, 3, 0, 2, 1)),               # corner to corner, apart: hypot
            ((0, 0, q, 1, 1), (2 * r2 + 0.5, 0, q, 1, 1)),    # rotated, vertex to vertex
            ((0, 0, 0, 1, 1), (1 + r2 + 0.25, 0, q, 1, 1)),   # vertex onto an edge
            ((0, 0, 0, 2, 1), (4 - 5e-10, 0, 0, 2, 1)),       # inside the tolerance: 0
            ((0, 0, 0, 2, 1), (4 - 2e-9, 0, 0, 2, 1)),        # past it: minus the depth
            ((0, 0, 0, 2, 1), (0, 0, 0, 2, 1)),               # coincident
            ((0, 0, 0.3, 2, 1), (0.5, 0.2, -1.1, 0.25, 0.25)),  # one inside the other
        ]
        self._check(pairs)
        a = torch.tensor([p[0] for p in pairs], dtype=torch.float64)
        b = torch.tensor([p[1] for p in pairs], dtype=torch.float64)
        got = S.signed_distance(a, b).tolist()
        self.assertEqual(got[0], 0.0)
        self.assertAlmostEqual(got[2], math.hypot(1.0, 1.0), places=12)
        self.assertEqual(got[5], 0.0)
        self.assertAlmostEqual(got[6], -2e-9, delta=1e-15)

    def test_broadcasts_over_slots_and_entities(self):
        a = torch.tensor([[0, 0, 0, 2, 1]], dtype=torch.float64).expand(3, 2, 5)
        b = torch.tensor([[[4, 0, 0, 2, 1], [6, 0, 0, 2, 1]]] * 3, dtype=torch.float64)
        self.assertEqual(tuple(S.signed_distance(a, b).shape), (3, 2))


@unittest.skipIf(torch is None, "no torch or no sim_vehicle_ecu")
class Tracking(unittest.TestCase):
    def assertSame(self, want, got, bar=1e-12):
        self.assertEqual([w["record"] for w in want], [g["record"] for g in got])
        for w, g in zip(want, got):
            wo, go = w["outcome"], g["outcome"]
            self.assertEqual(set(wo), set(go), (wo, go))
            for key in wo:
                if key == "score":
                    self.assertLessEqual(abs(wo[key] - go[key]), bar, (wo, go))
                elif key == "closest":
                    self.assertEqual(wo[key]["entity"], go[key]["entity"], (wo, go))
                    self.assertEqual(wo[key]["frame"], go[key]["frame"], (wo, go))
                    self.assertEqual(wo[key]["sim_time"], go[key]["sim_time"], (wo, go))
                else:
                    self.assertEqual(wo[key], go[key], (key, wo, go))

    def _walker_run(self, walker_x, outcomes=None):
        """One slot: the ego still at the origin (its box from -0.9 to 3.7 m), the van far
        off, the walker at walker_x[f] on the ego's axis."""
        run = FakeRun(1, ENTS)
        steps = []
        for f, wx in enumerate(walker_x):
            o = None if outcomes is None else [outcomes[f]]
            ob = run.obs([[0.0, 50.0, wx]], [[0.0, 0.0, 0.0]], [[0.0, 0.0, 0.0]], o)
            steps.append(("begin", ob, None) if f == 0 else ("record", ob, [f * DT]))
        return run, steps

    def test_a_tie_between_frames_keeps_the_first(self):
        run, steps = self._walker_run([9.0, 6.0, 8.0, 6.0, 7.0])
        want, got = _both(run, steps)
        self.assertSame(want, got)
        self.assertEqual(got[0]["outcome"]["closest"]["frame"], 1)
        self.assertAlmostEqual(got[0]["outcome"]["score"], 6.0 - 0.25 - 3.7, places=12)

    def test_a_tie_between_entities_keeps_the_first_in_order(self):
        run = FakeRun(1, ENTS)
        # the van's box from 6.0 m and the walker's from 6.0 m: the same gap, the van first
        ob = run.obs([[0.0, 7.5, 6.25]], [[0.0, 0.0, 0.0]], [[0.0, 0.0, 0.0]])
        want, got = _both(run, [("begin", ob, None)])
        self.assertSame(want, got)
        self.assertEqual(got[0]["outcome"]["closest"]["entity"], "van")

    def test_an_episode_closed_mid_run_ignores_later_frames(self):
        run, steps = self._walker_run([9.0, 7.0, 8.0, 3.0, 2.0], outcomes=[0, 0, 1, 0, 0])
        want, got = _both(run, steps)
        self.assertSame(want, got)
        o = got[0]["outcome"]
        self.assertEqual(o["closest"]["frame"], 1)
        self.assertFalse(o["contact"])

    def test_a_slot_reopened_by_begin_starts_a_new_episode(self):
        run = FakeRun(2, ENTS)
        steps = []
        xs = [[9.0, 8.0], [3.0, 7.5], [6.0, 7.0], [8.0, 3.5], [5.0, 9.0]]
        for f, (w0, w1) in enumerate(xs):
            ob = run.obs([[0.0, 50.0, w0], [0.0, 50.0, w1]], [[0.0] * 3] * 2, [[0.0] * 3] * 2,
                         [0, 0])
            if f == 0:
                steps.append(("begin", ob, None))
            elif f == 2:
                steps.append(("begin", ob, [True, False]))   # slot 0 only, at frame 2
            else:
                steps.append(("record", ob, [f * DT, f * DT]))
        want, got = _both(run, steps)
        self.assertSame(want, got)
        runs = [g["outcome"]["run"] for g in got]
        self.assertEqual(runs, ["slot_0_ep0", "slot_0_ep1", "slot_1_ep0"])
        ep0, ep1 = got[0]["outcome"], got[1]["outcome"]
        self.assertEqual(ep0["closest"]["frame"], 1)           # 3.0 m, frames 0 and 1 only
        self.assertTrue(ep0["contact"])
        self.assertEqual(ep1["closest"]["frame"], 2)           # 5.0 m at its frame 2
        self.assertFalse(ep1["contact"])

    def test_random_trajectories_agree_with_closest_on_the_export(self):
        rng = random.Random(7)
        run = FakeRun(8, ENTS)
        n, steps = 8, []
        for f in range(60):
            x = [[rng.uniform(-2, 2), rng.uniform(-3, 9), rng.uniform(-3, 9)] for _ in range(n)]
            y = [[rng.uniform(-1, 1), rng.uniform(-3, 3), rng.uniform(-3, 3)] for _ in range(n)]
            h = [[rng.uniform(-math.pi, math.pi) for _ in range(3)] for _ in range(n)]
            out = [1 if rng.random() < 0.03 else 0 for _ in range(n)]
            if f == 0:
                steps.append(("begin", run.obs(x, y, h, [0] * n), None))
            elif f % 17 == 0:
                steps.append(("begin", run.obs(x, y, h, [0] * n),
                              [rng.random() < 0.5 for _ in range(n)]))
            else:
                steps.append(("record", run.obs(x, y, h, out), [f * DT] * n))
        want, got = _both(run, steps)
        self.assertGreater(len(got), n)                         # some slots reopened
        self.assertTrue(any(g["outcome"]["contact"] for g in got))
        self.assertSame(want, got)

    def test_the_threshold_and_a_missing_record_id(self):
        run, steps = self._walker_run([9.0, 6.0])
        cg = S.ClosestGap(run)
        cg.begin(steps[0][1])
        cg.record(steps[1][1])
        self.assertTrue(cg.rows(threshold=2.5)[0]["outcome"]["failed"])
        self.assertFalse(cg.rows()[0]["outcome"]["failed"])
        run.c.records = [{}]
        with self.assertRaisesRegex(ValueError, "no record id"):
            cg.rows()


@unittest.skipIf(torch is None, "no torch or no sim_vehicle_ecu")
class Runner(unittest.TestCase):
    RECS = [{"id": f"{i:064x}", "values": {"ttc_entry": t},
             "scenario": {"path": "cases/cs1.xosc", "sha256": "0" * 64},
             "seeds": {"scenario": 1 + i, "pilots": {"walker": 2 + i}}}
            for i, t in enumerate((0.5, 1.5, 3.0, 6.0))]

    def test_without_the_export_the_outcomes_equal_the_exports(self):
        sr = _search_run()
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            sr.run(self.RECS, CASE, StraightWorld(), Path(a), steps=240, step_time=DT)
            sr.run(self.RECS, CASE, StraightWorld(), Path(b), steps=240, step_time=DT,
                   truth=True)
            self.assertFalse(Path(a, "truth").exists())
            self.assertTrue(Path(b, "truth").is_dir())
            ra = [json.loads(x) for x in Path(a, "outcomes.jsonl").read_text().splitlines()]
            exp = T.slot_outcomes(Path(b, "truth"))
        self.assertEqual(len(ra), len(self.RECS))
        Tracking.assertSame(self, exp, ra, bar=1e-9)

    def test_the_sloped_score_in_the_batch_equals_the_saved_files(self):
        sr = _search_run()
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            sr.run(self.RECS, CASE, StraightWorld(), Path(a), steps=240, step_time=DT,
                   margin_k=1.0)
            sr.run(self.RECS, CASE, StraightWorld(), Path(b), steps=240, step_time=DT,
                   margin_k=1.0, truth=True)
            ra = [json.loads(x) for x in Path(a, "outcomes.jsonl").read_text().splitlines()]
            exp = T.slot_outcomes(Path(b, "truth"), margin_k=1.0)
        Tracking.assertSame(self, exp, ra, bar=1e-9)
        for r in ra:
            o = r["outcome"]
            self.assertEqual(o["failed"], o["closest_gap"] <= 0)
        self.assertTrue(any(r["outcome"]["decision_margin"] is not None for r in ra))

    def test_a_disagreement_names_the_slot_episode_values_and_bar(self):
        sr = _search_run()
        row = {"record": "r", "outcome": {"score": 0.5, "failed": False, "contact": False,
                                          "error": False, "run": "slot_3_ep1",
                                          "closest": {"entity": "walker", "frame": 7,
                                                      "sim_time": 0.35}}}
        off = json.loads(json.dumps(row))
        off["outcome"]["score"] = 0.5 + 2e-6
        sr.compare_outcomes([row], [json.loads(json.dumps(row))])     # equal: no error
        with self.assertRaises(SystemExit) as e:
            sr.compare_outcomes([off], [row])
        msg = str(e.exception)
        for part in ("slot 3", "episode 1", "0.500002", "0.5", "1e-09"):
            self.assertIn(part, msg)
        other = json.loads(json.dumps(row))
        other["outcome"]["closest"]["frame"] = 8
        with self.assertRaisesRegex(SystemExit, "slot 3.*episode 1.*frame"):
            sr.compare_outcomes([other], [row])


if __name__ == "__main__":
    unittest.main()
