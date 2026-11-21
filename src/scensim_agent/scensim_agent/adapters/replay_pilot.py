"""`replay_pilot`: the ego driven by a fixed command stream, indexed by simulation frame
(scensim roadmap 092 K2.4, the agreement table: the same ego on seats and in batch).

The commands are Autoware's control commands, one per scenario frame:

    {"step_time": 0.05,
     "commands": [{"accel": 0.5, "velocity": 3.0, "steer": 0.0}, ...]}   # JSON or YAML

Command k is published for the k-th world frame after the pilot's start frame f0, the first
world frame after SSv2 engages the ego (the goal arrives); before it the pilot holds (velocity
0, the most braking `hold_accel`); past the last command the last one is held. A world frame
is the world's clock (`/clock`, simulation time) as a frame number, `round((t - BASE_S) /
step_time)` (time-and-ticking.md: every clock is nanos(elapsed) + 1000 s): one command per
frame, whatever the clock's rate, never by wall time.

Every frame is logged (`<run dir>/replay_pilot.jsonl`, or `log:`): the world frame, k (None
while holding), the clock, the command published, and what the car reported back on the
vehicle interface that frame (`/vehicle/status/steering_status`, `velocity_status`), so the
frame a command took effect is read from the log, not assumed. A batch replay takes f0 - S (S
the trace's frames before startNpcLogic, scensim.truth.start_frames) as the steps the ego
holds before command 0, pairing the two by time, not by frame number (243): f0's line's
`clock_ns` is the trace frame's `sim_time_ns`, and that frame's line number less the first's,
less S, is the hold. A world frame the pilot never saw (/clock skipped it) is counted in its
line's `skipped` and warned once, since its command was never sent.

    ros2 run scensim_agent replay_pilot --relay tcp://localhost:5560 --entity ego \\
        --config replay.yaml        # {commands: <file>, ...}

Config: `commands` (the file; required), `log` (default `<run dir>/replay_pilot.jsonl`),
`hold_accel` (-3.0 m/s^2), `use_sim_time` (true).
"""

import json
import sys
import threading
from pathlib import Path

import scensim_agent
from scensim_agent import protocol as P

BASE_S = 1000.0     # every clock's origin (time-and-ticking.md)
DEFAULTS = {"commands": "", "log": "", "hold_accel": -3.0, "use_sim_time": True}
FIELDS = ("accel", "velocity", "steer")


def load_commands(path):
    """(step_time, [ {accel, velocity, steer} ]) from a JSON or YAML file."""
    text = Path(path).read_text()
    try:
        doc = json.loads(text)
    except ValueError:
        import yaml
        doc = yaml.safe_load(text)
    if not isinstance(doc, dict) or "commands" not in doc or "step_time" not in doc:
        raise ValueError(f"{path}: needs step_time and commands")
    dt = float(doc["step_time"])
    if dt <= 0:
        raise ValueError(f"{path}: step_time {dt} is not positive")
    cmds = []
    for i, c in enumerate(doc["commands"]):
        missing = [f for f in FIELDS if f not in c]
        if missing:
            raise ValueError(f"{path}: commands[{i}] has no {', '.join(missing)}")
        cmds.append({f: float(c[f]) for f in FIELDS})
    if not cmds:
        raise ValueError(f"{path}: no commands")
    return dt, cmds


def world_frame(t, step_time):
    """The world frame of clock reading `t` (s)."""
    return round((t - BASE_S) / step_time)


class Replay:
    """What to publish each world frame: no ROS, no clock of its own."""

    def __init__(self, step_time, commands, hold_accel=-3.0):
        self.dt, self.commands, self.hold_accel = step_time, commands, hold_accel
        self.armed = False      # the goal has arrived: start at the next frame
        self.f0 = None
        self.last = None
        self.skipped = 0        # world frames between the last two seen, this frame

    def reset(self):
        self.armed, self.f0, self.last, self.skipped = False, None, None, 0

    def arm(self):
        self.armed = True

    def disarm(self):
        self.armed, self.f0 = False, None

    def frame(self, f):
        """(k, command) for world frame `f`, or None when `f` is not a new frame."""
        if self.last is not None and f <= self.last:
            return None
        self.skipped = 0 if self.last is None else f - self.last - 1
        self.last = f
        if self.armed and self.f0 is None:
            self.f0 = f
        if self.f0 is None:
            return None, {"accel": self.hold_accel, "velocity": 0.0, "steer": 0.0}
        k = f - self.f0
        return k, self.commands[min(k, len(self.commands) - 1)]


