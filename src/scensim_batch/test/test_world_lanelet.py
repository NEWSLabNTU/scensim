"""The Lanelet2 world adapter (092 K2.6) without lanelet2: SSv2's spline against SSv2's own
unit tests' values (common/math/geometry/test/src/spline/test_catmull_rom_spline.cpp), the
cubic solver against numpy, a polyline world's queries, and the export's digest check. Where
python3 lanelet2 and the Town01 map are on the host, the export of Town01 too."""
import json
import math
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

try:
    import torch
    from scensim_batch import map_export
    from scensim_batch import world_lanelet as W
except ImportError:   # no torch
    torch = None

EPS = 1e-6


def P(*xy):
    return list(xy)


@unittest.skipIf(torch is None, "no torch")
class SplineTest(unittest.TestCase):
    """SSv2's own expectations, value for value."""

    def line(self):
        return W.Spline([P(0, 0), P(1, 3), P(2, 6)])

    def curve(self):
        return W.Spline([P(0, 0), P(1, 1), P(2, 0)])

    def curve2(self):
        return W.Spline([P(0, 0), P(1, 1), P(0, 2)])

    def test_length(self):
        self.assertAlmostEqual(self.line().length, math.hypot(2, 6), delta=EPS)
        self.assertAlmostEqual(self.curve().length, 3.0, delta=0.1)
        self.assertAlmostEqual(W.Spline([P(0, 0), P(1, 0), P(2, 0)]).length, 2.0, delta=EPS)

    def test_point_and_pose(self):
        x, y, _ = self.line().point(math.hypot(1.5, 4.5))
        self.assertAlmostEqual(x, 1.5, delta=EPS)
        self.assertAlmostEqual(y, 4.5, delta=EPS)
        self.assertAlmostEqual(self.line().yaw(math.hypot(1.5, 4.5)), math.atan(3.0), delta=EPS)
        x, y, _ = self.curve().point(1.5)
        self.assertLess(math.hypot(x - 1.0, y - 1.0), 0.02)
        # SSv2 checks the pose's quaternion within 0.02 of identity: qz = sin(yaw / 2)
        self.assertLess(abs(math.sin(self.curve().yaw(1.5) / 2)), 0.02)

    def test_trajectory_with_and_without_offset(self):
        sp = self.curve2()
        want = [(0.0, 0.0), (0.559992, 0.336669), (0.893292, 0.673338), (0.999898, 1.010091),
                (0.87779, 1.349586), (0.525168, 1.68908)]
        for i, (wx, wy) in enumerate(want):
            x, y, _ = sp.point(0.5 * i)
            self.assertAlmostEqual(x, wx, delta=EPS)
            self.assertAlmostEqual(y, wy, delta=EPS)
        want = [(0.447214, -0.894427), (1.161918, -0.461883), (1.730462, 0.126395),
                (1.999695, 1.030269), (1.697341, 1.922592), (1.112457, 2.498458)]
        for i, (wx, wy) in enumerate(want):
            x, y, _ = sp.point(0.5 * i, -1.0)
            self.assertAlmostEqual(x, wx, delta=EPS)
            self.assertAlmostEqual(y, wy, delta=EPS)

    def test_collision(self):
        sp = W.Spline([P(0, 0), P(1, 0), P(2, 0)])
        self.assertAlmostEqual(sp.collision_s([P(0.1, 1.0), P(0.1, -1.0)]), 0.1, delta=EPS)
        sp = W.Spline([P(0, 0), P(2, 0), P(4, 0)])
        self.assertAlmostEqual(sp.collision_s([P(0.1, 1.0), P(0.1, -1.0)]), 0.1, delta=EPS)
        self.assertAlmostEqual(sp.collision_s([P(3.5, 1.0), P(3.5, -1.0)]), 3.5, delta=EPS)
        self.assertIsNone(self.curve().collision_s([P(0.5, 0.0), P(1.5, 0.0)]))
        poly = [P(0, 1), P(-1, 0), P(0, -1), P(1, 0)]
        self.assertAlmostEqual(self.curve().collision_s(poly), 0.56727227, delta=EPS)
        self.assertAlmostEqual(self.curve().collision_s(poly, True), 0.56727227, delta=EPS)

    def test_s_value(self):
        sp = W.Spline([P(0, 0), P(1, 0), P(2, 0), P(4, 0)])
        self.assertAlmostEqual(sp.s_value(0.1, 0.0, 0.0, 1.0), 0.1, delta=EPS)
        self.assertIsNone(sp.s_value(10.0, 0.0, 0.0, 3.0))
        self.assertIsNone(self.curve().s_value(-2.0, -2.0, 0.0, 1.0))
        sp = W.Spline([P(89122.2, 43364.1, 3.13364), P(89122.5, 43363.8, 3.13364),
                       P(89122.8, 43363.4, 3.13364), P(89123.1, 43363.0, 3.13364),
                       P(89123.4, 43362.6, 3.13364)])
        q0 = (-0.0159808, -0.00566353, -0.453507, 0.891092)
        q1 = (0.0159365, -0.00578704, -0.446597, 0.894575)
        # SSv2 expects these with EXPECT_DOUBLE_EQ (4 ulps); the port agrees to 1e-11 (the
        # order of its floating-point operations is not SSv2's to the last bit)
        self.assertAlmostEqual(sp.s_value(89122.8, 43363.4, 0.0, 1.0, quat=q0),
                               0.92433178422155371, delta=1e-11)
        self.assertAlmostEqual(sp.s_value(89122.5, 43363.8, 0.0, 1.0, quat=q1),
                               0.42440442127906564, delta=1e-11)

    def test_curves_join_at_the_control_points(self):
        pts = [P(0, 0), P(1, 3), P(2, 5), P(4, 6), P(4, 1)]
        sp = W.Spline(pts)
        for c, a, b in zip(sp.curves, pts, pts[1:]):
            self.assertEqual([round(v, 12) for v in c.point(0.0)[:2]], [float(v) for v in a])
            self.assertEqual([round(v, 12) for v in c.point(1.0)[:2]], [float(v) for v in b])

    def test_cubic_roots(self):
        import numpy as np
        rnd = random.Random(1)
        for _ in range(300):
            roots = sorted(rnd.uniform(-1, 2) for _ in range(3))
            a = rnd.choice([1.0, -2.5, 0.3])
            coef = a * np.poly(roots)
            got = sorted(W._cubic(*coef, 0.0, 1.0))
            want = sorted(r for r in roots if 0 <= r <= 1)
            if min(abs(x - y) for x in roots for y in roots if x is not y) < 1e-3:
                continue      # near-double roots: both solvers are ill-conditioned there
            self.assertEqual(len(got), len(want), (roots, got))
            for g, w in zip(got, want):
                self.assertAlmostEqual(g, w, delta=1e-6)
        self.assertEqual(W._cubic(0, 1, -3, 2, 0, 3), [1.0, 2.0])     # a = 0: the quadratic
        self.assertEqual(W._cubic(0, 0, 2, -1, 0, 1), [0.5])          # and the linear


