"""scensim.behaviour's car-follower (roadmap 092 K13): the Intelligent Driver Model on a lane,
its parameter set, and its numpy and torch forms bit for bit on a closed loop (a leader on a
lane, the follower integrated as the world integrates its command, K12 D5)."""
import math
import random

import pytest

from scensim import behaviour
from scensim.behaviour import follower as f

xpmod = pytest.importorskip("sim_vehicle_ecu.xp")
from test_behaviour import cuda_unusable, usable_torch  # noqa: E402

DT = 0.05


def straight_lane(length=400.0, limit=25.0):
    xs = [float(i) for i in range(0, int(length) + 1, 5)]
    return {"kind": "lane", "length": length, "speed_limit": limit,
            "x": xs, "y": [0.0] * len(xs)}


def arc_lane(radius=60.0, angle=math.pi, limit=13.89):
    n = 200
    th = [angle * i / (n - 1) for i in range(n)]
    return {"kind": "lane", "length": radius * angle, "speed_limit": limit,
            "x": [radius * math.sin(t) for t in th],
            "y": [radius * (1.0 - math.cos(t)) for t in th]}


def world(xp, act, v, x, y, dt=DT, trig=None):
    """K12 D5: the speed toward the command within its limit, the yaw set to the heading, the
    position moved v dt along it. `trig`: (cos, sin) of the heading (xp's sin_cos, or math)."""
    lim = act["accel_limit"] * dt
    v = v + xp.minimum(xp.maximum(act["speed"] - v, -lim), lim)
    c, s = trig(act["heading"])
    return v, x + v * c * dt, y + v * s * dt


def xp_trig(xp):
    return lambda h: xpmod.sin_cos(xp, h)[::-1]


def run(xp, params, lane, x0, v0, lead_x0, lead_v, lead_decel_at=None, lead_decel=0.0,
        steps=600, trig=None, leader=True):
    """A closed loop on `lane` (straight along +x unless `trig` says otherwise): the leader
    driving along x at lead_v (braking at lead_decel from lead_decel_at s), the follower moved
    by its command. Per step, host copies of (speed, heading, accel_limit, events, x, y, v,
    leader x)."""
    n = len(params)
    m = f.IdmFollower(params, [0] * n, [{"lane": lane}] * n, xp)
    trig = trig or xp_trig(xp)
    x = xp.asarray(x0, xp.float64)
    y = xp.zeros(n)
    v = xp.asarray(v0, xp.float64)
    lx = xp.asarray(lead_x0, xp.float64)
    lv = xp.asarray(lead_v, xp.float64)
    out = []
    for k in range(steps):
        obs = {"x": x, "y": y, "vx": v * trig(xp.zeros(n))[0], "vy": xp.zeros(n),
               "leader_x": lx, "leader_y": xp.zeros(n), "leader_vx": lv,
               "leader_vy": xp.zeros(n), "leader_valid": xp.full(n, leader, xp.bool),
               "valid": xp.ones(n, xp.bool)}
        act, ev = m.step(obs, DT)
        v, x, y = world(xp, act, v, x, y, trig=trig)
        if lead_decel_at is not None and k * DT >= lead_decel_at:
            lv = xp.maximum(lv - xp.full(n, lead_decel * DT), xp.zeros(n))
        lx = lx + lv * DT
        out.append([xp.to_host(a).copy() for a in (act["speed"], act["heading"],
                                                    act["accel_limit"], ev, x, y, v, lx)])
    return m, out


def equilibrium_gap(v, v0, s0, T):
    return (s0 + v * T) / math.sqrt(1.0 - (v / v0) ** 4)


def test_parameter_set_is_the_papers():
    s = behaviour.parameter_set("zhang2024_highd_car")
    assert s["form"] == "idm" and s["source"]["id"] == "arXiv:2210.03571"
    assert s["source"]["licence"] == "CC-BY-4.0"
    # Table I, "Pooled MA-IDM (car)": [v0, s0, T, alpha, beta]
    c = s["coefficients"]
    assert [c[k] for k in ("v0", "s0", "T", "a", "b")] == [12.244, 2.833, 1.133, 0.362, 2.140]
    assert c["delta"] == 4 and len(s["sha256"]) == 64


