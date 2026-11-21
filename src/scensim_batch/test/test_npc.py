"""The batched default vehicle behaviour (092 K2.1) against SSv2's logic transcribed for one
vehicle (ssv2_ref.py): the planner and the stop distance equal per element; a follower on a
straight road equals the scalar run slot by slot over N random slots; the front entity found
only on the path, ahead, in the cone."""
import json
import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import torch
except ImportError:  # the package's torch extra
    torch = None

import ssv2_ref as ref  # noqa: E402

if torch is not None:
    from scensim_batch import npc  # noqa: E402

DT = 0.05
F64 = dict(dtype=torch.float64) if torch is not None else {}


def t(x):
    return torch.tensor(x, **F64)


@unittest.skipIf(torch is None, "no torch")
class Planner(unittest.TestCase):
    def test_a_sampled_curve_is_followed_on_its_arc(self):
        """092 K2.4: a route of a curve sampled every 5 m (world.route's) is the curve's arc
        length, its poses on a cubic through the samples and the yaw its tangent; chords
        cut a 10 m radius turn by ~0.3 m and head up to 0.25 rad off."""
        import math
        R, ds = 10.0, 5.0
        n = 13
        ang = [i * ds / R for i in range(n)]
        pts = torch.tensor([[[[R * math.sin(a), R - R * math.cos(a)] for a in ang]]],
                           dtype=torch.float64)
        smooth, chords = npc.Routes(pts, spacing=ds), npc.Routes(pts)
        self.assertAlmostEqual(float(smooth.length), ds * (n - 1))
        worst_p = worst_end = worst_y = 0.0
        for k in range(1, 100):
            s = torch.tensor([[k * ds * (n - 1) / 100]], dtype=torch.float64)
            a = float(s) / R
            x, y, yaw = smooth.pose(s)
            err = math.hypot(float(x) - R * math.sin(a), float(y) - (R - R * math.cos(a)))
            inner = ds <= float(s) <= ds * (n - 2)
            worst_p, worst_end = (max(worst_p, err), worst_end) if inner else (
                worst_p, max(worst_end, err))
            worst_y = max(worst_y, abs((float(yaw) - a + math.pi) % (2 * math.pi) - math.pi))
        self.assertLess(worst_p, 0.03)       # a chord's sagitta here: 0.31 m
        self.assertLess(worst_end, 0.1)      # the end segments' parabola
        self.assertLess(worst_y, 0.03)
        _, _, cyaw = chords.pose(torch.tensor([[0.1]], dtype=torch.float64))
        self.assertGreater(abs(float(cyaw)), 0.2)            # a chord's heading, as before
        # a point on the curve projects to its arc length
        s_p, lat = smooth.project(pts[..., 4:5, :])
        self.assertAlmostEqual(float(s_p), 4 * ds, places=6)

    def test_dynamic_states_and_running_distance_equal_the_scalar_planner(self):
        rng = random.Random(3)
        rows = [(rng.uniform(0, 30), rng.uniform(0, 30), rng.uniform(-5, 5)) for _ in range(400)]
        target, v, a = (t([[r[i] for r in rows]]) for i in range(3))
        c = npc.Constraints.default(v.shape)
        v1, a1, j1 = npc.dynamic_states(target, c, v, a, DT)
        for i, (tg, vv, aa) in enumerate(rows):
            want = ref.dynamic_states(tg, ref.C, vv, aa, DT)
            self.assertEqual((v1[0, i].item(), a1[0, i].item(), j1[0, i].item()), want)
        zero = torch.zeros_like(v)
        d = npc.running_distance(zero, c, v, a, zero, DT)
        for i, (_, vv, aa) in enumerate(rows):
            self.assertAlmostEqual(d[0, i].item(), ref.running_distance(0.0, ref.C, vv, aa, 0.0, DT),
                                   places=9)

    def test_the_limits_hold_on_a_run_to_target(self):
        v = torch.zeros(1, 1, **F64)
        a = torch.zeros_like(v)
        c = npc.Constraints.default(v.shape)
        for _ in range(400):
            v1, a1, j = npc.dynamic_states(t([[15.0]]), c, v, a, DT)
            self.assertLessEqual(a1.item(), 10.0 + 1e-9)
            if v1.item() < 13.0:   # SSv2 caps acceleration at (target - v) / dt on arrival,
                self.assertLessEqual(abs(j.item()), 3.0 + 1e-6)   # past the jerk limit
            v, a = v1, a1
        self.assertAlmostEqual(v.item(), 15.0, places=6)


def straight(n, e, length=600.0):
    xs = torch.linspace(0, length, 61, **F64)
    pts = torch.stack([xs, torch.zeros_like(xs)], -1)
    return npc.Routes(pts.expand(n, e, 61, 2).clone())


