"""092 K11c: the CPU point-mass ego, aeb_ttc and the interim search runner, on CS1 in a straight
world (test_core's)."""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "scensim_sampler"))
sys.path.insert(0, str(HERE.parents[1] / "sim_vehicle_ecu"))
sys.path.insert(0, str(HERE.parents[1] / "scensim"))
sys.path.insert(0, str(HERE.parents[1] / "scensim_launch" / "scripts"))
sys.path.insert(0, str(HERE))

try:
    import numpy as np
    import torch
    from sim_vehicle_ecu import batch as ecu_batch
    from test_core import DT, StraightWorld
    from scensim_batch import pointmass as P
except ImportError:
    torch = None

CASE = HERE.parents[1] / "scensim_sampler" / "examples" / "cases" / "cs1_walker_gap_acceptance.xosc"


def box(x, y=0.0, yaw=0.0, cx=0.0, length=4.0, width=2.0):
    return tuple(np.array([float(v)]) for v in (x, y, yaw, cx, length, width))


@unittest.skipIf(torch is None, "no torch or no sim_vehicle_ecu")
class Ttc(unittest.TestCase):
    def test_a_walker_ahead_in_the_corridor(self):
        # ego front at 2 m; the walker turned across, its box from 9.75 m: 7.75 m at 5 m/s
        t = P.ttc(box(0.0), box(10.0, 0.5, math.pi / 2, length=0.4, width=0.5), np.array([5.0]))
        self.assertAlmostEqual(float(t[0]), (10.0 - 0.25 - 2.0) / 5.0, places=9)

    def test_outside_the_corridor_behind_or_stopped_is_no_collision(self):
        v = np.array([5.0])
        self.assertEqual(float(P.ttc(box(0.0), box(10.0, 1.6, length=0.4, width=0.5), v)[0]),
                         math.inf)                                   # beside the corridor
        self.assertEqual(float(P.ttc(box(0.0), box(-10.0, length=0.4, width=0.5), v)[0]),
                         math.inf)                                   # behind
        self.assertEqual(float(P.ttc(box(0.0), box(10.0, length=0.4, width=0.5),
                                     np.array([0.0]))[0]), math.inf)  # the ego stopped

    def test_overlapping_boxes_are_zero(self):
        self.assertEqual(float(P.ttc(box(0.0), box(1.9, length=0.4, width=0.5),
                                     np.array([5.0]))[0]), 0.0)


@unittest.skipIf(torch is None, "no torch or no sim_vehicle_ecu")
class PointMassEgo(unittest.TestCase):
    def test_the_requested_acceleration_is_what_the_mass_does(self):
        from scensim_batch import core
        from scensim_batch.compile import compile_scenario
        recs = [{"values": {}, "seeds": {"scenario": 1, "pilots": {"walker": 2}}}]
        c = compile_scenario(CASE, recs, StraightWorld())
        r = core.BatchRun(c, StraightWorld(), P.PointMass(c.n),
                          ecu_batch.load_batch(P.Accel, {}, {}, [0]))
        r.reset()
        v0 = float(r.obs["v"][0, r.ego])
        for _ in range(10):
            r.step(P.commands([-2.0]), DT)
        self.assertAlmostEqual(float(r.obs["v"][0, r.ego]), v0 - 2.0 * 10 * DT, places=9)

    def test_aeb_brakes_below_its_ttc_and_stays_braking(self):
        """A walker standing in the lane 30 m ahead of an ego at 10 m/s: no braking while the
        time to collision is 1.5 s or more, then 6 m/s^2 every step until the ego stops."""
        from types import SimpleNamespace as NS
        ent = lambda length, width: NS(cx=0.0, length=length, width=width)   # noqa: E731
        run = NS(ego=0, c=NS(n=1, entities=[ent(4.0, 2.0), ent(0.4, 0.5)]))
        aeb = P.AebTtc(run, 1)
        x, v, acc = 0.0, 10.0, []
        for _ in range(200):
            t = lambda q: torch.tensor([q], dtype=torch.float64)   # noqa: E731
            obs = {"x": t([x, 30.0]), "y": t([0.0, 0.0]), "yaw": t([0.0, 0.0]),
                   "v": t([v, 0.0])}
            a = float(aeb(obs)["acceleration"][0])
            acc.append((round((30.0 - 0.2 - 2.0 - x) / v, 6) if v > 0 else None, a))
            v = max(0.0, v + a * DT)
            x += v * DT
        started = next(i for i, (_, a) in enumerate(acc) if a < 0)
        self.assertTrue(started > 0 and all(a == 0.0 and ttc >= P.TTC
                                            for ttc, a in acc[:started]))
        self.assertLess(acc[started][0], P.TTC)       # the first step below 1.5 s brakes
        moving = [a for ttc, a in acc[started:] if ttc is not None]
        self.assertTrue(all(a == -P.DECEL for a in moving))
        self.assertEqual(v, 0.0)
        self.assertLess(x, 30.0 - 0.2 - 2.0)          # stopped short: 10^2 / 12 = 8.3 m < 15 m