def track():
    """Two lanelets: a 100 m straight along x (1), then a 50 m straight up y (2), and 2's loop
    back is absent; lane 3 is 1's left neighbour, 3.5 m over."""
    w = W.LaneletWorld.from_polylines(      # points every 2 m, as a map's lanelets have
        {1: [[x, 0] for x in range(0, 101, 2)], 2: [[100, y] for y in range(0, 51, 2)],
         3: [[x, 3.5] for x in range(0, 101, 2)]},
        following={1: [2], 3: []}, speed_limit=10.0, width=3.5)
    w.lanelets[1]["left"] = 3
    w.lanelets[3]["right"] = 1
    return w


@unittest.skipIf(torch is None, "no torch")
class WorldTest(unittest.TestCase):
    def test_lane_pose_and_back(self):
        w = track()
        x, y, h = w.lane_pose([1, 1, 2], torch.tensor([10.0, 60.0, 5.0]),
                              torch.tensor([0.0, 1.0, 0.0]))
        self.assertAlmostEqual(float(x[0]), 10.0, places=9)
        self.assertAlmostEqual(float(y[1]), 1.0, places=9)        # + left
        self.assertAlmostEqual(float(h[2]), math.pi / 2, places=9)
        lane, s, off = w.lanelet_pose(30.0, 0.5, 0.0)
        self.assertEqual(lane, 1)
        self.assertAlmostEqual(s, 30.0, places=6)
        self.assertAlmostEqual(off, 0.5, places=6)
        # SSv2 matches along the pose's own y axis: a turned pose lands further along
        _, s, off = w.lanelet_pose(30.0, 0.5, 0.1)
        self.assertAlmostEqual(s, 30.0 + 0.5 * math.tan(0.1), places=6)
        self.assertIsNone(w.lanelet_pose(30.0, 0.5, math.pi / 2))    # 90 deg off the lane
        self.assertEqual(w.lanelet_pose(30.0, 0.5, math.pi)[0], 1)    # backwards matches
        self.assertIsNone(w.lanelet_pose(30.0, 20.0, 0.0))            # on no lanelet

    def test_route_follows_the_lanelets(self):
        w = track()
        r = w.route(torch.tensor([[90.0]]), torch.tensor([[0.0]]), torch.tensor([[0.0]]),
                    30.0, 7)
        self.assertEqual(tuple(r.shape), (1, 1, 7, 2))
        self.assertAlmostEqual(float(r[0, 0, 0, 0]), 90.0, places=6)
        self.assertGreater(float(r[0, 0, -1, 1]), 15.0)               # round the corner, up 2
        with self.assertRaisesRegex(ValueError, "on no lanelet"):
            w.route(torch.tensor([30.0]), torch.tensor([20.0]), torch.tensor([0.0]), 10, 3)

    def test_speed_limit_along_and_lanes(self):
        w = track()
        self.assertEqual(w.speed_limit(torch.tensor([5.0]), torch.tensor([0.0])).tolist(), [10.0])
        self.assertTrue(math.isnan(float(w.speed_limit(torch.tensor([5.0]),
                                                       torch.tensor([30.0]))[0])))
        lane, s = w.along_lanelet(1, 90.0, 20.0)
        self.assertEqual(lane, 2)
        self.assertAlmostEqual(s, 110.0 - w.length(1), places=9)
        self.assertTrue(w.can_change_lane(1, 3))
        self.assertFalse(w.can_change_lane(1, 2))
        self.assertEqual(w.adjacent_lane(1, "left", 1), 3)
        self.assertIsNone(w.adjacent_lane(1, "left", 2))
        self.assertAlmostEqual(w.collision_s(3, (40.0, 10.0), (40.0, 0.0)), 40.0, places=6)
        tx, ty = w.tangent(1, 30.0)
        self.assertGreater(tx, 0)
        self.assertAlmostEqual(ty, 0.0, places=9)

    def test_following_prefers_straight(self):
        w = W.LaneletWorld.from_polylines(
            {1: [[0, 0], [5, 0], [10, 0]], 2: [[10, 0], [12, 3], [13, 8]],
             3: [[10, 0], [15, 0], [20, 0]]}, following={1: [2, 3]})
        self.assertEqual(w.following(1, 5.0), [1, 2])                 # no straight: the first
        w.lanelets[3]["turn_direction"] = "straight"
        self.assertEqual(w.following(1, 5.0), [1, 3])


