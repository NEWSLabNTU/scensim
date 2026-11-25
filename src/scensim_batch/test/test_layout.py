"""Engine A's slot layout (issue 113): no slot's route box within the gap of another's.

Plain unittest, no pytest: the suite also runs in Isaac's own Python, which has none (issues
090 and 186)."""
import math
import unittest

import numpy as np

from scensim_batch import layout
from scensim_batch.tasks import leadbrake as LB

BOX = LB.route_box(1.25 * 5.22, 0.05)


class Layout(unittest.TestCase):

    def test_leadbrake_box_covers_a_step_past_its_bounds_at_its_fastest(self):
        x0, x1, hw = BOX
        v_max = math.sqrt(LB.RANGES["lead_speed"][1] ** 2 + 2 * 1.25 * 5.22 * LB.ROUTE)
        self.assertGreaterEqual(hw, LB.OFF_ROAD + v_max * 0.05 + LB.FRONT)
        self.assertGreaterEqual(x1, LB.EGO_S + LB.ROUTE + v_max * 0.05 + LB.FRONT)
        self.assertLessEqual(x0, LB.EGO_S - LB.FRONT)

    def test_layout_has_no_overlap_and_fits_the_ground(self):
        for n in (2, 4, 64, 1024, 4096):
            with self.subTest(n=n):
                ground = (4000.0, 4000.0) if n <= 1024 else (12000.0, 12000.0)
                o = layout.route_layout(n, BOX, ground, 3.0)
                self.assertEqual(o.shape, (n, 2))
                self.assertEqual(layout.route_overlaps(o, BOX, 3.0), [])
                x0, x1, hw = BOX
                self.assertGreaterEqual((o[:, 0] + x0).min(), -ground[0] / 2 - 1e-6)
                self.assertLessEqual((o[:, 0] + x1).max(), ground[0] / 2 + 1e-6)
                self.assertGreaterEqual((o[:, 1] - hw).min(), -ground[1] / 2 - 1e-6)
                self.assertLessEqual((o[:, 1] + hw).max(), ground[1] / 2 + 1e-6)

    def test_layout_without_ground_is_about_square_and_apart(self):
        o = layout.route_layout(16, (-10.0, 150.0, 6.0), None, 3.0)
        self.assertEqual(layout.route_overlaps(o, (-10.0, 150.0, 6.0), 3.0), [])

    def test_layout_refuses_a_ground_too_small(self):
        with self.assertRaisesRegex(ValueError, "do not fit"):
            layout.route_layout(1024, BOX, (1000.0, 1000.0), 3.0)

    def test_isaac_lab_grid_at_10_m_overlaps(self):
        """Stock's grid (what engine A had: issue 113): every neighbour's box overlaps."""
        side = 32
        g = np.array([((i % side) * 10.0, (i // side) * 10.0) for i in range(side * side)])
        self.assertGreater(len(layout.route_overlaps(g, BOX, 3.0)), 1000)

    def test_min_separation(self):
        d, pair = layout.min_separation([[0.0, 0.0], [10.0, 0.0], [10.0, 4.0]])
        self.assertAlmostEqual(d, 4.0, delta=4e-6)
        self.assertEqual(pair, (1, 2))
        self.assertEqual(layout.min_separation([[0.0, 0.0]]), (math.inf, None))

    def test_engine_a_refuses_many_slots_without_a_box(self):
        with self.assertRaisesRegex(ValueError, "no route_box"):
            layout.engine_a_origins(2, (), None, 3.0)
        self.assertEqual(layout.engine_a_origins(1, (), None, 3.0).tolist(), [[0.0, 0.0]])
        o = layout.engine_a_origins(64, BOX, (4000.0, 4000.0), 3.0)
        self.assertGreaterEqual(layout.min_separation(o)[0], 2 * BOX[2] + 3.0 - 1e-6)


if __name__ == "__main__":
    unittest.main()
