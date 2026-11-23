"""092 K10's walker agreement, its batch side without a simulator: TruthPlayback in place of the
ego's engine, Models reading the map-frame velocity, and agreement.py's readers of a seats run
(the ego's states, a commanded entity's pose a frame on, the attachment's decisions)."""
import importlib.util
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "scensim_sampler"))
sys.path.insert(0, str(HERE.parents[1] / "sim_vehicle_ecu"))
sys.path.insert(0, str(HERE.parents[1] / "scensim"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "scensim_launch" / "scripts"))   # gap_geometry

try:
    import torch
    from sim_vehicle_ecu import batch as ecu_batch
    from test_core import DT, Accel, PointMass, StraightWorld, cmds
    _spec = importlib.util.spec_from_file_location(
        "gap_trace", HERE.parents[1] / "scensim_launch" / "scripts" / "gap_trace.py")
    gt = importlib.util.module_from_spec(_spec)
    sys.modules.setdefault("gap_trace", gt)
    _spec.loader.exec_module(gt)
except ImportError:
    torch = None

CASE = HERE.parents[1] / "scensim_sampler" / "examples" / "cases" / "cs1_walker_gap_acceptance.xosc"
REC = [{"values": {}, "seeds": {"scenario": 100, "pilots": {"walker": 7}}}]


@unittest.skipIf(torch is None, "no torch, sim_vehicle_ecu or the trace reader")
class Playback(unittest.TestCase):
    def batch(self, backend, comp):
        from scensim_batch import compile as C, core
        c = C.compile_scenario(CASE, REC, StraightWorld())
        return c, core.BatchRun(c, StraightWorld(), backend, comp)

    def record(self, c, run, command, steps):
        from scensim_batch import agreement as A
        run.reset()
        rec = A.BatchRecorder(run)
        rec.record(run.obs)
        egos = [run.backend.state()]
        for _ in range(steps):
            rec.record(run.step(command, DT))
            egos.append(run.backend.state())
        return rec, egos

    def test_playing_a_run_back_gives_its_walker_decisions_and_triggers(self):
        """CS1 on the point-mass ego, then the same ego's states played back: the walker, its
        decisions and every element's steps are the same, step for step."""
        from scensim_batch.playback import NoComponent, TruthPlayback
        steps = 200
        c, run = self.batch(PointMass(1), ecu_batch.load_batch(Accel, {}, {}, [7]))
        ref, egos = self.record(c, run, cmds(1, 0.0), steps)
        states = [{"x": float(s["x"][0]), "y": float(s["y"][0]), "yaw": float(s["yaw"][0]),
                   "vx_map": float(s["v"][0] * torch.cos(s["yaw"][0])),
                   "vy_map": float(s["v"][0] * torch.sin(s["yaw"][0]))} for s in egos]
        c2, run2 = self.batch(TruthPlayback(states), ecu_batch.load_batch(NoComponent, {}, {},
                                                                          [0]))
        got, _ = self.record(c2, run2, cmds(1, 0.0), steps)
        self.assertTrue(ref.decisions["walker"])                 # it decided something
        self.assertEqual(got.decisions, ref.decisions)
        self.assertEqual(got.steps, ref.steps)
        for a, b in zip(ref.poses["walker"], got.poses["walker"]):
            self.assertLess(math.hypot(a[0] - b[0], a[1] - b[1]), 1e-12)

    def test_playback_holds_its_last_state_and_reports_body_frame_acceleration(self):
        from scensim_batch.playback import TruthPlayback
        b = TruthPlayback([{"x": 0, "y": 0, "yaw": math.pi / 2, "vx_map": 0.0, "vy_map": 1.0},
                           {"x": 0, "y": 0.05, "yaw": math.pi / 2, "vx_map": 0.0,
                            "vy_map": 2.0}])
        b.reset(None, None, None, None, None)
        self.assertEqual(float(b.state()["accel_x"][0]), 0.0)
        b.advance(0.05)
        st = b.state()
        self.assertAlmostEqual(float(st["accel_x"][0]), 20.0)    # along its heading, north
        self.assertAlmostEqual(float(st["accel_y"][0]), 0.0)
        b.advance(0.05)
        self.assertEqual(float(b.state()["y"][0]), 0.05)         # held

    def test_models_read_the_map_frame_velocity_when_the_backend_gives_it(self):
        """A sliding ego: v along the body is 10 m/s east, its map-frame velocity has 2 m/s north
        as well. The model is given the map frame's, as the seats attachment reads the truth."""
        from scensim_batch import core
        seen = {}

        class Stub:
            def step(self, obs, dt):
                seen["vx"], seen["vy"] = float(obs["ego_vx"][0]), float(obs["ego_vy"][0])
                z = torch.zeros(1, dtype=torch.float64)
                return {"speed": z, "heading": z, "accel_limit": z + 1}, torch.zeros(1)

        m = core.Models.__new__(core.Models)
        m.idx, m.models, m.events, m._prev_v, m.pending = [0], [Stub()], {}, None, [None]

        class Run:
            class c:
                n = 1
                entities = [type("E", (), {"name": "walker"})]
        m.run = Run
        z = torch.zeros(1, dtype=torch.float64)
        zz = torch.zeros(1, 1, dtype=torch.float64)       # [slots, model entities]
        m.x, m.y, m.yaw, m.v = zz.clone(), zz.clone(), zz.clone(), zz.clone()
        one = lambda v: torch.tensor([v], dtype=torch.float64)    # noqa: E731
        st = {"x": z, "y": z, "yaw": z, "v": one(10.0)}
        m.step(st, DT)
        self.assertEqual((seen["vx"], seen["vy"]), (10.0, 0.0))  # derived: the slide dropped
        m.step({**st, "vx_map": one(10.0), "vy_map": one(2.0)}, DT)
        self.assertEqual((seen["vx"], seen["vy"]), (10.0, 2.0))


