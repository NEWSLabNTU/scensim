"""The sampler on OpenSCENARIO distribution files and model files: what it reads, what it
draws, its seeds and its weights."""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _files import EXAMPLES, Dir  # noqa: E402
from scensim_sampler import Sampler, SpecError, check  # noqa: E402
from scensim_sampler.xosc import Scenario  # noqa: E402

MODEL = """model: 1
header: {name: m, dataset: d, version: "1", licence: CC-BY-4.0}
variables:
  - {name: kind, categorical: {car: 0.5, truck: 0.5}}
  - name: speed
    given: kind
    cases:
      car: {normal: {mean: 12, sd: 1}}
      truck: {normal: {mean: 8, sd: 1}}
  - {name: gap, lognormal: {mean: "2.0 + 0.0 * speed", sd: 0.5}, range: [0.2, 10]}
derived: {headway: "gap / speed"}
constraints: ["speed > 0", "gap < max_gap"]
knobs: {max_gap: 3}
"""



CS6_ANCHORS = {"hwy_right": {"kind": "lane", "lanelet": 201}}   # cs6_anchors.yaml

class Base(unittest.TestCase):
    def setUp(self):
        self.d = Dir()

    def tearDown(self):
        self.d.close()


class Deterministic(Base):
    def test_sets_ranges_and_value_sets_are_enumerated_as_a_product(self):
        p = self.d.dist("""<Deterministic>
          <DeterministicSingleParameterDistribution parameterName="kind">
            <DistributionSet><Element value="car"/><Element value="truck"/></DistributionSet>
          </DeterministicSingleParameterDistribution>
          <DeterministicSingleParameterDistribution parameterName="speed">
            <DistributionRange stepWidth="2.5"><Range lowerLimit="5" upperLimit="10"/></DistributionRange>
          </DeterministicSingleParameterDistribution>
          <DeterministicMultiParameterDistribution><ValueSetDistribution>
            <ParameterValueSet><ParameterAssignment parameterRef="gap" value="1.5"/>
              <ParameterAssignment parameterRef="lanes" value="2"/></ParameterValueSet>
            <ParameterValueSet><ParameterAssignment parameterRef="gap" value="3"/>
              <ParameterAssignment parameterRef="lanes" value="3"/></ParameterValueSet>
          </ValueSetDistribution></DeterministicMultiParameterDistribution>
        </Deterministic>""")
        b = Sampler.from_file(p).draw()
        self.assertEqual(len(b.records), 2 * 3 * 2)
        vals = [r["values"] for r in b.records]
        self.assertEqual(sorted({v["speed"] for v in vals}), [5.0, 7.5, 10.0])
        self.assertEqual({(v["gap"], v["lanes"]) for v in vals}, {(1.5, 2), (3.0, 3)})
        self.assertTrue(all(isinstance(v["lanes"], int) for v in vals))
        sc = Scenario(self.d.path / "s.xosc")
        for r in b.records:
            self.assertEqual(check(r, scenario=sc), [])
            self.assertEqual((r["weight"], r["log_weight"], r["base"]), (1.0, 0.0, None))

    def test_a_value_the_parameter_type_cannot_hold_is_refused(self):
        p = self.d.dist("""<Deterministic><DeterministicSingleParameterDistribution parameterName="lanes">
            <DistributionSet><Element value="2.5"/></DistributionSet>
          </DeterministicSingleParameterDistribution></Deterministic>""")
        with self.assertRaisesRegex(SpecError, "lanes: 2.5 is not an integer"):
            Sampler.from_file(p)

    def test_an_undeclared_parameter_is_refused_by_name(self):
        p = self.d.dist("""<Deterministic><DeterministicSingleParameterDistribution parameterName="nope">
            <DistributionSet><Element value="1"/></DistributionSet>
          </DeterministicSingleParameterDistribution></Deterministic>""")
        with self.assertRaisesRegex(SpecError, "nope is not a parameter of s.xosc"):
            Sampler.from_file(p)


