"""A map's anchors resolved (092 K9a): scensim_batch.anchors on a two-lanelet map (a 20 m
straight, then a quarter circle of radius 10 m turning left), and the resolved file as the
sampler reads it (scensim_sampler.anchors: digest, numbers, heading(s) within the file's
stated error)."""
import json
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scensim_sampler"))

try:
    import torch  # noqa: F401 - world_lanelet's
except ImportError:  # the package's torch extra
    torch = None

if torch is not None:
    from scensim_batch import anchors as RES, map_export
    from scensim_batch.world_lanelet import LaneletWorld
from scensim_sampler import anchors as A  # noqa: E402


def _map(d):
    """A map directory and its export: lanelet 1 straight along x for 20 m, lanelet 2 a
    quarter circle of radius 10 m from (20, 0) to (30, 10), lanelet 3 apart."""
    d = Path(d)
    (d / "lanelet2_map.osm").write_text("<osm><!-- a fixture: its bytes fix the digest --></osm>")
    straight = [[x, 0.0, 0.0] for x in (0.0, 5.0, 10.0, 15.0, 20.0)]
    arc = [[20.0 + 10.0 * math.sin(a), 10.0 - 10.0 * math.cos(a), 0.0]
           for a in [math.pi / 2 * k / 12 for k in range(13)]]
    apart = [[0.0, 50.0, 0.0], [5.0, 50.0, 0.0], [10.0, 50.0, 0.0]]
    across = [[10.0, y, 0.0] for y in (-10.0, -5.0, 0.0, 5.0, 10.0)]   # crosses lanelet 1

    def ll(c, following, limit):
        return {"centerline": c, "subtype": "road", "turn_direction": "else",
                "following": following, "previous": [], "left": None, "right": None,
                "adjacent_left": None, "adjacent_right": None, "speed_limit": limit,
                "speed_limit_tagged": True}
    doc = {"format": map_export.FORMAT, "version": map_export.VERSION, "map": d.name,
           "map_sha256": map_export.map_digest(d), "frame": "map",
           "lanelets": {"1": ll(straight, [2], 13.89), "2": ll(arc, [], 8.33),
                        "3": ll(apart, [], 13.89), "4": ll(across, [], 8.33)}}
    export = d / "export.json"
    export.write_text(json.dumps(doc))
    return d, export


