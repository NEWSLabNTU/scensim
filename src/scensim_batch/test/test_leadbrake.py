"""094 P4's episode (scenarios/projects/leadbrake_rl): its distribution is stock's
(bench/p4_leadbrake's RANGES, drawn as its reset_episode draws them), it compiles on the task's
straight world, and a reset gives each slot its record's storyboard (Storyboard.rebind)."""
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
REPO = HERE.parents[2]
DIST = REPO / "scenarios" / "projects" / "leadbrake_rl" / "scenarios" / "leadbrake_dist.xosc"
CATALOGS = {"vehicles": str(REPO / "src" / "sim_vehicle_spec" / "catalogs" / "vehicles.xosc")}
try:
    import torch
    from scensim_batch import compile as C, start_pool as SP
    from scensim_batch.tasks import leadbrake as LB
except ImportError:      # pragma: no cover
    torch = None


def ks_uniform(xs, lo, hi):
    """The one-sample Kolmogorov-Smirnov statistic of xs against U[lo, hi]."""
    xs = sorted(xs)
    n = len(xs)
    return max(max((i + 1) / n - (x - lo) / (hi - lo), (x - lo) / (hi - lo) - i / n)
               for i, x in enumerate(xs))


def ks_two(a, b):
    a, b = sorted(a), sorted(b)
    i = j = 0
    d = 0.0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            i += 1
        else:
            j += 1
        d = max(d, abs(i / len(a) - j / len(b)))
    return d


@unittest.skipIf(torch is None or not DIST.exists(), "no torch, or no leadbrake_rl project")
class Distribution(unittest.TestCase):
    N = 10000

    @classmethod
    def setUpClass(cls):
        cls.pool = SP.StartPool(DIST, LB.straight_world(), seed=5, chunk=cls.N, background=False,
                                catalogs=CATALOGS)
        cls.eps = [LB.episode_from_record(r["values"]) for r in cls.pool.records[:cls.N]]

    def test_the_four_draws_are_stocks_uniforms(self):
        """133: each of stock's four marginals, KS against its U[lo, hi] at 10k draws (the 0.1 %
        critical value is 1.95 / sqrt(n) = 0.0195)."""
        crit = 1.95 / math.sqrt(self.N)
        for name, (lo, hi) in LB.RANGES.items():
            xs = [e[name] for e in self.eps]
            self.assertGreaterEqual(min(xs), lo, name)
            self.assertLessEqual(max(xs), hi, name)
            self.assertLess(ks_uniform(xs, lo, hi), crit, name)

    def test_the_gap_is_stocks_headway_times_speed(self):
        """The gap, front to rear (headway x speed), against stock's own sampler's (its
        reset_episode: torch's uniform_ per range) at 10k each, two-sample KS (0.1 %: 0.0276)."""
        g = torch.Generator().manual_seed(11)
        u = lambda lo, hi: torch.empty(self.N).uniform_(lo, hi, generator=g)  # noqa: E731
        stock = (u(*LB.RANGES["lead_speed"]) * u(*LB.RANGES["headway"])).tolist()
        ours = [e["headway"] * e["lead_speed"] for e in self.eps]
        self.assertLess(ks_two(ours, stock), 1.95 * math.sqrt(2 / self.N))

    def test_the_draws_are_independent(self):
        """Stock draws the four independently: their pairwise correlations are nil."""
        names = list(LB.RANGES)
        cols = torch.tensor([[e[k] for k in names] for e in self.eps], dtype=torch.float64)
        z = (cols - cols.mean(0)) / cols.std(0)
        r = (z.T @ z) / (len(cols) - 1)                # their correlation matrix
        off = r - torch.eye(len(names), dtype=torch.float64)
        self.assertLess(float(off.abs().max()), 4.0 / math.sqrt(self.N))

    def test_the_ego_starts_at_the_leads_speed_its_gap_behind(self):
        for r, e in zip(self.pool.records[:100], self.eps[:100]):
            v = r["values"]
            self.assertEqual(float(v["ego_speed"]), float(v["lead_speed"]))
            gap = float(v["lead_s"]) - LB.REAR - (LB.EGO_S + LB.FRONT)       # rear to front
            self.assertAlmostEqual(gap, e["headway"] * e["lead_speed"], places=9)


