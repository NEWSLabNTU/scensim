"""The sampler: a distribution file (or a scenario and a model file) to concrete parameter
sets, each with its sample record.

    from scensim_sampler import Sampler
    batch = Sampler.from_file("walker_dartout_dist.xosc").draw(n=100, seed=7)
    batch.records[0]["values"], batch.rejected

Per sample i of a run seeded S, numpy's SeedSequence(S, spawn_key=(i,)) gives four
independent streams: the draw, the scenario's seed, the world's and the pilots'. A sample is
therefore the same whichever other samples are drawn, and a record names S and i.
"""
import itertools
import math
import platform
from pathlib import Path

import numpy as np

from . import __version__, anchors as A, record as R
from .dist import SpecError
from .expr import ExprError
from .plugins.importance import Importance
from .plugins.joint import Joint
from .xosc import Distribution, Scenario

# What drew it, for tracing a record that does not reproduce: numpy's Generator streams may
# change between versions (NEP 19), and libm may differ in the last bit between hosts
ENV = {"python": platform.python_version(), "numpy": np.__version__,
       "platform": f"{platform.system()}-{platform.machine()}"}
MAX_REJECTS = 1000  # per sample: draws refused by constraints or outside the base's support


class SamplingError(ValueError):
    pass


class Batch:
    def __init__(self, records, rejected, rejected_why):
        self.records, self.rejected, self.rejected_why = records, rejected, rejected_why

    def summary(self):
        return {"records": len(self.records), "rejected": self.rejected,
                "rejected_why": dict(self.rejected_why)}