class RosVehicle:
    """The vehicle interface in the pilot's domain: /clock and the status in, the commands
    out, one call to `on_frame` per new world frame."""

    def __init__(self, cfg, entity, step_time, on_frame, log):
        import rclpy
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.parameter import Parameter
        from rclpy.qos import QoSProfile, ReliabilityPolicy
        from autoware_control_msgs.msg import Control
        from autoware_vehicle_msgs.msg import GearCommand, SteeringReport, VelocityReport
        from rosgraph_msgs.msg import Clock

        self.Control, self.GearCommand = Control, GearCommand
        if not rclpy.ok():
            rclpy.init()
        name = "replay_pilot" if entity == "ego" else f"replay_pilot_{entity}"
        self.node = n = rclpy.create_node(name, parameter_overrides=[
            Parameter("use_sim_time", value=bool(cfg["use_sim_time"]))])
        reliable = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE)
        self.dt, self.on_frame, self.log = step_time, on_frame, log
        self._lock = threading.Lock()
        self.status = {"steering": None, "velocity": None}
        n.create_subscription(Clock, "/clock", self._on_clock, 10)
        n.create_subscription(SteeringReport, "/vehicle/status/steering_status",
                              lambda m: self._set("steering", float(m.steering_tire_angle)),
                              reliable)
        n.create_subscription(VelocityReport, "/vehicle/status/velocity_status",
                              lambda m: self._set("velocity", float(m.longitudinal_velocity)),
                              reliable)
        self.control = n.create_publisher(Control, "/control/command/control_cmd", reliable)
        self.gear = n.create_publisher(GearCommand, "/control/command/gear_cmd", reliable)
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(n)
        threading.Thread(target=self._executor.spin, daemon=True).start()

    def _set(self, k, v):
        with self._lock:
            self.status[k] = v

    def _on_clock(self, msg):
        t = msg.clock.sec + msg.clock.nanosec * 1e-9
        with self._lock:
            status = dict(self.status)
        self.on_frame(world_frame(t, self.dt), t, status)

    def publish(self, cmd):
        stamp = self.node.get_clock().now().to_msg()
        c = self.Control()
        c.stamp = c.control_time = stamp
        c.lateral.stamp = c.lateral.control_time = stamp
        c.lateral.steering_tire_angle = cmd["steer"]
        c.longitudinal.stamp = c.longitudinal.control_time = stamp
        c.longitudinal.velocity = cmd["velocity"]
        c.longitudinal.acceleration = cmd["accel"]
        self.control.publish(c)
        g = self.GearCommand()
        g.stamp, g.command = stamp, self.GearCommand.DRIVE
        self.gear.publish(g)

    def close(self):
        self._executor.shutdown()
        self.node.destroy_node()


class ReplayPilotAgent(scensim_agent.Agent):
    """A fixed command stream by simulation frame. See the module docstring."""

    name = "replay_pilot"

    def __init__(self, config=None, vehicle=None):
        super().__init__(config)
        self.cfg = {**DEFAULTS, **{k: v for k, v in self.config.items() if k in DEFAULTS}}
        if not self.cfg["commands"]:
            raise ValueError("replay_pilot: give commands: <file>")
        dt, cmds = load_commands(self.cfg["commands"])
        self.replay = Replay(dt, cmds, float(self.cfg["hold_accel"]))
        log = self.cfg["log"] or (Path(self.run_dir) / "replay_pilot.jsonl" if self.run_dir
                                  else None)
        self._out = open(log, "a") if log else None
        self._lock = threading.Lock()
        self._warned_skip = False
        self.vehicle = vehicle if vehicle is not None else RosVehicle(
            self.cfg, self.entity, dt, self.on_frame, self.log)
        self.log.info(f"{len(cmds)} commands at {dt:g} s from {self.cfg['commands']}"
                      + (f"; log {log}" if log else ""))

    def on_frame(self, f, t, status):
        with self._lock:
            got = self.replay.frame(f)
            if got is None:
                return
            k, cmd = got
            self.vehicle.publish(cmd)
            skipped = self.replay.skipped
            if skipped and not self._warned_skip:
                self.log.warning(f"world frame {f}: {skipped} frame(s) before it never seen on "
                                 "/clock: their commands were not sent")
                self._warned_skip = True
            if self._out is not None:
                self._out.write(json.dumps({"frame": f, "k": k, "clock": t,
                                            "clock_ns": round(t * 1e9), "skipped": skipped,
                                            "cmd": cmd, "status": status}) + "\n")
                self._out.flush()

    def on_reset(self, ep):
        with self._lock:
            self.replay.reset()
            if self._out is not None:
                self._out.write(json.dumps({"reset": True}) + "\n")
        self.report(P.IDLE, detail="")

    def on_goal(self, goal, waypoints):
        with self._lock:
            self.replay.arm()
        self.report(P.DRIVING, detail="")

    def on_speed_limit(self, mps):
        """Accepted and logged: the commands are fixed, so a limit changes none of them (an
        Autoware-controlled ego's scenario sets one at its start; refusing it ends the run)."""
        with self._lock:
            if self._out is not None:
                self._out.write(json.dumps({"speed_limit": mps}) + "\n")
                self._out.flush()

    def on_stop(self):
        with self._lock:
            self.replay.disarm()

    def on_clear_goal(self):
        self.on_stop()
        self.report(P.IDLE)

    def close(self):
        if self._out is not None:
            self._out.close()
        self.vehicle.close()


def main(argv=None):
    return scensim_agent.main(ReplayPilotAgent, argv)


if __name__ == "__main__":
    sys.exit(main())
