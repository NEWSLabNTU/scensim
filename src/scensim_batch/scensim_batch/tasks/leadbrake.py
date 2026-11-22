"""094 P4, ours: the lead car brakes ahead (CS2's family, straight, dry, day), stock's task
(WheeledLab isaaclab-3.0 bench/p4_leadbrake, fef6385) through K2's environment. The episode
is a compiled scenario (scenarios/projects/leadbrake_rl: leadbrake.xosc, drawn per reset by
leadbrake_dist.xosc's joint model at stock's distribution), the lead SSv2's default vehicle on
the batched behaviour, braking by the storyboard at its record's onset and rate.

The road is the world here: one straight lanelet (id 1), `LANE_LENGTH` long and 3.5 m wide, on
x from 0 at y = 0, as stock's each env's +x axis; the ego starts EGO_S along it, so stock's route
of ROUTE metres ends at EGO_S + ROUTE."""
from pathlib import Path

# stock's (mdp.py), named; positions here are along lanelet 1
ROUTE = 300.0              # m, from the ego's start
LANE_HALF = 1.75           # m: the lane is 3.5 m wide
OFF_ROAD = 3.0             # m from the lane's centre
SPEED_LIMIT = 15.0         # m/s
SAFE_GAP = (2.0, 8.0)      # m: the safe stop behind a stopped lead
RANGES = {"lead_speed": (8.0, 14.0), "headway": (1.0, 3.0), "decel": (3.0, 7.0),
          "onset": (40.0, 120.0)}
# ours: the ego's start along the lanelet (leadbrake.xosc), the lanelet's length (ROUTE and the
# lead's longest stop, 14 m/s from 120 m + 3 s x 14 m/s ahead at 3 m/s^2, inside it), and the
# Model 3's box about its origin (sim_vehicle_spec's catalog entry: stock's lead's footprint)
EGO_S = 5.0
LANE_LENGTH = 400.0
FRONT, REAR = 3.812, 0.98
BEHIND = 1000.0            # m: leadbrake.xosc's onset is a distance from (-BEHIND, 0)


def project():
    return Path(__file__).resolve().parents[4] / "scenarios" / "projects" / "leadbrake_rl"


def straight_world():
    """The task's world: lanelet 1, straight along +x from 0, LANE_LENGTH long, 3.5 m wide, at a
    speed limit SSv2's default vehicle never reaches here (the lead cruises at its record's)."""
    from ..world_lanelet import LaneletWorld
    return LaneletWorld.from_polylines({1: [[0.0, 0.0], [LANE_LENGTH, 0.0]]}, width=2 * LANE_HALF,
                                       speed_limit=30.0)


def episode_from_record(values):
    """Stock's draws (lead_speed, headway, decel, onset) back from a record's values: the joint
    model's derived positions inverted (models/leadbrake_episode.yaml)."""
    v = float(values["lead_speed"])
    return {"lead_speed": v,
            "headway": (float(values["lead_s"]) - EGO_S - FRONT - REAR) / v,
            "decel": float(values["decel"]),
            "onset": float(values["onset_d"]) - BEHIND - EGO_S - REAR}


KEYS = ("lead_speed", "headway", "decel", "onset")      # stock's samples, its order


def record_from_episode(ep, k=0):
    """A start-pool record of one of stock's episodes (its four samples): the values the
    distribution's model derives from them (models/leadbrake_episode.yaml), the latents named,
    an id of its values. The inverse of episode_from_record."""
    import hashlib
    import json
    v, h, d, on = (float(ep[k_]) for k_ in KEYS)
    values = {"lead_speed": v, "decel": d, "ego_speed": v,
              "lead_s": EGO_S + h * v + FRONT + REAR, "onset_d": BEHIND + EGO_S + on + REAR}
    rid = hashlib.sha256(json.dumps([k, values], sort_keys=True).encode()).hexdigest()
    return {"record": k + 1, "id": rid, "values": values, "latent": {"headway": h, "onset": on},
            "derived": ["ego_speed", "lead_s", "onset_d"], "replayed": "stock evaluator",
            "stock": {x: ep[x] for x in ("success", "end_reason") if x in ep}}


def records_from_samples(path):
    """Stock's evaluator's --samples-out file (WheeledLab isaaclab-3.0 9810846: its episodes in
    env order) as start-pool records, in that order."""
    import json
    doc = json.loads(Path(path).read_text())
    if list(doc.get("keys", [])) != list(KEYS):
        raise ValueError(f"{path}: keys {doc.get('keys')}, not stock's {list(KEYS)}")
    return [record_from_episode(ep, k) for k, ep in enumerate(doc["episodes"])], doc


# --- the task, through K2's environment ---------------------------------------------------------
# Isaac Lab is imported by the environment's module; this file's constants and world serve the
# tests without it (test_leadbrake)

BRAKE_DAMPING = 6000.0     # N m s/rad: stock's, the spin joints' damping while braking
SPEC = "tesla_model3"
BODY_NAME = "carla-0.9.16"                   # the spec's body stock's car copies
BODY = f"articulation_{BODY_NAME}.yaml"      # its generated articulation file


def _spec_root():
    return Path(__file__).resolve().parents[3] / "sim_vehicle_spec"


def check_trigger_geometry(scenario, world):
    """243: leadbrake.xosc's onset is the lead's distance from a point BEHIND metres behind the
    lane's start, which is its s + BEHIND only while lanelet 1 runs straight along y = 0, the
    point lies on that line and the lead keeps to the centre line. Refuse anything else, loudly,
    so the trigger cannot stop being s without an error. Returns nothing; raises ValueError."""
    import xml.etree.ElementTree as ET
    pts = world.lanelets[1]["centerline"]
    if abs(float(pts[0][0])) > 1e-12 or any(abs(float(p[1])) > 1e-12 for p in pts) or \
            any(float(b[0]) <= float(a[0]) for a, b in zip(pts, pts[1:])):
        raise ValueError("leadbrake: lanelet 1 is not straight along +x from x = 0 at y = 0: "
                         "the onset condition is not the lead's s, nor x - EGO_S the ego's")
    root = ET.parse(scenario).getroot()
    for c in root.iter("DistanceCondition"):
        wp = c.find("Position/WorldPosition")
        if wp is None or abs(float(wp.get("y", "0"))) > 1e-12 or \
                float(wp.get("x", "0")) != -BEHIND:
            raise ValueError("leadbrake: the onset's WorldPosition is not on the lane's line, "
                             f"{BEHIND} m behind its start")
    for p in root.iter("Private"):
        if p.get("entityRef") == "lead":
            for lp in p.iter("LanePosition"):
                if float(lp.get("offset", "0")) != 0.0:
                    raise ValueError("leadbrake: the lead is off the lane's centre line: the "
                                     "onset condition is not its s")


def ackermann(delta, wheel_base, tread):
    """Stock's (mdp.ackermann): the left and right front wheels' angles for the bicycle angle."""
    import torch
    t = torch.tan(delta)
    left = torch.atan2(wheel_base * t, wheel_base - 0.5 * tread * t)
    right = torch.atan2(wheel_base * t, wheel_base + 0.5 * tread * t)
    return torch.where(delta.abs() < 1e-9, torch.zeros_like(delta), left), \
        torch.where(delta.abs() < 1e-9, torch.zeros_like(delta), right)
