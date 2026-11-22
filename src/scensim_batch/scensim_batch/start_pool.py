"""Episode starts drawn per reset from real sample records (roadmap 094 P2; batch-executor.md
section 10): a pool the scenario's own Sampler fills on the host, in chunks and in the
background, every record compiled to its Init (the ego's pose and speed), and taken one per
reset. So every training episode is a sample record as `scensim-sample draw` writes it, its id
logged with the slot and episode that ran it, and replayable on seats unchanged.

    pool = StartPool(dist_xosc, world, seed=7, chunk=10000, device="cuda")
    rows = pool.take(env_ids)          # one record each, never one used before
    x, y, yaw, speed = pool.init(rows) # the ego's Init on the device

Only Init is drawn again: a scenario whose storyboard reads a sampled parameter (a trigger at
`$onset_s`, say) is refused, since its compiled storyboard holds each slot's values. The pool
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


class StartPool:
    """Sample records of one distribution, compiled to the ego's Init, taken one per reset."""

    def __init__(self, distribution, world, seed, chunk=10000, low_water=None, device="cpu",
                 provides=(), background=True, sampler=None):
        from scensim_sampler.sampler import Sampler
        self.sampler = sampler or Sampler.from_file(distribution)
        self.scenario = Path(self.sampler.scenario.path)
        sampled = set(self.sampler.scenario.parameters)
        reads = storyboard_parameters(self.scenario) & sampled
        if reads:
            raise PoolError(f"{self.scenario.name}: its storyboard reads {', '.join(sorted(reads))}"
                            ", which a record sets: a start pool draws only Init again per reset "
                            "(the compiled storyboard holds each slot's values)")
        self.world, self.provides = world, tuple(provides)
        self.seed, self.chunk = int(seed), int(chunk)
        self.low_water = int(low_water if low_water is not None else chunk // 2)
        self.device = torch.device(device)
        self.records = []            # every record drawn, in order (the pool's rows)
        self.next = 0                # the first row not yet taken
        self.chunks = 0
        self.stalls, self.stall_s = 0, 0.0
        self.refill_s, self.refills = 0.0, 0
        self._x = self._y = self._yaw = self._speed = None
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
        c = compilemod.compile_scenario(self.scenario, recs, self.world, provides=self.provides)
        e = c.of_role("ego")[0]
        cols = [t[:, e].to(self.device, torch.float64) for t in (c.x, c.y, c.yaw, c.speed)]
        with self._lock:
            self.records.extend(recs)
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
        idx = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        with self._lock:
            return self._x[idx], self._y[idx], self._yaw[idx], self._speed[idx]

    def record(self, row):
        return self.records[row]

    def stats(self):
        return {"records_drawn": len(self.records), "taken": self.next, "chunk": self.chunk,
                "chunks": self.chunks, "refill_s": self.refill_s,
                "refill_s_per_record": self.refill_s / max(1, len(self.records)),
                "stalls": self.stalls, "stall_s": self.stall_s}