@unittest.skipIf(torch is None or not DIST.exists(), "no torch, or no leadbrake_rl project")
class Compile(unittest.TestCase):
    def test_it_compiles_on_the_straight_world_and_rebinds_per_slot(self):
        pool = SP.StartPool(DIST, LB.straight_world(), seed=2, chunk=8, background=False,
                            catalogs=CATALOGS)
        rows = pool.take(4)
        recs = [pool.record(r) for r in rows]
        c = C.compile_scenario(pool.scenario, recs, LB.straight_world(), catalogs=CATALOGS)
        sb = c.storyboard
        self.assertEqual(sb.params_live, {"onset_d", "decel"})
        pool.check_storyboard(sb)                                  # nothing compiled in
        ego, lead = c.index("ego"), c.index("lead")
        for k, r in enumerate(recs):
            v = r["values"]
            self.assertAlmostEqual(float(c.x[k, ego]), LB.EGO_S, places=6)
            self.assertAlmostEqual(float(c.x[k, lead]), float(v["lead_s"]), places=6)
            self.assertAlmostEqual(float(c.y[k, lead]), 0.0, places=9)
            self.assertAlmostEqual(float(c.speed[k, ego]), float(v["ego_speed"]), places=9)
        self.assertEqual(c.entities[lead].role, "default")         # SSv2's default vehicle
        fresh = [pool.record(r) for r in pool.take(4)]
        sb.rebind(fresh, [0, 1, 2, 3])
        c2 = C.compile_scenario(pool.scenario, fresh, LB.straight_world(), catalogs=CATALOGS)
        for (_, a), (_, b) in zip(sb._rebinds, c2.storyboard._rebinds):
            for x, y in zip(a, b):
                self.assertTrue(torch.equal(x, y))



