"""scensim.behaviour.seats (roadmap 092 K12): models on the truth stream, their commands on the
tick gate."""
import io
import json

import numpy as np

from scensim.behaviour import seats


class Gate:
    def __init__(self):
        self.sent = []

    def send(self, frame, commands):
        self.sent.append((frame, dict(commands)))


class Model:
    """Walks east at the ego's distance in m/s, and says `go` on its second step."""

    def __init__(self):
        self.seen, self.k = [], 0

    def step(self, obs, dt):
        self.seen.append((dict((k, float(v[0])) for k, v in obs.items()), dt))
        self.k += 1
        gap = abs(float(obs["ego_x"][0] - obs["x"][0]))
        return ({"speed": np.array([gap]), "heading": np.array([0.0]),
                 "accel_limit": np.array([1.5])}, np.array([1 if self.k == 2 else 0]))


def frame(n, ents, t0=1_000_000_000_000):
    return {"frame": n, "sim_frame": 5000 + n, "sim_time_ns": t0 + n * 50_000_000,
            "entities": ents}


def test_each_frame_is_answered_with_its_commands_and_decisions():
    gate, model, out = Gate(), Model(), io.StringIO()
    r = seats.Runner({"walker": model}, "ego", gate, out, step_time=0.05)
    r.on_frame(frame(1, {"ego": (0.0, 0.0, 0.0, 10.0, 0.0), "walker": (3.0, 4.0, 0.0, 0, 0)}))
    r.on_frame(frame(2, {"ego": (0.5, 0.0, 0.0, 11.0, 0.0), "walker": (3.0, 4.0, 0.0, 0, 0)}))
    # a frame without the walker: the world keeps its last command, the frame is still answered
    r.on_frame(frame(3, {"ego": (1.0, 0.0, 0.0, 11.0, 0.0), "walker": None}))
    assert gate.sent == [(5001, {"walker": (3.0, 0.0, 1.5)}), (5002, {"walker": (2.5, 0.0, 1.5)}),
                         (5003, {})]
    # the ego's acceleration differenced over the frame's sim time: 1 m/s in 0.05 s
    (o1, dt1), (o2, dt2) = model.seen
    assert (o1["ego_ax"], dt1) == (0.0, 0.05)
    assert abs(o2["ego_ax"] - 20.0) < 1e-9 and abs(dt2 - 0.05) < 1e-12
    (line,) = out.getvalue().splitlines()
    assert json.loads(line) == {"frame": 2, "sim_frame": 5002, "entity": "walker", "event": "go"}


def test_the_record_is_the_runs_sample_else_its_parameters_and_seed(tmp_path):
    env = {"SCENSIM_RUN_DIR": str(tmp_path), "SCENSIM_RUN_SEED": "42",
           "SCENSIM_PARAMETERS": json.dumps({"walk_speed": 1.4})}
    assert seats.record_of(env) == {"seeds": {"scenario": 42}, "values": {"walk_speed": 1.4}}
    (tmp_path / "sample.json").write_text(json.dumps(
        {"id": "s", "values": {"walk_speed": 1.2, "gap": 3}, "seeds": {"pilots": {"walker": 7}}}))
    rec = seats.record_of(env)
    assert rec["seeds"] == {"pilots": {"walker": 7}} and rec["values"]["walk_speed"] == 1.4


def test_a_truth_frame_message_becomes_a_frame():
    class Msg:
        frame, sim_frame, sim_time_ns = 3, 5003, 1_000_150_000_000
        names, present = ["ego", "walker"], [True, False]
        poses = [1, 2, 0, 0, 0, 0.5] + [0] * 6
        velocities = [4, 0.5, 0] + [0] * 3
    f = seats.frame_of(Msg)
    assert f == {"frame": 3, "sim_frame": 5003, "sim_time_ns": 1_000_150_000_000,
                 "entities": {"ego": (1, 2, 0.5, 4, 0.5), "walker": None}}
