"""Behaviour models on seats (roadmap 092 K10, K12): a testbench attachment that runs each
model its scenario names for the entities it commands, on the truth stream, and sends their
commands with the tick gate's datagrams, so the world server moves them.

    attachments:
      - name: walkers
        run: [python3, -m, scensim.behaviour.seats]
        lockstep: true                # DONE <frame> + commands; false: CMD, never waited for
        commands: [walker]            # each a pedestrian whose controller is `model`

Each model is built as the batch builds it (scensim_batch: the scenario compiled for this run's
record, the anchors by `model_anchors` on the run's map), for one slot, on numpy. Per truth
frame it reads its own entity's pose and the ego's truth (the ego's acceleration differenced
from its velocity over the frame), each the entity's pose: the truth carries the simulator's
body pose, and the body's `origin_offset` (the latched entities topic) is taken back off, as
`scensim.truth.boxes` does (issue 130). A frame's entity whose offset has not arrived yet is
absent for that frame. Velocities are the entity origin's too (the body's, less the yaw rate
times the offset). The model steps, and the frame's commands go out as one datagram answering
that frame's `sim_frame`. A model whose entity or the ego is absent from a frame
sends nothing for it (the world keeps its last command). Before SSv2 starts NPC logic (the
frame's `npc_logic_started` false, the frames S) no model steps or commands, as SSv2 holds its
own NPCs (issue 163); each frame is still answered. Its decisions (the model's events)
are written, one JSON line per event, to `$SCENSIM_ATTACHMENT_DIR/decisions.jsonl` (D6),
where K10's agreement check reads them.

Its environment is the attachment's (scensim.attachments): SCENSIM_SCENARIO,
SCENSIM_PARAMETERS, SCENSIM_COMMANDS, SCENSIM_TICK_GATE, SCENSIM_LOCKSTEP, SCENSIM_MAP_DIR,
SCENSIM_RUN_DIR (its `sample.json`, when the run is sampled, gives the record and seeds),
SCENSIM_RUN_SEED and SCENSIM_TRUTH_TOPIC. SCENSIM_STEP_TIME (s) is the first frame's dt, which
has no previous frame to difference (default 0.05).
"""
import json
import os
import signal
import sys
from pathlib import Path

DEFAULT_STEP_TIME = 0.05
DECISIONS = "decisions.jsonl"


class Runner:
    """The runner's core, without ROS: `on_frame` per truth frame, in order."""

    def __init__(self, models, ego, gate, decisions=None, step_time=DEFAULT_STEP_TIME):
        import numpy as np
        self.np = np
        self.models = dict(models)       # entity -> model (one slot, numpy)
        self.ego, self.gate, self.decisions = ego, gate, decisions
        self.step_time = step_time
        self.prev_t = self.prev_v = None

    def on_frame(self, frame: dict) -> dict:
        """`frame`: {"frame", "sim_frame", "sim_time_ns", "npc_logic_started", "entities":
        {name: (x, y, yaw, vx, vy) or None when absent}}. Sends the frame's datagram; returns
        its commands (none before SSv2 starts NPC logic, issue 163)."""
        np = self.np
        t = frame.get("sim_time_ns")
        dt = ((t - self.prev_t) / 1e9 if t is not None and self.prev_t is not None
              and t > self.prev_t else self.step_time)
        self.prev_t = t if t is not None else self.prev_t
        ego = frame["entities"].get(self.ego)
        if ego is not None:
            ax, ay = ((0.0, 0.0) if self.prev_v is None else
                      ((ego[3] - self.prev_v[0]) / dt, (ego[4] - self.prev_v[1]) / dt))
            self.prev_v = (ego[3], ego[4])
        commands = {}
        if not frame["npc_logic_started"]:
            # SSv2 holds its NPCs until startNpcLogic, and a model is NPC logic: no step, no
            # command, the entity at its Init pose (issue 163). The frame is still answered,
            # so the tick gate never waits on it.
            self.gate.send(int(frame["sim_frame"]), commands)
            return commands
        for name, m in self.models.items():
            me = frame["entities"].get(name)
            if me is None:
                continue
            if getattr(m, "name", "") == "idm_follower":
                # the car-follower reads its leader, not the ego (092 K13)
                from scensim.behaviour.follower import seats_obs
                obs = seats_obs(me, frame["entities"], m.params[0]["leader"], np)
            else:
                if ego is None:
                    continue
                a = lambda v: np.array([float(v)])   # noqa: E731
                obs = {"x": a(me[0]), "y": a(me[1]), "ego_x": a(ego[0]), "ego_y": a(ego[1]),
                       "ego_vx": a(ego[3]), "ego_vy": a(ego[4]), "ego_ax": a(ax),
                       "ego_ay": a(ay), "valid": np.array([True])}
            act, ev = m.step(obs, dt)
            commands[name] = (float(act["speed"][0]), float(act["heading"][0]),
                              float(act["accel_limit"][0]))
            e = int(np.asarray(ev)[0])
            if e and self.decisions is not None:
                events = getattr(m, "events", None)
                if events is None:
                    from scensim.behaviour.walker import EVENTS as events
                self.decisions.write(json.dumps({"frame": frame["frame"],
                                                 "sim_frame": frame["sim_frame"],
                                                 "entity": name,
                                                 "event": events.get(e, str(e))}) + "\n")
                self.decisions.flush()
        self.gate.send(int(frame["sim_frame"]), commands)
        return commands


