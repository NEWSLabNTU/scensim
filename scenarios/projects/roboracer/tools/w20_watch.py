"""Roadmap 091 W20's verdict on a run of f1tenth_system against the RoboRacer twin, from outside
the stack, over `duration` s of sim time after the first command on `/drive`:

- the drive: the commands (their count, mean speed, and the steering's mean, step and share
  at full lock), the distance base_link travelled (the truth's), its mean speed, and its closest
  approach to the room's walls (inner faces at x = +-hx, y = +-hy): base_link's, and the body
  box's corners' (the spec's: 0.46 m ahead of the rear axle, 0.12 m behind, 0.155 m each side);
- `/odom` (vesc_to_odom, from the VESC's telemetry and the servo command) against the truth
  (`/ground_truth/odom`): each `/odom` message paired with the truth nearest in stamp (within
  30 ms), the truth taken relative to its first pose in the start's heading, as vesc_to_odom
  starts at (0, 0, 0). The position error (at the end, the largest, every 30 s), the speed's
  error (mean, RMS), the yaw rate's ratio to the truth's while turning, the heading's error;
- `/scan`: messages, their rate and gaps in sim time (stamps), the beam count, the share of
  beams in range.

    python3 w20_watch.py DURATION OUT.json [HX HY]
"""
import bisect
import json
import math
import sys
import time

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan

dur = float(sys.argv[1])
out = sys.argv[2]
HX, HY = (float(sys.argv[3]), float(sys.argv[4])) if len(sys.argv) > 4 else (6.0, 4.0)
# the truth's pose is base_link, the rear axle's centre; the spec's body box about it: wheel base
# 0.33 + front overhang 0.13 ahead, rear overhang 0.12 behind, half the 0.31 m width each side
FRONT, REAR, HALF_W = 0.33 + 0.13, 0.12, 0.155


def stamp(h):
    return h.stamp.sec + h.stamp.nanosec * 1e-9


def yaw(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


rclpy.init()
n = rclpy.create_node("w20_watch")
now = [None]
st = {"t0": None, "drives": 0, "gt": [], "odom": [], "scans": [], "speeds_cmd": []}


def on_clock(m):
    now[0] = m.clock.sec + m.clock.nanosec * 1e-9


def on_drive(m):
    st["drives"] += 1
    st["speeds_cmd"].append(m.drive.speed)
    st.setdefault("steer", []).append(m.drive.steering_angle)
    if st["t0"] is None and now[0] is not None:
        st["t0"] = now[0]


def on_gt(m):
    if st["t0"] is None:
        return
    p = m.pose.pose.position
    st["gt"].append((stamp(m.header), p.x, p.y, yaw(m.pose.pose.orientation),
                     m.twist.twist.linear.x, m.twist.twist.angular.z))


def on_odom(m):
    if st["t0"] is None:
        return
    p = m.pose.pose.position
    st["odom"].append((stamp(m.header), p.x, p.y, yaw(m.pose.pose.orientation),
                       m.twist.twist.linear.x, m.twist.twist.angular.z))


def on_scan(m):
    if st["t0"] is None:
        return
    r = [x for x in m.ranges if math.isfinite(x) and m.range_min <= x <= m.range_max]
    st["scans"].append((stamp(m.header), len(m.ranges), len(r) / max(1, len(m.ranges))))


n.create_subscription(Clock, "/clock", on_clock, 10)
n.create_subscription(AckermannDriveStamped, "/drive", on_drive, 10)
n.create_subscription(Odometry, "/ground_truth/odom", on_gt, 50)
n.create_subscription(Odometry, "/odom", on_odom, 50)
n.create_subscription(LaserScan, "/scan", on_scan, 10)
wall0 = time.monotonic()
while rclpy.ok():
    rclpy.spin_once(n, timeout_sec=0.05)
    if st["t0"] is None and time.monotonic() - wall0 > 900:   # no drive in 15 min: the run failed
        with open(out, "w") as f:
            json.dump({"error": "no /drive within 900 s wall clock", "scans": len(st["scans"])}, f)
        sys.exit(1)
    if st["t0"] is not None and now[0] is not None and now[0] - st["t0"] > dur:
        break

gt, od = st["gt"], st["odom"]
res = {"duration_s": dur, "room_inner_half": [HX, HY], "drive_msgs": st["drives"],
       "cmd_speed_mean": round(sum(st["speeds_cmd"]) / max(1, len(st["speeds_cmd"])), 3)}
sv = st.get("steer", [])
if len(sv) > 2:
    dd = [b - a for a, b in zip(sv, sv[1:])]
    res["steer_cmd"] = {"abs_mean_rad": round(sum(abs(x) for x in sv) / len(sv), 3),
                        "step_abs_mean_rad": round(sum(abs(x) for x in dd) / len(dd), 4),
                        "sign_flips_share": round(
                            sum(1 for a, b in zip(sv, sv[1:]) if a * b < 0) / len(dd), 3),
                        "at_lock_share": round(sum(1 for x in sv if abs(x) >= 0.359) / len(sv), 3)}
dist, wall_c, wall_b = 0.0, 1e9, 1e9
for (_, x0, y0, *_), (_, x, y, h, *_) in zip(gt, gt[1:]):
    dist += math.hypot(x - x0, y - y0)
for _, x, y, h, *_ in gt:
    wall_c = min(wall_c, HX - abs(x), HY - abs(y))
    c, s = math.cos(h), math.sin(h)
    for dx, dy in ((FRONT, HALF_W), (FRONT, -HALF_W), (-REAR, HALF_W), (-REAR, -HALF_W)):
        wall_b = min(wall_b, HX - abs(x + c * dx - s * dy), HY - abs(y + s * dx + c * dy))
res.update(distance_m=round(dist, 2), truth_speed_mean=round(sum(g[4] for g in gt) / len(gt), 3),
           closest_wall_centre_m=round(wall_c, 3), closest_wall_body_m=round(wall_b, 3),
           wall_contact=wall_b <= 0.0)

# /odom against the truth, relative to the truth's first pose in the start's heading
t0, gx0, gy0, gh0 = gt[0][:4]
c0, s0 = math.cos(-gh0), math.sin(-gh0)


def rel(g):
    dx, dy = g[1] - gx0, g[2] - gy0
    return c0 * dx - s0 * dy, s0 * dx + c0 * dy, math.remainder(g[3] - gh0, 2 * math.pi), g[4]


gts = [g[0] for g in gt]


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * q / 100))]