STANDARD = """<Stochastic numberOfTestRuns="{n}" randomSeed="{seed}">
  <StochasticDistribution parameterName="speed">
    <NormalDistribution expectedValue="10" variance="4"><Range lowerLimit="0" upperLimit="30"/></NormalDistribution>
  </StochasticDistribution>
  <StochasticDistribution parameterName="gap">
    <LogNormalDistribution expectedValue="2" variance="0.25"/>
  </StochasticDistribution>
  <StochasticDistribution parameterName="lanes">
    <PoissonDistribution expectedValue="2"><Range lowerLimit="1" upperLimit="4"/></PoissonDistribution>
  </StochasticDistribution>
  <StochasticDistribution parameterName="kind">
    <ProbabilityDistributionSet><Element value="car" weight="3"/><Element value="truck" weight="1"/></ProbabilityDistributionSet>
  </StochasticDistribution>
  <StochasticDistribution parameterName="wet">
    <ProbabilityDistributionSet><Element value="true" weight="1"/><Element value="false" weight="1"/></ProbabilityDistributionSet>
  </StochasticDistribution>
</Stochastic>"""


class Stochastic(Base):
    def test_the_standard_distributions_draw_typed_values(self):
        p = self.d.dist(STANDARD.format(n=2000, seed=5))
        b = Sampler.from_file(p).draw()
        self.assertEqual(len(b.records), 2000)
        v = [r["values"] for r in b.records]
        sp = np.array([x["speed"] for x in v])
        self.assertAlmostEqual(sp.mean(), 10, delta=0.2)
        self.assertTrue(all(1 <= x["lanes"] <= 4 and isinstance(x["lanes"], int) for x in v))
        self.assertTrue(all(isinstance(x["wet"], bool) for x in v))
        self.assertAlmostEqual(sum(x["kind"] == "car" for x in v) / 2000, 0.75, delta=0.03)
        self.assertEqual(b.records[0]["sampler"]["plugins"], ["independent"])
        self.assertEqual(b.records[0]["cell"], {"surface": "dry"})

    def test_the_same_seed_gives_the_same_records_and_a_sample_does_not_depend_on_n(self):
        p = self.d.dist(STANDARD.format(n=10, seed=5))
        a = Sampler.from_file(p).draw()
        b = Sampler.from_file(p).draw(n=3)
        self.assertEqual(a.records[:3], b.records)
        c = Sampler.from_file(p).draw(seed=6)
        self.assertNotEqual(a.records[0]["values"], c.records[0]["values"])
        ids = {r["id"] for r in a.records}
        self.assertEqual(len(ids), 10)
        seeds = a.records[0]["seeds"]
        self.assertEqual(set(seeds["pilots"]), {"ego", "lead"})
        self.assertEqual(a.records[4]["sampler"]["index"], 4)

    def test_a_stochastic_file_needs_a_seed(self):
        p = self.d.dist(STANDARD.format(n=3, seed=5).replace(' randomSeed="5"', ""))
        with self.assertRaisesRegex(SpecError, "a run seed is required"):
            Sampler.from_file(p).draw()
        self.assertEqual(len(Sampler.from_file(p).draw(seed=1).records), 3)


