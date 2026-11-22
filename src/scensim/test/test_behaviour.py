"""scensim.behaviour (roadmap 092 K10): the gap-acceptance walker, its parameter set, and its
numpy and torch forms bit for bit on a closed loop (an ego driving through a crossing, the
walker integrated as the world would integrate its command)."""
import math
import random

import pytest

from scensim import behaviour
from scensim.behaviour import walker as w

xpmod = pytest.importorskip("sim_vehicle_ecu.xp")


def anchors():
    # a crossing of 7 m at x = 30, the ego driving +x along y = 1.75
    return {"kerb": [30.0, -1.75], "far": [30.0, 5.25], "conflict": [30.0, 1.75]}


def episode(xp, params, seeds, ego_speed, ego_decel_at=None, steps=400, dt=0.05):
    """A closed loop: the ego at constant speed (or braking at 4 m/s^2 from ego_decel_at s),
    the walker moved by its command. Returns, per step, the host copies of every output."""
    n = len(params)
    m = w.GapAcceptanceWalker(params, seeds, [anchors()] * n, xp)
    ex = xp.asarray([0.0] * n)
    ey = xp.full(n, 1.75)
    v = xp.asarray(ego_speed, xp.float64)
    wx, wy = xp.full(n, 30.0), xp.full(n, -1.75)
    ws = xp.zeros(n)
    trace = []
    for k in range(steps):
        a = xp.zeros(n)
        if ego_decel_at is not None and k * dt >= ego_decel_at:
            a = xp.where(v > 0.0, xp.full(n, -4.0), xp.zeros(n))
        obs = {"x": wx, "y": wy, "ego_x": ex, "ego_y": ey, "ego_vx": v, "ego_vy": xp.zeros(n),
               "ego_ax": a, "ego_ay": xp.zeros(n), "valid": xp.ones(n, xp.bool)}
        act, ev = m.step(obs, dt)
        # the world: the walker's speed toward its command within its acceleration limit
        lim = act["accel_limit"] * dt
        ws = ws + xp.minimum(xp.maximum(act["speed"] - ws, -lim), lim)
        wy = wy + ws * dt          # heading is +y here (kerb to far)
        v = xp.maximum(v + a * dt, xp.zeros(n))
        ex = ex + v * dt
        trace.append([xp.to_host(x).copy() for x in (act["speed"], ev, m.phase, m.wait_t,
                                                     m.decision_gap, m.decision_u, wy)])
    return m, trace


def params_mix(n, rng):
    styles = w.STYLES
    return [{"speed": rng.uniform(0.9, 2.2), "style": styles[i % 3], "group": rng.random() < 0.3,
             "lane": 1 + i % 2, "conflict_rate": rng.uniform(0.1, 1.0)} for i in range(n)]


def test_parameter_set_is_the_papers():
    s = behaviour.parameter_set("khaki2021_restricted")
    c = {k: v["beta"] for k, v in s["coefficients"].items()}
    assert c == {"intercept": -14.153, "PS": 1.817, "GR": -0.604, "TIME": -0.089,
                 "ROLL": 0.797, "GAP": 2.021, "LAG": 1.158, "YIELD": 1.854, "LANE": 1.593,
                 "RATE": 4.846}
    assert s["source"]["id"] == "arXiv:2101.10903" and s["source"]["licence"] == "CC0-1.0"
    assert len(s["sha256"]) == 64
    # the cross-check: the meta-analysis's pooled odds ratio for the gap
    assert abs(math.log(s["cross_check"]["gap_odds_ratio_per_s"]) - c["GAP"]) < 0.05
    with pytest.raises(ValueError, match="no parameter set"):
        behaviour.parameter_set("nope")


def test_fifty_percent_gap_at_the_sample_means():
    """At the paper's sample means (PS 1.37, RATE 0.462), alone, a lag, the near lane, no
    yield, no wait: U = 0 at a gap of 3.3 s, the sample's mean gap 3.29 s."""
    s = behaviour.parameter_set("khaki2021_restricted")
    b = {k: v["beta"] for k, v in s["coefficients"].items()}
    const = b["intercept"] + b["PS"] * 1.37 + b["LAG"] + b["LANE"] + b["RATE"] * 0.462
    assert -const / b["GAP"] == pytest.approx(3.3, abs=0.05)


