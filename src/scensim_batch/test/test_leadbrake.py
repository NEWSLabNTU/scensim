"""094 P4's episode (scenarios/projects/leadbrake_rl): its distribution is stock's
(bench/p4_leadbrake's RANGES, drawn as its reset_episode draws them), it compiles on the task's
straight world, and a reset gives each slot its record's storyboard (Storyboard.rebind)."""
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
REPO = HERE.parents[2]
DIST = REPO / "scenarios" / "projects" / "leadbrake_rl" / "scenarios" / "leadbrake_dist.xosc"
CATALOGS = {"vehicles": str(REPO / "src" / "sim_vehicle_spec" / "catalogs" / "vehicles.xosc")}
try:
    import torch
    from scensim_batch import compile as C, start_pool as SP
    from scensim_batch.tasks import leadbrake as LB
except ImportError:      # pragma: no cover
    torch = None


def ks_uniform(xs, lo, hi):
    """The one-sample Kolmogorov-Smirnov statistic of xs against U[lo, hi]."""
    xs = sorted(xs)
    n = len(xs)
    return max(max((i + 1) / n - (x - lo) / (hi - lo), (x - lo) / (hi - lo) - i / n)
               for i, x in enumerate(xs))


def ks_two(a, b):
    a, b = sorted(a), sorted(b)
    i = j = 0
    d = 0.0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            i += 1
        else:
            j += 1
        d = max(d, abs(i / len(a) - j / len(b)))
    return d


@unittest.skipIf(torch is None or not DIST.exists(), "no torch, or no leadbrake_rl project")
class Distribution(unittest.TestCase):
    N = 10000

    @classmethod
    def setUpClass(cls):
        cls.pool = SP.StartPool(DIST, LB.straight_world(), seed=5, chunk=cls.N, background=False,
                                catalogs=CATALOGS)
        cls.eps = [LB.episode_from_record(r["values"]) for r in cls.pool.records[:cls.N]]

    def test_the_four_draws_are_stocks_uniforms(self):
        """133: each of stock's four marginals, KS against its U[lo, hi] at 10k draws (the 0.1 %
        critical value is 1.95 / sqrt(n) = 0.0195)."""
        crit = 1.95 / math.sqrt(self.N)
        for name, (lo, hi) in LB.RANGES.items():
            xs = [e[name] for e in self.eps]
            self.assertGreaterEqual(min(xs), lo, name)
            self.assertLessEqual(max(xs), hi, name)
            self.assertLess(ks_uniform(xs, lo, hi), crit, name)

    def test_the_gap_is_stocks_headway_times_speed(self):
        """The gap, front to rear (headway x speed), against stock's own sampler's (its
        reset_episode: torch's uniform_ per range) at 10k each, two-sample KS (0.1 %: 0.0276)."""
        g = torch.Generator().manual_seed(11)
        u = lambda lo, hi: torch.empty(self.N).uniform_(lo, hi, generator=g)  # noqa: E731
        stock = (u(*LB.RANGES["lead_speed"]) * u(*LB.RANGES["headway"])).tolist()
        ours = [e["headway"] * e["lead_speed"] for e in self.eps]
        self.assertLess(ks_two(ours, stock), 1.95 * math.sqrt(2 / self.N))

    def test_the_draws_are_independent(self):
        """Stock draws the four independently: their pairwise correlations are nil."""
        names = list(LB.RANGES)
        cols = torch.tensor([[e[k] for k in names] for e in self.eps], dtype=torch.float64)
        z = (cols - cols.mean(0)) / cols.std(0)
        r = (z.T @ z) / (len(cols) - 1)                # their correlation matrix
        off = r - torch.eye(len(names), dtype=torch.float64)
        self.assertLess(float(off.abs().max()), 4.0 / math.sqrt(self.N))

    def test_the_ego_starts_at_the_leads_speed_its_gap_behind(self):
        for r, e in zip(self.pool.records[:100], self.eps[:100]):
            v = r["values"]
            self.assertEqual(float(v["ego_speed"]), float(v["lead_speed"]))
            gap = float(v["lead_s"]) - LB.REAR - (LB.EGO_S + LB.FRONT)       # rear to front
            self.assertAlmostEqual(gap, e["headway"] * e["lead_speed"], places=9)


@unittest.skipIf(torch is None or not DIST.exists(), "no torch, or no leadbrake_rl project")
class Compile(unittest.TestCase):
    def test_it_compiles_on_the_straight_world_and_rebinds_per_slot(self):
        pool = SP.StartPool(DIST, LB.straight_world(), seed=2, chunk=8, background=False,
                            catalogs=CATALOGS)
        rows = pool.take(4)
        recs = [pool.record(r) for r in rows]
        c = C.compile_scenario(pool.scenario, recs, LB.straight_world(), catalogs=CATALOGS)
        sb = c.storyboard
        self.assertEqual(sb.params_live, {"onset_s", "decel"})
        pool.check_storyboard(sb)                                  # nothing compiled in
        ego, lead = c.index("ego"), c.index("lead")
        for k, r in enumerate(recs):
            v = r["values"]
            self.assertAlmostEqual(float(c.x[k, ego]), LB.EGO_S, places=6)
            self.assertAlmostEqual(float(c.x[k, lead]), float(v["lead_s"]), places=6)
            self.assertAlmostEqual(float(c.y[k, lead]), 0.0, places=9)
            self.assertAlmostEqual(float(c.speed[k, ego]), float(v["ego_speed"]), places=9)
        self.assertEqual(c.entities[lead].role, "default")         # SSv2's default vehicle
        fresh = [pool.record(r) for r in pool.take(4)]
        sb.rebind(fresh, [0, 1, 2, 3])
        c2 = C.compile_scenario(pool.scenario, fresh, LB.straight_world(), catalogs=CATALOGS)
        for (_, a), (_, b) in zip(sb._rebinds, c2.storyboard._rebinds):
            for x, y in zip(a, b):
                self.assertTrue(torch.equal(x, y))


if __name__ == "__main__":
    unittest.main()
