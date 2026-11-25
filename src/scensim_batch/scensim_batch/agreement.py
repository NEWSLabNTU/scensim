"""K2.4's agreement between a seats run and a batch replay of it (roadmap 092; batch-executor.md
section 8): no simulator here, only the two runs' records.

The seats side is the run directory: its truth (gap trace: each entity's pose per SSv2 frame,
`npc_logic_started`), its storyboard log (`context.jsonl`: each element's state changes at
SSv2's time) and the replay pilot's log (`replay_pilot.jsonl`: the world frame each command
went out on). The batch side is what the runner records per batch step k: every entity's
pose, the storyboard elements' states and the outcome.

Frames are paired on scenario time: seats frame S + k (S, the frames before startNpcLogic,
`scensim.truth.start_frames`) is batch step k, both at scenario time k dt. The ego's commands
start on seats at world frame f0 (the replay pilot's first command); that frame's trace line
less S is the steps the batch ego holds before its command 0 (`hold_steps`), paired by time
(the line whose `sim_time_ns` is f0's clock), not by frame number (243).

    table = agreement.compare(seats, batch)     # per entity: max and RMS position error,
                                                # per element: first-running and complete
                                                # steps on each side; the two outcomes
"""
import json
import math
from pathlib import Path

RUNNING, COMPLETE = "runningState", "completeState"


# --- the seats side ----------------------------------------------------------------------------

def replay_log(path):
    """The replay pilot's frame lines (after its last reset)."""
    rows = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        if o.get("reset"):
            rows = []
        elif "frame" in o:          # not a speed_limit line
            rows.append(o)
    return rows


def first_command(rows):
    """The replay log line of command 0, or None when the pilot never started."""
    return next((r for r in rows if r.get("k") == 0), None)


def hold_steps(trace, start_frames, command0):
    """Batch steps the ego holds before command 0: the trace line at command 0's clock, as a
    count of lines from the first, less S. None when no line has that clock."""
    frames = sorted(trace.frames, key=lambda f: f.frame)
    ns = command0["clock_ns"]
    for f in frames:
        if f.sim_time_ns is not None and f.sim_time_ns == ns:
            return (f.frame - frames[0].frame) - start_frames
    return None


def seats_poses(trace, start_frames, steps, entities, pose="ssv2", shift=None):
    """{entity: [(x, y, yaw) | None] for k in 0..steps-1}: seats frame S + k's poses. `pose`
    {entity: "ssv2" | "sim"}, or one for all: SSv2's pose (what it drives) or the simulator's
    (what physics did: the ego's), the latter as the entity's, the truth's `origin_offset`
    taken off (issue 130), so it compares with the batch's entity poses. `shift` {entity:
    frames}: that entity's pose from frame S + k + shift (092 K10: a commanded walker moves a
    frame after the truth its model read)."""
    gg = _gap_geometry()
    frames = sorted(trace.frames, key=lambda f: f.frame)
    first = frames[0].frame
    by = {f.frame: f for f in frames}
    out = {e: [] for e in entities}
    shift = shift or {}
    for k in range(steps):
        for e in entities:
            f = by.get(first + start_frames + k + shift.get(e, 0))
            which = pose.get(e, "ssv2") if isinstance(pose, dict) else pose
            st = None if f is None else f.entities.get(e)
            p = None if st is None else (st.sim_pose if which == "sim" else st.ssv2)
            if p is not None and which == "sim":
                o = trace.entities[e].origin_offset
                p = gg.entity_pose_from_actor(gg.Pose2D(p.x, p.y, p.yaw), o.x, o.y, o.yaw)
            out[e].append(None if p is None else (p.x, p.y, p.yaw))
    return out


def ego_states(trace, start_frames, steps, ego):
    """The seats ego at frames S + k, k in 0..steps-1, for TruthPlayback (092 K10): the
    entity's pose (the simulator's body pose with the truth's `origin_offset` taken back off,
    as scensim.truth.boxes does; issue 130) and its map-frame velocity (the truth's body
    velocity less the yaw rate times the offset), as the seats attachment reads them. A frame
    without the ego holds the last state."""
    gg = _gap_geometry()
    o = trace.entities[ego].origin_offset
    frames = sorted(trace.frames, key=lambda f: f.frame)
    first = frames[0].frame
    by = {f.frame: f for f in frames}
    out, last = [], None
    for k in range(steps):
        f = by.get(first + start_frames + k)
        st = None if f is None else f.entities.get(ego)
        if st is not None:
            p = gg.entity_pose_from_actor(gg.Pose2D(st.sim_pose.x, st.sim_pose.y,
                                                    st.sim_pose.yaw), o.x, o.y, o.yaw)
            # the entity origin's velocity: the body's less w x r (r body from entity)
            wz = st.angular_velocity[2]
            rx, ry = st.sim_pose.x - p.x, st.sim_pose.y - p.y
            last = {"x": p.x, "y": p.y, "yaw": p.yaw,
                    "vx_map": st.velocity[0] + wz * ry, "vy_map": st.velocity[1] - wz * rx}
        if last is None:
            raise ValueError(f"the truth has no {ego!r} at frame {first + start_frames + k}")
        out.append(dict(last))
    return out