class Joint(Base):
    def setUp(self):
        super().setUp()
        self.d.write("m.yaml", MODEL)

    def dist(self):
        return self.d.dist("""<Stochastic numberOfTestRuns="3000" randomSeed="11">
          <StochasticDistribution parameterName="speed">
            <UserDefinedDistribution type="scensim.sampler:joint">m.yaml</UserDefinedDistribution>
          </StochasticDistribution>
          <StochasticDistribution parameterName="gap">
            <UserDefinedDistribution type="scensim.sampler:joint">m.yaml</UserDefinedDistribution>
          </StochasticDistribution>
        </Stochastic>""")

    def test_conditional_variables_keep_their_dependency(self):
        b = Sampler.from_file(self.dist()).draw()
        v = [r["values"] for r in b.records]
        car = np.mean([x["speed"] for x in v if x["kind"] == "car"])
        truck = np.mean([x["speed"] for x in v if x["kind"] == "truck"])
        self.assertAlmostEqual(car, 12, delta=0.1)
        self.assertAlmostEqual(truck, 8, delta=0.1)
        r = b.records[0]
        self.assertEqual(r["base"]["id"], "m.yaml")
        self.assertEqual(r["derived"], [])  # headway is not a parameter of the scenario

    def test_constraints_reject_and_the_rejections_are_counted(self):
        b = Sampler.from_file(self.dist()).draw()
        self.assertTrue(all(x["values"]["gap"] < 3 for x in b.records))
        self.assertGreater(b.rejected, 0)
        self.assertEqual(set(b.rejected_why), {"gap < max_gap"})
        b2 = Sampler.from_file(self.dist(), knobs={"max_gap": 2.2}).draw(n=500)
        self.assertTrue(all(x["values"]["gap"] < 2.2 for x in b2.records))
        self.assertGreater(b2.rejected, b.rejected * 500 / 3000)

    def test_a_scenario_with_a_model_file_draws_without_a_distribution_file(self):
        b = Sampler.from_file(self.d.path / "s.xosc", model=self.d.path / "m.yaml").draw(
            n=5, seed=1)
        self.assertEqual(len(b.records), 5)
        self.assertIsNone(b.records[0]["distribution"])

    def test_a_model_without_a_licence_is_refused(self):
        self.d.write("m.yaml", MODEL.replace(", licence: CC-BY-4.0", ""))
        with self.assertRaisesRegex(SpecError, "header needs licence: a fitted model names"):
            Sampler.from_file(self.dist())

    def test_a_parameter_given_by_two_distributions_is_refused(self):
        p = self.d.dist("""<Stochastic numberOfTestRuns="3" randomSeed="1">
          <StochasticDistribution parameterName="speed">
            <UserDefinedDistribution type="scensim.sampler:joint">m.yaml</UserDefinedDistribution>
          </StochasticDistribution>
          <StochasticDistribution parameterName="gap">
            <UniformDistribution><Range lowerLimit="1" upperLimit="2"/></UniformDistribution>
          </StochasticDistribution></Stochastic>""")
        with self.assertRaisesRegex(SpecError, "gap is given by two distributions"):
            Sampler.from_file(p)

    def test_an_unknown_plugin_is_refused_listing_the_installed(self):
        p = self.d.dist("""<Stochastic numberOfTestRuns="3" randomSeed="1">
          <StochasticDistribution parameterName="speed">
            <UserDefinedDistribution type="scensim.sampler:bayes">x</UserDefinedDistribution>
          </StochasticDistribution></Stochastic>""")
        with self.assertRaisesRegex(ValueError, "no sampler plug-in 'bayes'.*installed: "
                                                "importance, independent, joint, twise"):
            Sampler.from_file(p)


CASES = Path(__file__).resolve().parents[1] / "examples" / "cases"


class Latent(Base):
    """scenario-description.md 2a, gap 2: a model variable marked latent is drawn and recorded
    (the record's `latent`), feeds derived values and constraints, and never reaches the
    scenario; CS6's time_headway and reveal_time are latent."""

    def test_cs6_records_its_latent_variables_and_binds_only_its_parameters(self):
        b = Sampler.from_file(CASES / "cs6_cut_out_stopped_car_dist.xosc", anchors=CS6_ANCHORS).draw(n=50, seed=3)
        sc = Scenario(CASES / "cs6_cut_out_stopped_car.xosc")
        for r in b.records:
            self.assertEqual(set(r["latent"]), {"time_headway", "reveal_time"})
            self.assertFalse(set(r["latent"]) & set(r["values"]))
            self.assertTrue(set(r["values"]) <= set(sc.parameters))
            v, lat = r["values"], r["latent"]
            # the derived values read the latent ones (models/cs6_cut_out.yaml)
            self.assertAlmostEqual(v["reveal_m"], v["ego_speed"] * lat["reveal_time"], places=9)
            self.assertAlmostEqual(v["lead_s"], 5 + v["ego_speed"] * lat["time_headway"],
                                   places=9)
            self.assertLess(v["reveal_m"], 600 - v["lead_s"])   # a constraint on them
            self.assertEqual(check(r, sc), [])

    def test_a_latent_variable_named_like_a_parameter_is_refused(self):
        self.d.write("m.yaml", MODEL.replace("  - {name: gap, lognormal",
                                             "  - {name: gap, latent: true, lognormal"))
        with self.assertRaisesRegex(SpecError, "gap is latent, but s.xosc declares a parameter"):
            Sampler.from_file(self.d.path / "s.xosc", model=self.d.path / "m.yaml")

    def test_latent_is_a_boolean(self):
        self.d.write("m.yaml", MODEL.replace("  - {name: gap, lognormal",
                                             "  - {name: gap, latent: yes please, lognormal"))
        with self.assertRaisesRegex(SpecError, "latent is true or false"):
            Sampler.from_file(self.d.path / "s.xosc", model=self.d.path / "m.yaml")

    def test_the_record_check_keeps_latent_out_of_values_and_the_scenario(self):
        r = Sampler.from_file(CASES / "cs6_cut_out_stopped_car_dist.xosc", anchors=CS6_ANCHORS).draw(
            n=1, seed=3).records[0]
        sc = Scenario(CASES / "cs6_cut_out_stopped_car.xosc")
        bad = dict(r, latent={**r["latent"], "ego_speed": r["values"]["ego_speed"]})
        self.assertTrue(any("also in values" in p for p in check(bad)))
        self.assertTrue(any("latent.ego_speed: a parameter of" in p for p in check(bad, sc)))


