"""scensim.behaviour.seats (roadmap 092 K12): models on the truth stream, their commands on the
tick gate."""
import io
import math
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


def frame(n, ents, t0=1_000_000_000_000, started=True):
    return {"frame": n, "sim_frame": 5000 + n, "sim_time_ns": t0 + n * 50_000_000,
            "npc_logic_started": started, "entities": ents}


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


def test_a_model_does_not_step_command_or_decide_before_ssv2_starts_npc_logic():
    """Issue 163: SSv2 holds its NPCs until startNpcLogic, and a model is NPC logic. Before it
    (the frames S) the runner answers each frame with no command and does not step the model,
    so the entity stands at its Init pose; from the first started frame it runs as before."""
    gate, model, out = Gate(), Model(), io.StringIO()
    r = seats.Runner({"walker": model}, "ego", gate, out, step_time=0.05)
    ents = {"ego": (0.0, 0.0, 0.0, 10.0, 0.0), "walker": (3.0, 4.0, 0.0, 0, 0)}
    for n in (1, 2, 3):
        r.on_frame(frame(n, ents, started=False))
    assert gate.sent == [(5001, {}), (5002, {}), (5003, {})]
    assert model.seen == [] and out.getvalue() == ""
    r.on_frame(frame(4, ents))
    r.on_frame(frame(5, ents))
    assert gate.sent[3:] == [(5004, {"walker": (3.0, 0.0, 1.5)}),
                             (5005, {"walker": (3.0, 0.0, 1.5)})]
    assert len(model.seen) == 2                      # its first step is the first started frame
    (line,) = out.getvalue().splitlines()
    assert json.loads(line)["frame"] == 5            # its second step's event, as before


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
        npc_logic_started = True
        names, present = ["ego", "walker"], [True, False]
        poses = [1, 2, 0, 0, 0, 0.5] + [0] * 6
        velocities = [4, 0.5, 0] + [0] * 3
        angular_velocities = [0] * 6
    f = seats.frame_of(Msg, {"ego": (0.0, 0.0, 0.0), "walker": (0.0, 0.0, 0.0)})
    assert f == {"frame": 3, "sim_frame": 5003, "sim_time_ns": 1_000_150_000_000,
                 "npc_logic_started": True,
                 "entities": {"ego": (1, 2, 0.5, 4, 0.5), "walker": None}}
    # an entity whose offset has not arrived (the latched entities topic) is absent
    assert seats.frame_of(Msg, {})["entities"]["ego"] is None


def test_a_model_reads_the_entitys_pose_as_boxes_takes_it_from_the_truth():
    """Issue 130: on a truth whose ego body sits 1.387 m ahead of its entity, the model's ego
    is the entity's pose, the one scensim.truth.boxes builds the ego's box from."""
    from scensim import truth as T
    gt, gg = T._module("gap_trace"), T._module("gap_geometry")
    off = (1.387, 0.0, 0.0)
    header = gt.EntityHeader(frame=0, name="ego", kind="ego",
                             declared=gt.DeclaredBox((1.416, 0.0, 0.744), (4.792, 2.163, 1.488)),
                             origin_offset=gt.OriginOffset(*off), sim_id=1, asset="t",
                             asset_box=None)
    body = gt.Pose6(317.8, -129.5, 0, 0, 0, math.pi - 0.01)
    trace = gt.Trace(episode=gt.Episode(schema=2, episode=1, start_unix=0.0,
                                        npc_motion="tracked", map="m", step_time=0.05))
    trace.entities["ego"] = header
    fr = gt.Frame(frame=7, sim_time=0.35, sim_frame=107, sim_time_ns=10**12, entities={
        "ego": gt.EntityState(ssv2=body, sim_pose=body, velocity=(-8.0, 0.1, 0.0),
                              angular_velocity=(0, 0, 0), velocity_source="measured")})
    box = T.boxes(trace, fr)["ego"]

    class Msg:
        frame, sim_frame, sim_time_ns = 7, 107, 10**12
        npc_logic_started = True
        names, present = ["ego"], [True]
        poses = [body.x, body.y, 0, 0, 0, body.yaw]
        velocities = [-8.0, 0.1, 0.0]
        angular_velocities = [0.0, 0.0, 0.0]

    class Ent:
        name, origin_offset = "ego", off

    gate, model = Gate(), Model()
    r = seats.Runner({"walker": model}, "ego", gate, io.StringIO(), step_time=0.05)
    f = seats.frame_of(Msg, seats.offsets_of(type("E", (), {"entities": [Ent]})))
    f["entities"]["walker"] = (0.0, 0.0, 0.0, 0.0, 0.0)
    r.on_frame(f)
    seen = model.seen[0][0]
    e = gg.entity_pose_from_actor(gg.Pose2D(body.x, body.y, body.yaw), *off)
    assert abs(seen["ego_x"] - e.x) < 1e-12 and abs(seen["ego_y"] - e.y) < 1e-12
    again = gg.ssv2_box(e, header.declared.center, header.declared.dimensions)
    assert abs(again.cx - box.cx) < 1e-12 and abs(again.cy - box.cy) < 1e-12
    assert abs(seen["ego_x"] - body.x) > 1.3                 # not the body's pose


