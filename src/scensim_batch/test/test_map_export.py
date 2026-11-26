"""Issue 194: map_export's centre points are SSv2's own line (LaneletLoader::
generateFineCenterline and resamplePoints, fork 31b12c5f lanelet_loader.cpp 137-255), ported:
3D lengths, SSv2's index search and arithmetic, refusals where SSv2 throws or gets NaN, a custom
centreline kept, CenterPointsCache's midpoint. No lanelet2."""
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scensim_batch import map_export as M


def close(test, a, b, tol=1e-12):
    test.assertEqual(len(a), len(b))
    for p, q in zip(a, b):
        for u, v in zip(p, q):
            test.assertAlmostEqual(u, v, delta=tol)


class Port(unittest.TestCase):
    def test_straight_bounds_of_unequal_length(self):
        # the longer bound (5 m) makes ceil(5 / 2) = 3 segments; each bound split in thirds
        left = [(0, 1, 0), (5, 1, 0)]
        right = [(0, -1, 0), (4, -1, 0)]
        c = M.ssv2_centerline(left, right)
        close(self, c, [[0, 0, 0], [1.5, 0, 0], [3.0, 0, 0], [4.5, 0, 0]])

    def test_a_two_point_bound_against_a_many_point_one(self):
        left = [(0, 1, 0), (6, 1, 0)]
        right = [(0, -1, 0), (1, -1, 0), (2, -1, 0), (3, -1, 0), (6, -1, 0)]
        c = M.ssv2_centerline(left, right)
        self.assertEqual(len(c), 4)                     # ceil(6 / 2) = 3 segments
        close(self, c, [[0, 0, 0], [2, 0, 0], [4, 0, 0], [6, 0, 0]])

    def test_lengths_are_3d_and_z_is_averaged(self):
        # a 3-4-5 slope: 3D length 5 (3 segments), 2D length 4 (2 segments)
        left = [(0, 1, 0), (4, 1, 3)]
        right = [(0, -1, 0), (4, -1, 3)]
        c = M.ssv2_centerline(left, right)
        self.assertEqual(len(c), 4)
        close(self, c, [[0, 0, 0], [4 / 3, 0, 1], [8 / 3, 0, 2], [4, 0, 3]])
        # one bound up, the other flat: z averaged
        c = M.ssv2_centerline([(0, 1, 0), (2, 1, 2)], [(0, -1, 0), (2, -1, 0)])
        self.assertAlmostEqual(c[-1][2], 1.0)

    def test_the_index_search_takes_the_earlier_segment_on_a_tie(self):
        # a target exactly on the middle point (t = 2 of 4): the earlier segment (0..2), at its
        # end, gives the same point as the later at its start; the order is SSv2's
        pts = [(0, 0, 0), (2, 0, 0), (4, 0, 0)]
        out = M._resample(pts, 2, "t")
        close(self, out, [[0, 0, 0], [2, 0, 0], [4, 0, 0]])
        # first and last segments: below acc[1] and above acc[N-2]
        pts = [(0, 0, 0), (1, 0, 0), (3, 0, 0), (4, 0, 0)]
        close(self, M._resample(pts, 4, "t"),
              [[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0], [4, 0, 0]])

    def test_the_arithmetic_is_ssv2s(self):
        # t = (i / n) * length; back + dir * (t - back_len) / seg_len, on an uneven polyline
        pts = [(0, 0, 0), (0.3, 0.1, 0.0), (1.7, 0.4, 0.2), (2.9, 0.0, 0.1)]
        acc = M._accumulated(pts)
        n = 3
        out = M._resample(pts, n, "t")
        for i, p in enumerate(out):
            t = (i / n) * acc[-1]
            j = 0 if t < acc[1] else (len(acc) - 2 if t > acc[-2] else
                                      next(k - 1 for k in range(1, len(acc))
                                           if acc[k - 1] <= t <= acc[k]))
            b, f = pts[j], pts[j + 1]
            want = [b[d] + (f[d] - b[d]) * (t - acc[j]) / (acc[j + 1] - acc[j]) for d in range(3)]
            self.assertEqual(p, want)                    # bit for bit

    def test_two_metres_is_one_segment_and_gets_the_midpoint(self):
        one = M.ssv2_centerline([(0, 1, 0), (2.0, 1, 0)], [(0, -1, 0), (2.0, -1, 0)])
        self.assertEqual(len(one), 2)                    # ceil(2.0 / 2.0) = 1
        self.assertEqual(len(M.midpoint(one)), 3)        # CenterPointsCache's midpoint
        two = M.ssv2_centerline([(0, 1, 0), (2.001, 1, 0)], [(0, -1, 0), (2.001, -1, 0)])
        self.assertEqual(len(two), 3)                    # ceil(2.0005) = 2
        self.assertEqual(len(M.midpoint(two)), 3)        # none added
        short = M.ssv2_centerline([(0, 1, 0), (0.5, 1, 0)], [(0, -1, 0), (0.5, -1, 0)])
        self.assertEqual(len(short), 2)                  # max(ceil(0.25), 1) = 1

    def test_what_ssv2_cannot_resample_is_refused_naming_the_lanelet(self):
        good = [(0, -1, 0), (3, -1, 0)]
        with self.assertRaisesRegex(M.ExportError, "lanelet 7: its left bound has 1 point"):
            M.ssv2_centerline([(0, 1, 0)], good, "lanelet 7")
        for bad, k in (([(0, 1, 0), (0, 1, 0), (3, 1, 0)], 0),            # at the start
                       ([(0, 1, 0), (3, 1, 0), (3, 1, 0)], 1)):           # at the end
            with self.assertRaisesRegex(M.ExportError,
                                        f"lanelet 7: its left bound repeats point {k} at {k + 1}"):
                M.ssv2_centerline(bad, good, "lanelet 7")
            with self.assertRaisesRegex(M.ExportError, "its right bound repeats"):
                M.ssv2_centerline(good, bad, "lanelet 7")

    def test_a_duplicate_in_the_middle_is_allowed_as_ssv2_allows_it(self):
        # the segment before the duplicate wins the tie, so SSv2 never selects the zero one
        mid = [(0, 1, 0), (1, 1, 0), (1, 1, 0), (3, 1, 0)]
        c = M.ssv2_centerline(mid, [(0, -1, 0), (3, -1, 0)], "lanelet 7")
        close(self, c, [[0, 0, 0], [1.5, 0, 0], [3, 0, 0]])

    def test_no_segment_holding_t_is_a_named_error(self):
        with self.assertRaisesRegex(M.ExportError, "lanelet 7 left: no segment holds"):
            M._resample([(0, 0, 0), (1, 0, 0), (float("nan"), 0, 0), (3, 0, 0)], 2,
                        "lanelet 7 left")