class Anchors(Base):
    """093 gap 7: a world anchor's attributes in derived values, anchor.<name>.<attribute>;
    CS7's exit lane heading, which a constant parameter stood in for."""

    def anchors(self):
        import yaml
        return yaml.safe_load((CASES / "cs7_anchors.yaml").read_text())

    def test_cs7_computes_its_glare_from_the_exit_lanes_heading(self):
        b = Sampler.from_file(CASES / "cs7_cyclist_low_sun_dist.xosc",
                              anchors=self.anchors()).draw(n=200, seed=4)
        for r in b.records:
            self.assertEqual(r["anchors"], {"approach_n": {"lanelet": 101.0},
                                            "exit_n": {"heading": 1.5708, "lanelet": 102.0}})
            self.assertEqual((r["values"]["approach_lane"], r["values"]["exit_lane"]),
                             ("101", "102"))       # bound, as the lanelets' ids
            self.assertNotIn("exit_heading", r["values"])
            az, el = r["values"]["sun_azimuth"], r["values"]["sun_elevation"]
            want = "into_sun" if abs(az - 1.5708) < 0.35 and el < 0.2 else "low_sun"
            self.assertEqual(r["cell"]["glare"], want)
            self.assertEqual(check(r), [])
        self.assertEqual({r["cell"]["glare"] for r in b.records}, {"into_sun", "low_sun"})

    def test_the_suns_azimuth_follows_the_worlds_heading(self):
        for heading in (1.5708, 0.0):
            an = self.anchors()
            an["exit_n"]["heading"] = heading
            for r in Sampler.from_file(CASES / "cs7_cyclist_low_sun_dist.xosc",
                                       anchors=an).draw(n=20, seed=4).records:
                self.assertEqual(r["anchors"]["exit_n"], {"heading": heading, "lanelet": 102.0})
                self.assertAlmostEqual(r["values"]["sun_azimuth"],
                                       heading + r["values"]["rel_azimuth"], places=9)

    def test_a_world_without_the_anchor_is_refused(self):
        for an in (None, {"exit_s": {"kind": "lane", "heading": 0.0},
                          "approach_n": {"kind": "lane", "lanelet": 101}}):
            with self.assertRaisesRegex(SpecError, "anchor.exit_n.heading: read by a derived "
                                        "value, but the world declares no such anchor"):
                Sampler.from_file(CASES / "cs7_cyclist_low_sun_dist.xosc", anchors=an)

    def test_an_anchor_attribute_is_a_number(self):
        with self.assertRaisesRegex(SpecError, "anchor exit_n.heading: a number"):
            Sampler.from_file(CASES / "cs7_cyclist_low_sun_dist.xosc",
                              anchors={"exit_n": {"kind": "lane", "heading": "north"},
                                       "approach_n": {"kind": "lane", "lanelet": 101}})

    def test_the_record_check_takes_anchors(self):
        r = Sampler.from_file(CASES / "cs7_cyclist_low_sun_dist.xosc",
                              anchors=self.anchors()).draw(n=1, seed=4).records[0]
        for bad in ({}, {"exit_n": {}}, {"exit_n": {"heading": "1"}}, {"exit_n": 1.0}):
            self.assertTrue(any(p.startswith("anchors:") for p in check(dict(r, anchors=bad))),
                            bad)



