"""The search (purpose B, roadmap 092 K11): the cross-entropy method over one cell of a scenario,
each generation a proposal file, stepped from outside, and the rate from a fresh stage.

    scensim-sample search init spec.yaml -o dir      # g0 and its draws (g0.yaml, g0.jsonl)
    scensim-sample search next dir --outcomes g0.out.jsonl   # refit: g1 (or the fresh stage)
    scensim-sample search report dir                 # the estimate and the failures found

The method is de Boer, Kroese, Mannor and Rubinstein, "A Tutorial on the Cross-Entropy
Method" (Annals of OR 134, 2005): draw N from the current density, take the most critical
fraction rho by the score as the elite, set the level gamma_t to the elite's least critical
score (never past the failure threshold), and refit the density to the elite, each sample
weighted by base / the density it was drawn from; smooth the update by alpha. Each generation is
drawn from the defensive mixture (1 - beta) g_t + beta base (Hesterberg 1995), through the
importance plug-in's `defensive:`. When the level reaches the threshold, or after the last
generation, N fresh draws from the last mixture give the rate, with the plain likelihood-ratio
estimator: the generations chose their densities from their own draws, so an estimate from
them is biased, and is reported only as a diagnostic.

The weights must be exact density ratios for the plain estimator. A range's truncation is
renormalised by the distributions themselves (scensim_sampler.dist). Constraints are not: they
draw from base 1_C / Z_b and from q 1_C / Z_q, so the weight is (base / q) (Z_q / Z_b). Both
acceptance probabilities are estimated by drawing (constraints need no simulation), and the
record carries the ratio as `search.normaliser`, with the binomial errors in the estimate's
standard error.

A score is lower for more critical, and a run fails when its score is at most the threshold
(K11: the closest gap, box to box, at most 0 m). The parameters are fixed (092, "K11's plan").
"""
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
import yaml

from . import record as R
from .dist import Categorical, LogNormal, Normal, SpecError, Uniform
from .expr import Expr
from .plugins.joint import Joint
from .plugins.model import Var
from .sampler import Sampler

RHO, ALPHA, BETA, MAX_GENERATIONS, FLOOR = 0.1, 0.7, 0.1, 20, 0.01
SD_FLOOR = 1e-3        # a refitted sd never below this share of the base's: the density stays one
ACCEPTANCE_DRAWS = 100_000
Z95 = 1.959963984540054
STATE = "state.json"
SPEC_KEYS = {"search", "id", "scenario", "model", "variables", "n", "seed", "threshold", "knobs",
             "acceptance_draws", "map"}


class SearchError(SpecError):
    pass


# -- the spec ---------------------------------------------------------------------------------

def read_spec(path):
    path = Path(path)
    data = path.read_bytes()
    doc = yaml.safe_load(data)
    where = str(path)
    if not isinstance(doc, dict) or doc.get("search") != 1:
        raise SearchError(f"{where}: `search: 1` (the format's version) is required")
    extra = set(doc) - SPEC_KEYS
    if extra:
        raise SearchError(f"{where}: unknown {sorted(extra)} (a search has "
                          f"{', '.join(sorted(SPEC_KEYS))})")
    if not isinstance(doc.get("id"), str) or not doc["id"].strip() or "/" in doc["id"]:
        raise SearchError(f"{where}: id is a name (no /)")
    if not isinstance(doc.get("scenario"), str):
        raise SearchError(f"{where}: scenario is the path of a distribution file, or of a "
                          f"scenario with model:")
    v = doc.get("variables")
    if not isinstance(v, list) or not v or not all(isinstance(x, str) for x in v) \
            or len(set(v)) != len(v):
        raise SearchError(f"{where}: variables is a non-empty list of the base's variable names")
    for k, lo in (("n", 2), ("seed", 0)):
        x = doc.get(k)
        if isinstance(x, bool) or not isinstance(x, int) or x < lo:
            raise SearchError(f"{where}: {k} is an integer >= {lo}")
    th = doc.get("threshold", 0.0)
    if isinstance(th, bool) or not isinstance(th, (int, float)) or not math.isfinite(th):
        raise SearchError(f"{where}: threshold is a number (a run fails at a score at most it)")
    m = doc.get("acceptance_draws", ACCEPTANCE_DRAWS)
    if isinstance(m, bool) or not isinstance(m, int) or m < 1000:
        raise SearchError(f"{where}: acceptance_draws is an integer >= 1000")
    knobs = doc.get("knobs") or {}
    if not isinstance(knobs, dict):
        raise SearchError(f"{where}: knobs is {{name: value}}")
    base = path.parent
    return {"id": doc["id"], "scenario": (base / doc["scenario"]).resolve(),
            "model": (base / doc["model"]).resolve() if doc.get("model") else None,
            "model_as_written": doc.get("model"),
            "scenario_as_written": doc["scenario"],
            "variables": list(v), "n": doc["n"], "seed": doc["seed"], "threshold": float(th),
            "knobs": knobs, "acceptance_draws": m,
            # the map whose anchors the scenario binds (its anchors.resolved.json, checked
            # against the map's digest), as `scensim run` reads them for a project's map
            "map": (base / doc["map"]).resolve() if doc.get("map") else None,
            "sha256": hashlib.sha256(data).hexdigest(), "path": path.resolve()}