@unittest.skipIf(torch is None, "no torch, sim_vehicle_ecu or the trace reader")
class LagAndView(unittest.TestCase):
    """092 K10's agreement run 1's fix: a model's command moves its entity a step later (the
    lockstep channel's lag 1), and SSv2's view of a model entity is two steps back."""

    def test_a_command_moves_the_entity_the_step_after_it(self):
        from scensim_batch import core

        class North:
            def step(self, obs, dt):
                one = torch.ones(1, dtype=torch.float64)
                return ({"speed": one, "heading": one * math.pi / 2, "accel_limit": one * 1e6},
                        torch.zeros(1))

        m = core.Models.__new__(core.Models)
        m.idx, m.models, m.events, m._prev_v, m.pending = [0], [North()], {}, None, [None]

        class Run:
            class c:
                n = 1
                entities = [type("E", (), {"name": "walker"})]
        m.run = Run
        zz = torch.zeros(1, 1, dtype=torch.float64)
        m.x, m.y, m.yaw, m.v = zz.clone(), zz.clone(), zz.clone(), zz.clone()
        z = torch.zeros(1, dtype=torch.float64)
        st = {"x": z, "y": z, "yaw": z, "v": z}
        m.step(st, 0.05)
        self.assertEqual(float(m.y[0, 0]), 0.0)                  # decided, not moved yet
        m.step(st, 0.05)
        self.assertAlmostEqual(float(m.y[0, 0]), 0.05)           # the first command's step

    def test_ssv2_sees_a_model_entity_when_it_sees_the_ego(self):
        from scensim_batch import core
        run = core.BatchRun.__new__(core.BatchRun)
        run.ego = 0
        run.models = type("M", (), {"idx": [2]})()
        cols = lambda *v: torch.tensor([v], dtype=torch.float64)  # noqa: E731
        obs = {k: cols(1.0, 5.0, 9.0) for k in ("x", "y", "yaw", "v")}
        obs["ego"] = {}
        seen = {k: torch.tensor([0.5]) for k in ("x", "y", "yaw", "v")}
        seen["ego"] = {}
        seen["models"] = {k: torch.tensor([[8.0]], dtype=torch.float64)
                          for k in ("x", "y", "yaw", "v")}
        view = run._as_ssv2_sees(obs, seen)
        self.assertEqual(view["x"].tolist(), [[0.5, 5.0, 8.0]])  # ego and model back, NPC now


def trace(n=5):
    st = lambda x, y, vx=0.0, vy=0.0: gt.EntityState(        # noqa: E731
        ssv2=gt.Pose6(x, y, 0, 0, 0, 0), sim_pose=gt.Pose6(x + 0.01, y, 0, 0, 0, 0.1),
        velocity=(vx, vy, 0.0), angular_velocity=(0.0, 0.0, 0.0), velocity_source="measured")
    t = gt.Trace(episode=gt.Episode(schema=3, episode=1, start_unix=0.0, npc_motion="tracked",
                                    map="Town01", step_time=0.05))
    for i, (name, kind, off) in enumerate((("ego", "ego", (1.387, 0.0, 0.0)),
                                           ("walker", "pedestrian", (0.0, 0.0, 0.0)))):
        t.entities[name] = gt.EntityHeader(
            frame=0, name=name, kind=kind,
            declared=gt.DeclaredBox(center=(1.416, 0.0, 0.744), dimensions=(4.792, 2.163, 1.488)),
            origin_offset=gt.OriginOffset(*off), sim_id=i, asset="t", asset_box=None, index=i)
    for k in range(n):
        f = 10 + k
        t.frames.append(gt.Frame(frame=f, sim_time=0.05 * k, sim_frame=100 + k,
                                 sim_time_ns=10**12 + 5 * 10**7 * k,
                                 entities={"ego": st(1.0 * k, 0.0, 8.0, 0.5),
                                           "walker": st(50.0, 0.1 * k)}))
    return t


