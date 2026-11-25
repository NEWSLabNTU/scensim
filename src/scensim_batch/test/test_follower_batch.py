"""The car-follower in the batch (092 K13): 092's platoon case (k13_platoon_idm.xosc) compiled
and run on test_core's kinematic stand-ins (a straight world, a point-mass ego): the follower,
scensim.behaviour's idm_follower, holds its lane anchor and follows the scripted lead, which
brakes to rest."""
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
    import torch
    from sim_vehicle_ecu import batch as ecu_batch
    from test_core import DT, Accel, PointMass, StraightWorld, cmds
except ImportError:
    torch = None

CASE = HERE.parents[1] / "scensim_sampler" / "examples" / "cases" / "k13_platoon_idm.xosc"
# the straight world's lane 34513 as a resolved K9 lane anchor: y = 0, x along it
LANE = {"kind": "lane", "length": 400.0, "speed_limit": 15.0,
        "x": [float(x) for x in range(0, 401, 5)], "y": [0.0] * 81}


def records(n, **values):
    return [{"values": dict(values), "seeds": {"scenario": 100 + i}} for i in range(n)]


@unittest.skipIf(torch is None, "no torch or no sim_vehicle_ecu")
class Follower(unittest.TestCase):
    def run_of(self, recs, anchors=None):
        from scensim_batch import compile as C, core
        c = C.compile_scenario(CASE, recs, StraightWorld())
        comp = ecu_batch.load_batch(Accel, {}, {}, [7] * len(recs))
        return c, core.BatchRun(c, StraightWorld(), PointMass(c.n), comp, model_dt=DT,
                                anchors={"straight": LANE} if anchors is None else anchors)

    def test_it_compiles_as_a_model_with_its_lane(self):
        c, run = self.run_of(records(2))
        f = c.index("follower")
        self.assertEqual(c.entities[f].role, "model")
        self.assertEqual(c.entities[f].model["entry"], "scensim.behaviour:idm_follower")
        self.assertEqual(run.models.anchors[0][0]["lane"]["length"], 400.0)

    def test_a_lane_the_map_does_not_have_is_refused_by_name(self):
        with self.assertRaisesRegex(ValueError, "lane 'straight': no such anchor"):
            self.run_of(records(1), anchors={"other": LANE})

    def test_its_first_command_is_pending_after_reset_and_moves_it_at_step_1(self):
        """Issue 165: the model decides on the reset observation, so its first command is
        pending and its event recorded before any step; the entity stays put at reset and
        first moves at step 1, as on seats and as SSv2's own NPCs first move."""
        c, run = self.run_of(records(1))
        f = c.index("follower")
        obs = run.reset()
        j = run.models.idx.index(f)
        self.assertIsNotNone(run.models.pending[j])
        self.assertGreater(float(run.models.pending[j]["speed"][0]), 0.0)
        self.assertEqual(int(obs["model_events"]["follower"][0]), 1)     # follow, at step 0
        x0 = float(obs["x"][0, f])
        self.assertEqual(x0, float(c.x[0, f]))
        obs = run.step(cmds(c.n, 0.0), DT)
        self.assertNotEqual(float(obs["x"][0, f]), x0)

    def test_a_model_without_a_step_to_decide_over_is_refused_at_reset(self):
        from scensim_batch import compile as C, core
        c = C.compile_scenario(CASE, records(1), StraightWorld())
        comp = ecu_batch.load_batch(Accel, {}, {}, [7])
        run = core.BatchRun(c, StraightWorld(), PointMass(c.n), comp,
                            anchors={"straight": LANE})
        with self.assertRaisesRegex(ValueError, "model_dt"):
            run.reset()

    def test_it_follows_the_lead_to_rest_and_stops_behind_it(self):
        """The follower starts at rest 25.3 m (rear to its front) behind a lead at 12 m/s,
        catches up under IDM (a 1.5 m/s^2, toward the lane's 15 m/s), and stops behind the
        lead, which brakes to rest at 8 s; a larger time gap keeps it farther back while it
        follows."""
        c, run = self.run_of(records(2, time_gap=0.8) + records(2, time_gap=2.4))
        n, f, l = c.n, c.index("follower"), c.index("lead")
        obs = run.reset()
        gaps = []
        evs = [obs["model_events"]["follower"].clone()]   # its first decision, at reset (165)
        for k in range(int(25.0 / DT)):
            obs = run.step(cmds(n, 0.0), DT)
            gaps.append((obs["x"][:, l] - obs["x"][:, f] - 4.7).clone())
            evs.append(obs["model_events"]["follower"].clone())
        gaps = torch.stack(gaps)
        ev = torch.stack(evs)
        from scensim.behaviour import follower as fm
        self.assertTrue(bool((gaps > 0.5).all()), float(gaps.min()))       # never touches
        at_brake = gaps[int(10.0 / DT)]     # as the lead brakes
        self.assertTrue(bool((at_brake[2:] > at_brake[:2]).all()), at_brake)
        self.assertTrue(bool((gaps[-1] < 4.0).all()), gaps[-1])             # stopped behind it
        self.assertTrue(bool((ev == fm.FOLLOW).any(0).all()))
        # the short time gap's pair is at rest by 20 s; the long one creeps up on s0 still
        self.assertTrue(bool((ev[:, :2] == fm.STOPPED).any(0).all()))
        rec = run.models.records()["follower"]
        self.assertEqual(rec[0]["parameter_set"]["name"], "zhang2024_highd_car")
        self.assertEqual(rec[0]["params"]["v0"], 15.0)
        self.assertEqual([r["params"]["T"] for r in rec], [0.8, 0.8, 2.4, 2.4])


