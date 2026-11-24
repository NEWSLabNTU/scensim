"""092 K10's close-out (1): each engine gives the ego's map-frame velocity (vx_map, vy_map), and
a behaviour model reads it, not v along the heading. A sliding ego: 10 m/s forward and 2 m/s to
its left, yawed 30 degrees (engine A's also pitched 5 degrees, with 0.3 m/s along its up axis)."""
import math
import sys
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "scensim"))

try:
    import numpy as np
    import torch
except ImportError:
    torch = None

YAW, PITCH = math.radians(30.0), math.radians(5.0)
BODY = (10.0, 2.0, 0.3)


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def quat_wxyz(yaw, pitch):
    """Yaw about z, then pitch about the body's y: R = Rz(yaw) Ry(pitch)."""
    cy, sy, cp, sp = math.cos(yaw / 2), math.sin(yaw / 2), math.cos(pitch / 2), math.sin(pitch / 2)
    return (cy * cp, -sy * sp, cy * sp, sy * cp)


def model_reads(st):
    """What Models.step hands a behaviour model as the ego's velocity, on state `st`."""
    from scensim_batch import core
    seen = {}

    class Stub:
        def step(self, obs, dt):
            seen["v"] = (float(obs["ego_vx"][0]), float(obs["ego_vy"][0]))
            z = torch.zeros(1, dtype=torch.float64)
            return {"speed": z, "heading": z, "accel_limit": z + 1}, torch.zeros(1)

    m = core.Models.__new__(core.Models)
    m.idx, m.models, m.events, m._prev_v, m.pending = [0], [Stub()], {}, None, [None]
    m.follower = [False]
    m.run = types.SimpleNamespace(c=types.SimpleNamespace(
        n=1, entities=[types.SimpleNamespace(name="walker")]))
    zz = torch.zeros(1, 1, dtype=torch.float64)
    m.x, m.y, m.yaw, m.v = zz.clone(), zz.clone(), zz.clone(), zz.clone()
    m.step(st, 0.05)
    return seen["v"]


@unittest.skipIf(torch is None, "no torch")
class EngineB(unittest.TestCase):
    def state(self):
        from scensim_batch.articulation import ArticulationModel
        m = ArticulationModel.__new__(ArticulationModel)
        m.device = None
        lin = rot_z(YAW) @ np.array([BODY[0], BODY[1], 0.0])
        q = (0.0, 0.0, math.sin(YAW / 2), math.cos(YAW / 2))      # xyzw
        st, _ = m.state([[100.0, 50.0, 0.0]], [q], [lin], [[0.0, 0.0, 0.0]], [[0.0] * 4],
                        None, None, [[90.0, 40.0]])
        return st, lin

    def test_a_sliding_egos_map_velocity_is_the_worlds(self):
        st, lin = self.state()
        self.assertAlmostEqual(float(st["vx_map"][0]), lin[0], delta=1e-12)
        self.assertAlmostEqual(float(st["vy_map"][0]), lin[1], delta=1e-12)
        self.assertAlmostEqual(float(st["v"][0]), BODY[0], delta=1e-12)   # still along the body

    def test_the_model_reads_it(self):
        st, lin = self.state()
        vx, vy = model_reads(st)
        self.assertAlmostEqual(vx, lin[0], delta=1e-12)
        self.assertAlmostEqual(vy, lin[1], delta=1e-12)
        self.assertGreater(abs(vy - BODY[0] * math.sin(YAW)), 1.0)   # not v along the heading


@unittest.skipIf(torch is None, "no torch")
class EngineA(unittest.TestCase):
    def expected(self):
        return rot_z(YAW) @ rot_y(PITCH) @ np.array(BODY)

    def state(self):
        from scensim_batch.physx_vehicle import PhysxVehicleBackend
        b = PhysxVehicleBackend.__new__(PhysxVehicleBackend)
        b.n, b.origins = 1, np.zeros((1, 2))
        b.cars = [types.SimpleNamespace(wheel_states=None)]
        b.states = [types.SimpleNamespace(position=(5.0, 6.0, 0.0), quat=quat_wxyz(YAW, PITCH),
                                          velocity=BODY, angular_velocity=(0.0, 0.0, 0.0),
                                          acceleration=(0.0, 0.0, 0.0))]
        return b.state()

    def test_the_quaternion_is_the_rotation_the_test_means(self):
        from scensim_batch.physx_vehicle import map_velocity
        e = self.expected()
        got = map_velocity(quat_wxyz(YAW, PITCH), BODY)
        self.assertAlmostEqual(got[0], e[0], delta=1e-12)
        self.assertAlmostEqual(got[1], e[1], delta=1e-12)

    def test_a_sliding_pitched_egos_map_velocity(self):
        st, e = self.state(), self.expected()
        self.assertAlmostEqual(float(st["vx_map"][0]), e[0], delta=1e-12)
        self.assertAlmostEqual(float(st["vy_map"][0]), e[1], delta=1e-12)

    def test_the_model_reads_it(self):
        e = self.expected()
        vx, vy = model_reads(self.state())
        self.assertAlmostEqual(vx, e[0], delta=1e-12)
        self.assertAlmostEqual(vy, e[1], delta=1e-12)


if __name__ == "__main__":
    unittest.main()