def _sampler(spec, proposal=None):
    anchors = None
    if spec["map"] is not None:
        from . import anchors as A
        f = spec["map"] / A.RESOLVED
        if not f.is_file():
            raise SearchError(f"{spec['map']}: no {A.RESOLVED} (the map's resolved anchors)")
        try:
            anchors = A.merge(None, A.load_resolved(f, map_dir=spec["map"]))
        except A.AnchorError as e:
            raise SearchError(str(e)) from None
    s = Sampler.from_file(spec["scenario"], model=spec["model"], proposal=proposal,
                          knobs=spec["knobs"] or None, anchors=anchors)
    if spec["model_as_written"]:
        # the base's id is the model's path as the spec writes it, not where this host keeps
        # it: the id is part of the record's identity
        base = dict(s.base, id=spec["model_as_written"])
        s.base = base
        for p in s.plugins:
            if getattr(p, "base", None) is not None:
                p.base = base
    return s


def _joint(sampler):
    for p in sampler.plugins:
        if isinstance(p, Joint):
            return p
    raise SearchError("a search explores a fitted base model (scensim.sampler:joint), and "
                      "this scenario's distributions have none")


# -- the searched family ----------------------------------------------------------------------

def _const(p):
    return None if isinstance(p, Expr) else p


def initial(model, names):
    """{name: theta} for the searched variables, from the base: a normal or log-normal keeps its
    kind and range, a uniform stays uniform in g0 and becomes a normal within its range from g1
    (refit), a categorical keeps its values. Anything else is refused by name."""
    by = {e.names: e for e in model.entries}
    theta = {}
    for n in names:
        e = by.get((n,))
        if e is None:
            grouped = any(n in e2.names for e2 in model.entries)
            raise SearchError(f"{n}: " + ("drawn in a joint group, which K11 does not search"
                                          if grouped else
                                          f"not a variable of the base {model.where}"))
        if not isinstance(e, Var):
            raise SearchError(f"{n}: conditional (given), which K11 does not search")
        if e.latent:
            raise SearchError(f"{n}: latent, which K11 does not search")
        d = e.dist
        rng = list(d.range) if d.range is not None else None
        if isinstance(d, (Normal, LogNormal)):
            m, s = _const(d.mean), _const(d.sd)
            if m is None or s is None:
                raise SearchError(f"{n}: its {d.kind} reads other values; K11 searches only "
                                  f"constant parameters")
            theta[n] = {"kind": d.kind, "mean": m, "sd": s, "range": rng}
        elif isinstance(d, Uniform):
            lo, hi = _const(d.low), _const(d.high)
            if lo is None or hi is None:
                raise SearchError(f"{n}: its uniform reads other values; K11 searches only "
                                  f"constant parameters")
            # g0 keeps the uniform, the base itself (092 K11e; K11d's centred normal put less
            # mass where failures live); refit turns it into a normal within its range from g1,
            # starting from the uniform's own mean and sd
            theta[n] = {"kind": "uniform", "mean": (lo + hi) / 2,
                        "sd": (hi - lo) / math.sqrt(12.0), "range": [lo, hi]}
        elif isinstance(d, Categorical):
            if len(d.values) * FLOOR >= 1:
                raise SearchError(f"{n}: {len(d.values)} categories leave no room above the "
                                  f"floor {FLOOR}")
            theta[n] = {"kind": "categorical", "values": list(d.values), "p": list(d.p)}
        else:
            raise SearchError(f"{n}: a {d.kind}, which K11 does not search (normal, log-normal, "
                              f"uniform, categorical)")
    return theta