def run_record(run_dir):
    """The record a seats run's attachment built its models from (scensim.behaviour.seats's
    record_of): the run's sample.json, else its seed and parameters from result.json."""
    run_dir = Path(run_dir)
    p = run_dir / "sample.json"
    sc = {}
    if (run_dir / "result.json").exists():
        sc = json.loads((run_dir / "result.json").read_text()).get("scenario") or {}
    if p.is_file():
        rec = json.loads(p.read_text())
    else:
        seed = sc.get("seed")
        rec = {"seeds": {"scenario": int(seed if seed is not None else 0)}}
    rec.setdefault("values", {}).update(sc.get("parameters") or {})
    return rec


def seats_decisions(path, start_frames, first_frame):
    """{entity: [(step, event)]} from the seats attachment's decisions.jsonl (092 K12 D6): a
    decision written for truth frame f is batch step f - first - S, the step whose ego it read."""
    out = {}
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        if line.strip():
            o = json.loads(line)
            out.setdefault(o["entity"], []).append(
                (o["frame"] - first_frame - start_frames, o["event"]))
    return out


def decisions_agree(seats, batch):
    """{entity: {seats, batch, agree}}: the same events at the same steps, per model entity."""
    return {e: {"seats": seats.get(e, []), "batch": batch.get(e, []),
                "agree": seats.get(e, []) == batch.get(e, [])}
            for e in sorted(set(seats) | set(batch))}


def taken_commands(trace, start_frames, steps, ego):
    """[TakenCommand | None for k in 0..steps-1]: the command the seats ego ran in the step
    that ended at frame S + k (the truth's `command`, 092 K2.4); None where the frame has none
    (no command yet, or a world server that does not report it)."""
    frames = sorted(trace.frames, key=lambda f: f.frame)
    first = frames[0].frame
    by = {f.frame: f for f in frames}
    out = []
    for k in range(steps):
        f = by.get(first + start_frames + k)
        st = None if f is None else f.entities.get(ego)
        out.append(None if st is None else getattr(st, "command", None))
    return out


def taken_before(trace, start_frames, ego):
    """[TakenCommand | None]: what the seats ego ran in the steps up to scenario time 0, the
    trace's lines 0..S (the frames before startNpcLogic and the one it began on): a batch
    pre-roll of the ego (BatchRun.reset's `preroll`), so it starts the scenario as seats did,
    its brake held by the pilot's hold or already pulling (092 K2.4)."""
    frames = sorted(trace.frames, key=lambda f: f.frame)[:start_frames + 1]
    return [None if f.entities.get(ego) is None else getattr(f.entities[ego], "command", None)
            for f in frames]


def delivery(trace, ego, step_time):
    """How the seats ego's commands reached its vehicle, over the frames that ran one:
    `delay` {frames: count}, the frames between the frame a command answered (its stamp) and
    the step it ran in, less one (0: the next step, as the batch has it); `superseded`, the
    commands that arrived with a later one and never ran (arrived above 1); `repeated`, the
    frames that ran an older command again (arrived 0)."""
    step_ns = round(step_time * 1e9)
    delay, superseded, repeated, frames = {}, 0, 0, 0
    prev_ns = None
    last_ns = None       # the previous frame's sim_time_ns: the step's start (243)
    for f in sorted(trace.frames, key=lambda f: f.frame):
        st = f.entities.get(ego)
        c = None if st is None else getattr(st, "command", None)
        start_ns, last_ns = last_ns, f.sim_time_ns
        if c is None or f.sim_time_ns is None or start_ns is None:
            continue
        frames += 1
        d = round((start_ns - c.stamp_ns) / step_ns)
        if d < 0:
            raise ValueError(
                f"frame {f.frame}: the command it ran is stamped {c.stamp_ns}, after its step "
                f"began ({start_ns}): the sender's clock is not the truth's sim_time_ns (a run "
                "on another clock_source?), so no delay can be read")
        delay[d] = delay.get(d, 0) + 1
        superseded += max(c.arrived - 1, 0)
        repeated += c.arrived == 0 and c.stamp_ns == prev_ns
        prev_ns = c.stamp_ns
    return {"frames": frames, "delay": dict(sorted(delay.items())),
            "superseded": superseded, "repeated": int(repeated)}


def context_steps(path, step_time):
    """{element path: {state: the first step k (at scenario time k dt) it entered}} from the
    storyboard log's state changes. Its `sim` is the time of the context SSv2 published, after
    the frame's update (evaluate at T, update to T + dt, publish: the interpreter's
    evaluate_storyboard), so the evaluation that made a change was a step before. Except an
    exit's: exitSuccess and exitFailure throw in the evaluate, and the handler publishes before
    any update, at the evaluation's own time (243). That is the log's last time, with an action
    starting in it."""
    rows = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        if o.get("ev") != "state" or o.get("sim") is None:
            continue
        rows.append(o)
    last = max((float(o["sim"]) for o in rows), default=None)
    exit_tick = any(float(o["sim"]) == last and o["element"].count("/") >= 5
                    and o["to"] in ("startTransition", RUNNING) for o in rows)
    out = {}
    for o in rows:
        at_exit = exit_tick and float(o["sim"]) == last
        k = round(float(o["sim"]) / step_time) - (0 if at_exit else 1)
        out.setdefault(o["element"], {}).setdefault(o["to"], k)
    return out