@unittest.skipIf(torch is None, "no torch, sim_vehicle_ecu or the trace reader")
class SeatsSide(unittest.TestCase):
    def test_ego_states_are_the_entitys_pose_and_the_truths_velocity(self):
        """Issue 130: the body's pose with the truth's origin_offset taken back off."""
        from scensim_batch import agreement as A
        s = A.ego_states(trace(), 1, 3, "ego")
        dx = 1.387 * math.cos(0.1)
        self.assertEqual([round(x["x"], 6) for x in s],
                         [round(k + 0.01 - dx, 6) for k in (1, 2, 3)])
        self.assertAlmostEqual(s[0]["y"], -1.387 * math.sin(0.1), places=12)
        self.assertEqual((s[0]["vx_map"], s[0]["vy_map"], s[0]["yaw"]), (8.0, 0.5, 0.1))

    def test_the_played_back_egos_box_is_the_seats_truths_box_at_every_frame(self):
        """Issue 130: the batch's ego box (its entity pose and declared box) against
        scensim.truth.boxes on the seats truth, frame S + k against step k."""
        from scensim import truth as T
        from scensim_batch import agreement as A
        gg = T._module("gap_geometry")
        t = trace()
        h = t.entities["ego"].declared
        frames = sorted(t.frames, key=lambda f: f.frame)
        for k, st in enumerate(A.ego_states(t, 1, 4, "ego")):
            b = gg.ssv2_box(gg.Pose2D(st["x"], st["y"], st["yaw"]), h.center, h.dimensions)
            s = T.boxes(t, frames[1 + k])["ego"]
            self.assertLess(math.hypot(b.cx - s.cx, b.cy - s.cy), 1e-12, k)
            self.assertAlmostEqual(b.yaw, s.yaw, places=12)

    def test_a_commanded_entity_is_read_a_frame_on(self):
        from scensim_batch import agreement as A
        p = A.seats_poses(trace(), 1, 3, ["walker"], pose="sim", shift={"walker": 1})
        self.assertEqual([round(q[1], 6) for q in p["walker"]], [0.2, 0.3, 0.4])
        p = A.seats_poses(trace(), 1, 4, ["walker"], pose="sim", shift={"walker": 1})
        self.assertIsNone(p["walker"][-1])                       # past the truth's last frame

    def test_decisions_pair_by_the_step_whose_truth_they_read(self):
        from scensim_batch import agreement as A
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "decisions.jsonl"
            p.write_text("\n".join(json.dumps(o) for o in (
                {"frame": 12, "sim_frame": 102, "entity": "walker", "event": "reject"},
                {"frame": 13, "sim_frame": 103, "entity": "walker", "event": "go_after"})))
            seats = A.seats_decisions(p, 1, 10)
        self.assertEqual(seats, {"walker": [(1, "reject"), (2, "go_after")]})
        row = A.decisions_agree(seats, {"walker": [(1, "reject"), (2, "go_after")]})
        self.assertTrue(row["walker"]["agree"])
        row = A.decisions_agree(seats, {"walker": [(1, "reject"), (3, "go_after")]})
        self.assertFalse(row["walker"]["agree"])

    def test_the_record_is_the_runs_seed_and_parameters(self):
        from scensim_batch import agreement as A
        with tempfile.TemporaryDirectory() as d:
            Path(d, "result.json").write_text(json.dumps(
                {"scenario": {"seed": 31, "parameters": {"ttc_entry": 3.0}}}))
            self.assertEqual(A.run_record(d), {"seeds": {"scenario": 31},
                                               "values": {"ttc_entry": 3.0}})
            Path(d, "sample.json").write_text(json.dumps({"seeds": {"scenario": 5}}))
            self.assertEqual(A.run_record(d)["seeds"], {"scenario": 5})


