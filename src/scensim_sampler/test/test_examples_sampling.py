"""092 E1a's first example, docs/tutorials/08-sample-scenarios.md, as its exit check: the
tutorial's commands on the walker dart-out, run through the command line in process."""
import io
import json
import math
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _files import EXAMPLES  # noqa: E402
from scensim_sampler import record as R  # noqa: E402
from scensim_sampler.cli import main  # noqa: E402

CASES = EXAMPLES.parent / "cases"


def cli(*argv):
    s = io.StringIO()
    with redirect_stdout(s), redirect_stderr(s):
        rc = main([str(a) for a in argv])
    return rc, s.getvalue()


def rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


class SampleScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = Path(tempfile.mkdtemp())
        for name, dist in (("a", "walker_dartout_dist.xosc"), ("b", "walker_dartout_dist.xosc"),
                           ("w", "walker_dartout_importance.xosc")):
            rc, _ = cli("draw", EXAMPLES / dist, "-n", 200, "--seed", 7,
                        "-o", cls.d / f"{name}.jsonl")
            assert rc == 0, name

    def test_step_1_two_hundred_records_each_passing_the_check(self):
        recs = rows(self.d / "a.jsonl")
        self.assertEqual(len(recs), 200)
        rc, out = cli("check", self.d / "a.jsonl",
                      "--scenario", EXAMPLES / "walker_dartout.xosc")
        self.assertEqual(rc, 0, out)
        self.assertIn("200 records, 0 problems", out)

    def test_step_2_the_same_seed_draws_the_same_records(self):
        self.assertEqual((self.d / "a.jsonl").read_bytes(), (self.d / "b.jsonl").read_bytes())

    def test_step_3_every_value_in_its_support_and_every_constraint_held(self):
        ranges = {"adult": (0.6, 2.4), "child": (0.6, 3.0), "runner": (1.8, 6.0)}
        for r in rows(self.d / "a.jsonl"):
            v = r["values"]
            lo, hi = ranges[v["walker_type"]]
            self.assertTrue(lo <= v["walk_speed"] <= hi, v)
            self.assertTrue(0.3 <= v["ttc_entry"] <= 8.0, v)
            self.assertIn(v["illumination"], ("day", "night"))
            self.assertLessEqual(v["ego_speed"], 1.2 * 13.9)
            self.assertGreater(v["van_offset"], 0.5)
            self.assertAlmostEqual(v["trigger_distance"], v["ego_speed"] * v["ttc_entry"],
                                   places=9)

    def test_step_4_importance_records_carry_a_proposal_and_consistent_weights(self):
        recs = rows(self.d / "w.jsonl")
        self.assertEqual([R.check(r) for r in recs], [[]] * len(recs))
        for r in recs:
            self.assertIsNotNone(r["proposal"])
            self.assertTrue(math.isfinite(r["weight"]) and r["weight"] > 0, r["weight"])
            self.assertAlmostEqual(math.log(r["weight"]), r["log_weight"], places=9)
        w = [r["weight"] for r in recs]
        n_eff = sum(w) ** 2 / sum(x * x for x in w)
        self.assertLess(n_eff, len(w))           # weighted: fewer effective samples than drawn

    def test_step_5_both_cases_compile_for_a_batch(self):
        rc, out = cli("compilable", EXAMPLES / "walker_dartout.xosc", "--ego", "seats")
        self.assertEqual(rc, 0, out)
        self.assertIn("walker_dartout.xosc: compiles", out)
        rc, out = cli("compilable", CASES / "cs1_walker_gap_acceptance_k11c.xosc")
        self.assertEqual(rc, 0, out)
        self.assertIn("compiles with the ego replaced by the batch's policy", out)


if __name__ == "__main__":
    unittest.main()
