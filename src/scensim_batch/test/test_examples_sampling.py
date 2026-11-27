"""092 E1a's second and third examples as their exit checks, small: CS1's walker search on the
examples' straight world (docs/tutorials/09-search-for-failures.md) and the coverage of its
fresh stage (10-coverage.md). The tutorial's search has N 200; this one N 100."""
import importlib.util
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1]
SAMPLING = SRC / "scensim_examples" / "sampling"
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(SRC / "scensim_sampler"))
for p in ("sim_vehicle_ecu", "scensim"):
    sys.path.insert(0, str(SRC / p))

try:
    import torch  # noqa: F401
    import sim_vehicle_ecu  # noqa: F401
except ImportError:
    torch = None


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


@unittest.skipIf(torch is None, "no torch or no sim_vehicle_ecu")
class SearchAndCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scensim_batch.world_lanelet import LaneletWorld
        from scensim_sampler import search as S
        cls.d = Path(tempfile.mkdtemp())
        world_file = cls.d / "straight_world.json"
        mk = _module("make_straight_world", SAMPLING / "make_straight_world.py")
        world_file.write_text(json.dumps(mk.export(), separators=(",", ":")) + "\n")
        cls.shipped = (SAMPLING / "straight_world.json").read_text()
        cls.made = world_file.read_text()
        world = LaneletWorld.load(world_file)
        sr = _module("search_run", HERE.parent / "scripts" / "search_run.py")
        spec = (SAMPLING / "cs1_search.yaml").read_text().replace("n: 200", "n: 100")
        cls.spec = cls.d / "cs1_search.yaml"
        cls.spec.write_text(spec.replace("scenario: cs1_walker_search.xosc",
                                         f"scenario: {SAMPLING / 'cs1_walker_search.xosc'}")
                                .replace("model: ../../", f"model: {SRC}/"))
        cls.out = cls.d / "search"
        st = S.init(cls.spec, cls.out)
        cls.stages = []
        while st["phase"] != "done" and len(cls.stages) < 12:
            g = st["generations"][-1]
            recs = rows(cls.out / g["records"])
            run_dir = cls.d / f"run-{g['records']}"
            sr.run(recs, SAMPLING / "cs1_walker_search.xosc", world, run_dir, margin_k=1.0,
                   truth=not cls.stages)          # the first stage audited (092 K11f)
            cls.stages.append((g, recs, rows(run_dir / "outcomes.jsonl")))
            st = S.next_step(cls.out, run_dir / "outcomes.jsonl")
        cls.state = st
        cls.sr, cls.world = sr, world

    def test_the_shipped_world_is_the_script_s(self):
        self.assertEqual(self.shipped, self.made)

    def test_every_stage_scores_every_record_without_error(self):
        for g, recs, outs in self.stages:
            self.assertEqual([o["record"] for o in outs], [r["id"] for r in recs], g["records"])
            for o in outs:
                self.assertFalse(o["outcome"]["error"], o)
                self.assertTrue(math.isfinite(o["outcome"]["score"]), o)

    def test_the_search_stops_and_reports_a_rate_with_its_interval(self):
        self.assertEqual(self.state["phase"], "done")
        self.assertEqual(self.stages[-1][0]["stage"], "fresh")
        from scensim_sampler import search as S
        rep = S.report(self.out)
        self.assertEqual(rep["schema"], "scensim.search/1")
        e = self.state["estimate"]
        self.assertGreater(e["failures"], 0)
        lo, hi = e["interval"]
        self.assertTrue(0 <= lo <= e["p"] <= hi, e)

    def test_a_failure_run_alone_scores_the_same_bit_for_bit(self):
        _, recs, outs = self.stages[-1]
        k = next(i for i, o in enumerate(outs) if o["outcome"]["failed"])
        d = self.d / "alone"
        self.sr.run([recs[k]], SAMPLING / "cs1_walker_search.xosc", self.world, d, margin_k=1.0)
        (alone,) = rows(d / "outcomes.jsonl")
        self.assertEqual(alone["outcome"]["score"], outs[k]["outcome"]["score"])

    def test_coverage_of_the_fresh_stage_is_the_search_s_estimate(self):
        from scensim_sampler import coverage as C
        g, recs, outs = self.stages[-1]
        join = _module("join_outcomes", SAMPLING / "join_outcomes.py")
        f = self.d / "fresh.joined.jsonl"
        sys.argv = ["join_outcomes", str(self.out / g["records"]),
                    str(self.d / f"run-{g['records']}" / "outcomes.jsonl"), "-o", str(f)]
        join.main()
        items = C.outcomes_from_jsonl(f)
        self.assertEqual(sorted(r["id"] for r, _ in items), sorted(r["id"] for r in recs))
        rep = C.report(items)
        (cell,) = rep["layer3"]
        self.assertEqual(cell["runs"], len(recs))
        self.assertAlmostEqual(cell["rate"], self.state["estimate"]["p"], places=15)
        # against the study's catalogue: the pairs covered are the ones the records hold
        cat = C.load_catalogue(SAMPLING / "catalogue.yaml")
        (l2,) = [x for x in C.report(items, cat)["layer2"]
                 if x["category"] == "R2.walker_crossing.dart_out"]
        pairs = {frozenset([(a, r["cell"][a]), (b, r["cell"][b])]) for r, _ in items
                 for a, b in (("illumination", "surface"), ("illumination", "occluder"),
                              ("occluder", "surface"))}
        self.assertEqual((l2["covered"], l2["tuples"]), (len(pairs), 12))


if __name__ == "__main__":
    unittest.main()
