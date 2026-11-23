"""092 K11b: `scensim.truth outcomes`, each batch slot's closest gap as the search's outcomes."""
import json
import tempfile
from pathlib import Path

from scensim import truth as T


def slot(d, k, ego_x, rid):
    """A batch truth export's slot directory: an ego and a walker 2 m long and wide apart in y,
    the ego driving to ego_x."""
    p = Path(d) / f"slot_{k}_ep0"
    p.mkdir()
    lines = [{"type": "episode", "schema": 2, "episode": 0, "start_unix": 0.0,
              "npc_motion": "kinematic", "map": "", "step_time": 0.05}]
    for i, (name, kind) in enumerate((("ego", "ego"), ("walker", "pedestrian"))):
        lines.append({"type": "entity", "frame": 0, "name": name, "index": i,
                      "role": "ego" if i == 0 else "scenario", "kind": kind,
                      "subtype": "car" if i == 0 else "pedestrian",
                      "declared": {"center": [0.0, 0.0, 0.5], "dimensions": [2.0, 2.0, 1.0]},
                      "origin_offset": [0.0, 0.0, 0.0], "sim_id": i, "asset": "scensim_batch",
                      "asset_box": None})
    xs = [0.0, ego_x / 2, ego_x]
    for f, x in enumerate(xs):
        ents = {}
        for name, pose in (("ego", [x, 0.0, 0.0, 0.0, 0.0, 0.0]),
                           ("walker", [10.0, 0.0, 0.0, 0.0, 0.0, 0.0])):
            ents[name] = {"ssv2": pose, "sim_pose": pose, "velocity": [0.0, 0.0, 0.0],
                          "angular_velocity": [0.0, 0.0, 0.0], "velocity_source": "measured",
                          "flags": ["spawn"] if f == 0 else []}
        lines.append({"type": "frame", "frame": f, "sim_time": 0.05 * f,
                      "sim_time_ns": int(5e7) * f, "sim_frame": f, "entities": ents})
    lines.append({"type": "end", "frame": len(xs) - 1, "sim_time": 0.05 * (len(xs) - 1),
                  "frames": len(xs), "dropped_frames": 0, "complete": True})
    (p / "truth.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    (p / "sample.json").write_text(json.dumps({"id": rid}))


def test_each_slot_gives_its_closest_gap_as_the_score():
    with tempfile.TemporaryDirectory() as d:
        slot(d, 0, 5.0, "a")      # closest 10 - 5 - 2 = 3 m
        slot(d, 1, 9.0, "b")      # 10 - 9 - 2 = -1 m: overlapping
        slot(d, 10, 8.0, "c")     # touching: 0 m, a failure at the threshold 0
        rows = T.slot_outcomes(d)
    assert [r["record"] for r in rows] == ["a", "b", "c"]          # slot order, not text
    got = {r["record"]: r["outcome"] for r in rows}
    assert abs(got["a"]["score"] - 3.0) < 1e-9 and not got["a"]["failed"]
    assert abs(got["b"]["score"] + 1.0) < 1e-9 and got["b"]["failed"]
    assert abs(got["c"]["score"]) < 1e-9 and got["c"]["failed"]


def test_a_slot_without_a_truth_is_an_error_run():
    with tempfile.TemporaryDirectory() as d:
        slot(d, 0, 5.0, "a")
        (Path(d) / "slot_0_ep0" / "truth.jsonl").write_text("")
        (row,) = T.slot_outcomes(d)
    assert row["outcome"]["error"] and "score" not in row["outcome"]