# --- the batch side ----------------------------------------------------------------------------

def element_paths(storyboard):
    """{path: node} of the batch storyboard's elements, as the storyboard log names them
    (story/act/group/maneuver/event[/action])."""
    out = {}

    def walk(x, prefix):
        for ch in x.children:
            path = f"{prefix}/{ch.name}" if prefix else ch.name
            out[path] = ch
            walk(ch, path)

    walk(storyboard.root, "")
    return out


def batch_only(compiled) -> list:
    """Issue 175: the model entities a compiled scenario starts at an Init speed, which seats
    refuse (a known divergence between the batch and seats): no agreement check may use it."""
    return [compiled.entities[i].name for i in compiled.of_role("model")
            if bool(compiled.speed_set[:, i].any())]


def event_names(compiled) -> dict:
    """{model entity: {event code: name}}: each model's own `events` table, as the seats runner
    names them (issue 164; the walker's table only for a model that has none)."""
    from scensim import behaviour
    from scensim.behaviour.walker import EVENTS
    out = {}
    for e in compiled.entities:
        if e.role == "model" and e.model:
            out[e.name] = getattr(behaviour.MODELS[e.model["model"]], "events", None) or EVENTS
    return out


class BatchRecorder:
    """What the runner records per batch step of slot `slot`: poses and element states."""

    NAMES = {0: "standbyState", 1: RUNNING, 2: COMPLETE}

    def __init__(self, run, slot=0):
        self.run, self.slot = run, slot
        self.paths = element_paths(run.storyboard) if run.storyboard is not None else {}
        self.poses = {e.name: [] for e in run.c.entities}
        self.steps = {}
        self.decisions = {}      # {model entity: [(step, event)]} (092 K10)
        self.event_names = event_names(run.c)
        self.k = 0

    def record(self, obs):
        names = [e.name for e in self.run.c.entities]
        for i, n in enumerate(names):
            self.poses[n].append((float(obs["x"][self.slot, i]), float(obs["y"][self.slot, i]),
                                  float(obs["yaw"][self.slot, i])))
        sb = self.run.storyboard
        for path, node in self.paths.items():
            name = self.NAMES.get(int(sb.state[id(node)][self.slot]))
            if name is not None:
                self.steps.setdefault(path, {}).setdefault(name, self.k)
        if obs.get("model_events"):
            for ent, ev in obs["model_events"].items():
                e = int(ev[self.slot])
                if e:
                    names = self.event_names.get(ent, {})
                    self.decisions.setdefault(ent, []).append((self.k, names.get(e, str(e))))
        self.k += 1


# --- the comparison ----------------------------------------------------------------------------

def _gap_geometry():
    """scensim_launch's gap_geometry (its scripts on the path, as the truth reader is)."""
    import gap_geometry
    return gap_geometry


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def trajectory_error(seats, batch):
    """{entity: {frames, max_m, rms_m, max_yaw_rad, missing}} over the steps both have."""
    out = {}
    for e, b in batch.items():
        s = seats.get(e)
        if s is None:
            continue
        d2, dy, missing = [], [], 0
        for p, q in zip(s, b):
            if p is None or q is None:
                missing += 1
                continue
            d2.append((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2)
            dy.append(abs(_wrap(p[2] - q[2])))
        out[e] = {"frames": len(d2), "missing": missing,
                  "max_m": math.sqrt(max(d2)) if d2 else None,
                  "rms_m": math.sqrt(sum(d2) / len(d2)) if d2 else None,
                  "max_yaw_rad": max(dy) if dy else None}
    return out


def trigger_steps(seats, batch, states=(RUNNING, COMPLETE)):
    """{element: {state: (seats step, batch step, batch - seats)}} for the elements either side
    names; a side that never entered the state has None."""
    out = {}
    for el in sorted(set(seats) | set(batch)):
        row = {}
        for st in states:
            a, b = seats.get(el, {}).get(st), batch.get(el, {}).get(st)
            row[st] = (a, b, None if a is None or b is None else b - a)
        out[el] = row
    return out


def compare(seats, batch):
    """The agreement table's row: `seats` and `batch` are {poses, steps, outcome}."""
    traj = trajectory_error(seats["poses"], batch["poses"])
    trig = trigger_steps(seats["steps"], batch["steps"])
    dec = ({"decisions": decisions_agree(seats.get("decisions", {}), batch.get("decisions", {}))}
           if seats.get("decisions") or batch.get("decisions") else {})
    return {"outcome": {"seats": seats["outcome"], "batch": batch["outcome"],
                        "agree": seats["outcome"] == batch["outcome"]},
            "trajectory": traj, "triggers": trig, **dec,
            "trigger_offsets": sorted({r[2] for row in trig.values() for r in row.values()
                                       if r[2] is not None})}