def test_a_turning_bodys_velocity_becomes_the_entity_origins():
    """Issue 130: the body 1.387 m ahead of the entity, turning at 0.3 rad/s: the entity's
    velocity is the body's less w x r, here 0.416 m/s less to its left."""
    off = (1.387, 0.0, 0.0)

    class Msg:
        frame, sim_frame, sim_time_ns = 1, 101, 10**12
        npc_logic_started = True
        names, present = ["ego"], [True]
        poses = [10.0, 0.0, 0, 0, 0, 0.0]              # heading +x
        velocities = [8.0, 0.0 + 0.3 * 1.387, 0.0]     # the body's: the entity's 8 m/s + w x r
        angular_velocities = [0.0, 0.0, 0.3]

    x, y, yaw, vx, vy = seats.frame_of(Msg, {"ego": off})["entities"]["ego"]
    assert abs(x - (10.0 - 1.387)) < 1e-12 and abs(y) < 1e-12
    assert abs(vx - 8.0) < 1e-12 and abs(vy) < 1e-12



def test_a_car_follower_reads_its_leader_not_the_ego():
    """092 K13: an idm_follower's observation is its own truth and its leader's; a frame
    without the leader is free road, and one without the ego still answers the follower."""
    from sim_vehicle_ecu.xp import namespace

    from scensim.behaviour.follower import IdmFollower
    lane = {"kind": "lane", "length": 400.0, "speed_limit": 15.0,
            "x": [float(x) for x in range(0, 401, 5)], "y": [0.0] * 81}
    m = IdmFollower([{"lane": "straight", "leader": "lead"}], [0], [{"lane": lane}],
                    namespace("numpy"))
    gate, out = Gate(), io.StringIO()
    r = seats.Runner({"car": m}, "ego", gate, out, step_time=0.05)
    r.on_frame(frame(1, {"ego": None, "car": (10.0, 0.0, 0.0, 10.0, 0.0),
                         "lead": (30.0, 0.0, 0.0, 5.0, 0.0)}))
    r.on_frame(frame(2, {"ego": None, "car": (10.5, 0.0, 0.0, 10.0, 0.0), "lead": None}))
    (f1, c1), (f2, c2) = gate.sent
    assert (f1, f2) == (5001, 5002)
    # closing at 5 m/s on 15.5 m: it brakes; with the lead gone, free road below v0
    assert c1["car"][0] < 10.0 and c2["car"][0] > 10.0
    events = [json.loads(x)["event"] for x in out.getvalue().splitlines()]
    assert events == ["follow", "free"]