@unittest.skipIf(torch is None, "no torch")
class ExportFileTest(unittest.TestCase):
    def test_digest_and_format_are_checked(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "map").mkdir()
            (d / "map" / "lanelet2_map.osm").write_text("<osm/>")
            digest = map_export.map_digest(d / "map")
            doc = {"format": map_export.FORMAT, "version": map_export.VERSION, "map": "map",
                   "map_sha256": digest, "frame": "map",
                   "lanelets": {"1": {"centerline": [[0, 0, 0], [1, 0, 0], [2, 0, 0]],
                                      "following": [], "turn_direction": "else"}}}
            f = d / "export.json"
            f.write_text(json.dumps(doc))
            self.assertEqual(W.LaneletWorld.load(f, map_dir=d / "map").sha256, digest)
            (d / "map" / "lanelet2_map.osm").write_text("<osm>changed</osm>")
            with self.assertRaisesRegex(ValueError, "export it again"):
                W.LaneletWorld.load(f, map_dir=d / "map")
            W.LaneletWorld.load(f)                                       # no map: no check
            f.write_text(json.dumps(dict(doc, version=99)))
            with self.assertRaisesRegex(ValueError,
                                        f"not a scensim-batch-lanelet-map v{map_export.VERSION}"):
                W.LaneletWorld.load(f)


