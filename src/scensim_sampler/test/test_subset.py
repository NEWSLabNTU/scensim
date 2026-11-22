"""The compilable subset (roadmap 092 S2, docs/design/compilable-subset.md): the five case
studies' verdicts, a refusal per seats and derived row, the XML path of a refusal, the ego as
the batch's policy or refused, distributions read through, and SSv2's own example scenarios
measured (skipped without the submodule)."""
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scensim_sampler import subset  # noqa: E402
from scensim_sampler.cli import main  # noqa: E402

CASES = Path(__file__).resolve().parents[1] / "examples" / "cases"
SSV2 = Path(__file__).resolve().parents[3] / "src" / "scenario_simulator_v2"

BASE = """<?xml version="1.0"?>
<OpenSCENARIO>
  <ParameterDeclarations>{params}</ParameterDeclarations>
  <Entities>
    <ScenarioObject name="ego"><Vehicle name="c"/><ObjectController><Controller name="ego">
      <Properties><Property name="isEgo" value="true"/></Properties></Controller>
    </ObjectController></ScenarioObject>
    <ScenarioObject name="cone"><MiscObject name="cone"/></ScenarioObject>
    {entities}
  </Entities>
  <Storyboard>
    <Init><Actions>{init}</Actions></Init>
    <Story name="s"><Act name="a"><ManeuverGroup name="g"><Actors/><Maneuver name="m">
      <Event name="e"><Action name="x">{action}</Action>
        <StartTrigger><ConditionGroup><Condition name="c">{condition}</Condition>
        </ConditionGroup></StartTrigger></Event></Maneuver></ManeuverGroup></Act></Story>
    <StopTrigger/>
  </Storyboard>
</OpenSCENARIO>
"""
SPEED = ("<PrivateAction><LongitudinalAction><SpeedAction><SpeedActionDynamics/>"
         "<SpeedActionTarget><AbsoluteTargetSpeed value='3'/></SpeedActionTarget></SpeedAction>"
         "</LongitudinalAction></PrivateAction>")
TIME = "<ByValueCondition><SimulationTimeCondition value='1' rule='greaterThan'/></ByValueCondition>"


def scenario(d, params="", entities="", init="", action=SPEED, condition=TIME, name="s.xosc"):
    p = Path(d) / name
    p.write_text(BASE.format(params=params, entities=entities, init=init, action=action,
                             condition=condition))
    return p


