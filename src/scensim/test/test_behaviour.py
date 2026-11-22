"""scensim.behaviour (roadmap 092 K10): the gap-acceptance walker, its parameter set, and its
numpy and torch forms bit for bit on a closed loop (an ego driving through a crossing, the
walker integrated as the world would integrate its command)."""
import math
import random
import sys

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
    wx = xp.full(n, 30.0)
    wy = xp.asarray([-1.75 - p.get("approach", 0.0) for p in params])   # hidden behind the kerb
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
    out = [{"speed": rng.uniform(0.9, 2.2), "style": styles[i % 3], "group": rng.random() < 0.3,
            "lane": 1 + i % 2, "conflict_rate": rng.uniform(0.1, 1.0)} for i in range(n)]
    for i in range(3, n, 4):       # every fourth hidden until a start gap (CS1)
        out[i]["start_gap"] = rng.uniform(1.0, 3.0)
        out[i]["approach"] = rng.uniform(0.5, 2.0)
    return out


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


# what a torch built for another NumPy ABI says (a user-site NumPy 2 against the system torch,
# built for NumPy 1); only these are a skip: any other failure is a broken torch, and fails
ABI_MISMATCH = ("_ARRAY_API", "Numpy is not available", "compiled using NumPy",
                "numpy.core.multiarray failed to import")
HINT = ("a NumPy built for another ABI, e.g. a user-site NumPy 2 against the system torch: run "
        "in the gate's environment, or with PYTHONNOUSERSITE=1")
PROBE = ("import numpy, torch\n"
         "torch.as_tensor(numpy.zeros(1))\n"
         "print('ok', numpy.__version__, torch.__version__)\n")
_probe_cache = []


def probe_torch():
    """Whether torch imports and takes NumPy's arrays, asked once per session of a separate
    interpreter (this one's executable and environment), so a torch that fails never loads
    here: a failed `import torch` leaves a half-initialised module behind, and touching it
    crashes the interpreter (243's segfault). Returns (ok, the probe's output)."""
    if not _probe_cache:
        import subprocess
        r = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True,
                           timeout=300)
        _probe_cache.append((r.returncode == 0, (r.stdout + r.stderr).strip()))
    return _probe_cache[0]


def judge_probe(ok, text):
    """What a probe's outcome means: None (usable), or a skip or a failure. Only a missing
    torch and the NumPy ABI mismatch skip; anything else fails, with the probe's output."""
    if ok:
        return None
    if "No module named 'torch'" in text:
        return ("skip", "no torch")
    if any(m in text for m in ABI_MISMATCH):
        last = text.strip().splitlines()[-1] if text.strip() else ""
        return ("skip", f"torch does not work with this NumPy ({last}); {HINT}")
    return ("fail", f"torch is broken (not the NumPy ABI mismatch):\n{text}")


def usable_torch():
    """torch, imported here only if the probe passed; else a skip or a failure."""
    verdict = judge_probe(*probe_torch())
    if verdict is not None:
        kind, why = verdict
        (pytest.skip if kind == "skip" else pytest.fail)(why)
    import torch
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
    assert {w.GO, w.REJECT, w.GO_AFTER, w.HESITATE, w.RESUME, w.DONE, w.APPEAR} <= seen
    del torch


# the probe's verdicts, on synthetic outcomes: no real torch, no real array conversion, so
# they read the same on every host

def test_a_torch_that_fails_to_import_is_a_skip():
    """The failure 243's shell had: `import torch` itself raising AttributeError."""
    text = ("Traceback (most recent call last):\n  File \"<string>\", line 1\n"
            "AttributeError: _ARRAY_API not found")
    kind, why = judge_probe(False, text)
    assert kind == "skip" and "_ARRAY_API not found" in why and "PYTHONNOUSERSITE=1" in why


def test_a_torch_that_cannot_convert_is_a_skip():
    kind, why = judge_probe(False, "RuntimeError: Numpy is not available")
    assert kind == "skip" and "Numpy is not available" in why


def test_no_torch_is_a_skip():
    assert judge_probe(False, "ModuleNotFoundError: No module named 'torch'") == ("skip", "no torch")


def test_an_unrelated_import_error_fails():
    """A broken torch that is not the ABI mismatch is not hidden as a skip."""
    kind, why = judge_probe(False, "AttributeError: module 'torch._C' has no attribute "
                                   "'_cuda_getDevice'")
    assert kind == "fail" and "_cuda_getDevice" in why


def test_an_unrelated_conversion_error_fails():
    kind, why = judge_probe(False, "RuntimeError: CUDA error: an illegal memory access was "
                                   "encountered")
    assert kind == "fail" and "illegal memory access" in why


def test_a_good_probe_is_usable():
    assert judge_probe(True, "ok 1.21.5 1.8.0") is None


def test_usable_torch_never_imports_after_a_failed_probe(monkeypatch):
    """After a failed probe, usable_torch skips without importing torch in this interpreter."""
    import builtins
    real = builtins.__import__

    def guard(name, *a, **k):
        if name == "torch" or name.startswith("torch."):
            raise AssertionError("torch imported after a failed probe")
        return real(name, *a, **k)

    monkeypatch.setattr(sys.modules[__name__], "_probe_cache",
                        [(False, "AttributeError: _ARRAY_API not found")])
    monkeypatch.setattr(builtins, "__import__", guard)
    with pytest.raises(pytest.skip.Exception, match="_ARRAY_API"):
        usable_torch()


def test_a_hidden_walker_appears_at_its_start_gap_and_decides_at_the_kerb():
    """CS1: behind the van until the ego is start_gap away in time, then `approach` metres to
    the kerb at its speed, and the decision there sees the gap as it is then."""
    xp = xpmod.namespace("numpy")
    v, dt, approach, start_gap, speed = 10.0, 0.05, 1.4, 2.5, 1.4
    p = {"speed": speed, "start_gap": start_gap, "approach": approach}
    m = w.GapAcceptanceWalker([p], [3], [anchors()], xp)
    assert int(m.phase[0]) == w.HIDDEN
    ex, wy, ws, events = 0.0, -1.75 - approach, 0.0, []
    for k in range(200):
        obs = {"x": xp.asarray([30.0]), "y": xp.asarray([wy]), "ego_x": xp.asarray([ex]),
               "ego_y": xp.asarray([1.75]), "ego_vx": xp.asarray([v]), "ego_vy": xp.zeros(1),
               "ego_ax": xp.zeros(1), "ego_ay": xp.zeros(1), "valid": xp.ones(1, xp.bool)}
        act, ev = m.step(obs, dt)
        events.append((k, int(ev[0])))
        ws = float(act["speed"][0])        # an ideal world: the command at once
        wy += ws * dt
        ex += v * dt
    seq = [e for _, e in events if e]
    assert seq[0] == w.APPEAR and seq[1] in (w.GO, w.REJECT)   # the decision at the kerb
    k_appear = next(k for k, e in events if e == w.APPEAR)
    assert (30.0 - k_appear * dt * v) / v == pytest.approx(start_gap, abs=v * dt / v)
    # it decides where it can still stop at the kerb, speed^2 / (2 accel_limit) = 0.65 m before
    # it: the ego is closer by the walk to there, (1.4 - 0.65) m at 1.4 m/s
    stop = speed ** 2 / (2 * 1.5)
    assert float(m.decision_gap[0]) == pytest.approx(start_gap - (approach - stop) / speed,
                                                     abs=0.11)
