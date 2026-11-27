"""The sampling examples' world: a straight three-lane road as a batch map export, made without
Lanelet2 or map data, so the CS1 search runs on any machine with Python and torch.

    python3 make_straight_world.py -o straight_world.json

Lanelet 34513 + k is the lane whose centre line is y = 3.5 k (k = -1, 0, 1), from x = -50 to
x = 250 in 2 m steps, as the batch's tests' straight world (scensim_batch's test_core). The
file is the format scensim_batch.map_export writes; its map digest names this script's
geometry, not a Lanelet2 map.
"""
import argparse
import hashlib
import json

FORMAT, VERSION = "scensim-batch-lanelet-map", 3
BASE, WIDTH, X0, X1, STEP = 34513, 3.5, -50.0, 250.0, 2.0


def lanelet(k):
    y = WIDTH * k
    xs = [X0 + STEP * i for i in range(int((X1 - X0) / STEP) + 1)]
    lane = BASE + k
    return {
        "centerline": [[x, y, 0.0] for x in xs],
        "left_bound": [[x, y + WIDTH / 2] for x in xs],
        "right_bound": [[x, y - WIDTH / 2] for x in xs],
        "subtype": "road",
        "turn_direction": "else",
        "following": [],
        "previous": [],
        "left": lane + 1 if k < 1 else None,
        "right": lane - 1 if k > -1 else None,
        "adjacent_left": lane + 1 if k < 1 else None,
        "adjacent_right": lane - 1 if k > -1 else None,
        "speed_limit": 13.89,
        "speed_limit_tagged": False,
    }


def export():
    geometry = {"width": WIDTH, "x": [X0, X1], "step": STEP, "lanes": [-1, 0, 1], "base": BASE}
    digest = hashlib.sha256(json.dumps(geometry, sort_keys=True).encode()).hexdigest()
    return {"format": FORMAT, "version": VERSION, "centerline": "ssv2-fine-2.0",
            "use_custom_centerline": True, "map": "straight_three_lane", "map_sha256": digest,
            "frame": "map", "lanelets": {str(BASE + k): lanelet(k) for k in (-1, 0, 1)}}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    with open(a.output, "w") as f:
        json.dump(export(), f, indent=None, separators=(",", ":"))
        f.write("\n")


if __name__ == "__main__":
    main()