@unittest.skipIf(torch is None, "no torch")
class Resolve(unittest.TestCase):
    def resolved(self, d, lanes="exit_n: {lanelets: [1, 2]}"):
        d, export = _map(d)
        (d / RES.DECLARATION).write_text(f"anchors: 1\nlanes:\n  {lanes}\n")
        return d, export, RES.resolve(d, export)

    def test_a_lane_of_two_lanelets(self):
        with tempfile.TemporaryDirectory() as d:
            d, export, doc = self.resolved(d)
            w = LaneletWorld.load(export, map_dir=d)
            a = doc["anchors"]["exit_n"]
            self.assertEqual(doc["map_sha256"], map_export.map_digest(d))
            self.assertAlmostEqual(a["length"], w.length(1) + w.length(2), places=12)
            self.assertAlmostEqual(a["length"], 20.0 + 10.0 * math.pi / 2, delta=0.05)
            self.assertEqual([x["id"] for x in a["lanelets"]], [1, 2])
            self.assertEqual(a["speed_limit"], 8.33)                 # the lowest
            self.assertAlmostEqual(a["heading"][0], 0.0, places=9)
            self.assertAlmostEqual(a["heading"][-1], math.pi / 2, delta=0.02)
            self.assertEqual(a["heading_s"][-1], a["length"])
            self.assertTrue(all(b - x <= RES.HEADING_STEP + 1e-12
                                for x, b in zip(a["heading_s"], a["heading_s"][1:])))
            self.assertLess(doc["heading_max_error"], 1e-3)
            self.assertAlmostEqual(a["end_x"], 30.0, delta=1e-6)
            # the centreline at heading_s (092 K9): on the straight y = 0, x = s
            self.assertEqual(len(a["x"]), len(a["heading_s"]))
            for s, x, y in zip(a["heading_s"], a["x"], a["y"]):
                if s <= 20.0:
                    self.assertAlmostEqual(x, s, delta=1e-6)
                    self.assertAlmostEqual(y, 0.0, delta=1e-9)
            self.assertAlmostEqual(a["end_y"], 10.0, delta=1e-6)

    def test_the_sampler_reads_it_within_its_stated_error(self):
        with tempfile.TemporaryDirectory() as d:
            d, export, doc = self.resolved(d)
            out = d / RES.RESOLVED
            out.write_text(json.dumps(doc))
            anchors = A.load_resolved(out, map_dir=d)
            numbers, functions = A.env(anchors)
            self.assertEqual(numbers["anchor.exit_n.length"], doc["anchors"]["exit_n"]["length"])
            self.assertNotIn("anchor.exit_n.heading", numbers)     # only heading(s)
            self.assertEqual(functions["anchor.exit_n.heading"](0.0), 0.0)
            w = LaneletWorld.load(export, map_dir=d)
            heading = functions["anchor.exit_n.heading"]
            rng = random.Random(3)
            L1 = w.length(1)
            for _ in range(400):
                s = rng.uniform(0.0, doc["anchors"]["exit_n"]["length"])
                exact = w.spline(1).yaw(s) if s <= L1 else w.spline(2).yaw(s - L1)
                err = abs(math.atan2(math.sin(heading(s) - exact), math.cos(heading(s) - exact)))
                self.assertLessEqual(err, doc["heading_max_error"] * 1.5 + 1e-12, s)
            with self.assertRaisesRegex(A.AnchorError, "outside the lane"):
                heading(doc["anchors"]["exit_n"]["length"] + 1.0)
            # the digest: another map's bytes refuse the file
            (d / "lanelet2_map.osm").write_text("<osm><!-- edited --></osm>")
            with self.assertRaisesRegex(A.AnchorError, "not the map in use"):
                A.load_resolved(out, map_dir=d)

    def test_the_sampler_digest_is_the_exports(self):
        with tempfile.TemporaryDirectory() as d:
            d, _ = _map(d)
            self.assertEqual(A.map_digest(d), map_export.map_digest(d))

    def test_a_wiggly_centreline_is_refined_to_the_tolerance(self):
        """Points 0.25 m apart with 2 cm of noise (Town01's lanelet 42664 is like it): SSv2's
        spline heading wiggles faster than 0.5 m, and the table halves its intervals until
        linear interpolation is within the tolerance."""
        with tempfile.TemporaryDirectory() as d:
            d, export = _map(d)
            doc = json.loads(export.read_text())
            rng = random.Random(1)
            doc["lanelets"]["3"]["centerline"] = [[0.25 * k, 50.0 + rng.uniform(-0.02, 0.02), 0.0]
                                                  for k in range(81)]
            doc["map_sha256"] = map_export.map_digest(d)
            export.write_text(json.dumps(doc))
            (d / RES.DECLARATION).write_text("anchors: 1\nlanes:\n  w: {lanelets: [3]}\n")
            res = RES.resolve(d, export)
            a = res["anchors"]["w"]
            self.assertLessEqual(a["heading_max_error"], RES.HEADING_TOLERANCE)
            self.assertGreater(len(a["heading_s"]), a["length"] / RES.HEADING_STEP + 2)  # refined
            self.assertEqual(res["heading_tolerance"], RES.HEADING_TOLERANCE)

    def test_reversed_stretches_are_listed_and_heading_refuses_inside_them(self):
        """Issue 166: a straight centreline whose points step from 0.015 m to 0.3 m apart (as
        Town05's lanelet 105401's do) makes SSv2's uniform spline run backward for a few
        centimetres. The lane lists those stretches, its error leaves them out, and the
        sampler's heading(s) refuses an s inside one; an evenly spaced lane lists none."""
        with tempfile.TemporaryDirectory() as d:
            d, export = _map(d)
            doc = json.loads(export.read_text())
            xs = [0.0, 0.015, 0.03, 0.045, 0.06] + [0.06 + 0.3 * k for k in range(1, 41)]
            doc["lanelets"]["3"]["centerline"] = [[x, 50.0, 0.0] for x in xs]
            doc["map_sha256"] = map_export.map_digest(d)
            export.write_text(json.dumps(doc))
            (d / RES.DECLARATION).write_text("anchors: 1\nlanes:\n  u: {lanelets: [3]}\n"
                                             "  even: {lanelets: [1]}\n")
            res = RES.resolve(d, export)
            u, even = res["anchors"]["u"], res["anchors"]["even"]
            self.assertEqual(even["reversed"], [])
            self.assertGreaterEqual(len(u["reversed"]), 1)
            w = LaneletWorld.load(export, map_dir=d)
            for r in u["reversed"]:
                self.assertLess(r["to_s"] - r["from_s"], 0.1)
                mid = (r["from_s"] + r["to_s"]) / 2
                self.assertGreater(abs(w.spline(3).yaw(mid)), math.pi / 2)   # runs backward
            self.assertLess(u["heading_max_error"], 1e-2)
            self.assertGreater(u["heading_max_error_reversed"], math.pi / 2)
            out = d / RES.RESOLVED
            out.write_text(json.dumps(res))
            _, functions = A.env(A.load_resolved(out, map_dir=d))
            heading = functions["anchor.u.heading"]
            r = u["reversed"][0]
            with self.assertRaisesRegex(A.AnchorError, "reversed stretch.*issue 166"):
                heading((r["from_s"] + r["to_s"]) / 2)
            self.assertLess(abs(heading(5.0)), 1e-2)                 # elsewhere: along +x

    def test_refusals(self):
        for lanes, why in (("x: {lanelets: [1, 3]}", "lanelet 3 does not follow 1"),
                           ("x: {lanelets: [9]}", "lanelet 9 is not in map"),
                           ("x: {lanelets: []}", "lanelets"),
                           ("x: {lanelets: [one]}", "is not an id")):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaisesRegex(RES.AnchorError, why):
                    self.resolved(d, lanes)
        with tempfile.TemporaryDirectory() as d:
            d, export = _map(d)
            (d / RES.DECLARATION).write_text("anchors: 1\npoints: {p: {}}\n")
            with self.assertRaisesRegex(RES.AnchorError, "a point is stated"):
                RES.resolve(d, export)

    def test_a_conflict_is_where_two_lanes_cross(self):
        """lanelet 4 runs north along x = 10 across lanelet 1 (east along y = 0): the conflict is
        10 m along each, at (10, 0), the second lane 90 degrees left of the first."""
        lanes = "exit_n: {lanelets: [1, 2]}\n  north: {lanelets: [4]}\n" \
                "conflicts:\n  exit_x_north: {lanes: [exit_n, north]}"
        with tempfile.TemporaryDirectory() as d:
            d, export, doc = self.resolved(d, lanes)
            c = doc["anchors"]["exit_x_north"]
            self.assertEqual(c["kind"], "conflict")
            self.assertAlmostEqual(c["s_exit_n"], 10.0, delta=1e-3)
            self.assertAlmostEqual(c["s_north"], 10.0, delta=1e-3)
            self.assertAlmostEqual(c["x"], 10.0, delta=1e-3)
            self.assertAlmostEqual(c["y"], 0.0, delta=1e-3)
            self.assertAlmostEqual(c["angle"], math.pi / 2, delta=1e-3)
            self.assertLess(c["position_error"], 1e-3)
            out = d / RES.RESOLVED
            out.write_text(json.dumps(doc))
            numbers, _ = A.env(A.load_resolved(out, map_dir=d))
            self.assertAlmostEqual(numbers["anchor.exit_x_north.s_north"], c["s_north"])
            self.assertIn("anchor.exit_x_north.angle", numbers)
        for conflicts, why in (("c: {lanes: [exit_n, apart]}", "cross 0 times"),
                               ("c: {lanes: [exit_n, ghost]}", "'ghost' is not a lane"),
                               ("c: {lanes: [exit_n]}", "two lanes"),
                               ("exit_n: {lanes: [exit_n, apart]}", "another anchor")):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaisesRegex(RES.AnchorError, why):
                    self.resolved(d, "exit_n: {lanelets: [1, 2]}\n  apart: {lanelets: [3]}\n"
                                     f"conflicts:\n  {conflicts}")

    def test_a_curve_is_a_stretch_of_a_lane(self):
        """exit_n's quarter circle (radius 10 m, from s 20): a left turn of pi/2 over its
        length, radius 10; the straight before it has none."""
        lanes = "exit_n: {lanelets: [1, 2]}\ncurves:\n  bend: {lane: exit_n, from_s: 20.5, " \
                "to_s: 35.0}\n  flat: {lane: exit_n, from_s: 2.0, to_s: 18.0}"
        with tempfile.TemporaryDirectory() as d:
            d, export, doc = self.resolved(d, lanes)
            bend, flat = doc["anchors"]["bend"], doc["anchors"]["flat"]
            self.assertEqual((bend["kind"], bend["direction"], bend["lane"]),
                             ("curve", "left", "exit_n"))
            self.assertAlmostEqual(bend["length"], 14.5)
            self.assertAlmostEqual(bend["min_radius"], 10.0, delta=1.0)
            self.assertAlmostEqual(bend["turn"], 14.5 / 10.0, delta=0.05)
            self.assertAlmostEqual(bend["mean_radius"], 10.0, delta=0.3)
            self.assertIsNone(flat["min_radius"])    # a straight: none, not Infinity
            self.assertIsNone(flat["mean_radius"])
        for curves, why in (("c: {lane: ghost, from_s: 0, to_s: 1}", "'ghost' is not a lane"),
                            ("c: {lane: exit_n, from_s: 5, to_s: 99}", "not a stretch"),
                            ("c: {lane: exit_n, from_s: x, to_s: 1}", "numbers")):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaisesRegex(RES.AnchorError, why):
                    self.resolved(d, f"exit_n: {{lanelets: [1, 2]}}\ncurves:\n  {curves}")

    def test_a_region_is_a_polygon_and_where_lanes_cross_it(self):
        lanes = "exit_n: {lanelets: [1, 2]}\n  north: {lanelets: [4]}\nregions:\n" \
                "  box: {polygon: [[5, -2], [15, -2], [15, 2], [5, 2]]}"
        with tempfile.TemporaryDirectory() as d:
            d, export, doc = self.resolved(d, lanes)
            box = doc["anchors"]["box"]
            self.assertEqual(box["kind"], "region")
            self.assertAlmostEqual(box["area"], 40.0)
            self.assertAlmostEqual(box["x"], 10.0)
            self.assertAlmostEqual(box["y"], 0.0)
            self.assertAlmostEqual(box["from_exit_n"], 5.0, delta=0.11)
            self.assertAlmostEqual(box["to_exit_n"], 15.0, delta=0.11)
            self.assertAlmostEqual(box["from_north"], 8.0, delta=0.11)
            self.assertAlmostEqual(box["to_north"], 12.0, delta=0.11)
            out = d / RES.RESOLVED
            out.write_text(json.dumps(doc))
            numbers, _ = A.env(A.load_resolved(out, map_dir=d))
            self.assertEqual(numbers["anchor.box.area"], box["area"])
            self.assertNotIn("anchor.box.polygon", numbers)
        for regions, why in (("r: {polygon: [[0, 0], [1, 1]]}", "three or more"),
                             ("r: {polygon: [[0, 0], [1, 1], [2, 2]]}", "no area"),
                             ("exit_n: {polygon: [[0, 0], [1, 0], [0, 1]]}", "another anchor")):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaisesRegex(RES.AnchorError, why):
                    self.resolved(d, f"exit_n: {{lanelets: [1, 2]}}\nregions:\n  {regions}")

    def test_the_command_writes_beside_the_map(self):
        with tempfile.TemporaryDirectory() as d:
            d, export = _map(d)
            (d / RES.DECLARATION).write_text("anchors: 1\nlanes:\n  exit_n: {lanelets: [1, 2]}\n")
            self.assertEqual(RES.main(["resolve", str(d), "--export", str(export)]), 0)
            doc = json.loads((d / RES.RESOLVED).read_text())
            self.assertEqual(set(doc["anchors"]), {"exit_n"})