def _floor(p):
    k = len(p)
    return [FLOOR + (1.0 - k * FLOOR) * x for x in p]


def refit(theta, theta0, values, weights):
    """The weighted elite's moments (frequencies for a categorical), smoothed by alpha."""
    w = np.asarray(weights, dtype=float)
    w = w / w.sum()
    out = {}
    for n, th in theta.items():
        x = [v[n] for v in values]
        if th["kind"] == "categorical":
            f = [float(sum(wi for wi, xi in zip(w, x) if str(xi) == str(c)))
                 for c in th["values"]]
            p = [ALPHA * a + (1 - ALPHA) * b for a, b in zip(f, th["p"])]
            s = sum(p)
            out[n] = dict(th, p=_floor([q / s for q in p]))
            continue
        xa = np.asarray(x, dtype=float)
        m = float(np.dot(w, xa))
        sd = math.sqrt(max(float(np.dot(w, (xa - m) ** 2)), 0.0))
        m = ALPHA * m + (1 - ALPHA) * th["mean"]
        sd = max(ALPHA * sd + (1 - ALPHA) * th["sd"], SD_FLOOR * theta0[n]["sd"])
        if th["kind"] == "lognormal" and m <= 0:
            raise SearchError(f"{n}: the refitted log-normal's mean is {m}, not > 0")
        kind = "normal" if th["kind"] == "uniform" else th["kind"]
        out[n] = dict(th, kind=kind, mean=m, sd=sd)
    return out


def proposal_doc(sid, t, base_rel, theta):
    variables = []
    for n, th in theta.items():
        if th["kind"] == "categorical":
            variables.append({"name": n, "categorical": dict(zip(th["values"], th["p"]))})
        elif th["kind"] == "uniform":
            lo, hi = th["range"]
            variables.append({"name": n, "uniform": {"low": lo, "high": hi}})
        else:
            v = {"name": n, th["kind"]: {"mean": th["mean"], "sd": th["sd"]}}
            if th["range"] is not None:
                v["range"] = list(th["range"])
            variables.append(v)
    return {"proposal": 1, "name": f"{sid}.g{t}", "base": base_rel, "defensive": BETA,
            "variables": variables}


# -- drawing ----------------------------------------------------------------------------------

def _seed(seed, *key):
    return int(np.random.SeedSequence(seed, spawn_key=key).generate_state(1)[0])


def _truncates(sampler):
    sc = sampler.scenario
    models = [p.model for p in sampler.plugins if hasattr(p, "model")]
    return bool(any(m.constraints for m in models) or sc.anchor_bindings or sc.knob_profiles)


def acceptance(sampler, m, seed):
    """(Z, draws): the share of `m` draws the constraints (and the base's support) accept."""
    if not _truncates(sampler):
        return 1.0, 0
    ok = 0
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(seed)))
    for i in range(m):
        values = {}
        for p in sampler.plugins:
            env = dict(sampler.knobs)
            env.update(values)
            values.update(p.draw(rng, i, env))
        ok += not sampler._finish(values)[4]
    if ok == 0:
        raise SearchError(f"none of {m} draws passes the constraints")
    return ok / m, m


def _rel_err(z, m):
    return 0.0 if m == 0 else math.sqrt((1 - z) / (z * m))