def scalar_follow(s, v, target, s_lead, v_lead, steps, L=4.0, L_lead=4.0):
    """One follower behind a lead at constant speed, the tree's speed logic per step."""
    a = j = 0.0
    following = False
    out = []
    for _ in range(steps):
        horizon = max(min(max(v * 5.0, 20.0), 50.0), ref.running_distance(0.0, ref.C, v, a, j, DT))
        ds = s_lead - s
        gap = ds - L / 2 - L_lead / 2
        d = gap + L / 2 if (ds > 0 and gap >= 0 and ds <= horizon + L_lead) else None
        local, following = ref.local_target(target, v, a, j, L, d, v_lead, DT,
                                            running=following)
        v1, a1, j1 = ref.dynamic_states(local, ref.C, v, a, DT)
        s += (v1 + v) / 2.0 * DT
        v, a, j = v1, a1, j1
        s_lead += v_lead * DT
        out.append((s, v))
    return out


@unittest.skipIf(torch is None, "no torch")
class Following(unittest.TestCase):
    def test_n_slots_equal_n_scalar_runs(self):
        rng = random.Random(5)
        n, steps = 64, 300
        cases = [(rng.uniform(0, 20), rng.uniform(0, 15), rng.uniform(5, 20),
                  rng.uniform(15, 80), rng.choice([0.0, rng.uniform(0, 12)])) for _ in range(n)]
        routes = straight(n, 1)
        s0 = t([[c[0]] for c in cases])
        v0 = t([[c[1]] for c in cases])
        car = npc.DefaultVehicles(routes, s0, v0, torch.full_like(s0, 4.0),
                                  torch.full_like(s0, 1.8), t([[c[2]] for c in cases]))
        lead_s = t([[c[0] + c[3]] for c in cases])
        lead_v = t([[c[4]] for c in cases])
        got = []
        for _ in range(steps):
            others = {"x": lead_s, "y": torch.zeros_like(lead_s), "yaw": torch.zeros_like(lead_s),
                      "length": torch.full_like(lead_s, 4.0), "width": torch.full_like(lead_s, 1.8),
                      "v": lead_v}
            car.step(DT, others)
            got.append((car.s.clone(), car.v.clone()))
            lead_s = lead_s + lead_v * DT
        # 1e-6, not bit for bit: the cone test uses atan2, a function numpy and math may
        # round differently in the last bit (S3's rule); an entity at exactly pi/2 could flip
        for i, c in enumerate(cases):
            want = scalar_follow(c[0], c[1], c[2], c[0] + c[3], c[4], steps)
            for k in (0, 50, 150, steps - 1):
                self.assertAlmostEqual(got[k][0][i, 0].item(), want[k][0], places=6, msg=(i, k))
                self.assertAlmostEqual(got[k][1][i, 0].item(), want[k][1], places=6, msg=(i, k))

    def test_a_follower_keeps_following_while_its_stop_distance_shrinks(self):
        """092 K2.4: seats' k24_npc_stops_for_ego, the follower's first 300 steps (its brake
        from 6 m/s behind an ego pulling away, then following at 2.74 m/s), to 1 mm/s. Braking
        shrinks the stop distance, so FollowLane's hand-off test would pass again at step 11
        and its target reset the deceleration; SSv2's tree resumes FollowFrontEntity instead.
        The ego as the update reads it: its pose the tick's reply, its speed a frame earlier
        (see the fixture's note)."""
        fx = json.loads((Path(__file__).resolve().parent / "data" /
                         "seats_follower_stops_for_ego.json").read_text())
        f = fx["follower"]
        car = npc.DefaultVehicles(straight(1, 1), t([[0.0]]), t([[f["v0"]]]), t([[f["length"]]]),
                                  t([[f["width"]]]), t([[f["target"]]]), cx=t([[f["cx"]]]))
        ego = fx["ego"]
        worst = 0.0
        for k, (s_ego, v_ego) in enumerate(zip(fx["ego_s"], fx["ego_v"])):
            v_before = car.v.clone()
            car.step(DT, {"x": t([[s_ego]]), "y": t([[0.0]]), "yaw": t([[0.0]]),
                          "length": t([[ego["length"]]]), "width": t([[ego["width"]]]),
                          "cx": t([[ego["cx"]]]), "v": t([[v_ego]])})
            got = ((car.v + v_before) / 2).item()
            worst = max(worst, abs(got - fx["follower_v"][k]))
            if k >= 3:
                self.assertEqual(car.mode.item(), 1, k)
        self.assertLess(worst, 1e-3)


        routes = straight(1, 1)
        car = npc.DefaultVehicles(routes, t([[0.0]]), t([[12.0]]), t([[4.0]]), t([[1.8]]),
                                  t([[12.0]]))
        lead = {"x": t([[80.0]]), "y": t([[0.0]]), "yaw": t([[0.0]]), "length": t([[4.0]]),
                "width": t([[1.8]]), "v": t([[0.0]])}
        for _ in range(600):
            car.step(DT, lead)
        self.assertLess(car.v.item(), 0.05)
        self.assertLess(car.s.item() + 2.0, 80.0 - 2.0)   # bumpers apart

    def test_only_an_entity_on_the_path_ahead_counts(self):
        routes = straight(1, 1)
        car = npc.DefaultVehicles(routes, t([[10.0]]), t([[10.0]]), t([[4.0]]), t([[1.8]]),
                                  t([[10.0]]))
        car.dt = DT
        for x, y, seen in ((30.0, 0.0, True), (30.0, 3.5, False), (5.0, 0.0, False),
                           (30.0, 1.5, True)):   # 1.5 m off: its box reaches the path
            d, _, _ = car.front({"x": t([[x]]), "y": t([[y]]), "yaw": t([[0.0]]),
                                 "length": t([[4.0]]), "width": t([[1.8]]), "v": t([[0.0]])})
            self.assertEqual(math.isfinite(d.item()), seen, (x, y))

    def test_the_front_distance_equals_ssv2s_for_trucks_overlaps_and_offsets(self):
        """243's cases: a box wider than the car centred on its path (SSv2's polygon fallback
        sees it), and a box already overlapping the bumper (SSv2 returns no distance)."""
        routes = straight(1, 1)
        car = npc.DefaultVehicles(routes, t([[10.0]]), t([[10.0]]), t([[4.0]]), t([[1.8]]),
                                  t([[10.0]]))
        car.dt = DT
        for x, y, length, width in ((30.0, 0.0, 10.0, 2.5),    # a truck, centred
                                    (30.0, 0.0, 12.0, 6.0),    # wider still
                                    (30.0, 2.4, 4.0, 1.8),     # off the path
                                    (13.0, 0.0, 4.0, 1.8),     # overlapping: gap < 0
                                    (16.0, 0.0, 4.0, 1.8)):    # just touching: gap 2
            d, _, _ = car.front({"x": t([[x]]), "y": t([[y]]), "yaw": t([[0.0]]),
                                 "length": t([[length]]), "width": t([[width]]),
                                 "v": t([[0.0]])})
            lat = [y + width / 2, y - width / 2, y - width / 2, y + width / 2]
            want = ref.front_distance(x - 10.0, 4.0, length, lat, 1.8)
            got = d.item() if math.isfinite(d.item()) else None
            if want is None:
                self.assertIsNone(got, (x, y, length, width))
            else:
                self.assertAlmostEqual(got, want, places=9, msg=(x, y, length, width))

    def test_the_front_distance_takes_each_boxs_centre(self):
        """SSv2's gap is from the own box's front edge to the other's rear edge, each at its
        centre.x -+ length / 2 from the pose (k24's follower 1.5 m, its ego 1.416 m)."""
        routes = straight(1, 1)
        for cx_self, cx_other, x in ((1.5, 1.416, 30.0), (0.0, 1.416, 30.0), (1.5, 0.0, 30.0),
                                     (-0.5, 2.0, 20.0), (1.5, 1.416, 14.8)):
            car = npc.DefaultVehicles(routes, t([[10.0]]), t([[10.0]]), t([[4.5]]), t([[2.1]]),
                                      t([[10.0]]), cx=t([[cx_self]]))
            car.dt = DT
            d, _, _ = car.front({"x": t([[x]]), "y": t([[0.0]]), "yaw": t([[0.0]]),
                                 "length": t([[4.792]]), "width": t([[2.163]]),
                                 "v": t([[0.0]]), "cx": t([[cx_other]])})
            lat = [2.163 / 2, -2.163 / 2, -2.163 / 2, 2.163 / 2]
            want = ref.front_distance(x - 10.0, 4.5, 4.792, lat, 2.1, cx_self, cx_other)
            got = d.item() if math.isfinite(d.item()) else None
            if want is None:
                self.assertIsNone(got, (cx_self, cx_other, x))
            else:
                self.assertAlmostEqual(got, want, places=9, msg=(cx_self, cx_other, x))
        # k24's boxes: SSv2's distance is the pose distance less 2.48
        self.assertAlmostEqual(ref.front_distance(20.0, 4.5, 4.792, lat, 2.1, 1.5, 1.416),
                               20.0 - 2.48, places=9)

    def test_an_inactive_vehicle_never_holds_the_stop_distance_loop(self):
        routes = straight(1, 2)
        car = npc.DefaultVehicles(routes, t([[0.0, 50.0]]), t([[10.0, math.nan]]),
                                  torch.full((1, 2), 4.0, **F64), torch.full((1, 2), 1.8, **F64),
                                  t([[10.0, 10.0]]), active=torch.tensor([[True, False]]))
        car.step(DT)
        self.assertTrue(math.isfinite(car.s[0, 0].item()))

    def test_vehicles_in_one_slot_see_each_other(self):
        routes = straight(1, 2)
        car = npc.DefaultVehicles(routes, t([[0.0, 40.0]]), t([[12.0, 0.0]]),
                                  torch.full((1, 2), 4.0, **F64), torch.full((1, 2), 1.8, **F64),
                                  t([[12.0, 0.0]]))
        for _ in range(600):
            car.step(DT)
        self.assertLess(car.v[0, 0].item(), 0.05)
        self.assertLess(car.s[0, 0].item(), car.s[0, 1].item() - 4.0)


if __name__ == "__main__":
    unittest.main()