def test_params_are_checked_by_name():
    with pytest.raises(ValueError, match="unknown parameter 'sped'"):
        w.resolve({"sped": 1.0})
    with pytest.raises(ValueError, match="speed: 9.0 outside"):
        w.resolve({"speed": 9.0})
    with pytest.raises(ValueError, match="style: 'dance'"):
        w.resolve({"style": "dance"})
    assert w.resolve({"group": "true"})["group"] is True


def test_acceptance_follows_the_logit():
    """Over many walkers offered one gap, the accepted fraction is P(U) (binomial bound)."""
    xp = xpmod.namespace("numpy")
    n = 4000
    gap_s = 3.0
    p = [{"speed": 1.4, "conflict_rate": 0.462}] * n
    m = w.GapAcceptanceWalker(p, list(range(n)), [anchors()] * n, xp)
    v = 10.0
    obs = {"x": xp.full(n, 30.0), "y": xp.full(n, -1.75), "ego_x": xp.full(n, 30.0 - v * gap_s),
           "ego_y": xp.full(n, 1.75), "ego_vx": xp.full(n, v), "ego_vy": xp.zeros(n),
           "ego_ax": xp.zeros(n), "ego_ay": xp.zeros(n), "valid": xp.ones(n, xp.bool)}
    _, ev = m.step(obs, 0.05)
    frac = float((ev == w.GO).mean())
    s = behaviour.parameter_set("khaki2021_restricted")
    b = {k: x["beta"] for k, x in s["coefficients"].items()}
    u = b["intercept"] + b["PS"] * 1.4 + b["LAG"] + b["LANE"] + b["RATE"] * 0.462 + b["GAP"] * gap_s
    pr = 1.0 / (1.0 + math.exp(-u))
    assert abs(frac - pr) < 4 * math.sqrt(pr * (1 - pr) / n)
    assert float(m.decision_gap[0]) == pytest.approx(gap_s)


def test_reject_waits_for_the_ego_then_crosses():
    xp = xpmod.namespace("numpy")
    # a seed whose draw rejects a short gap: find one by its threshold
    seed = next(s for s in range(1000) if w.GapAcceptanceWalker.draw(s) > 0.0)
    m, tr = episode(xp, [{"speed": 1.4}], [seed], [12.0], steps=300)
    events = [int(t[1][0]) for t in tr]
    assert events[0] == w.REJECT          # 2.5 s away at 12 m/s: U < 0 < threshold
    k_after = events.index(w.GO_AFTER)
    assert k_after * 0.05 > 30.0 / 12.0 - 0.1   # only once the ego has passed x = 30
    assert w.DONE in events
    rec = m.record()[0]
    assert rec["parameter_set"]["name"] == "khaki2021_restricted"
    assert rec["decision"]["gap_s"] == pytest.approx(2.5)


def usable_torch():
    """torch, if it can take this NumPy's arrays; else a skip naming why. A user-site NumPy 2
    against a torch built for NumPy 1 imports, then fails at the first conversion
    ("_ARRAY_API not found", "Numpy is not available")."""
    torch = pytest.importorskip("torch")
    import numpy as np
    try:
        torch.as_tensor(np.zeros(1))
    except Exception as e:
        pytest.skip(f"torch {torch.__version__} cannot take NumPy {np.__version__}'s arrays "
                    f"({type(e).__name__}: {e}); a NumPy built for another ABI, e.g. a user-site "
                    "NumPy 2 against the system torch: run in the gate's environment, or with "
                    "PYTHONNOUSERSITE=1")
    return torch


def test_numpy_and_torch_agree_bit_for_bit():
    torch = usable_torch()
    rng = random.Random(7)
    n = 96
    params = params_mix(n, rng)
    seeds = [rng.randrange(1 << 30) for _ in range(n)]
    speeds = [rng.uniform(4.0, 16.0) for _ in range(n)]
    out = {}
    for name in ("numpy", "torch"):
        xp = xpmod.namespace(name)
        _, tr = episode(xp, params, seeds, speeds, ego_decel_at=1.0)
        out[name] = tr
    for k, (a, b) in enumerate(zip(out["numpy"], out["torch"])):
        for j, (x, y) in enumerate(zip(a, b)):
            assert x.tobytes() == y.tobytes(), f"step {k}, output {j}"
    # every behaviour happened somewhere, so the agreement is not vacuous
    seen = {int(e) for t in out["numpy"] for e in t[1]}
    assert {w.GO, w.REJECT, w.GO_AFTER, w.HESITATE, w.RESUME, w.DONE} <= seen
    del torch