def worst(errs, ts):
    """The largest heading error, when, and how many pairs are over 30 deg."""
    i = max(range(len(errs)), key=lambda i: abs(errs[i]))
    return {"t": round(ts[i], 2), "deg": round(math.degrees(errs[i]), 2),
            "pairs_over_30deg": sum(1 for e in errs if abs(e) > math.radians(30))}
pos_err, v_err, h_err, pairs, ts_p, w_pairs = [], [], [], 0, [], []
for o in od:
    i = bisect.bisect_left(gts, o[0])
    cand = [j for j in (i - 1, i) if 0 <= j < len(gt)]
    j = min(cand, key=lambda j: abs(gts[j] - o[0]))
    if abs(gts[j] - o[0]) > 0.03:
        continue
    x, y, h, v = rel(gt[j])
    pos_err.append(math.hypot(o[1] - x, o[2] - y))
    v_err.append(o[4] - v)
    w_pairs.append((o[5], gt[j][5]))
    h_err.append(math.remainder(o[3] - h, 2 * math.pi))
    ts_p.append(o[0] - t0)
    pairs += 1
if pairs:
    turning = [a / b for a, b in w_pairs if abs(b) > 0.2]
    res["odom_vs_truth"] = {
        "pairs": pairs, "odom_msgs": len(od),
        "pos_err_end_m": round(pos_err[-1], 3), "pos_err_max_m": round(max(pos_err), 3),
        "pos_err_end_share_of_distance": round(pos_err[-1] / max(dist, 1e-9), 4),
        "speed_err_mean": round(sum(v_err) / pairs, 4),
        "speed_err_rms": round(math.sqrt(sum(e * e for e in v_err) / pairs), 4),
        # yaw rate: vesc_to_odom's kinematic v tan(servo angle) / wheel base against the truth's,
        # over the pairs turning faster than 0.2 rad/s: their ratio's median, and the mean error
        "yaw_rate_ratio_median": round(pct(turning, 50), 4) if turning else None,
        "yaw_rate_err_rms": round(math.sqrt(sum((a - b) ** 2 for a, b in w_pairs)
                                            / len(w_pairs)), 4),
        "heading_err_end_deg": round(math.degrees(h_err[-1]), 2),
        "heading_err_max_deg": round(max(abs(math.degrees(e)) for e in h_err), 2),
        "heading_err_abs_p50_deg": round(pct([abs(math.degrees(e)) for e in h_err], 50), 2),
        "heading_err_abs_p95_deg": round(pct([abs(math.degrees(e)) for e in h_err], 95), 2),
        "heading_err_worst": worst(h_err, ts_p),
        "every_30s": [{"t": round(ts_p[i], 1), "pos_err_m": round(pos_err[i], 3),
                       "heading_err_deg": round(math.degrees(h_err[i]), 2)}
                      for i in range(len(ts_p))
                      if i == len(ts_p) - 1 or int(ts_p[i] // 30) != int(ts_p[i + 1] // 30)],
        "odom_end": [round(od[-1][1], 3), round(od[-1][2], 3)],
        "truth_end_rel": [round(v, 3) for v in rel(gt[-1])[:2]],
    }
sc = st["scans"]
if len(sc) > 1:
    ts = [a for a, _, _ in sc]
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    res["scan"] = {"msgs": len(sc), "rate_hz": round((len(sc) - 1) / (ts[-1] - ts[0]), 2),
                   "gap_max_s": round(max(gaps), 4), "gap_min_s": round(min(gaps), 4),
                   "beams": sorted({b for _, b, _ in sc}),
                   "in_range_mean": round(sum(f for _, _, f in sc) / len(sc), 3)}
print(json.dumps(res))
with open(out, "w") as f:
    json.dump(res, f, indent=1)