def record_of(env) -> dict:
    """The run's sample record (its `sample.json`), else one from its parameters and seed."""
    run_dir = Path(env.get("SCENSIM_RUN_DIR", "."))
    p = run_dir / "sample.json"
    if p.is_file():
        rec = json.loads(p.read_text())
    else:
        seed = env.get("SCENSIM_RUN_SEED") or "0"
        rec = {"seeds": {"scenario": int(seed)}}
    rec.setdefault("values", {}).update(json.loads(env.get("SCENSIM_PARAMETERS") or "{}"))
    return rec


def build(env) -> tuple:
    """(models, ego): each commanded entity's model as the batch builds it, for one slot."""
    from scensim_batch.compile import compile_scenario
    from scensim_batch.core import model_anchors
    from scensim_batch.map_export import export
    from scensim_batch.world_lanelet import LaneletWorld
    from sim_vehicle_ecu.xp import namespace

    from scensim import behaviour
    scenario = env.get("SCENSIM_SCENARIO") or ""
    map_dir = env.get("SCENSIM_MAP_DIR") or ""
    if not scenario or not map_dir:
        raise SystemExit("scensim.behaviour.seats: SCENSIM_SCENARIO and SCENSIM_MAP_DIR are "
                         "required (a testbench attachment has them)")
    doc = export(map_dir)
    world = LaneletWorld(doc["lanelets"], doc["map"], doc["map_sha256"])
    c = compile_scenario(scenario, [record_of(env)], world)
    names = [e.name for e in c.entities]
    egos = [i for i, e in enumerate(c.entities) if e.role == "ego"]
    if len(egos) != 1:
        raise SystemExit(f"{scenario}: {len(egos)} egos; a model reads one ego's truth")
    models, xp = {}, namespace("numpy")
    for name in json.loads(env.get("SCENSIM_COMMANDS") or "[]"):
        if name not in names:
            raise SystemExit(f"{scenario}: no entity {name!r}")
        i = names.index(name)
        spec = c.entities[i].model
        if c.entities[i].role != "model" or not spec:
            raise SystemExit(f"{scenario}: {name!r} names no behaviour model "
                             "(<Property name=\"model\" value=\"scensim.behaviour:...\"/>)")
        cls = behaviour.MODELS[spec["model"]]
        if spec["model"] == "idm_follower":
            # its lane from the map's resolved anchors (092 K13)
            from scensim.behaviour.follower import lane_anchors
            from scensim_sampler import anchors as A
            f = Path(map_dir) / A.RESOLVED
            resolved = A.load_resolved(f, map_dir=map_dir) if f.is_file() else {}
            anchors = lane_anchors(spec["params"], resolved)
        else:
            anchors = model_anchors(c, world, i, egos[0])
        models[name] = cls(spec["params"], spec["seeds"], anchors, xp)
    return models, names[egos[0]]