def draw_stage(spec, out, state, t, stage):
    """Draw generation t's records (stage cross_entropy or fresh) from g<t>.yaml's mixture."""
    prop = out / f"g{t}.yaml"
    s = _sampler(spec, proposal=prop)
    zq, mq = acceptance(s, spec["acceptance_draws"], _seed(spec["seed"], t, 2))
    norm = zq / state["z_base"]
    key = (t,) if stage == "cross_entropy" else (t, 1)
    batch = s.draw(n=spec["n"], seed=_seed(spec["seed"], *key))
    recs, cells = [], set()
    for r in batch.records:
        # the scenario's path as the spec writes it, not this host's (not part of the identity,
        # but what a run's outcome.json names; 133)
        r = dict(r, search={"id": spec["id"], "generation": t, "stage": stage,
                            "normaliser": norm},
                 scenario=dict(r["scenario"], path=spec["scenario_as_written"]))
        r.pop("id")
        r["id"] = R.record_id(r)
        recs.append({k: r[k] for k in R.KEYS if k in r})
        cells.add(json.dumps(r["cell"], sort_keys=True))
    if len(cells) > 1:
        raise SearchError(f"a search is one cell, and generation {t} drew {len(cells)}: fix the "
                          f"cell's attributes (knobs, or scensim.cell.<attribute>)")
    name = f"g{t}.jsonl" if stage == "cross_entropy" else "fresh.jsonl"
    _write(out / name, "".join(json.dumps(r, sort_keys=True) + "\n" for r in recs))
    return {"generation": t, "stage": stage, "records": name, "proposal": prop.name,
            "proposal_sha256": hashlib.sha256(prop.read_bytes()).hexdigest(),
            "z_proposal": zq, "z_proposal_draws": mq, "normaliser": norm,
            "rejected": batch.rejected}


def _write(path, text):
    Path(path).write_text(text)


def _dump(obj):
    return json.dumps(obj, sort_keys=True, indent=1) + "\n"


def _write_proposal(out, t, spec, state, theta):
    doc = proposal_doc(spec["id"], t, state["base_rel"], theta)
    _write(out / f"g{t}.yaml", yaml.safe_dump(doc, sort_keys=False))


# -- the steps --------------------------------------------------------------------------------

def init(spec_path, out):
    spec = read_spec(spec_path)
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise SearchError(f"{out}: not empty; a search starts in a new directory")
    out.mkdir(parents=True, exist_ok=True)
    base = _sampler(spec)
    joint = _joint(base)
    theta = initial(joint.model, spec["variables"])
    zb, mb = acceptance(base, spec["acceptance_draws"], _seed(spec["seed"], 0, 3))
    state = {"state": 1, "id": spec["id"], "spec": os.path.relpath(spec["path"], out.resolve()),
             "spec_sha256": spec["sha256"],
             "base_rel": os.path.relpath(Path(joint.path).resolve(), out.resolve()),
             "base": joint.base,
             "parameters": {"rho": RHO, "alpha": ALPHA, "beta": BETA,
                            "max_generations": MAX_GENERATIONS, "floor": FLOOR,
                            "sd_floor": SD_FLOOR, "n": spec["n"],
                            "threshold": spec["threshold"]},
             "z_base": zb, "z_base_draws": mb, "theta0": theta, "theta": theta,
             "generations": [], "failures": [], "phase": "cross_entropy", "stop": None}
    _write_proposal(out, 0, spec, state, theta)
    try:
        state["generations"].append(draw_stage(spec, out, state, 0, "cross_entropy"))
    except Exception:
        (out / "g0.yaml").unlink()       # a refused start leaves the directory as it was
        raise
    _write(out / STATE, _dump(state))
    return state


def read_outcomes(path, records):
    """{record id: (score or None, error, outcome)} for every record, from a JSONL of
    {record, outcome}."""
    ids = {r["id"] for r in records}
    got = {}
    for i, line in enumerate(Path(path).read_text().splitlines()):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or "record" not in row or "outcome" not in row:
            raise SearchError(f"{path}: line {i + 1}: {{record, outcome}}")
        rid = row["record"]["id"] if isinstance(row["record"], dict) else row["record"]
        if rid not in ids:
            raise SearchError(f"{path}: line {i + 1}: record {rid} is not this stage's")
        o = row["outcome"] or {}
        sc = o.get("score")
        if sc is not None and (isinstance(sc, bool) or not isinstance(sc, (int, float))
                               or not math.isfinite(sc)):
            raise SearchError(f"{path}: line {i + 1}: score is a number, not {sc!r}")
        got[rid] = (None if o.get("error") else sc, bool(o.get("error")), o)
    missing = ids - set(got)
    if missing:
        raise SearchError(f"{path}: {len(missing)} of {len(ids)} records have no outcome "
                          f"(first: {sorted(missing)[0]})")
    return got


def _records(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


# 183's one-sided 95 % split (Bonferroni): the failure share at ALPHA_F, each acceptance at ALPHA_Z
ALPHA_F, ALPHA_Z = 0.025, 0.0125


def _betacf(a, b, x):
    """The continued fraction of the regularised incomplete beta (modified Lentz)."""
    tiny, qab, qap, qam = 1e-300, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 10000):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            return h
    raise ArithmeticError("the incomplete beta did not converge")