def _with(xml, init="", story=""):
    """k13_platoon_idm.xosc with `init` appended to the follower's Init Private and `story` a
    ManeuverGroup naming the follower in the act (issue 175's cases)."""
    import re
    m = re.search(r'<Private entityRef="follower">(.*?)</Private>', xml, re.S)
    xml = xml[:m.end(1)] + init + xml[m.end(1):]
    if story:
        i = xml.index("<ManeuverGroup")
        xml = xml[:i] + story + xml[i:]
    return xml


def _speed(shape="step", target='<AbsoluteTargetSpeed value="11.0"/>'):
    return ('<PrivateAction><LongitudinalAction><SpeedAction><SpeedActionDynamics '
            f'dynamicsShape="{shape}" value="1" dynamicsDimension="time"/><SpeedActionTarget>'
            f'{target}</SpeedActionTarget></SpeedAction></LongitudinalAction></PrivateAction>')


@unittest.skipIf(torch is None, "no torch or no sim_vehicle_ecu")
class InitialSpeed(unittest.TestCase):
    """Issue 175: a model entity's Init step AbsoluteTargetSpeed is its speed at reset, in the
    batch only; any other Init action on it, and any Story action, is refused by name."""

    def compiled(self, xml, n=1):
        import tempfile
        from scensim_batch import compile as C
        f = Path(tempfile.mkdtemp()) / CASE.name
        f.write_text(xml)
        return C.compile_scenario(f, records(n), StraightWorld())

    def test_a_step_absolute_speed_starts_the_model_at_it_and_none_at_rest(self):
        from scensim_batch import agreement as A, core
        for xml, want in ((_with(CASE.read_text(), _speed()), 11.0), (CASE.read_text(), 0.0)):
            c = self.compiled(xml)
            run = core.BatchRun(c, StraightWorld(), PointMass(c.n),
                                ecu_batch.load_batch(Accel, {}, {}, [7]), model_dt=DT,
                                anchors={"straight": LANE})
            run.reset()
            j = run.models.idx.index(c.index("follower"))
            self.assertEqual(float(run.models.v[0, j]), want)
            self.assertEqual(A.batch_only(c), ["follower"] if want else [])

    def test_its_own_object_controller_is_not_an_action(self):
        c = self.compiled(CASE.read_text())    # the model's Controller in its definition
        self.assertEqual(c.entities[c.index("follower")].role, "model")

    def test_any_other_init_action_on_it_is_refused_by_name(self):
        from scensim_batch import compile as C
        ctrl = ('<PrivateAction><ControllerAction><ActivateControllerAction longitudinal="true"/>'
                '</ControllerAction></PrivateAction>')
        rel = ('<RelativeTargetSpeed entityRef="lead" value="0" speedTargetValueType="delta" '
               'continuous="false"/>')
        for init, what in ((_speed("linear"), "dynamicsShape 'linear'"),
                           (_speed(target=rel), "LongitudinalAction/SpeedAction"),
                           (ctrl, "ControllerAction/ActivateControllerAction")):
            with self.subTest(what=what):
                with self.assertRaisesRegex(C.CompileError, f"{what}.*on 'follower', a model "
                                            r"entity.*\(issue 175\)"):
                    self.compiled(_with(CASE.read_text(), init))

    def test_a_story_action_on_it_is_refused_by_name(self):
        from scensim_batch import compile as C
        lane = ('<LateralAction><LaneChangeAction><LaneChangeActionDynamics dynamicsShape="step" '
                'value="1" dynamicsDimension="time"/><LaneChangeTarget><RelativeTargetLane '
                'entityRef="follower" value="1"/></LaneChangeTarget></LaneChangeAction>'
                '</LateralAction>')
        speed = _speed()[len("<PrivateAction>"):-len("</PrivateAction>")]
        for action, what in ((speed, "a SpeedAction on 'follower', a model entity"),
                             (lane, "a LaneChangeAction on 'follower', a model entity")):
            mg = ('<ManeuverGroup name="m" maximumExecutionCount="1"><Actors '
                  'selectTriggeringEntities="false"><EntityRef entityRef="follower"/></Actors>'
                  '<Maneuver name="m"><Event name="m" priority="override"><Action name="m">'
                  f'<PrivateAction>{action}</PrivateAction></Action><StartTrigger>'
                  '<ConditionGroup><Condition name="m" delay="0" conditionEdge="none">'
                  '<ByValueCondition><SimulationTimeCondition value="1" rule="greaterThan"/>'
                  '</ByValueCondition></Condition></ConditionGroup></StartTrigger></Event>'
                  '</Maneuver></ManeuverGroup>')
            with self.subTest(what=what):
                with self.assertRaisesRegex(C.CompileError, what):
                    self.compiled(_with(CASE.read_text(), story=mg))


if __name__ == "__main__":
    unittest.main()
