"""SSv2's Catmull-Rom spline, ported (math::geometry::CatmullRomSpline, HermiteCurve), with no
torch: the geometry of world_lanelet's map queries, which world_lanelet imports from here, so a
tool without torch (scensim check's lint of reversed stretches, issue 166) reads the same
spline. See world_lanelet's docstring for how it follows SSv2.
"""
import math

TOL = 1e-7                  # SSv2's PolynomialSolver::tolerance
EPS = 2.220446049250313e-16
MATCHING_DISTANCE = 1.0     # SSv2's default for toLaneletPose
NEARBY_DISTANCE = 0.1       # nearbyLaneletIds' distance_threshold and search_count
NEARBY_COUNT = 5
YAW_THRESHOLD = math.radians(45.0)


# --- SSv2's polynomial solver ------------------------------------------------------------------

def _approx(a, b):
    return abs(a - b) <= TOL


def _filter(values, lo, hi):
    out = []
    for v in values:
        if lo <= v <= hi:
            out.append(v)
        elif abs(v - hi) <= TOL:
            out.append(hi)
        elif abs(v - lo) <= TOL:
            out.append(lo)
    return out


def _linear(a, b, lo, hi):
    if _approx(a, 0):
        if _approx(b, 0):
            raise ValueError("a linear equation 0 x + 0 = 0")
        return []
    return _filter([-b / a], lo, hi)


def _quadratic(a, b, c, lo, hi):
    if _approx(a, 0):
        return _linear(b, c, lo, hi)
    disc = b * b - 4 * a * c
    if _approx(disc, 0):
        sols = [-b / (2 * a)]
    elif disc < 0:
        sols = []
    else:
        r = math.sqrt(disc)
        sols = [(-b - r) / (2 * a), (-b + r) / (2 * a)]
    return _filter(sols, lo, hi)


def _monic_cubic(a, b, c):
    """Real roots of x^3 + a x^2 + b x + c (SSv2's solveMonicCubicEquationWithComplex, then
    its real parts with |imag| <= eps)."""
    q = (a * a - 3 * b) / 9
    r = (a * (2 * a * a - 9 * b) + 27 * c) / 54
    q3 = q * q * q
    if r * r <= q3 + TOL:
        if q3 <= 0:      # sqrt of a negative, or 0/0: NaN roots in SSv2, which none passes
            return []
        t = math.acos(max(-1.0, min(1.0, r / math.sqrt(q3))))
        sq = math.sqrt(q)
        return [-2 * sq * math.cos(t / 3) - a / 3,
                -2 * sq * math.cos((t + 2 * math.pi) / 3) - a / 3,
                -2 * sq * math.cos((t - 2 * math.pi) / 3) - a / 3]
    real = -((abs(r) + math.sqrt(r * r - q3)) ** (1.0 / 3.0))
    A = -real if r < 0 else real
    B = 0.0 if _approx(A, 0) else q / A
    imag = 0.5 * math.sqrt(3.0) * (A - B)
    if _approx(imag, 0):
        return [(A + B) - a / 3, -0.5 * (A + B) - a / 3]
    return [(A + B) - a / 3]     # the other two have an imaginary part above eps


def _cubic(a, b, c, d, lo, hi):
    if _approx(a, 0):
        return _quadratic(b, c, d, lo, hi)
    return _filter(_monic_cubic(b / a, c / a, d / a), lo, hi)


# --- SSv2's Hermite curve and Catmull-Rom spline -----------------------------------------------