def _betainc(a, b, x):
    """I_x(a, b), the regularised incomplete beta."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lb = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
          + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lb) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lb) * _betacf(b, a, 1.0 - x) / b


def _beta_quantile(a, b, q):
    """x with I_x(a, b) = q, by bisection (to 1e-15)."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _betainc(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-15:
            break
    return 0.5 * (lo + hi)


def clopper_pearson(k, n, alpha):
    """(lower, upper): Clopper-Pearson's one-sided bounds at `alpha` each for k of n."""
    lo = 0.0 if k == 0 else _beta_quantile(k, n - k + 1, alpha)
    hi = 1.0 if k == n else _beta_quantile(k + 1, n - k, 1.0 - alpha)
    return lo, hi


def _normaliser_bounds(z_q, m_q, z_b, m_b):
    """(low, high) of Z_q / Z_b at ALPHA_Z for each acceptance, or None: taken as exact (no
    counts given, or both acceptances exact: no constraints draw)."""
    if z_q is None or z_b is None:
        return None
    def side(z, m):
        if not m:
            return z, z
        k = round(z * m)
        return clopper_pearson(k, m, ALPHA_Z)
    (ql, qh), (bl, bh) = side(z_q, m_q), side(z_b, m_b)
    return ql / bh, qh / bl


def plain_estimate(log_w, normaliser, failed, rel_err, *, cap=None, z_q=None, m_q=None,
                   z_b=None, m_b=None):
    """The plain likelihood-ratio estimate {p, se, interval, interval_method, interval_exact,
    interval_normal, upper_exact, n_eff, max_weight} (issue 183).

    `upper_exact` is a rigorous one-sided 95 % upper bound at any failure count k: every weight
    before the normaliser is at most `cap` (the defensive mixture's 1 / beta), so
    p <= cap (Z_q / Z_b) q(F), q(F) the proposal's own failure share, bounded by Clopper-Pearson
    for k of n at ALPHA_F; the normaliser's two acceptances by Clopper-Pearson at ALPHA_Z each
    (`z_q`, `m_q`, `z_b`, `m_b`; without them it is taken as exact). It is loose: it charges
    every failure the largest weight. Without `cap` there is none.

    At k = 0 the normal interval is [0, 0], which is no answer: the interval is [0, upper_exact],
    exact (None without `cap`). At k >= 1 the interval is the normal (delta-method) one,
    p +- 1.96 se, approximate; with counts its ends are widened by the normaliser's bounds
    instead of `rel_err`; an upper end past `upper_exact` is clipped there."""
    w = np.exp(np.asarray(log_w, dtype=float)) * normaliser
    f = np.asarray(failed, dtype=float)
    n = len(w)
    wf = w * f
    p = float(wf.mean())
    se0 = float(wf.std(ddof=1) / math.sqrt(n)) if n > 1 else math.inf
    se = math.sqrt(se0 ** 2 + (p * rel_err) ** 2)
    k = int(f.sum())
    nb = _normaliser_bounds(z_q, m_q, z_b, m_b)
    if nb is None:
        normal = [max(0.0, p - Z95 * se), p + Z95 * se]
        how = "normaliser taken as exact"
    else:
        normal = [max(0.0, p - Z95 * se0) * nb[0] / normaliser,
                  (p + Z95 * se0) * nb[1] / normaliser]
        how = f"normaliser by Bonferroni ({ALPHA_F} / {ALPHA_Z} / {ALPHA_Z})"
    upper = None
    if cap is not None:
        upper = cap * (normaliser if nb is None else nb[1]) * clopper_pearson(k, n, ALPHA_F)[1]
    out = {"n": n, "failures": k, "p": p, "se": se, "interval_normal": normal,
           "upper_exact": upper,
           "n_eff": float(w.sum() ** 2 / (w ** 2).sum()), "max_weight": float(w.max())}
    if k == 0:
        if upper is None:
            return dict(out, interval=None, interval_exact=False,
                        interval_method="0 failures: no bound (the proposal's weight cap is not "
                                        "known here; the search's report has it)")
        return dict(out, interval=[0.0, upper], interval_exact=True,
                    interval_method=f"0 failures: exact one-sided 95 % bound through the weight "
                                    f"cap {cap:.4g}, Clopper-Pearson, {how}")
    method = f"plain likelihood ratio, normal 95 % (delta; approximate), {how}"
    interval = list(normal)
    if upper is not None and interval[1] > upper:
        interval[1] = upper
        method += "; upper end clipped at the exact bound"
    return dict(out, interval=interval, interval_exact=False, interval_method=method)