@unittest.skipIf(torch is None or not DIST.exists(), "no torch, or no leadbrake_rl project")
class Resets(unittest.TestCase):
    def test_a_reset_gives_every_entity_its_records_init(self):
        """A reset slot's lead starts where its new record puts it, at its speed: the pool wrote
        the ego's Init alone, and the lead kept the slot's first record's (found before P4's
        first run). Here against a compile of the new records, and through BatchRun's reset."""
        from scensim_batch import core
        from sim_vehicle_ecu import batch as ecu_batch
        from test_core import Accel, PointMass
        world = LB.straight_world()
        pool = SP.StartPool(DIST, world, seed=9, chunk=12, background=False, catalogs=CATALOGS)
        first = pool.take(4)
        c = C.compile_scenario(pool.scenario, [pool.record(r) for r in first], world,
                               catalogs=CATALOGS)
        rows = pool.take(4)
        pool.write_init(c, [0, 1, 2, 3], rows)
        fresh = C.compile_scenario(pool.scenario, [pool.record(r) for r in rows], world,
                                   catalogs=CATALOGS)
        for name in ("x", "y", "yaw", "speed"):
            self.assertTrue(torch.equal(getattr(c, name).double(), getattr(fresh, name).double()),
                            name)
        lead = c.index("lead")
        comp = ecu_batch.load_batch(Accel, {}, {}, [1] * 4)
        run = core.BatchRun(c, world, PointMass(c.n), comp, route_length=LB.LANE_LENGTH)
        obs = run.reset()
        for k, r in enumerate(rows):
            v = pool.record(r)["values"]
            self.assertAlmostEqual(float(obs["x"][k, lead]), float(v["lead_s"]), places=6)
            self.assertAlmostEqual(float(obs["v"][k, lead]), float(v["lead_speed"]), places=9)


    def test_a_reset_gives_the_ego_its_records_route_goal(self):
        """243: the ego's route goal (Init's RoutingAction) is a record's too when it reads a
        sampled parameter: a variant whose ego acquires $lead_s's position, written per reset as
        a compile of the new records holds it."""
        import shutil
        import tempfile
        d = Path(tempfile.mkdtemp())
        shutil.copytree(DIST.parent, d / "scenarios")
        sc = d / "scenarios" / "leadbrake.xosc"
        text = sc.read_text()
        tele = ('<Private entityRef="ego">\n\t\t\t\t<PrivateAction><TeleportAction><Position>'
                '<LanePosition roadId="" laneId="1" s="5.0" offset="0" /></Position>'
                '</TeleportAction></PrivateAction>')
        self.assertIn(tele, text)
        sc.write_text(text.replace(tele, tele + '\n\t\t\t\t<PrivateAction><RoutingAction>'
                                   '<AcquirePositionAction><Position><LanePosition roadId="" '
                                   'laneId="1" s="$lead_s" offset="0" /></Position>'
                                   '</AcquirePositionAction></RoutingAction></PrivateAction>', 1))
        world = LB.straight_world()
        pool = SP.StartPool(d / "scenarios" / DIST.name, world, seed=9, chunk=12,
                            background=False, catalogs=CATALOGS)
        first = pool.take(4)
        c = C.compile_scenario(pool.scenario, [pool.record(r) for r in first], world,
                               catalogs=CATALOGS)
        self.assertTrue(c.goal_waypoints)
        rows = pool.take(4)
        pool.write_init(c, [0, 1, 2, 3], rows)
        fresh = C.compile_scenario(pool.scenario, [pool.record(r) for r in rows], world,
                                   catalogs=CATALOGS)
        for w, f in zip(c.goal_waypoints, fresh.goal_waypoints):
            for t, u in zip(w, f):
                self.assertTrue(torch.allclose(torch.as_tensor(t).double(),
                                               torch.as_tensor(u).double(), atol=1e-12))
        self.assertFalse(torch.allclose(torch.as_tensor(fresh.goal_waypoints[0][0]).double(),
                                        torch.as_tensor(C.compile_scenario(
                                            pool.scenario, [pool.record(r) for r in first],
                                            world, catalogs=CATALOGS).goal_waypoints[0][0])
                                        .double()))      # the records' goals do differ

    def test_an_env_compile_of_other_entities_is_refused(self):
        world = LB.straight_world()
        pool = SP.StartPool(DIST, world, seed=9, chunk=4, background=False, catalogs=CATALOGS)
        c = C.compile_scenario(pool.scenario, [pool.record(r) for r in pool.take(2)], world,
                               catalogs=CATALOGS)
        c.entities = list(reversed(c.entities))
        with self.assertRaisesRegex(SP.PoolError, "entities"):
            pool.write_init(c, [0, 1], pool.take(2))



@unittest.skipIf(torch is None or not DIST.exists(), "no torch, or no leadbrake_rl project")
class Replay(unittest.TestCase):
    """Stock's evaluator's episodes (--samples-out) replayed as the pool's records."""

    def test_a_stock_episode_is_the_record_the_model_derives(self):
        from scensim_sampler.sampler import Sampler
        recs = Sampler.from_file(DIST).draw(n=200, seed=5).records
        for r in recs:
            ep = LB.episode_from_record(r["values"])
            got = LB.record_from_episode(ep)["values"]
            for k, v in r["values"].items():
                self.assertAlmostEqual(got[k], v, places=9, msg=k)
            self.assertAlmostEqual(ep["headway"], r["latent"]["headway"], places=9)
            self.assertAlmostEqual(ep["onset"], r["latent"]["onset"], places=9)

    def test_the_pool_replays_the_file_in_order_then_round_again(self):
        import json
        import tempfile
        eps = [{"lead_speed": 8.0 + k, "headway": 1.0 + 0.3 * k, "decel": 3.0 + 0.5 * k,
                "onset": 40.0 + 10 * k, "success": k % 2 == 0, "end_reason": "time_out"}
               for k in range(5)]
        f = Path(tempfile.mkdtemp()) / "samples.json"
        f.write_text(json.dumps({"seed": 1, "conditions": 5, "keys": list(LB.KEYS),
                                 "episodes": eps}))
        recs, _ = LB.records_from_samples(f)
        from scensim_sampler.sampler import Sampler
        world = LB.straight_world()
        pool = SP.StartPool(DIST, world, seed=0, chunk=5, background=False, catalogs=CATALOGS,
                            sampler=SP.ReplaySampler(Sampler.from_file(DIST), recs))
        rows = pool.take(5)
        for k, row in enumerate(rows):
            got = LB.episode_from_record(pool.record(row)["values"])
            for key in LB.KEYS:
                self.assertAlmostEqual(got[key], eps[k][key], places=9)
            self.assertEqual(pool.record(row)["stock"]["success"], eps[k]["success"])
        more = pool.take(3)                    # a refill: the file again, its next round
        self.assertEqual([pool.record(r)["id"] for r in more], [r["id"] for r in recs[:3]])
        self.assertEqual(pool.record(more[0])["replay_round"], 1)
        bad = Path(tempfile.mkdtemp()) / "bad.json"
        bad.write_text(json.dumps({"keys": ["headway", "lead_speed"], "episodes": eps}))
        with self.assertRaisesRegex(ValueError, "not stock's"):
            LB.records_from_samples(bad)