class CaseStudies(unittest.TestCase):
    def verdict(self, name, ego="policy"):
        return subset.check(CASES / f"{name}.xosc", ego=ego)

    def test_a_named_lane_id_is_refused_with_the_binding_to_use(self):
        """SSv2 reads a laneId as a lanelet's id: CS7's old laneId="exit_n" ran nowhere (092
        K9b); a $parameter bound to the world's anchor, or a number, is what runs."""
        with tempfile.TemporaryDirectory() as d:
            for f in ("cs7_cyclist_low_sun.xosc", "cs7_cyclist_low_sun_dist.xosc"):
                shutil.copy(CASES / f, Path(d) / f)
            shutil.copytree(CASES / "models", Path(d) / "models")
            p = Path(d) / "cs7_cyclist_low_sun.xosc"
            self.assertFalse(any("laneId" in r["construct"]
                                 for r in subset.check(p).refusals))
            p.write_text(p.read_text().replace('laneId="$exit_lane"', 'laneId="exit_n"'))
            r = [r for r in subset.check(p).refusals if "laneId" in r["construct"]]
            self.assertEqual(len(r), 1)
            self.assertEqual(r[0]["class"], subset.UNIMPLEMENTED)
            self.assertIn("exit_n.lanelet_at(<s>)", r[0]["fix"])
            p.write_text(p.read_text().replace('laneId="exit_n"', 'laneId="6583"'))
            self.assertFalse(any("laneId" in r["construct"]
                                 for r in subset.check(p).refusals))

    def test_cs6_conditions_its_per_sample_vehicle_class_on_per_slot_assets(self):
        """093 D7 gap 6: CS6's stopped car is `vehicleCategory="$stopped_kind"`. A batch can
        vary it only with an asset per value in every slot, so the checker names the parameter
        and its values (the joint model's, read through the distribution) as a condition."""
        import shutil
        with tempfile.TemporaryDirectory() as d:
            for f in ("cs6_cut_out_stopped_car.xosc", "cs6_cut_out_stopped_car_dist.xosc"):
                shutil.copy(CASES / f, d)
            shutil.copytree(CASES / "models", Path(d) / "models")
            dist = subset.check(Path(d) / "cs6_cut_out_stopped_car_dist.xosc")
            self.assertTrue(dist.compiles)
            got = [c for c in dist.conditions if "$stopped_kind" in c]
            self.assertEqual(got, [
                "Vehicle vehicleCategory $stopped_kind (values car, truck, motorbike): "
                + subset.PER_SLOT_ASSETS])
            # the scenario alone knows only its declared default
            alone = subset.check(Path(d) / "cs6_cut_out_stopped_car.xosc")
            self.assertIn("Vehicle vehicleCategory $stopped_kind (drawn per sample, declared "
                          "'car'): " + subset.PER_SLOT_ASSETS, alone.conditions)
            # a literal class is no condition
            p = Path(d) / "cs6_cut_out_stopped_car.xosc"
            p.write_text(p.read_text().replace('vehicleCategory="$stopped_kind"',
                                               'vehicleCategory="truck"'))
            self.assertFalse([c for c in subset.check(p).conditions if "per-slot assets" in c])

    def test_cs1_compiles_with_its_trigger_derived_and_refuses_the_ttc_form(self):
        v = self.verdict("cs1_walker_dartout")
        self.assertTrue(v.compiles)
        self.assertEqual(v.conditions, ["behaviour model scensim.behaviour:gap_acceptance_walker:"
                                        " a batched form of the model"])
        t = self.verdict("cs1_walker_dartout_ttc")
        r = t.refusals[0]
        self.assertEqual((r["class"], r["construct"]), ("derived", "TimeToCollisionCondition"))
        self.assertIn("DistanceCondition on a parameter the sampler derives", r["fix"])
        self.assertTrue(r["at"].startswith("/OpenSCENARIO/Storyboard/Story[@name='main']/"
                                           "Act[@name='act']/ManeuverGroup[@name='dart']/"))
        self.assertTrue(r["at"].endswith("/EntityCondition/TimeToCollisionCondition"))

    def test_cs2_compiles_if_the_slot_has_a_camera_for_night(self):
        v = self.verdict("cs2_lead_brakes_wet_night")
        self.assertTrue(v.compiles)
        self.assertIn("world knob illumination=night: a slot camera (illumination), and its "
                      "render time", v.conditions)
        self.assertFalse(any("surface" in c for c in v.conditions))   # a material: batch

    def test_cs3_compiles_with_the_ego_as_policy_and_is_refused_with_its_autopilot(self):
        v = self.verdict("cs3_stale_map")
        self.assertTrue(v.compiles)
        self.assertTrue(v.line().startswith("compiles with the ego replaced by the batch's "
                                            "policy; the scenario's own autopilot does not "
                                            "run in a batch"))
        self.assertIn(subset.PILOT_PARAM, v.notes)
        s = self.verdict("cs3_stale_map", ego="seats")
        self.assertEqual(s.refusals[0]["construct"], "the ego's autopilot")

    def test_cs4_compiles_with_the_fault_as_a_mask(self):
        v = self.verdict("cs4_lidar_dropout_cutin")
        self.assertTrue(v.compiles)
        self.assertEqual(v.counts.get("batch", 0) >= 1, True)

    def test_cs5s_fog_profile_runs_on_seats_only(self):
        """CS5's fog is a knob profile (092 K9), which the bridge applies each frame: a batch
        has no per-slot renderer for it, refused by name."""
        v = self.verdict("cs5_fog_mid_route")
        self.assertFalse(v.compiles)
        r = v.refusals[0]
        self.assertEqual((r["class"], r["construct"]), ("seats", "world knob visibility as a "
                                                                 "profile"))
        self.assertIn("applied by the bridge each frame", r["reason"])