def _cap(out, gen):
    """The largest weight the stage's proposal can give before the normaliser: 1 / its
    `defensive` share of the base (issue 183), or 1 for a proposal without one."""
    doc = yaml.safe_load((Path(out) / gen["proposal"]).read_text()) or {}
    beta = doc.get("defensive")
    return 1.0 / float(beta) if beta else 1.0


def _estimate(out, gen, state, rows, th):
    """A stage's plain estimate from its scored rows [(record, score)]."""
    rel = math.sqrt(_rel_err(state["z_base"], state["z_base_draws"]) ** 2
                    + _rel_err(gen["z_proposal"], gen["z_proposal_draws"]) ** 2)
    return plain_estimate([r["log_weight"] for r, _ in rows], gen["normaliser"],
                          [s <= th for _, s in rows], rel, cap=_cap(out, gen),
                          z_q=gen["z_proposal"], m_q=gen["z_proposal_draws"],
                          z_b=state["z_base"], m_b=state["z_base_draws"])


def _scored(out, gen, outcomes_path, spec, state):
    recs = _records(out / gen["records"])
    got = read_outcomes(outcomes_path, recs)
    th = spec["threshold"]
    base_model = _joint(_sampler(spec)).model
    rows, errors, avoided = [], 0, set()
    for r in recs:
        sc, err, o = got[r["id"]]
        if sc is None:
            errors += 1
            continue
        rows.append((r, float(sc)))
        # 092 K11e: a walker that went (decision margin < 0) and was avoided (gap > 0): the
        # near-failures a sloped score's elite should climb through
        m, g = o.get("decision_margin"), o.get("closest_gap")
        if m is not None and g is not None and m < 0 and g > th:
            avoided.add(r["id"])
        if sc <= th:
            vals = dict(r["values"], **(r.get("latent") or {}))
            state["failures"].append({"record": r["id"], "generation": gen["generation"],
                                      "stage": gen["stage"], "score": float(sc),
                                      "log_base_density": base_model.logpdf(vals)})
    if not rows:
        raise SearchError(f"generation {gen['generation']}: no run has a score")
    est = _estimate(out, gen, state, rows, th)
    gen.update(outcomes=os.path.relpath(Path(outcomes_path).resolve(), out.resolve()),
               errors=errors, estimate=est, max_weight=est["max_weight"],
               went_avoided=len(avoided))
    gen["_avoided"] = sorted(avoided)
    return rows


def next_step(out, outcomes_path):
    out = Path(out)
    state = json.loads((out / STATE).read_text())
    spec = read_spec((out / state["spec"]).resolve())
    if spec["sha256"] != state["spec_sha256"]:
        raise SearchError(f"{state['spec']}: changed since the search started")
    if state["phase"] == "done":
        raise SearchError(f"{out}: the search is done (search report)")
    gen = state["generations"][-1]
    if "outcomes" in gen:
        raise SearchError(f"{out}: generation {gen['generation']} has its outcomes already")
    rows = _scored(out, gen, outcomes_path, spec, state)
    if state["phase"] == "fresh":
        gen.pop("_avoided", None)
        state["estimate"] = gen["estimate"]
        ce = [g for g in state["generations"] if g["stage"] == "cross_entropy"]
        # the generations' own estimate, each generation's plain estimate averaged: biased by
        # the adaptation, a diagnostic only
        state["diagnostic"] = {"generations_estimate":
                               float(np.mean([g["estimate"]["p"] for g in ce])),
                               "note": "from the adaptive generations: biased, not the rate"}
        state["phase"] = "done"
        _write(out / STATE, _dump(state))
        return state
    th = spec["threshold"]
    t = gen["generation"]
    scores = sorted(s for _, s in rows)
    k = max(1, math.ceil(RHO * len(rows)))
    gamma = scores[k - 1]
    reached = gamma <= th
    if reached:
        gamma = th
    elite = [(r, s) for r, s in rows if s <= gamma]
    lw = np.asarray([r["log_weight"] for r, _ in elite], dtype=float)
    w = np.exp(lw - lw.max())
    values = [dict(r["values"], **(r.get("latent") or {})) for r, _ in elite]
    theta = refit(state["theta"], state["theta0"], values, w)
    av = set(gen.pop("_avoided", []))
    gen.update(level=gamma, elite=len(elite),
               elite_went_avoided=sum(1 for r, _ in elite if r["id"] in av))
    state["theta"] = theta
    _write_proposal(out, t + 1, spec, state, theta)
    if reached or t + 1 >= MAX_GENERATIONS:
        state["stop"] = ("the level reached the threshold" if reached
                         else f"the generation cap ({MAX_GENERATIONS})")
        state["phase"] = "fresh"
        state["generations"].append(draw_stage(spec, out, state, t + 1, "fresh"))
    else:
        state["generations"].append(draw_stage(spec, out, state, t + 1, "cross_entropy"))
    _write(out / STATE, _dump(state))
    return state