def test_params_are_checked_by_name():
    lane = {"lane": straight_lane()}
    np_ = xpmod.namespace("numpy")
    with pytest.raises(ValueError, match="unknown parameter 'speed'"):
        f.IdmFollower([{"lane": "l", "speed": 3.0}], [0], [lane], np_)
    with pytest.raises(ValueError, match="T: 9.0 outside"):
        f.IdmFollower([{"lane": "l", "T": 9.0}], [0], [lane], np_)
    with pytest.raises(ValueError, match="lane: the lane anchor it holds is required"):
        f.IdmFollower([{}], [0], [lane], np_)
    with pytest.raises(ValueError, match="above the vehicle's max_accel"):
        f.IdmFollower([{"lane": "l", "a": 3.0, "max_accel": 2.0}], [0], [lane], np_)
    with pytest.raises(ValueError, match="above the vehicle's max_decel"):
        f.IdmFollower([{"lane": "l", "b": 5.0, "max_decel": 4.0}], [0], [lane], np_)


def test_v0_is_the_lanes_limit_and_the_rest_the_sets():
    m = f.IdmFollower([{"lane": "l"}], [0], [{"lane": straight_lane(limit=13.89)}],
                      xpmod.namespace("numpy"))
    r = m.record()[0]
    assert r["params"]["v0"] == 13.89
    assert (r["params"]["s0"], r["params"]["T"], r["params"]["a"], r["params"]["b"]) == \
        (2.833, 1.133, 0.362, 2.140)
    assert r["parameter_set"]["name"] == "zhang2024_highd_car"


def test_steady_following_keeps_the_equilibrium_gap():
    """At the equilibrium gap IDM's acceleration is 0: the follower keeps it."""
    xp = xpmod.namespace("numpy")
    v, v0 = 10.0, 25.0
    p = {"lane": "l", "leader": "lead"}
    s_e = equilibrium_gap(v, v0, 2.833, 1.133)
    lead_x = 50.0 + s_e + 4.5            # rear to front: half of each 4.5 m length
    _, out = run(xp, [p], straight_lane(), [50.0], [v], [lead_x], [v], steps=200)
    gap = out[-1][7][0] - out[-1][4][0] - 4.5
    assert abs(gap - s_e) / s_e < 1e-9
    assert abs(out[-1][6][0] - v) < 1e-9


def test_a_free_road_approaches_v0_without_overshoot():
    xp = xpmod.namespace("numpy")
    _, out = run(xp, [{"lane": "l", "a": 1.5}], straight_lane(length=3000.0, limit=20.0),
                 [0.0], [0.0], [1e9], [0.0], steps=600, leader=False)
    speeds = [o[6][0] for o in out]       # 30 s, before the lane's end (2.6 km on) brakes it
    assert all(b >= a for a, b in zip(speeds, speeds[1:]))
    assert max(speeds) <= 20.0
    assert speeds[-1] > 0.95 * 20.0


def test_it_stops_behind_a_standing_car():
    xp = xpmod.namespace("numpy")
    m, out = run(xp, [{"lane": "l", "leader": "lead"}], straight_lane(), [0.0], [10.0],
                 [150.0], [0.0], steps=1200)
    gap = out[-1][7][0] - out[-1][4][0] - 4.5
    assert out[-1][6][0] < 0.05
    assert 0.5 * 2.833 < gap < 2.833 + 0.5
    assert f.STOPPED in {int(o[3][0]) for o in out}
    assert f.CAPPED not in {int(o[3][0]) for o in out}


def test_the_lanes_end_is_a_standing_obstacle():
    xp = xpmod.namespace("numpy")
    _, out = run(xp, [{"lane": "l"}], straight_lane(length=200.0, limit=15.0), [0.0], [10.0],
                 [1e9], [0.0], steps=1200, leader=False)
    front = out[-1][4][0] + 2.25
    assert out[-1][6][0] < 0.05 and 200.0 - 3.5 < front < 200.0


def test_a_hard_brake_close_ahead_binds_the_cap():
    """IDM's own deceleration is unbounded; the cap is the vehicle's, and binding it is an event."""
    xp = xpmod.namespace("numpy")
    p = {"lane": "l", "leader": "lead", "max_decel": 6.0}
    _, out = run(xp, [p], straight_lane(), [0.0], [20.0], [4.5 + 12.0], [20.0],
                 lead_decel_at=0.5, lead_decel=9.0, steps=400)
    evs = [int(o[3][0]) for o in out]
    assert evs.count(f.CAPPED) > 0
    assert min(o[2][0] for o in out) >= 1e-3      # accel_limit never 0
    dv = [(out[k + 1][6][0] - out[k][6][0]) / DT for k in range(len(out) - 1)]
    assert min(dv) >= -6.0 - 1e-9