@unittest.skipIf(torch is None, "no torch or no sim_vehicle_ecu")
class Runner(unittest.TestCase):
    def test_a_generation_gives_one_scored_outcome_per_record(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("search_run",
                                                      HERE.parent / "scripts" / "search_run.py")
        sr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sr)
        recs = [{"id": f"{i:064x}", "values": {"ttc_entry": t},
                 "scenario": {"path": "cases/cs1.xosc", "sha256": "0" * 64},
                 "seeds": {"scenario": 1 + i, "pilots": {"walker": 2 + i}}}
                for i, t in enumerate((0.5, 3.0, 6.0))]
        with tempfile.TemporaryDirectory() as d:
            s = sr.run(recs, CASE, StraightWorld(), Path(d), steps=240, step_time=DT)
            rows = [json.loads(x) for x in Path(d, "outcomes.jsonl").read_text().splitlines()]
            named = {json.loads(p.read_text())["scenario"]
                     for p in Path(d, "truth").glob("slot_*_ep0/outcome.json")}
        self.assertEqual(named, {"cases/cs1.xosc"})       # the records' path, not the host's
        self.assertEqual(s["slots"], 3)
        self.assertEqual([r["record"] for r in rows], [r["id"] for r in recs])
        for r in rows:
            self.assertFalse(r["outcome"]["error"], r)
            self.assertTrue(math.isfinite(r["outcome"]["score"]))
            self.assertEqual(r["outcome"]["failed"], r["outcome"]["score"] <= 0)


    def test_the_sloped_score_is_recomputed_from_the_saved_files_alone(self):
        """092 K11e: with margin_k, each outcome carries closest_gap, decision_margin and the
        score; scensim.truth.sloped_score on the saved slot directory (truth, record,
        decision) gives the same, and a failure is still exactly gap <= 0."""
        import importlib.util
        from scensim import truth as T
        spec = importlib.util.spec_from_file_location("search_run",
                                                      HERE.parent / "scripts" / "search_run.py")
        sr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sr)
        recs = [{"id": f"{i:064x}", "values": {"ttc_entry": t},
                 "scenario": {"path": "cases/cs1.xosc", "sha256": "0" * 64},
                 "seeds": {"scenario": 1 + i, "pilots": {"walker": 2 + i}}}
                for i, t in enumerate((0.5, 1.5, 3.0, 6.0))]
        with tempfile.TemporaryDirectory() as d:
            sr.run(recs, CASE, StraightWorld(), Path(d), steps=240, step_time=DT, margin_k=1.0)
            rows = [json.loads(x) for x in Path(d, "outcomes.jsonl").read_text().splitlines()]
            for k, r in enumerate(rows):
                o = r["outcome"]
                again = T.sloped_score(Path(d, "truth", f"slot_{k}_ep0"), 1.0)
                self.assertEqual(again["score"], o["score"])
                self.assertEqual(again["decision_margin"], o["decision_margin"])
                self.assertEqual(o["failed"], o["closest_gap"] <= 0)
                m = o["decision_margin"]
                want = (o["closest_gap"] if o["closest_gap"] <= 0 or m is None
                        else o["closest_gap"] + max(m, 0.0))
                self.assertEqual(o["score"], want)
        self.assertTrue(any(r["outcome"]["decision_margin"] is not None for r in rows))


if __name__ == "__main__":
    unittest.main()
