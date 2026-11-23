"""Engine A's env origins (issue 113): slots laid out so that no car can reach another's.

Engine A's cars (aib's PhysX vehicles, built by the backend, not scene assets) are in no per-env
collision group: Isaac Lab filters only a scene built from its config's assets, and its filter
(`physxScene:invertCollisionGroupFilter`, scene-wide) would invert aib's own groups (the wheels'
ground queries against every chassis) and take the wheels off the ground. So cars of different
envs collide, and engine A keeps them apart by place instead: each slot's car stays inside its
route box (`box`, about its origin: from x0 to x1 along +x, within half_width of y = 0), and the
boxes, `gap` apart at least, are laid out in columns along y. Nothing here imports Isaac."""
import math

import numpy as np


def route_layout(n, box, ground=None, gap=3.0):
    """[n, 2] origins, slot i in column i // rows and row i % rows, the whole centred on (0, 0):
    rows `2 half_width + gap` apart in y, columns `x1 - x0 + gap` apart in x. On a `ground`
    (size x, y, m) the boxes stay on it: as many rows as fit, then as many columns as needed;
    refused when they do not fit. Without a ground, about square."""
    x0, x1, hw = (float(v) for v in box)
    if not (x1 > x0 and hw > 0 and gap >= 0):
        raise ValueError(f"route box {box}, gap {gap}: need x1 > x0, half_width > 0, gap >= 0")
    col, row = x1 - x0 + gap, 2 * hw + gap
    if ground:
        gx, gy = (float(v) for v in ground)
        rows = min(n, int((gy + gap) // row))
        if rows < 1:
            raise ValueError(f"route box {box}: not one row fits the ground's {gy} m in y")
        cols = math.ceil(n / rows)
        if cols * col - gap > gx:
            raise ValueError(f"{n} route boxes {box} ({cols} columns of {rows}, {col:.1f} m by "
                             f"{row:.1f} m) do not fit the ground ({gx} by {gy} m)")
    else:
        cols = max(1, round(math.sqrt(n * row / col)))
        rows = math.ceil(n / cols)
    i = np.arange(n)
    c, r = i // rows, i % rows
    span_x, span_y = (cols - 1) * col + (x1 - x0), (min(n, rows) - 1) * row + 2 * hw
    ox = c * col - x0 - span_x / 2
    oy = r * row + hw - span_y / 2
    return np.stack([ox, oy], -1).astype(np.float64)


def route_overlaps(origins, box, gap=0.0):
    """The pairs (i, j), i < j, whose route boxes about `origins` come closer than `gap`."""
    o = np.asarray(origins, dtype=np.float64)[:, :2]
    x0, x1, hw = (float(v) for v in box)
    dx = np.abs(o[:, None, 0] - o[None, :, 0])
    dy = np.abs(o[:, None, 1] - o[None, :, 1])
    eps = 1e-6                       # a layout's exact pitch is not an overlap
    near = (dx < (x1 - x0) + gap - eps) & (dy < 2 * hw + gap - eps)
    i, j = np.nonzero(np.triu(near, 1))
    return list(zip(i.tolist(), j.tolist()))


def min_separation(xy):
    """The smallest distance between two of the cars at `xy` [n, 2] (m), and the pair; inf and
    None for fewer than two."""
    xy = np.asarray(xy, dtype=np.float64)
    if len(xy) < 2:
        return math.inf, None
    d = np.hypot(xy[:, None, 0] - xy[None, :, 0], xy[:, None, 1] - xy[None, :, 1])
    np.fill_diagonal(d, np.inf)
    k = int(np.argmin(d))
    i, j = divmod(k, len(xy))
    return float(d[i, j]), (min(i, j), max(i, j))


def engine_a_origins(n, box, ground=None, gap=3.0):
    """Engine A's slots' places: (0, 0) for one slot; for more, laid out by their route boxes
    (`route_layout`), refused without a box or when two come closer than `gap` (issue 113)."""
    if n == 1:
        return np.zeros((1, 2))
    if not box:
        raise ValueError(f"engine A with {n} envs and no route_box: its cars are in no per-env "
                         "collision group, so their slots must be laid out apart (issue 113)")
    origins = route_layout(n, box, ground or None, gap)
    bad = route_overlaps(origins, box, gap)
    if bad:
        raise ValueError(f"engine A: route boxes {box} of slots {bad[:5]} come closer than "
                         f"{gap} m (issue 113)")
    return origins
