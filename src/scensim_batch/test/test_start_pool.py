"""094 P2's start pool (scensim_batch.start_pool): real sample records, compiled to the ego's
Init, taken one per reset, never one used before; a dry pool waits and counts it; a storyboard
that reads a sampled parameter is refused."""
import json
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
REPO = HERE.parents[2]
DRIFT = REPO / "scenarios" / "projects" / "mushr_drift" / "scenarios" / "mushr_drift_dist.xosc"
CASES = HERE.parents[1] / "scensim_sampler" / "examples" / "cases"

try:
    import torch
    from scensim_batch import start_pool as SP
    from test_core import StraightWorld
except ImportError:      # no torch
    torch = None


@unittest.skipIf(torch is None or not DRIFT.exists(), "no torch, or no mushr_drift project")
class StartPoolTest(unittest.TestCase):
    def pool(self, **kw):
        return SP.StartPool(DRIFT, StraightWorld(), seed=7, chunk=kw.pop("chunk", 40),
                            background=kw.pop("background", False), **kw)

    def test_rows_are_records_never_reused(self):
        p = self.pool()
        seen = set()
        for _ in range(10):
            rows = p.take(13)
            ids = [p.record(r)["id"] for r in rows]
            self.assertFalse(seen & set(ids))
            seen.update(ids)
        self.assertEqual(len(seen), 130)
        self.assertGreaterEqual(p.chunks, 4)            # refilled as it ran low

    def test_init_is_the_records_start(self):
        p = self.pool()
        rows = p.take(5)
        x, y, yaw, v = p.init(rows)
        for i, r in enumerate(rows):
            vals = p.record(r)["values"]
            self.assertAlmostEqual(x[i].item(), vals["start_x"], places=12)
            self.assertAlmostEqual(y[i].item(), vals["start_y"], places=12)
            self.assertAlmostEqual(math.remainder(yaw[i].item() - vals["start_h"], 2 * math.pi),
                                   0.0, places=9)
            self.assertEqual(v[i].item(), 0.0)          # at rest, as stock's reset

    def test_a_dry_pool_waits_and_counts_it(self):
        p = self.pool(chunk=10, low_water=-1)           # no refill ahead of need
        p.take(10)
        self.assertEqual(p.stalls, 0)
        p.take(15)                                      # 0 left: two refills, both waited on
        self.assertEqual(p.stalls, 2)
        self.assertGreater(p.stats()["stall_s"], 0.0)

    def test_chunks_are_reproducible(self):
        a = [r["id"] for r in self.pool().records]
        b = [r["id"] for r in self.pool().records]
        self.assertEqual(a, b)
        self.assertEqual(len(set(a)), len(a))

    def test_a_background_refill_lands(self):
        p = self.pool(chunk=20, low_water=15, background=True)
        p.take(10)                                      # 10 left < 15: a refill starts
        p._thread.join()
        self.assertEqual(len(p.records), 40)

    def test_a_storyboard_reading_a_sampled_parameter_is_refused(self):
        dist = CASES / "cs6_cut_out_stopped_car_dist.xosc"
        reads = SP.storyboard_parameters(CASES / "cs7_cyclist_low_sun.xosc")
        if not reads:
            self.skipTest("cs6s storyboard reads no parameter")
        with self.assertRaisesRegex(SP.PoolError, "its storyboard reads"):
            SP.StartPool(dist, StraightWorld(), seed=1, chunk=5, background=False)

    def test_stocks_20_points_a_run_then_an_index_per_episode(self):
        from scensim_batch.tasks.drift_start import TRACK_LENGTH, reference_points
        knobs = reference_points(3)
        self.assertEqual(knobs, reference_points(3))               # the run's, reproducibly
        self.assertNotEqual(knobs, reference_points(4))
        self.assertEqual(len(knobs), 20)
        self.assertTrue(all(0.0 <= v < TRACK_LENGTH for v in knobs.values()))
        p = SP.StartPool(DRIFT, StraightWorld(), seed=3, chunk=200, background=False,
                         knobs=knobs)
        refs = set()
        for r in p.records:
            refs.add(r["latent"]["ref"])
            dx = r["latent"]["dx"]
            self.assertLessEqual(abs(dx), 0.5)
        self.assertEqual(refs, set(range(20)))       # every point drawn, only those 20

    def test_the_drift_storyboard_reads_no_parameter(self):
        self.assertEqual(SP.storyboard_parameters(DRIFT.parent / "mushr_drift.xosc"), set())


if __name__ == "__main__":
    unittest.main()