def stock_lead(rear0, v0, decel, onset, steps, dt):
    """Stock's lead (mdp.py LeadCommand._update_command), from its reset: per policy step, it
    brakes when its rear is at or past the onset, then steps its speed and its rear."""
    s, v, vs, first = rear0, v0, [], None
    for k in range(steps):
        braking = s >= onset and v > 0.0
        if braking and first is None:
            first = k
        a = -decel if braking else 0.0
        v = max(v + a * dt, 0.0)
        s = s + v * dt
        vs.append(v)
    return vs, first


@unittest.skipIf(torch is None or not DIST.exists(), "no torch, or no leadbrake_rl project")
class Lead(unittest.TestCase):
    """243: the lead as SSv2's default vehicle under the storyboard against stock's own lead:
    the brake's rate and sign, and its first step, at stock's 20 Hz policy step; one lead starts
    past its onset (stock brakes it at once), one a step short of it."""

    CASES = [  # (lead_speed, headway, decel, onset)
        (10.0, 2.0, 5.0, 80.0),
        (14.0, 3.0, 3.0, 40.0),        # its rear starts at 45.8 m: past the onset
        (12.0, 2.5, 7.0, 34.2),        # 33.81 m: a step's travel (0.6 m) short of it
        (8.0, 1.0, 6.5, 119.0),
    ]

    def test_it_brakes_on_stocks_step_at_stocks_rate(self):
        from scensim_batch import core
        from sim_vehicle_ecu import batch as ecu_batch
        from test_core import Accel, PointMass, cmds
        recs = []
        for v, hw, dec, on in self.CASES:
            recs.append({"values": {"lead_speed": v, "ego_speed": v, "decel": dec,
                                    "lead_s": LB.EGO_S + hw * v + LB.FRONT + LB.REAR,
                                    "onset_d": LB.BEHIND + LB.EGO_S + on + LB.REAR}})
        world = LB.straight_world()
        pool = SP.StartPool(DIST, world, seed=1, chunk=4, background=False, catalogs=CATALOGS)
        c = C.compile_scenario(pool.scenario, recs, world, catalogs=CATALOGS)
        c.y[:, c.index("ego")] = 3.5          # beside the lane: the lead sees nothing ahead
        comp = ecu_batch.load_batch(Accel, {}, {}, [1] * len(recs))
        run = core.BatchRun(c, world, PointMass(c.n), comp, route_length=LB.LANE_LENGTH)
        lead = c.index("lead")
        dt, steps = 1.0 / 20.0, 600          # stock's 30 s episode
        run.reset()
        vs = []
        for _ in range(steps):
            obs = run.step(cmds(c.n, 0.0), dt)
            vs.append(obs["v"][:, lead].clone())
        vs = torch.stack(vs).double()
        for k, (v, hw, dec, on) in enumerate(self.CASES):
            want, first = stock_lead(LB.FRONT + hw * v, v, dec, on, steps, dt)
            ours = vs[:, k]
            fall = torch.nonzero(ours[1:] < ours[:-1] - 1e-9).flatten()
            got = int(fall[0]) + 1 if len(fall) else (0 if float(ours[0]) < v - 1e-9 else None)
            self.assertIsNotNone(got, f"case {k}: never braked")
            # a lead that starts past its onset: stock brakes it in the first step, ours a step
            # later, as SSv2 (its storyboard's first evaluation is a step after startNpcLogic,
            # 092 K2.4); a lead that reaches it, on stock's step
            late = 1 if LB.FRONT + hw * v >= on else 0
            self.assertEqual(got, first + late, f"case {k}: the first braking step")
            drops = (ours[:-1] - ours[1:])[got:]
            braking = drops[drops > 1e-9]
            # the rate, its sign: dec x dt a step until the last, partial one; never back up
            self.assertTrue(torch.allclose(braking[:-1], torch.full_like(braking[:-1], dec * dt),
                                           atol=1e-9), f"case {k}")
            self.assertTrue(bool((ours[1:] <= ours[:-1] + 1e-12).all()), f"case {k}: reaccelerated")
            self.assertEqual(float(ours[-1]), 0.0)
            want = [v] * late + want[:steps - late]
            self.assertTrue(torch.allclose(ours, torch.tensor(want, dtype=torch.float64),
                                           atol=1e-9), f"case {k}: the speed trace")



