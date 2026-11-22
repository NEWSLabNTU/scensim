"""Behaviour models in the batch (092 K10): CS1 with its walker as scensim.behaviour's
gap_acceptance_walker, compiled and run on test_core's kinematic stand-ins (a straight world, a
point-mass ego at its Init speed)."""
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "scensim_sampler"))
sys.path.insert(0, str(HERE.parents[1] / "sim_vehicle_ecu"))
sys.path.insert(0, str(HERE.parents[1] / "scensim"))
sys.path.insert(0, str(HERE))

try:
    import numpy as np
    import torch
    from sim_vehicle_ecu import batch as ecu_batch
    from test_core import DT, Accel, PointMass, StraightWorld, cmds
except ImportError:
    torch = None

CASE = HERE.parents[1] / "scensim_sampler" / "examples" / "cases" / "cs1_walker_gap_acceptance.xosc"


def records(n, **values):
    return [{"values": dict(values), "seeds": {"scenario": 100 + i, "pilots": {"walker": 7 + i}}}
            for i in range(n)]


@unittest.skipIf(torch is None, "no torch or no sim_vehicle_ecu")
class Models(unittest.TestCase):
    def run_of(self, recs):
        from scensim_batch import compile as C, core
        c = C.compile_scenario(CASE, recs, StraightWorld())
        comp = ecu_batch.load_batch(Accel, {}, {}, [7] * len(recs))
        return c, core.BatchRun(c, StraightWorld(), PointMass(c.n), comp)

    def test_the_walker_compiles_as_a_model_with_its_anchors(self):
        c, run = self.run_of(records(2))
        w = c.index("walker")
        e = c.entities[w]
        self.assertEqual(e.role, "model")
        self.assertEqual(e.model["entry"], "scensim.behaviour:gap_acceptance_walker")
        self.assertEqual(e.model["params"][0]["start_gap"], 3.0)
        self.assertEqual(e.model["seeds"], [7, 8])
        self.assertAlmostEqual(float(c.yaw[0, w]), math.pi / 2)     # LanePosition's Orientation
        a = run.models.anchors[0][0]
        for got, want in zip(a["kerb"] + a["far"] + a["conflict"],
                             [47.0, -1.75, 47.0, 5.25, 47.0, 0.0]):
            self.assertAlmostEqual(got, want, places=9)

    def test_a_walker_appears_at_its_start_gap_and_waits_out_a_short_gap(self):
        """The ego at 8.3 m/s from x = 5 reaches the crossing at x = 47 at 5.06 s. The walker
        appears at 3.0 s before it, walks from rest toward the kerb, and decides 0.65 m before it
        (where it can still stop there): 0.85 m from the start, 1.07 s at 1.5 m/s^2 up to
        1.4 m/s, so about 1.93 s is offered, which the logit mostly rejects (U = -2.8,
        P = 0.06). It stops at the kerb, waits until the ego has passed, then crosses."""
        recs = records(8)
        c, run = self.run_of(recs)
        n, w = c.n, c.index("walker")
        run.reset()
        ev_log, ys = [], []
        for k in range(int(12.0 / DT)):
            obs = run.step(cmds(n, 0.0), DT)
            ev_log.append(obs["model_events"]["walker"].clone())
            ys.append(obs["y"][:, w].clone())
        ev = torch.stack(ev_log)              # [T, N]
        from scensim.behaviour import walker as wk
        appear = (ev == wk.APPEAR).int().argmax(0).double() * DT
        t_conflict = (47.0 - 5.0) / 8.3
        for i in range(n):
            self.assertAlmostEqual(float(appear[i]) + DT, t_conflict - 3.0, delta=2 * DT)
        rec = run.models.records()["walker"]
        for i in range(n):
            d = rec[i]["decision"]
            self.assertAlmostEqual(d["gap_s"], 1.93, delta=0.08)
            self.assertEqual(rec[i]["parameter_set"]["name"], "khaki2021_restricted")
        rejected = [i for i in range(n) if bool((ev[:, i] == wk.REJECT).any())]
        self.assertGreaterEqual(len(rejected), 6)
        ego_x = 5.0 + 8.3 * torch.arange(1, len(ys) + 1, dtype=torch.float64) * DT
        y = torch.stack(ys)
        for i in rejected:
            go = int((ev[:, i] == wk.GO_AFTER).int().argmax())
            self.assertGreater(float(ego_x[go]), 47.0)       # only once the ego has passed
            self.assertLessEqual(float(y[:go, i].max()), -1.75 + 1e-9)   # not into the lane
            self.assertTrue(bool((ev[:, i] == wk.DONE).any()))
        # done at the far kerb (y = 5.25), then stopped by the world's limit: 1.4^2 / (2 x 1.5)
        # = 0.65 m onto the far pavement
        for i in rejected:
            self.assertGreaterEqual(float(y[-1, i]), 5.25)
            self.assertLessEqual(float(y[-1, i]), 5.25 + 0.66 + 1.4 * DT)

    def test_a_masked_reset_restarts_only_its_walkers(self):
        recs = records(4)
        c, run = self.run_of(recs)
        n, w = c.n, c.index("walker")
        run.reset()
        for _ in range(int(9.0 / DT)):
            obs = run.step(cmds(n, 0.0), DT)
        moved = obs["y"][:, w].clone()
        mask = torch.tensor([True, False, True, False])
        obs = run.reset(mask)
        self.assertTrue(torch.allclose(obs["y"][mask, w], c.y[mask, w]))
        self.assertTrue(torch.equal(obs["y"][~mask, w], moved[~mask]))
        from scensim.behaviour import walker as wk
        self.assertTrue(bool((run.models.models[0].phase[mask] == wk.HIDDEN).all()))


if __name__ == "__main__":
    unittest.main()