@unittest.skipIf(torch is None, "no torch, sim_vehicle_ecu or the trace reader")
class FromTruth(unittest.TestCase):
    def test_a_seats_run_made_from_a_batch_run_agrees_with_lag_one(self):
        """A seats run written from a point-mass batch run as the seats side records one: the
        ego's and the walker's truth at frame first + S + k are the batch's step k (the batch
        applies a command a step later, K12's lag 1), a decision at step k written for truth
        frame first + S + k. agreement_run's --ego-from-truth then agrees exactly: walker error
        0, the same decisions at the same steps."""
        import argparse
        from scensim_batch import agreement as A
        sys.path.insert(0, str(HERE.parents[1] / "autoware_isaac_bridge" / "src" / "aib"))
        _s = importlib.util.spec_from_file_location("agreement_run",
                                                    HERE.parent / "scripts" / "agreement_run.py")
        ar = importlib.util.module_from_spec(_s)
        try:
            _s.loader.exec_module(ar)
        except ImportError as e:
            self.skipTest(f"agreement_run does not import here: {e}")
        steps, S, first = 160, 2, 10
        ref, egos = Playback.record(self, *Playback.batch(
            self, PointMass(1), ecu_batch.load_batch(Accel, {}, {}, [7])), cmds(1, 0.0), steps)
        es = lambda x, y, yaw=0.0, vx=0.0, vy=0.0: gt.EntityState(   # noqa: E731
            ssv2=gt.Pose6(x, y, 0, 0, 0, yaw), sim_pose=gt.Pose6(x, y, 0, 0, 0, yaw),
            velocity=(vx, vy, 0.0), angular_velocity=(0.0, 0.0, 0.0),
            velocity_source="measured")
        t = gt.Trace(episode=gt.Episode(schema=3, episode=1, start_unix=0.0,
                                        npc_motion="tracked", map="x", step_time=DT))
        for i, name in enumerate(("ego", "walker")):     # the body is the entity here
            t.entities[name] = gt.EntityHeader(
                frame=0, name=name, kind="ego" if i == 0 else "pedestrian",
                declared=gt.DeclaredBox(center=(0.0, 0.0, 0.0), dimensions=(1.0, 1.0, 1.0)),
                origin_offset=gt.OriginOffset(0.0, 0.0, 0.0), sim_id=i, asset="t",
                asset_box=None, index=i)
        n_frames = S + steps + 1
        w0 = ref.poses["walker"][0]
        for j in range(n_frames):
            k = j - S
            e = egos[min(max(k, 0), steps)]
            v, yaw = float(e["v"][0]), float(e["yaw"][0])
            ego = es(float(e["x"][0]), float(e["y"][0]), yaw, v * math.cos(yaw),
                     v * math.sin(yaw))
            # the batch applies the walker's command a step later, as the lockstep channel
            # does: its pose at step k is the seats walker's at frame S + k
            w = ref.poses["walker"][k] if 0 <= k <= steps else w0
            t.frames.append(gt.Frame(frame=first + j, sim_time=DT * j, sim_frame=100 + j,
                                     sim_time_ns=10**12 + int(DT * 1e9) * j,
                                     entities={"ego": ego, "walker": es(w[0], w[1], w[2])}))
        with tempfile.TemporaryDirectory() as d:
            att = Path(d, "attachments", "walker")
            att.mkdir(parents=True)
            att.joinpath("decisions.jsonl").write_text("".join(
                json.dumps({"frame": first + S + k, "sim_frame": 0, "entity": "walker",
                            "event": ev}) + "\n" for k, ev in ref.decisions["walker"]))
            Path(d, "result.json").write_text(json.dumps({"verdict": None}))
            Path(d, "rec.json").write_text(json.dumps(REC[0]))
            a = argparse.Namespace(world="", map="", record=str(Path(d, "rec.json")),
                                   route_points=121, attachment="", dump=None, truth_out=None,
                                   out=str(Path(d, "row.json")), scenario=str(CASE))
            import scensim_batch.world_lanelet as wl
            load = wl.LaneletWorld.load
            wl.LaneletWorld.load = staticmethod(lambda *x, **y: StraightWorld())
            try:
                ar.from_truth(a, Path(d), t, S, A)
            finally:
                wl.LaneletWorld.load = load
            row = json.loads(Path(d, "row.json").read_text())
        self.assertTrue(row["decisions"]["walker"]["agree"], row["decisions"])
        self.assertLess(row["trajectory"]["walker"]["max_m"], 1e-9)
        self.assertLess(row["trajectory"]["ego"]["max_m"], 1e-9)


if __name__ == "__main__":
    unittest.main()