class Hermite:
    """x(t) = ax t^3 + bx t^2 + cx t + dx (and y, z), t in [0, 1]."""

    __slots__ = ("c", "length")

    def __init__(self, cx, cy, cz):
        self.c = (cx, cy, cz)
        self.length = self._length(100)

    def _length(self, n):
        (ax, bx, cx, _), (ay, by, cy, _), (az, bz, cz, _) = self.c
        ret, ds = 0.0, 1.0 / n
        for i in range(n):
            s = i * ds
            x = 3 * s * s * ax + 2 * s * bx + cx
            y = 3 * s * s * ay + 2 * s * by + cy
            z = 3 * s * s * az + 2 * s * bz + cz
            ret += math.sqrt(x * x + y * y + z * z) * ds
        return ret

    def point(self, t):
        return tuple(a * t ** 3 + b * t * t + c * t + d for a, b, c, d in self.c)

    def tangent(self, t):
        return tuple(3 * a * t * t + 2 * b * t + c for a, b, c, _ in self.c)

    def collisions(self, p0, p1):
        """SSv2's getCollisionPointsIn2D(point0, point1): the curve's parameters where it
        crosses the segment p0-p1."""
        (ax, bx, cx, dx), (ay, by, cy, dy), _ = self.c
        fx, ex = p0[0], p1[0] - p0[0]
        fy, ey = p0[1], p1[1] - p0[1]
        a = ay * ex - ax * ey
        b = by * ex - bx * ey
        c = cy * ex - cx * ey
        d = dy * ex - dx * ey - ex * fy + ey * fx
        if _approx(a, 0) and _approx(b, 0) and _approx(c, 0) and _approx(d, 0):
            sols = [0.0]
        else:
            sols = _cubic(a, b, c, d, 0.0, 1.0)
        out = set()
        for t in sols:
            x = ax * t ** 3 + bx * t * t + cx * t + dx
            y = ay * t ** 3 + by * t * t + cy * t + dy
            with_nan = lambda num, den: num / den if den != 0 else (  # noqa: E731
                math.copysign(math.inf, num) if num != 0 else math.nan)
            tx, ty = with_nan(x - p0[0], ex), with_nan(y - p0[1], ey)
            if abs(tx - ty) > EPS or math.isnan(tx) or math.isnan(ty):
                if 0 <= tx <= 1 or 0 <= ty <= 1:
                    out.add(t)
            elif 0 <= tx <= 1 and 0 <= ty <= 1:
                out.add(t)
        return out


def _catmull_curves(p):
    """SSv2's CatmullRomSpline curves through control points `p` (three or more)."""
    n = len(p) - 1
    curves = []
    for i in range(n):
        axes = []
        for k in range(3):
            if i == 0:
                a, b = 0.0, p[0][k] - 2 * p[1][k] + p[2][k]
                c, d = -3 * p[0][k] + 4 * p[1][k] - p[2][k], 2 * p[0][k]
            elif i == n - 1:
                a, b = 0.0, p[i - 1][k] - 2 * p[i][k] + p[i + 1][k]
                c, d = -p[i - 1][k] + p[i + 1][k], 2 * p[i][k]
            else:
                a = -p[i - 1][k] + 3 * p[i][k] - 3 * p[i + 1][k] + p[i + 2][k]
                b = 2 * p[i - 1][k] - 5 * p[i][k] + 4 * p[i + 1][k] - p[i + 2][k]
                c, d = -p[i - 1][k] + p[i + 1][k], 2 * p[i][k]
            axes.append((a * 0.5, b * 0.5, c * 0.5, d * 0.5))
        curves.append(Hermite(*axes))
    return curves