def _lane(ids_lengths, h0=0.0, h1=1.5708):
    """A resolved lane as anchors.resolved.json carries it (092 K9a), by hand: lanelets of the
    given lengths in a row, its heading turning linearly from h0 to h1."""
    spans, s0 = [], 0.0
    for i, ln in ids_lengths:
        spans.append({"id": i, "from_s": s0, "to_s": s0 + ln})
        s0 += ln
    return {"kind": "lane", "lanelets": spans, "length": s0, "speed_limit": 13.89,
            "start_x": 0.0, "start_y": 0.0, "end_x": s0, "end_y": 0.0,
            "heading_s": [0.0, s0], "heading": [h0, h1], "heading_max_error": 0.0}


class Binding(Base):
    """092 K9b: a scenario parameter bound to the world's anchor (FileHeader
    scensim.anchor.<parameter>), set before SSv2 starts: CS7 on a resolved exit lane, its
    cyclist's LanePosition the lanelet holding cyclist_s and the s in that lanelet."""

    def cs7(self, model_edit=lambda m: m, bind_s=True):
        import shutil
        for f in ("cs7_cyclist_low_sun.xosc", "cs7_cyclist_low_sun_dist.xosc"):
            shutil.copy(CASES / f, self.d.path / f)
        shutil.copytree(CASES / "models", self.d.path / "models")
        m = self.d.path / "models" / "cs7_cyclist.yaml"
        m.write_text(model_edit(m.read_text().replace("anchor.exit_n.heading",
                                                      "anchor.exit_n.heading(cyclist_s)")))
        p = self.d.path / "cs7_cyclist_low_sun.xosc"
        x = p.read_text().replace("exit_n.lanelet\"", "exit_n.lanelet_at(param:cyclist_s)\"")
        if bind_s:
            x = x.replace('<Property name="scensim.anchor.exit_lane"',
                          '<Property name="scensim.anchor.exit_ls" '
                          'value="exit_n.local_s(param:cyclist_s)"/>\n      '
                          '<Property name="scensim.anchor.exit_lane"')
            x = x.replace('<ParameterDeclaration name="exit_lane" parameterType="string" value=""/>',
                          '<ParameterDeclaration name="exit_lane" parameterType="string" value=""/>'
                          '\n    <ParameterDeclaration name="exit_ls" parameterType="double" '
                          'value="0"/>')
            x = x.replace('s="$cyclist_s" offset="$kerb_offset"', 's="$exit_ls" offset="$kerb_offset"')
        p.write_text(x)
        return self.d.path / "cs7_cyclist_low_sun_dist.xosc"

    def anchors(self, exit_lengths=((1, 15.0), (2, 15.7))):
        return {"approach_n": {"kind": "lane", "lanelet": 101}, "exit_n": _lane(exit_lengths)}

    def test_a_lane_position_is_the_lanelet_holding_s_and_s_in_it(self):
        b = Sampler.from_file(self.cs7(), anchors=self.anchors()).draw(n=200, seed=4)
        sc = Scenario(self.d.path / "cs7_cyclist_low_sun.xosc")
        self.assertEqual(sc.anchor_bindings["exit_ls"], "exit_n.local_s($cyclist_s)")
        seen = set()
        for r in b.records:
            v = r["values"]
            want = ("1", v["cyclist_s"]) if v["cyclist_s"] < 15.0 else ("2", v["cyclist_s"] - 15.0)
            self.assertEqual(v["exit_lane"], want[0])
            self.assertAlmostEqual(v["exit_ls"], want[1], places=9)
            self.assertEqual(v["approach_lane"], "101")
            seen.add(v["exit_lane"])
            self.assertEqual(check(r), [])
        self.assertEqual(seen, {"1", "2"})                  # cyclist_s spans both lanelets

    def test_a_draw_off_the_lane_is_rejected_by_name(self):
        """cyclist_s is drawn in [5, 25]; a 20 m exit lane rejects the draws past its end, as a
        constraint does, and counts them under one reason."""
        b = Sampler.from_file(self.cs7(), anchors=self.anchors(((1, 20.0),))).draw(n=100, seed=4)
        self.assertTrue(all(r["values"]["cyclist_s"] <= 20.0 for r in b.records))
        self.assertGreater(b.rejected_why.get("a lane position outside anchor.exit_n", 0), 0)

    def test_bindings_are_checked_before_any_draw(self):
        cases = (
            ("exit_n.lanelet_at(param:cyclist_s)", "ghost_n.lanelet_at(param:cyclist_s)",
             "anchor.ghost_n.lanelet_at"),
            ("exit_n.lanelet_at(param:cyclist_s)", "exit_n.heading", "read at a lane position"),
            ("exit_n.lanelet_at(param:cyclist_s)", "exit_n.lanelet_at(99.0)", "outside the lane"),
            ("exit_n.lanelet_at(param:cyclist_s)", "exit_n.lanelet_at(param:nope)", "not a declared"),
            ("exit_n.lanelet_at(param:cyclist_s)", "exit_n lanelet", "an anchor binding is"),
            ("approach_n.lanelet", "approach_n.lanelet_at(3.0)", "no such function"),
        )
        for old, new, why in cases:
            dist = self.cs7()
            p = self.d.path / "cs7_cyclist_low_sun.xosc"
            p.write_text(p.read_text().replace(f'value="{old}"', f'value="{new}"', 1))
            with self.assertRaisesRegex(SpecError, why, msg=new):
                Sampler.from_file(dist, anchors=self.anchors())
            import shutil
            shutil.rmtree(self.d.path / "models")

    def test_a_drawn_parameter_is_not_also_bound(self):
        dist = self.cs7()
        p = self.d.path / "cs7_cyclist_low_sun.xosc"
        p.write_text(p.read_text().replace('name="scensim.anchor.exit_ls"',
                                           'name="scensim.anchor.cyclist_s"'))
        with self.assertRaisesRegex(SpecError, "cyclist_s is drawn and bound"):
            Sampler.from_file(dist, anchors=self.anchors())

    def test_the_record_names_the_resolved_file(self):
        an = self.anchors()
        src = {"map": "town_street", "map_sha256": "a" * 64, "file_sha256": "b" * 64}
        an["exit_n"]["source"] = src
        r = Sampler.from_file(self.cs7(), anchors=an).draw(n=1, seed=4).records[0]
        self.assertEqual(r["anchor_source"], [src])
        self.assertEqual(r["anchors"], {"approach_n": {"lanelet": 101.0}})
        self.assertEqual(check(r), [])