TOWN01 = os.environ.get("SCENSIM_TEST_TOWN01_MAP", "")


@unittest.skipIf(torch is None or not TOWN01 or not Path(TOWN01).is_dir(),
                 "SCENSIM_TEST_TOWN01_MAP names no map directory")
class Town01Test(unittest.TestCase):
    def test_export_and_round_trip(self):
        try:
            import lanelet2   # noqa: F401
        except ImportError:
            self.skipTest("no python3 lanelet2")
        doc = map_export.export(TOWN01)
        self.assertEqual(doc["map_sha256"], map_export.map_digest(TOWN01))
        w = W.LaneletWorld(doc["lanelets"], doc["map"], doc["map_sha256"])
        roads = [k for k, v in w.lanelets.items() if v["subtype"] == "road"]
        self.assertGreater(len(roads), 100)
        ok = 0
        for k in roads[:40]:
            sp = w.spline(k)
            x, y, _ = sp.point(sp.length / 2)
            lp = w.lanelet_pose(x, y, sp.yaw(sp.length / 2), lanes=[k])
            ok += lp is not None and abs(lp[1] - sp.length / 2) < 1e-6 and abs(lp[2]) < 1e-6
        self.assertEqual(ok, 40)
        # SSv2's own following() order at Town01's 36 branches (traffic_simulator's
        # lanelet_wrapper, VEHICLE_WITH_ROAD_SHOULDER): a route-less NPC takes the first, and
        # v1's order (a graph on the moved map) differed at 20 of them (K2.4's follow_to_goal)
        for k, v in SSV2_TOWN01_BRANCHES.items():
            self.assertEqual(w.lanelets[int(k)]["following"], v, k)


SSV2_TOWN01_BRANCHES = {
    "31300": [38791, 39254], "27898": [35308, 35798], "20475": [39868, 39641],
    "18715": [43549, 43381], "6583": [42664, 42451], "5230": [42219, 41795],
    "16676": [43149, 43640], "7768": [36945, 36717], "34721": [43302, 43074],
    "29825": [38704, 38203], "149": [35397, 35653], "12008": [38477, 38053],
    "21828": [41040, 41443], "32582": [41581, 41199], "16946": [39406, 39114],
    "10732": [37162, 36630], "3183": [36464, 35887], "32189": [39041, 38966],
    "4051": [37322, 37903], "1159": [35976, 36149], "2922": [37664, 37411],
    "2113": [35161, 35576], "28257": [42063, 41654], "27676": [40892, 40484],
    "17761": [40738, 40314], "9379": [38294, 38556], "29216": [42296, 41884],
    "32855": [42737, 42824], "34940": [36305, 36543], "30482": [39485, 40054],
    "28958": [39793, 39961], "33476": [37014, 37233], "34136": [41370, 40967],
    "31871": [42526, 42911], "28575": [40395, 40573], "31516": [37743, 37980],
}


if __name__ == "__main__":
    unittest.main()
