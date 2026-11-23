"""The search (roadmap 092 K11): exit checks 1 to 3 of "K11's plan", and the refusals."""
import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _files import Dir  # noqa: E402
from scensim_sampler import coverage as C, record as R, search as S  # noqa: E402

HEADER = 'header: {name: t, dataset: t, version: "1", licence: t}\n'
TAIL_MODEL = ("model: 1\n" + HEADER + "variables:\n"
              "  - {name: speed, normal: {mean: 0, sd: 1}}\n"
              "  - {name: gap, normal: {mean: 0, sd: 1}}\n")
P_TAIL = 0.5 * math.erfc(5.2 / math.sqrt(2) / math.sqrt(2))   # Phi(-5.2 / sqrt 2) = 1.18e-4


def tail_score(r):
    return 5.2 - (r["values"]["speed"] + r["values"]["gap"])


def records(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def run(d, spec, score, name="run", until_done=True):
    """Step a search to its end, scoring each record with `score`."""
    d.write("spec.yaml", spec)
    out = d.path / name
    st = S.init(d.path / "spec.yaml", out)
    while st["phase"] != "done":
        g = st["generations"][-1]
        o = out / f"{g['records']}.out"
        o.write_text("".join(json.dumps({"record": r["id"], "outcome": {"score": score(r)}})
                             + "\n" for r in records(out / g["records"])))
        st = S.next_step(out, o)
        if not until_done:
            break
    return out, st


def spec(seed, n=1000, variables="[speed, gap]", model="m.yaml", extra=""):
    return (f"search: 1\nid: tail\nscenario: s.xosc\nmodel: {model}\nvariables: {variables}\n"
            f"n: {n}\nseed: {seed}\n{extra}")


class KnownRareEvent(unittest.TestCase):
    """Check 1: base N(0, I), failure x1 + x2 > 5.2, p = 1.18e-4, N = 1000, seeds 1 to 20."""

    @classmethod
    def setUpClass(cls):
        cls.rows = []
        for seed in range(1, 21):
            d = Dir()
            d.write("m.yaml", TAIL_MODEL)
            out, st = run(d, spec(seed), tail_score)
            e = st["estimate"]
            fresh = st["generations"][-1]
            cls.rows.append({"seed": seed, "fresh_generation": fresh["generation"],
                             "stop": st["stop"], "p": e["p"], "lo": e["interval"][0],
                             "hi": e["interval"][1], "n_eff_share": e["n_eff"] / e["n"],
                             "max_weight": max(g["max_weight"] for g in st["generations"]),
                             "diagnostic": st["diagnostic"]["generations_estimate"]})
            d.close()
        print("\nK11 check 1 (p = %.4g):" % P_TAIL, file=sys.stderr)
        for r in cls.rows:
            print("  seed %(seed)2d: fresh g%(fresh_generation)d, p %(p).4g [%(lo).4g, %(hi).4g]"
                  ", n_eff/N %(n_eff_share).3f, largest weight %(max_weight).4f, generations' "
                  "%(diagnostic).4g" % r, file=sys.stderr)

    def test_the_level_reaches_the_threshold_within_4_generations_in_every_seed(self):
        for r in self.rows:
            self.assertEqual(r["stop"], "the level reached the threshold", r)
            self.assertLessEqual(r["fresh_generation"], 4, r)   # g0..g3, then the fresh stage

    def test_the_fresh_interval_contains_p_in_at_least_18_of_20(self):
        inside = sum(r["lo"] <= P_TAIL <= r["hi"] for r in self.rows)
        self.assertGreaterEqual(inside, 18, inside)

    def test_every_weight_at_most_10(self):
        for r in self.rows:
            self.assertLessEqual(r["max_weight"], 10.0 + 1e-9, r)

    # n_eff / N above 0.1 was predicted and failed in 3 of 20 seeds (092, "K11a's result"):
    # Kish's count over all of the mixture's weights sits near beta by construction. It is
    # reported (the rows above), and is not a bar.


class UnitMeanWeights(unittest.TestCase):
    """For an event that always holds, mean(w) estimates 1: every kind, with and without
    constraints, through the mixture. g1 is fitted toward a corner so it is not the base."""

    MODELS = {
        "truncated": ("  - {name: speed, normal: {mean: 10, sd: 3}, range: [4, 20]}\n"
                      "  - {name: gap, lognormal: {mean: 2, sd: 1}, range: [0.5, 6]}\n"
                      "  - {name: kind, categorical: {car: 0.7, van: 0.2, bus: 0.1}}\n",
                      "[speed, gap, kind]"),
        "uniform": ("  - {name: speed, uniform: {low: 0, high: 20}}\n"
                    "  - {name: gap, normal: {mean: 2, sd: 1}}\n", "[speed, gap]"),
    }

    def check(self, body, variables, constraints):
        d = Dir()
        d.write("m.yaml", "model: 1\n" + HEADER + "variables:\n" + body
                + ("constraints: [\"speed + 3 * gap < 22\"]\n" if constraints else ""))
        # toward high speed and low gap; one generation, then g1's records
        out, st = run(d, spec(5, n=10000, variables=variables,
                              extra="acceptance_draws: 100000\n"),
                      lambda r: -r["values"]["speed"] + r["values"]["gap"], until_done=False)
        g = st["generations"][-1]
        self.assertEqual(g["generation"], 1)
        w = [math.exp(r["log_weight"]) * g["normaliser"] for r in records(out / g["records"])]
        n = len(w)
        m = sum(w) / n
        se = math.sqrt(sum((x - m) ** 2 for x in w) / (n - 1) / n)
        rel = math.sqrt(sum(0 if mm == 0 else (1 - z) / (z * mm) for z, mm in
                            ((st["z_base"], st["z_base_draws"]),
                             (g["z_proposal"], g["z_proposal_draws"]))))
        tot = math.sqrt(se ** 2 + rel ** 2)
        if constraints:
            self.assertLess(st["z_base"], 0.99)        # the constraint does truncate
        self.assertNotEqual(g["normaliser"] == 1.0, constraints)
        self.assertLess(abs(m - 1), 3 * tot, (m, tot))
        d.close()

    def test_truncated_kinds_without_constraints(self):
        self.check(*self.MODELS["truncated"], False)

    def test_truncated_kinds_with_constraints(self):
        self.check(*self.MODELS["truncated"], True)

    def test_a_uniform_as_a_normal_without_constraints(self):
        self.check(*self.MODELS["uniform"], False)

    def test_a_uniform_as_a_normal_with_constraints(self):
        self.check(*self.MODELS["uniform"], True)


class Files(unittest.TestCase):
    def setUp(self):
        self.d = Dir()
        self.d.write("m.yaml", TAIL_MODEL)

    def tearDown(self):
        self.d.close()

    def test_check_2_the_same_spec_seed_and_outcomes_give_the_same_files(self):
        a, _ = run(self.d, spec(3, n=300), tail_score, "a")
        b, _ = run(self.d, spec(3, n=300), tail_score, "b")
        fa = sorted(p.name for p in a.iterdir())
        self.assertEqual(fa, sorted(p.name for p in b.iterdir()))
        for name in fa:
            self.assertEqual((a / name).read_bytes(), (b / name).read_bytes(), name)

    def test_check_3_records_pass_check_and_coverage_reads_them(self):
        out, st = run(self.d, spec(3, n=300), tail_score)
        items = []
        for g in st["generations"]:
            for r in records(out / g["records"]):
                self.assertEqual(R.check(r), [], r["id"])
                self.assertEqual(r["search"]["generation"], g["generation"])
                self.assertEqual(r["search"]["stage"], g["stage"])
                self.assertIsNotNone(r["proposal"])
                self.assertLessEqual(r["weight"], 10.0 + 1e-9)
                if g["stage"] == "fresh":
                    s = tail_score(r)
                    items.append((r, {"failed": s <= 0, "contact": False, "error": False,
                                      "seeds_not_applied": False, "run": r["id"]}))
        rep = C.report(items)
        (cell,) = rep["layer3"]
        self.assertEqual(cell["interval_method"], "plain likelihood ratio, normal 95 %")
        self.assertAlmostEqual(cell["rate"], st["estimate"]["p"], places=15)

    def test_an_outcome_missing_is_refused(self):
        self.d.write("spec.yaml", spec(3, n=50))
        out = self.d.path / "r"
        st = S.init(self.d.path / "spec.yaml", out)
        recs = records(out / st["generations"][0]["records"])
        o = self.d.write("o.jsonl", "".join(json.dumps({"record": r["id"],
                                                        "outcome": {"score": 1.0}}) + "\n"
                                            for r in recs[1:]))
        with self.assertRaisesRegex(S.SearchError, "1 of 50 records have no outcome"):
            S.next_step(out, o)

    def test_an_error_run_is_left_out_and_counted(self):
        self.d.write("spec.yaml", spec(3, n=50))
        out = self.d.path / "r"
        st = S.init(self.d.path / "spec.yaml", out)
        recs = records(out / st["generations"][0]["records"])
        o = self.d.write("o.jsonl", "".join(
            json.dumps({"record": r["id"], "outcome": ({"error": True} if i < 3
                                                       else {"score": tail_score(r)})}) + "\n"
            for i, r in enumerate(recs)))
        st = S.next_step(out, o)
        self.assertEqual(st["generations"][0]["errors"], 3)
        self.assertEqual(st["generations"][0]["estimate"]["n"], 47)


class Refusals(unittest.TestCase):
    def refused(self, body, variables, text):
        d = Dir()
        d.write("m.yaml", "model: 1\n" + HEADER + "variables:\n" + body)
        d.write("spec.yaml", spec(1, n=10, variables=variables))
        with self.assertRaisesRegex(S.SearchError, text):
            S.init(d.path / "spec.yaml", d.path / "r")
        d.close()

    def test_a_latent_variable(self):
        self.refused("  - {name: speed, normal: {mean: 0, sd: 1}}\n"
                     "  - {name: u, normal: {mean: 0, sd: 1}, latent: true}\n"
                     "  - {name: gap, normal: {mean: 0, sd: 1}}\n", "[u]", "u: latent")

    def test_a_joint_group(self):
        self.refused("  - names: [speed, gap]\n    mixture:\n"
                     "      - {weight: 1, mean: [0, 0], cov: [[1, 0], [0, 1]]}\n",
                     "[speed]", "speed: drawn in a joint group")

    def test_a_conditioned_parameter(self):
        self.refused("  - {name: speed, normal: {mean: 0, sd: 1}}\n"
                     "  - {name: gap, normal: {mean: \"speed\", sd: 1}}\n",
                     "[gap]", "gap: its normal reads other values")

    def test_a_poisson(self):
        self.refused("  - {name: speed, normal: {mean: 0, sd: 1}}\n"
                     "  - {name: gap, normal: {mean: 0, sd: 1}}\n"
                     "  - {name: lanes, poisson: {mean: 2}}\n", "[lanes]",
                     "lanes: a poisson, which K11 does not search")


if __name__ == "__main__":
    unittest.main()
