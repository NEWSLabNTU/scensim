"""K2.2c: the lazy ticks (BatchRun's steps between its host checks, where a device run skips no
branch and defers its checks) give the eager ones' results: test_storyboard's and test_core's
cases run again with every BatchRun lazy on the CPU (core.CPU_SYNC_EVERY 16). A case that
expects a check to raise at once is left to the eager run (LAZY_SKIP)."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import test_core  # noqa: E402
import test_storyboard  # noqa: E402

LAZY_SKIP = set()


def _lazy(cls):
    from scensim_batch import core

    def setUpClass(k):
        k._was = core.CPU_SYNC_EVERY
        core.CPU_SYNC_EVERY = 16
        super(lazy_cls, k).setUpClass()

    def tearDownClass(k):
        core.CPU_SYNC_EVERY = k._was
        super(lazy_cls, k).tearDownClass()

    lazy_cls = type(f"Lazy{cls.__name__}", (cls,), {
        "setUpClass": classmethod(setUpClass), "tearDownClass": classmethod(tearDownClass),
        "__module__": __name__})
    for name in LAZY_SKIP:
        if hasattr(lazy_cls, name):
            setattr(lazy_cls, name, unittest.skip("checks at once (eager only)")(
                getattr(lazy_cls, name)))
    return lazy_cls


for _mod in (test_storyboard, test_core):
    for _name, _obj in list(vars(_mod).items()):
        if (isinstance(_obj, type) and issubclass(_obj, unittest.TestCase)
                and _obj.__module__ == _mod.__name__):
            globals()[f"Lazy{_name}"] = _lazy(_obj)

if __name__ == "__main__":
    unittest.main()


class LazyRepeatedLaneChange(unittest.TestCase):
    """An event of two executions whose lane change runs again after a check (243): its action
    is COMPLETE between the two, but the event is back in STANDBY, so it is not settled; the
    lazy run starts the change twice, as the eager run does, and ends on the same pose."""

    def run_of(self, sync_every):
        from sim_vehicle_ecu import batch as ecu_batch
        from scensim_batch import compile as C, core, storyboard as sbmod
        from test_core import DT, PointMass, StraightWorld, cmds
        from test_core import Accel
        from test_storyboard import NIGHT, case, event, lane_change, story

        def cond(t):
            return (f'<ConditionGroup><Condition name="c{t}" delay="0" conditionEdge="rising">'
                    f'<ByValueCondition><SimulationTimeCondition value="{t}" rule="greaterThan"/>'
                    '</ByValueCondition></Condition></ConditionGroup>')
        trig = f'<StartTrigger>{cond(0.5)}{cond(2.0)}</StartTrigger>'
        ev = event("lc", lane_change(target='<RelativeTargetLane entityRef="lead" value="-1"/>'),
                   trig, count=2)
        p = case(story(ev), params='<ParameterDeclaration name="lc_t" parameterType="double" '
                                   'value="1"/>')
        text = p.read_text()
        i = text.index('<Private entityRef="lead">')
        p.write_text(text[:i] + text[i:].replace('laneId="34513"', 'laneId="34514"', 1))
        c = C.compile_scenario(p, [{"values": {}}], StraightWorld(), provides=NIGHT)
        c.y[:, c.index("ego")] = -14.0
        run = core.BatchRun(c, StraightWorld(), PointMass(1),
                            ecu_batch.load_batch(Accel, {}, {}, [1]), route_length=2000.0,
                            sync_every=sync_every)
        starts = []
        begin = sbmod.LaneChangeAction._begin

        def counting(self_, *a, **k):
            starts.append(run._ticks)
            return begin(self_, *a, **k)
        sbmod.LaneChangeAction._begin = counting
        try:
            run.reset()
            for _ in range(80):
                obs = run.step(cmds(1, 0.0), DT)
        finally:
            sbmod.LaneChangeAction._begin = begin
        return starts, float(obs["y"][0, c.index("lead")])

    def test_the_second_execution_starts_its_change_on_both(self):
        eager, y_eager = self.run_of(1)
        lazy, y_lazy = self.run_of(16)
        self.assertEqual(len(eager), 2, eager)
        self.assertEqual(lazy, eager)
        self.assertEqual(y_lazy, y_eager)