class Static(unittest.TestCase):
    """scenario-description.md 2a, gap 4: a vehicle that never moves (scensim.static with SSv2's
    maxSpeed 0) is a batch prop with no behaviour condition; a motion action on it, or a static
    one SSv2 would not hold at rest, is refused by name."""

    def cs6(self, d, edit=lambda s: s):
        import shutil
        for f in ("cs6_cut_out_stopped_car.xosc", "cs6_cut_out_stopped_car_dist.xosc"):
            shutil.copy(CASES / f, d)
        shutil.copytree(CASES / "models", Path(d) / "models")
        p = Path(d) / "cs6_cut_out_stopped_car.xosc"
        p.write_text(edit(p.read_text()))
        return Path(d) / "cs6_cut_out_stopped_car_dist.xosc"

    def test_cs6s_stopped_car_is_a_prop_with_no_behaviour_condition(self):
        # the lead given a behaviour model, so a default-controller condition could only be
        # the stopped car's
        lead = '<Property name="isBlind" value="true"/>'
        with tempfile.TemporaryDirectory() as d:
            v = subset.check(self.cs6(d, lambda s: s.replace(
                lead, lead + '<Property name="model" value="scensim.behaviour:lead"/>')))
            self.assertTrue(v.compiles)
            self.assertEqual(v.static, {"stopped"})
            self.assertFalse([c for c in v.conditions if c.startswith("SSv2's default")])
            self.assertIn("scensim.static: " + subset.EXECUTOR_PENDING_REASON, v.conditions)
            self.assertIn("behaviour model scensim.behaviour:lead: a batched form of the model",
                          v.conditions)

    def test_cs6s_blind_lead_needs_lane_following_alone(self):
        """093 gap 5: SSv2's isBlind turns see_around off, so FollowLane reads no other entity;
        the condition is lane following alone, executor pending until scensim_batch passes it
        to its vehicles."""
        with tempfile.TemporaryDirectory() as d:
            v = subset.check(self.cs6(d))
            self.assertTrue(v.compiles)
            self.assertIn("SSv2's default controller, blind: " + subset.BLIND_REASON, v.conditions)
            self.assertIn("isBlind: " + subset.EXECUTOR_PENDING_REASON, v.conditions)
            # the lead is CS6's only default-controlled entity: no whole-traffic condition
            self.assertNotIn("SSv2's default controller: " + subset.DEFAULT_REASON, v.conditions)
        for value in ("false", "0"):
            with tempfile.TemporaryDirectory() as d:
                v = subset.check(self.cs6(d, lambda s: s.replace(
                    '<Property name="isBlind" value="true"/>',
                    f'<Property name="isBlind" value="{value}"/>')))
                self.assertIn("SSv2's default controller: " + subset.DEFAULT_REASON, v.conditions)
                self.assertFalse([c for c in v.conditions if "blind" in c])

    def test_a_state_condition_on_a_repeating_groups_maneuver_is_executor_pending(self):
        """SSv2's ManeuverGroup::start restarts its maneuvers on every execution; the batch does
        not, so a state condition on such a maneuver is executor pending (as its compiler)."""
        import re
        cond = ('<StoryboardElementStateCondition storyboardElementType="maneuver" '
                'storyboardElementRef="{m}" state="completeState"/>')
        for count, pending in (("1", False), ("2", True), ("$reps", True)):
            def edit(s, count=count):
                s = s.replace('<ManeuverGroup name="cut_out" maximumExecutionCount="1">',
                              f'<ManeuverGroup name="cut_out" maximumExecutionCount="{count}">')
                name = re.search(r'<Maneuver name="([^"]+)"', s).group(1)
                assert "<ParameterDeclarations>" in s and "<StopTrigger>" in s
                s = s.replace("<ParameterDeclarations>",
                              '<ParameterDeclarations><ParameterDeclaration name="reps" '
                              'parameterType="unsignedInt" value="3"/>', 1)
                # a condition on the maneuver, as a second group of the storyboard's StopTrigger
                return s.replace("<StopTrigger>", "<StopTrigger><ConditionGroup><Condition "
                                 'name="m_done" delay="0" conditionEdge="none"><ByValueCondition>'
                                 + cond.format(m=name) + "</ByValueCondition></Condition>"
                                 "</ConditionGroup>", 1)
            with tempfile.TemporaryDirectory() as d:
                v = subset.check(self.cs6(d, edit))
                hit = [c for c in v.conditions if "a state condition on maneuver" in c]
                self.assertEqual(bool(hit), pending, (count, v.conditions))
                if pending:
                    want = "3" if count == "$reps" else count
                    self.assertIn(f"of a ManeuverGroup of {want} executions: "
                                  + subset.EXECUTOR_PENDING_REASON, hit[0])

    def test_a_static_entity_needs_maxspeed_0(self):
        with tempfile.TemporaryDirectory() as d:
            dist = self.cs6(d, lambda s: s.replace('<Property name="maxSpeed" value="0"/>', ""))
            with self.assertRaisesRegex(subset.SubsetError, "stopped is scensim.static but its "
                                        "controller's maxSpeed is None"):
                subset.check(dist)

    def test_a_motion_action_on_a_static_entity_is_refused(self):
        speed = ('<Private entityRef="stopped"><PrivateAction><TeleportAction>')
        move = ('<Private entityRef="stopped"><PrivateAction><LongitudinalAction><SpeedAction>'
                '<SpeedActionDynamics dynamicsShape="step" value="0" dynamicsDimension="time"/>'
                '<SpeedActionTarget><AbsoluteTargetSpeed value="3"/></SpeedActionTarget>'
                '</SpeedAction></LongitudinalAction></PrivateAction></Private>' + speed)
        with tempfile.TemporaryDirectory() as d:
            dist = self.cs6(d, lambda s: s.replace(speed, move))
            with self.assertRaisesRegex(subset.SubsetError, "SpeedAction at .* moves stopped, "
                                        "which is scensim.static"):
                subset.check(dist)
        # in a story, as an actor of the maneuver group
        actor = '<EntityRef entityRef="lead"/>'
        with tempfile.TemporaryDirectory() as d:
            dist = self.cs6(d, lambda s: s.replace(actor, actor + '<EntityRef entityRef="stopped"/>'))
            with self.assertRaisesRegex(subset.SubsetError, "LaneChangeAction at .* moves stopped"):
                subset.check(dist)