def lanelet(i, left, right, centre=()):
    pt = lambda p: SimpleNamespace(x=p[0], y=p[1], z=p[2])  # noqa: E731
    return SimpleNamespace(id=i, leftBound=[pt(p) for p in left],
                           rightBound=[pt(p) for p in right], centerline=[pt(p) for p in centre])


class CentrePoints(unittest.TestCase):
    def test_a_lanelet_without_a_custom_centreline_gets_ssv2s(self):
        ll = lanelet(1, [(0, 1, 0), (4, 1, 0)], [(0, -1, 0), (4, -1, 0)],
                     centre=[(0, 0.5, 0), (4, 0.5, 0)])       # lanelet2's, ignored
        close(self, M._centre_points(ll), [[0, 0, 0], [2, 0, 0], [4, 0, 0]])

    def test_a_custom_centreline_is_kept_then_given_its_midpoint(self):
        ll = lanelet(1, [(0, 1, 0), (4, 1, 0)], [(0, -1, 0), (4, -1, 0)],
                     centre=[(0, 0.5, 0), (4, 0.5, 0)])
        close(self, M._centre_points(ll, custom={1}), [[0, 0.5, 0], [2, 0.5, 0], [4, 0.5, 0]])

    def test_the_osms_centerline_role_is_read(self):
        osm = """<osm><node id="1" lat="0" lon="0"/><way id="5"><nd ref="1"/></way>
          <relation id="10"><member type="way" ref="5" role="left"/>
            <member type="way" ref="6" role="right"/><tag k="type" v="lanelet"/></relation>
          <relation id="11"><member type="way" ref="5" role="left"/>
            <member type="way" ref="6" role="right"/><member type="way" ref="7" role="centerline"/>
            <tag k="type" v="lanelet"/></relation></osm>"""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "lanelet2_map.osm"
            p.write_text(osm)
            self.assertEqual(M.custom_centerlines(p), {11})


if __name__ == "__main__":
    unittest.main()