class Importance(Base):
    def setUp(self):
        super().setUp()
        self.d.write("m.yaml", MODEL.replace('constraints: ["speed > 0", "gap < max_gap"]\n', ""))
        self.d.write("q.yaml", """proposal: 1
name: short_gaps
base: m.yaml
variables:
  - {name: gap, lognormal: {mean: 1.0, sd: 0.5}, range: [0.2, 10]}
""")
        self.p = self.d.dist("""<Stochastic numberOfTestRuns="20000" randomSeed="3">
          <StochasticDistribution parameterName="gap">
            <UserDefinedDistribution type="scensim.sampler:joint">m.yaml</UserDefinedDistribution>
          </StochasticDistribution></Stochastic>""")

    def test_self_normalised_weights_recover_the_bases_expectations(self):
        base = Sampler.from_file(self.p).draw()
        imp = Sampler.from_file(self.p, proposal=self.d.path / "q.yaml").draw()
        g0 = np.array([r["values"]["gap"] for r in base.records])
        g = np.array([r["values"]["gap"] for r in imp.records])
        w = np.exp([r["log_weight"] for r in imp.records])
        self.assertLess(g.mean(), g0.mean() - 0.5)  # drawn where gaps are short
        self.assertAlmostEqual(float(np.sum(w * g) / np.sum(w)), float(g0.mean()), delta=0.06)
        p_short = float(np.sum(w * (g < 0.8)) / np.sum(w))
        self.assertAlmostEqual(p_short, float(np.mean(g0 < 0.8)), delta=0.004)
        r = imp.records[0]
        self.assertEqual(r["proposal"]["id"], "short_gaps")
        self.assertEqual(r["sampler"]["plugins"], ["importance"])
        self.assertEqual(check(r), [])
        self.assertTrue(math.isclose(r["weight"], math.exp(r["log_weight"])))

    def test_the_user_defined_importance_type_is_the_same_draw(self):
        p = self.d.dist("""<Stochastic numberOfTestRuns="5" randomSeed="3">
          <StochasticDistribution parameterName="gap">
            <UserDefinedDistribution type="scensim.sampler:importance">q.yaml</UserDefinedDistribution>
          </StochasticDistribution></Stochastic>""", name="i.xosc")
        a = Sampler.from_file(p).draw()
        b = Sampler.from_file(self.p, proposal=self.d.path / "q.yaml").draw(n=5)
        self.assertEqual([r["values"] for r in a.records], [r["values"] for r in b.records])
        self.assertEqual([r["log_weight"] for r in a.records],
                         [r["log_weight"] for r in b.records])

    def test_a_proposal_may_not_change_what_kind_of_variable_it_replaces(self):
        self.d.write("q.yaml", """proposal: 1
name: bad
base: m.yaml
variables:
  - {name: speed, poisson: {mean: 9}}
""")
        with self.assertRaisesRegex(SpecError, "the proposal makes speed discrete"):
            Sampler.from_file(self.p, proposal=self.d.path / "q.yaml")