class Spline:
    """SSv2's CatmullRomSpline (three or more control points)."""

    def __init__(self, points):
        pts = [tuple(float(v) for v in (list(q) + [0.0] * (3 - len(q)))[:3]) for q in points]
        if len(pts) < 3:
            raise ValueError(f"a spline needs three points, got {len(pts)}")
        self.points = pts
        self.curves = _catmull_curves(pts)
        self.lengths = [c.length for c in self.curves]
        self.length = sum(self.lengths)

    def index_and_s(self, s):
        if s < 0:
            return 0, s
        if s >= self.length:
            return len(self.curves) - 1, s - (self.length - self.lengths[-1])
        acc = 0.0
        for i, ln in enumerate(self.lengths):
            if acc <= s < acc + ln:
                return i, s - acc
            acc += ln
        return len(self.curves) - 1, s - (self.length - self.lengths[-1])

    def _t(self, s):
        i, local = self.index_and_s(s)
        return self.curves[i], local / self.curves[i].length

    def point(self, s, offset=0.0):
        c, t = self._t(s)
        x, y, z = c.point(t)
        if offset:
            tx, ty, _ = c.tangent(t)
            th = math.atan2(tx, -ty)     # the normal: the tangent turned by +90 degrees
            x, y = x + offset * math.cos(th), y + offset * math.sin(th)
        return x, y, z

    def tangent(self, s):
        c, t = self._t(s)
        return c.tangent(t)

    def yaw(self, s):
        tx, ty, _ = self.tangent(s)
        return math.atan2(ty, tx)

    def s_value(self, x, y, yaw, threshold, quat=None):
        """SSv2's getSValue(pose, threshold): where the pose's y axis (±threshold) first
        crosses the spline. The pose is (x, y, yaw), or its full orientation `quat` (x, y, z,
        w), as SSv2 transforms the segment's ends."""
        if quat is None:
            ey = (-math.sin(yaw), math.cos(yaw))
        else:
            qx, qy, qz, qw = quat
            ey = (2 * (qx * qy - qz * qw), 1 - 2 * (qx * qx + qz * qz))   # R's second column
        p0 = (x + threshold * ey[0], y + threshold * ey[1])
        p1 = (x - threshold * ey[0], y - threshold * ey[1])
        acc = 0.0
        for c in self.curves:
            ts = c.collisions(p0, p1)
            if ts:
                return acc + min(ts) * c.length
            acc += c.length
        return None

    def collision_s(self, polygon, search_backward=False):
        """SSv2's getCollisionPointIn2D(polygon): the first s (the last, `search_backward`)
        where the closed polygon's edges cross the spline (two points: the segment both
        ways)."""
        poly = [tuple(p[:2]) for p in polygon]
        if len(poly) < 2:
            raise ValueError("a polygon of fewer than two points")
        edges = list(zip(poly, poly[1:])) + [(poly[-1], poly[0])]
        out = set()
        acc = 0.0
        for c in self.curves:
            for a, b in edges:
                out |= {acc + t * c.length for t in c.collisions(a, b)}
            acc += c.length
        if not out:
            return None
        return max(out) if search_backward else min(out)


# --- geometry helpers --------------------------------------------------------------------------

def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 <= 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _inside(px, py, poly):
    hit = False
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        if (ay > py) != (by > py) and px < ax + (py - ay) * (bx - ax) / (by - ay):
            hit = not hit
    return hit


def _poly_dist(px, py, poly):
    """lanelet2's 2D distance from a point to a lanelet's polygon (0 inside)."""
    if _inside(px, py, poly):
        return 0.0
    return min(_seg_dist(px, py, *a, *b) for a, b in zip(poly, poly[1:] + poly[:1]))


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi



def reversed_ts(curve):
    """The parameter ranges in [0, 1] where a spline curve's tangent points against its chord
    (issue 166): tangent . chord is a quadratic in t, so its roots bound them exactly."""
    (ax, bx, cx, _), (ay, by, cy, _), _ = curve.c
    ex, ey = ax + bx + cx, ay + by + cy          # the chord, point(1) - point(0)
    qa, qb, qc = 3 * (ax * ex + ay * ey), 2 * (bx * ex + by * ey), cx * ex + cy * ey
    cuts = [0.0, 1.0]
    if abs(qa) > 1e-15:
        disc = qb * qb - 4 * qa * qc
        if disc > 0:
            r = math.sqrt(disc)
            cuts += [t for t in ((-qb - r) / (2 * qa), (-qb + r) / (2 * qa)) if 0 < t < 1]
    elif abs(qb) > 1e-15 and 0 < -qc / qb < 1:
        cuts.append(-qc / qb)
    cuts.sort()
    out = []
    for a, b in zip(cuts, cuts[1:]):
        m = (a + b) / 2
        if b > a and qa * m * m + qb * m + qc < 0:
            out.append((a, b))
    return out


def lanelet_stretches(points):
    """A lanelet's reversed stretches, [(from_s, to_s)] in its own s, from its centre points
    (SSv2's spline through them; issue 166), merged where they touch; [] for fewer than three
    points (a line or a point never reverses)."""
    pts = [tuple(float(v) for v in (list(q) + [0.0] * (3 - len(q)))[:3]) for q in points]
    dedup = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
    if len(dedup) < 3:
        return []
    spl = Spline(points)
    out, c0 = [], 0.0
    for curve, ln in zip(spl.curves, spl.lengths):
        for a, b in reversed_ts(curve):
            lo, hi = c0 + a * ln, c0 + b * ln
            if out and lo <= out[-1][1] + 1e-9:
                out[-1] = (out[-1][0], max(out[-1][1], hi))
            else:
                out.append((lo, hi))
        c0 += ln
    return out