class Chain(unittest.TestCase):
    def test_a_conflicts_position_feeds_a_lane_binding(self):
        """092 K9c: bind conflict_s = <conflict>.s_<lane>, then <lane>.lanelet_at($conflict_s):
        the lanelet and local s at the crossing, as a scenario places an entity there."""
        lane = {"kind": "lane", "lanelets": [{"id": 6583, "from_s": 0.0, "to_s": 224.22},
                                             {"id": 42664, "from_s": 224.22, "to_s": 245.6}],
                "length": 245.6, "speed_limit": 11.2, "start_x": 0.0, "start_y": 0.0,
                "end_x": 0.0, "end_y": 0.0, "heading_s": [0.0, 245.6], "heading": [3.14, -1.57]}
        conflict = {"kind": "conflict", "lanes": ["turn", "north"], "s_turn": 233.62,
                    "s_north": 55.14, "x": 92.39, "y": -131.19, "angle": -2.2,
                    "position_error": 0.0}
        numbers, functions = A.env({"turn": lane, "cross": conflict})
        self.assertEqual(numbers["anchor.cross.s_turn"], 233.62)
        self.assertNotIn("anchor.cross.lanes", numbers)
        vals = {}
        vals["conflict_s"] = A.bind("cross.s_turn", vals, numbers, functions)
        self.assertEqual(A.bind("turn.lanelet_at($conflict_s)", vals, numbers, functions), 42664)
        self.assertAlmostEqual(A.bind("turn.local_s($conflict_s)", vals, numbers, functions), 9.4)


class Merge(unittest.TestCase):
    def test_a_name_in_both_is_refused(self):
        with self.assertRaisesRegex(A.AnchorError, "exit_n: declared by the map"):
            A.merge({"exit_n": {"kind": "lane", "heading": 1.0}}, {"exit_n": {"heading_s": [0]}})
        self.assertEqual(set(A.merge({"a": {"kind": "lane", "length": 1}}, {"b": {}})), {"a", "b"})


if __name__ == "__main__":
    unittest.main()