@unittest.skipIf(torch is None or not DIST.exists(), "no torch, or no leadbrake_rl project")
class Guards(unittest.TestCase):
    """243: the onset condition is the lead's s only on a straight lane along y = 0, the point on
    its line, the lead on the centre line; anything else is refused at the env's start."""

    SCEN = DIST.parent / "leadbrake.xosc"

    def variant(self, old, new):
        import tempfile
        text = self.SCEN.read_text()
        self.assertIn(old, text)
        d = Path(tempfile.mkdtemp())
        p = d / "leadbrake.xosc"
        p.write_text(text.replace(old, new, 1))
        return p

    def test_the_task_as_shipped_passes(self):
        LB.check_trigger_geometry(self.SCEN, LB.straight_world())

    def test_a_shifted_point_or_an_offset_lead_or_a_bent_lane_is_refused(self):
        with self.assertRaisesRegex(ValueError, "not on the lane's line"):
            LB.check_trigger_geometry(self.variant('x="-1000.0" y="0.0"', 'x="-1000.0" y="2.0"'),
                                      LB.straight_world())
        with self.assertRaisesRegex(ValueError, "not on the lane's line"):
            LB.check_trigger_geometry(self.variant('x="-1000.0"', 'x="-500.0"'),
                                      LB.straight_world())
        lead = ('<Private entityRef="lead">\n\t\t\t\t<PrivateAction><TeleportAction><Position>'
                '<LanePosition roadId="" laneId="1" s="$lead_s" offset="0" />')
        with self.assertRaisesRegex(ValueError, "off the lane's centre line"):
            LB.check_trigger_geometry(self.variant(lead, lead.replace('offset="0"',
                                                                      'offset="0.5"')),
                                      LB.straight_world())
        from scensim_batch.world_lanelet import LaneletWorld
        bent = LaneletWorld.from_polylines({1: [[0.0, 0.0], [200.0, 0.0], [400.0, 30.0]]},
                                           width=3.5)
        with self.assertRaisesRegex(ValueError, "not straight"):
            LB.check_trigger_geometry(self.SCEN, bent)

    def test_ackermann_is_stocks(self):
        """Stock's mdp.ackermann, its formula: at wheel base 3.005 and tread 1.667."""
        d = torch.tensor([-0.7, -0.2, 0.0, 1e-12, 0.3, 0.7], dtype=torch.float64)
        left, right = LB.ackermann(d, 3.005, 1.667)
        t = torch.tan(d)
        want_l = torch.atan2(3.005 * t, 3.005 - 0.8335 * t)
        want_r = torch.atan2(3.005 * t, 3.005 + 0.8335 * t)
        small = d.abs() < 1e-9
        self.assertTrue(torch.equal(left, torch.where(small, torch.zeros_like(d), want_l)))
        self.assertTrue(torch.equal(right, torch.where(small, torch.zeros_like(d), want_r)))
        self.assertGreater(float(left[4]), float(right[4]))     # the inner wheel turns more


if __name__ == "__main__":
    unittest.main()