class EntityClass(unittest.TestCase):
    """093 D7 gap 6 beyond CS6: every class and model attribute, `${p}`, and a catalog
    entry, each a condition naming the parameter; a deterministic set's values listed."""

    def test_every_class_attribute_with_a_parameter_is_a_condition(self):
        entities = (
            '<ScenarioObject name="w"><Pedestrian name="w" pedestrianCategory="pedestrian" '
            'model="${walker}"/></ScenarioObject>'
            '<ScenarioObject name="b"><MiscObject name="b" miscObjectCategory="$prop"/>'
            '</ScenarioObject>'
            '<ScenarioObject name="t"><CatalogReference catalogName="vehicles" '
            'entryName="$kind"/></ScenarioObject>')
        params = ('<ParameterDeclaration name="walker" parameterType="string" value="w1"/>'
                  '<ParameterDeclaration name="prop" parameterType="string" value="barrier"/>'
                  '<ParameterDeclaration name="kind" parameterType="string" value="sedan"/>')
        with tempfile.TemporaryDirectory() as d:
            sc = scenario(d, params=params, entities=entities)
            v = subset.check(sc)
            got = sorted(c.split(":")[0] for c in v.conditions if "per-slot assets" in c)
            self.assertEqual(got, [
                "CatalogReference entryName $kind (drawn per sample, declared 'sedan')",
                "MiscObject miscObjectCategory $prop (drawn per sample, declared 'barrier')",
                "Pedestrian model $walker (drawn per sample, declared 'w1')"])
            dist = Path(d) / "d.xosc"
            dist.write_text(
                '<OpenSCENARIO><ParameterValueDistribution><ScenarioFile filepath="s.xosc"/>'
                '<Deterministic><DeterministicSingleParameterDistribution parameterName="kind">'
                '<DistributionSet><Element value="sedan"/><Element value="van"/>'
                '</DistributionSet></DeterministicSingleParameterDistribution></Deterministic>'
                '</ParameterValueDistribution></OpenSCENARIO>')
            self.assertIn("CatalogReference entryName $kind (values sedan, van): "
                          + subset.PER_SLOT_ASSETS, subset.check(dist).conditions)


