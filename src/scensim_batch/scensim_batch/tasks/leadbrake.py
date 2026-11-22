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