def _fresh_estimate(out, state):
    """The fresh stage's estimate read again from its records and outcomes, so a search done
    before issue 183 reports by today's rule (nothing is re-run); None before the fresh stage
    has its outcomes."""
    gen = state["generations"][-1]
    if gen.get("stage") != "fresh" or "outcomes" not in gen:
        return state.get("estimate")
    recs = _records(out / gen["records"])
    got = read_outcomes(out / gen["outcomes"], recs)
    rows = [(r, float(got[r["id"]][0])) for r in recs if got[r["id"]][0] is not None]
    return _estimate(out, gen, state, rows, state["parameters"]["threshold"])


def report(out):
    out = Path(out)
    state = json.loads((out / STATE).read_text())
    fails = sorted(state["failures"], key=lambda f: (-f["log_base_density"], f["record"]))
    return {"schema": "scensim.search/1", "id": state["id"], "phase": state["phase"],
            "stop": state["stop"], "parameters": state["parameters"],
            "z_base": state["z_base"],
            "generations": [{k: g.get(k) for k in ("generation", "stage", "level", "elite",
                                                   "errors", "normaliser", "max_weight",
                                                   "went_avoided", "elite_went_avoided")}
                            | {"failures": (g.get("estimate") or {}).get("failures"),
                               "estimate": (g.get("estimate") or {}).get("p")}
                            for g in state["generations"]],
            "estimate": _fresh_estimate(out, state), "diagnostic": state.get("diagnostic"),
            "failures": fails}


def print_report(rep, file):
    p = print
    p(f"search {rep['id']}: {rep['phase']}" + (f", stopped: {rep['stop']}" if rep["stop"]
                                                else ""), file=file)
    for g in rep["generations"]:
        p(f"  g{g['generation']} {g['stage']}: level {g['level']}, elite {g['elite']}, "
          f"failures {g['failures']}, errors {g['errors']}, normaliser {g['normaliser']:.4g}, "
          f"largest weight {g['max_weight']}"
          + (f", went and avoided {g['went_avoided']} (elite {g['elite_went_avoided']})"
             if g.get("went_avoided") is not None else ""), file=file)
    e = rep["estimate"]
    if e:
        iv = ("none" if e.get("interval") is None
              else f"[{e['interval'][0]:.4g}, {e['interval'][1]:.4g}]")
        p(f"  failures {e['failures']} of {e['n']}: rate {e['p']:.4g} (se {e['se']:.3g}), "
          f"interval {iv} ({e['interval_method']}), n_eff {e['n_eff']:.1f}, largest weight "
          f"{e['max_weight']:.4g}", file=file)
        if e.get("upper_exact") is not None and e["failures"] > 0:
            p(f"  exact one-sided 95 % upper bound {e['upper_exact']:.4g} (loose: every "
              f"failure charged the largest weight)", file=file)
        p(f"  diagnostic, not the rate: the generations' own estimate "
          f"{rep['diagnostic']['generations_estimate']:.4g}", file=file)
    p(f"  failures found: {len(rep['failures'])}", file=file)
    for f in rep["failures"][:20]:
        p(f"    {f['record'][:16]} g{f['generation']} {f['stage']}: score {f['score']:.4g}, "
          f"log base density {f['log_base_density']:.3f}", file=file)


__all__ = ["init", "next_step", "report", "read_spec", "plain_estimate"]