class Rows(unittest.TestCase):
    def refused(self, construct, **kw):
        with tempfile.TemporaryDirectory() as d:
            v = subset.check(scenario(d, **kw))
        self.assertFalse(v.compiles, v.line())
        self.assertEqual(v.refusals[0]["construct"], construct, v.line())
        return v

    def test_the_plain_scenario_compiles_unconditionally(self):
        with tempfile.TemporaryDirectory() as d:
            v = subset.check(scenario(d))
        self.assertTrue(v.compiles)
        self.assertEqual(v.conditions, [])

    def test_each_seats_row_is_refused_by_name(self):
        for construct, action in (
                ("AddEntityAction", "<GlobalAction><EntityAction entityRef='x'><AddEntityAction/>"
                                    "</EntityAction></GlobalAction>"),
                ("ParameterAction", "<GlobalAction><ParameterAction parameterRef='p'><SetAction "
                                    "value='1'/></ParameterAction></GlobalAction>"),
                ("ControllerAction", "<PrivateAction><ControllerAction><AssignControllerAction/>"
                                     "</ControllerAction></PrivateAction>"),
                ("VisibilityAction", "<PrivateAction><VisibilityAction graphics='false'/>"
                                     "</PrivateAction>"),
                ("CustomCommandAction V2ITrafficSignalStateAction(1, red)",
                 "<UserDefinedAction><CustomCommandAction type='V2ITrafficSignalStateAction(1, "
                 "red)'/></UserDefinedAction>")):
            with self.subTest(construct):
                v = self.refused(construct, action=action)
                self.assertEqual(v.refusals[0]["class"], "seats")
        udvc = ("<ByValueCondition><UserDefinedValueCondition name='{}' value='1' "
                "rule='equalTo'/></ByValueCondition>")
        for name in ("ego.currentState", "/count_up"):
            self.refused(f"UserDefinedValueCondition {name}", condition=udvc.format(name))
        with tempfile.TemporaryDirectory() as d:   # SSv2's built-in function: per slot
            for name in ("RelativeHeadingCondition(ego)", "RelativeHeadingCondition(ego, 34507, 50)"):
                self.assertTrue(subset.check(scenario(d, condition=udvc.format(name))).compiles)

    def test_what_ssv2_does_not_implement_is_refused_for_both(self):
        offset = ("<PrivateAction><LateralAction><LaneOffsetAction continuous='false'>"
                  "<LaneOffsetActionDynamics dynamicsShape='sinusoidal' maxLateralAcc='1'/>"
                  "<LaneOffsetTarget><AbsoluteTargetLaneOffset value='1'/></LaneOffsetTarget>"
                  "</LaneOffsetAction></LateralAction></PrivateAction>")
        v = self.refused("LaneOffsetAction", action=offset)
        self.assertEqual(v.refusals[0]["class"], "unimplemented")
        self.assertIn("SSv2 does not implement it", v.refusals[0]["reason"])
        self.refused("TraveledDistanceCondition", condition=(
            "<ByEntityCondition><TriggeringEntities triggeringEntitiesRule='any'><EntityRef "
            "entityRef='ego'/></TriggeringEntities><EntityCondition><TraveledDistanceCondition "
            "value='5'/></EntityCondition></ByEntityCondition>"))

    def test_every_batch_and_conditional_row_is_a_construct_ssv2_runs(self):
        doc = SSV2 / "docs/developer_guide/OpenSCENARIOSupport.md"
        if not doc.is_file():
            self.skipTest("no scenario_simulator_v2 submodule")
        import re
        sup = {}
        for line in doc.read_text().splitlines():
            m = re.match(r"^\| (\w+)\s+\| ([^|]+?)\s+\|", line)
            if m:
                sup[m.group(1)] = m.group(2)
        bad = [k for k, (cls, *_) in subset.TABLE.items()
               if cls in ("batch", "conditional") and "unimplemented" in sup.get(k, "")]
        self.assertEqual(bad, [])

    def test_a_knob_bound_by_property_is_a_world_knob(self):
        with tempfile.TemporaryDirectory() as d:
            p = scenario(d, params="<ParameterDeclaration name='light' parameterType='string' "
                                   "value='night'/>")
            p.write_text(p.read_text().replace(
                "<OpenSCENARIO>", "<OpenSCENARIO><FileHeader><Properties><Property "
                "name='scensim.knob.illumination' value='$light'/></Properties></FileHeader>", 1))
            v = subset.check(p)
        self.assertTrue(v.compiles)
        self.assertTrue(any(c.startswith("world knob illumination (bound to $light): a slot "
                                         "camera") for c in v.conditions), v.conditions)

    def test_a_parameter_set_before_the_run_is_fixed_for_the_slot(self):
        init = ("<GlobalAction><ParameterAction parameterRef='p'><SetAction value='1'/>"
                "</ParameterAction></GlobalAction>")
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(subset.check(scenario(d, init=init)).compiles)

    def test_a_second_autopilot_and_an_agent_pilot_are_seats_only(self):
        ent = ("<ScenarioObject name='npc'><Vehicle name='c'/><ObjectController><Controller "
               "name='Autoware'/></ObjectController></ScenarioObject>")
        self.assertEqual(self.refused("2 egos (ego, npc)", entities=ent).refusals[0]["class"],
                         "seats")
        ent = ("<ScenarioObject name='npc'><Vehicle name='c'/><ObjectController><Controller "
               "name='agent'/></ObjectController></ScenarioObject>")
        v = self.refused("controller agent", entities=ent)
        # an entity made an ego in Init (as SSv2's examples do) is an ego too
        init = ("<Private entityRef='npc'><PrivateAction><ControllerAction><AssignControllerAction>"
                "<Controller name='x'><Properties><Property name='isEgo' value='true'/>"
                "</Properties></Controller></AssignControllerAction></ControllerAction>"
                "</PrivateAction></Private>")
        ent2 = "<ScenarioObject name='npc'><Vehicle name='c'/></ScenarioObject>"
        self.refused("2 egos (ego, npc)", entities=ent2, init=init)
        # an external agent pilot assigned to a non-ego in Init stays seats
        agent = ("<Private entityRef='npc'><PrivateAction><ControllerAction><AssignControllerAction>"
                 "<Controller name='agent'/></AssignControllerAction></ControllerAction>"
                 "</PrivateAction></Private>")
        self.assertEqual(self.refused("ControllerAction", entities=ent2, init=agent)
                         .refusals[0]["class"], "seats")
        self.assertEqual(v.refusals[0]["class"], "seats")

    def test_an_unlisted_element_is_refused_not_admitted(self):
        v = self.refused("AppearanceAction", action="<PrivateAction><AppearanceAction>"
                                                   "<AnimationAction/></AppearanceAction>"
                                                   "</PrivateAction>")
        self.assertEqual(v.refusals[0]["class"], "unlisted")

    def test_an_unknown_command_is_refused_and_the_known_ones_compile(self):
        for t, ok in (("exitSuccess", True), ("exitFailure", True), ("scensim.fault", True),
                      ("echo hello", False), ("", False)):
            with self.subTest(t), tempfile.TemporaryDirectory() as d:
                a = f"<UserDefinedAction><CustomCommandAction type='{t}'/></UserDefinedAction>"
                self.assertEqual(subset.check(scenario(d, action=a)).compiles, ok)

    def test_a_distribution_is_read_through_to_its_scenario(self):
        with tempfile.TemporaryDirectory() as d:
            scenario(d, action="<PrivateAction><VisibilityAction/></PrivateAction>")
            dist = Path(d) / "dist.xosc"
            dist.write_text("<OpenSCENARIO><ParameterValueDistribution><ScenarioFile "
                            "filepath='s.xosc'/></ParameterValueDistribution></OpenSCENARIO>")
            v = subset.check(dist)
        self.assertEqual(v.refusals[0]["construct"], "VisibilityAction")
        self.assertTrue(v.path.endswith("s.xosc"))

    def test_ssv2_yaml_scenario_format_is_read_as_the_same_tree(self):
        y = ("OpenSCENARIO:\n  Entities:\n    ScenarioObject:\n      - name: npc\n"
             "        Vehicle: {name: c}\n  Storyboard:\n    Init:\n      Actions: {}\n"
             "    Story:\n      - name: s\n        Act:\n          - name: a\n"
             "            ManeuverGroup:\n              - name: g\n                Maneuver:\n"
             "                  - name: m\n                    Event:\n"
             "                      - name: e\n                        Action:\n"
             "                          - name: x\n                            PrivateAction:\n"
             "                              - VisibilityAction: {graphics: false}\n")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.yaml"
            p.write_text(y)
            v = subset.check(p)
        self.assertEqual(v.refusals[0]["construct"], "VisibilityAction")
        self.assertIn("Story[@name='s']/Act[@name='a']", v.refusals[0]["at"])