class Sampler:
    def __init__(self, scenario, plugins, distribution=None, stochastic=True, runs=None,
                 seed=None, knobs=None, anchors=None):
        self.scenario, self.plugins = scenario, list(plugins)
        self.distribution, self.stochastic = distribution, stochastic
        self.runs, self.seed = runs, seed
        reads = {}
        for p in self.plugins:
            reads.update(p.derived_reads())
        # the world's anchor attributes (093 gap 7): read-only values an expression reads as
        # anchor.<name>.<attribute>, {name: {attribute: value}} as testbench.yaml's
        # world.anchors declares them; a derived value may read them and still feed the cell
        try:
            numbers, functions = A.env(anchors)
        except A.AnchorError as e:
            raise SpecError(str(e)) from None
        self.anchors = numbers
        self.anchor_functions = {k + "()": f for k, f in functions.items()}
        self._functions = functions
        self.anchor_specs = dict(anchors or {})
        missing = sorted({r for rs in reads.values() for r in rs
                          if r.startswith("anchor.") and r not in self.anchors
                          and r not in functions})
        if missing:
            known = sorted(set(self.anchors) | set(functions))
            raise SpecError(f"{', '.join(missing)}: read by a derived value, but the world "
                            f"declares no such anchor attribute (testbench.yaml world.anchors, "
                            f"or the map's {A.RESOLVED}"
                            f"{': ' + ', '.join(known) if known else ': none'})")
        # the bindings, checked where they can be: a literal anchor the world lacks, the wrong
        # form, or a constant s off the lane (an s from a drawn value is checked per draw)
        drawn_names = {n for p in self.plugins for n in getattr(p, "names", ())}
        for param, text in scenario.anchor_bindings.items():
            where = f"{scenario.path.name}: scensim.anchor.{param}"
            if param in drawn_names:
                raise SpecError(f"{where}: {param} is drawn and bound to an anchor; keep one")
            ref, attr, arg = A.parse_binding(text, where)
            if ref.startswith("$"):
                continue
            dotted = f"anchor.{ref}.{attr}"
            if arg is None and dotted not in numbers:
                why = (f"read at a lane position, {dotted}(s)" if dotted in functions
                       else "the world declares no such anchor attribute")
                raise SpecError(f"{where}: {dotted}: {why}")
            if arg is not None:
                if dotted not in functions:
                    raise SpecError(f"{where}: {dotted}(...): no such function of the world's "
                                    f"anchors")
                if not arg.startswith("$"):
                    try:
                        functions[dotted](float(arg))
                    except A.AnchorError as e:
                        raise SpecError(f"{where}: {e}") from None
        self.anchors_read = sorted({r for rs in reads.values() for r in rs
                                    if r.startswith("anchor.")}
                                   | {f"anchor.{r}.{a}" for r, a, _ in
                                      (A.parse_binding(t) for t in
                                       scenario.anchor_bindings.values())
                                      if not r.startswith("$")})
        # a read the world declares only as a function (a resolved lane's heading) has no
        # value of its own to record: its file does (anchor_source)
        self.anchor_values_read = [r for r in self.anchors_read if r in self.anchors]
        # a $parameter binding picks its anchor per draw: every resolved file may be read
        dynamic = any(A.parse_binding(t)[0].startswith("$")
                      for t in scenario.anchor_bindings.values())
        self.anchor_source = A.sources(
            self.anchor_specs, [f"anchor.{n}.x" for n in self.anchor_specs] if dynamic
            else self.anchors_read)
        # the derived values a cell may be computed from: reading only parameters (a bound knob
        # is one), anchor attributes and such values, transitively (scenario-description.md
        # section 7)
        self.derived_ok = scenario.derived_ok(reads, fixed=set(self.anchors) | set(functions))
        self.knobs = {}
        for p in self.plugins:
            self.knobs.update(p.knobs)
        self.knobs.update(knobs or {})
        # latent variables (scenario-description.md 2a, gap 2): drawn, recorded under `latent`,
        # read by derived values and constraints, never passed to the scenario
        self.latent = [n for p in self.plugins for n in getattr(p, "latent", ())]
        clash = [n for n in self.latent if n in scenario.parameters]
        if clash:
            raise SpecError(f"{', '.join(clash)} is latent, but {scenario.path.name} declares a "
                            f"parameter of that name: a latent variable never reaches the "
                            f"scenario; rename it, or drop latent to bind it")
        # a factor drawn first (twise rows, set by index) may condition what follows
        self.plugins.sort(key=lambda p: not p.deterministic)
        bases = [p.base for p in self.plugins if p.base is not None]
        if len({b["sha256"] for b in bases}) > 1:
            raise SpecError("more than one fitted base model; a record (version 1) names one")
        self.base = bases[0] if bases else None
        props = [p.proposal for p in self.plugins if p.proposal is not None]
        if len(props) > 1:
            raise SpecError("more than one proposal; a record (version 1) names one")
        self.proposal = props[0] if props else None
        if not self.scenario.category:
            raise SpecError(f"{self.scenario.path}: its FileHeader has no scensim.category "
                            f"property (R<family>.<category>.<subtype>)")
        if not R.CATEGORY.match(self.scenario.category):
            raise SpecError(f"{self.scenario.path}: scensim.category "
                            f"{self.scenario.category!r} is not R<family>.<category>.<subtype>")

    @classmethod
    def from_file(cls, path, model=None, proposal=None, knobs=None, anchors=None):
        """A ParameterValueDistribution file; or a scenario with `model`, a model file whose
        variables it draws. `proposal`: a proposal file, replacing the model of its base."""
        path = Path(path)
        sc = Scenario(path)
        if sc.is_distribution:
            if model is not None:
                raise SpecError(f"{path} is a distribution file; --model is for a scenario")
            d = Distribution(path)
            s = cls(d.scenario, d.plugins, distribution={"path": str(path), "sha256": d.sha256},
                    stochastic=d.stochastic, runs=d.runs, seed=d.seed, knobs=knobs,
                    anchors=anchors)
        else:
            if model is None:
                raise SpecError(f"{path} declares no distribution: give a "
                                f"ParameterValueDistribution file, or a model file (--model)")
            plugin = Joint(str(model), base_dir=".", parameter=None, scenario=sc)
            plugin.name = "joint"
            s = cls(sc, [plugin], knobs=knobs, anchors=anchors)
        if proposal is not None:
            s._propose(proposal)
        return s

    def _propose(self, path):
        for i, p in enumerate(self.plugins):
            if isinstance(p, Joint):
                imp = Importance(proposal_path=path, base_plugin=p)
                imp.name = "importance"
                self.plugins[i] = imp
                self.proposal = imp.proposal
                return
        raise SpecError(f"{path}: a proposal replaces a fitted model, and this scenario's "
                        f"distributions have none")

    # -- one sample

    def _finish(self, values):
        env = dict(self.knobs)
        env.update(self.anchors)
        env.update(self.anchor_functions)
        env.update(values)
        derived = []
        why = []
        try:
            for p in self.plugins:
                d = p.derived(env)
                env.update(d)
                derived += list(d)
        except ExprError as e:
            if "outside the lane" not in str(e):
                raise
            # a lane position the draw put off its lane (092 K9b): a rejection, named
            return ({k: env[k] for k in itertools.chain(values, derived)}, derived, {}, 0.0,
                    [_lane_why(str(e))])
        # the parameters bound to the world's anchors (scensim.anchor.<parameter>, 092 K9b)
        sc = self.scenario
        if sc.anchor_bindings:
            vals = {k: v for k, (_t, v) in sc.parameters.items()}
            vals.update({k: env[k] for k in env if k in sc.parameters})
            for param, text in sc.anchor_bindings.items():
                try:
                    env[param] = A.bind(text, vals, self.anchors, self._functions,
                                        f"scensim.anchor.{param}")
                except A.AnchorError as e:
                    if "outside the lane" not in str(e):
                        raise SpecError(str(e)) from None
                    return ({k: env[k] for k in itertools.chain(values, derived)}, derived, {},
                            0.0, [_lane_why(str(e))])
                v = env[param]
                if (isinstance(v, float) and v.is_integer()
                        and sc.parameters[param][0] != "double"):
                    v = env[param] = int(v)     # a lanelet id, not 6583.0
                env[param] = sc.cast(param, v)
                vals[param] = env[param]
                derived.append(param)
        for p in self.plugins:
            why += p.violations(env)
        log_w = sum(p.log_weight(env) for p in self.plugins)
        if log_w == -math.inf:
            why.append("outside the base's support")
        cell = dict(self.scenario.fixed_cell())
        for p in self.plugins:
            cell.update(p.cell(env))
        drawn = {k: env[k] for k in itertools.chain(values, derived)}
        return drawn, derived, cell, log_w, why

    def _record(self, run_seed, index, drawn, derived, cell, log_w, streams):
        sc = self.scenario
        params, cell, latent = {}, dict(cell), {}
        for k, v in drawn.items():
            if k in self.latent:
                latent[k] = _plain(v)
            elif k in sc.parameters:
                params[k] = sc.cast(k, v)
            elif k in derived:
                continue  # an intermediate the constraints or the cell read; not recorded
            elif k in sc.cell_attributes:
                raise SpecError(f"{k} is drawn and names a cell attribute, but {sc.path.name} "
                                f"declares no parameter {k}: it would only label the cell, the "
                                f"world would never get it; fix: declare it and bind it "
                                f"(scensim.knob.<name> = ${k})")
            else:
                raise SpecError(f"{k} is drawn, and it is neither a parameter of "
                                f"{sc.path.name} nor one of its cell attributes")
        # the cell is computed from the values through the scenario's bindings (a bound knob, a
        # parameter, or what the scenario fixes), never labelled (093 D7)
        problems = sc.cell_problems(self.derived_ok)
        if problems:
            raise SpecError(f"{sc.path.name}: " + "; ".join(problems))
        dvals = {k: drawn[k] for k in derived if k in drawn}
        cell = {a: _plain(v) for a, v in sc.cell_of(params, dvals, self.derived_ok).items()}
        _, scen_ss, world_ss, pilot_ss = streams
        pilots = pilot_ss.generate_state(max(1, len(sc.entities)))
        weight = math.exp(log_w) if self.proposal is not None else 1.0
        rec = {
            "record": R.VERSION,
            "scenario": {"path": str(sc.path), "sha256": sc.sha256},
            "distribution": self.distribution,
            "category": sc.category,
            "cell": cell,
            "values": params,
            "derived": [k for k in derived if k in params],
            **({"latent": latent} if latent else {}),
            # the anchor attributes this sample's derived values read, as the world declared
            # them: a replay recomputes its cell from them (093 gap 7)
            **({"anchors": _anchors_record(self.anchors, self.anchor_values_read)}
               if self.anchor_values_read else {}),
            # the map's resolved anchors files read (092 K9a): which geometry, by digest
            **({"anchor_source": self.anchor_source} if self.anchor_source else {}),
            "seeds": {"scenario": int(scen_ss.generate_state(1)[0]),
                      "world": int(world_ss.generate_state(1)[0]),
                      "pilots": {e: int(s) for e, s in zip(sc.entities, pilots)}},
            "base": self.base,
            "proposal": self.proposal,
            "weight": weight,
            "log_weight": float(log_w) if self.proposal is not None else 0.0,
            "search": None,
            "sampler": {"name": "scensim_sampler", "version": __version__,
                        "plugins": [p.name for p in self.plugins], "run_seed": int(run_seed),
                        "index": int(index), "env": ENV},
        }
        rec["id"] = R.record_id(rec)
        return {k: rec[k] for k in R.KEYS if k in rec}

    # -- a batch

    def draw(self, n=None, seed=None):
        """`n` samples (stochastic; default numberOfTestRuns), or every row (deterministic;
        `n` takes the first n). `seed`: the run seed (default the file's randomSeed; 0 for a
        deterministic file); a stochastic one requires it, so a batch can be drawn again."""
        seed = self.seed if seed is None else seed
        if seed is None and not self.stochastic:
            seed = 0  # rows are not drawn; the seed only derives the runs' seeds
        if seed is None:
            raise SpecError("a run seed is required (--seed, or the Stochastic randomSeed)")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise SpecError(f"the run seed is an integer >= 0, not {seed!r}")
        if self.stochastic:
            n = self.runs if n is None else n
            if n is None:
                raise SpecError("how many samples: give n (-n)")
            return self._stochastic(n, seed)
        return self._deterministic(n, seed)

    def _stochastic(self, n, seed):
        records, rejected, why_count = [], 0, {}
        for i in range(n):
            streams = np.random.SeedSequence(seed, spawn_key=(i,)).spawn(4)
            rng = np.random.Generator(np.random.PCG64(streams[0]))
            for tries in range(MAX_REJECTS + 1):
                values = {}
                for p in self.plugins:
                    env = dict(self.knobs)
                    env.update(values)
                    values.update(p.draw(rng, i, env))
                drawn, derived, cell, log_w, why = self._finish(values)
                if not why:
                    break
                rejected += 1
                for w in why:
                    why_count[w] = why_count.get(w, 0) + 1
            else:
                raise SamplingError(f"sample {i}: {MAX_REJECTS} draws in a row rejected "
                                    f"(last: {'; '.join(why)}); the constraints leave almost "
                                    f"nothing of the distribution")
            records.append(self._record(seed, i, drawn, derived, cell, log_w, streams))
        return Batch(records, rejected, why_count)

    def _deterministic(self, n, seed):
        records, rejected, why_count = [], 0, {}
        lists = [p.rows() for p in self.plugins]
        for i, combo in enumerate(itertools.product(*lists)):
            if n is not None and len(records) >= n:
                break
            values = {}
            for row in combo:
                values.update(row)
            drawn, derived, cell, log_w, why = self._finish(values)
            if why:
                rejected += 1
                for w in why:
                    why_count[w] = why_count.get(w, 0) + 1
                continue
            streams = np.random.SeedSequence(seed, spawn_key=(i,)).spawn(4)
            records.append(self._record(seed, i, drawn, derived, cell, log_w, streams))
        return Batch(records, rejected, why_count)


def _plain(v):
    if isinstance(v, (np.generic,)):
        return v.item()
    return v


def _anchors_record(env, read):
    """{name: {attribute: value}} of the attributes read."""
    out = {}
    for dotted in read:
        _, name, attr = dotted.split(".", 2)
        out.setdefault(name, {})[attr] = env[dotted]
    return out


def _lane_why(text):
    """A lane-position rejection's reason, without the sample's own number (counted by kind)."""
    import re
    m = re.search(r"(anchor\.\w+)", text)
    return f"a lane position outside {m.group(1) if m else 'its lane'}"