class Example(unittest.TestCase):
    """The shipped CS1 example: each file draws, and every record checks against the scenario."""

    def test_every_example_draws_valid_records(self):
        sc = Scenario(EXAMPLES / "walker_dartout.xosc")
        for name in ("walker_dartout_dist", "walker_dartout_importance",
                     "walker_dartout_standard", "walker_dartout_cells"):
            b = Sampler.from_file(EXAMPLES / f"{name}.xosc").draw(n=50)
            self.assertTrue(b.records, name)
            for r in b.records:
                self.assertEqual(check(r, scenario=sc), [], name)
        r = Sampler.from_file(EXAMPLES / "walker_dartout_dist.xosc").draw(n=1).records[0]
        self.assertEqual(r["values"]["trigger_distance"],
                         r["values"]["ego_speed"] * r["values"]["ttc_entry"])
        self.assertEqual(r["derived"], ["trigger_distance"])
        self.assertEqual(r["cell"]["occluder"], "van")

    def test_a_seed_gives_the_same_bits_in_every_python(self):
        """The same 50 draws (values, seeds, log-weights) under numpy 1.x and 2.x, Python 3.10
        and 3.12: just test runs this in the system Python and in Isaac's. The mixture is
        summed in a fixed order, not by BLAS, for this. Update the digest only on purpose (the
        example's files or the sampler's streams changed)."""
        import hashlib
        from scensim_sampler.record import canonical
        b = Sampler.from_file(EXAMPLES / "walker_dartout_importance.xosc").draw(n=50)
        got = hashlib.sha256(canonical([[r["values"], r["seeds"], r["log_weight"]]
                                        for r in b.records]).encode()).hexdigest()
        self.assertEqual(got, "ea28b5b67d775526f9b91304310f6b8ec5ede005f129f40a04ff86312416a0f6")

    def test_the_example_model_says_it_is_invented(self):
        text = (EXAMPLES / "models" / "walker_dartout.yaml").read_text()
        self.assertIn("INVENTED FOR ILLUSTRATION, NOT FITTED FROM DATA", text)
        self.assertIn("invented for illustration, not fitted from data", text)


if __name__ == "__main__":
    unittest.main()
