"""Episode starts drawn per reset from real sample records (roadmap 094 P2; batch-executor.md
section 10): a pool the scenario's own Sampler fills on the host, in chunks and in the
background, every record compiled to its Init (the ego's pose and speed), and taken one per
reset. So every training episode is a sample record as `scensim-sample draw` writes it, its id
logged with the slot and episode that ran it, and replayable on seats unchanged.

    pool = StartPool(dist_xosc, world, seed=7, chunk=10000, device="cuda")
    rows = pool.take(env_ids)          # one record each, never one used before
    x, y, yaw, speed = pool.init(rows) # the ego's Init on the device

A record sets its slot's Init and, through Storyboard.rebind, every storyboard value it reads
live (a trigger at `$onset_s`, a SpeedAction's `-$decel`; 094 P4); a storyboard that compiled in
a sampled parameter (a lane name, an execution count) is refused (check_storyboard). The pool
never reuses a record: when it runs dry the reset waits for the refill, and the wait is counted
(`stalls`, `stall_s`). `refill` and `take` are what 094's harness times as its `sample` stage
(wheeledlab_bench `--sample-hook scensim_batch.start_pool:StartPool.refill` and
`...:StartPool.take`)."""
import re
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import torch

from . import compile as compilemod


class PoolError(ValueError):
    pass


PARAM = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def storyboard_parameters(scenario):
    """The `$names` the scenario's storyboard reads outside its Init (its stories and its
    StopTrigger)."""
    sb = ET.parse(scenario).getroot().find("Storyboard")
    names = set()
    for part in sb:
        if part.tag == "Init":
            continue
        for el in part.iter():
            for v in el.attrib.values():
                names.update(PARAM.findall(v))
    return names


class ReplaySampler:
    """A fixed list of records, drawn in order (another tool's conditions, replayed: 094 P4's
    stock evaluator's episodes): `draw(n)` gives the next n, round again from the first once
    through (each round's records marked `replay_round`), so a pool's refills still have rows.
    The scenario is the distribution's own sampler's."""

    def __init__(self, sampler, records):
        if not records:
            raise PoolError("a replay of no records")
        self.scenario = sampler.scenario
        self._recs, self._next, self._round = [dict(r) for r in records], 0, 0

    def draw(self, n, seed=None):
        from types import SimpleNamespace
        out = []
        while len(out) < n:
            r = dict(self._recs[self._next], replay_round=self._round)
            out.append(r)
            self._next += 1
            if self._next == len(self._recs):
                self._next, self._round = 0, self._round + 1
        return SimpleNamespace(records=out, rejected=0, rejected_why={},
                               summary=lambda: f"replayed {len(out)}")