class Cli(unittest.TestCase):
    def test_exit_codes_lines_and_json(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as d, redirect_stdout(out):
            j = Path(d) / "v.json"
            rc = main(["compilable", str(CASES / "cs3_stale_map.xosc"),
                       str(CASES / "cs1_walker_dartout_ttc.xosc"), "--all", "--json", str(j)])
            doc = json.loads(j.read_text())
        self.assertEqual(rc, 1)
        self.assertIn("1 of 2 compile", out.getvalue())
        self.assertEqual(doc["format"], "scensim.compilable/1")
        self.assertEqual([s["compiles"] for s in doc["scenarios"]], [True, False])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["compilable", str(CASES / "cs4_lidar_dropout_cutin.xosc")]), 0)
            self.assertEqual(main(["compilable", "--ego", "seats",
                                   str(CASES / "cs4_lidar_dropout_cutin.xosc")]), 1)


@unittest.skipUnless((SSV2 / "test_runner").is_dir(), "no scenario_simulator_v2 submodule")
class Ssv2Examples(unittest.TestCase):
    def test_every_example_is_read_and_has_a_verdict(self):
        files = sorted((SSV2 / "test_runner/scenario_test_runner/scenario").glob("*.yaml")) + \
            sorted((SSV2 / "openscenario/openscenario_interpreter/example").glob("*.xosc"))
        verdicts = [subset.check(f) for f in files]
        s = subset.summary(verdicts)
        self.assertEqual(s["scenarios"], len(files))
        self.assertGreater(s["scenarios"], 50)
        self.assertEqual(s["compile"] + s["refused"], s["scenarios"])
        unlisted = [r for v in verdicts for r in v.refusals if r["class"] == "unlisted"]
        self.assertEqual(unlisted, [], "an element SSv2's examples use has no row")


if __name__ == "__main__":
    unittest.main()