def test_it_keeps_to_a_curved_lane():
    """On a half circle of 60 m radius the world moves it along its heading; the heading's
    correction keeps it on the centreline."""
    import numpy as np
    xp = xpmod.namespace("numpy")
    lane = arc_lane()
    m = f.IdmFollower([{"lane": "l"}], [0], [{"lane": lane}], xp)
    x, y, v = np.array([0.0]), np.array([0.0]), np.array([8.0])
    worst = 0.0
    for _ in range(400):
        h = 0.0
        obs = {"x": x, "y": y, "vx": v * math.cos(h), "vy": v * math.sin(h),
               "leader_x": x, "leader_y": y, "leader_vx": v, "leader_vy": v,
               "leader_valid": np.array([False]), "valid": np.array([True])}
        act, _ = m.step(obs, DT)
        lim = act["accel_limit"] * DT
        v = v + np.minimum(np.maximum(act["speed"] - v, -lim), lim)
        h = float(act["heading"][0])
        x, y = x + v * math.cos(h) * DT, y + v * math.sin(h) * DT
        r = math.hypot(float(x[0]), float(y[0]) - 60.0)
        if float(y[0]) < 119.0:
            worst = max(worst, abs(r - 60.0))
    assert worst < 0.1


def params_mix(n, rng):
    return [{"lane": "l", "leader": "lead", "T": rng.uniform(0.6, 2.4),
             "a": rng.uniform(0.3, 2.0), "b": rng.uniform(1.0, 3.5), "s0": rng.uniform(1.0, 4.0),
             "max_decel": rng.uniform(4.0, 9.0)} for _ in range(n)]


def closed_loop(name, device=None):
    rng = random.Random(11)
    n = 96
    params = params_mix(n, rng)
    x0 = [rng.uniform(0.0, 20.0) for _ in range(n)]
    v0 = [rng.uniform(5.0, 20.0) for _ in range(n)]
    lead = [x + rng.uniform(8.0, 40.0) for x in x0]
    xp = xpmod.namespace(name, device)
    return run(xp, params, straight_lane(length=600.0), x0, v0, lead,
               [rng.uniform(5.0, 20.0) for _ in range(n)], lead_decel_at=2.0,
               lead_decel=6.0, steps=400)[1]


def compare(a, b):
    for k, (sa, sb) in enumerate(zip(a, b)):
        for j, (x, y) in enumerate(zip(sa, sb)):
            assert x.tobytes() == y.tobytes(), f"step {k}, output {j}"


def test_numpy_and_torch_on_the_cpu_agree_bit_for_bit():
    usable_torch()
    a, b = closed_loop("numpy"), closed_loop("torch")
    compare(a, b)
    seen = {int(e) for s in a for e in s[3]}
    assert {f.FOLLOW, f.CAPPED, f.STOPPED} <= seen      # not vacuous


def test_torch_on_a_gpu_agrees_with_numpy():
    """sim_vehicle_ecu.xp runs one operation per kernel on CUDA, nothing fused: expected bit for
    bit there too (its own tests check it); the bound K13 states for a GPU is 0 differing
    arrays, checked here when a GPU is present."""
    torch = usable_torch()
    why = cuda_unusable(torch)      # issue 179: a card this torch has no kernel for is a skip
    if why:
        pytest.skip(why)
    compare(closed_loop("numpy"), closed_loop("torch", "cuda"))


def test_a_lane_resolved_without_its_centreline_has_it_rebuilt_from_its_headings():
    """K9's anchors resolved before the centreline was recorded carry only the headings: the
    lane is rebuilt from them (on the half circle of 199 steps, within 2 mm of the arc at its
    end: each step a chord of the arc)."""
    lane = arc_lane()
    n = len(lane["x"])
    ss = [lane["length"] * i / (n - 1) for i in range(n)]
    old = {"kind": "lane", "length": lane["length"], "speed_limit": lane["speed_limit"],
           "start_x": 0.0, "start_y": 0.0, "heading_s": ss,
           "heading": [math.pi * i / (n - 1) for i in range(n)]}
    c = f.centreline_of(old)
    assert math.hypot(c["x"][-1] - lane["x"][-1], c["y"][-1] - lane["y"][-1]) < 2e-3
    m = f.IdmFollower([{"lane": "l"}], [0], [{"lane": old}], xpmod.namespace("numpy"))
    assert m.K > 0