class StartPool:
    """Sample records of one distribution, compiled to the ego's Init, taken one per reset."""

    def __init__(self, distribution, world, seed, chunk=10000, low_water=None, device="cpu",
                 provides=(), background=True, sampler=None, knobs=None, catalogs=None):
        from scensim_sampler.sampler import Sampler
        # `knobs`: the run's own draw (stock's 20 reference points of a drift run, say), the
        # distribution's world knobs for every record of this run; the run's log records them
        self.knobs = dict(knobs or {})
        self.sampler = sampler or Sampler.from_file(distribution, knobs=self.knobs)
        self.scenario = Path(self.sampler.scenario.path)
        self.sampled = set(self.sampler.scenario.parameters)
        self.world, self.provides = world, tuple(provides)
        self.catalogs = dict(catalogs or {})       # compile_scenario's
        self.seed, self.chunk = int(seed), int(chunk)
        self.low_water = int(low_water if low_water is not None else chunk // 2)
        self.device = torch.device(device)
        self.records = []            # every record drawn, in order (the pool's rows)
        self.next = 0                # the first row not yet taken
        self.chunks = 0
        self.stalls, self.stall_s = 0, 0.0
        self.refill_s, self.refills = 0.0, 0
        self._x = self._y = self._yaw = self._speed = None
        self.ego = None
        self.entity_names = None      # the compile's entities, in its column order
        self._goal = None             # the ego's route goal per waypoint: (x, y, yaw) [rows]
        self._lock = threading.Lock()
        self._thread = None
        self.background = background
        self.refill()                # the first chunk before the first reset

    # --- the host side -------------------------------------------------------------------

    def refill(self):
        """Draw one chunk (seed + its index: every chunk its own, reproducibly), compile its
        Init, append it to the pool."""
        t0 = time.perf_counter()
        k = self.chunks
        batch = self.sampler.draw(n=self.chunk, seed=self.seed + k)
        recs = [dict(r, pool_chunk=k) for r in batch.records]
        if not recs:
            raise PoolError(f"{self.scenario.name}: chunk {k} drew no records "
                            f"({batch.summary()})")
        c = compilemod.compile_scenario(self.scenario, recs, self.world, provides=self.provides,
                                        catalogs=self.catalogs or None)
        self.ego = c.of_role("ego")[0]
        # every entity's Init, not the ego's alone: the lead's start and speed are a record's too
        # (094 P4: written for the ego only, a slot's other entities kept its first record's)
        cols = [t.to(self.device, torch.float64) for t in (c.x, c.y, c.yaw, c.speed)]
        names = [e.name for e in c.entities]
        goal = [tuple(torch.as_tensor(t).to(self.device, torch.float64) for t in w)
                for w in (c.goal_waypoints or [])]
        with self._lock:
            self.records.extend(recs)
            if self.entity_names is not None and names != self.entity_names:
                raise PoolError(f"{self.scenario.name}: chunk {k} compiled entities {names}, "
                                f"not {self.entity_names}")
            self.entity_names = names
            if self._goal is not None and len(goal) != len(self._goal):
                raise PoolError(f"{self.scenario.name}: chunk {k} compiled {len(goal)} route "
                                f"waypoints, not {len(self._goal)}")
            self._goal = goal if self._goal is None else [
                tuple(torch.cat([a, b]) for a, b in zip(old, new))
                for old, new in zip(self._goal, goal)]
            if self._x is None:
                self._x, self._y, self._yaw, self._speed = cols
            else:
                self._x, self._y, self._yaw, self._speed = (
                    torch.cat([a, b]) for a, b in zip((self._x, self._y, self._yaw, self._speed),
                                                      cols))
            self.chunks += 1
        self.refill_s += time.perf_counter() - t0
        self.refills += 1

    def _maybe_refill(self):
        if len(self.records) - self.next > self.low_water:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        if self.background:
            self._thread = threading.Thread(target=self.refill, daemon=True)
            self._thread.start()
        else:
            self.refill()

    # --- per reset ---------------------------------------------------------------------------

    def check_storyboard(self, storyboard):
        """Refuse a storyboard that compiled in a parameter a record sets (a lane name, an
        execution count, a parameter condition: Storyboard.params_fixed): a reset could not
        give a slot its record's value. The parameters it reads live (its conditions' and
        actions' values, its positions) a reset sets per slot (Storyboard.rebind; 094 P4)."""
        if storyboard is None:
            return
        # a backstop (243): every $name in the storyboard's text the compile read some other
        # way (a site not instrumented) is neither live nor fixed, and would never be rebound
        unread = (storyboard_parameters(self.scenario) & self.sampled) - \
            (set(storyboard.params_live) | set(storyboard.params_fixed))
        if unread:
            raise PoolError(f"{self.scenario.name}: its storyboard reads "
                            f"{', '.join(sorted(unread))}, which a record sets, by a route the "
                            "compile does not account for (neither live nor fixed): refused "
                            "rather than left at its first slot's value")
        fixed = set(storyboard.params_fixed) & self.sampled
        if fixed:
            raise PoolError(f"{self.scenario.name}: its storyboard compiles in "
                            f"{', '.join(sorted(fixed))}, which a record sets: a reset could not "
                            "give a slot its record's value (only a value, a condition's or an "
                            "action's, or a position is set per reset)")

    def take(self, n):
        """`n` rows, each a record no episode has run; waits (and counts it) when the pool is
        dry. Returns the rows' indices [n] (a host list: the reset's own indices are host)."""
        n = int(n)
        while len(self.records) - self.next < n:
            t0 = time.perf_counter()
            self.stalls += 1
            if self._thread is not None and self._thread.is_alive():
                self._thread.join()
            else:
                self.refill()
            self.stall_s += time.perf_counter() - t0
        rows = list(range(self.next, self.next + n))
        self.next += n
        self._maybe_refill()
        return rows

    def init(self, rows):
        """The rows' ego Init on the device: x, y, yaw, speed [len(rows)]."""
        x, y, yaw, v = self.init_all(rows)
        e = self.ego
        return x[:, e], y[:, e], yaw[:, e], v[:, e]

    def init_all(self, rows):
        """The rows' Init of every entity on the device: x, y, yaw, speed [len(rows), E]."""
        idx = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        with self._lock:
            return self._x[idx], self._y[idx], self._yaw[idx], self._speed[idx]

    def write_init(self, compiled, ids, rows):
        """Slots `ids` take rows `rows`' Init, every entity's (the compiled scenario's x, y, yaw,
        speed), as a compile of those records would have them."""
        c = compiled
        names = [e.name for e in c.entities]
        if names != self.entity_names:          # it writes by column (243)
            raise PoolError(f"{self.scenario.name}: the env's compile has entities {names}, the "
                            f"pool's {self.entity_names}")
        x, y, yaw, v = self.init_all(rows)
        it = torch.as_tensor(list(ids), dtype=torch.long, device=c.x.device)
        for t, val in ((c.x, x), (c.y, y), (c.yaw, yaw), (c.speed, v)):
            t[it] = val.to(t.device, t.dtype)
        # and the ego's route goal, which Init's routing may place by a record's parameter (243)
        if len(c.goal_waypoints or []) != len(self._goal or []):
            raise PoolError(f"{self.scenario.name}: the env's compile has "
                            f"{len(c.goal_waypoints or [])} route waypoints, the pool's "
                            f"{len(self._goal or [])}")
        idx = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        with self._lock:
            for w, src in zip(c.goal_waypoints or [], self._goal or []):
                for t, s in zip(w, src):
                    t[it.to(t.device)] = s[idx].to(t.device, t.dtype)

    def record(self, row):
        return self.records[row]

    def stats(self):
        return {"records_drawn": len(self.records), "taken": self.next, "chunk": self.chunk,
                "chunks": self.chunks, "refill_s": self.refill_s,
                "refill_s_per_record": self.refill_s / max(1, len(self.records)),
                "stalls": self.stalls, "stall_s": self.stall_s}
