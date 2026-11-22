"""Roadmap 091 W10: draw a perturbation nobody has seen, for a blind check of the fit.

    python3 draw_perturbation.py --out SEALED_DIR/perturbation.yaml

p1 and p2 are files in the repository, so whoever runs the fit can read their truth. This one
is drawn from os.urandom within the ranges below (the car as it might differ from its spec,
the span p1 and p2 cover) and written straight to `--out`, inside a sealed directory that
twin_runs.py reads with `--perturb` and copies to its own `--sealed`. Only its sha256 is
printed. Read it only after the fit, as check_recovery.py does.
"""
import argparse
import hashlib
import os
import random
from pathlib import Path

import yaml

RANGES = {  # uniform, inclusive
    ("vehicle", "mass"): (3.4, 4.3),
    ("front", "lat_stiff_value"): (6.0, 16.0),
    ("front", "tire_friction"): (0.6, 1.0),
    ("rear", "lat_stiff_value"): (10.0, 24.0),
    ("rear", "tire_friction"): (0.9, 1.3),
    ("component", "current_max"): (25.0, 45.0),
    ("component", "speed_kp"): (0.004, 0.008),
    ("component", "latency"): (0.020, 0.050),
    ("component", "servo_offset"): (0.520, 0.545),
}
NOISE = {"ref_pos": 0.002, "ref_yaw": 0.003, "imu_accel": 0.05, "imu_gyro": 0.005,
         "erpm": 30.0, "current": 0.3}


def draw(rng):
    """A perturbation in twin_runs.py's format, from `rng`."""
    def u(key, digits):
        lo, hi = RANGES[key]
        return round(rng.uniform(lo, hi), digits)
    return {
        "vehicle": {
            "mass": u(("vehicle", "mass"), 3),
            "axle_tires": {axle: {"tire_friction": u((axle, "tire_friction"), 4),
                                  "lat_stiff_value": u((axle, "lat_stiff_value"), 4)}
                           for axle in ("front", "rear")},
        },
        "component": {k: u(("component", k), 5)
                      for k in ("current_max", "speed_kp", "latency", "servo_offset")},
        "noise": dict(NOISE),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"{out} exists: a drawn perturbation is never overwritten")
    out.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(draw(random.Random(os.urandom(32))), sort_keys=False)
    out.write_text(text)
    print(f"drawn: {out} sha256 {hashlib.sha256(text.encode()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
