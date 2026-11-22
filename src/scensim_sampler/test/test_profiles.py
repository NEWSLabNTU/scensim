"""Knob profiles in a scenario (092 K9): the binding's grammar, its parameters, and the per-draw
check that the breakpoints increase."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scensim_sampler import Sampler, SpecError  # noqa: E402
from scensim_sampler import profiles as P  # noqa: E402
from scensim_sampler.xosc import Scenario  # noqa: E402

CASES = Path(__file__).resolve().parents[1] / "examples" / "cases"


class Grammar(unittest.TestCase):
    def test_a_profile_parses_and_evaluates(self):
        c, lane, pts = P.parse("s(route_n): 0 1000; $fog_start 1000; $fog_end $vmin")
        self.assertEqual((c, lane), ("s", "route_n"))
        self.assertEqual(pts, [(0.0, 1000.0), ("$fog_start", 1000.0), ("$fog_end", "$vmin")])
        self.assertEqual(P.parameters(pts), ["fog_end", "fog_start", "vmin"])
        got = P.evaluate(pts, {"fog_start": 200, "fog_end": 300, "vmin": "80"})
        self.assertEqual(got, [(0.0, 1000.0), (200.0, 1000.0), (300.0, 80.0)])
        self.assertEqual(P.parse("time: 0 1; 2.5e1 -3")[0:2], ("time", None))
        self.assertTrue(P.is_profile("time: 0 1") and not P.is_profile("$fog"))

    def test_bad_profiles_are_refused(self):
        for text, why in (("route: 0 1", "a profile is"), ("time: 0", "breakpoint 1"),
                          ("time: 0 1 2", "breakpoint 1"), ("time:", "no breakpoints"),
                          ("s(): 0 1", "a profile is"), ("time: 0 x", "breakpoint 1")):
            with self.assertRaisesRegex(P.ProfileError, why, msg=text):
                P.parse(text)
        pts = P.parse("time: $a 1; $b 2")[2]
        with self.assertRaisesRegex(P.ProfileError, "do not increase"):
            P.evaluate(pts, {"a": 5, "b": 1})
        with self.assertRaisesRegex(P.ProfileError, r"\$b is not a number"):
            P.evaluate(pts, {"a": 5})


class InTheScenario(unittest.TestCase):
    def test_cs5_binds_its_fog_as_a_profile(self):
        sc = Scenario(CASES / "cs5_fog_mid_route.xosc")
        self.assertEqual(sc.knobs, {})
        coord, lane, pts = sc.knob_profiles["visibility"]
        self.assertEqual((coord, lane), ("s", "route_n"))
        self.assertEqual(P.parameters(pts), ["fog_end", "fog_start", "visibility_min"])

    def test_an_undeclared_parameter_in_a_profile_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cs5.xosc"
            p.write_text((CASES / "cs5_fog_mid_route.xosc").read_text().replace(
                "$fog_end $visibility_min", "$fog_end $nope"))
            with self.assertRaisesRegex(SpecError, r"\$nope is not a declared parameter"):
                Scenario(p)

    def test_a_draw_whose_breakpoints_cross_is_rejected_by_name(self):
        """fog_start and fog_end drawn independently: a draw with fog_end before fog_start is
        rejected, as a constraint is, under one reason."""
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            shutil.copy(CASES / "cs5_fog_mid_route.xosc", d / "s.xosc")
            (d / "m.yaml").write_text(
                "model: 1\nheader: {name: m, dataset: none, version: '0', licence: CC0-1.0}\n"
                "variables:\n"
                "  - {name: fog_start, uniform: {low: 100, high: 300}}\n"
                "  - {name: fog_end, uniform: {low: 150, high: 350}}\n")
            b = Sampler.from_file(d / "s.xosc", model=d / "m.yaml").draw(n=100, seed=3)
            self.assertTrue(all(r["values"]["fog_end"] >= r["values"]["fog_start"]
                                for r in b.records))
            self.assertGreater(b.rejected_why.get("knob profile visibility: breakpoints out of "
                                                  "order", 0), 0)


if __name__ == "__main__":
    unittest.main()