def entity_pose(x, y, yaw, offset):
    """The entity's (x, y, yaw) from the body's and its `origin_offset` (x, y m, yaw rad):
    gap_geometry.entity_pose_from_actor, the inverse of where the world placed the body."""
    from scensim.truth import _module
    gg = _module("gap_geometry")
    e = gg.entity_pose_from_actor(gg.Pose2D(x, y, yaw), *offset)
    return e.x, e.y, e.yaw


def entity_velocity(vx, vy, wz, x_body, y_body, x_entity, y_entity):
    """The entity origin's map-frame (vx, vy) from the body origin's: v - w x r, r the body
    origin from the entity's (a rigid body; yaw rate wz)."""
    rx, ry = x_body - x_entity, y_body - y_entity
    return vx + wz * ry, vy - wz * rx


def offsets_of(msg) -> dict:
    """{name: origin_offset} from a TruthEntities message."""
    return {e.name: tuple(e.origin_offset) for e in msg.entities}


def frame_of(msg, offsets) -> dict:
    """A TruthFrame message as `Runner.on_frame` takes it, each pose the entity's (`offsets`,
    {name: origin_offset}); an entity without an offset yet is absent."""
    ents = {}
    for k, name in enumerate(msg.names):
        if not msg.present[k] or name not in offsets:
            ents[name] = None
            continue
        p, v = msg.poses[6 * k:6 * k + 6], msg.velocities[3 * k:3 * k + 3]
        x, y, yaw = entity_pose(p[0], p[1], p[5], offsets[name])
        wz = msg.angular_velocities[3 * k + 2]
        ents[name] = (x, y, yaw, *entity_velocity(v[0], v[1], wz, p[0], p[1], x, y))
    return {"frame": msg.frame, "sim_frame": msg.sim_frame, "sim_time_ns": msg.sim_time_ns,
            "npc_logic_started": bool(msg.npc_logic_started), "entities": ents}


def main(argv=None) -> int:
    import rclpy
    from rclpy.qos import QoSProfile, ReliabilityPolicy
    from rclpy.qos import DurabilityPolicy
    from scensim_interfaces.msg import TruthEntities, TruthFrame

    from scensim.attachments import CommandGate, TRUTH_TOPIC
    env = dict(os.environ)
    models, ego = build(env)
    out_dir = Path(env.get("SCENSIM_ATTACHMENT_DIR") or ".")
    out_dir.mkdir(parents=True, exist_ok=True)
    step = float(env.get("SCENSIM_STEP_TIME") or DEFAULT_STEP_TIME)
    with CommandGate() as gate, open(out_dir / DECISIONS, "a") as decisions:
        runner = Runner(models, ego, gate, decisions, step)
        rclpy.init()
        node = rclpy.create_node("scensim_behaviour_seats")
        topic = env.get("SCENSIM_TRUTH_TOPIC") or TRUTH_TOPIC
        offsets = {}
        node.create_subscription(TruthEntities, topic + "/entities",
                                 lambda m: offsets.update(offsets_of(m)),
                                 QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                                            durability=DurabilityPolicy.TRANSIENT_LOCAL))
        node.create_subscription(TruthFrame, topic,
                                 lambda m: runner.on_frame(frame_of(m, offsets)),
                                 QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE))
        signal.signal(signal.SIGTERM, lambda *_: rclpy.try_shutdown())
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            pass
        finally:
            node.destroy_node()
            rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
